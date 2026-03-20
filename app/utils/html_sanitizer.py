"""
HTML Sanitization Utility.

Защита от XSS атак через:
- HTML escape пользовательских данных
- Whitelist разрешённых тегов
- Удаление опасных атрибутов
"""

import html
import re
from typing import Optional, Any, Dict, List


# Whitelist разрешённых HTML тегов
ALLOWED_TAGS = {
    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's',
    'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'blockquote', 'pre', 'code',
    'a', 'img',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'div', 'span',
}

# Whitelist разрешённых атрибутов
ALLOWED_ATTRIBUTES = {
    'a': {'href', 'title', 'rel'},
    'img': {'src', 'alt', 'title', 'width', 'height'},
    'td': {'colspan', 'rowspan'},
    'th': {'colspan', 'rowspan'},
}

# Опасные протоколы для URL
DANGEROUS_PROTOCOLS = {'javascript:', 'data:', 'vbscript:', 'file:'}


def sanitize_html(text: str, allow_html: bool = False) -> str:
    """
    Санитизация HTML текста для защиты от XSS.

    Args:
        text: Входной текст
        allow_html: Если True, разрешить безопасные HTML теги

    Returns:
        Очищенный текст
    """
    if not text:
        return ""

    if not allow_html:
        # Полный escape всех HTML символов
        return html.escape(text, quote=True)

    # Разрешаем безопасные HTML теги
    return sanitize_with_whitelist(text)


def sanitize_with_whitelist(text: str) -> str:
    """
    Санитизация с whitelist тегов.

    Удаляет все теги кроме разрешённых и опасные атрибуты.
    """
    if not text:
        return ""

    # Удаляем скрипты и опасные теги полностью
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<iframe[^>]*>.*?</iframe>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<object[^>]*>.*?</object>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<embed[^>]*>', '', text, flags=re.IGNORECASE)

    # Парсим и фильтруем теги
    def replace_tag(match):
        tag_match = re.match(r'</?(\w+)', match.group(0))
        if not tag_match:
            return match.group(0)

        tag_name = tag_match.group(1).lower()

        # Если тег не в whitelist - escape
        if tag_name not in ALLOWED_TAGS:
            return html.escape(match.group(0))

        # Если это закрывающий тег - оставляем
        if match.group(0).startswith('</'):
            return f'</{tag_name}>'

        # Проверяем атрибуты
        attr_pattern = r'(\w+)\s*=\s*["\']([^"\']*)["\']'
        attrs = re.findall(attr_pattern, match.group(0))

        safe_attrs = []
        allowed_attrs = ALLOWED_ATTRIBUTES.get(tag_name, set())

        for attr_name, attr_value in attrs:
            attr_name = attr_name.lower()

            # Пропускаем опасные атрибуты (onclick, onerror, onload и т.д.)
            if attr_name.startswith('on'):
                continue

            # Пропускаем атрибуты не из whitelist
            if attr_name not in allowed_attrs:
                continue

            # Проверяем URL на опасные протоколы
            if attr_name in ('href', 'src'):
                if is_dangerous_url(attr_value):
                    continue

                # Добавляем rel="noopener noreferrer" для внешних ссылок
                if attr_name == 'href' and attr_value.startswith('http'):
                    safe_attrs.append('rel="noopener noreferrer"')

            safe_attrs.append(f'{attr_name}="{html.escape(attr_value, quote=True)}"')

        attrs_str = ' '.join(safe_attrs)
        return f'<{tag_name} {attrs_str}>' if attrs_str else f'<{tag_name}>'

    # Заменяем все теги
    text = re.sub(r'<[^>]+>', replace_tag, text)

    return text


def is_dangerous_url(url: str) -> bool:
    """
    Проверка URL на опасные протоколы.

    Args:
        url: URL для проверки

    Returns:
        True если URL опасный
    """
    if not url:
        return True

    url_lower = url.lower().strip()

    # Проверяем опасные протоколы
    for protocol in DANGEROUS_PROTOCOLS:
        if url_lower.startswith(protocol):
            return True

    return False


def sanitize_user_input(data: Any) -> Any:
    """
    Рекурсивная санитизация пользовательских данных.

    Args:
        data: Данные для санитизации (dict, list, str)

    Returns:
        Очищенные данные
    """
    if isinstance(data, dict):
        return {k: sanitize_user_input(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_user_input(item) for item in data]
    elif isinstance(data, str):
        return sanitize_html(data, allow_html=False)
    else:
        return data


def sanitize_text_field(text: str, max_length: int = 10000) -> str:
    """
    Санитизация текстового поля с ограничением длины.

    Args:
        text: Входной текст
        max_length: Максимальная длина

    Returns:
        Очищенный текст
    """
    if not text:
        return ""

    # Ограничиваем длину
    text = text[:max_length]

    # Полный HTML escape
    return html.escape(text, quote=True)


def sanitize_description(description: str, max_length: int = 50000) -> str:
    """
    Санитизация описания с разрешением безопасного HTML.

    Args:
        description: Описание
        max_length: Максимальная длина

    Returns:
        Очищенное описание
    """
    if not description:
        return ""

    # Ограничиваем длину
    description = description[:max_length]

    # Разрешаем безопасный HTML
    return sanitize_with_whitelist(description)
