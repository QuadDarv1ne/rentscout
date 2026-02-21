"""Response compression middleware для оптимизации размера ответов."""

import gzip
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.datastructures import Headers, MutableHeaders


class GZipMiddleware(BaseHTTPMiddleware):
    """Middleware для сжатия ответов с помощью gzip."""
    
    def __init__(self, app, minimum_size: int = 500, compression_level: int = 6):
        """
        Args:
            app: ASGI приложение
            minimum_size: Минимальный размер ответа для сжатия (байты)
            compression_level: Уровень сжатия gzip (1-9, где 9 - максимальное сжатие)
        """
        super().__init__(app)
        self.minimum_size = minimum_size
        self.compression_level = compression_level
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Обработка запроса с возможным сжатием ответа."""
        # Проверяем, поддерживает ли клиент gzip
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding.lower():
            return await call_next(request)
        
        # Получаем ответ
        response = await call_next(request)
        
        # Не сжимаем уже сжатые ответы
        if response.headers.get("content-encoding"):
            return response
        
        # Не сжимаем streaming responses
        if isinstance(response, StreamingResponse):
            return response
        
        # Получаем тело ответа
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        
        # Проверяем размер
        if len(body) < self.minimum_size:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        
        # Сжимаем
        compressed_body = gzip.compress(body, compresslevel=self.compression_level)
        
        # Создаем новый ответ с сжатым телом
        headers = MutableHeaders(response.headers)
        headers["content-encoding"] = "gzip"
        headers["content-length"] = str(len(compressed_body))
        headers["vary"] = "Accept-Encoding"
        
        return Response(
            content=compressed_body,
            status_code=response.status_code,
            headers=dict(headers),
            media_type=response.media_type,
        )
