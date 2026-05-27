from datetime import datetime, timezone
from typing import cast
from unittest.mock import Mock

class FakeDateTime:
    current = datetime(2026, 1, 1, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return cls.current.astimezone(tz)

        return cls.current

def as_mock(value: object) -> Mock:
    return cast(Mock, value)
