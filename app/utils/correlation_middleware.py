"""Middleware для correlation IDs и логирования запросов."""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.utils.structured_logger import set_correlation_id, clear_correlation_id, logger


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Middleware для добавления correlation ID к каждому запросу."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Обработка запроса с correlation ID.
        
        Args:
            request: Входящий запрос
            call_next: Следующий обработчик
            
        Returns:
            Ответ с correlation ID в заголовках
        """
        # Получаем или генерируем correlation ID
        corr_id = request.headers.get("X-Correlation-ID")
        if not corr_id:
            corr_id = str(uuid.uuid4())

        # Устанавливаем correlation ID в контекст
        set_correlation_id(corr_id)

        # Засекаем время начала
        start_time = time.time()

        try:
            # Логируем начало запроса
            logger.debug(
                f"Request started: {request.method} {request.url.path}",
                method=request.method,
                path=str(request.url.path),
                query_params=dict(request.query_params),
            )

            # Обрабатываем запрос
            response = await call_next(request)

            # Вычисляем длительность
            duration = time.time() - start_time

            # Добавляем correlation ID в заголовки ответа
            response.headers["X-Correlation-ID"] = corr_id

            # Логируем завершение запроса
            logger.log_request(
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
                duration=duration,
            )

            return response

        except Exception as e:
            # Логируем ошибку
            duration = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} - {str(e)}",
                method=request.method,
                path=str(request.url.path),
                duration=duration,
                exc_info=True,
            )
            raise

        finally:
            # Очищаем correlation ID из контекста
            clear_correlation_id()
