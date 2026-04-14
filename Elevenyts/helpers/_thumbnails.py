import os
import asyncio
import aiohttp
from PIL import (
    Image, ImageDraw, ImageEnhance,
    ImageFilter, ImageFont
)

from Elevenyts import config
from Elevenyts.helpers import Track

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CANVAS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
W, H = 1280, 720

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  WHITE CARD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CARD_W  = 800
CARD_H  = 590
CARD_X  = (W - CARD_W) // 2
CARD_Y  = (H - CARD_H) // 2
CARD_R  = 42

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ALBUM ART (inside card, top)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ART_PAD = 24
ART_W   = CARD_W - ART_PAD * 2
ART_H   = 295
ART_X   = CARD_X + ART_PAD
ART_Y   = CARD_Y + ART_PAD
ART_R   = 22

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEXT POSITIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TXT_X    = CARD_X + 30
TITLE_Y  = ART_Y + ART_H + 20
VIEWS_Y  = TITLE_Y + 58
BAR_Y    = VIEWS_Y + 48
BAR_X    = CARD_X + 30
BAR_W    = CARD_W - 60
BAR_H    = 7
TIME_Y   = BAR_Y + 18
CTRL_Y   = TIME_Y + 42
MARK_Y   = CARD_Y + CARD_H - 34

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  COLORS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
C_CARD       = (250, 250, 252, 228)
C_TITLE      = (22,  22,  28,  255)
C_SUBTEXT    = (105, 105, 115, 255)
C_RED        = (215, 48,  48,  255)
C_BAR_TRACK  = (205, 205, 210, 255)
C_CTRL       = (28,  28,  34,  255)
C_MARK       = (200, 48,  48,  190)


class Thumbnail:

    def __init__(self):
        base = "Elevenyts/helpers"
        try:
            self.font_title  = ImageFont.truetype(f"{base}/Syne-Bold.ttf",      40)
            self.font_views  = ImageFont.truetype(f"{base}/DMSans-Regular.ttf",  26)
            self.font_time   = ImageFont.truetype(f"{base}/DMSans-Regular.ttf",  23)
            self.font_ctrl   = ImageFont.truetype(f"{base}/DMSans-Regular.ttf",  34)
            self.font_mark   = ImageFont.truetype(f"{base}/DMSans-Medium.ttf",   21)
        except Exception as e:
            print(f"[Thumbnail] Font load error: {e} — using default")
            _f = ImageFont.load_default()
            self.font_title = self.font_views = self.font_time = \
                self.font_ctrl = self.font_mark = _f

    # ── Download YouTube thumbnail ───────────────────────
    async def _fetch(self, path: str, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                with open(path, "wb") as f:
                    f.write(await resp.read())
        return path

    # ── Public entry point ───────────────────────────────
    async def generate(self, song: Track) -> str:
        try:
            os.makedirs("cache", exist_ok=True)
            temp   = f"cache/{song.id}_raw.jpg"
            output = f"cache/{song.id}_card.png"

            if os.path.exists(output):
                return output

            await self._fetch(temp, song.thumbnail)

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._draw, temp, output, song
            )
        except Exception as e:
            print(f"[Thumbnail] generate() error: {e}")
            return config.DEFAULT_THUMB

    # ── Main draw ────────────────────────────────────────
    def _draw(self, temp: str, output: str, song: Track) -> str:
        try:
            raw = Image.open(temp).convert("RGBA")

            # 1. Blurred + darkened background from album art
            bg = raw.resize((W, H), Image.LANCZOS)
            bg = bg.filter(ImageFilter.GaussianBlur(38))
            bg = ImageEnhance.Brightness(bg).enhance(0.55)
            bg = ImageEnhance.Saturation(bg).enhance(1.4)  # more vivid bg

            # 2. White card
            card_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(card_layer, "RGBA").rounded_rectangle(
                (CARD_X, CARD_Y, CARD_X + CARD_W, CARD_Y + CARD_H),
                radius=CARD_R,
                fill=C_CARD
            )
            bg = Image.alpha_composite(bg, card_layer)

            # 3. Subtle card shadow (darker rounded rect behind card)
            shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(shadow, "RGBA").rounded_rectangle(
                (CARD_X + 8, CARD_Y + 12,
                 CARD_X + CARD_W + 8, CARD_Y + CARD_H + 12),
                radius=CARD_R,
                fill=(0, 0, 0, 55)
            )
            # Insert shadow below card
            base_with_shadow = Image.alpha_composite(
                bg.copy().split()[0:3][0].convert("RGBA"), shadow
            )
            # Simpler: just composite on bg before card
            bg2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            bg2 = Image.alpha_composite(
                Image.alpha_composite(
                    raw.resize((W, H), Image.LANCZOS)
                       .filter(ImageFilter.GaussianBlur(38))
                       .convert("RGBA"),
                    shadow
                ),
                card_layer
            )
            # Apply brightness to the composited result
            bg = ImageEnhance.Brightness(bg2).enhance(0.72)

            # 4. Album art inside card (rounded)
            art      = raw.resize((ART_W, ART_H), Image.LANCZOS)
            art_mask = Image.new("L", (ART_W, ART_H), 0)
            ImageDraw.Draw(art_mask).rounded_rectangle(
                (0, 0, ART_W, ART_H), radius=ART_R, fill=255
            )
            bg.paste(art, (ART_X, ART_Y), art_mask)

            draw = ImageDraw.Draw(bg, "RGBA")

            # 5. Song title — split into 2 parts at pipe or middle
            title = song.title.strip()
            # Try split at | or — or •
            for sep in ["|", "—", "•", "-"]:
                if sep in title:
                    parts = title.split(sep, 1)
                    t1 = parts[0].strip()
                    t2 = parts[1].strip()
                    break
            else:
                # Split at middle space
                if len(title) > 24:
                    mid   = len(title) // 2
                    split = title.rfind(" ", 0, mid + 8)
                    t1    = title[:split].strip() if split > 0 else title[:24]
                    t2    = title[split:].strip() if split > 0 else title[24:]
                    if len(t2) > 26:
                        t2 = t2[:26] + "…"
                else:
                    t1 = title
                    t2 = None

            draw.text((TXT_X, TITLE_Y), t1,
                      fill=C_TITLE, font=self.font_title)
            if t2:
                t1_w = int(draw.textlength(t1, font=self.font_title))
                draw.text(
                    (TXT_X + t1_w + 22, TITLE_Y),
                    t2,
                    fill=C_TITLE,
                    font=self.font_title
                )

            # 6. Views line — "YouTube  |  XXX views"
            views = str(getattr(song, "views", "") or "").strip()
            if views and views.lower() not in ("none", "0", ""):
                views_line = f"YouTube  |  {views} views"
            else:
                views_line = "YouTube"
            draw.text((TXT_X, VIEWS_Y), views_line,
                      fill=C_SUBTEXT, font=self.font_views)

            # 7. Progress bar track (grey)
            draw.rounded_rectangle(
                (BAR_X, BAR_Y, BAR_X + BAR_W, BAR_Y + BAR_H),
                radius=4,
                fill=C_BAR_TRACK
            )

            # 8. Red filled portion (static 42% — dynamic hoga bot mein)
            bar_progress = int(BAR_W * 0.42)
            draw.rounded_rectangle(
                (BAR_X, BAR_Y, BAR_X + bar_progress, BAR_Y + BAR_H),
                radius=4,
                fill=C_RED
            )

            # 9. Red knob on progress
            kx = BAR_X + bar_progress
            ky = BAR_Y + BAR_H // 2
            draw.ellipse(
                (kx - 10, ky - 10, kx + 10, ky + 10),
                fill=C_RED
            )

            # 10. Time labels
            draw.text((BAR_X, TIME_Y), "00:00",
                      fill=C_SUBTEXT, font=self.font_time)
            dur = str(getattr(song, "duration", "0:00") or "0:00").strip()
            dur_w = int(draw.textlength(dur, font=self.font_time))
            draw.text(
                (BAR_X + BAR_W - dur_w, TIME_Y),
                dur,
                fill=C_SUBTEXT,
                font=self.font_time
            )

            # 11. Player control icons
            icons   = ["⇄", "⏮", "▶", "⏭", "↺"]
            i_space = 100
            i_start = CARD_X + (CARD_W // 2) - (i_space * 2)
            for idx, icon in enumerate(icons):
                ix = i_start + idx * i_space
                # Center icon horizontally
                iw = int(draw.textlength(icon, font=self.font_ctrl))
                draw.text(
                    (ix - iw // 2, CTRL_Y),
                    icon,
                    fill=C_CTRL,
                    font=self.font_ctrl
                )

            # 12. Bot watermark bottom-right of card
            mark = "AdamMusicBot"
            mark_w = int(draw.textlength(mark, font=self.font_mark))
            draw.text(
                (CARD_X + CARD_W - mark_w - 22, MARK_Y),
                mark,
                fill=C_MARK,
                font=self.font_mark
            )

            # Save
            bg.convert("RGB").save(output, "PNG", optimize=True)
            try:
                os.remove(temp)
            except OSError:
                pass

            return output

        except Exception as e:
            print(f"[Thumbnail] _draw() error: {e}")
            return config.DEFAULT_THUMB
