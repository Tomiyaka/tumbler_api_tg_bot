import asyncio
import base64
import hashlib
import hmac
import os
import re
import ssl  
import sys
import time
import uuid
from urllib.parse import quote
import selectors

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BufferedInputFile, InputMediaPhoto, InputMediaVideo, Message
from dotenv import load_dotenv
import httpx

load_dotenv()
USE_PROXY = True  
HTTP_PROXY = os.getenv("PROXY")


BOT_TOKEN = os.getenv("BOT_TOKEN")
TUMBLR_CONSUMER_KEY = os.getenv("TUMBLR_CONSUMER_KEY")
TUMBLR_CONSUMER_SECRET = os.getenv("TUMBLR_CONSUMER_SECRET")
TUMBLR_OAUTH_TOKEN = os.getenv("TUMBLR_OAUTH_TOKEN")
TUMBLR_OAUTH_TOKEN_SECRET = os.getenv("TUMBLR_OAUTH_TOKEN_SECRET")

router = Router()

TUMBLR_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:"
    r"([\w-]+)\.tumblr\.com/post/(\d+)|"
    r"at\.tumblr\.com/([\w-]+)/(\d+)|"
    r"www\.tumblr\.com/([\w-]+)/post/(\d+)|"
    r"tumblr\.com/([\w-]+)/(\d+)"
    r")"
)

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 **Привет!**\n\n"
        "Я бот, который помогает скачивать фото и видео из постов Tumblr.\n"
        "Просто отправь мне ссылку на пост, и я пришлю тебе медиафайлы в оригинальном качестве.\n\n"
        "Используй /help, чтобы увидеть примеры ссылок."
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "**Как мной пользоваться:**\n\n"
        "Отправь мне обычную ссылку на пост в Tumblr. Например:\n"
        "• `https://tumblr.com`\n"
        "• `https://blog_://tumblr.com`\n\n"
        "Я автоматически распознаю её, скачаю картинки или видео через API и отправлю тебе в чат."
    )


@router.message()
async def handle_links(message: Message, bot: Bot):
    text = message.text or message.caption
    if not text or "tumblr.com" not in text.lower():
        return

    print(f"[DEBUG] Получен текст: {text}")

    try:
        url_match = re.search(r'https?://[^\s]+', text)
        url_to_parse = url_match.group(0) if url_match else text
        url_to_parse = url_to_parse.split("?")[0].strip()
        
        match = TUMBLR_URL_PATTERN.search(url_to_parse)
        if not match:
            raise ValueError("Ссылка не соответствует формату Tumblr постов")
            
        groups = [g for g in match.groups() if g]
        if len(groups) < 2:
            raise ValueError("Не удалось извлечь имя блога или ID поста")
            
        blog_name = groups[0]
        post_id = groups[1]

        print(f"[DEBUG] Идеально распарсили! Блог: {blog_name}, ID поста: {post_id}")

    except Exception as parse_error:
        print(f"[-] Ошибка разбора ссылки: {parse_error}")
        return

    status_message = await message.answer("🔄 Запрашиваю Tumblr API...")
    
    try:
        media_urls, caption = await get_media_from_api(blog_name, post_id)

        if not media_urls:
            await status_message.edit_text("❌ В этом посте нет картинок или видео.")
            return

        await status_message.edit_text("📥 Скачиваю медиафайлы...")
        await send_media_to_telegram(message.chat.id, media_urls, caption, bot)
        await status_message.delete()

    except Exception as e:
        print(f"[-] Ошибка выполнения: {type(e).__name__}: {e}")
        await status_message.edit_text(f"⚠ Ошибка: {type(e).__name__}: {e}")


def make_tls12_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    return ctx
 
 
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
}
 
 
async def make_proxied_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        proxy=HTTP_PROXY if USE_PROXY else None,
        timeout=30.0,
        http2=False,
        verify=make_tls12_ssl_context(),
        headers=DEFAULT_HEADERS,
        limits=httpx.Limits(max_keepalive_connections=0, max_connections=10),
    )
 
 
async def request_with_retries(method_coro_factory, retries: int = 3, base_delay: float = 1.0):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return await method_coro_factory()
        except (httpx.TransportError, ssl.SSLError) as e:
            last_exc = e
            print(f"[!] Попытка {attempt}/{retries} не удалась: {type(e).__name__}: {e}")
            if attempt < retries:
                await asyncio.sleep(base_delay * attempt)
    raise last_exc


def oauth1_sign_params(method: str, url: str, params: dict) -> dict:
    def enc(s) -> str:
        return quote(str(s), safe="~")

    oauth_params = {
        "oauth_consumer_key": TUMBLR_CONSUMER_KEY,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": TUMBLR_OAUTH_TOKEN,
        "oauth_version": "1.0",
    }
    all_params = {**params, **oauth_params}
    param_str = "&".join(f"{enc(k)}={enc(v)}" for k, v in sorted(all_params.items()))
    base_str = "&".join([method.upper(), enc(url), enc(param_str)])
    signing_key = f"{enc(TUMBLR_CONSUMER_SECRET)}&{enc(TUMBLR_OAUTH_TOKEN_SECRET)}"
    signature = base64.b64encode(
        hmac.new(signing_key.encode(), base_str.encode(), hashlib.sha1).digest()
    ).decode()
    oauth_params["oauth_signature"] = signature
    return {**params, **oauth_params}


async def get_media_from_api(blog_name: str, post_id: str) -> tuple[list[dict], str]:
    url = f"https://api.tumblr.com/v2/blog/{blog_name}/posts"
    signed_params = oauth1_sign_params("GET", url, {"id": post_id, "npf": "true"})

    print(f"[DEBUG] Отправка подписанного OAuth-запроса в v2 API!")
    print(f"[DEBUG] Сформированный URL: {url} (ID: {post_id})")
    print(f"[DEBUG] Используемый прокси: {HTTP_PROXY if USE_PROXY else '—'}")

    async def do_request():
        async with await make_proxied_client() as client:
            return await client.get(url, params=signed_params)

    response = await request_with_retries(do_request)
    print(f"[DEBUG] Ответ от API Tumblr получил статус: {response.status_code}")

    if response.status_code != 200:
        print(f"[-] Tumblr API вернул ошибку {response.status_code}: {response.text[:300]}")
        return [], ""

    res_json = response.json()
    response_data = res_json.get("response", {})
    
    posts = response_data.get("posts", [])

    if not posts:
        print("[-] Пост не найден в ответе API")
        return [], ""

    post_data = posts[0]
    media_list = []
    caption_parts = []

    blocks = post_data.get("content", [])
    for block in blocks:
        block_type = block.get("type")
        if block_type == "text":
            caption_parts.append(block.get("text", ""))
        elif block_type == "image":
            media_array = block.get("media", [])
            if media_array and isinstance(media_array, list) and len(media_array) > 0:
                first_image = media_array[0]
                if isinstance(first_image, dict) and "url" in first_image:
                    media_list.append({"type": "photo", "url": first_image.get("url")})
        elif block_type == "video":
            media_obj = block.get("media", {})
            if isinstance(media_obj, list) and media_obj:
                first_video = media_obj[0]
                if isinstance(first_video, dict) and "url" in first_video:
                    media_list.append({"type": "video", "url": first_video.get("url")})
            elif isinstance(media_obj, dict) and "url" in media_obj:
                media_list.append({"type": "video", "url": media_obj.get("url")})

    caption = "\n".join(caption_parts).strip()
    return media_list, caption


async def send_media_to_telegram(chat_id: int, media_urls: list[dict], caption: str, bot: Bot):
    async with await make_proxied_client() as client:
        tasks = []
        for item in media_urls:
            tasks.append(download_file(client, item["url"], item["type"]))
        
        downloaded_media = await asyncio.gather(*tasks)
        downloaded_media = [m for m in downloaded_media if m is not None]

        if not downloaded_media:
            return

        if len(downloaded_media) == 1:
            file_data, m_type = downloaded_media[0]
            file = BufferedInputFile(file_data, filename=f"file.{'mp4' if m_type == 'video' else 'jpg'}")
            if m_type == "video":
                await bot.send_video(chat_id, video=file, caption=caption)
            else:
                await bot.send_photo(chat_id, photo=file, caption=caption)
        else:
            media_group = []
            for i, (file_data, m_type) in enumerate(downloaded_media):
                ext = "mp4" if m_type == "video" else "jpg"
                file = BufferedInputFile(file_data, filename=f"file_{i}.{ext}")
                current_caption = caption if i == 0 else None
                if m_type == "video":
                    media_group.append(InputMediaVideo(media=file, caption=current_caption))
                else:
                    media_group.append(InputMediaPhoto(media=file, caption=current_caption))
            
            for i in range(0, len(media_group), 10):
                await bot.send_media_group(chat_id, media=media_group[i:i+10])
                await asyncio.sleep(0.5)


async def download_file(client: httpx.AsyncClient, url: str, media_type: str):
    async def do_get():
        return await client.get(url)

    try:
        response = await request_with_retries(do_get)
        if response.status_code == 200:
            return response.content, media_type
        else:
            print(f"[-] Файл вернул статус: {response.status_code}")
    except Exception as e:
        print(f"[-] Ошибка скачивания {url}: {type(e).__name__}: {e}")
    return None


async def main():
    bot_session = AiohttpSession(proxy=HTTP_PROXY if USE_PROXY else None)
    bot_session._connector_init["ssl"] = make_tls12_ssl_context() 
    bot = Bot(token=BOT_TOKEN, session=bot_session)

    dp = Dispatcher()
    dp.include_router(router)
    
    print("[+] Бот успешно запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))