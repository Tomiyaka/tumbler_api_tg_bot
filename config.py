import os
from dotenv import load_dotenv

load_dotenv()

USE_PROXY = True
HTTP_PROXY = os.getenv("PROXY")

BOT_TOKEN = os.getenv("BOT_TOKEN")

TUMBLR_CONSUMER_KEY = os.getenv("TUMBLR_CONSUMER_KEY")
TUMBLR_CONSUMER_SECRET = os.getenv("TUMBLR_CONSUMER_SECRET")
TUMBLR_OAUTH_TOKEN = os.getenv("TUMBLR_OAUTH_TOKEN")
TUMBLR_OAUTH_TOKEN_SECRET = os.getenv("TUMBLR_OAUTH_TOKEN_SECRET")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в .env")