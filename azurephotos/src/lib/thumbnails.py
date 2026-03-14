from flask import current_app
from io import BytesIO
from PIL import Image, ImageFile, ImageOps
from PIL.Image import DecompressionBombError
from typing import IO

import os
import shutil
import subprocess
import tempfile

WIDTH = 384
HEIGHT = 384
SIZE = (WIDTH, HEIGHT)
OUTPUT_FORMAT = "WEBP"

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
    - Converts to an efficient output format (:obj:`OUTPUT_FORMAT`)
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
    """
    Create a compressed thumbnail of a video.

    - Converts to an efficient output format (:obj:`OUTPUT_FORMAT`)
    - Takes thumbnail from first second of video, falling back to 0 seconds if video is shorter than 1 second
    - Appends a play button icon to the top-left of the thumbnail to differentiate it from photo thumbnails
    """
    
    # find ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise Exception("Cannot find ffmpeg")
    
    # find video icon
    video_icon_path = os.path.join(str(current_app.static_folder), "video_icon.png")
    if not os.path.exists(video_icon_path):
        raise Exception("Cannot find video icon")

    if video_bytes.seekable():
        video_bytes.seek(0)

    # Copy bytes to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
        shutil.copyfileobj(video_bytes, temp_video)
        temp_video.flush()
        temp_video_path = temp_video.name

    # Use ffmpeg to compute thumbnail
    def run_ffmpeg(seek_seconds: int = 1) -> bytes:
        cmd = [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel", "error",
            "-ss", str(seek_seconds),
            "-i", temp_video_path,
            "-i", video_icon_path,
            "-frames:v", "1",
            "-filter_complex",
            f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase," # extending string over multiple lines
                f"crop={WIDTH}:{HEIGHT}[thumb];"
                "[1:v]format=rgba,scale=64:-1:flags=lanczos[icon];"
                "[thumb][icon]overlay=10:10", # top-left corner
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
                if seek_seconds != 0: # fallback to seeking to 0 seconds
                    return run_ffmpeg(seek_seconds=0)
                else:
                    raise RuntimeError("No output from ffmpeg process")
        
            return process_stdout
        except subprocess.CalledProcessError as e:
            # TODO: Should we create a default thumbnail? Maybe this can be done in /thumbnail route?
            raise RuntimeError(
                f"ffmpeg failed:\n{e.stderr.decode(errors='ignore')}"
            ) from e
        finally:
            os.remove(temp_video_path)

    ffmpeg_results = run_ffmpeg()
    if ffmpeg_results is None or len(ffmpeg_results) == 0:
        raise RuntimeError("No output from ffmpeg process")

    return ffmpeg_results
