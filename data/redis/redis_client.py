"""Redis client wrapper for OASM Assistant"""
import redis
from redis.asyncio import Redis as AsyncRedis
from common.logger import logger


class RedisClient:
    """Thin wrapper around redis-py client"""
    
    def __init__(
        self,
        url: str,
        max_connections: int = 10,
        socket_timeout: int = 5,
        socket_connect_timeout: int = 5,
        decode_responses: bool = True,
    ):
        """Initialize Redis client"""
        try:
            # Sync client
            self.client = redis.from_url(
                url,
                max_connections=max_connections,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_connect_timeout,
                decode_responses=decode_responses,
            )
            
            # Async client
            self.async_client = AsyncRedis.from_url(
                url,
                max_connections=max_connections,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_connect_timeout,
                decode_responses=decode_responses,
            )
            
            # Test connection
            self.client.ping()
            logger.info(f"Redis connected")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def __getattr__(self, name):
        """Delegate all other methods to sync client"""
        return getattr(self.client, name)
    
    async def health_check(self) -> bool:
        """Check Redis health"""
        try:
            await self.async_client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
    
    def close(self):
        """Close connections"""
        try:
            self.client.close()
        except Exception as e:
            logger.error(f"Error closing Redis: {e}")
    
    async def aclose(self):
        """Async close connections"""
        try:
            await self.async_client.close()
        except Exception as e:
            logger.error(f"Error closing async Redis: {e}")
