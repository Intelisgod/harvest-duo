"""All on-screen drawing: world tiles, entities, prompts, HUD and overlays.

Owner: "UI & Rendering" chat.
Related modules: ui.py (fonts, panels, hotbar, minimap), assets/ (sprites),
menu.py, homeiso.py, lighting.py.

This is the presentation layer. Gameplay systems own *state*; this mixin turns
that state into pixels. ``draw_world`` deliberately renders several features
inline (crops, sprinklers, the festival stall, quest board, signposts) because
they share the single tile/camera pass -- coordinate here when a new feature
needs a world-space visual.
"""
import math
import random
import pygame
from ..settings import (TILE, SCREEN_W, SCREEN_H, AREA_FARM, AREA_TOWN,
                        AREA_MINE, AREA_HOME, AREA_FOREST, AREA_TEMPLE, AREA_COOP,
                        AREA_BEACH, P1_KEYS, P2_KEYS)
try:
    from ..settings import AREA_MEADOW
except Exception:                                   # pragma: no cover
    AREA_MEADOW = "meadow"
from ..ui import key_label
from ..world import (GRASS, GRASS2, PATH, DIRT, SAND, SAND2, TILE_COLORS, WATER, WALL,
                    TFLOOR, TMAT, FLOOR)

# outdoor walkable ground that turns snowy in winter
_SNOW_GROUND = (GRASS, GRASS2, PATH, DIRT, SAND, SAND2)
_SNOW_AREAS = (AREA_FARM, AREA_TOWN, AREA_FOREST, AREA_BEACH)
# rain/snow overlay areas (the meadow turns its own tiles to SNOW in winter, so
# it is NOT in _SNOW_AREAS)
_WEATHER_AREAS = (AREA_FARM, AREA_TOWN, AREA_FOREST, AREA_BEACH, AREA_MEADOW)
# subtle biome hue blended into mine boulders so they match the floor
# (fallback only -- world.BIOME_STYLE[biome]["rock_tint"] wins when present)
_BIOME_ROCK_TINT = {"ice": (150, 190, 218), "lava": (156, 72, 54), "crystal": (126, 94, 168)}
# ground-accent tint for mine floors whose biome has no rock_tint (plain rock)
_ROCK_GROUND_TINT = (150, 138, 128)


def _mine_wall_color(floor_col, tint):
    """Border-wall colour that belongs to the biome: its floor mixed with
    the rock tint, darkened (never the flat generic taupe)."""
    m = [f * 0.55 + r * 0.45 for f, r in zip(floor_col, tint)]
    luma = 0.3 * floor_col[0] + 0.59 * floor_col[1] + 0.11 * floor_col[2]
    k = 0.6 if luma > 110 else 0.66
    return tuple(max(0, min(255, int(c * k))) for c in m)
# seasonal grass palette (base, alt, blade colour) for outdoor ground
_GRASS_SEASON = {
    "Spring": ((162, 208, 148), (154, 202, 141), (122, 176, 112)),
    "Summer": ((142, 200, 124), (135, 194, 117), (98, 160, 90)),
    "Fall":   ((200, 196, 124), (192, 187, 116), (170, 142, 80)),
    "Winter": ((178, 196, 176), (171, 189, 169), (140, 160, 140)),
}
_FLOWER_COLS = {"Spring": [(246, 170, 200), (252, 226, 154), (216, 198, 242), (255, 250, 250)],
                "Summer": [(252, 214, 96), (246, 150, 120), (255, 250, 240)],
                "Fall":   [(232, 128, 70), (206, 86, 64), (246, 190, 90)],
                "Winter": [(236, 240, 250)]}
_GROUND_CACHE_MAX = 3
# World's 2026-09 flat tiles (guarded: fall back to their chars)
from .. import world as _wm
_T_COBBLE = getattr(_wm, "COBBLE", "o")
_T_SNOW = getattr(_wm, "SNOW", "*")
_T_SNOWPATH = getattr(_wm, "SNOWPATH", "~")
_T_ABYSS = getattr(_wm, "ABYSS", "v")
_T_RUINS = getattr(_wm, "RUINS", "u")
from .. import assets, festival, weather, lighting, homeiso
from .. import world as _world_mod
from .. import furniture as F
from .. import fishing


class RenderMixin:
    """The full draw pipeline for the play / build / menu states."""

    # ---------- draw ----------
    def draw(self):
        # online: a farmer in another area is hidden from this screen
        parked = getattr(self, "_draw_parked", None)
        if parked is None:
            return self._draw_frame()
        with parked():
            return self._draw_frame()

    def _draw_frame(self):
        # HUD reservations (ui_system.hud_reserve): last frame's become current
        self._hud_res = self.__dict__.get("_hud_res_cur", [])
        self._hud_res_cur = []
        self.screen.fill((18, 18, 22))
        if self.state == "menu":
            self.menu.draw(self.screen)
            pygame.display.flip()
            return

        if self.state == "create":
            self.creator.update(self.clock.get_time() / 1000.0)
            self.creator.draw(self.screen)
            pygame.display.flip()
            return

        if self.state == "build":
            self.draw_world()                 # iso room (incl. players) + grid
            self.build.draw(self.screen)
            pygame.display.flip()
            return

        if self.state == "inventory" and getattr(self, "inv_screen", None):
            self.inv_screen.draw(self.screen)   # fullscreen arrange screen (press I)
            pygame.display.flip()
            return

        if self.state == "mistcity":
            f = getattr(self, "_mist_draw", None)   # MistMixin (guarded); without
            if f:                                   # it we fall through to the
                f()                                 # normal draw -- never a black
                pygame.display.flip()               # screen.
                return

        if self.state == "sleep":
            self.update_sleep(self.clock.get_time() / 1000.0)

        ox, oy = self._shake_offset()
        self.cam.x += ox
        self.cam.y += oy
        self.draw_world()
        # the iso home view draws its own players; everywhere else uses the
        # normal top-down entity + prompt pass
        iso_home = (self.world.current == AREA_HOME)
        if not iso_home:
            self.draw_entities()
        self._run_hooks("_draw_world_")                     # domain world-space layers
        self._ambient_fx(self.clock.get_time() / 1000.0)   # chimney smoke / flames / embers / bubbles
        self.parts.draw(self.screen, self.cam)
        self._draw_popups()
        if not iso_home:
            self.draw_prompts()
        self._draw_anniv_hint()
        self.cam.x -= ox
        self.cam.y -= oy
        self._draw_weather()
        lights = []                  # extra glows from _lights_* hooks (lamps, fires, ...)
        for n in self._hook_names("_lights_"):
            lights += self._call_hook(n) or ()
        self.night = lighting.apply(self.screen, self.time.minutes, self.world.current,
                                    self.players, self.cam, lights)
        self._draw_hurt_flash()
        self._run_hooks("_draw_sky_")                       # lightning etc. (under the HUD)
        if self.fade > 0:
            self._draw_transition()
        self.draw_hud()
        self._run_hooks("_draw_hud_")                       # domain HUD widgets

        if self.state == "shop":
            self.ui.draw_shop(self.screen, self.shop)
        elif self.state == "dialogue":
            self.ui.draw_dialogue(self.screen, self.dialogue_text)
        elif self.state == "craft":
            self.craft.draw(self.screen)
        elif self.state == "quest":
            self.quest.draw(self.screen)
        elif self.state == "cook":
            self.cook.draw(self.screen)
        elif self.state == "storage":
            self.storage.draw(self.screen)
        elif self.state == "sleep":
            self.ui.draw_center_banner(self.screen, "Sleeping...",
                                       f"{self.time.date_str()}   {self.time.clock_str()}")
        else:
            self._run_state("draw")                         # domain custom states
        # toasts go on top of the modal menus above (the HUD hook pass skips
        # them in these states), so e.g. a quest reward or an achievement
        # unlocked at the workbench is shown at full brightness, not under the panel
        if self.state in getattr(self, "_TOAST_OVER_STATES", ()):
            f = getattr(self, "_ui_draw_toasts", None)
            if f:
                f()
        pygame.display.flip()

    def _popup_surf(self, text, color):
        """Floating text with a soft dark outline so it reads on any ground
        (cached per text/colour)."""
        cache = self.__dict__.setdefault("_popup_cache", {})
        key = (text, tuple(color[:3]))
        s = cache.get(key)
        if s is None:
            from .. import ui_kit
            # bold + a 2 px outline: readable on sand, snow and water alike
            s = ui_kit.outlined(ui_kit.font(15, True), text, color, (30, 22, 30), 2)
            if len(cache) > 160:
                cache.clear()
            cache[key] = s
        return s

    def _popup_avoid_rects(self):
        """Screen rects floating texts must not cover: the fixed HUD cards
        (minimap, hotbars, clock card, player panels), rects other domains
        reserved (hud_reserve) and last frame's item tags / area card."""
        out = []
        if self.state == "play":
            out += [pygame.Rect(0, 0, 232, 204),                       # minimap card
                    pygame.Rect(404, 0, 472, 106),                     # both hotbars
                    pygame.Rect(SCREEN_W - 298, 0, 298, 118),          # clock card
                    pygame.Rect(0, SCREEN_H - 132, 270, 132),          # player panels
                    pygame.Rect(SCREEN_W - 270, SCREEN_H - 132, 270, 132)]
        if getattr(self, "in_sync", False):                    # the In Sync pill's spot
            out.append(pygame.Rect(SCREEN_W // 2 - 64, 98, 128, 32))
        f = getattr(self, "hud_reserved", None)
        if f:
            out += f()
        out += list(getattr(self, "_seltag_last", None) or [])
        f = getattr(self, "_ui_player_rects", None)          # never over a farmer
        if f:
            out += f()
        out += list(getattr(self, "_toast_rects_last", None) or [])
        out += list(getattr(self, "_prompt_rects_last", None) or [])
        f = getattr(self, "area_card_rect", None)
        card = f() if f else None
        if card is not None:
            out.append(card)
        return out

    def _draw_popups(self):
        """Floating texts: each one takes the nearest free spot to its anchor
        (the newest keeps its anchor, older ones step up above it), never on
        another text and never under the fixed HUD cards / tags."""
        cam = self.cam
        items = []
        for pop in reversed(self.popups):                  # newest first
            x, y, text, color, life = pop[:5]
            surf = self._popup_surf(str(text), color)
            r = surf.get_rect()
            r.midtop = (int(x - cam.x), int(y - cam.y))
            items.append((surf, r, life))
        if not items:
            self._popup_rects_last = []
            return
        avoid = self._popup_avoid_rects()
        screen = self.screen.get_rect()
        placed = []
        for surf, r, life in items:
            step = r.h + 1
            cands = [(0, -k * step) for k in range(8)] + [(0, k * step) for k in range(1, 12)]
            # beside a HUD card it overlaps (e.g. just right of the minimap)
            for a in avoid:
                if r.colliderect(a):
                    cands += [(a.right + 4 - r.left, -k * step) for k in range(4)]
            best = None
            for dx, dy in cands:
                q = r.move(dx, dy)
                if not screen.contains(q):
                    continue
                if any(q.colliderect(o) for o in placed) or any(q.colliderect(a) for a in avoid):
                    continue
                best = q
                break
            if best is None:                               # crowded: at least not on a text
                best = r.move(0, 0)
                while any(best.colliderect(o) for o in placed) and best.top > 0:
                    best.move_ip(0, -step)
            placed.append(best)
            surf.set_alpha(max(0, min(255, int(life * 255))))
            self.screen.blit(surf, best.topleft)
        self._popup_rects_last = placed

    def _draw_anniv_hint(self):
        """The anniversary cabana's 'needs two players' nudge -- a small Thai label
        in a soft bubble above the cabana, shown when one player presses there alone.
        Rendered apart from _draw_popups because Consolas has no Thai glyphs, so it
        uses the UI's dedicated Thai font plus a drawn heart (emoji won't render)."""
        hint = getattr(self, "_anniv_hint", None)
        if not hint:
            return
        wx, wy, life = hint
        cam = self.cam
        a = max(0, min(255, int(min(1.0, life / 0.9) * 255)))
        font = getattr(self.ui, "thai", self.ui.small)
        txt = font.render("ต้องมาด้วยกันสองคน", True, (255, 246, 250))
        padx, pady = 10, 6
        heart_w = 16
        w = txt.get_width() + padx * 2 + heart_w
        h = txt.get_height() + pady * 2
        bub = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(bub, (34, 26, 38, 225), (0, 0, w, h), border_radius=9)
        pygame.draw.rect(bub, (255, 150, 185, 235), (0, 0, w, h), 2, border_radius=9)
        bub.blit(txt, (padx, pady))
        # a little drawn heart after the text (an emoji glyph would not render)
        hx = padx + txt.get_width() + 9
        hy = h // 2
        for (ox, rr) in ((-3, 3), (3, 3)):
            pygame.draw.circle(bub, (255, 120, 160), (hx + ox, hy - 1), rr)
        pygame.draw.polygon(bub, (255, 120, 160),
                            [(hx - 5, hy), (hx + 5, hy), (hx, hy + 6)])
        bub.set_alpha(a)
        sx = int(wx - cam.x - w // 2)
        sy = int(wy - cam.y - h)
        self.screen.blit(bub, (sx, sy))

    def _home_shadow(self, fw, fh):
        """Cached soft contact shadow for a furniture footprint."""
        if not hasattr(self, "_shadow_cache"):
            self._shadow_cache = {}
        key = (fw, fh)
        sh = self._shadow_cache.get(key)
        if sh is None:
            sh = pygame.Surface((fw * TILE, TILE), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (0, 0, 0, 55), (5, TILE - 13, fw * TILE - 10, 11))
            self._shadow_cache[key] = sh
        return sh

    def _draw_room_door(self, wp, cam):
        scr = self.screen
        dx = wp["gx"] * TILE - cam.x
        dy = wp["gy"] * TILE - cam.y
        # warm wooden door set into the wall + knob + little welcome mat
        pygame.draw.rect(scr, (120, 86, 58), (dx + 4, dy + TILE - 24, TILE - 8, 24), border_radius=3)
        pygame.draw.rect(scr, (160, 122, 86), (dx + 7, dy + TILE - 21, TILE - 14, 21), border_radius=2)
        pygame.draw.line(scr, (120, 86, 58), (dx + TILE // 2, dy + TILE - 21),
                         (dx + TILE // 2, dy + TILE - 2), 1)
        pygame.draw.circle(scr, (240, 214, 120), (dx + TILE - 13, dy + TILE - 11), 2)
        pygame.draw.ellipse(scr, (214, 170, 192), (dx + 9, dy + TILE - 5, TILE - 18, 6))

    def _draw_home_topdown(self, area, cam):
        scr = self.screen
        wall = F.WALL_COLORS[self.world.home_wall_idx]
        floor = F.FLOOR_COLORS[self.world.home_floor_idx]
        wdk = tuple(max(0, c - 30) for c in wall)
        wlt = tuple(min(255, c + 16) for c in wall)
        fdk = tuple(max(0, c - 24) for c in floor)
        flt = tuple(min(255, c + 16) for c in floor)
        grain = tuple(max(0, c - 12) for c in floor)
        for gy in range(area.h):
            for gx in range(area.w):
                rx = gx * TILE - cam.x
                ry = gy * TILE - cam.y
                if area.tile(gx, gy) == WALL:
                    if gy == 0:
                        # papered BACK feature wall: vertical stripes + dot + rail
                        pygame.draw.rect(scr, wall, (rx, ry, TILE, TILE))
                        pygame.draw.rect(scr, wlt, (rx + 7, ry, 3, TILE))
                        pygame.draw.rect(scr, wlt, (rx + 31, ry, 3, TILE))
                        pygame.draw.circle(scr, wlt, (rx + 24, ry + 13), 2)
                        pygame.draw.rect(scr, wdk, (rx, ry + TILE - 6, TILE, 6))   # rail/skirting
                        pygame.draw.line(scr, wlt, (rx, ry + TILE - 6), (rx + TILE, ry + TILE - 6), 1)
                    elif gx == 0:
                        # papered LEFT feature wall: horizontal stripes + dot + rail
                        pygame.draw.rect(scr, wall, (rx, ry, TILE, TILE))
                        pygame.draw.rect(scr, wlt, (rx, ry + 7, TILE, 3))
                        pygame.draw.rect(scr, wlt, (rx, ry + 31, TILE, 3))
                        pygame.draw.circle(scr, wlt, (rx + 13, ry + 24), 2)
                        pygame.draw.rect(scr, wdk, (rx + TILE - 6, ry, 6, TILE))   # rail/skirting
                        pygame.draw.line(scr, wlt, (rx + TILE - 6, ry), (rx + TILE - 6, ry + TILE), 1)
                    else:
                        # plain boundary wall (bottom + right edges open the room)
                        pygame.draw.rect(scr, wdk, (rx, ry, TILE, TILE))
                        pygame.draw.rect(scr, wall, (rx + 3, ry + 3, TILE - 6, TILE - 6))
                else:
                    # parquet plank floor: staggered boards with seams + faint grain
                    base = flt if gy % 2 == 0 else floor
                    pygame.draw.rect(scr, base, (rx, ry, TILE, TILE))
                    pygame.draw.line(scr, fdk, (rx, ry), (rx + TILE, ry), 1)
                    pygame.draw.line(scr, flt, (rx, ry + 1), (rx + TILE, ry + 1), 1)
                    jx = rx + (TILE // 2 if gy % 2 == 0 else 0)
                    pygame.draw.line(scr, fdk, (jx, ry), (jx, ry + TILE), 1)
                    h = (gx * 73856093) ^ (gy * 19349663)
                    if h % 2 == 0:
                        yy = ry + 18 + (h % 12)
                        pygame.draw.line(scr, grain, (rx + 6, yy), (rx + TILE - 8, yy), 1)
        # pretty doors set into the bottom wall
        for wp in area.warps:
            self._draw_room_door(wp, cam)
        # dynamic furniture: rugs (floor layer) under, then ground items by depth
        # (the bed is a normal furniture piece, drawn in the loop below)
        fl = [p for p in self.world.home_furniture if F.CAT[p.kind]["layer"] == "floor"]
        gr = [p for p in self.world.home_furniture if F.CAT[p.kind]["layer"] != "floor"]
        for p in fl:
            scr.blit(F.sprite(p.kind, p.color, p.rot),
                     (p.gx * TILE - cam.x, p.gy * TILE - cam.y))
        for p in sorted(gr, key=lambda q: q.gy):
            px = p.gx * TILE - cam.x
            py = p.gy * TILE - cam.y
            if F.CAT[p.kind]["layer"] == "ground":
                fw, fh = F.footprint(p.kind, p.rot)
                scr.blit(self._home_shadow(fw, fh), (px, py + (fh - 1) * TILE))
            scr.blit(F.sprite(p.kind, p.color, p.rot), (px, py))
            F.draw_quality(scr, px + 2, py + 2, getattr(p, "level", 1))

    def _tile_detail(self, t, rx, ry, gx, gy, scr=None, season=None):
        """Cheap deterministic ground decoration: grass blades & seasonal
        flowers / fallen leaves, path pebbles, soil specks. Drawn once into
        the cached ground layer (``scr``)."""
        h = (gx * 73856093) ^ (gy * 19349663)
        scr = scr or self.screen
        if t in (GRASS, GRASS2):
            pal = _GRASS_SEASON.get(season)
            bc = pal[2] if pal else (122, 172, 114)
            # soft light/dark patches break up the checkerboard
            if h % 7 == 0:
                pygame.draw.ellipse(scr, tuple(max(0, c - 10) for c in (pal[0] if pal else (160, 206, 150))),
                                    (rx + 6, ry + 10, 30, 16))
            elif h % 11 == 3:
                pygame.draw.ellipse(scr, tuple(min(255, c + 10) for c in (pal[1] if pal else (146, 196, 138))),
                                    (rx + 10, ry + 20, 26, 12))
            if h % 3 == 0:
                pygame.draw.line(scr, bc, (rx + 11, ry + 35), (rx + 13, ry + 27), 2)
                pygame.draw.line(scr, bc, (rx + 31, ry + 40), (rx + 33, ry + 32), 2)
            if h % 5 == 1:
                pygame.draw.line(scr, bc, (rx + 22, ry + 20), (rx + 23, ry + 13), 2)
            if season == "Summer" and h % 4 == 2:                  # lush extra tufts
                pygame.draw.line(scr, bc, (rx + 38, ry + 22), (rx + 40, ry + 14), 2)
                pygame.draw.line(scr, bc, (rx + 6, ry + 18), (rx + 7, ry + 11), 2)
            cols = _FLOWER_COLS.get(season) or [(246, 184, 204), (252, 226, 154), (216, 198, 242)]
            if season == "Fall":
                if h % 6 == 0:                                      # fallen leaves
                    for k in range(2):
                        lx, ly = rx + 8 + (h >> (3 + k)) % 30, ry + 8 + (h >> (6 + k)) % 30
                        pygame.draw.ellipse(scr, cols[(h >> k) % len(cols)], (lx, ly, 6, 4))
            elif h % (13 if season == "Spring" else 29) == 0:
                fc = cols[h % len(cols)]
                cx2, cy2 = rx + 14 + h % 20, ry + 14 + (h >> 4) % 20
                for ang in range(0, 360, 72):
                    a = math.radians(ang)
                    pygame.draw.circle(scr, fc, (int(cx2 + math.cos(a) * 3),
                                                 int(cy2 + math.sin(a) * 3)), 2)
                pygame.draw.circle(scr, (255, 248, 224), (cx2, cy2), 1)
        elif t == PATH:
            if h % 5 == 0:
                pygame.draw.circle(scr, (206, 188, 152), (rx + 16, ry + 30), 2)
            if h % 7 == 0:
                pygame.draw.circle(scr, (234, 216, 180), (rx + 34, ry + 16), 2)
        elif t == DIRT:
            if h % 4 == 0:
                pygame.draw.circle(scr, (184, 156, 118), (rx + 20, ry + 24), 1)
        elif t == _T_COBBLE:                    # cobbled path: a few rounded stones
            for k, (ox, oy, w_, h_) in enumerate(((4, 5, 18, 14), (25, 3, 19, 15),
                                                   (2, 24, 15, 17), (19, 21, 17, 14),
                                                   (37, 22, 9, 16), (8, 39, 20, 8),
                                                   (30, 38, 16, 9))):
                shade = 8 if (h >> k) & 1 else -6
                col = tuple(max(0, min(255, c + shade)) for c in (178, 168, 150))
                pygame.draw.ellipse(scr, col, (rx + ox, ry + oy, w_, h_))
                pygame.draw.ellipse(scr, (146, 136, 120), (rx + ox, ry + oy, w_, h_), 1)
        elif t == _T_SNOW:                      # winter meadow: drifts + glints
            if h % 3 == 0:
                pygame.draw.ellipse(scr, (226, 232, 244), (rx + 6, ry + 26, 30, 10))
            if h % 5 == 1:
                pygame.draw.circle(scr, (255, 255, 255), (rx + 12 + h % 24, ry + 10 + (h >> 3) % 24), 1)
        elif t == _T_SNOWPATH:                  # packed snow: soft ruts + pebbles
            pygame.draw.line(scr, (202, 198, 204), (rx, ry + 16), (rx + TILE, ry + 16), 1)
            pygame.draw.line(scr, (202, 198, 204), (rx, ry + 32), (rx + TILE, ry + 32), 1)
            if h % 4 == 0:
                pygame.draw.circle(scr, (176, 168, 166), (rx + 10 + h % 28, ry + 24), 2)
        elif t == _T_ABYSS:                     # abyss floor: faint violet fissures
            if h % 3 == 0:
                x0 = rx + 6 + h % 20
                pygame.draw.lines(scr, (70, 56, 104), False,
                                  [(x0, ry + 8), (x0 + 6, ry + 20), (x0 + 2, ry + 30),
                                   (x0 + 10, ry + 42)], 1)
            if h % 7 == 2:
                pygame.draw.circle(scr, (116, 90, 170), (rx + 30, ry + 14), 1)
        elif t == _T_RUINS:                     # ancient ruins: sandstone slabs
            seam = (146, 128, 98)
            pygame.draw.line(scr, seam, (rx, ry), (rx + TILE, ry), 1)
            pygame.draw.line(scr, seam, (rx + (0 if gy % 2 else TILE // 2), ry),
                             (rx + (0 if gy % 2 else TILE // 2), ry + TILE), 1)
            if h % 6 == 0:
                pygame.draw.line(scr, seam, (rx + 12, ry + 20), (rx + 22, ry + 26), 1)
        elif t == TFLOOR:                       # ornate temple tiles: gold seams
            seam = (206, 178, 112)
            pygame.draw.line(scr, seam, (rx, ry), (rx + TILE, ry), 1)
            pygame.draw.line(scr, seam, (rx, ry), (rx, ry + TILE), 1)
            if (gx + gy) % 2 == 0:
                pygame.draw.circle(scr, (214, 188, 128), (rx + TILE // 2, ry + TILE // 2), 2)
        elif t == TMAT:                         # red prayer-mat runner with fringe
            pygame.draw.line(scr, (150, 46, 44), (rx + 2, ry), (rx + 2, ry + TILE), 2)
            pygame.draw.line(scr, (150, 46, 44), (rx + TILE - 2, ry), (rx + TILE - 2, ry + TILE), 2)
            pygame.draw.line(scr, (206, 150, 90), (rx + TILE // 2, ry + 6),
                             (rx + TILE // 2, ry + TILE - 6), 1)

    @staticmethod
    def _wall_detail(scr, rx, ry, gx, gy, col):
        """Indoor / mine border wall: staggered stone courses with a lit top
        edge and the odd crack (baked into the cached ground layer)."""
        h = (gx * 73856093) ^ (gy * 19349663)
        dk = tuple(max(0, int(c * 0.7)) for c in col)
        lt = tuple(min(255, int(c * 1.18) + 8) for c in col)
        q = TILE // 3
        for row in range(3):
            y0 = ry + row * q
            pygame.draw.line(scr, dk, (rx, y0), (rx + TILE - 1, y0), 1)
            pygame.draw.line(scr, lt, (rx, y0 + 1), (rx + TILE - 1, y0 + 1), 1)
            off = (TILE // 4) if (row + gy) % 2 else (TILE * 3 // 4)
            for jx in (off - TILE // 2, off):
                if 0 < jx < TILE:
                    pygame.draw.line(scr, dk, (rx + jx, y0 + 2), (rx + jx, y0 + q - 1), 1)
        if h % 5 == 0:
            cx0, cy0 = rx + 10 + h % 24, ry + 6 + (h >> 5) % 30
            pygame.draw.lines(scr, dk, False, [(cx0, cy0), (cx0 + 4, cy0 + 5),
                                               (cx0 + 2, cy0 + 10)], 1)

    @staticmethod
    def _floor_planks(scr, rx, ry, gx, gy, col):
        """Indoor FLOOR (coop / cabins): wooden planks with staggered end
        joints, a little grain and the odd straw wisp -- deterministic."""
        h = (gx * 73856093) ^ (gy * 19349663)
        seam = tuple(max(0, int(c * 0.82)) for c in col)
        grain = tuple(max(0, int(c * 0.92)) for c in col)
        ph = TILE // 4
        for k in range(4):
            y0 = ry + k * ph
            if k:
                pygame.draw.line(scr, seam, (rx, y0), (rx + TILE - 1, y0), 1)
            jx = (gx * 17 + (gy * 4 + k) * 29) % TILE
            if (h >> (k + 4)) & 1 and 4 < jx < TILE - 4:        # long boards: ~1 joint / 2 tiles
                pygame.draw.line(scr, seam, (rx + jx, y0 + 1), (rx + jx, y0 + ph - 1), 1)
            if (h >> k) & 3 == 0:
                gx0 = rx + 6 + (h >> (k + 2)) % (TILE - 20)
                pygame.draw.line(scr, grain, (gx0, y0 + ph // 2), (gx0 + 8, y0 + ph // 2), 1)
        if h % 7 == 0:                                   # a stray wisp of straw
            sx, sy = rx + 8 + h % 28, ry + 8 + (h >> 4) % 28
            pygame.draw.line(scr, (222, 196, 112), (sx, sy), (sx + 7, sy - 2), 1)
            pygame.draw.line(scr, (206, 176, 96), (sx + 2, sy + 2), (sx + 8, sy + 3), 1)

    def _ground_cache(self, area):
        """One pre-rendered Surface of the whole area's static ground, rebuilt
        only when the area / season / tile grid changes. Returns
        {"surf": Surface, "water": {(gx, gy): shore_mask}}."""
        season = self.time.season
        try:
            sig = hash("".join("".join(r) for r in area.grid))
        except Exception:
            sig = id(area.grid)
        key = (area.name, id(area), season, sig, area.w, area.h)
        cache = self.__dict__.setdefault("_ground_caches", {})
        hit = cache.get(key)
        if hit is not None:
            return hit
        if len(cache) >= _GROUND_CACHE_MAX:
            cache.pop(next(iter(cache)))
        W, H = area.w * TILE, area.h * TILE
        surf = pygame.Surface((max(1, W), max(1, H)))
        surf.fill((18, 18, 22))
        winter_snow = (season == "Winter" and area.name in _SNOW_AREAS)
        outdoor = area.name not in (AREA_MINE, AREA_HOME, AREA_COOP)
        gpal = _GRASS_SEASON.get(season) if outdoor else None
        snow_ov = None
        if winter_snow:
            snow_ov = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            snow_ov.fill((242, 246, 252, 224))
            for sx, sy in ((6, 9), (20, 5), (13, 18), (30, 14), (24, 28), (38, 22), (10, 34)):
                pygame.draw.circle(snow_ov, (255, 255, 255, 235), (sx, sy), 2)
                pygame.draw.circle(snow_ov, (214, 224, 240, 150), (sx + 3, sy + 3), 1)
        # mine floor accent from the biome style (speckles / cracks)
        biome = getattr(area, "biome", None)
        style = (getattr(_world_mod, "BIOME_STYLE", None) or {}).get(biome) or {}
        rt = style.get("rock_tint")
        wall_col = None
        if area.name == AREA_MINE:
            if not rt:                          # plain rock floors: cracks + specks too
                rt = _ROCK_GROUND_TINT
            fcol = TILE_COLORS.get(style.get("floor", FLOOR), TILE_COLORS.get(FLOOR, (120, 110, 100)))
            wall_col = _mine_wall_color(fcol, rt)
        water_tiles = {}
        is_water = lambda gx, gy: area.tile(gx, gy) == WATER
        for gy in range(area.h):
            for gx in range(area.w):
                t = area.tile(gx, gy)
                rx, ry = gx * TILE, gy * TILE
                if t == WATER:
                    m = 0
                    if gy > 0 and not is_water(gx, gy - 1):
                        m |= 1
                    if gx < area.w - 1 and not is_water(gx + 1, gy):
                        m |= 2
                    if gy < area.h - 1 and not is_water(gx, gy + 1):
                        m |= 4
                    if gx > 0 and not is_water(gx - 1, gy):
                        m |= 8
                    water_tiles[(gx, gy)] = m
                    pygame.draw.rect(surf, TILE_COLORS.get(WATER, (80, 140, 200)),
                                     (rx, ry, TILE, TILE))
                    continue
                col = TILE_COLORS.get(t, (40, 40, 40))
                if gpal and t in (GRASS, GRASS2):
                    col = gpal[0] if t == GRASS else gpal[1]
                if t == WALL and wall_col is not None:
                    col = wall_col
                pygame.draw.rect(surf, col, (rx, ry, TILE, TILE))
                if t == WALL and not outdoor:
                    self._wall_detail(surf, rx, ry, gx, gy, col)
                elif t == FLOOR and not outdoor and area.name != AREA_MINE:
                    self._floor_planks(surf, rx, ry, gx, gy, col)
                if t == GRASS and (gx + gy) % 2 == 0:
                    pygame.draw.rect(surf, gpal[1] if gpal else TILE_COLORS[GRASS2],
                                     (rx, ry, TILE, TILE))
                self._tile_detail(t, rx, ry, gx, gy, surf, season if outdoor else None)
                if area.name == AREA_MINE and rt and t != WALL:
                    hh = (gx * 73856093) ^ (gy * 19349663)
                    dk = tuple(max(0, int(c * 0.8)) for c in col)
                    lt = tuple(min(255, int(c * 0.5 + v * 0.5)) for c, v in zip(col, rt))
                    if hh % 3 == 0:
                        pygame.draw.line(surf, dk, (rx + 8, ry + 30), (rx + 20, ry + 24), 1)
                        pygame.draw.line(surf, dk, (rx + 20, ry + 24), (rx + 26, ry + 32), 1)
                    if hh % 4 == 1:
                        pygame.draw.circle(surf, lt, (rx + 12 + hh % 24, ry + 10 + (hh >> 4) % 26), 2)
                if snow_ov is not None and t in _SNOW_GROUND:
                    surf.blit(snow_ov, (rx, ry))
                # damp, darker lip where land meets water
                if (t not in (WALL,)) and outdoor:
                    dark = tuple(max(0, int(c * 0.86)) for c in col)
                    if is_water(gx, gy + 1) and gy < area.h - 1:
                        pygame.draw.rect(surf, dark, (rx, ry + TILE - 5, TILE, 5))
                    if is_water(gx, gy - 1) and gy > 0:
                        pygame.draw.rect(surf, dark, (rx, ry, TILE, 3))
                    if is_water(gx + 1, gy) and gx < area.w - 1:
                        pygame.draw.rect(surf, dark, (rx + TILE - 4, ry, 4, TILE))
                    if is_water(gx - 1, gy) and gx > 0:
                        pygame.draw.rect(surf, dark, (rx, ry, 4, TILE))
        try:
            surf = surf.convert()
        except Exception:
            pass
        hit = {"surf": surf, "water": water_tiles}
        cache[key] = hit
        return hit

    def draw_world(self):
        area = self.world.area
        cam = self.cam
        if area.name == AREA_HOME:
            # Same iso room for both playing and decorating; Build adds a grid
            homeiso.draw_room(self, build=(self.state == "build"))
            return
        x0 = max(0, int(cam.x // TILE))
        y0 = max(0, int(cam.y // TILE))
        x1 = min(area.w, x0 + SCREEN_W // TILE + 2)
        y1 = min(area.h, y0 + SCREEN_H // TILE + 2)
        water = assets.water_frames()
        wf = int(self.anim_t * 6) % len(water)
        # static ground (tiles + detail + seasonal tint + snow + damp shores) is
        # pre-rendered once per area/season into one big surface -> one blit
        gc = self._ground_cache(area)
        fx, fy = math.floor(cam.x), math.floor(cam.y)
        self.screen.blit(gc["surf"], (-fx, -fy))
        # animated water + shoreline foam + twinkles (visible water tiles only)
        scr = self.screen
        foam_ph = int(self.anim_t * 3) % 4
        tw = int(self.anim_t * 2.5)
        for (gx, gy), mask in gc["water"].items():
            if not (x0 <= gx < x1 and y0 <= gy < y1):
                continue
            rx = gx * TILE - fx
            ry = gy * TILE - fy
            scr.blit(water[(wf + gx + gy) % len(water)], (rx, ry))
            if mask:
                scr.blit(assets.shore_foam(mask, (foam_ph + gx) % 4), (rx, ry))
            hh = (gx * 73856093) ^ (gy * 19349663)
            if (hh + tw) % 17 == 0:                          # sun glints on the water
                sx, sy = rx + 8 + hh % 30, ry + 8 + (hh >> 5) % 30
                pygame.draw.line(scr, (255, 255, 255), (sx - 3, sy), (sx + 3, sy), 1)
                pygame.draw.line(scr, (255, 255, 255), (sx, sy - 3), (sx, sy + 3), 1)
        # worked soil with furrows (dry / wet), over the cached ground
        an = area.name
        watered = self.world.watered
        dry_t, wet_t = assets.tilled_tile(False), assets.tilled_tile(True)
        for key in self.world.tilled:
            if key[0] != an:
                continue
            gx, gy = key[1], key[2]
            if not (x0 <= gx < x1 and y0 <= gy < y1):
                continue
            scr.blit(wet_t if key in watered else dry_t, (gx * TILE - fx, gy * TILE - fy))
        # TALL world objects (buildings / tall props / boulders / trees) are no
        # longer blitted here -- they're queued with a baseline key and merged
        # into draw_entities' y-sort, so an actor standing BEHIND one is
        # correctly occluded (was: actors always drew on top of everything).
        # Flat decor (height <= TILE, e.g. towels/shells) still paints here,
        # under the actors, like ground detail.
        occ = self._occ = []
        # buildings (baseline = the sprite's bottom tile row)
        for (bx, by, bw, bh, wall, roof, label) in area.buildings:
            spr = assets.building_sprite(bw * TILE, bh * TILE, wall, roof, label)
            occ.append(((by + bh) * TILE, spr,
                        (bx * TILE - cam.x, by * TILE - cam.y)))
        # interaction props (bed, shipping bin, market stall)
        for (kind, gx, gy) in getattr(area, "props", []):
            spr = assets.prop_sprite(kind)
            oy = spr.get_height() - TILE
            pos = (gx * TILE - cam.x, gy * TILE - cam.y - oy)
            if spr.get_height() > TILE:
                sw = max(20, int(spr.get_width() * 0.8))
                self.screen.blit(assets.hud.soft_shadow(sw, 12, 55),
                                 (gx * TILE - cam.x + spr.get_width() // 2 - sw // 2,
                                  gy * TILE - cam.y + TILE - 10))
                occ.append(((gy + 1) * TILE, spr, pos))
            else:
                self.screen.blit(spr, pos)
        # town quest board (pinned-papers signboard)
        if area.name == AREA_TOWN and getattr(area, "quest_board", None):
            qx, qy = area.quest_board
            bx = qx * TILE - cam.x
            by = qy * TILE - cam.y
            pygame.draw.rect(self.screen, (120, 86, 52), (bx + 19, by + 20, 8, 22))
            pygame.draw.rect(self.screen, (198, 170, 122), (bx + 3, by + 2, 42, 24), border_radius=3)
            pygame.draw.rect(self.screen, (120, 86, 52), (bx + 3, by + 2, 42, 24), 2, border_radius=3)
            pygame.draw.rect(self.screen, (248, 246, 236), (bx + 9, by + 6, 11, 13))
            pygame.draw.rect(self.screen, (246, 236, 200), (bx + 26, by + 7, 11, 12))
            pygame.draw.line(self.screen, (180, 150, 110), (bx + 11, by + 10), (bx + 18, by + 10), 1)
            pygame.draw.line(self.screen, (180, 150, 110), (bx + 11, by + 13), (bx + 18, by + 13), 1)
        # farm sprinklers (basic = grey, premium "sprinkler2" = brass, droplets
        # on the diagonals too so its 3x3 reach reads at a glance)
        if area.name == AREA_FARM:
            for (sx, sy), skind in self.world.farm_objects.items():
                if skind not in ("sprinkler", "sprinkler2"):
                    continue
                ox = sx * TILE - cam.x
                oy = sy * TILE - cam.y
                if skind == "sprinkler2":
                    body, head, rim = (168, 134, 70), (212, 178, 96), (110, 86, 40)
                else:
                    body, head, rim = (120, 130, 140), (152, 164, 174), (92, 102, 112)
                pygame.draw.rect(self.screen, body, (ox + 17, oy + 24, 14, 10), border_radius=2)
                pygame.draw.circle(self.screen, head, (ox + 24, oy + 22), 5)
                pygame.draw.circle(self.screen, rim, (ox + 24, oy + 22), 5, 1)
                if skind == "sprinkler2":
                    pygame.draw.circle(self.screen, (250, 246, 230), (ox + 24, oy + 22), 2)
                    for ddx, ddy in ((-11, -3), (11, -3), (-8, -10), (8, -10)):
                        pygame.draw.circle(self.screen, (150, 200, 235),
                                           (ox + 24 + ddx, oy + 19 + ddy), 1)
                else:
                    for ddx in (-11, 11):
                        pygame.draw.circle(self.screen, (150, 200, 235), (ox + 24 + ddx, oy + 19), 1)
        # festival plaza on the festival day -- a whole decorated town square,
        # centred on area.festival_stall (the tile where the player claims the
        # seasonal gift; see actions_system festival branch). Same source of
        # truth as the claim logic so a town redesign can't split them apart.
        if area.name == AREA_TOWN and festival.is_festival_day(self.time):
            scr = self.screen
            t = self.anim_t
            fgx, fgy = getattr(area, "festival_stall", None) or (20, 12)
            cx = fgx * TILE - cam.x         # left edge of the reward-stall tile
            gy = fgy * TILE - cam.y         # counter line of the stall row
            PAL = [(240, 92, 92), (245, 205, 90), (118, 205, 142),
                   (120, 182, 245), (200, 132, 230)]
            dk = lambda c, f=0.7: (int(c[0] * f), int(c[1] * f), int(c[2] * f))

            def _stall(x, awn):
                w = TILE + 8
                pygame.draw.rect(scr, (118, 84, 56), (x - 2, gy - 20, 4, 24))        # posts
                pygame.draw.rect(scr, (118, 84, 56), (x + w - 6, gy - 20, 4, 24))
                pygame.draw.rect(scr, (165, 120, 78), (x - 4, gy - 2, w + 4, 12), border_radius=3)
                pygame.draw.rect(scr, (132, 94, 60), (x - 4, gy - 2, w + 4, 12), 1, border_radius=3)
                for i, gc in enumerate([(230, 120, 120), (245, 210, 120), (150, 205, 160)]):
                    pygame.draw.circle(scr, gc, (x + 8 + i * 14, gy + 2), 3)         # goods
                for i in range(0, w, 10):                                            # striped canopy
                    c = awn if (i // 10) % 2 == 0 else (246, 246, 246)
                    pygame.draw.rect(scr, c, (x - 4 + i, gy - 32, 10, 14))
                    pygame.draw.polygon(scr, c, [(x - 4 + i, gy - 18),               # scalloped hem
                                                 (x - 4 + i + 10, gy - 18),
                                                 (x - 4 + i + 5, gy - 12)])

            def _bunting(x1, y1, x2, y2, n, phase):
                pts = []
                for k in range(n + 1):
                    u = k / n
                    sag = math.sin(math.pi * u) * abs(x2 - x1) * 0.14
                    pts.append((x1 + (x2 - x1) * u, y1 + (y2 - y1) * u + sag))
                pygame.draw.lines(scr, (92, 72, 56), False,
                                  [(int(px), int(py)) for px, py in pts], 1)
                for k in range(n):
                    mx = (pts[k][0] + pts[k + 1][0]) / 2
                    my = (pts[k][1] + pts[k + 1][1]) / 2
                    c = PAL[(k + phase) % len(PAL)]
                    sway = math.sin(t * 2 + k * 0.6) * 1.5
                    pygame.draw.polygon(scr, c, [(mx - 5, my), (mx + 5, my), (mx + sway, my + 9)])

            # flag poles flanking the square, with waving pennants
            for side in (-1, 1):
                px = cx + side * 3 * TILE + (TILE if side > 0 else 0)
                pygame.draw.rect(scr, (150, 120, 90), (px - 1, gy - 70, 3, 74))
                pygame.draw.circle(scr, (245, 210, 90), (px, gy - 71), 3)
                wav = int(math.sin(t * 3 + side) * 4)
                tip = px - side * (18 + wav)
                pygame.draw.polygon(scr, (240, 92, 92),
                                    [(px, gy - 70), (px, gy - 62), (tip, gy - 66)])

            # two tiers of bunting strung across the plaza
            lx, rx = cx - 3 * TILE, cx + 3 * TILE + TILE
            _bunting(lx, gy - 68, cx + TILE // 2, gy - 74, 6, 0)
            _bunting(cx + TILE // 2, gy - 74, rx, gy - 68, 6, 3)
            _bunting(cx - 2 * TILE, gy - 50, cx + 2 * TILE + TILE, gy - 50, 8, 1)

            # paper lanterns bobbing over the square
            for i in range(-2, 3):
                lxp = cx + TILE // 2 + i * TILE
                by = gy - 56 + int(math.sin(t * 1.5 + i) * 4)
                lc = PAL[(i + 2) % len(PAL)]
                pygame.draw.line(scr, (120, 100, 70), (lxp, by - 9), (lxp, by - 6), 1)
                pygame.draw.ellipse(scr, lc, (lxp - 5, by - 6, 10, 14))
                pygame.draw.ellipse(scr, dk(lc, 0.8), (lxp - 5, by - 6, 10, 14), 1)
                pygame.draw.line(scr, (245, 210, 90), (lxp, by + 8), (lxp, by + 11), 1)

            # three stalls: the centre one is the reward stall on grid (20, 12)
            _stall(cx - 2 * TILE, (230, 80, 80))
            _stall(cx, (90, 150, 235))
            _stall(cx + 2 * TILE, (110, 195, 140))

            # banner with the festival's name above the centre stall
            title = festival.name(self.time.season)
            lab = self.ui.small.render(title, True, (74, 42, 24))
            bw = lab.get_width() + 18
            bx = cx + TILE // 2 - bw // 2
            byy = gy - 46
            pygame.draw.rect(scr, (250, 238, 210), (bx, byy, bw, 18), border_radius=3)
            pygame.draw.rect(scr, (190, 150, 95), (bx, byy, bw, 18), 2, border_radius=3)
            scr.blit(lab, (bx + 9, byy + 2))

            # confetti drifting through the square (deterministic loop, no flicker)
            span = 6 * TILE
            for i in range(36):
                xpos = cx - 3 * TILE + (i * 113 + 17) % span
                ypos = gy - 70 + (t * 26 + i * 71) % (5 * TILE)
                c = PAL[i % len(PAL)]
                if i % 3 == 0:
                    pygame.draw.circle(scr, c, (int(xpos), int(ypos)), 2)
                else:
                    pygame.draw.rect(scr, c, (int(xpos), int(ypos), 3, 3))
        # directional signposts at the map exits (labels derive from area names)
        seen_sign = {}
        for wp in area.warps:
            seen_sign.setdefault(wp["to"], (wp["gx"], wp["gy"]))
        for to, (gx, gy) in seen_sign.items():
            sx, sy = gx, gy
            if gy <= 0:
                sy = gy + 1
            elif gy >= area.h - 1:
                sy = gy - 1
            if gx <= 0:
                sx = gx + 1
            elif gx >= area.w - 1:
                sx = gx - 1
            px = sx * TILE - cam.x
            py = sy * TILE - cam.y
            self.screen.blit(assets.signpost_sprite(), (px, py))
            lab = self.ui.tiny.render(to.upper(), True, (40, 28, 18))
            self.screen.blit(lab, (px + TILE // 2 - lab.get_width() // 2, py + 13))
        # crops
        for (an, gx, gy), crop in self.world.crops.items():
            if an != area.name:
                continue
            rx = gx * TILE - cam.x
            ry = gy * TILE - cam.y
            if not (-TILE <= rx <= SCREEN_W and -TILE <= ry <= SCREEN_H):
                continue
            r = crop.growth_ratio()
            ccol = tuple(crop.data.get("color", (150, 180, 90)))
            ready = crop.ready_to_harvest
            dead = bool(getattr(crop, "dead", False))
            stage = 3 if ready else (0 if r < 0.25 else (1 if r < 0.6 else 2))
            sway = int(math.sin(self.anim_t * 2 + gx * 0.7) * (1 + r * 2))
            self.screen.blit(assets.crop_sprite(stage, ccol, dead), (rx + (0 if dead else sway), ry))
            if ready and not dead:
                # the real produce icon pops out of the foliage, bobbing gently
                icache = self.__dict__.setdefault("_crop_icon_cache", {})
                ic = icache.get(crop.name)
                if ic is None:
                    try:
                        ic = pygame.transform.scale(assets.item_icon(crop.name), (24, 24))
                    except Exception:
                        ic = pygame.Surface((1, 1), pygame.SRCALPHA)
                    icache[crop.name] = ic
                bob = int(math.sin(self.anim_t * 3 + gx + gy) * 2)
                self.screen.blit(ic, (rx + TILE // 2 - 12 + sway, ry + TILE - 42 + bob))
                if int(self.anim_t * 2 + gx * 3 + gy) % 7 == 0:          # ready twinkle
                    tx, ty = rx + TILE // 2 + 10 + sway, ry + 8 + bob
                    pygame.draw.line(self.screen, (255, 252, 230), (tx - 3, ty), (tx + 3, ty), 1)
                    pygame.draw.line(self.screen, (255, 252, 230), (tx, ty - 3), (tx, ty + 3), 1)
        # rocks (tinted by mine biome so boulders match the floor) -- queued as
        # occluders so an actor walking just behind a boulder tucks behind it
        biome = getattr(area, "biome", None)
        style = (getattr(_world_mod, "BIOME_STYLE", None) or {}).get(biome)
        rtint = style.get("rock_tint") if style else _BIOME_ROCK_TINT.get(biome)
        rtint = tuple(rtint) if rtint else None
        rshadow = assets.hud.soft_shadow(40, 12, 60)
        for (gx, gy), ore in area.rocks.items():
            scr.blit(rshadow, (gx * TILE - cam.x + 4, gy * TILE - cam.y + TILE - 12))
            occ.append(((gy + 1) * TILE, assets.rock_sprite(ore, rtint),
                        (gx * TILE - cam.x, gy * TILE - cam.y)))
        # trees — gentle wind sway; queued as occluders. sorted() keeps the
        # append order stable so same-row canopies never flicker after the
        # tree set mutates (chop / regrow).
        outdoor = area.name not in (AREA_MINE, AREA_HOME, AREA_COOP)
        tframes = assets.tree_frames(self.time.season if outdoor else None)
        tshadow = assets.hud.soft_shadow(46, 14, 70)
        for (gx, gy) in sorted(area.trees, key=lambda t: (t[1], t[0])):
            if x0 - 1 <= gx <= x1 and y0 - 1 <= gy <= y1 + 1:
                scr.blit(tshadow, (gx * TILE - cam.x + 1, gy * TILE - cam.y + TILE - 10))
            ti = int(self.anim_t * 2 + gx * 0.5 + gy * 0.3) % len(tframes)
            occ.append(((gy + 1) * TILE, tframes[ti],
                        (gx * TILE - cam.x, (gy - 1) * TILE - cam.y)))
        # mine ladder
        if area.name == AREA_MINE and area.ladder:
            lx, ly = area.ladder
            pygame.draw.rect(self.screen, (60, 45, 30),
                             (lx * TILE - cam.x + 8, ly * TILE - cam.y + 4, TILE - 16, TILE - 8))
            for i in range(3):
                yy = ly * TILE - cam.y + 10 + i * 10
                pygame.draw.line(self.screen, (180, 150, 100),
                                 (lx * TILE - cam.x + 10, yy), (lx * TILE - cam.x + TILE - 10, yy), 3)

    def draw_entities(self):
        cam = self.cam
        # ambient beach crabs: Core spawns + moves these in self.beach_critters
        # (empty off the beach). Drawn under the actors so players/NPCs pass in
        # front; the sprite mirrors with the crab's facing. Purely decorative.
        for c in getattr(self, "beach_critters", ()):
            spr = assets.crab(facing=c["dir"])
            self.screen.blit(spr, (int(c["x"] - TILE / 2 - cam.x),
                                   int(c["y"] - TILE / 2 - cam.y)))
        drawables = self.players + self.npcs + self.monsters
        if self.world.current == AREA_COOP:
            drawables = drawables + self.animals
        # one shared y-sort for actors AND tall world objects (queued by
        # draw_world in self._occ): whoever's baseline is lower on screen
        # paints later. Actor key o.y + 10 = their sprite's visual feet, so
        # standing one row behind a tree/building/boulder tucks you behind it.
        items = [(o.y + 10, None, o) for o in drawables]
        items += getattr(self, "_occ", ())
        # domain y-sorted world objects (decor, machines, forage, critters...):
        # each _world_sprites_* hook returns a list of
        #   (baseline_world_y, surface, (screen_x, screen_y))   -> blitted, or
        #   (baseline_world_y, None, obj)  with obj.draw(screen, cam)
        for n in self._hook_names("_world_sprites_"):
            items += self._call_hook(n) or ()
        for key, spr, obj in sorted(items, key=lambda e: e[0]):
            if spr is None:
                obj.draw(self.screen, cam)
            else:
                self.screen.blit(spr, obj)
        # fishing bobber + reel indicator
        for idx, p in enumerate(self.players):
            st = self.fishing[idx]
            if st.state in ("casting", "bite", "reeling"):
                bx = int(p.x + p.fx * TILE - cam.x)
                by = int(p.y + p.fy * TILE - cam.y)
                tcol = fishing.TIER_COLOR.get(st.tier, (240, 240, 240)) if st.fish else (240, 240, 240)
                if st.state == "casting":
                    c = (240, 240, 240)
                elif st.state == "bite":
                    c = tcol if st.fish and fishing.is_special(st.fish) else (240, 80, 60)
                else:
                    c = tcol
                if getattr(st, "hotspot", False):
                    # cast into a bubbling hotspot: a soft pulsing gold halo
                    pr = 9 + int((math.sin(self.anim_t * 5) + 1) * 1.5)
                    pygame.draw.circle(self.screen, (255, 214, 110), (bx, by), pr, 2)
                pygame.draw.circle(self.screen, c, (bx, by), 6)
                # reel progress pips above the bobber while mashing
                if st.state == "reeling" and st.reel_needed > 1:
                    total = st.reel_needed
                    pw = 7
                    x0 = bx - (total * pw) // 2
                    for i in range(total):
                        col = tcol if i < st.reel_done else (70, 70, 80)
                        pygame.draw.rect(self.screen, col, (x0 + i * pw, by - 16, pw - 2, 5),
                                         border_radius=1)

    def _interactables(self):
        area = self.world.area
        out = []
        if area.shop:
            out.append((area.shop[0], area.shop[1], "shop"))
        if area.bed:
            out.append((area.bed[0], area.bed[1], "bed"))
        if area.name == AREA_MINE and area.ladder:
            out.append((area.ladder[0], area.ladder[1], "ladder"))
        if area.name == AREA_TOWN and getattr(area, "quest_board", None):
            out.append((area.quest_board[0], area.quest_board[1], "quest"))
        for n in self.npcs:
            out.append((n.x / TILE, n.y / TILE, "talk"))
        return out

    def _prompt_extras(self):
        """Draw-only prompt bubbles (NOT in _interactables, whose kinds Core's
        ambient sparkle maps by name): the meadow rest spots handled by World
        (the tree + lookout draw their own bubbles, Story sparkles the board)."""
        area = self.world.area
        out = []
        for attr in ("swing", "bench"):
            spot = getattr(area, attr, None)
            if spot:
                out.append((spot[0], spot[1], attr))
        return out

    def draw_prompts(self):
        cam = self.cam
        info = {"shop": ("$", (240, 205, 80)), "bed": ("Z", (150, 200, 235)),
                "ladder": ("v", (240, 150, 60)), "talk": ("!", (235, 170, 200)),
                "quest": ("?", (130, 195, 235)), "swing": ("~", (170, 226, 150)),
                "bench": ("+", (246, 170, 200))}
        near_only = ("swing", "bench")
        hud_top = [pygame.Rect(0, 0, 232, 204), pygame.Rect(404, 0, 472, 106),
                   pygame.Rect(SCREEN_W - 298, 0, 298, 118)]
        # kept apart from hud_reserve (a bubble must not dodge its own last
        # frame); floating texts avoid these via _popup_avoid_rects
        prompt_rects = self._prompt_rects_last = []
        for gx, gy, kind in self._interactables() + self._prompt_extras():
            if kind not in info:
                continue
            wx = gx * TILE + TILE / 2
            wy = gy * TILE + TILE / 2
            bestd, near = 1e9, 0
            for i, p in enumerate(self.players):
                d = abs(p.x - wx) + abs(p.y - wy)
                if d < bestd:
                    bestd, near = d, i
            if kind in near_only and bestd > TILE * 3:
                continue
            sx = int(wx - cam.x)
            sy = int(wy - cam.y)
            emote, col = info[kind]
            bob = int(math.sin(self.anim_t * 3 + gx) * 3)
            by = sy - int(TILE * 0.95) + bob
            r = 13
            show_key = bestd < TILE * 1.7
            # bubble (+ key pill) above the object; when that spot is under the
            # top HUD cards / off-screen / on a reserved prompt, hang it below
            span = pygame.Rect(sx - 26, by - r, 52, r * 2 + (30 if show_key else 0))
            blockers = hud_top + self.hud_reserved()
            if span.top < 0 or any(span.colliderect(b) for b in blockers):
                by = sy + int(TILE * 0.95) + bob
                span.y = by - r
            sx = max(30, min(SCREEN_W - 30, sx))
            prompt_rects.append(span)
            from .. import ui_kit
            # cream bubble with a wooden rim (matches the key pill under it)
            pygame.draw.circle(self.screen, (40, 20, 30), (sx + 1, by + 2), r)
            pygame.draw.circle(self.screen, ui_kit.WOOD, (sx, by), r)
            pygame.draw.circle(self.screen, ui_kit.CREAM, (sx, by), r - 2)
            ui_kit.blit_text(self.screen, ui_kit.font(14, True), emote,
                             tuple(int(c * 0.62) for c in col[:3]), (sx, by))
            if show_key:
                keys = P1_KEYS if near == 0 else P2_KEYS
                key = key_label(keys["action"])       # follows rebinding
                # the one world-prompt style (ui_kit.key_pill), key only
                ui_kit.key_pill(self.screen, key, None, (sx, by + r + 14),
                                accent=ui_kit.P_COL[near % 2], fnt=ui_kit.font(12, True))

    def _draw_weather(self):
        if self.world.current not in _WEATHER_AREAS:
            return
        scr = self.screen
        at = self.anim_t
        if self.weather == weather.RAIN:
            # two depth layers of slanted streaks -> denser, with a sense of depth
            for cnt, spd, length, col, wd in ((58, 720, 13, (148, 178, 220), 1),
                                              (38, 1120, 20, (188, 208, 238), 2)):
                t = int(at * spd)
                for i in range(cnt):
                    x = (i * 53 + t) % (SCREEN_W + 40) - 20
                    y = (i * 37 + t) % SCREEN_H
                    pygame.draw.line(scr, col, (x, y), (x - 5, y + length), wd)
        elif self.weather == weather.SNOW:
            # two layers: far small fast flakes + near big slow drifting flakes
            for cnt, spd, swing, base_r, col in ((80, 64, 12, 2, (236, 242, 250)),
                                                 (46, 38, 22, 3, (255, 255, 255))):
                for i in range(cnt):
                    sway = math.sin(at * 1.2 + i * 1.7) * swing
                    x = (i * 53 + sway) % SCREEN_W
                    y = (i * 47 + int(at * spd)) % SCREEN_H
                    pygame.draw.circle(scr, col, (int(x), int(y)), base_r + (i % 2))

    def _ambient_fx(self, dt):
        """Spawn small living-world particles: chimney smoke, temple candle flames,
        lava-depths embers, and bubbles when a fish bites. Throttled."""
        self._fx_acc = getattr(self, "_fx_acc", 0.0) + dt
        cur = self.world.current
        # warp burst when we land in a new area (edge-triggered)
        la = getattr(self, "_fx_last_area", None)
        if la is not None and la != cur:
            for p in self.players:
                self.parts.warp(p.x, p.y)
        self._fx_last_area = cur
        # fishing bite bubbles are edge-triggered -> check every frame (cheap)
        fp = getattr(self, "_fish_prev", None)
        if fp is None:
            fp = self._fish_prev = {0: "", 1: ""}
        for idx, st in self.fishing.items():
            s = getattr(st, "state", "")
            if s == "bite" and fp.get(idx) != "bite":
                p = self.players[idx]
                # at the bobber (matches the drawn bobber + the cast splash)
                self.parts.bubble(p.x + p.fx * TILE, p.y + p.fy * TILE, n=7)
            fp[idx] = s
        if self._fx_acc < 0.10:
            return
        self._fx_acc = 0.0
        area = self.world.area
        cam = self.cam
        # ripples on the water while a line is out
        for idx, st in self.fishing.items():
            if getattr(st, "state", "") in ("casting", "bite", "reeling"):
                p = self.players[idx]
                # ripples centred on the bobber (p.x+fx*TILE), not the tile centre
                self.parts.ripple(p.x + p.fx * TILE, p.y + p.fy * TILE, n=1)
        if cur in (AREA_FARM, AREA_TOWN):
            for (bx, by, bw, bh, wall, roof, label) in getattr(area, "buildings", []):
                if (label or "").strip().lower() in ("home", "house", ""):
                    self.parts.smoke((bx + bw * 0.72) * TILE, by * TILE + 6, n=1)
            if cur == AREA_TOWN and festival.is_festival_day(self.time):
                for _ in range(3):                       # festival confetti from above
                    self.parts.confetti(cam.x + random.uniform(0, SCREEN_W), cam.y - 12, n=2)
        elif cur == AREA_TEMPLE:
            for (kind, gx, gy) in getattr(area, "props", []):
                if kind in ("candle", "incense"):
                    self.parts.flame(gx * TILE + TILE / 2, gy * TILE + TILE * 0.45, n=1)
        elif cur == AREA_MINE:
            biome = getattr(area, "biome", None)
            style = (getattr(_world_mod, "BIOME_STYLE", None) or {}).get(biome) or {}
            amb = style.get("ambient")
            rx = lambda: cam.x + random.uniform(0, SCREEN_W)
            ry = lambda: cam.y + random.uniform(0, SCREEN_H)
            if amb == "void":                            # drifting violet motes
                self.parts.sparkle(rx(), ry(), n=1, color=(150, 110, 220))
                if random.random() < 0.5:
                    self.parts.bubble(rx(), ry(), n=1, color=(96, 70, 150))
            elif amb == "ruin":                          # sandy dust + old gold glints
                self.parts.dust(rx(), ry(), n=1, color=(196, 176, 136))
                if random.random() < 0.3:
                    self.parts.sparkle(rx(), ry(), n=1, color=(236, 206, 120))
            elif amb == "dust" and random.random() < 0.5:
                self.parts.dust(rx(), ry(), n=1, color=(150, 140, 130))
            if biome == "lava":
                for _ in range(2):
                    self.parts.ember(cam.x + random.uniform(0, SCREEN_W),
                                     cam.y + random.uniform(0, SCREEN_H), n=1)
            elif biome == "ice":
                for _ in range(2):                       # pale frost glints
                    self.parts.sparkle(cam.x + random.uniform(0, SCREEN_W),
                                       cam.y + random.uniform(0, SCREEN_H),
                                       n=1, color=(206, 230, 246))
            elif biome == "crystal":                     # faint crystal shimmer
                self.parts.sparkle(cam.x + random.uniform(0, SCREEN_W),
                                   cam.y + random.uniform(0, SCREEN_H),
                                   n=1, color=(214, 190, 246))

    def _draw_hurt_flash(self):
        if self.hurt_flash <= 0:
            return
        a = int(min(120, self.hurt_flash * 200))
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((220, 60, 60, 0))
        pygame.draw.rect(ov, (220, 60, 60, a), ov.get_rect(), 60)
        self.screen.blit(ov, (0, 0))

    # ---- HUD occlusion: never hide a farmer under a HUD strip ----
    def _player_screen_rects(self):
        """Screen rects of both farmers' sprites (empty in the iso home, where
        world x/y are not screen-projected)."""
        if self.world.current == AREA_HOME:
            return []
        cam = self.cam
        return [pygame.Rect(int(p.x - cam.x) - 22, int(p.y - cam.y) - 40, 44, 56)
                for p in self.players]

    def _hud_faded(self, rect, alpha, draw_fn):
        """Run ``draw_fn(surface)`` (which draws in screen coordinates inside
        ``rect``) on a reusable transparent layer, then blit that region onto
        the screen at ``alpha`` -- lets a HUD strip go see-through while a
        farmer walks behind it."""
        layer = self.__dict__.get("_hud_layer")
        if layer is None:
            layer = self._hud_layer = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        rect = pygame.Rect(rect).clip(layer.get_rect())
        layer.fill((0, 0, 0, 0), rect)
        prev = layer.get_clip()
        layer.set_clip(rect)
        try:
            draw_fn(layer)
        finally:
            layer.set_clip(prev)
        layer.set_alpha(alpha)
        self.screen.blit(layer, rect.topleft, rect)
        layer.set_alpha(255)      # NOT None: that drops SRCALPHA blending on pygame-ce

    def draw_hud(self):
        # custom overlay states (decor mode, journal...) show the real gold at
        # once so the clock card never disagrees with the overlay's own readout
        self.ui.draw_top(self.screen, self.time, self.gold, getattr(self, "weather", None),
                         tomorrow=getattr(self, "weather_tomorrow", None),
                         snap=self.state not in ("play", "shop", "sleep"))
        prs = self._player_screen_rects()
        self._hud_player_rects = prs
        # hotbar strips (top centre): see-through while a farmer is under them
        hb = pygame.Rect(SCREEN_W // 2 - 280, 0, 560, 104)
        if any(hb.colliderect(r) for r in prs):
            self._hud_faded(hb, 90, lambda s: (self.ui.draw_hotbar(s, self.players[0], 0),
                                               self.ui.draw_hotbar(s, self.players[1], 1)))
        else:
            self.ui.draw_hotbar(self.screen, self.players[0], 0)
            self.ui.draw_hotbar(self.screen, self.players[1], 1)
        # player panels (bottom corners) + the fortune/buff row above them
        for side in (0, 1):
            pr = pygame.Rect(0 if side == 0 else SCREEN_W - 272, SCREEN_H - 128, 272, 128)
            if any(pr.colliderect(r) for r in prs):
                self._hud_faded(pr, 110, lambda s, side=side:
                                self.ui.draw_player_panel(s, self.players[side], side))
            else:
                self.ui.draw_player_panel(self.screen, self.players[side], side)
        # area name -- derived from the area id itself (new areas show up free);
        # the mine appends its current depth. Shown as the minimap header (the
        # bottom-centre strip now belongs to the message feed).
        cur = self.world.current
        label = f"MINE  LV.{self.world.mine_level}" if cur == AREA_MINE else cur.upper()
        mm = pygame.Rect(0, 0, 228, 202)            # minimap card (top-left)
        if any(mm.colliderect(r) for r in prs):
            self._hud_faded(mm, 110, lambda s: self.ui.draw_minimap(
                s, self.world.area, self.players, self.npcs, label))
        else:
            self.ui.draw_minimap(self.screen, self.world.area, self.players, self.npcs, label)
        if self.world.current == AREA_HOME and self.state == "play":
            self._draw_build_banner()
        if self.fishing_banner:
            self._draw_fishing_banner()
        offs = self._draw_fortune_badges()
        for idx in (0, 1):
            self.ui.draw_buffs(self.screen, self.players[idx], idx, offs.get(idx, 0))
        self._draw_sync_pip()
        self.ui.draw_messages(self.screen, avoid=prs)

    def _draw_transition(self):
        """Warp transition: a soft iris that opens on the two farmers (Core
        drives ``self.fade`` 1 -> 0 after every warp)."""
        f = max(0.0, min(1.0, self.fade))
        cache = self.__dict__.setdefault("_iris_cache", {})
        ov = cache.get("ov")
        if ov is None:
            ov = cache["ov"] = pygame.Surface((SCREEN_W, SCREEN_H))
            ov.set_colorkey((255, 0, 255))
        # focus: midpoint of the players on screen (clamped inside the view)
        ps = self.players
        mx = sum(p.x for p in ps) / len(ps) - self.cam.x
        my = sum(p.y for p in ps) / len(ps) - self.cam.y
        mx = max(80, min(SCREEN_W - 80, mx))
        my = max(80, min(SCREEN_H - 80, my))
        t = 1.0 - f
        ease = t * t * (3 - 2 * t)
        maxr = math.hypot(SCREEN_W, SCREEN_H)
        r = int(24 + ease * maxr)
        ov.fill((26, 18, 34))
        pygame.draw.circle(ov, (255, 0, 255), (int(mx), int(my)), r)
        # warm rim light around the opening iris -- drawn INTO the veil so it
        # fades out with it (drawn on the screen it left stray gold arcs in the
        # corners after the veil had gone)
        if r < maxr:
            pygame.draw.circle(ov, (255, 214, 150), (int(mx), int(my)), r, 3)
        ov.set_alpha(int(255 * min(1.0, f * 1.6)))
        self.screen.blit(ov, (0, 0))

    def _draw_fortune_badges(self):
        """Small daily-fortune pill per player (lucky = gold, unlucky = violet),
        on the row just above each player's panel. Returns {idx: width used}
        so the buff chips line up after it."""
        style = {"lucky": ((250, 222, 120), (70, 56, 24), "LUCKY"),
                 "unlucky": ((196, 150, 224), (52, 36, 64), "UNLUCKY")}
        used = {}
        for idx in (0, 1):
            fort = (getattr(self, "fortune", None) or {}).get(idx)
            if fort not in style:
                continue
            fg, bg, label = style[fort]
            txt = self.ui.small.render(label, True, fg)
            w = txt.get_width() + 34
            x = 8 if idx == 0 else SCREEN_W - w - 8
            y = SCREEN_H - 94 - 30
            pill = pygame.Surface((w, 26), pygame.SRCALPHA)
            pygame.draw.rect(pill, (*bg, 228), (0, 0, w, 26), border_radius=9)
            pygame.draw.rect(pill, fg, (0, 0, w, 26), 1, border_radius=9)
            # four-point sparkle (lucky) / little moon (unlucky)
            cx, cy = 13, 13
            if fort == "lucky":
                pygame.draw.polygon(pill, fg, [(cx, cy - 7), (cx + 2, cy - 2), (cx + 7, cy),
                                               (cx + 2, cy + 2), (cx, cy + 7), (cx - 2, cy + 2),
                                               (cx - 7, cy), (cx - 2, cy - 2)])
            else:
                pygame.draw.circle(pill, fg, (cx, cy), 6)
                pygame.draw.circle(pill, (*bg, 255), (cx + 3, cy - 2), 5)
            pill.blit(txt, (24, 13 - txt.get_height() // 2))
            self.screen.blit(pill, (x, y))
            used[idx] = w + 6
        return used

    def _draw_sync_pip(self):
        """Small centred 'In Sync' heart chip shown while both farmers are close
        (see SocialMixin.update_coop_bond). Pure visual feedback for the bond."""
        if not getattr(self, "in_sync", False) or self.state != "play":
            return                  # never peeking out from behind a dialogue box
        from .. import ui_kit
        label = self.ui.small.render("In Sync", True, (255, 226, 234))
        pad = 12
        w = 18 + label.get_width() + pad * 2
        h = 24
        x = SCREEN_W // 2 - w // 2
        y = 136 if self.world.current == AREA_HOME else 102    # below both hotbars
        # a farmer standing right under the pill (e.g. the Town / Forest arrival
        # at the top edge): tuck it just above the bottom feed instead, or hide it
        # a farmer standing right under the pill (e.g. the Town / Forest
        # arrival at the top edge): hide it for now rather than jumping it to
        # the middle of the field, where it read like a stray world label
        prs = getattr(self, "_hud_player_rects", None) or []
        if any(pygame.Rect(x, y, w, h).colliderect(r) for r in prs):
            return
        self.hud_reserve(pygame.Rect(x, y, w, h))
        pulse = (math.sin(self.anim_t * 4) + 1) * 0.5
        # fill and outline share one radius (the square fill used to poke out)
        ui_kit.pill(self.screen, (x, y, w, h), (70, 30, 46), (255, 150, 180), alpha=210)
        hx = x + pad + 5
        hy = y + h // 2 - 3            # heart's visual centre is below its lobes
        r = 4 + int(pulse * 1.5)
        col = (255, 120, 150)
        pygame.draw.circle(self.screen, col, (hx - 3, hy - 1), r)
        pygame.draw.circle(self.screen, col, (hx + 3, hy - 1), r)
        pygame.draw.polygon(self.screen, col,
                            [(hx - r - 2, hy), (hx + r + 2, hy), (hx, hy + r + 4)])
        ui_kit.blit_text(self.screen, self.ui.small, "In Sync", (255, 226, 234),
                         (hx + 11, y + h // 2), align="left")

    def _draw_fishing_banner(self):
        txt, col, t = self.fishing_banner
        pulse = (math.sin(self.anim_t * 6) + 1) * 0.5
        big = self.ui.bigfont if hasattr(self.ui, "bigfont") else self.ui.font
        label = big.render(txt, True, col)
        w = label.get_width() + 48
        h = label.get_height() + 22
        x = SCREEN_W // 2 - w // 2
        # at home the "Press B" build banner owns y=102..140 -- drop below it
        y = 180 if self.world.current == AREA_HOME else 132
        from .. import ui_kit
        ui_kit.pill(self.screen, (x, y, w, h), (18, 14, 24), col, radius=10, alpha=215)
        if pulse > 0.5:                                    # pulsing inner glow line
            pygame.draw.rect(self.screen, col, (x + 3, y + 3, w - 6, h - 6), 1, border_radius=8)
        ui_kit.blit_text(self.screen, big, txt, col, (SCREEN_W // 2, y + h // 2))
        self.hud_reserve(pygame.Rect(x, y, w, h))

    def _draw_build_banner(self):
        # thin bar in the gap between the hotbars and the room top
        pulse = (math.sin(self.anim_t * 4) + 1) * 0.5
        try:
            from ..settings import BUILD_KEY
        except Exception:
            BUILD_KEY = pygame.K_b
        from .. import ui_kit
        # the one world-prompt style: [B] Decorate - Furniture Shop
        r = ui_kit.key_pill(self.screen, key_label(BUILD_KEY), "Decorate  -  Furniture Shop",
                            (SCREEN_W // 2, 117 + int(pulse * 1.5)), fnt=ui_kit.font(15, True))
        self.hud_reserve(r)
