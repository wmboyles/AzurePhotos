from datetime import datetime, timezone, timedelta
from typing import Callable, Any, TypeVar
from functools import wraps

MIN_UTC_TIME = datetime(
    year=1, month=1, day=1, hour=0, minute=0, second=0, tzinfo=timezone.utc
)

T = TypeVar("T")


def refreshed(every: timedelta) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache = dict[tuple[Any, Any], tuple[T, datetime]]()

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            now = datetime.now(timezone.utc)
            (result, last_called) = cache.get(
                (args, tuple(kwargs.items())), (None, MIN_UTC_TIME)
            )
            if result is None or now - last_called >= every:
                result = func(*args, **kwargs)
                last_called = now
                cache[(args, tuple(kwargs.items()))] = (result, last_called)

            return result

        return wrapper

    return decorator
