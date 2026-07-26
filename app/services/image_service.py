from io import BytesIO
from typing import Protocol

from PIL import (
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageFont,
    ImageOps,
    UnidentifiedImageError,
)


class ImageGenerator(Protocol):
    def generate(
        self, prompt: str, reference_image: bytes, product_name: str
    ) -> bytes: ...


class MockImageGenerator:
    canvas_size = (1024, 1024)

    def generate(
        self, prompt: str, reference_image: bytes, product_name: str
    ) -> bytes:
        del prompt  # The mock preserves the provider interface for later replacement.
        try:
            with Image.open(BytesIO(reference_image)) as opened:
                source = ImageOps.exif_transpose(opened)
                source.load()
                source = source.convert("RGBA")
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValueError("The uploaded file is not a readable image") from exc

        background = ImageOps.fit(
            source.convert("RGB"),
            self.canvas_size,
            method=Image.Resampling.LANCZOS,
        )
        background = background.filter(ImageFilter.GaussianBlur(radius=36))
        background = ImageEnhance.Brightness(background).enhance(0.78)
        canvas = background.convert("RGBA")
        canvas.alpha_composite(Image.new("RGBA", self.canvas_size, (245, 242, 238, 92)))

        product = source.copy()
        product.thumbnail((760, 680), Image.Resampling.LANCZOS)
        x = (self.canvas_size[0] - product.width) // 2
        y = (self.canvas_size[1] - product.height) // 2 - 20

        shadow = Image.new("RGBA", self.canvas_size, (0, 0, 0, 0))
        shadow_layer = Image.new("RGBA", product.size, (0, 0, 0, 0))
        shadow_layer.putalpha(product.getchannel("A").point(lambda alpha: alpha // 3))
        shadow.alpha_composite(shadow_layer, (x + 14, y + 20))
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=18))
        canvas.alpha_composite(shadow)
        canvas.alpha_composite(product, (x, y))

        draw = ImageDraw.Draw(canvas)
        label_font = self._font(22, bold=True)
        name_font = self._font(34, bold=True)
        label_box = (44, 42, 190, 82)
        draw.rounded_rectangle(label_box, radius=20, fill=(255, 255, 255, 210))
        draw.text((61, 51), "AI Preview", fill=(38, 38, 38, 255), font=label_font)

        display_name = self._fit_text(draw, product_name, name_font, 900)
        text_box = draw.textbbox((0, 0), display_name, font=name_font)
        text_width = text_box[2] - text_box[0]
        draw.rounded_rectangle(
            (42, 919, 982, 982), radius=18, fill=(20, 20, 20, 185)
        )
        draw.text(
            ((1024 - text_width) // 2, 932),
            display_name,
            fill=(255, 255, 255, 255),
            font=name_font,
        )

        output = BytesIO()
        canvas.convert("RGB").save(output, format="PNG", optimize=True)
        return output.getvalue()

    @staticmethod
    def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
        candidates = (
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
            "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        )
        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
        return ImageFont.load_default()

    @staticmethod
    def _fit_text(
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.ImageFont,
        max_width: int,
    ) -> str:
        cleaned = " ".join(text.split())
        if draw.textlength(cleaned, font=font) <= max_width:
            return cleaned
        while cleaned and draw.textlength(f"{cleaned}…", font=font) > max_width:
            cleaned = cleaned[:-1]
        return f"{cleaned.rstrip()}…"
