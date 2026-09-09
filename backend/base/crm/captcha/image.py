# Copyright 2025 FARA CRM
# Captcha module - отрисовка задачки картинкой (чтобы её нельзя было прочитать
# из DOM как текст: бот увидит только пиксели)

import base64
import io
import random

from PIL import Image, ImageDraw, ImageFont

WIDTH = 180
HEIGHT = 50


def _font(size: int):
    # Pillow >= 10.1 умеет масштабировать встроенный шрифт; на старых —
    # мелкий bitmap-фолбэк (текст останется картинкой, просто меньше).
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def render_challenge(text: str) -> str:
    """Картинка «7 + 4 = ?» → data-URI PNG. Символы дрожат, поверх — шум."""
    image = Image.new("RGB", (WIDTH, HEIGHT), (245, 247, 250))
    draw = ImageDraw.Draw(image)

    # Шум: несколько линий и точки — мешают простому OCR.
    for _ in range(4):
        draw.line(
            [
                (random.randint(0, WIDTH), random.randint(0, HEIGHT)),
                (random.randint(0, WIDTH), random.randint(0, HEIGHT)),
            ],
            fill=(random.randint(150, 210),) * 3,
            width=1,
        )
    for _ in range(140):
        draw.point(
            (random.randint(0, WIDTH), random.randint(0, HEIGHT)),
            fill=(random.randint(160, 220),) * 3,
        )

    # Текст по символам со случайным сдвигом по вертикали и цветом.
    font = _font(30)
    x = 12
    for char in f"{text} = ?":
        y = random.randint(2, 12)
        color = (
            random.randint(0, 80),
            random.randint(0, 80),
            random.randint(0, 90),
        )
        draw.text((x, y), char, font=font, fill=color)
        try:
            width = draw.textlength(char, font=font)
        except AttributeError:
            width = 12
        x += int(width) + random.randint(0, 3)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"
