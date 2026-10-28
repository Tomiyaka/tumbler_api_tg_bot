import asyncio

import httpx
from aiogram import Bot
from aiogram.types import BufferedInputFile, InputMediaPhoto, InputMediaVideo

from services.http_clients import (
    make_proxied_client,
    request_with_retries,
)


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
    except httpx.HTTPError as e:
        print(f"[-] Ошибка скачивания {url}: {type(e).__name__}: {e}")
    return None