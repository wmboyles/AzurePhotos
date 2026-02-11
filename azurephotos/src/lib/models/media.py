from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class MediaType(str, Enum):
    PHOTO = "photo",
    VIDEO = "video"

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