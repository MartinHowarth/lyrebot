import asyncio
import discord
import logging
import os
import time
import yaml

from discord.ext import commands
from textwrap import dedent

from lyrebot.lyrebird import generate_voice_for_text, generate_oauth2_url, generate_oauth2_token

log = logging.getLogger(__name__)

THUMBS_UP = "\U0001F44D"
THUMBS_DOWN = u"\U0001F44E"
CLOCK = "\U0001F550"


if not discord.opus.is_loaded():
    # the 'opus' library here is opus.dll on windows
    # or libopus.so on linux in the current directory
    # you should replace this with the location the
    # opus library is located in and with the proper filename.
    # note that on windows this DLL is automatically provided for you
    discord.opus.load_opus('opus')


class VoiceEntry:
    def __init__(self, message, player):
        self.requester = message.author
        self.channel = message.channel
        self.player = player

    def __str__(self):
        fmt = '*{0.title}* uploaded by {0.uploader} and requested by {1.display_name}'
        duration = self.player.duration
        if duration:
            fmt = fmt + ' [length: {0[0]}m {0[1]}s]'.format(divmod(duration, 60))
        return fmt.format(self.player, self.requester)


class VoiceState:
    def __init__(self, bot):
        self.current = None
        self.voice = None
        self.bot = bot
        self.speech_queue = asyncio.Queue()
        self.audio_player = self.bot.loop.create_task(self.audio_player_task())

    @property
    def player(self):
        return self.current.player

    async def no_audio_is_playing(self):
        while True:
            if self.voice is None or self.current is None:
                break

            player = self.current.player
            if player.is_done():
                break
            log.debug("Waiting for audio to finish")
            time.sleep(0.5)

    async def audio_player_task(self):
        while True:
            await self.no_audio_is_playing()
            self.current = await self.speech_queue.get()
            log.info("Got new speech from the queue.")
            self.current.player.start()


class LyreBot:
    """Voice related commands.

    Works in multiple servers at once.
    """
    def __init__(self, bot, lyre_client_id, lyre_client_secret, lyre_redirect_uri):
        self.bot = bot
        self.voice_states = {}
        self.lyrebird_tokens = {}  # Map from player to lyrebird auth tokens
        self._lyre_auth_state_cache = {}
        self.lyre_client_id = lyre_client_id
        self.lyre_client_secret = lyre_client_secret
        self.lyre_redirect_uri = lyre_redirect_uri
        self.volume = 1
        self.not_always_speak_users = []

    def get_voice_state(self, server):
        state = self.voice_states.get(server.id)
        if state is None:
            state = VoiceState(self.bot)
            self.voice_states[server.id] = state

        return state

    async def create_voice_client(self, channel):
        voice = await self.bot.join_voice_channel(channel)
        state = self.get_voice_state(channel.server)
        state.voice = voice

    def __unload(self):
        for state in self.voice_states.values():
            try:
                state.audio_player.cancel()
                if state.voice:
                    self.bot.loop.create_task(state.voice.disconnect())
            except:
                pass

    async def _summon(self, message):
        log.debug("Being summoned...")
        summoned_channel = message.author.voice_channel
        if summoned_channel is None:
            await self.bot.say('You are not in a voice channel.')
            return False

        state = self.get_voice_state(message.server)
        if state.voice is None:
            state.voice = await self.bot.join_voice_channel(summoned_channel)
        else:
            await state.voice.move_to(summoned_channel)

        return True

    @commands.command(pass_context=True, no_pm=True)
    async def volume(self, ctx, value: int):
        """Sets the volume of this bot."""
        log.debug("Setting volume...")

        state = self.get_voice_state(ctx.message.server)
        player = state.player
        self.volume = value / 100
        await self.bot.say('Set the volume to {:.0%}'.format(player.volume))

    @commands.command(pass_context=True)
    async def set_token(self, ctx, token: str):
        """Sets the Lyrebird API token."""
        user = ctx.message.author
        log.debug("Setting lyre token for user: %s", user)
        self.lyrebird_tokens[user.name] = token
        await self.bot.add_reaction(ctx.message, THUMBS_UP)

    @commands.command(pass_context=True)
    async def generate_token_uri(self, ctx):
        """Step 1 to generate your token. Call this command and follow the instructions."""
        user = ctx.message.author
        log.debug("Getting lyre oauth uri for user: %s", user)
        auth_url, state = generate_oauth2_url(self.lyre_client_id, self.lyre_redirect_uri)
        self._lyre_auth_state_cache[user] = state
        await self.bot.send_message(
            ctx.message.channel,
            "Please go to this url, authenticate the app, then paste the URL you are "
            "redirected to into the 'generate_token' command")
        await self.bot.send_message(ctx.message.channel, auth_url)

    @commands.command(pass_context=True)
    async def generate_token(self, ctx, callback_uri):
        """Step 2 to generate your token. Provide the url from the 'generate_token_uri' step."""
        user = ctx.message.author
        log.debug("Getting lyre oauth token for user: %s", user)
        token = generate_oauth2_token(
            self.lyre_client_id,
            self.lyre_client_secret,
            self._lyre_auth_state_cache[user],
            callback_uri
        )
        self.lyrebird_tokens['{}#{}'.format(user.name, user.discriminator)] = token
        await self.bot.send_message(
            ctx.message.channel,
            "Your token is '%s'. Please retain it in case I forget myself!" % token)
        await self.bot.send_message(
            ctx.message.channel,
            "You can set it again using the 'set_token' command.")

    async def speak_actual(self, message, *words: str):
        ident = '{}#{}'.format(message.author.name, message.author.discriminator)
        if ident not in self.lyrebird_tokens:
            await self.bot.send_message(
                message.channel,
                "I do not have a lyrebird token for you. Call set_token or generate_token_uri (in a PM)")
            return

        sentence = ' '.join(words)
        log.debug("Echoing '%s' as speech...", sentence)
        await self.bot.add_reaction(message, CLOCK)

        # Join the channel of the person who requested the say
        result = await self._summon(message)
        if not result:
            return

        state = self.get_voice_state(message.server)
        log.debug("Getting voice from lyrebird...")
        voice_bytes = await generate_voice_for_text(
            sentence, self.lyrebird_tokens[ident])
        log.debug("Got voice from lyrebird...")
        user_filename = "{}.wav".format(message.author)
        with open(user_filename, 'wb') as fi:
            fi.write(voice_bytes)

        try:
            state.voice.encoder_options(channels=2, sample_rate=48000)
            player = state.voice.create_ffmpeg_player(
                user_filename,
                after=lambda: os.remove(user_filename)
            )
        except Exception as e:
            fmt = 'An error occurred while processing this request: ```py\n{}: {}\n```'
            await self.bot.send_message(message.channel, fmt.format(type(e).__name__, e))
        else:
            player.volume = self.volume
            entry = VoiceEntry(message, player)
            await state.speech_queue.put(entry)
            await self.bot.add_reaction(message, THUMBS_UP)
            await self.bot.remove_reaction(message, CLOCK, message.server.me)
            log.debug("queued audio.")

    @commands.command(pass_context=True, no_pm=True)
    async def speak(self, ctx, *words: str):
        """Echoes the following text as speech."""
        await self.speak_actual(ctx.message, *words)

    @commands.command(pass_context=True)
    async def always_speak(self, ctx, word):
        """Enter "n" or "no" to disable speaking of everything. Any other entry disables."""
        log.debug("always_speak called with: {}".format(word))
        if word.lower() in ['n', 'no']:
            self.not_always_speak_users.append(ctx.message.author)
            await self.bot.add_reaction(ctx.message, THUMBS_UP)
        else:
            if ctx.message.author in self.not_always_speak_users:
                self.not_always_speak_users.remove(ctx.message.author)
                await self.bot.add_reaction(ctx.message, THUMBS_DOWN)
        log.debug("Always speak users are: {}".format(self.not_always_speak_users))


def create_bot(lyre_client_id, lyre_client_secret, lyre_redirect_uri):
    bot = commands.Bot(
        command_prefix=commands.when_mentioned_or('"'),
        description=dedent(
            """
            This bot echoes what you type into your current voice channel.
            
            Usage: "speak <what you want to say>
            
            First time:
                Set yourself up with a lyrebird account here: https://beta.myvoice.lyrebird.ai/
                Then run "generate_token_uri (in a PM!) and follow the instructions.
                The tokens time out after a year.
            
            Returning users:
                If this bot restarts/dies, it forgets your tokens.
                If you still have your token run "set_token <your token>
            """
        )
    )

    lyrebot = LyreBot(bot, lyre_client_id, lyre_client_secret, lyre_redirect_uri)
    bot.add_cog(lyrebot)

    # Load in some pre-defined tokens for ease of testing.
    # Expects a yaml file of <user name>: token
    # Where the user name is, for example: Alice#1234
    if os.path.exists(".tokens.yaml"):
        log.debug("tokens.yaml exists")
        with open(".tokens.yaml") as fi:
            token_dict = yaml.safe_load(fi)
            log.debug("file tokens are: %s", token_dict)
            for user, token in token_dict.items():
                log.info("loaded token from file for: %s", user)
                lyrebot.lyrebird_tokens[user] = token

    @bot.event
    async def on_ready():
        log.debug('Logged in as:\n{0} (ID: {0.id})'.format(bot.user))

    @bot.event
    async def on_message(message):
        log.debug("message from {}.".format(message.author))
        if not message.content.startswith('"') and message.author not in lyrebot.not_always_speak_users:
            log.debug("Always speaking for {}".format(message.author))
            await lyrebot.speak_actual(message, message.content)
        await bot.process_commands(message)

    return bot
