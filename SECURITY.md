# Security Policy

## Supported Versions

Мы поддерживаем следующие версии проекта с точки зрения обновлений безопасности:

| Version | Supported          |
| ------- | ------------------ |
| 1.5.x   | :white_check_mark: |
| 1.4.x   | :white_check_mark: |
| < 1.4   | :x:                |

## Reporting a Vulnerability

Если вы обнаружили уязвимость безопасности, пожалуйста:

1. **НЕ создавайте публичный issue** для уязвимостей безопасности
2. Отправьте информацию напрямую через GitHub Security Advisory или на email
3. Включите следующую информацию:
   - Описание уязвимости
   - Шаги для воспроизведения
   - Потенциальное влияние
   - Предложения по исправлению (если есть)

Мы постараемся ответить в течение 48 часов и предоставить временные рамки для исправления.

## Security Best Practices

### Для разработчиков

1. **Зависимости**: Регулярно обновляйте зависимости
   ```bash
   pip install --upgrade -r requirements.txt
   safety check
   ```

2. **Секреты**: Никогда не коммитьте секреты в репозиторий
   - Используйте `.env` файлы (добавлены в `.gitignore`)
   - Используйте переменные окружения
   - Используйте менеджеры секретов (AWS Secrets Manager, Azure Key Vault, etc.)

3. **Code Review**: Все изменения должны проходить review перед мержем

4. **Static Analysis**: Используйте инструменты:
   ```bash
   bandit -r app/
   safety check
   pip-audit
   ```

### Для production deployment

1. **HTTPS**: Всегда используйте HTTPS
2. **Secrets**: Используйте переменные окружения или секреты
3. **Rate Limiting**: Включен по умолчанию (настроен в `app/core/config.py`)
4. **CORS**: Настройте разрешенные источники
5. **Database**: Используйте подготовленные запросы (SQLAlchemy ORM делает это автоматически)
6. **Input Validation**: Используйте Pydantic модели для валидации

## Known Security Features

### Реализованные меры безопасности

- ✅ **Rate Limiting**: Защита от DDoS и брутфорса
- ✅ **Input Validation**: Pydantic модели валидируют все входные данные
- ✅ **SQL Injection Protection**: SQLAlchemy ORM
- ✅ **CORS**: Настраиваемая политика CORS
- ✅ **Secrets Management**: Поддержка переменных окружения
- ✅ **Error Handling**: Безопасная обработка ошибок без раскрытия деталей
- ✅ **Logging**: Structured logging без чувствительных данных
- ✅ **Dependencies Scanning**: GitHub Dependabot включен

### Планируемые улучшения

- [ ] JWT Authentication & Authorization
- [ ] API Key Management
- [ ] Request Signing
- [ ] Encryption at Rest
- [ ] Audit Logging
- [ ] WAF Integration

## Security Headers

Рекомендуется настроить следующие HTTP заголовки на уровне nginx/reverse proxy:

```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "no-referrer-when-downgrade" always;
add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

## Compliance

Проект следует лучшим практикам:

- OWASP Top 10
- CWE/SANS Top 25
- Python Security Best Practices

## Contact

Для вопросов безопасности: создайте Security Advisory на GitHub
