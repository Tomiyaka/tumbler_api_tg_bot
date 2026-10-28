from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

commands_router = Router()

@commands_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 **Привет!**\n\n"
        "Я бот, который помогает скачивать фото и видео из постов Tumblr.\n"
        "Просто отправь мне ссылку на пост, и я пришлю тебе медиафайлы в оригинальном качестве.\n\n"
        "Используй /help, чтобы увидеть примеры ссылок."
    )

@commands_router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "**Как мной пользоваться:**\n\n"
        "Отправь мне обычную ссылку на пост в Tumblr. Например:\n"
        "• `https://tumblr.com`\n"
        "• `https://blog_://tumblr.com`\n\n"
        "Я автоматически распознаю её, скачаю картинки или видео через API и отправлю тебе в чат."
    )

