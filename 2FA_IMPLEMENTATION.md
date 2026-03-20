# 🔐 2FA Authentication — Отчёт о реализации

**Дата:** 20 марта 2026 г.
**Статус:** ✅ Завершено
**Версия:** v2.7.0

---

## 📋 Обзор

Двухфакторная аутентификация (2FA) полностью интегрирована в систему аутентификации RentScout.

**Методы 2FA:**
- ✅ TOTP (Time-based One-Time Password)
- ✅ Backup коды
- ✅ Интеграция с Google Authenticator, Authy и др.

---

## 🚀 Новые API Endpoints

### Authentication

| Endpoint | Method | Описание |
|----------|--------|----------|
| `/api/auth/login` | POST | OAuth2 вход (проверяет 2FA) |
| `/api/auth/login-with-2fa` | POST | Вход с поддержкой 2FA |
| `/api/auth/2fa/setup` | POST | Настройка 2FA |
| `/api/auth/2fa/enable` | POST | Включение 2FA |
| `/api/auth/2fa/disable` | POST | Отключение 2FA |
| `/api/auth/2fa/verify` | POST | Проверка кода |
| `/api/auth/2fa/status` | GET | Статус 2FA |

---

## 📖 Как использовать 2FA

### 1. Настройка 2FA

```bash
# Шаг 1: Настройка
curl -X POST http://localhost:8000/api/auth/2fa/setup \
  -H "Authorization: Bearer <token>"

# Ответ:
{
  "secret": "JBSWY3DPEHPK3PXP",
  "qr_code": "iVBORw0KGgoAAAANSUhEUgAA...",
  "backup_codes": [
    "A1B2C3D4",
    "E5F6G7H8",
    ...
  ],
  "message": "Сохраните backup коды!"
}
```

```bash
# Шаг 2: Включение (после сканирования QR кода)
curl -X POST http://localhost:8000/api/auth/2fa/enable \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"code": "123456"}'
```

### 2. Вход с 2FA

```bash
# Метод 1: login-with-2fa endpoint
curl -X POST http://localhost:8000/api/auth/login-with-2fa \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "password123",
    "code": "123456"
  }'

# Ответ если 2FA требуется:
{
  "requires_2fa": true,
  "message": "Требуется 2FA код"
}

# Ответ если успешно:
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

```bash
# Метод 2: OAuth2 login (вернёт ошибку если 2FA включен)
curl -X POST http://localhost:8000/api/auth/login \
  -d "username=user@example.com&password=password123"

# Ответ с header X-2FA-Required: true
```

### 3. Использование backup кодов

```bash
# Если TOTP недоступен, используйте backup код
curl -X POST http://localhost:8000/api/auth/login-with-2fa \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "password123",
    "code": "A1B2C3D4"  # Backup код
  }'
```

---

## 🔧 Технические детали

### База данных

**Модель User (app/db/models/user.py):**
```python
class User(Base):
    # ...
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(32))  # Encrypted TOTP secret
    backup_codes = Column(String(1000))  # JSON array of hashed codes
    backup_codes_used = Column(String(500))  # JSON array of used indices
```

### TwoFactorManager (app/utils/two_factor.py)

**Основные методы:**
- `generate_secret()` — генерация TOTP секрета
- `generate_qr_code()` — создание QR кода
- `verify_code()` — проверка TOTP кода
- `generate_backup_codes()` — генерация backup кодов
- `verify_backup_code()` — проверка backup кода

### Безопасность

**Хранение:**
- TOTP секрет — зашифрован в БД
- Backup коды — хэшированы (SHA256)
- Использованные коды — отслеживаются

**Защита:**
- Rate limiting на login endpoint
- Блокировка при множественных неудачных попытках
- Окно времени для TOTP (valid_window=1)

---

## 🧪 Тесты

**Файл:** `app/tests/test_2fa.py`

**Покрытие:**
- Unit тесты для TwoFactorManager
- Integration тесты для endpoints
- Full flow тест (setup → enable → login)

**Запуск:**
```bash
pytest app/tests/test_2fa.py -v
```

---

## 📊 Статистика

| Метрика | Значение |
|---------|----------|
| Новых endpoints | 7 |
| Новых файлов | 2 |
| Изменено файлов | 3 |
| Строк кода добавлено | ~550 |
| Тестов добавлено | 15+ |

---

## 🔗 Интеграция с другими системами

### JWT Blacklist
- При logout токены добавляются в blacklist
- 2FA не влияет на механизм blacklist

### Rate Limiting
- Login endpoints защищены rate limiting
- Отдельные лимиты для 2FA кодов

### Monitoring
- Логирование всех 2FA событий
- Метрики для Prometheus

---

## 🎯 Рекомендации по использованию

### Для пользователей

1. **Включите 2FA** для защиты аккаунта
2. **Сохраните backup коды** в безопасном месте
3. **Используйте приложение** (Google Authenticator, Authy)
4. **Синхронизируйте время** на устройстве

### Для разработчиков

1. **Всегда проверяйте** `X-2FA-Required` header
2. **Обрабатывайте** `requires_2fa: true` в ответе
3. **Не логируйте** TOTP коды
4. **Используйте HTTPS** в production

---

## 📝 Примеры кода

### Python клиент

```python
import requests
import pyotp

# Логин с 2FA
def login_with_2fa(username, password, secret):
    # Генерируем TOTP код
    totp = pyotp.TOTP(secret)
    code = totp.now()
    
    response = requests.post(
        "http://localhost:8000/api/auth/login-with-2fa",
        json={
            "username": username,
            "password": password,
            "code": code
        }
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Login failed: {response.text}")

# Использование
tokens = login_with_2fa("user", "password", "JBSWY3DPEHPK3PXP")
print(f"Access token: {tokens['access_token']}")
```

### JavaScript клиент

```javascript
async function loginWith2FA(username, password, code) {
  const response = await fetch('/api/auth/login-with-2fa', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, code })
  });
  
  const data = await response.json();
  
  if (data.requires_2fa) {
    console.log('2FA required!');
    return null;
  }
  
  return data.access_token;
}
```

---

## 🐛 Troubleshooting

### "Неверный 2FA код"

**Причины:**
- Неправильное время на устройстве
- Неверный секрет
- Истёк срок действия кода (30 сек)

**Решение:**
- Синхронизируйте время
- Пересканируйте QR код
- Используйте backup код

### "2FA уже включен"

**Решение:**
- Отключите 2FA через `/api/auth/2fa/disable`
- Требуется пароль

### Backup коды не работают

**Причины:**
- Код уже использован
- Неправильный формат

**Решение:**
- Проверьте список использованных кодов
- Используйте другой код

---

## ✅ Чеклист готовности

- [x] TOTP аутентификация
- [x] Backup коды
- [x] Интеграция в login
- [x] API endpoints
- [x] Тесты
- [x] Документация
- [x] Синхронизация dev/main

---

**2FA полностью готова к использованию! 🎉**
