import re

from aiogram import Bot, Router
from aiogram.types import Message

from services.telegram_media import send_media_to_telegram
from services.tumblr import get_media_from_api

links_router = Router()

TUMBLR_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:"
    r"([\w-]+)\.tumblr\.com/post/(\d+)|"
    r"at\.tumblr\.com/([\w-]+)/(\d+)|"
    r"www\.tumblr\.com/([\w-]+)/post/(\d+)|"
    r"tumblr\.com/([\w-]+)/(\d+)"
    r")"
)

busy_users: set[int] = set()


def parse_post_link(text: str) -> tuple[str, str]:
    url_match = re.search(r"https?://[^\s]+", text)
    url = (url_match.group(0) if url_match else text).split("?")[0].strip()

    match = TUMBLR_URL_PATTERN.search(url)
    if not match:
        raise ValueError("Ссылка не соответствует формату Tumblr постов")

    groups = [g for g in match.groups() if g]
    if len(groups) < 2:
        raise ValueError("Не удалось извлечь имя блога или ID поста")

    return groups[0], groups[1]


@links_router.message()
async def handle_links(message: Message, bot: Bot):
    text = message.text or message.caption
    if not text or "tumblr.com" not in text.lower() or message.from_user is None:
        return

    print(f"[DEBUG] Получен текст: {text}")

    try:
        blog_name, post_id = parse_post_link(text)
    except ValueError as parse_error:
        print(f"[-] Ошибка разбора ссылки: {parse_error}")
        return

    print(f"[DEBUG] Блог: {blog_name}, ID поста: {post_id}")

    user_id = message.from_user.id
    if user_id in busy_users:
        await message.answer("⏳ Подожди, предыдущий пост ещё качается")
        return
    busy_users.add(user_id)

    try:
        status_message = await message.answer("🔄 Запрашиваю Tumblr API...")
        media_urls, caption = await get_media_from_api(blog_name, post_id)

        if not media_urls:
            await status_message.edit_text("❌ В этом посте нет картинок или видео.")
            return

        await status_message.edit_text("📥 Скачиваю медиафайлы...")
        await send_media_to_telegram(message.chat.id, media_urls, caption, bot)
        await status_message.delete()

    except Exception as e:  # noqa: BLE001 - верхний уровень хэндлера: бот не должен падать
        print(f"[-] Ошибка выполнения: {type(e).__name__}: {e}")
        await message.answer(f"⚠ Ошибка: {type(e).__name__}: {e}")

    finally:
        busy_users.discard(user_id)