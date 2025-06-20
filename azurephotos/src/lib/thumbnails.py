from io import BytesIO
from typing import IO
from PIL import Image

THUMBNAIL_SIZE = (370, 280)


def thumbnail(photo_bytes: BytesIO | IO[bytes]) -> BytesIO:
    with Image.open(photo_bytes) as img:
        img.thumbnail(THUMBNAIL_SIZE)
        buffer = BytesIO()
        img.save(buffer, img.format)
        return buffer
