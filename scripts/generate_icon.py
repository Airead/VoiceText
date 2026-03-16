"""Generate a macOS-style app icon for WenZi.

Creates a clean 1024x1024 icon with a microphone on the left
and text lines on the right, clearly separated.
"""

from PIL import Image, ImageDraw, ImageFilter


def make_superellipse_mask(size: int, n: float = 5.0) -> Image.Image:
    """Create a macOS-style squircle (superellipse) mask."""
    mask = Image.new("L", (size, size), 0)
    cx, cy = size / 2, size / 2
    r = size / 2 * 0.92

    for y in range(size):
        for x in range(size):
            dx = abs(x - cx) / r
            dy = abs(y - cy) / r
            if dx ** n + dy ** n <= 1.0:
                mask.putpixel((x, y), 255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=2))
    return mask


def draw_gradient(img: Image.Image, color_top: tuple, color_bottom: tuple):
    """Draw a vertical linear gradient."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for y in range(h):
        t = y / h
        r = int(color_top[0] + (color_bottom[0] - color_top[0]) * t)
        g = int(color_top[1] + (color_bottom[1] - color_top[1]) * t)
        b = int(color_top[2] + (color_bottom[2] - color_top[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def draw_microphone(draw: ImageDraw.Draw, cx: int, cy: int, s: float):
    """Draw a clean microphone icon centered at (cx, cy)."""
    white = (255, 255, 255)
    white_semi = (255, 255, 255, 210)

    # Mic capsule (pill shape)
    cap_w = int(75 * s)
    cap_h = int(190 * s)
    cap_r = int(75 * s)
    cap_top = cy - int(160 * s)
    draw.rounded_rectangle(
        [cx - cap_w, cap_top, cx + cap_w, cap_top + cap_h],
        radius=cap_r,
        fill=white,
    )

    # Grille lines on capsule
    for i in range(3):
        ly = cap_top + int(50 * s) + i * int(40 * s)
        draw.line(
            [(cx - int(45 * s), ly), (cx + int(45 * s), ly)],
            fill=(160, 190, 245),
            width=int(4 * s),
        )

    # U-shaped cradle
    cradle_w = int(110 * s)
    cradle_top = cy - int(80 * s)
    cradle_h = int(180 * s)
    draw.arc(
        [cx - cradle_w, cradle_top, cx + cradle_w, cradle_top + cradle_h],
        start=0, end=180,
        fill=white_semi,
        width=int(12 * s),
    )

    # Vertical stand
    stand_top = cradle_top + int(90 * s)
    stand_h = int(70 * s)
    stand_w = int(6 * s)
    draw.rectangle(
        [cx - stand_w, stand_top, cx + stand_w, stand_top + stand_h],
        fill=white_semi,
    )

    # Base
    base_top = stand_top + stand_h
    base_w = int(55 * s)
    base_h = int(10 * s)
    draw.rounded_rectangle(
        [cx - base_w, base_top, cx + base_w, base_top + base_h],
        radius=int(5 * s),
        fill=white_semi,
    )


def draw_text_lines(draw: ImageDraw.Draw, left_x: int, cy: int, s: float):
    """Draw three horizontal lines representing text output."""
    line_color = (255, 255, 255, 220)
    line_h = int(14 * s)
    line_r = int(7 * s)
    gap = int(36 * s)
    start_y = cy - int(50 * s)

    widths = [240, 190, 140]
    for i, w in enumerate(widths):
        lw = int(w * s)
        ly = start_y + i * gap
        draw.rounded_rectangle(
            [left_x, ly, left_x + lw, ly + line_h],
            radius=line_r,
            fill=line_color,
        )


def draw_arrow(draw: ImageDraw.Draw, cx: int, cy: int, s: float):
    """Draw a small right-pointing arrow between mic and text."""
    arrow_color = (255, 255, 255, 150)
    ax = cx
    ay = cy - int(20 * s)
    size_h = int(25 * s)
    size_w = int(20 * s)

    # Arrow triangle
    points = [
        (ax, ay - size_h),
        (ax + size_w, ay),
        (ax, ay + size_h),
    ]
    draw.polygon(points, fill=arrow_color)


def generate_icon(output_path: str = "icon.png", size: int = 1024):
    """Generate the WenZi app icon."""
    # Gradient background
    base = Image.new("RGB", (size, size))
    draw_gradient(base, (50, 130, 255), (130, 70, 220))

    # RGBA overlay
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    s = size / 1024
    cx, cy = size // 2, size // 2

    # Microphone on the left
    mic_cx = cx - int(170 * s)
    draw_microphone(od, mic_cx, cy, s)

    # Arrow in the middle
    draw_arrow(od, cx - int(20 * s), cy, s)

    # Text lines on the right
    text_left = cx + int(50 * s)
    draw_text_lines(od, text_left, cy, s)

    # Composite
    base_rgba = base.convert("RGBA")
    composited = Image.alpha_composite(base_rgba, overlay)

    # Apply squircle mask
    mask = make_superellipse_mask(size)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(composited, (0, 0), mask)

    # Top highlight
    highlight = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(highlight)
    for y in range(size // 4):
        alpha = int(35 * (1 - y / (size // 4)))
        h_draw.line([(0, y), (size, y)], fill=(255, 255, 255, alpha))
    result = Image.alpha_composite(
        result,
        Image.composite(
            highlight,
            Image.new("RGBA", (size, size), (0, 0, 0, 0)),
            mask.copy(),
        ),
    )

    # Drop shadow
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 45), (int(6 * s), int(6 * s)), mask.copy())
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=int(12 * s)))

    final = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    final = Image.alpha_composite(final, shadow)
    final = Image.alpha_composite(final, result)

    final.save(output_path, "PNG")
    print(f"Icon saved to {output_path} ({size}x{size})")


if __name__ == "__main__":
    generate_icon("resources/icon.png")
