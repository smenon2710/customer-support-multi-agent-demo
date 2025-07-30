import redis
import json
from typing import Dict, Any
import uuid

class MessageQueue:
    def __init__(self, host='localhost', port=6379, db=0):
        try:
            self.redis_client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
            self.redis_client.ping()
        except:
            # Fallback to in-memory queue for demo
            self.redis_client = None
            self.memory_queue = {}
    
    def send_message(self, queue_name: str, message: Dict[Any, Any]) -> str:
        message_id = str(uuid.uuid4())
        message['message_id'] = message_id
        
        if self.redis_client:
            self.redis_client.lpush(queue_name, json.dumps(message))
        else:
            if queue_name not in self.memory_queue:
                self.memory_queue[queue_name] = []
            self.memory_queue[queue_name].append(message)
        
        return message_id
    
    def receive_message(self, queue_name: str) -> Dict[Any, Any]:
        if self.redis_client:
            message = self.redis_client.brpop(queue_name, timeout=1)
            if message:
                return json.loads(message[1])
        else:
            if queue_name in self.memory_queue and self.memory_queue[queue_name]:
                return self.memory_queue[queue_name].pop(0)
        return None
