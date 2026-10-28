import base64
import hashlib
import hmac
import time
import uuid
from urllib.parse import quote

from config import (
    HTTP_PROXY,
    TUMBLR_CONSUMER_KEY,
    TUMBLR_CONSUMER_SECRET,
    TUMBLR_OAUTH_TOKEN,
    TUMBLR_OAUTH_TOKEN_SECRET,
    USE_PROXY,
)
from services.http_clients import make_proxied_client, request_with_retries


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

    print("[DEBUG] Отправка подписанного OAuth-запроса в v2 API!")
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