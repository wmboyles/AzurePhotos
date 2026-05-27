import pytest

from datetime import datetime

from src.lib.models import media


class TestMediaType:
    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("photo.jpg", media.MediaType.PHOTO),
            ("photo.JPG", media.MediaType.PHOTO),
            ("video.mp4", media.MediaType.VIDEO),
            ("video.MP4", media.MediaType.VIDEO),
            ("noextension", None),
            ("document.pdf", None),
            (None, None),
        ],
    )
    def test_photo_extensions(
        self, filename: str | None, expected: media.MediaType | None
    ) -> None:
        assert media.MediaType.from_file_extension(filename) == expected


class TestMediaRecord:
    @pytest.mark.parametrize(
        ("filename", "expect_none"),
        [
            ("photo.jpg", False),
            ("video.mp4", False),
            ("noextension", True),
            ("document.pdf", True),
        ],
    )
    def test_from_filename(self, filename: str, expect_none: bool) -> None:
        last_modified = datetime(2026, 1, 1, 1, 1, 1)
        media_record = media.MediaRecord.from_filename(
            last_modified=last_modified, filename=filename
        )
        
        if expect_none:
            assert media_record is None
        else:
            assert isinstance(media_record, media.MediaRecord)
            assert media_record.last_modified == last_modified
            assert media_record.filename == filename
            assert isinstance(media_record.type, media.MediaType)
