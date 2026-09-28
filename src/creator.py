"""Character creator: name + look (skin / hairstyle / hair colour / shirt) for P1 & P2."""
import math
import pygame
from .settings import SCREEN_W, SCREEN_H
from . import assets, ui_kit

ACCENT = (96, 206, 130)
PANELS = [70, 740]
PANEL_W = 470
PANEL_Y = 104               # parchment card top (tightened to fit its rows)
PANEL_H = 446
FIELDS = [("skin", "Skin"), ("hair_style", "Hairstyle"),
          ("hair_color", "Hair Colour"), ("shirt_color", "Shirt")]
# the title menu's cosy palette (menu.py buttons: parchment face + wooden rim)
WOOD = (138, 94, 64)
WOOD_DK = (104, 68, 46)
CREAM = (250, 238, 212)
CREAM_HI = (255, 250, 238)
INK = (74, 44, 36)
INK_SOFT = (128, 92, 70)
SPROUT = (92, 150, 70)
P_COL = [(206, 92, 80), (78, 118, 200)]
DEFAULT_NAMES = ("Player 1", "Player 2")
NAME_MAX = 12
# keyboard cursor: rows 0 (name) .. 4 (looks) in each panel, then the shared START
ROW_NAME, ROW_START = 0, len(FIELDS) + 1
_NAV_ORDER = ([(0, r) for r in range(ROW_START)] + [(1, r) for r in range(ROW_START)]
              + [(None, ROW_START)])
_K_UP = (pygame.K_UP, pygame.K_w)
_K_DOWN = (pygame.K_DOWN, pygame.K_s)
_K_LEFT = (pygame.K_LEFT, pygame.K_a)
_K_RIGHT = (pygame.K_RIGHT, pygame.K_d)
_K_OK = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
FOOTER_HINT = ("Arrows/WASD: move  -  Left/Right: change look  -  Enter: edit name / START"
               "  -  Esc: back  (or use the mouse)")


def name_char_ok(ch):
    """Only characters the UI font can draw everywhere a name shows up (HUD,
    farm sign, logs): plain printable ASCII. Thai and other scripts render as
    tofu boxes, so they are refused."""
    return bool(ch) and len(ch) == 1 and ch.isascii() and ch.isprintable()


class CharacterCreator:
    def __init__(self, game):
        self.g = game
        self.looks = [dict(game.look[0]), dict(game.look[1])]
        self.focus = None        # which player's name box is being typed (0/1/None)
        self.cur = (0, ROW_NAME)  # keyboard highlight: (panel, row); panel None = START
        self._last_pi = 0
        self._before = ["", ""]  # a box's name when it was focused (restored if left empty)
        self._warn_t = 0.0       # 'English letters only' note under a name box
        self._warn_pi = 0
        self.t = 0.0
        self._t0 = 0.0           # the title scene's clock when the creator opened
        self._last_t = None
        self.font = game.ui.font
        self.big = game.ui.big
        self.small = game.ui.small
        self.tiny = game.ui.tiny

    def load(self, looks):
        self.looks = [dict(looks[0]), dict(looks[1])]
        for i, L in enumerate(self.looks):
            L.setdefault("name", DEFAULT_NAMES[i])
            for f, _ in FIELDS:
                L.setdefault(f, 0)
        self.focus = None
        self.cur = (0, ROW_NAME)
        self._last_pi = 0
        self._before = ["", ""]
        self._warn_t = 0.0
        self.t = 0.0
        self._t0 = float(getattr(getattr(self.g, "menu", None), "t", 0.0) or 0.0)
        self._last_t = None

    # ---- layout ----
    def _name_rect(self, pi):
        return pygame.Rect(PANELS[pi] + 110, PANEL_Y + 214, PANEL_W - 140, 36)

    def _field_rows(self, pi):
        px = PANELS[pi]
        out = []
        for i, (f, label) in enumerate(FIELDS):
            y = PANEL_Y + 268 + i * 44
            left = pygame.Rect(px + 200, y, 32, 32)
            right = pygame.Rect(px + PANEL_W - 64, y, 32, 32)
            out.append((f, label, y, left, right))
        return out

    def _start_rect(self):
        return pygame.Rect(SCREEN_W // 2 - 110, PANEL_Y + PANEL_H + 30, 220, 58)

    def _back_rect(self):
        return pygame.Rect(PANELS[0], PANEL_Y + PANEL_H + 36, 136, 46)

    def _count(self, f):
        return {"skin": len(assets.SKIN_TONES), "hair_style": len(assets.HAIR_STYLES),
                "hair_color": len(assets.HAIR_COLORS), "shirt_color": len(assets.SHIRT_COLORS)}[f]

    def _cycle(self, pi, f, d):
        self.looks[pi][f] = (self.looks[pi].get(f, 0) + d) % self._count(f)
        self.g.audio.play("ui_move")

    # ---- names ----
    def _focus_name(self, pi):
        """Start typing into player ``pi``'s name box."""
        if self.focus is not None and self.focus != pi:
            self._unfocus()
        self.focus = pi
        self.cur = (pi, ROW_NAME)
        self._last_pi = pi
        name = self.looks[pi].get("name", "")
        self._before[pi] = name
        # clear a still-default name so typing starts fresh
        if name in DEFAULT_NAMES + ("Farmer", ""):
            self.looks[pi]["name"] = ""
        self.g.audio.play("ui_move")

    def _unfocus(self):
        """Leave the name box; an emptied box gets its old name back."""
        pi = self.focus
        self.focus = None
        if pi is None:
            return
        L = self.looks[pi]
        name = L.get("name", "").strip()
        L["name"] = name or (self._before[pi].strip() or DEFAULT_NAMES[pi])

    def _type(self, e):
        """A key while a name box is focused. True when it was consumed."""
        L = self.looks[self.focus]
        name = L.get("name", "")
        if e.key == pygame.K_BACKSPACE:
            L["name"] = name[:-1]
            return True
        if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._unfocus()
            self.g.audio.play("ui_select")
            return True
        if e.key in (pygame.K_TAB, pygame.K_UP, pygame.K_DOWN):
            return False                      # leave the box and move the highlight
        ch = getattr(e, "unicode", "") or ""
        if not ch or not ch.isprintable():
            return True                       # arrows, shift, F-keys...: nothing to type
        if not name_char_ok(ch):
            self._warn_t, self._warn_pi = 2.2, self.focus
            self.g.audio.play("error")
            return True
        if len(name) < NAME_MAX:
            L["name"] = name + ch
        return True

    def _start(self):
        if self.focus is not None:
            self._unfocus()
        for i, L in enumerate(self.looks):
            L["name"] = L.get("name", "").strip() or DEFAULT_NAMES[i]
        self.g.audio.play("ui_select")
        self.g.start_new(self.looks)

    # ---- keyboard highlight ----
    def _move(self, drow):
        pi, row = self.cur
        row = (row + drow) % (ROW_START + 1)
        if row == ROW_START:
            self.cur = (None, ROW_START)
        else:                                  # leaving START: back to the last panel
            self.cur = (self._last_pi if pi is None else pi, row)
        self.g.audio.play("ui_move")

    def _tab(self, step):
        i = _NAV_ORDER.index(self.cur) if self.cur in _NAV_ORDER else 0
        self.cur = _NAV_ORDER[(i + step) % len(_NAV_ORDER)]
        self.g.audio.play("ui_move")

    def _side(self, d):
        """Left/Right: change the highlighted look, or hop between the panels."""
        pi, row = self.cur
        if pi is not None and 1 <= row <= len(FIELDS):
            self._cycle(pi, FIELDS[row - 1][0], d)
        elif pi is not None:
            npi = 0 if d < 0 else 1
            if npi != pi:
                self.cur = (npi, row)
                self.g.audio.play("ui_move")

    def _activate(self):
        pi, row = self.cur
        if row == ROW_START:
            self._start()
        elif row == ROW_NAME:
            self._focus_name(pi)
        else:
            self._cycle(pi, FIELDS[row - 1][0], +1)

    # ---- input ----
    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                if self.focus is not None:
                    self._unfocus()
                else:
                    self.g.state = "menu"
                return
            if self.focus is not None:
                if self._type(e):
                    return
                self._unfocus()                   # Tab / Up / Down leave the box
            k = e.key
            if k == pygame.K_TAB:
                self._tab(-1 if (getattr(e, "mod", 0) & pygame.KMOD_SHIFT) else 1)
            elif k in _K_UP:
                self._move(-1)
            elif k in _K_DOWN:
                self._move(+1)
            elif k in _K_LEFT:
                self._side(-1)
            elif k in _K_RIGHT:
                self._side(+1)
            elif k in _K_OK:
                self._activate()
            if self.cur[0] is not None:
                self._last_pi = self.cur[0]      # where Up from START returns to
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            pos = e.pos
            if self._start_rect().collidepoint(pos):
                self._start()
                return
            if self._back_rect().collidepoint(pos):
                self._unfocus()
                self.g.audio.play("ui_move")
                self.g.state = "menu"
                return
            for pi in (0, 1):
                if self._name_rect(pi).collidepoint(pos):
                    if self.focus != pi:
                        self._focus_name(pi)
                    return
                for i, (f, label, y, left, right) in enumerate(self._field_rows(pi)):
                    if left.collidepoint(pos) or right.collidepoint(pos):
                        self._unfocus()
                        self.cur = (pi, i + 1)
                        self._last_pi = pi
                        self._cycle(pi, f, -1 if left.collidepoint(pos) else +1)
                        return
            self._unfocus()

    def update(self, dt):
        self.t += dt
        if self._warn_t > 0:
            self._warn_t = max(0.0, self._warn_t - dt)

    # ---- draw ----
    def _menu(self):
        return getattr(self.g, "menu", None)

    def _draw_backdrop(self, surf):
        """The title menu's animated diorama under a soft dusk dim (falls back
        to a warm gradient if the scene is unavailable)."""
        menu = self._menu()
        scene = getattr(menu, "scene", None) if menu is not None else None
        if scene is not None:
            try:
                t = self._t0 + self.t
                if self._last_t is not None and self.t > self._last_t:
                    scene.update(min(0.1, self.t - self._last_t), t)
                self._last_t = self.t
                scene.draw(surf, t)
                surf.blit(_cached_dim(), (0, 0))
                return
            except Exception:
                pass
        for y in range(0, SCREEN_H, 4):
            f = y / SCREEN_H
            surf.fill((int(70 - 30 * f), int(54 - 26 * f), int(76 - 30 * f)), (0, y, SCREEN_W, 4))

    def _button(self, surf, rect, label, selected, font=None):
        """The title menu's parchment button (menu.Menu._button); a local copy
        of its look is used if the menu is unavailable."""
        menu = self._menu()
        hover = 1.0 if (selected or rect.collidepoint(pygame.mouse.get_pos())) else 0.0
        if menu is not None and hasattr(menu, "_button"):
            try:
                menu._button(surf, rect, label, selected, font=font, hover=hover)
                return
            except Exception:
                pass
        pygame.draw.rect(surf, WOOD, rect, border_radius=14)
        pygame.draw.rect(surf, (255, 224, 150) if selected else CREAM, rect.inflate(-6, -6),
                         border_radius=11)
        t = (font or self.font).render(label, True, INK)
        surf.blit(t, (rect.centerx - t.get_width() // 2, rect.centery - t.get_height() // 2))

    def draw(self, surf):
        self._draw_backdrop(surf)
        # title on the title screen's parchment ribbon (folded tails)
        title = self.big.render("CREATE YOUR FARMERS", True, (80, 46, 40))
        cx = SCREEN_W // 2
        rw, rh = title.get_width() + 72, title.get_height() + 16
        ry = 34
        rib = pygame.Rect(cx - rw // 2, ry, rw, rh)
        tail = (206, 150, 110)
        pygame.draw.polygon(surf, tail, [(rib.x - 22, ry + 6), (rib.x + 4, ry + 6),
                                         (rib.x + 4, ry + rh + 6), (rib.x - 22, ry + rh + 6),
                                         (rib.x - 12, ry + rh // 2 + 6)])
        pygame.draw.polygon(surf, tail, [(rib.right + 22, ry + 6), (rib.right - 4, ry + 6),
                                         (rib.right - 4, ry + rh + 6), (rib.right + 22, ry + rh + 6),
                                         (rib.right + 12, ry + rh // 2 + 6)])
        pygame.draw.rect(surf, (250, 236, 206), rib, border_radius=6)
        pygame.draw.rect(surf, (196, 140, 100), rib, 2, border_radius=6)
        surf.blit(title, (cx - title.get_width() // 2, ry + (rh - title.get_height()) // 2))
        for pi in (0, 1):
            self._draw_panel(surf, pi)
        mouse = pygame.mouse.get_pos()
        # START glows gold when the keyboard highlight is on it (Enter presses it)
        self._button(surf, self._start_rect(), "START", self.cur[1] == ROW_START)
        br = self._back_rect()
        self._button(surf, br, "Back", br.collidepoint(mouse), font=self.font)
        # footer hint on a soft pill (like the title menu's)
        h = self.small.render(FOOTER_HINT, True, (250, 244, 232))
        pill = pygame.Surface((h.get_width() + 28, h.get_height() + 10), pygame.SRCALPHA)
        pygame.draw.rect(pill, (40, 28, 36, 170), pill.get_rect(), border_radius=12)
        py = SCREEN_H - 40
        surf.blit(pill, (SCREEN_W // 2 - pill.get_width() // 2, py))
        surf.blit(h, (SCREEN_W // 2 - h.get_width() // 2, py + 5))

    def _draw_panel(self, surf, pi):
        px = PANELS[pi]
        L = self.looks[pi]
        rect = pygame.Rect(px, PANEL_Y, PANEL_W, PANEL_H)
        surf.blit(_card(PANEL_W, PANEL_H), (px - 4, PANEL_Y - 2))
        if self.focus == pi:
            pygame.draw.rect(surf, (255, 214, 120), rect.inflate(8, 8), 3, border_radius=20)
        # header: player name plate + controls tag
        pc = P_COL[pi]
        hd = self.big.render(f"PLAYER {pi + 1}", True, pc)
        surf.blit(hd, (px + 26, PANEL_Y + 18))
        ctrl = self.tiny.render("WASD + Space" if pi == 0 else "Arrows + Enter", True, CREAM_HI)
        tag = pygame.Rect(0, 0, ctrl.get_width() + 18, ctrl.get_height() + 8)
        tag.topright = (px + PANEL_W - 24, PANEL_Y + 24)
        pygame.draw.rect(surf, pc, tag, border_radius=9)
        surf.blit(ctrl, (tag.x + 9, tag.y + 4))
        # live preview on a little grassy pedestal (animated bob)
        cx = px + PANEL_W // 2
        base_y = PANEL_Y + 190
        pygame.draw.ellipse(surf, (150, 196, 120), (cx - 72, base_y - 14, 144, 30))
        pygame.draw.ellipse(surf, (182, 220, 146), (cx - 66, base_y - 14, 132, 24))
        for i, fx in enumerate((-52, -34, 40, 56)):          # a few pastel flowers
            fc = ((250, 190, 214), (255, 230, 150), (214, 196, 250), (250, 190, 214))[i]
            pygame.draw.circle(surf, fc, (cx + fx, base_y - 3 + (i % 2) * 5), 3)
        spr = assets.player_sprite(L)
        big = pygame.transform.scale(spr, (spr.get_width() * 3, spr.get_height() * 3))
        bob = int(math.sin(self.t * 3 + pi) * 4)
        sh = _shadow()
        surf.blit(sh, (cx - sh.get_width() // 2, base_y - 9))
        surf.blit(big, (cx - big.get_width() // 2, base_y - big.get_height() + 4 + bob))
        # name box
        nr = self._name_rect(pi)
        if self.cur == (pi, ROW_NAME):
            self._draw_cursor(surf, pygame.Rect(px + 13, nr.y - 5, PANEL_W - 26, nr.h + 10))
        surf.blit(self.font.render("Name", True, INK), (px + 28, nr.y + 8))
        pygame.draw.rect(surf, CREAM_HI, nr, border_radius=8)
        pygame.draw.rect(surf, (214, 160, 70) if self.focus == pi else INK_SOFT, nr,
                         3 if self.focus == pi else 2, border_radius=8)
        name = L.get("name", "")
        caret = self.focus == pi and int(self.t * 2) % 2 == 0
        if name:
            surf.blit(self.font.render(name + ("|" if caret else ""), True, INK), (nr.x + 10, nr.y + 8))
        else:
            if caret:
                surf.blit(self.font.render("|", True, INK), (nr.x + 10, nr.y + 8))
            ph = self.small.render("type a name..." if self.focus == pi else
                                   "click or Enter to type", True, (176, 150, 128))
            surf.blit(ph, (nr.x + 22, nr.centery - ph.get_height() // 2))
        if self._warn_t > 0 and self._warn_pi == pi:
            wt = self.tiny.render("English letters only", True, (196, 72, 60))
            surf.blit(wt, (nr.right - wt.get_width() - 10, nr.centery - wt.get_height() // 2))
        # option rows
        mouse = pygame.mouse.get_pos()
        for i, (f, label, y, left, right) in enumerate(self._field_rows(pi)):
            kb = self.cur == (pi, i + 1)
            if kb:
                self._draw_cursor(surf, pygame.Rect(px + 13, y - 3, PANEL_W - 26, 38))
            surf.blit(self.font.render(label, True, INK), (px + 28, y + 7))
            mid = pygame.Rect(left.right + 8, y, right.left - left.right - 16, 32)
            pygame.draw.rect(surf, (240, 224, 194), mid, border_radius=8)
            for rect, d in ((left, -1), (right, 1)):
                hot = kb or rect.collidepoint(mouse)
                pygame.draw.rect(surf, WOOD, rect, border_radius=9)
                pygame.draw.rect(surf, (255, 232, 170) if hot else CREAM, rect.inflate(-4, -4),
                                 border_radius=7)
                ax, ay = rect.centerx, rect.centery
                pts = ([(ax + 4, ay - 7), (ax - 5, ay), (ax + 4, ay + 7)] if d < 0 else
                       [(ax - 4, ay - 7), (ax + 5, ay), (ax - 4, ay + 7)])
                pygame.draw.polygon(surf, SPROUT, pts)
            self._draw_value(surf, f, L[f], mid)

    def _draw_cursor(self, surf, band):
        """The keyboard highlight: a warm band behind the row + a bobbing sprout."""
        pulse = 0.5 + 0.5 * math.sin(self.t * 5)
        pygame.draw.rect(surf, (252, 226, 164), band, border_radius=10)
        rim = tuple(int(a + (b - a) * pulse) for a, b in zip((214, 160, 70), (240, 192, 104)))
        pygame.draw.rect(surf, rim, band, 2, border_radius=10)
        mx, my = band.x + 4, band.centery
        pygame.draw.polygon(surf, SPROUT, [(mx, my - 5), (mx + 6, my), (mx, my + 5)])

    def _draw_value(self, surf, f, idx, box):
        if f == "skin":
            pygame.draw.circle(surf, assets.SKIN_TONES[idx], (box.centerx, box.centery), 11)
            pygame.draw.circle(surf, INK_SOFT, (box.centerx, box.centery), 11, 2)
        elif f == "hair_style":
            ui_kit.blit_text(surf, self.font, assets.HAIR_STYLES[idx].title(), INK, box.center)
        else:
            pal = assets.HAIR_COLORS if f == "hair_color" else assets.SHIRT_COLORS
            r = pygame.Rect(box.centerx - 18, box.centery - 10, 36, 20)
            pygame.draw.rect(surf, pal[idx], r, border_radius=5)
            pygame.draw.rect(surf, INK_SOFT, r, 2, border_radius=5)


_CACHE = {}


def _cached_dim():
    s = _CACHE.get("dim")
    if s is None:
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        s.fill((40, 24, 44, 96))
        _CACHE["dim"] = s
    return s


def _shadow():
    s = _CACHE.get("shadow")
    if s is None:
        s = pygame.Surface((64, 14), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (60, 40, 30, 70), s.get_rect())
        _CACHE["shadow"] = s
    return s


def _card(w, h):
    """Parchment card with a wooden rim and a soft drop shadow (ui_kit)."""
    return ui_kit.card_surface(w, h)
