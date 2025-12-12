# 🛡️ Руководство по обходу защиты сайтов

## ⚠️ ВАЖНО: Легальность и этика

**Перед использованием методов обхода защиты:**

1. **Проверьте Terms of Service** сайта
2. **Используйте официальные API** где это возможно
3. **Соблюдайте rate limits** (не делайте слишком много запросов)
4. **Уважайте robots.txt**
5. **Не перегружайте серверы** целевых сайтов

## 🔧 Реализованные методы защиты

### 1. Случайные User-Agent и заголовки

```python
from app.utils.enhanced_http import EnhancedHTTPClient

async with EnhancedHTTPClient() as client:
    response = await client.get("https://example.com")
```

**Что это дает:**

- Имитация запросов от реальных браузеров
- Ротация User-Agent для каждого запроса
- Реалистичные HTTP заголовки

### 2. Прокси-серверы

**Настройка в `.env`:**

```env
PROXY_ENABLED=true
PROXY_FILE=proxies.txt
```

**Формат `proxies.txt`:**

```text
http://proxy1.example.com:8080
http://username:password@proxy2.example.com:3128
socks5://proxy3.example.com:1080
```

**Бесплатные источники прокси:**

- <https://free-proxy-list.net/>
- <https://www.sslproxies.org/>
- <https://hidemy.name/ru/proxy-list/>

**Платные сервисы (рекомендуется):**

- Bright Data (ex-Luminati)
- Smartproxy
- Oxylabs
- ScraperAPI

### 3. Задержки между запросами

**Настройка в `.env`:**

```env
MIN_REQUEST_DELAY=2.0
MAX_REQUEST_DELAY=5.0
```

**Что это дает:**

- Имитация поведения человека
- Снижение нагрузки на сервер
- Меньше шансов быть заблокированным

### 4. Обход SSL ошибок

Для временного решения проблемы с сертификатами (только для разработки!):

```python
# В enhanced_http.py уже настроено:
verify=False  # Отключает проверку SSL
```

**⚠️ НЕ используйте в продакшене!**

## 📚 Продвинутые методы (требуют дополнительной настройки)

### 1. Headless браузеры (Playwright/Selenium)

**Установка:**

```bash
pip install playwright playwright-stealth
playwright install chromium
```

**Пример использования:**

```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent="Mozilla/5.0...",
        viewport={'width': 1920, 'height': 1080}
    )
    page = await context.new_page()
    await page.goto("https://example.com")
    content = await page.content()
    await browser.close()
```

### 2. Обход Captcha

**Сервисы:**

- 2Captcha: <https://2captcha.com/>
- Anti-Captcha: <https://anti-captcha.com/>
- CapSolver: <https://www.capsolver.com/>

**Пример с 2Captcha:**

```python
from twocaptcha import TwoCaptcha

solver = TwoCaptcha('YOUR_API_KEY')
result = solver.recaptcha(
    sitekey='SITE_KEY',
    url='https://example.com'
)
```

### 3. Cookie Management

```python
# Сохранение cookies
cookies = client.cookies
with open('cookies.json', 'w') as f:
    json.dump(dict(cookies), f)

# Загрузка cookies
with open('cookies.json', 'r') as f:
    cookies = json.load(f)
    for name, value in cookies.items():
        client.cookies.set(name, value)
```

### 4. JavaScript рендеринг

Для сайтов с динамическим контентом используйте:

- Playwright
- Selenium
- Pyppeteer
- Splash

## 🎯 Рекомендуемый подход для каждого сайта

### Avito

1. ✅ Официальное API: <https://developers.avito.ru/>
2. 🔄 Headless браузер с прокси
3. ⏱️ Большие задержки (5-10 сек)

### Cian

1. ✅ Официальное API: <https://api.cian.ru/>
2. 🔄 Случайные заголовки + прокси
3. 🍪 Cookie management

### Yandex Realty

1. ✅ Официальное API: <https://yandex.ru/dev/realty/>
2. 🔄 Headless браузер (строгая защита)
3. 🎭 Решение captcha

### DomClick

1. 🔑 Требует авторизации
2. 🔄 Cookie management
3. 📝 Получите API ключ если возможно

### Domofond

1. 🔧 Исправить SSL конфигурацию
2. 🔄 Прокси с поддержкой SNI
3. 📦 Или использовать headless браузер

## ⚙️ Настройка в `.env`

```env
# Включить защиту от блокировки
USE_RANDOM_HEADERS=true
PROXY_ENABLED=false
MIN_REQUEST_DELAY=2.0
MAX_REQUEST_DELAY=5.0

# Таймауты
REQUEST_TIMEOUT=30
PARSER_TIMEOUT=60

# Повторы
MAX_RETRIES=3
RETRY_DELAY=1.0
```

## 🧪 Тестирование

```python
# Тест прокси
from app.utils.proxy import proxy_manager, ProxyConfig

proxy = ProxyConfig(
    protocol="http",
    host="proxy.example.com",
    port=8080
)
is_working = await proxy_manager.test_proxy(proxy)

# Тест заголовков
from app.utils.headers import get_random_headers
headers = get_random_headers()
print(headers)
```

## 📊 Мониторинг

Следите за:

- Успешностью запросов (% 200 ответов)
- Частотой captcha
- Скоростью блокировки IP
- Качеством прокси

## 🚨 Признаки блокировки

- HTTP 403 (Forbidden)
- HTTP 429 (Too Many Requests)
- Редиректы на captcha
- Пустые/искаженные ответы
- Внезапный рост латентности

## 💡 Best Practices

1. **Начните с официальных API**
2. **Используйте минимально необходимые методы**
3. **Добавляйте случайность во всё**
4. **Распределяйте нагрузку по времени**
5. **Мониторьте и адаптируйтесь**
6. **Уважайте целевые сайты**

## 📖 Дополнительные ресурсы

- [Scrapy Best Practices](https://docs.scrapy.org/en/latest/topics/practices.html)
- [Web Scraping Legality](https://benbernardblog.com/web-scraping-and-crawling-are-perfectly-legal-right/)
- [Playwright Documentation](https://playwright.dev/python/docs/intro)
- [2Captcha Documentation](https://2captcha.com/2captcha-api)
