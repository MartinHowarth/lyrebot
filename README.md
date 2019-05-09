# Lyrebot

A discord bot that uses the Lyrebird API to allow users to use text-to-speech in their own voice.

## Usage
The main command of this bot is text to speech:

    "speak Welcome to lyrebot.

Lyrebot will join the current voice channel of the user who sent that message, and say it in their voice.

## User setup
Users of your bot must perform some setup:
* Create a lyrebird account and create a voice model here: https://beta.myvoice.lyrebird.ai/
* Provide the bot with OAuth2 authentication to use their voice by running these commands and following the instructions.
    * `generate_token_uri`
    * `generate_token`

It is highly recommended that users carry this out in a PM to the bot so others cannot impersonate their voice by getting access to their token.

Authentication details are currently forgotten over bot restart. In this instance, returning users can use the `set_token` command to use a previously-generated token.

Tokens currently expire after 1 year (controlled by Lyrebird).

## Bot Installation and Setup
### Discord application
You need a discord application with a bot configured to use this package.
A good tutorial is here: https://www.devdungeon.com/content/make-discord-bot-python

### Lyrebird application
You need to create a lyrebird application so that users can authenticate your bot to use their voices.
You can do that here: https://beta.myvoice.lyrebird.ai/developer

The homepage and redirect uri just needs to be valid url as a web server is not actually required. Users will be redirected to it and instructed to simply copy-paste the url (now with their auth token) and give it to the bot.

### FFmpeg
FFmpeg is required - you can install it from https://www.ffmpeg.org/download.html

### Python package (the bot itself)
Install using:

    python setup.py install

Set the following variables in your environment:

    DISCORD_BOT_TOKEN=YOUR_BOT_TOKEN
    LYRE_CLIENT_ID=YOUR_LYREBIRD_CLIENT_ID
    LYRE_CLIENT_SECRET=YOUR_LYREBIRD_CLIENT_SECRET
    LYRE_REDIRECT_URI=YOUR_LYREBIRD_REDIRECT_URI

Then simply run:

    lyrebot

or

    python lyrebot/main.py
