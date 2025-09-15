import logging
from ai.skeleton import Skeleton
from dsk.api import DeepSeekAPI, AuthenticationError, RateLimitError, NetworkError, APIError
import asyncio

class DeepSeek(Skeleton):
    def __init__(self, logger: logging, key: str):
        self.logger = logger
        self.api = DeepSeekAPI(key)
    
    async def send(self, message: str, session_id: str, parent_id: str) -> dict:
        response = None
        
        try:
            response = await self._send(message, session_id, parent_id)
        except (AuthenticationError, RateLimitError, NetworkError, APIError) as e:
            self.logger.error("[DeepSeek][send] DeepSeek error: %s", e)
        finally:
            return response
    
    async def _send(self, message: str, session_id: str, parent_id: str) -> dict:
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, self.api.chat_completion, session_id, message, parent_id)
        finally:
            loop.close()
