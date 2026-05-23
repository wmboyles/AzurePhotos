import pytest

from io import BytesIO
from PIL import Image
from unittest.mock import Mock

from src.lib import thumbnails


class TestThumbnail:
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
            loop=0
        )
        buffer.seek(0)
        return buffer

    def test_thumbnail(self) -> None:
        photo = self.make_image()
        result = thumbnails.thumbnail(photo)

        assert isinstance(result, BytesIO)
        assert result.tell() == 0 # rewinds buffer

        with Image.open(result) as img:
            img.load() # ensures output is readable
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

        with pytest.raises(
            ValueError,
            match="Unsupported image format"
        ):
            _ = thumbnails.thumbnail(photo)

    def test_thumbnail_decompression_bomb(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(thumbnails.Image, "open", Mock(side_effect=Image.DecompressionBombError))

        with pytest.raises(ValueError, match="Image is too large"):
            _ = thumbnails.thumbnail(BytesIO(b"decompression bomb"))

    def test_thumbnail_too_large(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Set a tiny limit for testing
        monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)

        buffer = self.make_image(size=(100,100), image_format="PNG") # 10,000 pixels lossless
        with pytest.raises(ValueError, match="Image is too large"):
            _ = thumbnails.thumbnail(buffer)