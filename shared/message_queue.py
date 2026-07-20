import json
import logging
import uuid
from typing import Any, Dict, Optional

import redis

from shared.config import REDIS_URL

logger = logging.getLogger(__name__)


class MessageQueueError(RuntimeError):
    """Raised when a message cannot be sent or read because Redis is unavailable."""


class MessageQueue:
    def __init__(self, redis_url: str = REDIS_URL):
        self.redis_url = redis_url
        self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        try:
            self.redis_client.ping()
        except redis.RedisError as e:
            logger.warning(
                "Cannot connect to Redis at %s (%s). Queue operations will fail until "
                "Redis is reachable — there is no in-memory fallback.",
                redis_url, e,
            )

    def is_healthy(self) -> bool:
        try:
            return bool(self.redis_client.ping())
        except redis.RedisError:
            return False

    def send_message(self, queue_name: str, message: Dict[str, Any]) -> str:
        message_id = str(uuid.uuid4())
        message["message_id"] = message_id
        try:
            self.redis_client.lpush(queue_name, json.dumps(message))
        except redis.RedisError as e:
            raise MessageQueueError(f"Failed to enqueue message to '{queue_name}': {e}") from e
        return message_id

    def receive_message(self, queue_name: str) -> Optional[Dict[str, Any]]:
        try:
            result = self.redis_client.brpop(queue_name, timeout=1)
        except redis.RedisError as e:
            raise MessageQueueError(f"Failed to read from '{queue_name}': {e}") from e
        if result:
            return json.loads(result[1])
        return None
