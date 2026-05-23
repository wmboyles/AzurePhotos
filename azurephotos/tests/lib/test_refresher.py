import pytest
from datetime import datetime, timedelta, timezone

from src.lib import refresher
from tests.mocks import FakeDateTime

class TestRefresher:
    CACHE_WINDOW = timedelta(seconds=10)

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.call_count = 0

        FakeDateTime.current = datetime(2025, 1, 1, tzinfo=timezone.utc)

        monkeypatch.setattr(refresher, "datetime", FakeDateTime)

        @refresher.refreshed(every=TestRefresher.CACHE_WINDOW)
        def myfunc(x: int) -> int:
            self.call_count += 1
            return x * 2

        self.myfunc = myfunc

    def test_refreshed_cached(self) -> None:
        # First call executes function
        assert self.myfunc(3) == 6
        assert self.call_count == 1

        # Second call within cache window uses cached value, so call_count doesn't increase
        FakeDateTime.current += TestRefresher.CACHE_WINDOW / 2
        assert self.myfunc(3) == 6
        assert self.call_count == 1

    def test_refreshed_expired(self) -> None:
        # First call executes function
        assert self.myfunc(3) == 6
        assert self.call_count == 1

        # Second call outside cache window recalculates, so call_count increases
        FakeDateTime.current += TestRefresher.CACHE_WINDOW * 2
        assert self.myfunc(3) == 6
        assert self.call_count == 2

    def test_refreshed_separate(self) -> None:
        assert self.myfunc(1) == 2
        assert self.myfunc(2) == 4
        assert self.call_count == 2
