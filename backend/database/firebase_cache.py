"""
AeroPark Smart System - Firebase Cache Module
Provides in-memory caching for Firebase data to reduce quota usage.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging
import asyncio
from threading import Lock

logger = logging.getLogger(__name__)


class FirebaseCache:
    """
    Simple in-memory cache for Firebase data with TTL (Time To Live).
    Reduces Firebase quota usage by caching frequent read operations.
    """
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        
    def get(self, key: str, ttl_seconds: int = 600) -> Optional[Any]:
        """
        Get cached value if it exists and hasn't expired.
        
        Args:
            key: Cache key
            ttl_seconds: Time to live in seconds (default: 10 minutes)
            
        Returns:
            Cached value or None if expired/not found
        """
        with self._lock:
            if key not in self._cache:
                return None
                
            cache_entry = self._cache[key]
            cached_at = cache_entry.get("cached_at")
            
            if not cached_at:
                return None
                
            # Check if expired
            age = datetime.utcnow() - cached_at
            if age.total_seconds() > ttl_seconds:
                # Expired, remove from cache
                del self._cache[key]
                logger.debug(f"Cache expired for key: {key}")
                return None
                
            logger.debug(f"Cache hit for key: {key} (age: {age.total_seconds():.1f}s)")
            return cache_entry.get("value")
    
    def set(self, key: str, value: Any):
        """
        Set a value in the cache with current timestamp.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            self._cache[key] = {
                "value": value,
                "cached_at": datetime.utcnow()
            }
            logger.debug(f"Cached key: {key}")
    
    def invalidate(self, key: str):
        """
        Remove a specific key from cache.
        
        Args:
            key: Cache key to invalidate
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Invalidated cache key: {key}")
    
    def invalidate_pattern(self, pattern: str):
        """
        Invalidate all keys matching a pattern.
        
        Args:
            pattern: String pattern to match (simple prefix matching)
        """
        with self._lock:
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(pattern)]
            for key in keys_to_remove:
                del self._cache[key]
                logger.debug(f"Invalidated cache key: {key}")
    
    def clear(self):
        """Clear entire cache."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared cache ({count} entries)")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                "total_entries": len(self._cache),
                "keys": list(self._cache.keys())
            }


# Global cache instance
_firebase_cache: Optional[FirebaseCache] = None
_cache_lock = Lock()


def get_firebase_cache() -> FirebaseCache:
    """Get the global Firebase cache instance (singleton)."""
    global _firebase_cache
    
    with _cache_lock:
        if _firebase_cache is None:
            _firebase_cache = FirebaseCache()
            logger.info("Firebase cache initialized")
        
        return _firebase_cache
