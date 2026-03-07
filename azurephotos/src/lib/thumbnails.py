from io import BytesIO
from typing import IO
from PIL import Image, ImageFile, ImageOps
from PIL.Image import DecompressionBombError

import os
import shutil
import subprocess
import tempfile

WIDTH = 370
HEIGHT = 280
SIZE = (WIDTH, HEIGHT)
OUTPUT_FORMAT = "WEBP" # TODO: WEBP for video thumbnails possible?

# Protect against maliciously large images
# TODO: Should this be enforced before the call to thumbnail in upload logic?
# Maybe also a frontend size limit?
Image.MAX_IMAGE_PIXELS = 1 << 26

# Allow truncated images
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Base formats supported by Pillow
_supported_formats: set[str] = {
    "JPEG",
    "PNG",
    "WEBP",
    "BMP",
    "TIFF",
    "GIF",
    "MPO"
}

# Optional HEIC/HEIF support
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    _supported_formats.update({"HEIC", "HEIF"})
except ImportError:
    pass

SUPPORTED_FORMATS = frozenset(_supported_formats)

def thumbnail(photo_bytes: IO[bytes]) -> BytesIO:
    """
    Create a compressed thumbnail of an image.

    - Maintains EXIF orientation
    - Converts to an efficient output format
    - Strips other metadata
    """
    
    if photo_bytes.seekable():
        photo_bytes.seek(0)

    try:
        with Image.open(photo_bytes) as img:
            # Validate format if known
            img_format = img.format.upper() if img.format else None
            if img_format and img_format not in SUPPORTED_FORMATS:
                raise ValueError(f"Unsupported image format {img_format}")
            
            # Faster decoding for large JPEGs
            img.draft("RGB", SIZE)

            # Maintain EXIF orientation
            ImageOps.exif_transpose(img, in_place=True)

            # Ensure only first frame for animated or multiframe images
            if getattr(img, "n_frames", 1) > 1:
                img.seek(0)

            # Normalize color mode
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Early downscale for very large images
            img.thumbnail(
                (SIZE[0] * 4, SIZE[1] * 4),
                Image.Resampling.BOX
            )

            # Crop and resize
            img = ImageOps.fit(
                img,
                SIZE,
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.45)
            )

            # Save to buffer
            buffer = BytesIO()
            img.save(
                buffer,
                OUTPUT_FORMAT,
                quality=82,
                method=6, # encoder effort
                exact=False # ok with losing RGB data in transparent pixels
            )

            buffer.seek(0)
            return buffer
    except DecompressionBombError:
        raise ValueError("Image is too large")

def video_thumbnail(video_bytes: IO[bytes]) -> bytes:
    # find ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise Exception("Cannot find ffmpeg")
    
    if video_bytes.seekable():
        video_bytes.seek(0)

    # Copy bytes to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
        shutil.copyfileobj(video_bytes, temp_video)
        temp_video.flush()
        temp_video_path = temp_video.name

    # Use ffmpeg to compute thumbnail
    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel", "error",
        "-ss", "1",
        "-i", temp_video_path,
        "-frames:v", "1",
        "-vf",
        f"scale={WIDTH}:{HEIGHT}:"
        f"force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT}",
        "-vcodec", "libwebp",
        "-quality", "82",
        "-compression_level", "6",
        "-f", "image2",
        "pipe:1",
    ]
    try:
        process = subprocess.run(
            args = cmd,
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
            check = True
        )
        
        process_stdout = process.stdout
        if process_stdout is None or len(process_stdout) == 0:
            raise RuntimeError("No output from ffmpeg process")
        
        return process_stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"ffmpeg failed:\n{e.stderr.decode(errors='ignore')}"
        ) from e
    finally:
        os.remove(temp_video_path)