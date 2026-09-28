"""HUD, hotbars, message log, shop and dialogue overlays."""
import math
import time
import pygame
from .settings import (TILE, SCREEN_W, SCREEN_H, WHITE, GOLD, RED, GREEN, BLUE,
                       UI_BG, UI_BORDER, MAX_ENERGY, MAX_HEALTH, P1_KEYS)
from .inventory import Inventory
from . import assets
from . import ui_kit as _kit
from .world import (TILE_COLORS, WATER, GRASS, GRASS2, PATH, STONE, WALL, FLOOR, DIRT)
from .progress import SKILLS, SKILL_COLOR
from .craft import TIER_COLORS


def key_label(code):
    """Player-facing name of a key code — the ONE place hints get key names
    from, so every label follows P1_KEYS/P2_KEYS after a rebind."""
    try:
        return pygame.key.name(code).upper()
    except Exception:
        return "?"


def keys_hint(*pairs):
    """Compose a rebind-proof hint from (label, keycode) pairs:
    keys_hint(("select", P1_KEYS["action"]), ("close", P1_KEYS["prev"]))
    -> "select SPACE  -  close Q"."""
    return "  -  ".join(f"{label} {key_label(c)}" for label, c in pairs)


def scroll_window(total, visible, selected):
    """Return the ``(start, end)`` index slice (end exclusive) of at most
    ``visible`` entries that always keeps ``selected`` on screen, centring it
    where possible and clamping at the ends. Pure index math, reusable by any
    scrolling list (hotbar, shop, menus, storage)."""
    if visible <= 0 or total <= 0:
        return 0, 0
    if total <= visible:
        return 0, total
    start = selected - visible // 2
    start = max(0, min(start, total - visible))
    return start, start + visible


def _thai_font(size, bold=False):
    """A Thai-capable font for the rare in-game Thai string (the anniversary
    cabana's 'needs two players' hint). The UI default (Consolas) has no Thai
    glyphs, so try the common Thai system fonts and fall back gracefully."""
    for name in ("leelawadeeui", "tahoma", "angsanaupc", "cordiaupc",
                 "thsarabunnew", "notosansthai", "sarabun", "browallia"):
        path = pygame.font.match_font(name, bold=bold)
        if path:
            try:
                return pygame.font.Font(path, size)
            except Exception:
                continue
    return pygame.font.SysFont("tahoma", size, bold=bold)


class UI:
    def __init__(self):
        self.font = pygame.font.SysFont("consolas", 18)
        self.big = pygame.font.SysFont("consolas", 30, bold=True)
        self.small = pygame.font.SysFont("consolas", 14)
        self.tiny = pygame.font.SysFont("consolas", 11, bold=True)
        self.thai = _thai_font(19)    # only used for the cabana hint (Thai glyphs)
        self.messages = []        # (text, ttl)
        self._mm_cache = {}       # area name -> base minimap surface
        self._hud_cache = {}      # cached HUD cards
        self._hud_t = 0.0         # perf_counter of the last clock-card draw
        self._gold_disp = None    # count-up animation of the gold readout
        self._gold_last = None
        self._gold_pop = None     # [amount, age] "+N" pop under the card
        self._hb_sel = {}         # side -> [selected index, change time]

    def log(self, text):
        # the same line again (while it is still in the feed) just refreshes
        # that entry and moves it to the newest slot -- no stacked duplicates.
        # ttl 3.8 = "already slid in", so a repeat doesn't re-animate
        for m in self.messages:
            if m[0] == text:
                self.messages.remove(m)
                self.messages.append([text, max(m[1], 3.8)])
                return
        self.messages.append([text, 4.0])
        self.messages = self.messages[-5:]

    def update(self, dt):
        for m in self.messages:
            m[1] -= dt
        self.messages = [m for m in self.messages if m[1] > 0]

    # ---- shared HUD card look ----
    def _card(self, w, h, accent=None, alpha=240):
        """Cached rounded dark-plum HUD card with a soft top sheen."""
        key = ("card", w, h, accent, alpha)
        c = self._hud_cache.get(key)
        if c is None:
            c = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(c, (0, 0, 0, 70), (2, 3, w - 2, h - 3), border_radius=12)
            pygame.draw.rect(c, (34, 28, 44, alpha), (0, 0, w - 2, h - 3), border_radius=12)
            # soft top sheen: drawn on its own layer and BLENDED in (pygame.draw
            # on an SRCALPHA surface replaces pixels, which made the top band of
            # every card nearly transparent)
            sh_h = max(1, min(34, (h - 3) // 2 - 2))
            sheen = pygame.Surface((max(1, w - 10), sh_h), pygame.SRCALPHA)
            pygame.draw.rect(sheen, (255, 255, 255, 16), sheen.get_rect(), border_radius=10)
            c.blit(sheen, (4, 3))
            pygame.draw.rect(c, (104, 92, 128, 255), (0, 0, w - 2, h - 3), 2, border_radius=12)
            if accent:
                pygame.draw.rect(c, (*accent, 255), (14, 1, w - 30, 3), border_radius=2)
            if len(self._hud_cache) > 96:
                self._hud_cache.clear()
            self._hud_cache[key] = c
        return c

    # ---- top-right clock card ----
    def draw_top(self, surf, time_sys, gold, weather_kind=None, show_weather=True,
                 tomorrow=None, snap=False):
        import time as _time
        now = _time.perf_counter()
        gap = (now - self._hud_t) if self._hud_t else 0.0
        dt = min(0.1, gap)
        self._hud_t = now
        # the count-up is only for gold earned while the card is on screen:
        # after the HUD was hidden (full-screen page / menu) or the card never
        # counted yet, show the real value at once so every readout agrees
        # (``snap``: an overlay such as decor mode shows its own live gold)
        if gap > 0.25 or snap:
            self._gold_disp = float(gold)
        W, H = 292, 104
        x, y = SCREEN_W - W - 8, 8
        season = getattr(time_sys, "season", "Spring")
        tint = assets.hud.SEASON_TINT.get(str(season).lower(), (200, 200, 200))
        surf.blit(self._card(W, H, tint), (x, y))
        # row 1: season icon + date + year pill
        surf.blit(assets.hud.season_icon(season, 22), (x + 12, y + 9))
        day = getattr(time_sys, "day", 1)
        _kit.blit_text(surf, self.font, f"{season} {day}", WHITE, (x + 40, y + 20), align="left")
        ytxt = f"YEAR {getattr(time_sys, 'year', 1)}"
        pw = self.tiny.size(ytxt)[0] + 14
        ypill = pygame.Rect(x + W - pw - 16, y + 11, pw, 17)
        pygame.draw.rect(surf, tint, ypill, border_radius=8)
        _kit.blit_text(surf, self.tiny, ytxt, (40, 30, 24), ypill.center)
        # row 2: day/night dial + big clock
        self._draw_dial(surf, x + 14, y + 38, getattr(time_sys, "minutes", 360))
        surf.blit(self.big.render(time_sys.clock_str(), True, WHITE), (x + 58, y + 34))
        # row 3: weather + gold with count-up
        yy = y + 72
        if show_weather and weather_kind:
            surf.blit(assets.hud.weather_icon(weather_kind, 22), (x + 12, yy - 2))
            lab = str(weather_kind).replace("_", " ").title()
            try:
                from . import weather as _w
                lab = _w.LABEL.get(weather_kind, lab)
            except Exception:
                pass
            lt = self.small.render(lab, True, (206, 222, 244))
            surf.blit(lt, (x + 38, yy + 2))
            wx_end = x + 38 + lt.get_width()
        else:
            wx_end = x + 12
        # count-up: the shown value eases toward the real one
        if self._gold_disp is None:
            self._gold_disp = float(gold)
        if self._gold_last is not None and gold > self._gold_last:
            self._gold_pop = [gold - self._gold_last, 0.0]
        self._gold_last = gold
        diff = gold - self._gold_disp
        if abs(diff) >= 0.5:
            step = diff * min(1.0, dt * 7.0)
            if abs(step) < 1:
                step = 1 if diff > 0 else -1
            if abs(step) >= abs(diff):
                self._gold_disp = float(gold)
            else:
                self._gold_disp += step
        else:
            self._gold_disp = float(gold)
        shown = int(round(self._gold_disp))
        rising = shown < gold
        gt = self.font.render(f"{shown:,}g", True, (255, 244, 180) if rising else GOLD)
        gx = x + W - gt.get_width() - 18
        bounce = 2 if rising and int(now * 20) % 2 == 0 else 0
        surf.blit(assets.hud.coin_icon(18), (gx - 24, yy + 1 - bounce))
        surf.blit(gt, (gx, yy + 1))
        # "+N" pop: sits on the gold row's baseline, just left of the coin
        # (inside the card, never over the toasts below it)
        pop = None
        if self._gold_pop:
            amt, age = self._gold_pop
            age += dt
            self._gold_pop[1] = age
            if age > 1.2:
                self._gold_pop = None
            else:
                a = int(255 * min(1.0, (1.2 - age) / 0.5, age / 0.12 + 0.3))
                pop = self.small.render(f"+{amt:,}", True, (255, 236, 140))
                pop.set_alpha(a)
        pop_x = gx - 32 - (pop.get_width() if pop else 0)
        # tomorrow's forecast: a tiny '>' + icon after today's weather, when it
        # fits -- and it steps aside while a "+N" pop needs the room
        fc_end = wx_end + 34
        if show_weather and tomorrow and fc_end < gx - 30 and (pop is None or fc_end + 6 < pop_x):
            ar = self.tiny.render(">", True, (160, 170, 196))
            surf.blit(ar, (wx_end + 7, yy + 3))
            ti = assets.hud.weather_icon(tomorrow, 16)
            surf.blit(ti, (wx_end + 16, yy + 1))
        if pop is not None:
            base = yy + 1 + self.font.get_ascent()          # the gold digits' baseline
            slide = max(0, 3 - int(self._gold_pop[1] * 30)) if self._gold_pop else 0
            surf.blit(pop, (pop_x, base - self.small.get_ascent() + slide))

    def _draw_dial(self, surf, x, y, minutes):
        """Half-disc sky dial: the sun travels 06:00 -> 18:00, the moon after."""
        base = assets.hud.dial_base(16)
        surf.blit(base, (x, y))
        cx, cy, r = x + 18, y + 18, 12
        m = float(minutes) % 1440
        if 360 <= m < 1080:
            f = (m - 360) / 720.0
            night = False
        else:
            f = ((m - 1080) % 1440) / 720.0
            night = True
        ang = math.pi * (1 - f)
        px = cx + math.cos(ang) * r
        py = cy - math.sin(ang) * r
        if night:
            shade = self._hud_cache.get("dial_night")
            if shade is None:
                shade = pygame.Surface((36, 20), pygame.SRCALPHA)
                pygame.draw.circle(shade, (20, 24, 60, 150), (18, 18), 16,
                                   draw_top_left=True, draw_top_right=True)
                self._hud_cache["dial_night"] = shade
            surf.blit(shade, (x, y))
            surf.blit(assets.hud.moon_icon(9), (int(px) - 4, int(py) - 4))
        else:
            pygame.draw.circle(surf, (255, 214, 96), (int(px), int(py)), 4)
            pygame.draw.circle(surf, (255, 246, 200), (int(px) - 1, int(py) - 1), 1)

    # ---- per player panel ----
    def draw_player_panel(self, surf, player, side):
        w, h = 256, 88
        x = 8 if side == 0 else SCREEN_W - w - 8
        y = SCREEN_H - h - 6
        pcol = (240, 130, 120) if side == 0 else (120, 170, 240)
        surf.blit(self._card(w, h, pcol), (x, y))
        # face medallion
        fx, fy = x + 26, y + 30
        pygame.draw.circle(surf, (24, 20, 32), (fx, fy), 19)
        try:
            frames = getattr(player, "frames", None) or {}
            fr = frames.get("down", [None])[0]
            if fr is not None:
                face = assets.hud.face_icon(fr, 30)
                clip = surf.get_clip()
                surf.set_clip(pygame.Rect(fx - 17, fy - 17, 34, 34))
                surf.blit(face, (fx - face.get_width() // 2, fy - 16))
                surf.set_clip(clip)
        except Exception:
            pass
        pygame.draw.circle(surf, pcol, (fx, fy), 19, 2)
        tagr = pygame.Rect(fx - 11, fy + 13, 22, 13)
        pygame.draw.rect(surf, pcol, tagr, border_radius=6)
        _kit.blit_text(surf, self.tiny, f"P{side + 1}", (30, 22, 20), tagr.center)
        # name + bars with icons
        surf.blit(self.font.render(str(player.name)[:14], True, WHITE), (x + 52, y + 5))
        maxhp = max(1, getattr(player, "max_health", MAX_HEALTH))
        er = player.energy / MAX_ENERGY
        hr = player.health / maxhp
        surf.blit(assets.hud.bolt_icon(14), (x + 52, y + 28))
        self._bar(surf, x + 70, y + 30, 92, 10, er, (122, 212, 110), "")
        surf.blit(assets.hud.heart_icon(14), (x + 52, y + 45))
        self._bar(surf, x + 70, y + 47, 92, 10, hr, (236, 96, 110), "")
        # selected item
        entry = player.inv.selected_entry() if player.inv else None
        if entry:
            label = Inventory.label(entry)
            qty = ""
            if entry[0] == "item":
                qty = f" x{player.inv.count(entry[1])}"
            it = self.small.render(f"{label}{qty}", True, GOLD)
            cut = len(label)
            while it.get_width() > 122 and cut > 3:       # trim by pixels, keep qty
                cut -= 1
                it = self.small.render(f"{label[:cut].rstrip()}...{qty}", True, GOLD)
            surf.blit(it, (x + 52, y + 64))
        # skills / level column (right side, clear of the bars)
        self._draw_skills(surf, x + 176, y + 5, player)

    def draw_buffs(self, surf, player, side, offset=0):
        """Active buffs as little icon chips above the player's panel.
        Reads p.buffs = {kind: [amount, seconds_left, label]}."""
        buffs = getattr(player, "buffs", None)
        if not buffs:
            return
        y = SCREEN_H - 94 - 30
        x = 8 + offset if side == 0 else SCREEN_W - 8 - offset
        for kind, b in sorted(buffs.items()):
            try:
                secs = float(b[1])
            except Exception:
                continue
            txt = f"{int(secs)}s" if secs < 100 else f"{int(secs // 60)}m"
            tw = self.tiny.size(txt)[0]
            # body = card width - 2 (shadow): 5 | icon 18 | 4 | text | 9
            cw = 5 + 18 + 4 + tw + 9 + 2
            cx = x if side == 0 else x - cw
            surf.blit(self._card(cw, 27, None, 210), (cx, y))
            ic = assets.hud.buff_icon(kind, 18)
            if secs < 5 and int(secs * 6) % 2 == 0:          # about to run out: blink
                ic = ic.copy()
                ic.set_alpha(110)
            surf.blit(ic, (cx + 5, y + 3))
            _kit.blit_text(surf, self.tiny, txt, (240, 236, 220), (cx + 27, y + 12), align="left")
            x = x + cw + 6 if side == 0 else x - cw - 6

    def _draw_skills(self, surf, x, y, player):
        sk = getattr(player, "skills", None)
        if not sk:
            return
        surf.blit(self.tiny.render(f"Lv {sk.total_level()}", True, (255, 235, 150)), (x, y))
        for i, s in enumerate(SKILLS):
            ry = y + 14 + i * 13
            pygame.draw.rect(surf, SKILL_COLOR[s], (x, ry, 8, 8), border_radius=2)
            pygame.draw.rect(surf, (20, 22, 26), (x, ry, 8, 8), 1, border_radius=2)
            surf.blit(self.tiny.render(f"{s[:3].upper()} {sk.level(s)}", True, (220, 224, 228)),
                      (x + 11, ry - 2))

    def _bar(self, surf, x, y, w, h, ratio, color, tag):
        ratio = max(0.0, min(1.0, ratio))
        pygame.draw.rect(surf, (18, 14, 24), (x - 1, y - 1, w + 2, h + 2), border_radius=4)
        pygame.draw.rect(surf, (58, 50, 70), (x, y, w, h), border_radius=3)
        fw = int(w * ratio)
        if fw > 0:
            col = color
            if ratio < 0.2 and int(pygame.time.get_ticks() / 250) % 2 == 0:
                col = tuple(min(255, c + 60) for c in color)       # low: gentle blink
            pygame.draw.rect(surf, col, (x, y, fw, h), border_radius=3)
            pygame.draw.rect(surf, tuple(min(255, c + 50) for c in col),
                             (x + 2, y + 1, max(0, fw - 4), 2), border_radius=1)
        if tag:
            surf.blit(self.tiny.render(tag, True, (210, 210, 215)), (x - 22, y - 1))

    # ---- reusable scroll indicators ----
    def draw_scroll_arrows(self, surf, start, end, total, x, y, w, h, vertical=False,
                           color=None):
        """Hint triangles at the ends of a scroll region when entries continue
        off-screen. (x, y, w, h) is the visible region rect. Horizontal by
        default (◀ ▶); set ``vertical`` for ▲ ▼. The triangles sit OUTSIDE the
        region (2-9 px beyond it), so leave that much room around the list.
        ``color``: e.g. ui_kit.WOOD on a parchment panel."""
        col = color or (245, 232, 180)
        before, after = start > 0, end < total
        if vertical:
            mx = x + w // 2
            if before:
                pygame.draw.polygon(surf, col, [(mx, y - 9), (mx - 5, y - 2), (mx + 5, y - 2)])
            if after:
                pygame.draw.polygon(surf, col, [(mx, y + h + 9), (mx - 5, y + h + 2), (mx + 5, y + h + 2)])
        else:
            my = y + h // 2
            if before:
                pygame.draw.polygon(surf, col, [(x - 11, my), (x - 4, my - 6), (x - 4, my + 6)])
            if after:
                pygame.draw.polygon(surf, col, [(x + w + 11, my), (x + w + 4, my - 6), (x + w + 4, my + 6)])

    def draw_scrollbar(self, surf, x, y, h, total, visible, start, track=None, thumb_col=None):
        """Slim vertical scrollbar (track + thumb) for list overlays. No-op when
        everything already fits. ``track`` / ``thumb_col`` recolour it (e.g.
        ui_kit.WELL_LINE / ui_kit.WOOD on parchment)."""
        if total <= visible or total <= 0:
            return
        pygame.draw.rect(surf, track or (60, 60, 68), (x, y, 4, h), border_radius=2)
        thumb = max(14, int(h * visible / total))
        ty = y + int((h - thumb) * start / max(1, total - visible))
        pygame.draw.rect(surf, thumb_col or (205, 205, 214), (x, ty, 4, thumb), border_radius=2)

    # ---- hotbar ----
    def draw_hotbar(self, surf, player, side):
        bar = player.inv.hotbar()
        n = len(bar)
        if n == 0:
            return
        sel = player.inv.selected % n
        cell = 40
        step = cell + 4
        margin = 52                                    # leave room for P-label + arrows
        # the hotbar is locked to at most 10 slots on screen (the player arranges
        # which 10 in the inventory screen; Core caps the usable hotbar to 10)
        HOTBAR_SLOTS = 10
        fit = max(1, (SCREEN_W - margin * 2) // step)
        visible = min(HOTBAR_SLOTS, fit)
        start, end = scroll_window(n, visible, sel)
        shown = bar[start:end]
        total_w = len(shown) * step - 4
        # both rows share ONE left edge (that of a full 10-slot bar), so a
        # shorter P2 bar lines up under P1 instead of being centred on its own
        x0 = SCREEN_W // 2 - (visible * step - 4) // 2
        y = 10 if side == 0 else 56
        lab_w = 30 if n <= visible else 44             # player tag (+ room for the ◀ hint)
        now = time.perf_counter()
        hs = self._hb_sel.get(side)
        if hs is None or hs[0] != sel:
            self._hb_sel[side] = hs = [sel, now if hs is not None else now - 9]
        since = now - hs[1]
        pop = max(0.0, 1.0 - since / 0.25)              # 1 -> 0 right after a change
        pulse = (math.sin(now * 5.0) + 1) * 0.5
        # soft backing strip so the bar reads over any ground; it also carries
        # the player tag (a small player-coloured pill), readable on snow too
        strip = self._card(total_w + 12 + lab_w, cell + 12, None, 150)
        surf.blit(strip, (x0 - 6 - lab_w, y - 5))
        tag = pygame.Rect(x0 - lab_w - 1, y + 4 if n > visible else y + cell // 2 - 8, 26, 16)
        _kit.pill(surf, tag, _kit.P_COL[side % 2], (250, 240, 230), radius=8)
        _kit.blit_text(surf, self.tiny, f"P{side + 1}", (255, 250, 238), tag.center)
        if n > visible:                                # position while scrolling
            _kit.blit_text(surf, self.tiny, f"{sel + 1}/{n}", (226, 222, 232),
                           (tag.centerx, y + 30))
        for j, entry in enumerate(shown):
            idx = start + j
            x = x0 + j * step
            if idx == sel:
                g = int(2 + pop * 4)
                gl = assets.hud.glow(cell // 2 + 10, (255, 214, 110), int(60 + 50 * pulse))
                surf.blit(gl, (x + cell // 2 - gl.get_width() // 2, y + cell // 2 - gl.get_height() // 2))
                r = pygame.Rect(x - g // 2, y - g // 2 - int(pop * 3), cell + g, cell + g)
                pygame.draw.rect(surf, (132, 108, 62), r, border_radius=7)
                pygame.draw.rect(surf, (160, 134, 80), r.inflate(-8, -8), border_radius=5)
                bc = tuple(min(255, int(c + 30 * pulse)) for c in GOLD)
                pygame.draw.rect(surf, bc, r, 3, border_radius=7)
                ic = assets.hotbar_icon(entry)
                surf.blit(ic, (r.centerx - ic.get_width() // 2, r.centery - ic.get_height() // 2))
            else:
                pygame.draw.rect(surf, (58, 48, 64), (x, y, cell, cell), border_radius=6)
                pygame.draw.rect(surf, (72, 62, 80), (x + 3, y + 3, cell - 6, cell - 6),
                                 border_radius=4)
                pygame.draw.rect(surf, UI_BORDER, (x, y, cell, cell), 2, border_radius=6)
                surf.blit(assets.hotbar_icon(entry), (x + 6, y + 6))
            if entry[0] == "item":
                cnt = self.small.render(str(player.inv.count(entry[1])), True, GOLD)
                surf.blit(cnt, (x + cell - cnt.get_width() - 3, y + cell - 15))
            else:                                  # tool tier badge
                tier = getattr(player, "tool_tiers", {}).get(entry[1], 0)
                if tier > 0:
                    pygame.draw.rect(surf, TIER_COLORS[tier], (x + cell - 11, y + 3, 8, 8),
                                     border_radius=2)
                    pygame.draw.rect(surf, (20, 20, 24), (x + cell - 11, y + 3, 8, 8),
                                     1, border_radius=2)
        # ◀ ▶ hints when the bar extends past the visible window
        self.draw_scroll_arrows(surf, start, end, n, x0, y, total_w, cell)

    # ---- minimap ----
    def _build_minimap(self, area):
        base = pygame.Surface((area.w, area.h))
        for gy in range(area.h):
            for gx in range(area.w):
                base.set_at((gx, gy), TILE_COLORS.get(area.tile(gx, gy), (40, 40, 40)))
        for (gx, gy) in area.trees:
            base.set_at((gx, gy), (34, 90, 46))
        for (gx, gy) in area.rocks:
            base.set_at((gx, gy), (95, 95, 105))
        for (bx, by, bw, bh, *_rest) in area.buildings:
            for yy in range(by, by + bh):
                for xx in range(bx, bx + bw):
                    if 0 <= xx < area.w and 0 <= yy < area.h:
                        base.set_at((xx, yy), (155, 110, 80))
        return base

    def _mm_marker(self, surf, px, py, color, ch):
        pygame.draw.circle(surf, color, (px, py), 6)
        pygame.draw.circle(surf, (15, 15, 15), (px, py), 6, 1)
        _kit.blit_text(surf, self.tiny, ch, (20, 20, 20), (px, py))

    def draw_minimap(self, surf, area, players, npcs, label=None):
        pw, ph = 200, 148
        x, y = 14, 14
        my0 = y + 20
        surf.blit(self._card(pw + 12, ph + 34, (130, 200, 150)), (x - 6, y - 6))
        # area names derive from the area registry itself -- never a local dict
        surf.blit(self.small.render(label or area.name.upper(), True, WHITE), (x + 2, y))

        # rebuild when the map itself changes: winter tile swaps (meadow snow),
        # rocks broken / trees chopped during the visit
        try:
            sig = hash("".join("".join(r) for r in area.grid))
        except Exception:
            sig = 0
        key = (area.name, id(area), sig, len(area.rocks), len(area.trees))
        base = self._mm_cache.get(key)
        if base is None or base.get_width() != pw:
            if len(self._mm_cache) > 12:
                self._mm_cache.clear()
            base = pygame.transform.scale(self._build_minimap(area), (pw, ph))
            self._mm_cache[key] = base
        surf.blit(base, (x, my0))
        pygame.draw.rect(surf, UI_BORDER, (x, my0, pw, ph), 2, border_radius=3)

        sx, sy = pw / area.w, ph / area.h

        def P(gx, gy):
            return (x + int(gx * sx), my0 + int(gy * sy))

        # static structure markers (exit labels keep off them too)
        marks = []
        if area.shop:
            marks.append((P(*area.shop), (240, 205, 80), "$"))
        if area.bed:
            marks.append((P(*area.bed), (120, 200, 230), "Z"))
        if getattr(area, "ladder", None) and area.name == "mine":
            marks.append((P(*area.ladder), (240, 150, 60), "v"))
        for (mx, my), col, ch in marks:
            self._mm_marker(surf, mx, my, col, ch)
        soft = [pygame.Rect(mx - 7, my - 7, 14, 14) for (mx, my), _c, _h in marks]

        # where the farmers are (their dots are drawn last, and the exit labels
        # step aside so they never sit on top of "you are here")
        pdots = [pygame.Rect(0, 0, 12, 12) for _ in players]
        for r, p in zip(pdots, players):
            r.center = P(p.x / TILE, p.y / TILE)
        # warp markers (grouped by destination) -> arrow + label to next map
        self._mm_last = {"dots": pdots, "labels": []}      # read by test_ui
        seen = {}
        for w in area.warps:
            seen.setdefault(w["to"], []).append((w["gx"], w["gy"]))
        exits = []
        for to, cells in seen.items():
            agx = sum(c[0] for c in cells) / len(cells)
            agy = sum(c[1] for c in cells) / len(cells)
            exits.append((to, P(agx, agy)))
        for _to, (px, py) in exits:                    # every exit dot first ...
            pygame.draw.circle(surf, (250, 230, 90), (px, py), 4)
            pygame.draw.circle(surf, (0, 0, 0), (px, py), 4, 1)
            soft.append(pygame.Rect(px - 5, py - 5, 10, 10))
        # ... then the labels: a small rounded tag with 3-4 px padding, kept
        # inside the frame (4 px margin), off the farmers, and -- when there's
        # a free spot -- off the other markers and labels as well
        inner = pygame.Rect(x + 4, my0 + 4, pw - 8, ph - 8)
        placed = []
        for to, (px, py) in exits:
            text = "-> " + to.upper()
            tw, th = self.tiny.size(text)
            bw, bh = tw + 8, th + 3
            cx = min(max(inner.x, px - bw // 2), inner.right - bw)
            prefer_below = py < inner.bottom - 18
            cands = []
            for d in (6, 20, 34):                      # step further out if needed
                b, a = (cx, py + d), (cx, py - d - bh)
                cands += [b, a] if prefer_below else [a, b]
            cands += [(min(px + 8, inner.right - bw), py - bh // 2),
                      (max(inner.x, px - 8 - bw), py - bh // 2)]
            rects = [pygame.Rect(cxx, cyy, bw, bh) for cxx, cyy in cands]
            ok = [r for r in rects if inner.contains(r)
                  and not any(r.colliderect(d) for d in pdots)]
            best = next((r for r in ok if not any(r.colliderect(s) for s in soft)
                         and not any(r.colliderect(q) for q in placed)), None)
            if best is None:
                best = next((r for r in ok if not any(r.colliderect(q) for q in placed)), None)
            if best is None:
                best = ok[0] if ok else rects[0].clamp(inner)   # fallback: nearest spot
            placed.append(best)
            self._mm_last["labels"].append(best.copy())
            _kit.pill(surf, best, (18, 14, 26), None, radius=5, alpha=200)
            _kit.blit_text(surf, self.tiny, text, (255, 250, 170), best.center)

        # live NPC dots
        for n in npcs:
            px, py = P(n.x / TILE, n.y / TILE)
            pygame.draw.circle(surf, (230, 120, 150), (px, py), 2)
        # live player dots
        pcols = [(235, 80, 70), (80, 140, 235)]
        for i, p in enumerate(players):
            px, py = P(p.x / TILE, p.y / TILE)
            pygame.draw.circle(surf, (255, 255, 255), (px, py), 4)
            pygame.draw.circle(surf, pcols[i % 2], (px, py), 3)

    # ---- messages ----
    def _wrap(self, font, text, maxw, max_lines=2):
        """Word-wrap ``text`` to at most ``max_lines`` lines of ``maxw`` px; the
        last line ends with '...' when text had to be dropped."""
        words = str(text).split()
        lines, cur = [], ""
        for wd in words:
            cand = (cur + " " + wd) if cur else wd
            if font.size(cand)[0] <= maxw:
                cur = cand
                continue
            if cur:
                lines.append(cur)
            while font.size(wd)[0] > maxw and len(wd) > 1:    # one huge word
                k = max(1, len(wd) * maxw // max(1, font.size(wd)[0]))
                lines.append(wd[:k])
                wd = wd[k:]
            cur = wd
        if cur:
            lines.append(cur)
        lines = lines or [""]
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            last = lines[-1]
            while last and font.size(last + "...")[0] > maxw:
                last = last[:-1]
            lines[-1] = last.rstrip() + "..."
        return lines

    def _msg_surf(self, text, maxw):
        cache = self._hud_cache.setdefault("msg", {})
        key = str(text)
        s = cache.get(key)
        if s is None:
            # bullet | 18 px | text block | 12 px; every line is centred in the
            # text block (a wrapped 2nd line no longer hangs flush-left)
            texts = self._wrap(self.small, key, maxw - 30)
            full = self._wrap(self.small, key, maxw - 30, max_lines=99)
            if len(texts) > 1 and len(full) == len(texts):
                # balance: the narrowest width that still needs the same number
                # of lines, so a wrap never leaves one orphan word on line 2
                lo, hi = 1, maxw - 30
                while lo < hi:
                    mid = (lo + hi) // 2
                    if len(self._wrap(self.small, key, mid, max_lines=99)) <= len(texts):
                        hi = mid
                    else:
                        lo = mid + 1
                texts = self._wrap(self.small, key, lo, max_lines=99)
            lh = self.small.get_height()
            tw = max(self.small.size(ln)[0] for ln in texts)
            w = tw + 30
            n = len(texts)
            h = lh * n + 2 * (n - 1) + 8
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(s, (26, 20, 34, 228), (0, 0, w, h), border_radius=9)
            pygame.draw.rect(s, (120, 106, 144, 235), (0, 0, w, h), 1, border_radius=9)
            for i, ln in enumerate(texts):
                cy = h / 2 + (i - (n - 1) / 2) * (lh + 2)
                if i == 0:
                    pygame.draw.circle(s, (246, 214, 124), (10, int(cy)), 3)
                _kit.blit_text(s, self.small, ln, WHITE, (18 + tw // 2, int(cy)))
            if len(cache) > 40:
                cache.clear()
            cache[key] = s
        return s

    def draw_messages(self, surf, avoid=()):
        """Fading message feed tucked between the two player panels at the
        bottom (never over the middle of the play field). Newest line at the
        bottom; each line slides up in, then fades out. Long lines wrap to two
        lines. ``avoid``: screen rects (the farmers) the feed must not cover --
        it moves up out of the way, or goes see-through if it can't."""
        maxw = SCREEN_W - 2 * 272                      # the gap between the panels
        items = [(self._msg_surf(text, maxw), ttl)
                 for text, ttl in reversed(self.messages[-3:])]
        if not items:
            return
        total_h = sum(s.get_height() + 3 for s, _ in items)
        wmax = max(s.get_width() for s, _ in items)
        fade = 1.0
        bottom = SCREEN_H - 10
        for cand in (SCREEN_H - 10, SCREEN_H - 196):
            band = pygame.Rect(SCREEN_W // 2 - wmax // 2, cand - total_h, wmax, total_h + 10)
            if not any(band.colliderect(r) for r in avoid):
                bottom = cand
                break
        else:
            fade = 0.72          # can't dodge the farmers: see-through, still legible
        y = bottom
        for i, (s, ttl) in enumerate(items):
            age = 4.0 - ttl
            # full strength for the whole life, fading only in the last 0.6 s
            a = max(0.0, min(1.0, ttl / 0.6, age / 0.12 + 0.45)) * fade
            if i >= 2:
                a *= 0.9
            y -= s.get_height()
            rise = int((1 - min(1.0, age / 0.2)) * 10)
            s.set_alpha(int(255 * a))
            surf.blit(s, (SCREEN_W // 2 - s.get_width() // 2, y + rise))
            y -= 3

    # ---- shop ----
    def draw_shop(self, surf, shop):
        """The shop as a parchment modal (the title menu's look): ribbon title,
        ink text, gold row cursor, prices in little wells."""
        K = _kit
        w, h = 540, 420
        x = SCREEN_W // 2 - w // 2
        y = SCREEN_H // 2 - h // 2
        K.modal(surf, (x, y, w, h), getattr(shop, "title", "General Store"),
                K.font(26, True), dim_alpha=130)
        if getattr(shop, "mode", "main") == "sell":
            shop_hint = (f"{key_label(P1_KEYS['action'])} sell 1"
                         f" - Shift+{key_label(P1_KEYS['action'])} sell stack"
                         f" - {key_label(P1_KEYS['prev'])} back")
        else:
            shop_hint = (f"P1: {key_label(P1_KEYS['up'])}/{key_label(P1_KEYS['down'])} move"
                         f" - {key_label(P1_KEYS['action'])} select"
                         f" - {key_label(P1_KEYS['prev'])} close")
        # controls hint: centred footer under a rule (as Kitchen / Workbench / Quest Board)
        K.divider(surf, x + w // 2, y + h - 35, w // 2 - 60, heart=False)
        K.blit_text(surf, K.font(13), shop_hint, K.INK_SOFT, (x + w // 2, y + h - 20))
        # scroll the list so the highlighted row is always visible. The ▲ / ▼
        # hints get their own 12 px lanes above / below the rows.
        VIS, PITCH, ROW_H = 10, 32, 28
        total = len(shop.options)
        sel = shop.sel % max(1, total)
        start, end = scroll_window(total, VIS, sel)
        list_top = y + 46
        list_h = VIS * PITCH - (PITCH - ROW_H)
        bx, bw = x + 20, w - 50                       # row bands; scrollbar right of them
        lab_f, pr_f, hd_f = K.font(17, True), K.font(16, True), K.font(14, True)
        # one price-well width for the whole list, so the wells form a tidy column
        pr_w = max([pr_f.size(f"{o[1]}g")[0] for o in shop.options if o[1] is not None]
                   or [0]) + 18
        now = time.perf_counter()
        iy = list_top
        for i in range(start, end):
            label, price, kind = shop.options[i]
            band = pygame.Rect(bx, iy, bw, ROW_H)
            iy += PITCH
            if kind == "header":                     # section label: soft + centred
                hw = hd_f.size(label)[0]
                cy = band.centery
                pygame.draw.line(surf, K.WELL_LINE, (band.x + 8, cy), (band.centerx - hw // 2 - 12, cy), 2)
                pygame.draw.line(surf, K.WELL_LINE, (band.centerx + hw // 2 + 12, cy),
                                 (band.right - 8, cy), 2)
                K.blit_text(surf, hd_f, label, K.INK_SOFT, band.center)
                continue
            if i == sel:
                K.row_cursor(surf, band, now)
            elif kind == "hot":                      # today's market special
                pygame.draw.rect(surf, (255, 238, 196), band, border_radius=10)
                pygame.draw.rect(surf, K.GOLD_RIM, band, 2, border_radius=10)
            col = ((64, 124, 52) if kind in ("sell", "sellmenu") or kind.startswith("sellitem:")
                   else K.GOLD_TXT if kind == "hot"
                   else K.INK if kind == "buy" else K.INK_SOFT)
            right = band.right - 6
            if price is not None:
                ptxt = f"{price}g"
                pr = pygame.Rect(0, 0, pr_w, ROW_H - 6)
                pr.midright = (right, band.centery)
                K.well(surf, pr, hot=(i == sel), radius=7)
                K.blit_text(surf, pr_f, ptxt, K.GOLD_TXT, pr.center)
                right = pr.x - 8
            K.blit_text(surf, lab_f, K.ellipsize(lab_f, str(label), right - band.x - 16),
                        col, (band.x + 16, band.centery), align="left")
        # reusable scroll indicators (no-op when everything fits)
        self.draw_scrollbar(surf, x + w - 24, list_top, list_h, total, VIS, start,
                            track=K.WELL_LINE, thumb_col=K.WOOD)
        self.draw_scroll_arrows(surf, start, end, total, bx, list_top - 3, bw, list_h + 6,
                                vertical=True, color=K.WOOD)

    # ---- dialogue ----
    def draw_dialogue(self, surf, text):
        """Parchment speech box (the ui_kit look): the speaker's name on a
        wooden tag straddling the top edge, word-wrapped ink text and the
        standard continue line.  A villager's portrait card (handed over by the
        story domain as ``self.dialogue_portrait`` = {"text", "portrait",
        "hearts"}) sits beside it at exactly the box's height."""
        from . import ui_kit as K
        from .settings import P2_KEYS as _P2
        text = str(text)
        now = time.perf_counter()
        # "Name: line" -> a name tag + the line (short, name-like prefixes only)
        speaker, body = None, text
        head, sep, rest = text.partition(": ")
        if (sep and rest.strip() and 0 < len(head) <= 22 and len(head.split()) <= 3
                and head[:1].isupper() and not any(c in head for c in ".!?,()\"'+")):
            speaker, body = head, rest.strip()
        body = "\n".join(" ".join(p.split()) for p in body.split("\n"))   # tidy joined spaces
        dp = getattr(self, "dialogue_portrait", None)
        if not (isinstance(dp, dict) and dp.get("text") == text and dp.get("portrait")):
            dp = None
        # word-wrap into the box (a single huge word is split by characters)
        w, pad, lh = 700, 30, 26
        inner = w - pad * 2
        lines = []
        for ln in K.wrap(self.font, body, inner):
            while ln and self.font.size(ln)[0] > inner:
                k = max(1, len(ln) * inner // max(1, self.font.size(ln)[0]))
                lines.append(ln[:k])
                ln = ln[k:]
            lines.append(ln)
        lines = lines or [""]
        if len(lines) > 5:
            lines = lines[:5]
            lines[4] = K.ellipsize(self.font, lines[4] + " ...", inner)
        top = 34 if speaker else 28
        h = top + len(lines) * lh + 46
        pw = gap = 0
        if dp:
            pw, gap = 128, 14
            h = max(h, 132)
        x0 = SCREEN_W // 2 - (w + pw + gap) // 2          # box + card centred as a group
        bottom = SCREEN_H - 140                             # bottom edge fixed where it was
        box = pygame.Rect(x0 + pw + gap, bottom - h, w, h)
        # ---- portrait card: same parchment, same height as the box ----
        if dp:
            card = K.draw_card(surf, (x0, box.y, pw, h))
            hs = dp.get("hearts")
            hrow = (hs.get_height() + 10) if hs else 0
            win = pygame.Rect(card.x + 12, card.y + 12, pw - 24, h - 24 - hrow)
            K.well(surf, win)
            # the story domain hands over a fixed-size head-and-shoulders bust
            # (cropped from the sprite's own top), so every villager is framed
            # alike: centred in the window both ways, a gentle bob
            por = dp["portrait"]
            bob = int(math.sin(now * 2.4) * 2)
            prev = surf.get_clip()
            surf.set_clip(win.inflate(-4, -4).clip(prev))
            py = win.centery - por.get_height() // 2 + 2 + bob
            surf.blit(por, (win.centerx - por.get_width() // 2, py))
            surf.set_clip(prev)
            if hs:
                surf.blit(hs, (card.centerx - hs.get_width() // 2, card.bottom - 12 - hs.get_height()))
        # ---- the speech box ----
        K.draw_card(surf, box)
        if speaker:                  # the one speaker tag (shared with heart events)
            from .systems.story_restore import speaker_tag
            speaker_tag(surf, speaker, (box.x + 22, box.y - 15))
        for i, ln in enumerate(lines):
            K.blit_text(surf, self.font, ln, K.INK,
                        (box.x + pad, box.y + top + i * lh + lh // 2), align="left")
        # the standard continue line, built from the real action keys (follows rebinding)
        hint = f"{key_label(P1_KEYS['action'])} / {key_label(_P2['action'])}  -  continue"
        hf = K.font(15, True)                               # continue_hint's default face
        hy = box.bottom - 25
        hx = box.right - pad - 18 - hf.size(hint)[0] // 2
        K.continue_hint(surf, (hx, hy), now, text=hint)
        bob = int(abs(math.sin(now * 4)) * 3)
        tx, ty = box.right - pad - 4, hy - 1 + bob
        pygame.draw.polygon(surf, K.WOOD, [(tx - 6, ty - 4), (tx + 6, ty - 4), (tx, ty + 3)])

    # ---- sleep / fade ----
    def draw_center_banner(self, surf, title, subtitle=""):
        """Cosy night-sky interlude (used while sleeping): deep blue veil,
        twinkling stars, a glowing moon and a drifting 'z z z'."""
        ov = self._hud_cache.get("night_veil")
        if ov is None:
            ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            for y in range(0, SCREEN_H, 6):
                f = y / SCREEN_H
                pygame.draw.rect(ov, (int(14 + 20 * f), int(16 + 12 * f), int(44 + 20 * f), 222),
                                 (0, y, SCREEN_W, 6))
            self._hud_cache["night_veil"] = ov
        surf.blit(ov, (0, 0))
        now = time.perf_counter()
        for i in range(46):                                   # twinkling stars
            sx = (i * 283 + 71) % SCREEN_W
            sy = (i * 157 + 23) % (SCREEN_H - 160)
            tw = (math.sin(now * 2.2 + i * 1.7) + 1) * 0.5
            c = int(150 + 105 * tw)
            pygame.draw.circle(surf, (c, c, min(255, c + 20)), (sx, sy), 1 + (i % 3 == 0))
        mx, my = SCREEN_W // 2, SCREEN_H // 2 - 120
        surf.blit(assets.hud.glow(70, (230, 226, 200), 70), (mx - 70, my - 70))
        pygame.draw.circle(surf, (246, 240, 214), (mx, my), 30)
        pygame.draw.circle(surf, (226, 218, 190), (mx - 9, my + 6), 6)
        pygame.draw.circle(surf, (226, 218, 190), (mx + 10, my - 8), 4)
        for k in range(3):                                   # z z z
            ph = (now * 0.6 + k / 3) % 1.0
            zf = self.font if k < 2 else self.big
            z = zf.render("z", True, (200, 214, 255))
            z.set_alpha(int(255 * (1 - ph)))
            surf.blit(z, (mx + 44 + int(ph * 40) + k * 6, my - 10 - int(ph * 50)))
        # parchment banner: the title on the folded ribbon, the date/time
        # centred in the card below it (ui_kit look, like every opened panel)
        K = _kit
        tf, sf = K.font(28, True), K.font(20, True)
        # "Spring 2   6:00 AM" -> "Spring 2  ·  6:00 AM" (a visible separator
        # instead of a wide run of blanks)
        sub = "  ·  ".join(p.strip() for p in str(subtitle or "").split("   ") if p.strip())
        inner_w = max(tf.size(title)[0] + 110, sf.size(sub)[0] + 90 if sub else 0, 300)
        card = pygame.Rect(0, 0, inner_w, 104 if sub else 58)
        card.center = (SCREEN_W // 2, SCREEN_H // 2 + 16)
        K.modal(surf, card, title, tf)
        if sub:
            K.divider(surf, card.centerx, card.y + 49, min(110, card.w // 2 - 40), heart=True)
            K.blit_text(surf, sf, sub, K.INK, (card.centerx, card.y + 76))

    # ---- title / help ----
    def draw_title(self, surf):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((18, 30, 24, 235))
        surf.blit(overlay, (0, 0))
        t = self.big.render("HARVEST DUO", True, GOLD)
        surf.blit(t, (SCREEN_W // 2 - t.get_width() // 2, 80))
        sub = self.font.render("A two-player co-op farm  -  share one keyboard", True, WHITE)
        surf.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 130))
        lines = [
            "",
            "PLAYER 1            PLAYER 2",
            "Move:  W A S D       Move:  Arrow keys",
            "Use:   SPACE         Use:   ENTER",
            "Tool:  Q / E         Tool:  , / .",
            "",
            "HOW TO PLAY",
            " - On the farm: select Hoe to till soil, plant a seed,",
            "   then Watering Can. Crops grow over days.",
            " - Walk to the bottom path to reach TOWN.",
            " - In town: talk to villagers (Use), fish at the pond (Rod),",
            "   and visit the Shop to buy seeds & sell goods.",
            " - From town, head bottom-left into the MINE:",
            "   break rocks (Pickaxe) for ore, fight slimes (Sword).",
            " - Sleep in the bed at your house to start the next day.",
            "",
            "Press SPACE or ENTER to start farming!",
        ]
        y = 175
        for ln in lines:
            c = GOLD if ln in ("PLAYER 1            PLAYER 2", "HOW TO PLAY") else WHITE
            s = self.font.render(ln, True, c)
            surf.blit(s, (SCREEN_W // 2 - 320, y))
            y += 26
