import asyncio
import selectors

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from config import BOT_TOKEN, HTTP_PROXY, USE_PROXY
from handlers.commands import commands_router
from handlers.links import links_router
from services.http_clients import make_tls12_ssl_context


async def main():
    bot_session = AiohttpSession(proxy=HTTP_PROXY if USE_PROXY else None)
    bot_session._connector_init["ssl"] = make_tls12_ssl_context() 
    bot = Bot(token=BOT_TOKEN, session=bot_session)

    dp = Dispatcher()
    dp.include_router(commands_router)
    dp.include_router(links_router)
    
    print("[+] Бот успешно запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))