import pytest

from flask import Flask
from io import BytesIO
from PIL import Image
from subprocess import CalledProcessError, CompletedProcess
from unittest.mock import Mock

from src.lib import thumbnails


class TestPhotoThumbnail:
    @staticmethod
    def make_image(
        *,
        size: tuple[int, int] = (1000, 800),
        mode: str = "RGB",
        image_format: str = "JPEG",
        color: float | tuple[float, ...] | str = "red"
    ) -> BytesIO:
        img = Image.new(mode, size, color)
        buffer = BytesIO()
        img.save(buffer, format=image_format)
        buffer.seek(0)
        return buffer

    @staticmethod
    def make_multiframe_gif(
        *,
        size: tuple[int, int] = (1000, 800),
        mode: str = "RGB",
        n_frames: int = 2,
        duration: int = 100
    ) -> BytesIO:
        colors = ["red", "green", "blue"]
        frames = list[Image.Image]()
        for i in range(n_frames):
            color = colors[i % 3]
            frame = Image.new(mode, size, color)
            frames.append(frame)

        buffer = BytesIO()
        frames[0].save(
            buffer,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=duration,
            loop=0,
        )
        buffer.seek(0)
        return buffer

    def test_thumbnail(self) -> None:
        photo = self.make_image()
        result = thumbnails.thumbnail(photo)

        assert isinstance(result, BytesIO)
        assert result.tell() == 0  # rewinds buffer

        with Image.open(result) as img:
            img.load()  # ensures output is readable
            assert img.format == thumbnails.OUTPUT_FORMAT
            assert img.size == thumbnails.SIZE

    def test_thumbnail_rgba(self) -> None:
        photo = self.make_image(mode="RGBA", image_format="PNG")
        result = thumbnails.thumbnail(photo)

        with Image.open(result) as img:
            assert img.mode in ("RGB", "L")

    def test_thumbnail_gif(self) -> None:
        n_frames = 2
        photo = self.make_multiframe_gif(n_frames=n_frames)
        with Image.open(photo) as img:
            assert getattr(img, "n_frames") == n_frames

        result = thumbnails.thumbnail(photo)

        assert isinstance(result, BytesIO)
        assert result.tell() == 0

        with Image.open(result) as img:
            img.load()
            assert img.format == thumbnails.OUTPUT_FORMAT
            assert img.size == thumbnails.SIZE

    def test_thumbnail_unsupported_format(self) -> None:
        image_format = "PPM"
        assert image_format not in thumbnails.SUPPORTED_FORMATS

        photo = self.make_image(image_format=image_format)

        with pytest.raises(ValueError, match="Unsupported image format"):
            _ = thumbnails.thumbnail(photo)

    def test_thumbnail_decompression_bomb(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            thumbnails.Image, "open", Mock(side_effect=Image.DecompressionBombError)
        )

        with pytest.raises(ValueError, match="Image is too large"):
            _ = thumbnails.thumbnail(BytesIO(b"decompression bomb"))

    def test_thumbnail_too_large(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Set a tiny limit for testing
        monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)

        buffer = self.make_image(
            size=(100, 100), image_format="PNG"
        )  # 10,000 pixels lossless
        with pytest.raises(ValueError, match="Image is too large"):
            _ = thumbnails.thumbnail(buffer)


class TestVideoThumbnail:
    @pytest.fixture(autouse=True)
    def _setup(self, app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
        self.app = app

        monkeypatch.setattr(thumbnails.os.path, "exists", lambda _: True)

    def test_video_thumbnail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(*args, **kwargs):
            return CompletedProcess(
                args=[], returncode=0, stdout=b"thumbnail-bytes", stderr=b""
            )

        monkeypatch.setattr(thumbnails.subprocess, "run", fake_run)

        with self.app.app_context():
            result = thumbnails.video_thumbnail(
                "video.mp4", ffmpeg_path="/usr/bin/ffmpeg"
            )

        assert result == b"thumbnail-bytes"

    def test_video_thumbnail_zero_seconds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = []

        def fake_run(*args, **kwargs):
            cmd = kwargs["args"]
            calls.append(cmd)
            if len(calls) == 1: # hits here on first attempt
                return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

            return CompletedProcess(
                args=[], returncode=0, stdout=b"thumbnail-bytes", stderr=b""
            )

        monkeypatch.setattr(thumbnails.subprocess, "run", fake_run)

        with self.app.app_context():
            result = thumbnails.video_thumbnail(
                "video.mp4", ffmpeg_path="/usr/bin/ffmpeg"
            )

        assert result == b"thumbnail-bytes"
        assert "-ss" in calls[0]
        assert "1" in calls[1]

        assert "-ss" in calls[1]
        assert "0" in calls[1]

    def test_video_thumbnail_missing_ffmpeg(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(thumbnails.shutil, "which", lambda _: None)

        with pytest.raises(Exception, match="Cannot find ffmpeg"):
            thumbnails.video_thumbnail("video.mp4", ffmpeg_path=None)

    def test_video_thumbnail_missing_icon(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(thumbnails.os.path, "exists", lambda _: False)

        with self.app.app_context():
            with pytest.raises(Exception, match="Cannot find video icon"):
                thumbnails.video_thumbnail("video.mp4", ffmpeg_path="/usr/bin/ffmpeg")

    def test_video_thumbnail_no_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(*args, **kwargs):
            return CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

        monkeypatch.setattr(thumbnails.subprocess, "run", fake_run)

        with self.app.app_context():
            with pytest.raises(RuntimeError, match="No output from ffmpeg process"):
                thumbnails.video_thumbnail("video.mp4", ffmpeg_path="/usr/bin/ffmpeg")

    def test_video_thumbnail_ffmpeg_failed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_run(*args, **kwargs):
            raise CalledProcessError(returncode=1, cmd="ffmpeg", stderr=b"bad-video")

        monkeypatch.setattr(thumbnails.subprocess, "run", fake_run)

        with self.app.app_context():
            with pytest.raises(RuntimeError, match="ffmpeg failed"):
                thumbnails.video_thumbnail("video.mp4", ffmpeg_path="/usr/bin/ffmpeg")
