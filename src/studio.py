"""The Art Studio: paint 24x24 pixel art at the easel (state "studio").

Owner: Showpieces (2026-09-28). Glue lives in ``systems/showpiece_system.py``.

* A 24x24 canvas, zoomed big, with a cosy 21-colour palette (index 0 is the
  bare canvas, which is also what the eraser paints).
* Tools: Pencil, Eraser, Fill bucket, Picker (eyedropper), Line; Mirror
  symmetry (left <-> right) and a Grid toggle; Undo / Redo / Clear.
* Mouse: left paints with the tool, right erases, the wheel changes colour,
  every button is clickable. Keyboard: arrows move the cursor, Space / Enter
  use the tool (hold Space while moving to keep painting), 1-5 pick a tool,
  Q / E (or , / .) change colour, M mirror, G grid, Z undo, Y redo, C clear,
  S save, H hang on the wall, Tab next tool, Esc done (the canvas stays on
  the easel exactly as you left it -- leaving saves too).

Art is stored as a compact run-length string (``encode`` / ``decode``):
``"1:"`` + tokens, each a palette letter (A = canvas, B = ink...) followed by
an optional run length, e.g. a bare canvas is ``"1:A576"``. The easel keeps it
in ``Placed.data["art"]``; the in-room easel and the painting frames render
it with ``draw_on_face`` / ``art_surface``.
"""
import math
import pygame

from .settings import SCREEN_W, SCREEN_H, P1_KEYS, P2_KEYS
from . import ui_kit as K

N = 24                                   # canvas is N x N pixels
PREFIX = "1:"
_SYM = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# (name, rgb) -- index 0 is the bare canvas (the eraser's colour)
PALETTE = [
    ("Canvas", (250, 246, 236)), ("Ink", (74, 44, 36)), ("White", (255, 255, 255)),
    ("Mist", (170, 166, 176)), ("Rose", (220, 92, 96)), ("Blush", (244, 164, 188)),
    ("Heart", (228, 128, 150)), ("Peach", (246, 178, 140)), ("Pumpkin", (238, 146, 70)),
    ("Butter", (246, 214, 124)), ("Lemon", (250, 236, 150)), ("Mint", (160, 206, 150)),
    ("Leaf", (96, 160, 86)), ("Forest", (58, 110, 72)), ("Sky", (138, 182, 226)),
    ("Powder", (174, 220, 236)), ("Navy", (62, 72, 120)), ("Lilac", (190, 160, 226)),
    ("Plum", (130, 84, 150)), ("Cocoa", (140, 96, 60)), ("Sand", (222, 202, 162)),
]
RGB = [c for _n, c in PALETTE]

TOOLS = [("pencil", "Pencil", "1"), ("eraser", "Eraser", "2"), ("fill", "Fill", "3"),
         ("picker", "Picker", "4"), ("line", "Line", "5")]
UNDO_MAX = 60


# ---------------------------------------------------------------- encoding
def blank():
    return [0] * (N * N)


def is_blank(px):
    return not any(px)


def encode(px):
    """Pixels (N*N palette indices) -> compact run-length string."""
    out = [PREFIX]
    i, n = 0, len(px)
    while i < n:
        c = px[i]
        j = i + 1
        while j < n and px[j] == c:
            j += 1
        run = j - i
        out.append(_SYM[c % len(RGB)] + (str(run) if run > 1 else ""))
        i = j
    return "".join(out)


def decode(s):
    """Compact string -> list of N*N palette indices (None if it's not art)."""
    if not isinstance(s, str) or not s.startswith(PREFIX) or len(s) > 4000:
        return None
    px = []
    i, body = 0, s[len(PREFIX):]
    while i < len(body):
        ch = body[i]
        c = _SYM.find(ch)
        if c < 0 or c >= len(RGB):
            return None
        i += 1
        j = i
        while j < len(body) and body[j].isdigit():
            j += 1
        run = int(body[i:j]) if j > i else 1
        if run <= 0 or len(px) + run > N * N:
            return None
        px.extend([c] * run)
        i = j
    return px if len(px) == N * N else None


def valid(s):
    return decode(s) is not None


# ---------------------------------------------------------------- rendering
_SURF = {}


def art_surface(art, scale=1):
    """The artwork as a crisp Surface (N*scale square), cached. None = not art."""
    key = (art, scale)
    s = _SURF.get(key)
    if s is None:
        px = decode(art)
        if px is None:
            return None
        base = pygame.Surface((N, N))
        for i, c in enumerate(px):
            base.set_at((i % N, i // N), RGB[c])
        s = base if scale == 1 else pygame.transform.scale(base, (N * scale, N * scale))
        if len(_SURF) > 96:
            _SURF.clear()
        _SURF[key] = s
    return s


_SHEAR = {}


def sheared(art, w, h, slope):
    """The artwork fitted to a w x h px picture whose top edge climbs
    ``slope`` px per px (an iso wall / canvas face with vertical sides).
    Returns (surface, y_offset of its top-left corner). Cached."""
    w, h = max(2, int(round(w))), max(2, int(round(h)))
    key = (art, w, h, round(slope, 3))
    got = _SHEAR.get(key)
    if got is None:
        src = art_surface(art)
        if src is None:
            return None, 0
        # bigger than the art: keep the pixels crisp; smaller: blend them
        img = None
        if w < N or h < N:                   # smaller than the art: blend the pixels
            try:
                img = pygame.transform.smoothscale(src, (w, h))
            except (ValueError, pygame.error):
                img = None
        if img is None:                      # bigger: keep them crisp
            img = pygame.transform.scale(src, (w, h))
        rise = slope * (w - 1)
        top = max(0.0, -rise)
        out = pygame.Surface((w, h + int(math.ceil(abs(rise))) + 1), pygame.SRCALPHA)
        for x in range(w):
            out.blit(img, (x, int(round(top + slope * x))), (x, 0, 1, h))
        got = (out, int(round(top)))
        if len(_SHEAR) > 64:
            _SHEAR.clear()
        _SHEAR[key] = got
    return got


def draw_on_face(surf, tl, tr, bl, art):
    """Paint ``art`` into the parallelogram tl-tr-(br)-bl (screen points; the
    left/right sides are vertical, as on every iso wall or canvas face).
    True = painted."""
    w = tr[0] - tl[0]
    h = bl[1] - tl[1]
    if w < 2 or h < 2:
        return False
    img, top = sheared(art, w, h, (tr[1] - tl[1]) / w)
    if img is None:
        return False
    surf.blit(img, (int(round(tl[0])), int(round(tl[1])) - top))
    return True


# ---------------------------------------------------------------- little icons
def _tool_icon(surf, tool, c, col=K.INK):
    x, y = c
    if tool == "pencil":
        pygame.draw.polygon(surf, (246, 206, 96), [(x - 8, y + 6), (x + 5, y - 7), (x + 8, y - 4),
                                                   (x - 5, y + 9)])
        pygame.draw.polygon(surf, (236, 160, 170), [(x + 5, y - 7), (x + 7, y - 9), (x + 10, y - 6),
                                                    (x + 8, y - 4)])
        pygame.draw.polygon(surf, (240, 220, 180), [(x - 8, y + 6), (x - 5, y + 9), (x - 10, y + 11)])
        pygame.draw.line(surf, col, (x - 10, y + 11), (x - 9, y + 10), 2)
    elif tool == "eraser":
        pygame.draw.polygon(surf, (244, 164, 188), [(x - 9, y + 3), (x + 1, y - 7), (x + 9, y + 1),
                                                    (x - 1, y + 11)])
        pygame.draw.polygon(surf, (138, 182, 226), [(x - 9, y + 3), (x - 4, y - 2), (x + 4, y + 6),
                                                    (x - 1, y + 11)])
        pygame.draw.polygon(surf, col, [(x - 9, y + 3), (x + 1, y - 7), (x + 9, y + 1),
                                        (x - 1, y + 11)], 1)
    elif tool == "fill":
        pygame.draw.polygon(surf, (190, 196, 206), [(x - 8, y - 2), (x + 2, y - 8), (x + 8, y + 2),
                                                    (x - 2, y + 8)])
        pygame.draw.polygon(surf, col, [(x - 8, y - 2), (x + 2, y - 8), (x + 8, y + 2),
                                        (x - 2, y + 8)], 1)
        pygame.draw.circle(surf, (96, 150, 220), (x + 9, y + 8), 3)
        pygame.draw.polygon(surf, (96, 150, 220), [(x + 6, y + 7), (x + 12, y + 7), (x + 9, y + 2)])
    elif tool == "picker":
        pygame.draw.line(surf, (170, 176, 190), (x - 8, y + 8), (x + 3, y - 3), 4)
        pygame.draw.line(surf, col, (x + 2, y - 2), (x + 8, y - 8), 6)
        pygame.draw.circle(surf, (228, 128, 150), (x - 9, y + 9), 2)
    elif tool == "line":
        pygame.draw.line(surf, col, (x - 9, y + 8), (x + 9, y - 8), 3)
        for p in ((x - 9, y + 8), (x + 9, y - 8)):
            pygame.draw.circle(surf, (228, 128, 150), p, 3)
    elif tool == "mirror":
        pygame.draw.polygon(surf, (138, 182, 226), [(x - 2, y - 8), (x - 2, y + 8), (x - 10, y + 8)])
        pygame.draw.polygon(surf, (228, 128, 150), [(x + 2, y - 8), (x + 2, y + 8), (x + 10, y + 8)])
        for yy in range(y - 10, y + 11, 4):
            pygame.draw.line(surf, col, (x, yy), (x, yy + 1), 1)
    elif tool == "grid":
        for k in (-8, -3, 2, 7):
            pygame.draw.line(surf, col, (x + k, y - 9), (x + k, y + 8), 1)
            pygame.draw.line(surf, col, (x - 9, y + k), (x + 8, y + k), 1)
    elif tool in ("undo", "redo"):
        sgn = -1 if tool == "undo" else 1
        pygame.draw.arc(surf, col, (x - 8, y - 6, 16, 14), 0.2, math.pi - 0.2, 3)
        tip = (x + sgn * 8, y + 2)
        pygame.draw.polygon(surf, col, [(tip[0] - 5, tip[1] - 1), (tip[0] + 5, tip[1] - 1),
                                        (tip[0], tip[1] + 5)])
    elif tool == "save":                                # a canvas on a little easel
        pygame.draw.line(surf, K.WOOD, (x - 7, y + 10), (x, y - 10), 2)
        pygame.draw.line(surf, K.WOOD, (x + 7, y + 10), (x, y - 10), 2)
        pygame.draw.rect(surf, (250, 246, 236), (x - 8, y - 7, 16, 12))
        pygame.draw.rect(surf, col, (x - 8, y - 7, 16, 12), 1)
        pygame.draw.circle(surf, (228, 128, 150), (x - 2, y - 1), 3)
        pygame.draw.line(surf, K.WOOD_DK, (x - 10, y + 5), (x + 10, y + 5), 2)
    elif tool == "hang":                                # a framed heart on a nail
        pygame.draw.line(surf, col, (x, y - 11), (x - 7, y - 5), 1)
        pygame.draw.line(surf, col, (x, y - 11), (x + 7, y - 5), 1)
        pygame.draw.rect(surf, (158, 112, 64), (x - 10, y - 5, 20, 16), border_radius=2)
        pygame.draw.rect(surf, (174, 220, 236), (x - 7, y - 2, 14, 10))
        pygame.draw.circle(surf, (228, 128, 150), (x - 2, y + 2), 2)
        pygame.draw.circle(surf, (228, 128, 150), (x + 2, y + 2), 2)
        pygame.draw.polygon(surf, (228, 128, 150), [(x - 4, y + 3), (x + 4, y + 3), (x, y + 7)])
    elif tool == "clear":
        pygame.draw.rect(surf, (214, 200, 188), (x - 7, y - 5, 14, 14), border_radius=2)
        pygame.draw.rect(surf, col, (x - 7, y - 5, 14, 14), 1, border_radius=2)
        pygame.draw.line(surf, col, (x - 9, y - 7), (x + 9, y - 7), 2)
        pygame.draw.line(surf, col, (x - 2, y - 10), (x + 2, y - 10), 2)


# ---------------------------------------------------------------- the screen
class ArtStudio:
    """Full-screen pixel painting page for the easel ``easel`` (a Placed)."""

    CELL = 19

    def __init__(self, game, pidx, easel, client=False):
        self.g = game
        self.pidx = pidx
        self.easel = easel
        self.client = client
        art = (getattr(easel, "data", None) or {}).get("art") if easel is not None else None
        self.px = decode(art) or blank()
        self.saved = encode(self.px)
        self.color = 1
        self.tool = "pencil"
        self.mirror = False
        self.grid = True
        self.cx = self.cy = N // 2
        self.undo_stack = []
        self.redo_stack = []
        self.line_a = None               # (x, y) anchor of a line in progress
        self.stroke = None               # mouse button held on the canvas (1 / 3)
        self.last_cell = None
        self.hover = None
        self.space = False               # Space / Enter held (keyboard painting)
        self.t = 0.0
        self.msg = ""
        self.msg_t = 0.0
        self.closed = False
        # layout
        self.card = pygame.Rect(46, 40, SCREEN_W - 92, SCREEN_H - 74)
        side = N * self.CELL
        self.canvas = pygame.Rect(SCREEN_W // 2 - side // 2, 104, side, side)
        self.btns = {}
        x, y = 86, 118
        for tid, _lab, _k in TOOLS:
            self.btns[tid] = pygame.Rect(x, y, 272, 42)
            y += 48
        y += 10
        self.btns["mirror"] = pygame.Rect(x, y, 272, 42)
        y += 48
        self.btns["grid"] = pygame.Rect(x, y, 272, 42)
        y += 54
        self.btns["undo"] = pygame.Rect(x, y, 132, 42)
        self.btns["redo"] = pygame.Rect(x + 140, y, 132, 42)
        y += 54
        self.btns["clear"] = pygame.Rect(x, y, 272, 42)
        rx = self.canvas.right + 34
        self.swatch = []
        for i in range(len(RGB)):
            r, c = divmod(i, 7)
            self.swatch.append(pygame.Rect(rx + c * 42, 132 + r * 42, 36, 36))
        self.btns["save"] = pygame.Rect(rx, 456, 290, 42)
        self.btns["hang"] = pygame.Rect(rx, 506, 290, 42)

    # ------------------------------------------------------------ state
    @property
    def dirty(self):
        return encode(self.px) != self.saved

    def say(self, text):
        self.msg, self.msg_t = text, 3.0

    def snapshot(self):
        self.undo_stack.append(list(self.px))
        if len(self.undo_stack) > UNDO_MAX:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def do_undo(self):
        if not self.undo_stack:
            self.say("Nothing to undo")
            return False
        self.redo_stack.append(list(self.px))
        self.px = self.undo_stack.pop()
        self.line_a = None
        self._sfx("ui_move")
        return True

    def do_redo(self):
        if not self.redo_stack:
            self.say("Nothing to redo")
            return False
        self.undo_stack.append(list(self.px))
        self.px = self.redo_stack.pop()
        self._sfx("ui_move")
        return True

    def clear(self):
        if is_blank(self.px):
            return False
        self.snapshot()
        self.px = blank()
        self.line_a = None
        self.say("Fresh canvas! (Z to undo)")
        self._sfx("ui_toggle")
        return True

    def set_tool(self, tool):
        if tool != self.tool:
            self.tool = tool
            self.line_a = None
            self._sfx("ui_move")

    def set_color(self, c):
        self.color = c % len(RGB)
        if self.tool in ("eraser", "picker") and self.color:
            self.tool = "pencil"
        self._sfx("ui_move")

    # ------------------------------------------------------------ painting ops
    def _put(self, x, y, c):
        if 0 <= x < N and 0 <= y < N:
            self.px[y * N + x] = c
            if self.mirror:
                self.px[y * N + (N - 1 - x)] = c

    def get(self, x, y):
        return self.px[y * N + x]

    def fill(self, x, y, c):
        tgt = self.get(x, y)
        seeds = [(x, y)] + ([(N - 1 - x, y)] if self.mirror else [])
        for sx, sy in seeds:
            tgt = self.px[sy * N + sx]
            if tgt == c:
                continue
            stack = [(sx, sy)]
            while stack:
                a, b = stack.pop()
                if 0 <= a < N and 0 <= b < N and self.px[b * N + a] == tgt:
                    self.px[b * N + a] = c
                    stack.extend(((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)))

    @staticmethod
    def cells_between(a, b):
        """Bresenham cells from a to b (inclusive)."""
        (x0, y0), (x1, y1) = a, b
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        out = []
        while True:
            out.append((x0, y0))
            if (x0, y0) == (x1, y1):
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy
        return out

    def line(self, a, b, c):
        for x, y in self.cells_between(a, b):
            self._put(x, y, c)

    def _begin(self):
        self._pre = self.px[:]
        self._pushed = False

    def _commit(self):
        """Push the stroke's undo point the moment it first changes anything
        (a press that changes nothing leaves no undo step and keeps redo)."""
        pre = getattr(self, "_pre", None)
        if pre is not None and not self._pushed and self.px != pre:
            self.undo_stack.append(pre)
            if len(self.undo_stack) > UNDO_MAX:
                self.undo_stack.pop(0)
            self.redo_stack.clear()
            self._pushed = True

    def use_tool(self, x, y, tool=None, fresh=True):
        """Apply a tool at cell (x, y). ``fresh`` = start of a stroke (its
        undo point). Returns True if the canvas changed."""
        tool = tool or self.tool
        if not (0 <= x < N and 0 <= y < N):
            return False
        before = self.px[:]
        if tool == "picker":
            self.color = self.get(x, y)
            self.tool = "pencil" if self.color else "eraser"
            self.say(f"Picked {PALETTE[self.color][0]}")
            self._sfx("ui_select")
            return False
        if fresh or getattr(self, "_pre", None) is None:
            self._begin()
        if tool == "line":
            if self.line_a is None:
                self.line_a = (x, y)
                self._sfx("ui_move")
                return False
            self.line(self.line_a, (x, y), self.color)
            self.line_a = None
        elif tool == "fill":
            self.fill(x, y, self.color)
        else:
            c = 0 if tool == "eraser" else self.color
            if self.last_cell is not None and not fresh:
                self.line(self.last_cell, (x, y), c)
            else:
                self._put(x, y, c)
        self.last_cell = (x, y)
        self._commit()
        changed = self.px != before
        if changed:
            self._sfx("studio_dab", quiet=True)
        return changed

    # ------------------------------------------------------------ actions
    def save(self):
        fn = getattr(self.g, "_studio_save", None)
        msg = fn(self) if fn else ""
        self.saved = encode(self.px)
        if msg:
            self.say(msg)
        return True

    def hang(self):
        if is_blank(self.px):
            self.say("Paint something first!")
            self._sfx("ui_move")
            return False
        fn = getattr(self.g, "_studio_hang", None)
        msg = fn(self) if fn else ""
        self.saved = encode(self.px)
        if msg:
            self.say(msg)
        return True

    def close(self):
        if self.closed:
            return
        self.closed = True
        fn = getattr(self.g, "_studio_closed", None)
        if fn:
            fn(self)

    def _sfx(self, name, quiet=False):
        a = getattr(self.g, "audio", None)
        if a is None:
            return
        real = getattr(a, "_real", None) or a
        if quiet and getattr(real, "sfx", {}).get(name) is None:
            return
        a.play(name if getattr(real, "sfx", {}).get(name) is not None else "ui_move")

    # ------------------------------------------------------------ input
    def cell_at(self, pos):
        if not self.canvas.collidepoint(pos):
            return None
        return ((pos[0] - self.canvas.x) // self.CELL, (pos[1] - self.canvas.y) // self.CELL)

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            self.handle_key(e.key, getattr(e, "mod", 0))
        elif e.type == pygame.KEYUP:
            if e.key in (pygame.K_SPACE, pygame.K_RETURN, P1_KEYS.get("action"),
                         P2_KEYS.get("action")):
                self.space = False
                self.last_cell = None
        elif e.type == pygame.MOUSEBUTTONDOWN:
            b = getattr(e, "button", 1)
            if b in (4, 5):
                self.set_color(self.color + (-1 if b == 4 else 1))
                return
            self.click(e.pos, b)
        elif e.type == pygame.MOUSEBUTTONUP:
            b = getattr(e, "button", 1)
            if self.stroke is not None and b == self.stroke:
                c = self.cell_at(e.pos)
                if self.tool == "line" and self.line_a is not None and c is not None \
                        and c != self.line_a and b == 1:
                    self.use_tool(*c)
                self.stroke = None
                self.last_cell = None
        elif e.type == pygame.MOUSEMOTION:
            c = self.cell_at(e.pos)
            self.hover = c
            if c is not None:
                self.cx, self.cy = c
                if self.stroke is not None and c != self.last_cell:
                    if self.stroke == 3:
                        self.use_tool(*c, tool="eraser", fresh=False)
                    elif self.tool in ("pencil", "eraser"):
                        self.use_tool(*c, fresh=False)
        elif e.type == getattr(pygame, "MOUSEWHEEL", -1):
            y = getattr(e, "y", 0)
            if y:
                self.set_color(self.color + (-1 if y > 0 else 1))

    def click(self, pos, button=1):
        c = self.cell_at(pos)
        if c is not None:
            self.cx, self.cy = c
            if button == 3:
                self.stroke = 3
                self.last_cell = None
                self.use_tool(*c, tool="eraser", fresh=True)
            elif button == 1:
                self.stroke = 1
                self.last_cell = None
                if self.tool == "line" and self.line_a is not None:
                    self.use_tool(*c)
                    self.stroke = None
                else:
                    self.use_tool(*c, fresh=True)
            return
        if button != 1:
            return
        for i, r in enumerate(self.swatch):
            if r.collidepoint(pos):
                self.set_color(i)
                return
        for name, r in self.btns.items():
            if r.collidepoint(pos):
                self.press(name)
                return

    def press(self, name):
        if name in dict((t, 1) for t, _l, _k in TOOLS):
            self.set_tool(name)
        elif name == "mirror":
            self.mirror = not self.mirror
            self.say("Mirror ON: both halves paint together" if self.mirror else "Mirror off")
            self._sfx("ui_toggle")
        elif name == "grid":
            self.grid = not self.grid
            self._sfx("ui_toggle")
        elif name == "undo":
            self.do_undo()
        elif name == "redo":
            self.do_redo()
        elif name == "clear":
            self.clear()
        elif name == "save":
            self.save()
        elif name == "hang":
            self.hang()

    def handle_key(self, key, mod=0):
        moves = {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0),
                 pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1)}
        if key == pygame.K_ESCAPE:
            self.close()
        elif key in moves:
            dx, dy = moves[key]
            self.cx = max(0, min(N - 1, self.cx + dx))
            self.cy = max(0, min(N - 1, self.cy + dy))
            if self.space and self.tool in ("pencil", "eraser"):
                self.use_tool(self.cx, self.cy, fresh=False)
        elif key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
            first = not self.space
            self.space = True
            if first:
                self.last_cell = None
                self.use_tool(self.cx, self.cy, fresh=True)
        elif key == pygame.K_z:
            self.do_undo()
        elif key == pygame.K_y:
            self.do_redo()
        elif key == pygame.K_s:
            self.save()
        elif key == pygame.K_h:
            self.hang()
        elif key == pygame.K_c:
            self.clear()
        elif key == pygame.K_m:
            self.press("mirror")
        elif key == pygame.K_g:
            self.press("grid")
        elif key == pygame.K_TAB:
            ids = [t for t, _l, _k in TOOLS]
            self.set_tool(ids[(ids.index(self.tool) + 1) % len(ids)])
        elif key in (pygame.K_q, pygame.K_COMMA, pygame.K_LEFTBRACKET):
            self.set_color(self.color - 1)
        elif key in (pygame.K_e, pygame.K_PERIOD, pygame.K_RIGHTBRACKET):
            self.set_color(self.color + 1)
        else:
            for tid, _l, k in TOOLS:
                if key == getattr(pygame, f"K_{k}"):
                    self.set_tool(tid)

    # ------------------------------------------------------------ frame
    def update(self, dt):
        self.t += dt
        if self.msg_t > 0:
            self.msg_t = max(0.0, self.msg_t - dt)
        if self.easel is not None and self.g.state == "studio" and not self.client:
            if not any(q is self.easel for q in self.g.world.home_furniture):
                self.say("The easel was moved away!")
                self.close()

    # ------------------------------------------------------------ draw
    def _img(self, scale):
        """The canvas as a scaled picture, rebuilt only when it changes (kept
        per screen, so the big zoomed copies never pile up in a cache)."""
        cache = self.__dict__.setdefault("_imgs", {})
        enc = encode(self.px)
        got = cache.get(scale)
        if got is None or got[0] != enc:
            base = art_surface(enc)
            got = (enc, pygame.transform.scale(base, (N * scale, N * scale)))
            cache[scale] = got
        return got[1]

    def draw(self, surf):
        K.dim(surf, 150, (22, 14, 30))
        K.modal(surf, self.card, "Art Studio")
        name = self.g.players[self.pidx].name if self.pidx < len(self.g.players) else "You"
        K.blit_text(surf, K.font(14, True), f"{name} at the easel", K.INK_SOFT,
                    (self.card.centerx, self.card.y + 44))
        self._draw_tools(surf)
        self._draw_canvas(surf)
        self._draw_right(surf)
        self._draw_footer(surf)

    def _btn(self, surf, rect, label, key, on=False, icon=None, lit=None):
        hot = rect.collidepoint(pygame.mouse.get_pos()) if pygame.display.get_surface() else False
        if on:
            K.row_cursor(surf, rect, self.t)
        else:
            K.well(surf, rect, hot=hot)
        if icon:
            _tool_icon(surf, icon, (rect.x + 26, rect.centery))
        K.blit_text(surf, K.font(15, True), label, K.INK if on else K.INK_SOFT,
                    (rect.x + 46, rect.centery), align="left")
        kx = rect.right - 8
        if key:
            kf = K.font(12, True)
            kw = kf.size(key)[0] + 12
            kr = pygame.Rect(rect.right - kw - 8, rect.centery - 10, kw, 20)
            pygame.draw.rect(surf, K.WOOD, kr, border_radius=6)
            K.blit_text(surf, kf, key, K.CREAM_HI, kr.center)
            kx = kr.x - 4
        if lit is not None:                              # an on/off lamp before the key
            c = (kx - 6, rect.centery)
            pygame.draw.circle(surf, K.WOOD_DK, c, 6)
            pygame.draw.circle(surf, K.LEAF if lit else K.WELL, c, 4)
            if lit:
                pygame.draw.circle(surf, (214, 244, 190), (c[0] - 1, c[1] - 1), 1)

    def _draw_tools(self, surf):
        K.blit_text(surf, K.font(16, True), "Tools", K.SPROUT, (self.btns["pencil"].x + 4, 100),
                    align="left")
        for tid, lab, k in TOOLS:
            self._btn(surf, self.btns[tid], lab, k, on=self.tool == tid, icon=tid)
        self._btn(surf, self.btns["mirror"], "Mirror  " + ("on" if self.mirror else "off"), "M",
                  icon="mirror", lit=self.mirror)
        self._btn(surf, self.btns["grid"], "Grid  " + ("on" if self.grid else "off"), "G",
                  icon="grid", lit=self.grid)
        self._btn(surf, self.btns["undo"], "Undo", "Z", icon="undo")
        self._btn(surf, self.btns["redo"], "Redo", "Y", icon="redo")
        self._btn(surf, self.btns["clear"], "Clear canvas", "C", icon="clear")

    def _draw_canvas(self, surf):
        cv = self.canvas
        # the easel's wooden frame + a soft shadow
        sh = pygame.Surface((cv.w + 30, cv.h + 30), pygame.SRCALPHA)
        pygame.draw.rect(sh, (40, 20, 30, 70), sh.get_rect(), border_radius=10)
        surf.blit(sh, (cv.x - 11, cv.y - 7))
        frame = cv.inflate(22, 22)
        pygame.draw.rect(surf, K.WOOD, frame, border_radius=8)
        pygame.draw.rect(surf, K.WOOD_DK, frame, 2, border_radius=8)
        pygame.draw.rect(surf, (168, 120, 84), frame.inflate(-8, -8), 2, border_radius=6)
        art = self._img(self.CELL)
        surf.blit(art, cv.topleft)
        if self.grid:
            lay = pygame.Surface(cv.size, pygame.SRCALPHA)
            for i in range(1, N):
                a = 60 if i % 4 == 0 else 26
                pygame.draw.line(lay, (90, 70, 60, a), (i * self.CELL, 0), (i * self.CELL, cv.h))
                pygame.draw.line(lay, (90, 70, 60, a), (0, i * self.CELL), (cv.w, i * self.CELL))
            surf.blit(lay, cv.topleft)
        if self.mirror:
            mx = cv.x + cv.w // 2
            for yy in range(cv.y, cv.bottom, 10):
                pygame.draw.line(surf, (228, 128, 150), (mx, yy), (mx, min(cv.bottom, yy + 5)), 2)
        # line preview
        if self.tool == "line" and self.line_a is not None:
            lay = pygame.Surface(cv.size, pygame.SRCALPHA)
            tgt = (self.cx, self.cy)
            cells = self.cells_between(self.line_a, tgt)
            if self.mirror:
                cells += [(N - 1 - x, y) for x, y in cells]
            for x, y in cells:
                pygame.draw.rect(lay, RGB[self.color] + (150,),
                                 (x * self.CELL, y * self.CELL, self.CELL, self.CELL))
            surf.blit(lay, cv.topleft)
            ax, ay = self.line_a
            pygame.draw.rect(surf, (228, 128, 150), (cv.x + ax * self.CELL, cv.y + ay * self.CELL,
                                                     self.CELL, self.CELL), 2)
        # cursor (+ its mirror twin)
        pulse = 0.5 + 0.5 * math.sin(self.t * 6)
        rim = tuple(int(a + (b - a) * pulse) for a, b in zip(K.GOLD_RIM, (255, 236, 150)))
        spots = [(self.cx, self.cy)]
        if self.mirror and self.cx != N - 1 - self.cx:
            spots.append((N - 1 - self.cx, self.cy))
        for i, (x, y) in enumerate(spots):
            r = pygame.Rect(cv.x + x * self.CELL - 2, cv.y + y * self.CELL - 2,
                            self.CELL + 4, self.CELL + 4)
            pygame.draw.rect(surf, K.WOOD_DK, r, 3 if i == 0 else 1, border_radius=4)
            pygame.draw.rect(surf, rim, r.inflate(-2, -2), 2 if i == 0 else 1, border_radius=3)
        # status line
        txt = self.msg if self.msg_t > 0 else self._tip()
        col = K.SPROUT if self.msg_t > 0 else K.INK_SOFT
        K.blit_text(surf, K.font(15, True), txt, col, (cv.centerx, cv.bottom + 34))

    def _tip(self):
        return {"pencil": "Pencil: click or Space to paint - right-click erases",
                "eraser": "Eraser: back to bare canvas",
                "fill": "Fill: pours the colour over a whole area",
                "picker": "Picker: grab a colour from your painting",
                "line": ("Line: click the end point" if self.line_a is not None
                         else "Line: click the start, then the end")}.get(self.tool, "")

    def _draw_right(self, surf):
        rx = self.swatch[0].x
        K.blit_text(surf, K.font(16, True), "Palette", K.SPROUT, (rx + 2, 100), align="left")
        for i, r in enumerate(self.swatch):
            sel = i == self.color
            pygame.draw.rect(surf, K.GOLD_RIM if sel else K.WELL_LINE, r.inflate(6, 6), 0 if sel else 2,
                             border_radius=9)
            pygame.draw.rect(surf, RGB[i], r, border_radius=7)
            if i == 0:                                   # bare canvas: a little weave
                pygame.draw.line(surf, K.WELL_LINE, (r.x + 8, r.bottom - 8), (r.right - 8, r.y + 8), 2)
            if sel:
                pygame.draw.rect(surf, K.WOOD_DK, r, 2, border_radius=7)
        # current colour + name
        cur = pygame.Rect(rx, 272, 60, 44)
        K.well(surf, cur.inflate(8, 8))
        pygame.draw.rect(surf, RGB[self.color], cur, border_radius=6)
        K.blit_text(surf, K.font(18, True), PALETTE[self.color][0], K.INK, (cur.right + 16, cur.y + 14),
                    align="left")
        K.blit_text(surf, K.font(12, True), "Q / E  or  wheel", K.INK_SOFT,
                    (cur.right + 16, cur.y + 34), align="left")
        # preview: how it will look framed on the wall
        pv = pygame.Rect(rx + 10, 346, 72, 72)
        pygame.draw.line(surf, K.WOOD_DK, (pv.centerx, pv.y - 20), (pv.x + 8, pv.y - 9), 1)
        pygame.draw.line(surf, K.WOOD_DK, (pv.centerx, pv.y - 20), (pv.right - 8, pv.y - 9), 1)
        pygame.draw.circle(surf, K.GOLD_RIM, (pv.centerx, pv.y - 20), 3)      # the nail
        fr = pv.inflate(18, 18)
        pygame.draw.rect(surf, (158, 112, 64), fr, border_radius=3)
        pygame.draw.rect(surf, (104, 68, 46), fr, 2, border_radius=3)
        pygame.draw.rect(surf, (214, 172, 110), fr.inflate(-6, -6), 1)
        surf.blit(self._img(3), pv.topleft)
        gal = len(getattr(self.g, "art_gallery", []) or [])
        tx = fr.right + 16
        K.blit_text(surf, K.font(15, True), "On the wall", K.INK, (tx, pv.y + 10), align="left")
        K.blit_text(surf, K.font(13, True), f"Gallery: {gal} artwork" + ("" if gal == 1 else "s"),
                    K.INK_SOFT, (tx, pv.y + 34), align="left")
        K.blit_text(surf, K.font(12, True), "Paintings in the house", K.INK_FAINT,
                    (tx, pv.y + 54), align="left")
        K.blit_text(surf, K.font(12, True), "can show any of them", K.INK_FAINT,
                    (tx, pv.y + 70), align="left")
        self._btn(surf, self.btns["save"], "Save to easel", "S", icon="save")
        self._btn(surf, self.btns["hang"], "Hang on the wall", "H", icon="hang")
        if self.dirty:
            K.blit_text(surf, K.font(12, True), "unsaved changes", K.GOLD_TXT,
                        (self.btns["save"].right - 60, self.btns["save"].y - 10))

    def _draw_footer(self, surf):
        y = self.card.bottom - 30
        pills = [("Arrows", "Move"), ("Space", "Paint"), ("Tab", "Tool"), ("Q/E", "Colour"),
                 ("Esc", "Done")]
        f = K.font(13, True)
        widths = []
        for k, lab in pills:
            widths.append(f.size(k)[0] + f.size(lab)[0] + 44)
        x = self.card.centerx - (sum(widths) + 10 * (len(widths) - 1)) // 2
        for (k, lab), w in zip(pills, widths):
            K.key_pill(surf, k, lab, (x + w // 2, y), fnt=f)
            x += w + 10
