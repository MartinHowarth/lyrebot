import logging
import os
import sys

from lyrebot.discord_bot import create_bot

log = logging.getLogger(__name__)


def configure_logging():
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)


def main():
    configure_logging()
    discord_bot_token = os.environ['DISCORD_BOT_TOKEN']
    lyre_redirect_uri = os.environ['LYRE_REDIRECT_URI']
    lyre_client_id = os.environ['LYRE_CLIENT_ID']
    lyre_client_secret = os.environ['LYRE_CLIENT_SECRET']

    bot = create_bot(lyre_client_id, lyre_client_secret, lyre_redirect_uri)
    bot.run(discord_bot_token)


if __name__ == "__main__":
    main()
