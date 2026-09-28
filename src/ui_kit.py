"""Shared "cosy parchment" UI kit: the look of the title menu and the
character creator (cream card, wooden rim, folded ribbon title, gold row
highlight), plus text helpers that keep labels optically centred.

Every full-screen page / modal panel should draw with these so the whole game
reads as one set.  The in-world HUD (clock card, hotbar, minimap) keeps its
dark-plum cards; only panels you *open* are parchment.

Nothing here imports game modules, so any file may import it.
"""
import math
import pygame

# ---- palette --------------------------------------------------------------
WOOD = (138, 94, 64)
WOOD_DK = (104, 68, 46)
CREAM = (250, 238, 212)
CREAM_HI = (255, 250, 238)
WELL = (240, 224, 194)          # recessed parchment: value boxes, list rows, tracks
WELL_LINE = (214, 190, 160)     # thin rules / well outlines
INK = (74, 44, 36)              # main text on parchment
INK_SOFT = (128, 92, 70)        # secondary text
INK_FAINT = (176, 150, 128)     # placeholders / disabled
SPROUT = (92, 150, 70)          # markers, section heads
LEAF = (122, 182, 92)           # progress fills / ON
GOLD_RIM = (214, 160, 70)       # selection rim
HILITE = (252, 226, 164)        # selection band
WARN = (196, 72, 60)
GOLD_TXT = (170, 116, 30)       # gold amounts on parchment
HEART = (228, 128, 150)
RIBBON = (250, 236, 206)
RIBBON_LINE = (196, 140, 100)
RIBBON_TAIL = (206, 150, 110)
P_COL = [(206, 92, 80), (78, 118, 200)]   # player 1 / player 2 accents

CONTINUE_HINT = "SPACE / RETURN  -  continue"

_CACHE = {}
_FONTS = {}


def font(size, bold=False):
    """Cached consolas font (the game's UI face)."""
    key = (size, bold)
    f = _FONTS.get(key)
    if f is None:
        f = _FONTS[key] = pygame.font.SysFont("consolas", size, bold=bold)
    return f


def fit_font(text, maxw, sizes=(20, 18, 16, 14, 13, 12, 11, 10), bold=False):
    """Largest consolas size in ``sizes`` in which ``text`` fits ``maxw``."""
    for s in sizes:
        f = font(s, bold)
        if f.size(text)[0] <= maxw:
            return f
    return font(sizes[-1], bold)


# ---- text -----------------------------------------------------------------
def blit_text(surf, fnt, text, color, pos, align="center"):
    """Blit ``text`` with its capital letters optically centred on ``pos[1]``
    (the line box has room below for descenders, so centring the rendered
    surface puts letters a little high).  ``align``: pos[0] is the text's
    centre / left / right.  Returns the rect actually covered."""
    t = fnt.render(text, True, color)
    cap = fnt.metrics("H")[0][3]
    y = pos[1] - fnt.get_ascent() + (cap + 1) // 2
    if align == "left":
        x = pos[0]
    elif align == "right":
        x = pos[0] - t.get_width()
    else:
        x = pos[0] - t.get_width() // 2
    surf.blit(t, (x, y))
    return pygame.Rect(x, y, t.get_width(), t.get_height())


def outlined(fnt, text, color, outline=(40, 24, 30), px=2):
    """Text surface with a solid outline: readable on any ground (snow, water)."""
    key = ("ol", id(fnt), text, color, outline, px)
    s = _CACHE.get(key)
    if s is not None:
        return s
    body = fnt.render(text, True, color)
    edge = fnt.render(text, True, outline)
    w, h = body.get_width() + px * 2, body.get_height() + px * 2
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for ox in range(-px, px + 1):
        for oy in range(-px, px + 1):
            if ox or oy:
                s.blit(edge, (px + ox, px + oy))
    s.blit(body, (px, px))
    if len(_CACHE) > 600:
        _CACHE.clear()
    _CACHE[key] = s
    return s


def wrap(fnt, text, maxw):
    """Greedy word wrap -> list of lines that each fit ``maxw`` px."""
    out = []
    for para in str(text).split("\n"):
        words = para.split(" ")
        cur = ""
        for w in words:
            trial = w if not cur else cur + " " + w
            if fnt.size(trial)[0] <= maxw or not cur:
                cur = trial
            else:
                out.append(cur)
                cur = w
        out.append(cur)
    return out


def ellipsize(fnt, text, maxw):
    """Trim ``text`` with '...' so it fits ``maxw`` px."""
    if fnt.size(text)[0] <= maxw:
        return text
    while text and fnt.size(text + "...")[0] > maxw:
        text = text[:-1]
    return text.rstrip() + "..."


# ---- surfaces -------------------------------------------------------------
def card_surface(w, h, radius=18):
    """Parchment card with a wooden rim and a soft drop shadow (cached).
    The returned surface is (w + 8, h + 10); blit it at (x - 4, y - 2)."""
    key = ("card", w, h, radius)
    s = _CACHE.get(key)
    if s is None:
        s = pygame.Surface((w + 8, h + 10), pygame.SRCALPHA)
        pygame.draw.rect(s, (40, 20, 30, 90), (7, 9, w, h), border_radius=radius)   # shadow
        pygame.draw.rect(s, WOOD, (4, 2, w, h), border_radius=radius)                # rim
        pygame.draw.rect(s, WOOD_DK, (4, 2, w, h), 2, border_radius=radius)
        ir = max(4, radius - 5)
        pygame.draw.rect(s, CREAM, (11, 9, w - 14, h - 14), border_radius=ir)
        pygame.draw.rect(s, CREAM_HI, (19, 13, w - 30, 4), border_radius=2)          # sheen
        _CACHE[key] = s
    return s


def draw_card(surf, rect, radius=18):
    rect = pygame.Rect(rect)
    surf.blit(card_surface(rect.w, rect.h, radius), (rect.x - 4, rect.y - 2))
    return rect


def dim(surf, alpha=110, color=(30, 20, 40)):
    """Soft full-screen dim behind a modal."""
    key = ("dim", surf.get_size(), alpha, color)
    s = _CACHE.get(key)
    if s is None:
        s = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        s.fill((*color, alpha))
        _CACHE[key] = s
    surf.blit(s, (0, 0))


def ribbon(surf, fnt, title, center, color=INK):
    """The title screen's folded parchment ribbon, centred on ``center``."""
    tw = fnt.size(title)[0]
    rw, rh = tw + 72, fnt.get_height() + 14
    rib = pygame.Rect(0, 0, rw, rh)
    rib.center = center
    ry = rib.y
    for side in (-1, 1):
        if side < 0:
            pts = [(rib.x - 22, ry + 6), (rib.x + 4, ry + 6), (rib.x + 4, ry + rh + 6),
                   (rib.x - 22, ry + rh + 6), (rib.x - 12, ry + rh // 2 + 6)]
        else:
            pts = [(rib.right + 22, ry + 6), (rib.right - 4, ry + 6),
                   (rib.right - 4, ry + rh + 6), (rib.right + 22, ry + rh + 6),
                   (rib.right + 12, ry + rh // 2 + 6)]
        pygame.draw.polygon(surf, RIBBON_TAIL, pts)
    pygame.draw.rect(surf, RIBBON, rib, border_radius=6)
    pygame.draw.rect(surf, RIBBON_LINE, rib, 2, border_radius=6)
    blit_text(surf, fnt, title, color, rib.center)
    return rib


def modal(surf, rect, title=None, title_font=None, dim_alpha=None):
    """Parchment card + (optional) ribbon title straddling its top edge.
    Leave ~40 px of top padding inside ``rect`` for the ribbon."""
    if dim_alpha:
        dim(surf, dim_alpha)
    rect = draw_card(surf, rect)
    if title:
        f = title_font or font(30, True)
        ribbon(surf, f, title, (rect.centerx, rect.y + 2))
    return rect


def well(surf, rect, hot=False, radius=8):
    """Recessed parchment box (value boxes, list rows, input fields)."""
    pygame.draw.rect(surf, CREAM_HI if hot else WELL, rect, border_radius=radius)
    pygame.draw.rect(surf, GOLD_RIM if hot else WELL_LINE, rect, 2, border_radius=radius)


def row_cursor(surf, band, t=0.0):
    """Keyboard highlight behind a row: warm band, pulsing rim, sprout marker."""
    band = pygame.Rect(band)
    pulse = 0.5 + 0.5 * math.sin(t * 5)
    pygame.draw.rect(surf, HILITE, band, border_radius=10)
    rim = tuple(int(a + (b - a) * pulse) for a, b in zip(GOLD_RIM, (240, 192, 104)))
    pygame.draw.rect(surf, rim, band, 2, border_radius=10)
    mx, my = band.x + 5, band.centery
    pygame.draw.polygon(surf, SPROUT, [(mx, my - 5), (mx + 6, my), (mx, my + 5)])


def divider(surf, cx, y, half, heart=True):
    """Thin rule, optionally with a little heart in the middle."""
    gap = 14 if heart else 0
    pygame.draw.line(surf, WELL_LINE, (cx - half, y), (cx - gap, y), 2)
    pygame.draw.line(surf, WELL_LINE, (cx + gap, y), (cx + half, y), 2)
    if heart:
        for dx in (-3, 3):
            pygame.draw.circle(surf, HEART, (cx + dx, y - 2), 4)
        pygame.draw.polygon(surf, HEART, [(cx - 7, y - 1), (cx + 7, y - 1), (cx, y + 6)])


def button(surf, rect, label, selected=False, fnt=None, t=0.0):
    """Parchment button with a wooden rim (the title menu's look, static)."""
    rect = pygame.Rect(rect)
    fnt = fnt or font(18, True)
    sh = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    pygame.draw.rect(sh, (40, 20, 30, 80), sh.get_rect(), border_radius=12)
    surf.blit(sh, (rect.x + 2, rect.y + 4))
    pygame.draw.rect(surf, WOOD, rect, border_radius=12)
    face = (255, 224, 150) if selected else CREAM
    inner = rect.inflate(-6, -6)
    pygame.draw.rect(surf, face, inner, border_radius=9)
    pygame.draw.rect(surf, CREAM_HI, (inner.x + 5, inner.y + 3, inner.w - 10, 3), border_radius=2)
    blit_text(surf, fnt, label, INK if selected else (110, 78, 60), rect.center)
    return rect


def tabs(surf, rects, labels, active, fnt_sizes=(16, 14, 13, 12, 11, 10), t=0.0):
    """A row of parchment tabs; each label shrinks to fit its own tab (and is
    ellipsized as a last resort) so labels never spill into a neighbour."""
    for i, (r, lab) in enumerate(zip(rects, labels)):
        r = pygame.Rect(r)
        on = i == active
        pygame.draw.rect(surf, WOOD, r, border_radius=8)
        pygame.draw.rect(surf, (255, 224, 150) if on else WELL, r.inflate(-4, -4), border_radius=6)
        f = fit_font(lab, r.w - 10, fnt_sizes, bold=True)
        blit_text(surf, f, ellipsize(f, lab, r.w - 8), INK if on else INK_SOFT, r.center)


def key_pill(surf, key, label, center, accent=None, fnt=None, alpha=235):
    """The one world-prompt style: cream pill with a wooden rim, the key in a
    small inset box, then the action - e.g. [SPACE] Give.  ``center`` is the
    pill's centre; returns its rect (callers can nudge it clear of others)."""
    fnt = fnt or font(14, True)
    ktxt = fnt.render(str(key), True, CREAM_HI)
    ltxt = fnt.render(str(label), True, INK) if label else None
    kw = ktxt.get_width() + 12
    w = kw + (ltxt.get_width() + 18 if ltxt else 8)
    h = max(24, fnt.get_height() + 10)
    r = pygame.Rect(0, 0, w, h)
    r.center = (int(center[0]), int(center[1]))
    pill = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(pill, (*WOOD, alpha), pill.get_rect(), border_radius=h // 2)
    pygame.draw.rect(pill, (*CREAM, alpha), pill.get_rect().inflate(-4, -4), border_radius=h // 2 - 2)
    surf.blit(pill, r.topleft)
    kbox = pygame.Rect(r.x + 5, r.y + 4, kw, h - 8)
    pygame.draw.rect(surf, accent or WOOD, kbox, border_radius=6)
    blit_text(surf, fnt, str(key), CREAM_HI, kbox.center)
    if ltxt:
        blit_text(surf, fnt, str(label), INK, (kbox.right + 8, r.centery), align="left")
    return r


def continue_hint(surf, center, t=0.0, fnt=None, text=CONTINUE_HINT, color=INK_SOFT):
    """The standard 'press to continue' line; pulses gently but stays legible."""
    fnt = fnt or font(15, True)
    a = int(228 + 27 * math.sin(t * 3))          # gentle: never fades out of reach
    s = fnt.render(text, True, color)
    s.set_alpha(a)
    surf.blit(s, (center[0] - s.get_width() // 2, center[1] - s.get_height() // 2))


def pill(surf, rect, fill, outline=None, radius=None, alpha=255):
    """Rounded pill whose fill and outline share the same radius (no square
    corners poking out)."""
    rect = pygame.Rect(rect)
    radius = rect.h // 2 if radius is None else radius
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(s, (*fill[:3], alpha), s.get_rect(), border_radius=radius)
    if outline:
        pygame.draw.rect(s, (*outline[:3], 255), s.get_rect(), 2, border_radius=radius)
    surf.blit(s, rect.topleft)
    return rect


def spread_rects(rects, pad=2, bounds=None):
    """Nudge overlapping rects apart vertically (in place, in list order: later
    ones move up).  Used for floating texts / tags anchored at similar spots."""
    placed = []
    for r in rects:
        moved = True
        guard = 0
        while moved and guard < 40:
            moved = False
            guard += 1
            for p in placed:
                if r.colliderect(p.inflate(pad * 2, pad * 2)):
                    r.bottom = p.top - pad
                    moved = True
        if bounds is not None and r.top < bounds.top:
            r.top = bounds.top
        placed.append(r)
    return rects
