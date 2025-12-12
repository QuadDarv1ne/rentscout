"""
Генератор реалистичных HTTP заголовков для обхода защиты сайтов
"""
import random
from typing import Dict


USER_AGENTS = [
    # Chrome на Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Firefox на Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    # Edge на Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Chrome на MacOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Safari на MacOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]

ACCEPT_LANGUAGES = [
    "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "ru,en-US;q=0.9,en;q=0.8",
    "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
]


def get_random_headers(referer: str = None) -> Dict[str, str]:
    """
    Генерирует случайные, но реалистичные HTTP заголовки
    
    Args:
        referer: Опциональный referer
        
    Returns:
        Словарь с HTTP заголовками
    """
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "DNT": "1",
    }
    
    if referer:
        headers["Referer"] = referer
    
    return headers


def get_avito_headers() -> Dict[str, str]:
    """Специальные заголовки для Avito"""
    headers = get_random_headers()
    headers.update({
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
    })
    return headers


def get_cian_headers() -> Dict[str, str]:
    """Специальные заголовки для Cian"""
    headers = get_random_headers(referer="https://www.cian.ru/")
    return headers


def get_yandex_headers() -> Dict[str, str]:
    """Специальные заголовки для Yandex"""
    headers = get_random_headers(referer="https://yandex.ru/")
    headers["X-Requested-With"] = "XMLHttpRequest"
    return headers
