import asyncio
import ssl

import httpx

from config import HTTP_PROXY, USE_PROXY


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