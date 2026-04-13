import os
import re
import asyncio
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from datetime import datetime

from Elevenyts import config
from Elevenyts.helpers import Track

# Modern dark glass design constants
PANEL_W, PANEL_H = 763, 545
PANEL_X = (1280 - PANEL_W) // 2
PANEL_Y = 88
TRANSPARENCY = 120  # Lower transparency for darker glass

THUMB_W, THUMB_H = 542, 273
THUMB_X = PANEL_X + (PANEL_W - THUMB_W) // 2
THUMB_Y = PANEL_Y + 36

TITLE_X = 377
TITLE_Y = THUMB_Y + THUMB_H + 10
META_Y = TITLE_Y + 45

BAR_X, BAR_Y = 388, META_Y + 45
BAR_RED_LEN = 280
BAR_TOTAL_LEN = 480

ICONS_W, ICONS_H = 415, 45
ICONS_X = PANEL_X + (PANEL_W - ICONS_W) // 2
ICONS_Y = BAR_Y + 48

MAX_TITLE_WIDTH = 580

# Watermark constants
WATERMARK_TEXT = "Adammusicbot"


def trim_to_width(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    """Trim text to fit within max width, adding ellipsis if needed."""
    ellipsis = "…"
    if font.getlength(text) <= max_w:
        return text
    for i in range(len(text) - 1, 0, -1):
        if font.getlength(text[:i] + ellipsis) <= max_w:
            return text[:i] + ellipsis
    return ellipsis


class Thumbnail:
    def __init__(self):
        try:
            self.title_font = ImageFont.truetype(
                "Elevenyts/helpers/Raleway-Bold.ttf", 32)
            self.regular_font = ImageFont.truetype(
                "Elevenyts/helpers/Inter-Light.ttf", 18)
            self.watermark_font = ImageFont.truetype(
                "Elevenyts/helpers/Raleway-Bold.ttf", 28)  # BADA KIYA (28px)
        except OSError:
            self.title_font = self.regular_font = self.watermark_font = ImageFont.load_default()

    async def save_thumb(self, output_path: str, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                with open(output_path, "wb") as f:
                    f.write(await resp.read())
            return output_path

    async def generate(self, song: Track, size=(1280, 720)) -> str:
        """Generate thumbnail - downloads async, PIL operations in thread pool"""
        try:
            temp = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}_modern.png"
            if os.path.exists(output):
                return output

            # Download thumbnail (async operation)
            await self.save_thumb(temp, song.thumbnail)
            
            # Run PIL operations in thread executor
            return await asyncio.get_event_loop().run_in_executor(
                None, self._generate_sync, temp, output, song, size
            )
        except Exception:
            return config.DEFAULT_THUMB

    def _generate_sync(self, temp: str, output: str, song: Track, size=(1280, 720)) -> str:
        """Synchronous PIL operations - runs in thread pool"""
        try:
            # Prepare base image
            with Image.open(temp) as temp_img:
                base = temp_img.resize(size).convert("RGBA")

            # Create dark blurred background
            blurred = base.filter(ImageFilter.GaussianBlur(radius=20))
            bg = ImageEnhance.Brightness(blurred).enhance(0.35)
            bg = ImageEnhance.Color(bg).enhance(0.8)
            bg = ImageEnhance.Contrast(bg).enhance(1.2)

            # Create dark glass panel
            panel_area = bg.crop(
                (PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H))
            
            dark_glass = Image.new("RGBA", (PANEL_W, PANEL_H), 
                                  (20, 25, 35, TRANSPARENCY))
            glass_border = Image.new("RGBA", (PANEL_W, PANEL_H), 
                                    (0, 0, 0, 0))
            
            draw_gradient = ImageDraw.Draw(glass_border)
            for i in range(PANEL_H):
                r = int(30 * (1 - i / PANEL_H))
                g = int(40 * (1 - i / PANEL_H) + 20 * (i / PANEL_H))
                b = int(50 * (1 - i / PANEL_H) + 60 * (i / PANEL_H))
                alpha = int(15 * (1 - i / PANEL_H))
                draw_gradient.line([(0, i), (PANEL_W, i)], 
                                  fill=(r, g, b, alpha))
            
            frosted = Image.alpha_composite(panel_area, dark_glass)
            frosted = Image.alpha_composite(frosted, glass_border)

            mask = Image.new("L", (PANEL_W, PANEL_H), 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                (0, 0, PANEL_W, PANEL_H), 40, fill=255)
            bg.paste(frosted, (PANEL_X, PANEL_Y), mask)

            border_draw = ImageDraw.Draw(bg)
            border_draw.rounded_rectangle(
                (PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H),
                40, outline=(0, 150, 255, 80), width=2)

            thumb = base.resize((THUMB_W, THUMB_H))
            
            shadow = Image.new("RGBA", (THUMB_W + 20, THUMB_H + 20), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rounded_rectangle(
                (10, 10, THUMB_W + 10, THUMB_H + 10), 15, fill=(0, 150, 255, 40))
            
            tmask = Image.new("L", thumb.size, 0)
            ImageDraw.Draw(tmask).rounded_rectangle(
                (0, 0, THUMB_W, THUMB_H), 15, fill=255)
            
            bg.paste(shadow, (THUMB_X - 10, THUMB_Y - 10), shadow)
            bg.paste(thumb, (THUMB_X, THUMB_Y), tmask)

            border_draw.rounded_rectangle(
                (THUMB_X, THUMB_Y, THUMB_X + THUMB_W, THUMB_Y + THUMB_H),
                15, outline=(0, 200, 255, 120), width=2)

            draw = ImageDraw.Draw(bg)

            clean_title = re.sub(r"\W+", " ", song.title).title()
            title_text = trim_to_width(clean_title, self.title_font, MAX_TITLE_WIDTH)
            
            for offset in range(3, 0, -1):
                draw.text((TITLE_X + offset, TITLE_Y + offset), title_text,
                         fill=(0, 150, 255, 30), font=self.title_font)
            draw.text((TITLE_X, TITLE_Y), title_text,
                     fill="#FFFFFF", font=self.title_font)

            views_text = f"▶ {song.view_count or 'Unknown Views'} views"
            draw.text((TITLE_X + 2, META_Y + 2), views_text,
                     fill=(0, 150, 255, 80), font=self.regular_font)
            draw.text((TITLE_X, META_Y), views_text,
                     fill="#BBBBBB", font=self.regular_font)

            # Progress bar
            for i in range(8):
                alpha = 100 - i * 10
                draw.line([(BAR_X, BAR_Y + i), (BAR_X + BAR_RED_LEN, BAR_Y + i)],
                         fill=(0, 150, 255, alpha), width=1)
            
            for i in range(6):
                draw.line([(BAR_X + BAR_RED_LEN, BAR_Y + i),
                          (BAR_X + BAR_TOTAL_LEN, BAR_Y + i)], 
                         fill=(60, 60, 80, 80 - i * 10), width=1)
            
            draw.ellipse([(BAR_X + BAR_RED_LEN - 8, BAR_Y - 8),
                         (BAR_X + BAR_RED_LEN + 8, BAR_Y + 8)], 
                        fill=(0, 180, 255))
            draw.ellipse([(BAR_X + BAR_RED_LEN - 4, BAR_Y - 4),
                         (BAR_X + BAR_RED_LEN + 4, BAR_Y + 4)], 
                        fill=(100, 220, 255))
            draw.ellipse([(BAR_X + BAR_RED_LEN - 2, BAR_Y - 2),
                         (BAR_X + BAR_RED_LEN + 2, BAR_Y + 2)], 
                        fill=(180, 240, 255))

            draw.text((BAR_X, BAR_Y + 15), "00:00",
                     fill="#888888", font=self.regular_font)

            is_live = getattr(song, 'is_live', False)
            end_text = "🔴 LIVE" if is_live else f"{song.duration}"
            end_color = "#00CCFF" if is_live else "#888888"
            draw.text(
                (BAR_X + BAR_TOTAL_LEN - (80 if is_live else 60), BAR_Y + 15),
                end_text,
                fill=end_color,
                font=self.regular_font
            )

            # ===== WATERMARK: DURATION LINE KE NEECHE, RED FRAME KE SAATH =====
            watermark_text = WATERMARK_TEXT
            
            # Text size calculate karo
            bbox = draw.textbbox((0, 0), watermark_text, font=self.watermark_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Position: Duration line ke neeche
            watermark_x = BAR_X + 20
            watermark_y = BAR_Y + 40  # Line ke neeche
            
            # Red frame
            frame_padding = 15
            frame_x1 = watermark_x - frame_padding
            frame_y1 = watermark_y - frame_padding
            frame_x2 = watermark_x + text_width + frame_padding
            frame_y2 = watermark_y + text_height + frame_padding
            
            # Red glow effect
            for offset in range(5, 0, -1):
                alpha = 50 - (offset * 8)
                draw.rounded_rectangle(
                    [frame_x1 - offset, frame_y1 - offset, 
                     frame_x2 + offset, frame_y2 + offset],
                    radius=10,
                    outline=(255, 40, 40, alpha),
                    width=2
                )
            
            # Main red frame
            draw.rounded_rectangle(
                [frame_x1, frame_y1, frame_x2, frame_y2],
                radius=10,
                outline=(255, 30, 30, 255),
                width=3
            )
            
            # Dark background inside frame
            draw.rounded_rectangle(
                [frame_x1, frame_y1, frame_x2, frame_y2],
                radius=10,
                fill=(0, 0, 0, 220),
                outline=None
            )
            
            # Red glow for text
            for offset in range(3, 0, -1):
                draw.text((watermark_x + offset, watermark_y + offset), watermark_text,
                         fill=(255, 50, 50, 70), font=self.watermark_font)
            
            # Main text - Bright Cyan/White
            draw.text((watermark_x, watermark_y), watermark_text,
                     fill="#00EEFF", font=self.watermark_font)
            
            # Decorative red dots
            dot_y = frame_y1 + (frame_y2 - frame_y1) // 2
            
            # Left dot
            dot_x_left = frame_x1 - 10
            draw.ellipse([(dot_x_left - 5, dot_y - 5), (dot_x_left + 5, dot_y + 5)],
                        fill=(255, 50, 50))
            draw.ellipse([(dot_x_left - 2, dot_y - 2), (dot_x_left + 2, dot_y + 2)],
                        fill=(255, 150, 150))
            
            # Right dot
            dot_x_right = frame_x2 + 10
            draw.ellipse([(dot_x_right - 5, dot_y - 5), (dot_x_right + 5, dot_y + 5)],
                        fill=(255, 50, 50))
            draw.ellipse([(dot_x_right - 2, dot_y - 2), (dot_x_right + 2, dot_y + 2)],
                        fill=(255, 150, 150))
            # ===== WATERMARK END =====

            # Control icons
            icons_path = "Elevenyts/helpers/play_icons.png"
            if os.path.isfile(icons_path):
                with Image.open(icons_path) as icons_img:
                    ic = icons_img.resize((ICONS_W, ICONS_H)).convert("RGBA")
                    r, g, b, a = ic.split()
                    cyan_ic = Image.merge(
                        "RGBA", (r.point(lambda _: 0), 
                                g.point(lambda _: 150), 
                                b.point(lambda _: 255), a))
                    bg.paste(cyan_ic, (ICONS_X, ICONS_Y), cyan_ic)

            # Vignette effect
            vignette = Image.new("RGBA", size, (0, 0, 0, 0))
            draw_vignette = ImageDraw.Draw(vignette)
            for i in range(150, 0, -1):
                alpha = int(5 * (1 - i / 150))
                draw_vignette.rectangle([(i, i), (size[0] - i, size[1] - i)],
                                      outline=(0, 0, 0, alpha))
            bg = Image.alpha_composite(bg, vignette)

            bg.save(output, "PNG", quality=95)
            try:
                os.remove(temp)
            except OSError:
                pass

            return output
        except Exception as e:
            print(f"Thumbnail generation error: {e}")
            return config.DEFAULT_THUMB
