import discord
import logging
import os
import yaml
import sys

from collections import defaultdict
from discord import FFmpegPCMAudio, PCMVolumeTransformer
from discord.ext import commands
from textwrap import dedent

from lyrebot.lyrebird import generate_voice_for_text, generate_oauth2_url, generate_oauth2_token

log = logging.getLogger(__name__)

OK_HAND = "\U0001F44C"
ARROW_DOWN = "\U0001F53D"
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


class LyreBot(commands.Cog):
    """Voice related commands.

    Works in multiple guilds at once.
    """
    def __init__(self, bot, lyre_client_id, lyre_client_secret, lyre_redirect_uri):
        self.bot = bot
        self.voice_channels = {}
        self.lyrebird_tokens = {}  # Map from player to lyrebird auth tokens
        self._lyre_auth_state_cache = {}
        self.lyre_client_id = lyre_client_id
        self.lyre_client_secret = lyre_client_secret
        self.lyre_redirect_uri = lyre_redirect_uri
        self.volume = 1
        self.always_speak_users_by_channel = defaultdict(list)

    async def get_voice_client(self, channel):
        if channel.guild.id in self.voice_channels:
            log.debug("Already in a voice channel in this guild.")
            vc = self.voice_channels[channel.guild.id]

            if vc.channel != channel:
                log.debug("Moving voice channel from %s to %s", vc.channel, channel)
                await vc.move_to(channel)
        else:
            log.debug("Connecting to voice channel %s", channel)
            vc = await channel.connect()
            self.voice_channels[channel.guild.id] = vc

        log.debug("Got voice client for voice channel %s", channel)
        return vc

    async def summon(self, message):
        log.debug("Being summoned...")
        if message.author.voice is None or message.author.voice.channel is None:
            await message.channel.send('You are not in a voice channel.')
            return None

        log.debug("Being summoned to channel %s", message.author.voice.channel)
        vc = await self.get_voice_client(message.author.voice.channel)
        return vc

    @commands.command(no_pm=True)
    async def volume(self, ctx, value: int):
        """Sets the volume of this bot."""
        log.debug("Setting volume...")

        self.volume = value / 100
        await ctx.message.channel.send('Set the volume to {:.0%}'.format(self.volume))

    @commands.command()
    async def set_token(self, ctx, token: str):
        """Sets the Lyrebird API token. The token should look like `oauth_[random characters]`"""
        log.debug("Setting lyre token for user: %s", ctx.author)
        self.lyrebird_tokens[ctx.author.id] = token
        await ctx.message.add_reaction(THUMBS_UP)

    @commands.command()
    async def generate_token_uri(self, ctx):
        """Step 1 to generate your token. Call this command and follow the instructions."""
        user = ctx.author
        log.debug("Getting lyre oauth uri for user: %s", user)
        auth_url, state = generate_oauth2_url(self.lyre_client_id, self.lyre_redirect_uri)
        self._lyre_auth_state_cache[user.id] = state
        await ctx.channel.send(
            "Please go to this url, authenticate the app, then paste the URL you are "
            "redirected to into the 'generate_token' command")
        await ctx.channel.send(auth_url)

    @commands.command()
    async def generate_token(self, ctx, callback_uri):
        """Step 2 to generate your token. Provide the url from the 'generate_token_uri' step."""
        log.debug("Getting lyre oauth token for user: %s", ctx.author)
        token = generate_oauth2_token(
            self.lyre_client_id,
            self.lyre_client_secret,
            self._lyre_auth_state_cache[ctx.author.id],
            callback_uri
        )
        self.lyrebird_tokens[ctx.author.id] = token
        await ctx.channel.send(
            "Your token is '%s'. Please retain it in case I forget myself!" % token)
        await ctx.channel.send(
            "You can set it again using the 'set_token' command.")

    async def speak_aloud(self, message, *words: str):
        ident = message.author.id
        if ident not in self.lyrebird_tokens:
            await message.channel.send(
                "I do not have a lyrebird token for you. Call set_token or generate_token_uri (in a PM)")
            return

        sentence = ' '.join(words)
        log.debug("Echoing '%s' as speech...", sentence)
        await message.add_reaction(CLOCK)

        # Join the channel of the person who requested the say
        voice_client = await self.summon(message)
        if voice_client is None:
            return

        log.debug("Getting voice from lyrebird...")
        voice_bytes = await generate_voice_for_text(
            sentence, self.lyrebird_tokens[ident])
        log.debug("Got voice from lyrebird...")
        user_filename = "~/{}.wav".format(message.author.id)
        user_filename = os.path.expanduser(user_filename)
        with open(user_filename, 'wb') as fi:
            fi.write(voice_bytes)

        try:
            log.debug("Creating audio source.")
            audio_source = FFmpegPCMAudio(user_filename)
            audio_source = PCMVolumeTransformer(audio_source, volume=self.volume)
            log.debug("Created audio source.")
        except Exception as e:
            fmt = 'An error occurred while processing this request: ```py\n{}: {}\n```'
            await message.channel.send(fmt.format(type(e).__name__, e))
        else:
            def after(err):
                if err:
                    log.error("Error playing media: %s", err)
                os.remove(user_filename)

            voice_client.play(audio_source, after=after)
            await message.remove_reaction(CLOCK, self.bot.user)

    @commands.command(no_pm=True)
    async def speak(self, ctx, *words: str):
        """Echoes the following text as speech."""
        await self.speak_aloud(ctx.message, *words)

    @commands.command()
    async def always_speak(self, ctx, word):
        """Enter "y" or "yes" to enable speaking of everything. Any other entry disables."""
        log.debug("always_speak called with: {}".format(word))
        if word.lower() in ['y', 'ye', 'yes', 'on']:
            self.always_speak_users_by_channel[ctx.channel.id].append(ctx.author.id)
            await ctx.message.add_reaction(OK_HAND)
        else:
            if ctx.author.id in self.always_speak_users_by_channel[ctx.channel.id]:
                self.always_speak_users_by_channel[ctx.channel.id].remove(ctx.author.id)
                await ctx.message.add_reaction(ARROW_DOWN)
        log.debug("Always speak users are: {}".format(self.always_speak_users_by_channel))

    @commands.command()
    async def restart(self, ctx):
        """Force quit the bot (expecting something else to restart it)."""
        log.error("Force quitting...")
        sys.exit(1)

    @commands.Cog.listener()
    async def on_message(self, message):
        log.debug("message from {0!r} in channel {1!r}.".format(message.author, message.channel))
        a, b, c, d = (
            not message.content.startswith('"'),
            message.author.id in self.always_speak_users_by_channel[message.channel.id],
            message.author.voice is not None and message.author.voice.channel is not None,
            message.author != self.bot.user,
        )
        log.debug("always speak bools are: {} {} {} {}".format(a, b, c, d))
        if a and b and c and d:
            log.debug("Always speaking for {}".format(message.author))
            await self.speak_aloud(message, message.content)

    async def cog_command_error(self, ctx, error):
        log.error("command_error: %s; %s", ctx, error)


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
    # Expects a yaml file of:
    # <user_id>:
    #   token: <lyrebird_oauth_token>
    #   default_channels:
    #     - <channel id>
    filename = os.environ.get("TOKEN_FILE", os.path.join(os.getcwd(), ".tokens.yaml"))
    if os.path.exists(filename):
        log.debug("tokens.yaml exists at: %s", filename)
        with open(filename) as fi:
            token_dict = yaml.safe_load(fi)
            for user, details in token_dict.items():
                log.info("loaded token from file for: %s", user)
                if 'token' in details:
                    lyrebot.lyrebird_tokens[user] = details['token']
                for channel in details.get('default_channels', []):
                    lyrebot.always_speak_users_by_channel[channel].append(user)

    log.info("Initial always speak users: {}".format(lyrebot.always_speak_users_by_channel))

    @bot.event
    async def on_ready():
        log.debug('Logged in as:\n{0} (ID: {0.id})'.format(bot.user))

    return bot
