"""
Тесты для HTML санитизации (XSS защита).
"""
import pytest
from app.utils.html_sanitizer import (
    sanitize_html,
    sanitize_with_whitelist,
    is_dangerous_url,
    sanitize_user_input,
    sanitize_text_field,
    sanitize_description,
)


class TestSanitizeHTML:
    """Тесты для базовой санитизации HTML."""

    def test_escape_plain_text(self):
        """Тест escape обычного текста."""
        text = "Hello <script>alert('XSS')</script> World"
        result = sanitize_html(text, allow_html=False)
        
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
        assert "alert" in result

    def test_escape_quotes(self):
        """Тест escape кавычек."""
        text = 'Test "quotes" and \'apostrophes\''
        result = sanitize_html(text, allow_html=False)
        
        assert "&quot;" in result or "&#x27;" in result

    def test_empty_string(self):
        """Тест пустой строки."""
        assert sanitize_html("", allow_html=False) == ""
        assert sanitize_html(None, allow_html=False) == ""

    def test_nested_scripts(self):
        """Тест вложенных скриптов."""
        text = "<div><script><script></script></script></div>"
        result = sanitize_html(text, allow_html=False)
        
        assert "<script>" not in result


class TestSanitizeWithWhitelist:
    """Тесты для санитизации с whitelist."""

    def test_allowed_tags(self):
        """Тест разрешённых тегов."""
        text = "<p>Hello <strong>World</strong></p>"
        result = sanitize_with_whitelist(text)
        
        assert "<p>" in result
        assert "<strong>" in result

    def test_disallowed_tags(self):
        """Тест запрещённых тегов."""
        text = "<p>Hello <script>alert('XSS')</script> World</p>"
        result = sanitize_with_whitelist(text)
        
        assert "<script>" not in result
        assert "<p>" in result

    def test_dangerous_tags_removed(self):
        """Тест удаления опасных тегов."""
        dangerous_tags = ['script', 'style', 'iframe', 'object', 'embed']
        
        for tag in dangerous_tags:
            text = f"<{tag}>dangerous content</{tag}>"
            result = sanitize_with_whitelist(text)
            assert f"<{tag}>" not in result

    def test_onclick_attribute_removed(self):
        """Тест удаления onclick атрибута."""
        text = '<div onclick="alert(\'XSS\')">Click me</div>'
        result = sanitize_with_whitelist(text)
        
        assert "onclick" not in result.lower()

    def test_onerror_attribute_removed(self):
        """Тест удаления onerror атрибута."""
        text = '<img src="test.jpg" onerror="alert(\'XSS\')">'
        result = sanitize_with_whitelist(text)
        
        assert "onerror" not in result.lower()

    def test_onload_attribute_removed(self):
        """Тест удаления onload атрибута."""
        text = '<img src="test.jpg" onload="alert(\'XSS\")">'
        result = sanitize_with_whitelist(text)
        
        assert "onload" not in result.lower()

    def test_safe_attributes_preserved(self):
        """Тест сохранения безопасных атрибутов."""
        text = '<a href="https://example.com" title="Example">Link</a>'
        result = sanitize_with_whitelist(text)
        
        assert 'href=' in result
        assert 'title=' in result

    def test_dangerous_href_removed(self):
        """Тест удаления опасного href."""
        text = '<a href="javascript:alert(\'XSS\')">Click</a>'
        result = sanitize_with_whitelist(text)
        
        assert 'href=' not in result or 'javascript:' not in result

    def test_external_links_get_rel(self):
        """Тест добавления rel для внешних ссылок."""
        text = '<a href="https://external.com">Link</a>'
        result = sanitize_with_whitelist(text)
        
        assert 'rel="noopener noreferrer"' in result


class TestIsDangerousURL:
    """Тесты для проверки опасных URL."""

    def test_javascript_protocol(self):
        """Тест javascript: протокола."""
        assert is_dangerous_url("javascript:alert('XSS')") is True
        assert is_dangerous_url("JavaScript:alert('XSS')") is True

    def test_data_protocol(self):
        """Тест data: протокола."""
        assert is_dangerous_url("data:text/html,<script>alert('XSS')</script>") is True

    def test_vbscript_protocol(self):
        """Тест vbscript: протокола."""
        assert is_dangerous_url("vbscript:msgbox('XSS')") is True

    def test_safe_urls(self):
        """Тест безопасных URL."""
        safe_urls = [
            "https://example.com",
            "http://example.com",
            "/relative/path",
            "#anchor",
        ]
        
        for url in safe_urls:
            assert is_dangerous_url(url) is False

    def test_empty_url(self):
        """Тест пустого URL."""
        assert is_dangerous_url("") is True
        assert is_dangerous_url(None) is True


class TestSanitizeUserInput:
    """Тесты для санитизации пользовательских данных."""

    def test_sanitize_dict(self):
        """Тест санитизации словаря."""
        data = {
            "name": "<script>alert('XSS')</script>",
            "description": "Safe text"
        }
        result = sanitize_user_input(data)
        
        assert "<script>" not in result["name"]
        assert result["description"] == "Safe text"

    def test_sanitize_list(self):
        """Тест санитизации списка."""
        data = ["<script>alert(1)</script>", "safe", "<b>bold</b>"]
        result = sanitize_user_input(data)
        
        assert "<script>" not in result[0]
        assert result[1] == "safe"
        assert result[2] == "&lt;b&gt;bold&lt;/b&gt;"

    def test_sanitize_nested(self):
        """Тест санитизации вложенных структур."""
        data = {
            "items": [
                {"name": "<script>x</script>"},
                {"name": "safe"}
            ]
        }
        result = sanitize_user_input(data)
        
        assert "<script>" not in result["items"][0]["name"]

    def test_non_string_unchanged(self):
        """Тест что не-строковые данные не меняются."""
        data = {"number": 42, "boolean": True, "null": None}
        result = sanitize_user_input(data)
        
        assert result["number"] == 42
        assert result["boolean"] is True
        assert result["null"] is None


class TestSanitizeTextField:
    """Тесты для санитизации текстовых полей."""

    def test_max_length(self):
        """Тест ограничения длины."""
        text = "a" * 15000
        result = sanitize_text_field(text, max_length=10000)
        
        assert len(result) == 10000

    def test_html_escape(self):
        """Тест HTML escape."""
        text = "<script>alert('XSS')</script>"
        result = sanitize_text_field(text)
        
        assert "<script>" not in result

    def test_empty_string(self):
        """Тест пустой строки."""
        assert sanitize_text_field("") == ""


class TestSanitizeDescription:
    """Тесты для санитизации описаний."""

    def test_max_length(self):
        """Тест ограничения длины описания."""
        text = "a" * 60000
        result = sanitize_description(text, max_length=50000)
        
        assert len(result) == 50000

    def test_allowed_html(self):
        """Тест разрешённого HTML."""
        text = "<p>This is <strong>bold</strong> text</p>"
        result = sanitize_description(text)
        
        assert "<p>" in result
        assert "<strong>" in result

    def test_disallowed_html_removed(self):
        """Тест удаления запрещённого HTML."""
        text = "<p>Safe</p><script>alert('XSS')</script>"
        result = sanitize_description(text)
        
        assert "<script>" not in result
        assert "<p>" in result


class TestXSSAttackVectors:
    """Тесты на реальные XSS векторы атак."""

    def test_basic_script_injection(self):
        """Тест базовой инъекции скрипта."""
        payload = "<script>alert('XSS')</script>"
        result = sanitize_html(payload, allow_html=False)
        
        assert "<script>" not in result
        assert "alert" in result  # Текст остаётся

    def test_img_onerror(self):
        """Тест img onerror."""
        payload = '<img src=x onerror="alert(\'XSS\')">'
        result = sanitize_with_whitelist(payload)
        
        assert "onerror" not in result.lower()

    def test_svg_onload(self):
        """Тест svg onload."""
        payload = '<svg onload="alert(\'XSS\')">'
        result = sanitize_with_whitelist(payload)
        
        # SVG не в whitelist, должен быть escape
        assert "<svg" not in result

    def test_iframe_injection(self):
        """Тест iframe инъекции."""
        payload = '<iframe src="javascript:alert(\'XSS\')"></iframe>'
        result = sanitize_with_whitelist(payload)
        
        assert "<iframe" not in result

    def test_css_expression(self):
        """Тест CSS expression."""
        payload = '<div style="background:url(javascript:alert(\'XSS\'))">'
        result = sanitize_with_whitelist(payload)
        
        # style атрибут должен быть удалён для div (нет в whitelist)
        assert "style=" not in result.lower()

    def test_data_uri(self):
        """Тест data URI."""
        payload = '<a href="data:text/html,<script>alert(\'XSS\')</script>">Click</a>'
        result = sanitize_with_whitelist(payload)
        
        assert "data:" not in result or "href=" not in result

    def test_encoded_script(self):
        """Тест кодированного скрипта."""
        payload = "&lt;script&gt;alert('XSS')&lt;/script&gt;"
        result = sanitize_html(payload, allow_html=False)
        
        # Уже закодировано, должно остаться как есть
        assert result == payload


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
