"""Journal screen, HUD extras, transitions and other screen-space UI.

Owner: UI & Rendering (Chat 6). See docs/ARCHITECTURE.md (ownership map) and
src/systems/hooks.py (the hook API this mixin plugs into: define methods named
``_on_reset_*``, ``_on_update_*``, ``_interact_late_*``, ``_on_save_*`` ... and they
are called automatically -- no edits to game.py / save_system / actions_system).
Rules: no ``__init__``; initialise state in an ``_on_reset_*`` hook.

PUBLIC API used by every domain (keep the signature stable):
    self.toast(title, subtitle="", icon=None, color=None, seconds=3.5)
        big notification card (achievements, records, unlocks...). ``icon`` may be
        an item id (drawn with assets.item_icon) or a pygame Surface.

Features here:
  * toasts        -- slide-in cards (right edge) with a glowing icon + timer bar
  * journal       -- state "journal" (key settings.JOURNAL_KEY): a book with one
                     tab per ``_journal_tab_*`` hook + the built-in "Guide" tab
  * area cards    -- "~ Farm ~" title card + subtitle after every warp
  * select tags   -- item name pill above a player's head when their hotbar
                     selection changes
"""
import math
import os
import pygame
from ..settings import (SCREEN_W, SCREEN_H, WHITE, GOLD, UI_BG, UI_BORDER, TILE,
                        JOURNAL_KEY, P1_KEYS, P2_KEYS, KEY_ACTIONS)
from ..ui import key_label

try:                                   # single-purpose hotkeys (settings = source of truth)
    from ..settings import BUILD_KEY
except Exception:                      # pragma: no cover
    BUILD_KEY = pygame.K_b

# flavour subtitle per area id (title itself derives from the id). Unknown /
# future areas fall back to a generic line, so new areas work with no edits.
AREA_SUBTITLES = {
    "farm": "Our little patch of earth",
    "town": "Market square & friendly faces",
    "forest": "Whispering pines and hidden paths",
    "beach": "Salt breeze & seashells",
    "temple": "A quiet place to breathe",
    "coop": "Clucks, moos & fresh hay",
    "home": "Home, sweet home",
    "mine": "Deeper, darker, shinier",
    "meadow": "Wildflowers as far as the eye can see",
    "mistcity": "Stay close. Mind the fog.",
}
_GENERIC_SUB = "A new place to explore together"

_CARD_SECS = 2.2
_TOAST_IN = 0.35
_TOAST_OUT = 0.4
_TOAST_TITLE_MAX = 330      # px: title column cap (card is right-anchored)
_TOAST_W = 420              # every toast card has the same width (tidy right edge)
_TOAST_Y0 = 120             # first card: 8 px below the clock card
# toasts are shown (and their timers run) only while the world is on screen;
# while a panel / cut-scene is open they wait, then slide in when it closes
_TOAST_LIVE_STATES = ("play", "casting", "reeling", "decor")


def _strict():
    return os.environ.get("HD_STRICT_HOOKS") == "1"


def _ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


class UIMixin:
    """Journal screen, HUD extras, transitions and other screen-space UI."""

    # ================================================================ fonts
    def _ui_font(self, size, bold=True):
        cache = self.__dict__.setdefault("_ui_fonts", {})
        f = cache.get((size, bold))
        if f is None:
            f = cache[(size, bold)] = pygame.font.SysFont("consolas", size, bold=bold)
        return f

    # ================================================================ toasts
    def _on_reset_ui_toasts(self):
        self.toasts = []            # [title, subtitle, icon, color, ttl, total, card]

    def toast(self, title, subtitle="", icon=None, color=None, seconds=3.5):
        if not hasattr(self, "toasts"):
            self.toasts = []
        self.toasts.append([str(title), str(subtitle or ""), icon,
                            tuple(color or (255, 222, 140))[:3], float(seconds),
                            float(seconds), None])
        self.toasts = self.toasts[-4:]

    def _on_update_ui_toasts(self, dt):
        if getattr(self, "state", "play") not in _TOAST_LIVE_STATES:
            return                          # paused behind a panel (see above)
        for t in self.toasts:
            t[4] -= dt
        self.toasts = [t for t in self.toasts if t[4] > 0]

    def _toast_card(self, t):
        """Render (once) the static part of a toast card."""
        from .. import assets
        title, sub, icon, col = t[0], t[1], t[2], t[3]
        maxt = 330                                  # subtitle column width cap
        # title: never hard-clipped mid-word -- full size when it fits the
        # (right-anchored) card, else a slightly smaller font, else two
        # word-wrapped lines; '...' only for a single over-long word
        tlines = self._toast_title_lines(title, _TOAST_TITLE_MAX)
        tsurfs = [f.render(ln, True, col) for f, ln in tlines]
        th = sum(s.get_height() for s in tsurfs) - 2 * (len(tsurfs) - 1)
        ts = tsurfs[0]
        # subtitle word-wrapped to at most two lines
        lines = []
        if sub:
            cur = ""
            for wd in sub.split():
                cand = (cur + " " + wd).strip()
                if self.ui.small.size(cand)[0] <= maxt:
                    cur = cand
                else:
                    if cur:
                        lines.append(cur)
                    cur = wd
            if cur:
                lines.append(cur)
            if len(lines) > 2:
                lines = lines[:2]
                while self.ui.small.size(lines[1] + "...")[0] > maxt and len(lines[1]) > 1:
                    lines[1] = lines[1][:-1]
                lines[1] += "..."
        subs = [self.ui.small.render(ln, True, (232, 228, 240)) for ln in lines]
        ss = subs[0] if subs else None
        w = max(_TOAST_W, max([x.get_width() for x in tsurfs + subs]) + 86)
        sub_y = max(33, 9 + th + 3)                 # 33 = the classic one-line layout
        h = max(48, th + 22) if not subs else sub_y + 16 * len(subs) + 13
        card = pygame.Surface((w, h), pygame.SRCALPHA)
        # body: dark plum with a soft top sheen + coloured left rail
        pygame.draw.rect(card, (34, 28, 46, 236), card.get_rect(), border_radius=12)
        # top sheen on its own layer, blended in (drawing it straight onto the
        # SRCALPHA card replaced the body alpha and made the top see-through)
        sheen = pygame.Surface((w - 8, max(8, min(h // 2 - 2, th + 4))), pygame.SRCALPHA)
        pygame.draw.rect(sheen, (255, 255, 255, 18), sheen.get_rect(), border_radius=10)
        card.blit(sheen, (4, 3))
        pygame.draw.rect(card, (*col, 255), card.get_rect(), 2, border_radius=12)
        pygame.draw.rect(card, (*col, 255), (0, 8, 5, h - 16), border_radius=3)
        # icon inside a glowing medallion
        cy = h // 2
        card.blit(assets.hud.glow(26, col, 120), (36 - 26, cy - 26))
        pygame.draw.circle(card, (24, 20, 32), (36, cy), 17)
        pygame.draw.circle(card, col, (36, cy), 17, 2)
        ic = None
        if isinstance(icon, pygame.Surface):
            ic = icon
        elif isinstance(icon, str) and icon:
            try:
                ic = assets.item_icon(icon)
            except Exception:
                ic = None
        if ic is not None:
            try:
                ic = pygame.transform.smoothscale(ic, (26, 26))
            except Exception:
                ic = pygame.transform.scale(ic, (26, 26))
            card.blit(ic, (36 - 13, cy - 13))
        else:                                        # default: a little star
            pts = []
            for k in range(10):
                a = -math.pi / 2 + k * math.pi / 5
                r = 9 if k % 2 == 0 else 4
                pts.append((36 + math.cos(a) * r, cy + math.sin(a) * r))
            pygame.draw.polygon(card, col, pts)
        ty = 9 if ss else (h - th) // 2
        for s in tsurfs:
            card.blit(s, (62, ty))
            ty += s.get_height() - 2
        for i, line in enumerate(subs):
            card.blit(line, (62, sub_y + i * 16))
        return card

    def _toast_title_lines(self, title, maxw):
        """[(font, text), ...] -- one or two lines that fit ``maxw`` pixels."""
        big, mid = self._ui_font(18), self._ui_font(16)
        if big.size(title)[0] <= maxw:
            return [(big, title)]
        if mid.size(title)[0] <= maxw:
            return [(mid, title)]
        words, lines, cur = title.split(), [], ""
        for wd in words:
            cand = (cur + " " + wd).strip()
            if mid.size(cand)[0] <= maxw or not cur:
                cur = cand
            else:
                lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
        if len(lines) > 2:
            lines = [lines[0], " ".join(lines[1:])]
        out = []
        for ln in lines[:2]:
            if mid.size(ln)[0] > maxw:              # last resort: ellipsis
                while ln and mid.size(ln + "...")[0] > maxw:
                    ln = ln[:-1]
                ln = ln.rstrip() + "..."
            out.append((mid, ln))
        return out or [(big, "")]

    # (kept for compatibility: toasts are no longer painted over modal menus --
    # they wait until the panel closes, so they never cover its contents)
    _TOAST_OVER_STATES = ()

    def _draw_hud_ui_toasts(self):
        if getattr(self, "state", None) not in _TOAST_LIVE_STATES:
            return
        self._ui_draw_toasts()

    def _ui_draw_toasts(self):
        y = _TOAST_Y0
        prev_bottom = -999
        reserved = self.hud_reserved()
        self._toast_rects_last = []
        for t in self.toasts[:3]:
            while len(t) < 8:
                t.append(None)
            if t[6] is None:
                t[6] = self._toast_card(t)
            card = t[6]
            ttl, total = t[4], t[5]
            age = total - ttl
            w, h = card.get_size()
            # slide in from the right; leave by fading out with a short drift
            # (sliding off the edge showed half-cut text for a moment)
            slide = 1.0 - _ease_out(age / _TOAST_IN)
            out = 1.0 - ttl / _TOAST_OUT if ttl < _TOAST_OUT else 0.0
            x = SCREEN_W - w - 12 + int(slide * (w + 24))      # leaves by fading in place
            a = int(255 * max(0.0, min(1.0, (1.0 - slide) * (1.0 - out))))
            # cards below one that leaves glide up instead of jumping
            ty = t[7] if t[7] is not None else y
            ty += (y - ty) * 0.25
            if abs(ty - y) < 0.5:
                ty = y
            # never over the card above it (while the stack re-shuffles), nor
            # over a reserved HUD element (e.g. the boss plate): step below it
            ty = max(ty, prev_bottom + 8)
            slot = pygame.Rect(SCREEN_W - w - 12, int(ty), w, h)
            for _ in range(4):
                hit = next((r for r in reserved if slot.colliderect(r)), None)
                if hit is None:
                    break
                slot.top = hit.bottom + 8
            ty = max(ty, slot.top)
            t[7] = ty
            ty = int(ty)
            prev_bottom = ty + h
            card.set_alpha(a)
            self.screen.blit(card, (x, ty))
            self._toast_rects_last.append(pygame.Rect(SCREEN_W - w - 12, ty, w, h))
            # remaining-time bar under the text
            frac = max(0.0, min(1.0, ttl / max(0.01, total)))
            bw = int((w - 76) * frac)
            if bw > 0 and a > 200:
                pygame.draw.rect(self.screen, t[3], (x + 62, ty + h - 7, bw, 2))
            # sparkle while it lands
            if age < 0.6:
                s = int(6 + 10 * age)
                cx, cy = x + 36, ty + h // 2
                col = (255, 250, 230)
                pygame.draw.line(self.screen, col, (cx - s, cy - s - 4), (cx - s, cy - s + 2), 1)
                pygame.draw.line(self.screen, col, (cx - s - 3, cy - s - 1), (cx - s + 3, cy - s - 1), 1)
            y = max(y + h + 8, prev_bottom + 8)

    # ================================================================ area card + select tags
    def _on_reset_ui_card(self):
        self._area_card = None          # [title, subtitle, age]
        self._sel_tags = {}             # player idx -> [label, entry, age]
        self._sel_prev = {}             # player idx -> last selected entry
        self._card_welcome = True       # greet with a title card on the first play frame

    def _on_event_ui_card(self, event, data):
        if event != "warp":
            return
        area = str(data.get("area") or getattr(self.world, "current", "") or "")
        if not area:
            return
        title = area.replace("_", " ").title()
        sub = AREA_SUBTITLES.get(area, _GENERIC_SUB)
        if area == "mine":
            biome = getattr(getattr(self.world, "area", None), "biome", None)
            lvl = getattr(self.world, "mine_level", None)
            bits = []
            if lvl is not None:
                bits.append(f"Level {lvl}")
            if biome:
                bits.append(str(biome).replace("_", " ").title())
            if bits:
                sub = "  -  ".join(bits)
        self._area_card = [title, sub, 0.0]

    def _on_update_ui_card(self, dt):
        if getattr(self, "_card_welcome", False):
            self._card_welcome = False
            if not getattr(self, "_area_card", None):
                area = str(getattr(self.world, "current", "") or "")
                tm = self.time
                if area:
                    self._area_card = [area.replace("_", " ").title(),
                                       f"{tm.season} {tm.day}  -  Year {tm.year}", 0.0]
        c = getattr(self, "_area_card", None)
        if c:
            # held while the warp iris is still opening, so the card lands on
            # the new map instead of over the black transition
            if getattr(self, "fade", 0.0) <= 0.3:
                c[2] += dt
            if c[2] >= _CARD_SECS:
                self._area_card = None
        # hotbar selection change -> item-name tag above that player's head
        tags = self._sel_tags
        for idx, p in enumerate(self.players):
            inv = getattr(p, "inv", None)
            if inv is None:
                continue
            try:
                entry = inv.selected_entry()
            except Exception:
                entry = None
            key = tuple(entry) if entry else None
            prev = self._sel_prev.get(idx, key)
            self._sel_prev[idx] = key
            if key != prev and entry:
                try:
                    from ..inventory import Inventory
                    label = Inventory.label(entry)
                except Exception:
                    label = str(entry[-1]).replace("_", " ").title()
                tags[idx] = [label, entry, 0.0]
        for idx in list(tags):
            tags[idx][2] += dt
            if tags[idx][2] > 1.6:
                del tags[idx]

    def _draw_hud_ui_seltags(self):
        """Drawn in the HUD pass (after night lighting, so it stays readable);
        skipped in the iso home where world x/y are not screen-projected."""
        from .. import assets
        tags = getattr(self, "_sel_tags", None)
        if not tags or self.state != "play" or self.world.current == "home":
            return
        cam = self.cam
        placed = []                                     # [surf, x, y, alpha]
        for idx, (label, entry, age) in tags.items():
            if idx >= len(self.players):
                continue
            p = self.players[idx]
            a = min(1.0, age / 0.12, (1.6 - age) / 0.4)
            if a <= 0:
                continue
            key = ("seltag", label, idx)
            cache = self.__dict__.setdefault("_seltag_cache", {})
            surf = cache.get(key)
            if surf is None:
                txt = self.ui.small.render(label, True, (255, 250, 236))
                w, h = txt.get_width() + 34, 24
                surf = pygame.Surface((w, h), pygame.SRCALPHA)
                col = (235, 110, 100) if idx == 0 else (100, 150, 235)
                pygame.draw.rect(surf, (30, 24, 38, 225), (0, 0, w, h), border_radius=8)
                pygame.draw.rect(surf, col, (0, 0, w, h), 2, border_radius=8)
                try:
                    ic = pygame.transform.smoothscale(assets.hotbar_icon(entry), (18, 18))
                    surf.blit(ic, (5, 3))
                except Exception:
                    pass
                surf.blit(txt, (27, (h - txt.get_height()) // 2))
                if len(cache) > 64:
                    cache.clear()
                cache[key] = surf
            rise = int(6 * _ease_out(age / 0.25))
            sx = int(p.x - cam.x - surf.get_width() / 2)
            sy = int(p.y - cam.y - TILE * 1.45 - rise)
            placed.append([surf, sx, sy, a, int(p.y - cam.y) + 20])   # + feet y
        # two farmers side by side: push overlapping tags apart horizontally
        if len(placed) == 2:
            (s0, x0, y0, *_), (s1, x1, y1, *_) = placed
            r0 = pygame.Rect(x0, y0, *s0.get_size())
            r1 = pygame.Rect(x1, y1, *s1.get_size())
            if r0.colliderect(r1):
                if r0.centerx <= r1.centerx:
                    left, right = placed[0], placed[1]
                else:
                    left, right = placed[1], placed[0]
                ov = (left[1] + left[0].get_width()) - right[1] + 4
                left[1] -= ov // 2 + ov % 2
                right[1] += ov // 2
        # keep tags off the bottom player panels + their fortune/buff row
        panel_top = SCREEN_H - 128
        panels = (pygame.Rect(8, panel_top, 256, 128),
                  pygame.Rect(SCREEN_W - 264, panel_top, 256, 128))
        self._seltag_last = []                         # screen rects (read by test_ui)
        for tag in placed:
            surf, sx, sy, a, feet = tag
            w, h = surf.get_size()
            sx = max(4, min(SCREEN_W - w - 4, sx))
            if any(pygame.Rect(sx, sy, w, h).colliderect(r) for r in panels):
                sy = panel_top - h - 4
            # a floating text drawn this frame ("Loved by you both!") keeps its
            # spot; the tag steps up above it rather than printing over it
            # (and above reserved world prompts such as an animal's heart row)
            pops = list(getattr(self, "_popup_rects_last", None) or []) + [
                r for r in self.hud_reserved() if r.bottom > 120]
            for _ in range(6):
                hit = next((q for q in pops if pygame.Rect(sx, sy, w, h).colliderect(q)), None)
                if hit is None:
                    break
                sy = hit.top - h - 2
            # never over the top HUD cards (minimap, hotbars, clock). With no
            # free spot the tag is skipped: the item name is on the player
            # panel anyway, and a tag on the hotbar is worse than none
            hud_top = (pygame.Rect(0, 0, 232, 204), pygame.Rect(404, 0, 472, 106),
                       pygame.Rect(SCREEN_W - 298, 0, 298, 118))
            if sy < 0 or any(pygame.Rect(sx, sy, w, h).colliderect(r) for r in hud_top):
                sy = feet                              # under the farmer instead
                if any(pygame.Rect(sx, sy, w, h).colliderect(r) for r in hud_top + panels):
                    continue
            self._seltag_last.append(pygame.Rect(sx, sy, w, h))
            surf.set_alpha(int(255 * a))
            self.screen.blit(surf, (sx, sy))

    def _area_card_surf(self, title, sub):
        """The title screen's parchment ribbon ("~ Farm ~") with the subtitle
        on a cream strip under it -- solid, so it reads on snow, sand or
        water alike (cached per title/subtitle)."""
        from .. import ui_kit as K
        cache = self.__dict__.setdefault("_card_cache", {})
        surf = cache.get((title, sub))
        if surf is not None:
            return surf
        big = self._ui_font(34)
        tt = f"~ {title} ~"
        sf = self._ui_font(16)
        tw, th = big.size(tt)
        sw = sf.size(sub)[0] if sub else 0
        rib_w, rib_h = tw + 72, th + 14
        w = max(rib_w + 48, sw + 60)                 # + room for the ribbon tails
        strip_h = sf.get_height() + 12 if sub else 0
        h = rib_h + 10 + (strip_h - 4 if sub else 0) + 4
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        if sub:                                      # subtitle strip, tucked under the ribbon
            strip = pygame.Rect(0, 0, sw + 40, strip_h)
            strip.midtop = (w // 2, rib_h - 2)
            shadow = strip.move(0, 3)
            pygame.draw.rect(surf, (40, 20, 30, 70), shadow, border_radius=10)
            pygame.draw.rect(surf, K.CREAM, strip, border_radius=10)
            pygame.draw.rect(surf, K.RIBBON_LINE, strip, 2, border_radius=10)
            K.blit_text(surf, sf, sub, K.INK_SOFT, (strip.centerx, strip.centery + 2))
        sh = pygame.Rect(0, 0, rib_w, rib_h)
        sh.center = (w // 2, rib_h // 2 + 4)
        pygame.draw.rect(surf, (40, 20, 30, 70), sh, border_radius=8)
        K.ribbon(surf, big, tt, (w // 2, rib_h // 2 + 1))
        if len(cache) > 24:
            cache.clear()
        cache[(title, sub)] = surf
        return surf

    def area_card_rect(self):
        """Screen rect the area title card will occupy this frame (or None).
        Floating texts (drawn before the HUD pass) use it to keep clear."""
        lay = self._area_card_layout()
        return lay[1] if lay else None

    def _area_card_layout(self):
        c = getattr(self, "_area_card", None)
        if not c or self.state != "play" or getattr(self, "fade", 0.0) > 0.3:
            return None
        title, sub, age = c
        a = min(1.0, age / 0.35, (_CARD_SECS - age) / 0.7)
        if a <= 0:
            return None
        surf = self._area_card_surf(title, sub)
        w, h = surf.get_size()
        cx = SCREEN_W // 2 - w // 2
        cy = 190 if self.world.current == "home" else 150      # below the home build banner
        # never cover a farmer who just arrived (Town / Forest spawn at the top
        # edge) nor a HUD bar another domain reserved (egg hunt, boss bar...):
        # step lower on screen until the spot is free
        blockers = self._ui_player_rects() + self.hud_reserved()
        for cand in (cy, 250, 330, 420):
            if not any(pygame.Rect(cx, cand - 14, w, h + 18).colliderect(r) for r in blockers):
                cy = cand
                break
        else:
            a *= 110 / 255
        return surf, pygame.Rect(cx, cy, w, h), a, age

    def _draw_hud_ui_card(self):
        lay = self._area_card_layout()
        self._area_card_rect = lay[1] if lay else None
        if not lay:
            return
        surf, rect, a, age = lay
        drop = int((1 - _ease_out(age / 0.45)) * -18)
        surf.set_alpha(int(255 * a))
        self.screen.blit(surf, (rect.x, rect.y + drop))

    # ================================================================ HUD reservations
    def hud_reserve(self, rect):
        """PUBLIC: a domain drawing a fixed screen-space HUD element (egg-hunt
        bar, boss bar, event banner...) calls this every frame it draws it; the
        area title card, toasts and floating texts then keep clear of it."""
        self.__dict__.setdefault("_hud_res_cur", []).append(pygame.Rect(rect))

    def hud_reserved(self):
        """Rects reserved last frame + so far this frame (see hud_reserve)."""
        return (list(self.__dict__.get("_hud_res", ())) +
                list(self.__dict__.get("_hud_res_cur", ())))

    def _ui_player_rects(self):
        """Screen rects of the farmers (none in the iso home)."""
        if self.world.current == "home":
            return []
        cam = self.cam
        return [pygame.Rect(int(p.x - cam.x) - 22, int(p.y - cam.y) - 40, 44, 56)
                for p in self.players]

    # ================================================================ journal
    def _on_reset_ui_journal(self):
        self._jr_tabs = None            # gathered on open: [{"title","draw","key"?}]
        self._jr_idx = 0
        self._jr_last_title = "Guide"
        self._jr_flip = 0.0             # page-flip animation 1 -> 0
        self._jr_dir = 1
        self._jr_rects = []
        self._jr_t = 0.0

    def _on_keydown_ui_journal(self, key):
        # never swallow a key a player bound to a real action (e.g. WASD + J for
        # Use, or Emote on J): the binding wins, as in the coop emote hook
        for K in (P1_KEYS, P2_KEYS):
            if any(c == key for c in K.values()):
                return False
        if key == JOURNAL_KEY:
            self.journal_open()
            return True
        return False

    def journal_open(self, title=None):
        """Open the journal (optionally on a tab by title)."""
        self._jr_tabs = self._journal_gather()
        want = title or getattr(self, "_jr_last_title", "Guide")
        self._jr_idx = 0
        for i, t in enumerate(self._jr_tabs):
            if t["title"] == want:
                self._jr_idx = i
                break
        self._jr_flip = 1.0
        self._jr_dir = 1
        self.state = "journal"
        self.audio.play("page")

    def _journal_close(self):
        self.state = "play"
        self._jr_tabs = None
        self.audio.play("page")

    def _journal_gather(self):
        tabs = [{"title": "Guide", "draw": self._journal_draw_guide}]
        for n in self._hook_names("_journal_tab_"):
            d = self._call_hook(n)
            if isinstance(d, dict) and callable(d.get("draw")):
                d = dict(d)
                d["title"] = str(d.get("title") or n.split("_")[-1].title())
                d["_hook"] = n
                tabs.append(d)
        return tabs

    def _journal_tabs(self):
        if not getattr(self, "_jr_tabs", None):
            self._jr_tabs = self._journal_gather()
        return self._jr_tabs

    def _journal_switch(self, step):
        tabs = self._journal_tabs()
        if len(tabs) < 2:
            return
        self._jr_idx = (self._jr_idx + step) % len(tabs)
        self._jr_last_title = tabs[self._jr_idx]["title"]
        self._jr_flip = 1.0
        self._jr_dir = 1 if step > 0 else -1
        self.audio.play("page")

    def _journal_forward_key(self, key):
        tabs = self._journal_tabs()
        tab = tabs[self._jr_idx % len(tabs)]
        fn = tab.get("key")
        if not callable(fn):
            return False
        try:
            return bool(fn(key))
        except Exception:
            if _strict():
                raise
        return False

    def _state_event_journal(self, e):
        tabs = self._journal_tabs()
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k in (pygame.K_ESCAPE, JOURNAL_KEY):
                self._journal_close()
                return
            prev_keys = {pygame.K_q, pygame.K_COMMA, pygame.K_LEFT,
                         P1_KEYS.get("prev"), P2_KEYS.get("prev")}
            next_keys = {pygame.K_e, pygame.K_PERIOD, pygame.K_RIGHT,
                         P1_KEYS.get("next"), P2_KEYS.get("next")}
            # a tab that browses sideways (Achievements grid, Friends) gets the
            # players' left/right MOVE keys first -- P2 moves with the arrows, so
            # the arrows only turn the page when the tab doesn't use them
            side_keys = {pygame.K_LEFT, pygame.K_RIGHT, P1_KEYS.get("left"),
                         P1_KEYS.get("right"), P2_KEYS.get("left"), P2_KEYS.get("right")}
            forwarded = False
            if k in side_keys and k not in (P1_KEYS.get("prev"), P1_KEYS.get("next"),
                                            P2_KEYS.get("prev"), P2_KEYS.get("next")):
                forwarded = True
                if self._journal_forward_key(k):
                    return
            if k in prev_keys:
                self._journal_switch(-1)
            elif k in next_keys:
                self._journal_switch(1)
            elif pygame.K_1 <= k <= pygame.K_9 and (k - pygame.K_1) < len(tabs):
                step = (k - pygame.K_1) - self._jr_idx
                if step:
                    self._journal_switch(step)
            elif not forwarded:
                self._journal_forward_key(k)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for rect, i in self._jr_rects:
                if rect.collidepoint(e.pos) and i != self._jr_idx:
                    self._journal_switch(i - self._jr_idx)
                    return
        elif e.type == pygame.MOUSEWHEEL:
            self._journal_forward_key(pygame.K_UP if e.y > 0 else pygame.K_DOWN)

    def _state_update_journal(self, dt):
        self._jr_t += dt
        if self._jr_flip > 0:
            self._jr_flip = max(0.0, self._jr_flip - dt * 4.5)

    # ---- journal drawing ----
    def _journal_frame(self):
        """The book: cached cover + page background (drawn once)."""
        cache = self.__dict__.setdefault("_jr_cache", {})
        s = cache.get("frame")
        if s is not None:
            return s
        W, H = 1160, 664
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        # leather cover with stitched border
        pygame.draw.rect(s, (60, 36, 30), (0, 8, W, H - 8), border_radius=22)
        pygame.draw.rect(s, (112, 66, 48), (0, 0, W, H - 10), border_radius=22)
        pygame.draw.rect(s, (136, 84, 60), (6, 4, W - 12, 24), border_radius=16)
        for x in range(26, W - 26, 14):                               # stitching
            pygame.draw.line(s, (206, 164, 112), (x, 8), (x + 7, 8), 2)
        for y in range(26, H - 40, 14):
            pygame.draw.line(s, (206, 164, 112), (12, y), (12, y + 7), 2)
            pygame.draw.line(s, (206, 164, 112), (W - 13, y), (W - 13, y + 7), 2)
        # gold corner guards
        for cx, cy in ((22, 20), (W - 22, 20), (22, H - 32), (W - 22, H - 32)):
            pygame.draw.circle(s, (230, 190, 100), (cx, cy), 8)
            pygame.draw.circle(s, (160, 118, 52), (cx, cy), 8, 2)
        # page block: one cream parchment page (per the journal-tab contract:
        # tabs draw ui_kit INK text on it) + a paper edge under it. No centre
        # gutter -- tabs lay out across the full width.
        from .. import ui_kit as K
        px, py, pw, ph = 26, 84, W - 52, H - 130
        pygame.draw.rect(s, (206, 186, 150), (px - 4, py - 4, pw + 8, ph + 10), border_radius=12)
        pygame.draw.rect(s, (186, 160, 124), (px - 4, py + ph - 2, pw + 8, 8), border_radius=6)
        pygame.draw.rect(s, K.CREAM, (px, py, pw, ph), border_radius=10)
        pygame.draw.rect(s, K.CREAM_HI, (px + 10, py + 5, pw - 20, 4), border_radius=2)
        pygame.draw.rect(s, K.WELL_LINE, (px, py, pw, ph), 2, border_radius=10)
        cache["frame"] = s
        cache["page"] = pygame.Rect(px, py, pw, ph)
        return s

    def _state_draw_journal(self):
        from .. import ui_kit as K
        scr = self.screen
        tabs = self._journal_tabs()
        self._jr_idx %= max(1, len(tabs))
        cache = self.__dict__.setdefault("_jr_cache", {})
        dim = cache.get("dim")
        if dim is None:
            dim = cache["dim"] = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            dim.fill((12, 8, 18, 170))
        scr.blit(dim, (0, 0))
        frame = self._journal_frame()
        bx = SCREEN_W // 2 - frame.get_width() // 2
        by = 26
        scr.blit(frame, (bx, by))
        page = cache["page"].move(bx, by)
        # title on the cover
        # title on the menus' parchment ribbon, centred on the cover's top
        # edge; the two farmers' names on the cover's right
        K.ribbon(scr, self._ui_font(24), "Journal", (SCREEN_W // 2, by + 6))
        names = " & ".join(getattr(p, "name", f"P{i + 1}") for i, p in enumerate(self.players))
        K.blit_text(scr, self.ui.small, names, (236, 206, 160),
                    (bx + frame.get_width() - 44, by + 27), align="right")
        # ---- ribbon tabs across the top of the page ----
        self._jr_rects = []
        n = len(tabs)
        strip_x = bx + 34
        strip_w = frame.get_width() - 68
        tw = max(60, min(170, strip_w // max(1, n)))
        for i, t in enumerate(tabs):
            active = (i == self._jr_idx)
            x = strip_x + i * tw
            if x + tw > bx + frame.get_width() - 30:
                break
            h = 38 if active else 30
            y = page.y - h + 4
            # parchment tabs: the active one is the page's own cream and merges
            # into it; the others are a darker paper behind
            col = K.CREAM if active else (214, 190, 152)
            pygame.draw.rect(scr, col, (x + 2, y, tw - 4, h + 6), border_radius=8)
            pygame.draw.rect(scr, K.WOOD_DK if active else K.WOOD, (x + 2, y, tw - 4, h + 6),
                             2, border_radius=8)
            if active:                                 # open into the page
                pygame.draw.rect(scr, K.CREAM, (x + 4, page.y - 2, tw - 8, 6))
            lab = t["title"]
            f = K.fit_font(lab, tw - 16, (16, 15, 14, 13, 12), bold=True)
            lab = K.ellipsize(f, lab, tw - 12)
            K.blit_text(scr, f, lab, K.INK if active else K.INK_SOFT,
                        (x + tw // 2, y + (h + 4) // 2))
            self._jr_rects.append((pygame.Rect(x + 2, y, tw - 4, h), i))
        # ---- page content (clipped, slides in on a flip) ----
        tab = tabs[self._jr_idx]
        inner = page.inflate(-40, -36)
        off = int(self._jr_dir * 36 * self._jr_flip ** 2)
        prev_clip = scr.get_clip()
        clip = page.inflate(-6, -6)
        # during a flip the page is laid out normally on its own sheet and the
        # whole sheet slides (drawing the tab at an offset clipped its text)
        dst, rect_in, sheet = scr, inner, None
        if off:
            base = cache.get("page_bg")
            if base is None:                  # the page paper without its border
                lp = cache["page"].inflate(-6, -6)
                base = cache["page_bg"] = frame.subsurface(lp).copy()
            sheet = base.copy()
            dst, rect_in = sheet, inner.move(-clip.x, -clip.y)
        else:
            scr.set_clip(clip)
        try:
            tab["draw"](dst, rect_in)
        except Exception:
            scr.set_clip(prev_clip)
            if _strict():
                raise
            er = self.ui.font.render("tab error", True, (255, 150, 150))
            dst.blit(er, (rect_in.centerx - er.get_width() // 2, rect_in.centery - 10))
        if sheet is not None:
            sheet.set_alpha(int(255 * (1.0 - 0.55 * self._jr_flip)))   # fades in as it lands
            scr.set_clip(clip)
            scr.blit(sheet, (clip.x + off, clip.y))
        scr.set_clip(prev_clip)
        if self._jr_flip > 0:                          # page-flip light sweep
            sweep_x = int(page.x + page.w * (1 - self._jr_flip) if self._jr_dir > 0
                          else page.right - page.w * (1 - self._jr_flip))
            sw = cache.get("sweep")
            if sw is None:
                sw = pygame.Surface((40, page.h), pygame.SRCALPHA)
                for i in range(40):
                    pygame.draw.line(sw, (255, 250, 230, int(50 * (1 - abs(i - 20) / 20))),
                                     (i, 0), (i, page.h))
                cache["sweep"] = sw
            scr.set_clip(page)
            scr.blit(sw, (sweep_x - 20, page.y))
            scr.set_clip(prev_clip)
        # ---- footer ----
        hint = (f"{key_label(P1_KEYS['prev'])}/{key_label(P1_KEYS['next'])}  or  "
                f"{key_label(P2_KEYS['prev'])}/{key_label(P2_KEYS['next'])}  or  arrows: turn page"
                f"      {key_label(JOURNAL_KEY)} / ESC: close")
        foot_y = page.bottom + (by + frame.get_height() - 10 - page.bottom) // 2 + 2
        K.blit_text(scr, self.ui.small, hint, (236, 214, 176), (SCREEN_W // 2, foot_y))
        K.blit_text(scr, self._ui_font(13), f"{self._jr_idx + 1} / {n}", (236, 214, 176),
                    (bx + frame.get_width() - 44, foot_y), align="right")

    # ---- the built-in Guide tab ----
    def _keycap(self, surf, x, y, label, col=None):
        from .. import ui_kit as K
        f = self._ui_font(12)
        w = max(24, f.size(label)[0] + 14)
        pygame.draw.rect(surf, K.WOOD, (x, y + 2, w, 20), border_radius=5)
        pygame.draw.rect(surf, col or K.CREAM_HI, (x, y, w, 19), border_radius=5)
        pygame.draw.rect(surf, K.INK_SOFT, (x, y, w, 19), 1, border_radius=5)
        K.blit_text(surf, f, label, K.INK, (x + w // 2, y + 9))
        return w

    def _journal_draw_guide(self, surf, rect):
        from .. import ui_kit as K
        f, sm = self.ui.font, self.ui.small
        head = self._ui_font(20)
        colw = rect.w // 2 - 20
        # --- left half: controls for both players ---
        x, y = rect.x + 10, rect.y + 6
        surf.blit(head.render("Controls", True, K.INK), (x, y))
        y += 34
        pcol = K.P_COL
        for pi, (lbl, keys) in enumerate((("Player 1", P1_KEYS), ("Player 2", P2_KEYS))):
            cx = x + pi * (colw // 2 + 10)
            surf.blit(f.render(lbl, True, pcol[pi]), (cx, y))
            yy = y + 28
            for act, name in KEY_ACTIONS:
                if act not in keys:
                    continue
                surf.blit(sm.render(name, True, K.INK), (cx, yy + 3))
                self._keycap(surf, cx + 92, yy, key_label(keys[act]))
                yy += 25
        y = y + 28 + 25 * len(KEY_ACTIONS) + 12
        surf.blit(f.render("Everyone", True, K.SPROUT), (x, y))
        y += 28
        shared = [("Inventory", pygame.K_i), ("Journal", JOURNAL_KEY),
                  ("Build / Decor", BUILD_KEY), ("Pause / menu", pygame.K_ESCAPE),
                  ("Fullscreen", pygame.K_F11)]
        for i, (name, code) in enumerate(shared):
            cx = x + (i % 2) * (colw // 2 + 10)
            cy = y + (i // 2) * 25
            surf.blit(sm.render(name, True, K.INK), (cx, cy + 3))
            self._keycap(surf, cx + 132, cy, key_label(code))
        # --- right half: quick tips (a thin rule separates the halves) ---
        mid = rect.x + rect.w // 2 + 8
        pygame.draw.line(surf, K.WELL_LINE, (mid, rect.y + 8), (mid, rect.bottom - 12), 2)
        x2 = mid + 24
        y2 = rect.y + 6
        surf.blit(head.render("Farmer's Tips", True, K.INK), (x2, y2))
        y2 += 36
        tips = [
            "Till soil with the hoe, plant seeds, then water every day.",
            "Sleep in your bed to start a new day (and save the game).",
            "Rain waters crops for you - enjoy a lazy morning!",
            "Stand close together to get In Sync: hearts + a little energy.",
            f"Emote: {key_label(P1_KEYS.get('emote', pygame.K_f))} for P1, "
            f"{key_label(P2_KEYS.get('emote', pygame.K_SLASH))} for P2. Gift your partner: "
            "face them holding an item and press Use.",
            f"{key_label(BUILD_KEY)} on the farm: outdoor decor. {key_label(BUILD_KEY)} "
            "at home: furniture.",
            "Ship crops and goods to earn gold, then upgrade your tools.",
            "Break rocks in the mine for ore; take the ladder deeper.",
            "Talk to villagers every day - gifts make friends faster.",
            "Food gives buffs: watch the little icons above your panel.",
            "New tabs appear in this journal as you play.",
        ]
        maxw = rect.right - x2 - 10
        for tip in tips:
            words, line, lines = tip.split(), "", []
            for w_ in words:
                cand = (line + " " + w_).strip()
                if sm.size(cand)[0] <= maxw - 18:
                    line = cand
                else:
                    lines.append(line)
                    line = w_
            lines.append(line)
            pygame.draw.circle(surf, K.HEART, (x2 + 5, y2 + 8), 4)
            for ln in lines:
                surf.blit(sm.render(ln, True, K.INK), (x2 + 18, y2))
                y2 += 19
            y2 += 8
            if y2 > rect.bottom - 20:
                break
