"""Compose preview.png from the real native capture. Developer-only: Pillow."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', type=Path, required=True, help='Installed bold sans-serif TTF')
    parser.add_argument('--regular-font', type=Path, required=True)
    parser.add_argument('--symbols-font', type=Path, required=True, help='Symbols Nerd Font Mono TTF')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'preview.png')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    canvas = Image.new('RGB', (1920, 1080), '#20282e')
    draw = ImageDraw.Draw(canvas)
    accent, ink, muted = '#a7c080', '#e7e9df', '#b4bcb7'

    def text(x, y, value, size, color=ink, bold=False, max_width=475):
        font = ImageFont.truetype(str(args.font if bold else args.regular_font), size)
        bounds = draw.textbbox((x, y), value, font=font)
        assert bounds[2] - bounds[0] <= max_width, 'Text overflow: ' + value
        assert bounds[2] <= canvas.width and bounds[3] <= canvas.height
        draw.text((x, y), value, font=font, fill=color)

    text(72, 60, 'OMARCHY / WORKSPACES', 22, accent, bold=True)
    pin_font = ImageFont.truetype(str(args.symbols_font), 75)
    glyph = chr(0xF0403)
    box = draw.textbbox((0, 0), glyph, font=pin_font)
    draw.text((72-box[0], 151-box[1]), glyph, font=pin_font, fill=accent)
    text(72, 245, 'Workspace', 74, bold=True)
    text(72, 325, 'Pins', 74, bold=True)
    text(72, 470, 'Pin apps to', 43, bold=True)
    text(72, 526, 'workspaces.', 43, bold=True)
    text(72, 620, 'Assign once.', 29, muted)
    text(72, 664, 'Open where it belongs.', 29, muted)
    draw.line((72, 717, 499, 717), fill='#45524a', width=2)
    text(72, 750, 'Click. Drag. Keyboard.', 27, accent)
    text(72, 802, 'No Lua. No extra packages.', 25, muted)
    text(72, 1006, 'v0.6.0  /  github.com/jcarcinogen/OmaValet', 18, muted, max_width=650)

    screenshot = Image.open(root / 'examples/board-dark.png').convert('RGB')
    screenshot.thumbnail((1260, 850), Image.Resampling.LANCZOS)
    x, y = 600, 125
    draw.rectangle((x-3, y-3, x+screenshot.width+2, y+screenshot.height+2), fill='#607257')
    canvas.paste(screenshot, (x, y))
    text(x, 1006, 'Native Omarchy UI · Theme-aware · Your rules stay yours', 21, muted, max_width=1260)
    canvas.save(args.output, optimize=True)
    with Image.open(args.output) as result:
        result.verify()
    print(str(args.output))


if __name__ == '__main__':
    main()
