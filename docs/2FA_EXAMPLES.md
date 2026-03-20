# 2FA Examples — Примеры использования

Примеры кода для использования 2FA в RentScout API.

## Содержание

- [Python](#python)
- [JavaScript/Node.js](#javascriptnodejs)
- [cURL](#curl)

---

## Python

### Настройка 2FA

```python
import httpx
import pyotp

BASE_URL = "http://localhost:8000/api"

# 1. Логин
login_response = httpx.post(
    f"{BASE_URL}/auth/login",
    data={"username": "myuser", "password": "MyPassword123!"}
)
tokens = login_response.json()
headers = {"Authorization": f"Bearer {tokens['access_token']}"}

# 2. Настройка 2FA
setup_response = httpx.post(
    f"{BASE_URL}/auth/2fa/setup",
    headers=headers
)
setup_data = setup_response.json()

print(f"Secret: {setup_data['secret']}")
print(f"Backup codes: {setup_data['backup_codes']}")

# 3. Включение 2FA
totp = pyotp.TOTP(setup_data['secret'])
code = totp.now()

enable_response = httpx.post(
    f"{BASE_URL}/auth/2fa/enable",
    headers=headers,
    json={"code": code}
)
print(f"2FA enabled: {enable_response.json()}")
```

### Вход с 2FA

```python
import pyotp

# Генерация TOTP кода
secret = "YOUR_SECRET_FROM_SETUP"
totp = pyotp.TOTP(secret)
code = totp.now()

# Вход с кодом
login_response = httpx.post(
    f"{BASE_URL}/auth/login-with-2fa",
    json={
        "username": "myuser",
        "password": "MyPassword123!",
        "code": code  # TOTP код или backup код
    }
)

if login_response.status_code == 200:
    tokens = login_response.json()
    print(f"Access token: {tokens['access_token']}")
elif login_response.status_code == 401:
    print("Неверный код 2FA")
```

### Использование backup кода

```python
# Если у вас нет доступа к TOTP приложению
backup_code = "ABCD1234"  # Один из backup кодов

login_response = httpx.post(
    f"{BASE_URL}/auth/login-with-2fa",
    json={
        "username": "myuser",
        "password": "MyPassword123!",
        "code": backup_code
    }
)
```

### Проверка статуса 2FA

```python
status_response = httpx.get(
    f"{BASE_URL}/auth/2fa/status",
    headers=headers
)
print(f"2FA status: {status_response.json()}")
```

### Отключение 2FA

```python
disable_response = httpx.post(
    f"{BASE_URL}/auth/2fa/disable",
    headers=headers,
    json={"password": "MyPassword123!"}
)
print(f"2FA disabled: {disable_response.json()}")
```

---

## JavaScript/Node.js

### Настройка 2FA

```javascript
const axios = require('axios');
const speakeasy = require('speakeasy');
const qrcode = require('qrcode');

const BASE_URL = 'http://localhost:8000/api';

async function setup2FA() {
    // 1. Логин
    const loginResponse = await axios.post(
        `${BASE_URL}/auth/login`,
        new URLSearchParams({
            username: 'myuser',
            password: 'MyPassword123!'
        })
    );
    
    const token = loginResponse.data.access_token;
    const headers = { Authorization: `Bearer ${token}` };
    
    // 2. Настройка 2FA
    const setupResponse = await axios.post(
        `${BASE_URL}/auth/2fa/setup`,
        {},
        { headers }
    );
    
    const { secret, qr_code, backup_codes } = setupResponse.data;
    
    console.log('Secret:', secret);
    console.log('Backup codes:', backup_codes);
    
    // 3. Показать QR код
    console.log('QR Code (base64):', qr_code);
    
    // 4. Включение 2FA
    const totp = speakeasy.totp({
        secret: secret,
        encoding: 'base32'
    });
    
    const enableResponse = await axios.post(
        `${BASE_URL}/auth/2fa/enable`,
        { code: totp },
        { headers }
    );
    
    console.log('2FA enabled:', enableResponse.data);
}

setup2FA().catch(console.error);
```

### Вход с 2FA

```javascript
const speakeasy = require('speakeasy');

async function loginWith2FA() {
    const secret = 'YOUR_SECRET_FROM_SETUP';
    
    // Генерация TOTP кода
    const code = speakeasy.totp({
        secret: secret,
        encoding: 'base32'
    });
    
    try {
        const response = await axios.post(
            `${BASE_URL}/auth/login-with-2fa`,
            {
                username: 'myuser',
                password: 'MyPassword123!',
                code: code
            }
        );
        
        console.log('Access token:', response.data.access_token);
    } catch (error) {
        if (error.response?.status === 401) {
            console.error('Неверный код 2FA');
        } else {
            console.error('Ошибка:', error.message);
        }
    }
}

loginWith2FA().catch(console.error);
```

### Использование backup кода

```javascript
async function loginWithBackupCode() {
    const backupCode = 'ABCD1234';  // Один из backup кодов
    
    try {
        const response = await axios.post(
            `${BASE_URL}/auth/login-with-2fa`,
            {
                username: 'myuser',
                password: 'MyPassword123!',
                code: backupCode
            }
        );
        
        console.log('Logged in with backup code!');
        console.log('Access token:', response.data.access_token);
    } catch (error) {
        console.error('Ошибка:', error.response?.data || error.message);
    }
}

loginWithBackupCode().catch(console.error);
```

---

## cURL

### Настройка 2FA

```bash
# 1. Логин
LOGIN_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=myuser&password=MyPassword123!")

ACCESS_TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')

# 2. Настройка 2FA
SETUP_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/auth/2fa/setup" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

echo "Setup response: $SETUP_RESPONSE"

# Извлечь secret и backup_codes
SECRET=$(echo $SETUP_RESPONSE | jq -r '.secret')
BACKUP_CODES=$(echo $SETUP_RESPONSE | jq -r '.backup_codes[]')

echo "Secret: $SECRET"
echo "Backup codes: $BACKUP_CODES"

# 3. Генерация TOTP кода (требуется oathtool)
# Установите: brew install oath-toolkit (macOS) или apt-get install oathtool (Linux)
TOTP_CODE=$(oathtool --base32 --totp $SECRET)

# 4. Включение 2FA
curl -s -X POST "http://localhost:8000/api/auth/2fa/enable" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"code\": \"$TOTP_CODE\"}"
```

### Вход с 2FA

```bash
# Генерация TOTP кода
TOTP_CODE=$(oathtool --base32 --totp YOUR_SECRET)

# Вход с кодом
curl -s -X POST "http://localhost:8000/api/auth/login-with-2fa" \
  -H "Content-Type: application/json" \
  -d "{
    \"username\": \"myuser\",
    \"password\": \"MyPassword123!\",
    \"code\": \"$TOTP_CODE\"
  }" | jq .
```

### Использование backup кода

```bash
curl -s -X POST "http://localhost:8000/api/auth/login-with-2fa" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "myuser",
    "password": "MyPassword123!",
    "code": "ABCD1234"
  }' | jq .
```

### Проверка статуса 2FA

```bash
curl -s -X GET "http://localhost:8000/api/auth/2fa/status" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq .
```

### Отключение 2FA

```bash
curl -s -X POST "http://localhost:8000/api/auth/2fa/disable" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password": "MyPassword123!"}' | jq .
```

---

## Полезные утилиты

### Установка зависимостей

**Python:**
```bash
pip install pyotp httpx
```

**Node.js:**
```bash
npm install speakeasy qrcode axios
```

**cURL + инструменты:**
```bash
# macOS
brew install curl jq oathtool

# Linux (Ubuntu/Debian)
apt-get install curl jq oathtool
```

### Генерация TOTP кода вручную

```bash
# С помощью oathtool
oathtool --base32 --totp YOUR_SECRET

# С помощью Python
python -c "import pyotp; print(pyotp.TOTP('YOUR_SECRET').now())"

# С помощью Node.js
node -e "console.log(require('speakeasy').totp({secret: 'YOUR_SECRET', encoding: 'base32'}))"
```

---

## Безопасность

1. **Храните secret безопасно** — не коммитьте в git
2. **Backup коды используйте только в экстренных случаях** — каждый код одноразовый
3. **Обновляйте токены** — используйте refresh token endpoint
4. **Rate limiting** — 5 попыток ввода кода в минуту

## API Endpoints

| Endpoint | Method | Описание |
|----------|--------|----------|
| `/api/auth/2fa/setup` | POST | Настройка 2FA |
| `/api/auth/2fa/enable` | POST | Включение 2FA |
| `/api/auth/2fa/disable` | POST | Отключение 2FA |
| `/api/auth/2fa/status` | GET | Статус 2FA |
| `/api/auth/login-with-2fa` | POST | Вход с 2FA |
