from datetime import datetime, timezone


class FakeDateTime:
    current = datetime(2026, 1, 1, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return cls.current.astimezone(tz)

        return cls.current
