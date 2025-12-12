from .redis_client import RedisClient
from common.config import configs

redis_client = RedisClient(
    url=configs.redis.url,
    max_connections=configs.redis.max_connections,
    socket_timeout=configs.redis.socket_timeout,
    socket_connect_timeout=configs.redis.socket_connect_timeout,
    decode_responses=configs.redis.decode_responses,
)

__all__ = ["redis_client", "RedisClient"]
