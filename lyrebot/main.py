import logging
import os
import sys

from lyrebot.discord_bot import create_bot

log = logging.getLogger(__name__)


def configure_logging():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)


if __name__ == "__main__":
    configure_logging()
    DISCORD_BOT_TOKEN = os.environ['DISCORD_BOT_TOKEN']
    LYRE_REDIRECT_URI = os.environ['LYRE_REDIRECT_URI']
    LYRE_CLIENT_ID = os.environ['LYRE_CLIENT_ID']
    LYRE_CLIENT_SECRET = os.environ['LYRE_CLIENT_SECRET']

    bot = create_bot(LYRE_CLIENT_ID, LYRE_CLIENT_SECRET, LYRE_REDIRECT_URI)
    bot.run(DISCORD_BOT_TOKEN)
