from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


PHOTO_EXTENSIONS: frozenset[str] = frozenset({
    ".jpg", ".jpeg", ".jpe", ".jfif",
    ".png",
    ".webp",
    ".bmp", ".dib",
    ".tif", ".tiff",
    ".gif",
    ".mpo",
    ".heic", ".heif",
})
"""
Collection of supported file extensions for photo upload.
Should align with :obj:`thumbnails.SUPPORTED_FORMATS`.
"""

VIDEO_EXTENSIONS: frozenset[str] = frozenset({
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".m4v",
    ".3gp",
    ".3g2",
    ".ts",
    ".m2ts",
})
"""
Collection of supported file extensions for video upload.
"""


class MediaType(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"

    @classmethod
    def from_file_extension(cls, filename: str | None) -> MediaType | None:
        """
        Determine the :class:`MediaType` from the incoming file's extension.
        """
        
        if filename is None:
            return None

        extension_index = filename.rfind(".")
        if extension_index < 0:
            return None

        extension = str(filename[extension_index:]).lower()
        if extension in PHOTO_EXTENSIONS:
            return MediaType.PHOTO
        elif extension in VIDEO_EXTENSIONS:
            return MediaType.VIDEO
        else:
            return None


@dataclass(frozen=True, order=True)
class MediaRecord:
    """
    Entry representing a stored file.
    """

    last_modified: datetime
    filename: str
    type: MediaType = field(compare=False)

    @classmethod
    def from_filename(cls, last_modified: datetime, filename: str) -> MediaRecord | None:
        media_type = MediaType.from_file_extension(filename)
        if media_type is None:
            return None
        
        return cls(last_modified, filename, media_type)
