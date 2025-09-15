import logging
import asyncio
from typing import Optional, Dict, Any, Callable

from ai.skeleton import Skeleton
from dsk.api import (
    DeepSeekAPI,
    AuthenticationError,
    RateLimitError,
    NetworkError,
    APIError,
)

class DeepSeek(Skeleton):
    def __init__(self, key: str, system_prompt: str = "", logger: Optional[logging.Logger] = None):
        self.logger: logging.Logger = logger or logging.getLogger(__name__)
        self.api = DeepSeekAPI(key)
        self.system_prompt = system_prompt

        # настройки ретраев
        self._max_retries = 5
        self._base_backoff = 1  # секунды

    async def _to_thread(self, fn: Callable, *args, **kwargs):
        """Запускает синхронный вызов API в отдельном треде без трюков с event loop."""
        return await asyncio.to_thread(fn, *args, **kwargs)

    async def _retryable(self, func: Callable, *args, **kwargs):
        """Ретраит сеть/лимиты с экспоненциальной паузой; аутентификацию не ретраит."""
        for attempt in range(1, self._max_retries + 1):
            self.logger.info("[DeepSeek] Attempt %d/%d to call %s", attempt, self._max_retries, func.__name__)
            try:
                return await self._to_thread(func, *args, **kwargs)
            except AuthenticationError as e:
                self.logger.exception("[DeepSeek] Auth error on attempt %s: %s", attempt, e)
                raise
            except (RateLimitError, NetworkError) as e:
                if attempt == self._max_retries:
                    self.logger.exception("[DeepSeek] Failed after %s attempts: %s", attempt, e)
                    raise
                sleep_for = self._base_backoff * (2 ** (attempt - 1))
                self.logger.warning("[DeepSeek] %s, retrying in %.2fs (attempt %d/%d)",
                                    e.__class__.__name__, sleep_for, attempt, self._max_retries)
                await asyncio.sleep(sleep_for)
            except APIError as e:
                self.logger.exception("[DeepSeek] API error: %s", e)
                raise

    async def send(self, message: str, session_id: str, parent_id: Optional[str] = None) -> Dict[str, Any]:
        return await self._retryable(self.api.chat_completion, session_id, message, parent_id)

    async def create_thread(self) -> str:
        session_id: str = await self._retryable(self.api.create_chat_session)

        if self.system_prompt:
            try:
                response = await self.send(self.system_prompt, session_id)
            except Exception:
                self.logger.exception("[DeepSeek] Failed to apply system prompt for session %s", session_id)

        return session_id, response['next_parent_id']
