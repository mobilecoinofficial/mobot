from typing import Generic, Callable, TypeVar
import expiringdict


T = TypeVar('T')
V = TypeVar('V')


class LRUCache(Generic[T, V]):
    def __init__(self, ttl: int = 30):
        self.cache = expiringdict.ExpiringDict(100, max_age_seconds=ttl)

    def memoized(self, func: Callable[[T], V]) -> Callable[[T], V]:
        def inner(arg: T) -> V:
            result = self.cache.get(arg)
            if result:
                return result
            result_from_func = func(arg)
            self.cache[arg] = result_from_func
            return self.cache[arg]
        return inner