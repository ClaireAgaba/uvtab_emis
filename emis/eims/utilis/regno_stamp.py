import os
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings


def add_regno_to_image(img_path: str, reg_no: str) -> str:
    """
    Adds `reg_no` along the bottom of `img_path`.
    Returns the absolute path of the stamped file (same file, overwritten).
    """
    img = Image.open(img_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # pick a font – place a .ttf somewhere Django can reach, e.g. static/fonts
    font_path = os.path.join(settings.BASE_DIR, "static", "fonts", "arial.ttf")
    # fallback to default if font missing
    font = ImageFont.truetype(font_path, 20) if os.path.exists(font_path) else ImageFont.load_default()

    txt = reg_no
    w, h = img.size
    text_w, text_h = draw.textsize(txt, font=font)

    margin_x, margin_y = 10, 5
    box_height = text_h + 2 * margin_y
    # white strip
    draw.rectangle([(0, h - box_height), (w, h)], fill="white")
    # text (black)
    draw.text((margin_x, h - box_height + margin_y), txt, fill="black", font=font)

    img.save(img_path, optimize=True)
    return img_path
