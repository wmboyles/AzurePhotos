from io import BytesIO
from typing import IO
from PIL import Image, ImageOps

import os
import shutil
import subprocess
import tempfile

THUMBNAIL_WIDTH = 370
THUMBNAIL_HEIGHT = 280


def thumbnail(photo_bytes: BytesIO | IO[bytes]) -> BytesIO:
    if photo_bytes.seekable():
        photo_bytes.seek(0)
    
    with Image.open(photo_bytes) as img:
        img = ImageOps.exif_transpose(img)
        img = ImageOps.fit(
            img,
            (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT),
            Image.Resampling.LANCZOS)
        
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85, optimize=True)
        buffer.seek(0)
        return buffer

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
        f"scale={THUMBNAIL_WIDTH}:{THUMBNAIL_HEIGHT}:"
        f"force_original_aspect_ratio=increase,crop={THUMBNAIL_WIDTH}:{THUMBNAIL_HEIGHT}",
        "-q:v", "2",
        "-f", "image2",
        "-vcodec", "mjpeg",
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
