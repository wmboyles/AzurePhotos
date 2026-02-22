from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


PHOTO_EXTENSIONS: frozenset[str] = frozenset([".jpg", ".jpeg", ".bmp", ".webp"])

VIDEO_EXTENSIONS: frozenset[str] = frozenset([".mp4"])


class MediaType(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"


def media_type_from_file_extension(filename: str | None) -> MediaType | None:
    if filename is None:
        return None

    extension_index = filename.rfind(".")
    if extension_index < 0:
        return None

    extension = filename[extension_index:]
    if extension in PHOTO_EXTENSIONS:
        return MediaType.PHOTO
    elif extension in VIDEO_EXTENSIONS:
        return MediaType.VIDEO
    else:
        return None


@dataclass(order=True, frozen=True)
class MediaRecord(ABC):
    last_modified: datetime
    filename: str
    type: MediaType = field(init=False)


@dataclass(order=True, frozen=True)
class PhotoRecord(MediaRecord):
    type: MediaType = field(init=False, default=MediaType.PHOTO)


@dataclass(order=True, frozen=True)
class VideoRecord(MediaRecord):
    type: MediaType = field(init=False, default=MediaType.VIDEO)
