from io import BytesIO

from PIL import Image


def png_bytes(size: tuple[int, int] = (320, 240)) -> bytes:
    image = Image.new("RGB", size, (178, 112, 67))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
