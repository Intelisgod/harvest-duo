"""The Record Player: a real remote for the Spotify app on this PC.

Interact with a placed Record Player in the house. Switching it on drops the
needle for real: Spotify opens if it isn't running (on your saved playlist's
page, if you pasted one) and plays -- it carries on where it left off -- and
the game's own music ducks down while it does. The screen shows the record
spinning in the piece's colour and what Spotify is playing.

  Action        play / pause            Left / Right  previous / next song
  O             open Spotify (on the saved playlist)
  P             paste a playlist link
  X             switch it off (pauses Spotify)
  Esc / B       walk away (the music keeps playing)
  The three round buttons and the key pills are clickable too.

Pure UI: every Spotify action goes through ``game._records_*`` (RecordsMixin,
systems/records_system.py) and the status comes from ``spotify.REMOTE``, so the
LAN client runs this screen for its own PC's Spotify.
"""
import math
import random
import unicodedata
import pygame

from .settings import SCREEN_W, P1_KEYS, P2_KEYS
from . import ui_kit as K
from . import spotify

RPM_DEG = 200.0                 # 33 1/3 rpm, in degrees per second
PW, PH = 1000, 540              # panel size
ARM_LEN = 236
ARM_REST = 90.0                 # tonearm angle (deg, screen coords: 90 = straight down)

_WOOD = (176, 124, 84)
_WOOD_TOP = (190, 138, 96)
_WOOD_DK = (128, 86, 58)
_INLAY = (150, 104, 70)
_NOTE_COLS = ((150, 110, 220), (230, 120, 160), (90, 160, 220), (240, 170, 70))
_CACHE = {}


def _dk(c, f=0.7):
    return tuple(max(0, int(v * f)) for v in c[:3])


def _lt(c, f=1.2):
    return tuple(min(255, int(v * f)) for v in c[:3])


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def piece_tint(fr, default=(200, 70, 70)):
    from . import furniture as F
    try:
        return F.PALETTE[fr.ci % len(F.PALETTE)][1]
    except Exception:
        return default


# ------------------------------------------------------------------ song fonts
# Spotify titles can be anything (Thai, Japanese, accents, emoji). Consolas --
# the UI's face -- has no Thai at all, so song text picks the first system face
# that has every glyph; characters no face has are dropped rather than drawn as
# boxes (Segoe UI Emoji draws emoji as clean one-colour outlines). The toasts
# (systems/ui_system.py) use the same picker for text Consolas can't draw.
_SONG_FACES = ("consolas", "leelawadeeui", "leelawadee", "tahoma", "segoeui",
               "yugothicui", "malgungothic", "microsoftyahei", "nirmalaui",
               "segoeuiemoji", "segoeuisymbol")
PLACEHOLDER = "♪"          # a song title nothing can draw (Consolas has the note)
_PATHS = {}
_GLYPHS = {}
_FONTS = {}


def _face_path(face, bold=False):
    key = (face, bold)
    if key not in _PATHS:
        try:
            _PATHS[key] = pygame.font.match_font(face, bold=bold)
        except Exception:
            _PATHS[key] = None
    return _PATHS[key]


def _font_at(path, size, bold=False):
    key = (path, size, bold)
    f = _FONTS.get(key)
    if f is None:
        f = _FONTS[key] = pygame.font.Font(path, size)
    return f


def _pixels(s):
    try:
        return pygame.image.tobytes(s, "RGBA")
    except AttributeError:                            # pygame < 2.3
        return pygame.image.tostring(s, "RGBA")


_TOFU_REFS = ("͸", "")   # unassigned + private use: the 'tofu' box
                                    # (Segoe UI Symbol has a real U+E000 icon)


def _has_glyph(face, ch):
    """Does ``face`` draw ``ch``? (a missing glyph renders exactly like an
    unassigned code point: the font's 'tofu' box)."""
    key = (face, ch)
    v = _GLYPHS.get(key)
    if v is None:
        v = False
        path = _face_path(face)
        if path:
            try:
                f = _font_at(path, 16)
                a = f.render(ch, True, (255, 255, 255))
                pa = _pixels(a)
                v = True
                for ref in _TOFU_REFS:
                    b = f.render(ref, True, (255, 255, 255))
                    if a.get_size() == b.get_size() and pa == _pixels(b):
                        v = False
                        break
            except Exception:
                v = False
        _GLYPHS[key] = v
    return v


def clean_text(text):
    """Drop invisible format characters (zero-width joiners, emoji variation
    selectors...) and collapse whitespace."""
    out = []
    for ch in str(text or ""):
        if unicodedata.category(ch) == "Cf" or 0xFE00 <= ord(ch) <= 0xFE0F:
            continue
        out.append(ch)
    return " ".join("".join(out).split())


def song_face(text, placeholder=PLACEHOLDER):
    """(face, text): the first face in _SONG_FACES with every glyph of
    ``text``; otherwise the one missing the fewest, with those dropped. Text
    with nothing drawable left becomes ``placeholder`` (in Consolas)."""
    text = clean_text(text)
    need = {c for c in text if ord(c) > 0x7E and not c.isspace()}
    if not need:
        return "consolas", (text or placeholder)
    best, best_miss = "consolas", None
    for face in _SONG_FACES:
        if not _face_path(face):
            continue
        miss = sum(1 for c in need if not _has_glyph(face, c))
        if miss == 0:
            return face, text
        if best_miss is None or miss < best_miss:
            best, best_miss = face, miss
    kept = "".join(c for c in text if ord(c) <= 0x7E or c.isspace() or _has_glyph(best, c))
    kept = " ".join(kept.split())
    if not kept.strip(" -"):
        return "consolas", placeholder           # only tofu (and dashes) left
    return best, kept


def consolas_ok(text):
    """True if the UI face can draw ``text`` (toasts / the log use it)."""
    return all(ord(c) <= 0x7E or _has_glyph("consolas", c) for c in clean_text(text))


def song_font(face, size, bold=True):
    if face == "consolas":
        return K.font(size, bold)
    path = _face_path(face, bold) or _face_path(face)
    if not path:
        return K.font(size, bold)
    return _font_at(path, size, bold)


def _breakable(text, i):
    """May a line break before text[i]? (never in front of a combining mark,
    e.g. a Thai vowel or tone mark sitting on the previous letter)."""
    return i < len(text) and unicodedata.combining(text[i]) == 0 and \
        unicodedata.category(text[i]) != "Mn"


def wrap_lines(fnt, text, maxw, max_lines=2):
    """Greedy wrap into at most ``max_lines`` lines: break at a space when one
    fits, else mid-word (Thai / CJK titles have no spaces); the last line is
    ellipsized if text is left over."""
    lines = []
    s = str(text).strip()
    while s and len(lines) < max_lines:
        if fnt.size(s)[0] <= maxw:
            lines.append(s)
            s = ""
            break
        fit = 1
        for j in range(1, len(s) + 1):            # longest prefix that fits
            if fnt.size(s[:j])[0] > maxw:
                break
            fit = j
        cut = s.rfind(" ", 0, fit + 1)
        if cut <= 0:
            cut = fit
            while cut > 1 and not _breakable(s, cut):
                cut -= 1
        lines.append(s[:cut].rstrip())
        s = s[cut:].lstrip()
    if s and lines:
        lines[-1] = K.ellipsize(fnt, lines[-1] + " " + s, maxw)
    return lines or [""]


def song_layout(song, maxw, h, live):
    """The song well's text, laid out: [(rendered line, y offset)] for
    (artist, title) in a ``maxw`` x ``h`` well -- the title at the largest
    size that fits (else wrapped to two lines), the artist below it.
    RecordScreen caches it per song, so this runs once per song, not per frame."""
    artist, title = song
    tcol = K.INK if live else K.INK_SOFT
    acol = K.INK_SOFT if live else K.INK_FAINT
    face, title = song_face(title or "")
    lines, tf = None, None
    for size in (30, 28, 26, 24):
        tf = song_font(face, size, True)
        if tf.size(title)[0] <= maxw:
            lines = [title]
            break
    if lines is None:
        tf = song_font(face, 22, True)
        lines = wrap_lines(tf, title, maxw, 2)
    afont = None
    aface, artist = song_face(artist or "", placeholder="")
    if artist:
        for size in (18, 17, 16, 15):
            afont = song_font(aface, size, False)
            if afont.size(artist)[0] <= maxw:
                break
        artist = K.ellipsize(afont, artist, maxw)
    lh = tf.get_linesize()
    block = lh * len(lines) + (afont.get_linesize() + 6 if afont else 0)
    y = (h - block) // 2
    out = []
    for ln in lines:
        if ln:
            out.append((tf.render(ln, True, tcol), y))
        y += lh
    if afont and artist:
        out.append((afont.render(artist, True, acol), y + 6))
    return out


# ------------------------------------------------------------------ small art
def record_icon(tint=None, size=28):
    """A little vinyl record (toasts, the HUD)."""
    tint = tuple((tint or (200, 70, 70))[:3])
    key = ("icon", tint, size)
    s = _CACHE.get(key)
    if s is None:
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        c = (size // 2, size // 2)
        r = size // 2 - 1
        pygame.draw.circle(s, (22, 21, 27), c, r)
        pygame.draw.circle(s, (54, 53, 62), c, r - 3, 1)
        pygame.draw.circle(s, (54, 53, 62), c, r - 6, 1)
        pygame.draw.circle(s, tint, c, max(2, r // 3))
        pygame.draw.circle(s, (240, 240, 244), c, 1)
        pygame.draw.arc(s, (150, 150, 164), (c[0] - r + 2, c[1] - r + 2, 2 * r - 4, 2 * r - 4),
                        math.radians(100), math.radians(150), 2)
        _CACHE[key] = s
    return s


def _heart(w, col):
    """A small smooth heart ``w`` px wide (drawn 4x and scaled down)."""
    k = 4
    W = w * k
    s = pygame.Surface((W, W), pygame.SRCALPHA)
    r = W * 0.25                                      # lobe radius
    cy = W * 0.36                                     # lobe centres
    for cx in (W / 2 - r * 0.95, W / 2 + r * 0.95):
        pygame.draw.circle(s, col, (cx, cy), r)
    # the point: from the lobes' outer sides (a little below centre) to the
    # tip, closed up to the lobe centre line so the notch has no pinhole
    pygame.draw.polygon(s, col, [(W / 2 - r * 0.95, cy),
                                 (W / 2 + r * 0.95, cy),
                                 (W / 2 + r * 1.86, cy + r * 0.42),
                                 (W / 2, W * 0.94),
                                 (W / 2 - r * 1.86, cy + r * 0.42)])
    return pygame.transform.smoothscale(s, (w, w))


def _vinyl(R, tint):
    """The record (cached per size + label colour); it is rotated per frame."""
    key = ("vinyl", R, tint)
    s = _CACHE.get(key)
    if s is not None:
        return s
    D = R * 2 + 4
    s = pygame.Surface((D, D), pygame.SRCALPHA)
    c = (D // 2, D // 2)
    lr = int(R * 0.34)
    pygame.draw.circle(s, (20, 19, 25), c, R)
    for i, rr in enumerate(range(R - 6, lr + 8, -3)):                 # grooves
        pygame.draw.circle(s, (33, 32, 40) if i % 2 else (25, 24, 31), c, rr, 1)
    for k in (0.55, 0.71, 0.86):                                      # gaps between songs
        pygame.draw.circle(s, (44, 43, 53), c, int(R * k), 2)
    pygame.draw.circle(s, (64, 62, 74), c, R, 2)
    pygame.draw.circle(s, (14, 13, 18), c, lr + 6)                    # run-out groove
    # the label, in the piece's colour: its print shows the record turning
    pygame.draw.circle(s, tint, c, lr)
    pygame.draw.circle(s, _dk(tint, 0.72), c, lr, 2)
    pygame.draw.circle(s, _lt(tint, 1.18), c, int(lr * 0.72), 1)
    light = sum(tint) > 470
    ink = (70, 44, 36) if light else (255, 246, 232)
    t1 = K.font(max(9, lr // 4), True).render("HARVEST DUO", True, ink)
    s.blit(t1, t1.get_rect(center=(c[0], c[1] - int(lr * 0.46))))
    t2 = K.font(max(8, lr // 6), True).render("33 1/3", True, ink)
    s.blit(t2, t2.get_rect(center=(c[0], c[1] + int(lr * 0.50))))
    hrt = _heart(max(9, lr // 3), ink)                                # a tiny heart
    s.blit(hrt, hrt.get_rect(center=(c[0] + int(lr * 0.46), c[1] + 1)))
    pygame.draw.circle(s, (232, 232, 238), c, 6)                      # spindle
    pygame.draw.circle(s, (130, 130, 142), c, 6, 1)
    pygame.draw.circle(s, (255, 255, 255), (c[0] - 2, c[1] - 2), 2)
    _CACHE[key] = s
    return s


def _sheen(R):
    """Static light reflections on the record (they stay put while it spins)."""
    key = ("sheen", R)
    s = _CACHE.get(key)
    if s is not None:
        return s
    D = R * 2 + 4
    s = pygame.Surface((D, D), pygame.SRCALPHA)
    c = D // 2
    lr = int(R * 0.34) + 8
    # two soft reflections opposite each other: stacked wedges, brightest in
    # the middle, fading out to the sides
    for mid, half, alpha in ((-48, 17, 7), (132, 14, 6)):
        for layer in range(4, 0, -1):
            w = half * layer / 4
            pts = []
            for k in range(9):
                a = math.radians(mid - w + 2 * w * k / 8)
                pts.append((c + math.cos(a) * (R - 4), c + math.sin(a) * (R - 4)))
            for k in range(8, -1, -1):
                a = math.radians(mid - w + 2 * w * k / 8)
                pts.append((c + math.cos(a) * lr, c + math.sin(a) * lr))
            layer_s = pygame.Surface((D, D), pygame.SRCALPHA)
            pygame.draw.polygon(layer_s, (255, 255, 255, alpha), pts)
            s.blit(layer_s, (0, 0))
    pygame.draw.arc(s, (255, 255, 255, 60), (4, 4, D - 8, D - 8), math.radians(35),
                    math.radians(80), 2)                     # glint on the rim
    _CACHE[key] = s
    return s


def _plinth(w, h):
    """The wooden turntable base (cached per size)."""
    key = ("plinth", w, h)
    s = _CACHE.get(key)
    if s is not None:
        return s
    s = pygame.Surface((w, h + 14), pygame.SRCALPHA)
    pygame.draw.rect(s, (40, 22, 26, 80), (6, 12, w - 6, h), border_radius=24)   # shadow
    pygame.draw.rect(s, _WOOD_DK, (0, 10, w, h), border_radius=24)               # front edge
    pygame.draw.rect(s, _WOOD, (0, 0, w, h), border_radius=24)
    top = pygame.Rect(10, 10, w - 20, h - 22)
    pygame.draw.rect(s, _WOOD_TOP, top, border_radius=18)
    rnd = random.Random(11)                                       # wood grain
    for i in range(14):
        y0 = 22 + i * (h - 44) / 13 + rnd.uniform(-4, 4)
        amp, ph = rnd.uniform(1.5, 4), rnd.uniform(0, 6)
        pts = [(x, y0 + math.sin(x / 38 + ph) * amp) for x in range(top.x + 8, top.right - 8, 12)]
        if len(pts) > 1:
            pygame.draw.lines(s, _mix(_WOOD_TOP, _WOOD_DK, 0.28), False, pts, 1)
    pygame.draw.rect(s, _INLAY, top, 2, border_radius=18)
    pygame.draw.line(s, _lt(_WOOD_TOP, 1.1), (top.x + 18, top.y + 3), (top.right - 18, top.y + 3), 2)
    _CACHE[key] = s
    return s


def _note(surf, x, y, col, alpha, size=10):
    """A little quaver drifting off the record."""
    s = pygame.Surface((size * 2 + 4, size * 3), pygame.SRCALPHA)
    hx, hy = size // 2 + 2, size * 3 - size // 2 - 2
    pygame.draw.ellipse(s, (*col, alpha), (hx - size // 2, hy - size // 3, size, size * 2 // 3))
    pygame.draw.line(s, (*col, alpha), (hx + size // 2 - 1, hy), (hx + size // 2 - 1, 2), 2)
    pygame.draw.line(s, (*col, alpha), (hx + size // 2 - 1, 2), (hx + size + 2, size // 2 + 2), 2)
    surf.blit(s, (int(x) - hx, int(y) - hy))


# ------------------------------------------------------------------ layout
def _layout():
    P = pygame.Rect((SCREEN_W - PW) // 2, 124, PW, PH)
    deck = pygame.Rect(P.x + 30, P.y + 58, 430, 420)
    c = (deck.x + 196, deck.y + 206)
    R = 158
    pivot = (deck.right - 56, deck.y + 64)
    # play angle: the angle that sets the needle on the outer grooves
    best = (99.0, ARM_REST)
    for k in range(0, 140):
        a = ARM_REST + k * 0.5
        ex = pivot[0] + math.cos(math.radians(a)) * ARM_LEN
        ey = pivot[1] + math.sin(math.radians(a)) * ARM_LEN
        d = abs(math.hypot(ex - c[0], ey - c[1]) - R * 0.88)
        if d < best[0]:
            best = (d, a)
    info = pygame.Rect(P.x + 500, P.y + 58, 470, 430)
    well = pygame.Rect(info.x, info.y + 26, info.w, 136)
    ty = well.bottom + 104
    return {"P": P, "deck": deck, "c": c, "R": R, "pivot": pivot, "arm_play": best[1],
            "info": info, "well": well, "status_y": well.bottom + 28,
            "buttons": {"prev": ((info.centerx - 106, ty), 31),
                        "play": ((info.centerx, ty), 41),
                        "next": ((info.centerx + 106, ty), 31)},
            "pills_y": ty + 76}


# ------------------------------------------------------------------ the screen
class RecordScreen:
    def __init__(self, game, pidx, piece, client=False, fresh=False):
        self.g = game
        self.pidx = pidx
        self.client = client            # LAN client: the power switch lives on the host
        self._fr = piece
        self.gx, self.gy = piece.gx, piece.gy
        self.L = _layout()
        self.clock = 0.0
        self.angle = random.uniform(0.0, 360.0)
        self.spin = 0.0                 # platter speed 0 .. 1
        self.arm = 0.0                  # tonearm 0 rest .. 1 on the record
        self.msg = "Dropping the needle..." if fresh else ""
        self.msg_t = 2.4 if fresh else 0.0
        self.flash = {}                 # button -> press highlight seconds
        self.hover = None
        self.notes = []                 # [x, y, vx, life, max, colour]
        self._note_t = 0.0
        self._held = {}                 # key -> clock of its last KEYDOWN
        self._pills = {}                # button -> Rect (from the last draw)
        self._song_cache = None         # (key, song_layout(...)) of the song shown

    # ---- data ----
    @property
    def p(self):
        return self.g.players[self.pidx]

    @property
    def fr(self):
        """The live piece (a LAN world resync replaces Placed objects)."""
        home = self.g.world.home_furniture
        if any(q is self._fr for q in home):
            return self._fr
        for q in home:
            if q.kind == "record_player" and q.gx == self.gx and q.gy == self.gy:
                self._fr = q
                return q
        try:                            # replaced AND moved: the one the game tracks
            live = self.g._records_piece()
        except Exception:
            live = None
        if live is not None:
            self._fr, self.gx, self.gy = live, live.gx, live.gy
            return live
        return self._fr

    @staticmethod
    def status():
        return spotify.REMOTE.status

    def spinning(self):
        st = self.status()
        return st.playing or (spotify.REMOTE.web and not st.running)

    def _say(self, text, secs=3.2):
        self.msg, self.msg_t = text, secs

    # ---- input ----
    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            last = self._held.get(e.key)
            self._held[e.key] = self.clock
            if last is not None and self.clock - last < 0.5:
                return                  # a held key's auto-repeat: one press only
            self.handle_key(e.key)
        elif e.type == pygame.KEYUP:
            self._held.pop(e.key, None)
        elif e.type == pygame.MOUSEMOTION:
            self.hover = self._hit(e.pos)
        elif e.type == pygame.MOUSEBUTTONDOWN and getattr(e, "button", 1) == 1:
            b = self._hit(e.pos)
            if b:
                self.press(b)

    def handle_key(self, key):
        if key in (P1_KEYS["action"], P2_KEYS["action"]):
            self.press("play")
        elif key in (P1_KEYS["left"], P2_KEYS["left"]):
            self.press("prev")
        elif key in (P1_KEYS["right"], P2_KEYS["right"]):
            self.press("next")
        elif key in (pygame.K_ESCAPE, pygame.K_b):
            self.g._records_close(self)
        elif key == pygame.K_o:
            self.press("open")
        elif key == pygame.K_p:
            self.press("paste")
        elif key == pygame.K_x:
            self.press("off")

    def press(self, b):
        """One control: "play", "prev", "next", "open", "paste" or "off"."""
        self.flash[b] = 0.22
        st = self.status()
        a = self.g.audio
        if b == "play":
            if not st.running and not spotify.REMOTE.web:
                self._say("Opening Spotify...")
            self.g._records_cmd("toggle")
            a.play("ui_select")
        elif b in ("prev", "next"):
            if not st.running and not spotify.REMOTE.web:
                self._say("Spotify isn't running -- press O to open it")
                a.play("error" if "error" in getattr(a, "sfx", {}) else "ui_move")
                return
            self.g._records_cmd(b)
            a.play("ui_move")
        elif b == "open":
            self._say("Opening Spotify...")
            self.g._records_cmd("open")
            a.play("ui_toggle")
        elif b == "paste":
            ok, text = self.g._records_paste()
            self._say(text, 4.0)
            a.play("ui_select" if ok else ("error" if "error" in getattr(a, "sfx", {})
                                           else "ui_move"))
        elif b == "off":
            self.g._records_power_off(self)

    def _hit(self, pos):
        for b, (c, r) in self.L["buttons"].items():
            if (pos[0] - c[0]) ** 2 + (pos[1] - c[1]) ** 2 <= r * r:
                return b
        for b, r in self._pills.items():
            if r.collidepoint(pos):
                return b
        return None

    # ---- update ----
    def update(self, dt):
        self.clock += dt
        self.msg_t = max(0.0, self.msg_t - dt)
        for k in list(self.flash):
            self.flash[k] -= dt
            if self.flash[k] <= 0:
                del self.flash[k]
        on_rec = self.spinning()
        # the arm swings over first, the platter spins up under it
        arm_to = 1.0 if (on_rec or spotify.REMOTE.launching) else 0.0
        self.arm += max(-dt * 1.6, min(dt * 1.6, arm_to - self.arm))
        spin_to = 1.0 if on_rec else 0.0
        rate = 1.3 if spin_to > self.spin else 0.8
        self.spin += max(-dt * rate, min(dt * rate, spin_to - self.spin))
        self.angle = (self.angle + RPM_DEG * self.spin * dt) % 360.0
        # music notes drift up off the record while it plays
        self._note_t -= dt
        if self.spin > 0.6 and self._note_t <= 0:
            self._note_t = random.uniform(0.45, 0.9)
            c, R = self.L["c"], self.L["R"]
            a = math.radians(random.uniform(200, 340))
            x, y = c[0] + math.cos(a) * R * 0.8, c[1] + math.sin(a) * R * 0.8
            life = random.uniform(1.6, 2.4)
            self.notes.append([x, y, random.uniform(-14, 14), life, life,
                               random.choice(_NOTE_COLS)])
        for n in self.notes:
            n[3] -= dt
            n[0] += n[2] * dt + math.sin(self.clock * 3 + n[4] * 7) * 0.4
            n[1] -= 34 * dt
        self.notes = [n for n in self.notes if n[3] > 0]

    # ---- draw ----
    def draw(self, surf):
        L = self.L
        K.dim(surf, 150)
        P = K.modal(surf, L["P"], "Record Player", K.font(28, True))
        K.blit_text(surf, K.font(14, True), f"{self.p.name} at the record player",
                    K.INK_SOFT, (P.centerx, P.y + 44))
        tint = piece_tint(self.fr)
        self._draw_deck(surf, tint)
        self._draw_info(surf, tint)
        K.divider(surf, P.centerx, P.bottom - 30, 170, heart=True)
        hint = ("Action play/pause  -  Left/Right prev/next song  -  O open Spotify  -  "
                "P paste playlist  -  X switch off  -  Esc walk away (keeps playing)")
        K.blit_text(surf, K.fit_font(hint, PW - 60, (13, 12, 11), bold=True), hint,
                    K.INK_SOFT, (P.centerx, P.bottom - 14))

    def _draw_deck(self, surf, tint):
        L = self.L
        d, c, R = L["deck"], L["c"], L["R"]
        surf.blit(_plinth(d.w, d.h), d.topleft)
        # platter: silver rim with turning strobe dots, then the record
        pygame.draw.circle(surf, _dk(_WOOD_DK, 0.7), (c[0] + 3, c[1] + 6), R + 12)
        pygame.draw.circle(surf, (168, 172, 182), c, R + 11)
        pygame.draw.circle(surf, (212, 216, 224), c, R + 9)
        pygame.draw.circle(surf, (120, 124, 136), c, R + 11, 2)
        for i in range(48):
            a = math.radians(self.angle + i * 7.5)
            pygame.draw.circle(surf, (132, 136, 148),
                               (int(c[0] + math.cos(a) * (R + 5)), int(c[1] + math.sin(a) * (R + 5))), 2)
        rec = pygame.transform.rotozoom(_vinyl(R, tuple(tint[:3])), -self.angle, 1.0)
        surf.blit(rec, rec.get_rect(center=c))
        surf.blit(_sheen(R), (c[0] - R - 2, c[1] - R - 2))
        # power light + speed selector on the plinth corners
        on = bool(getattr(self.fr, "on", False))
        lx, ly = d.x + 34, d.bottom - 34
        pygame.draw.circle(surf, (60, 40, 30), (lx, ly), 8)
        pygame.draw.circle(surf, (120, 230, 140) if on else (150, 70, 60), (lx, ly), 6)
        if on:
            pygame.draw.circle(surf, (220, 255, 226), (lx - 2, ly - 2), 2)
        K.blit_text(surf, K.font(11, True), "POWER", (96, 62, 42), (lx + 14, ly), align="left")
        sx, sy = d.right - 60, d.bottom - 34
        f = K.font(11, True)
        for i, lab in enumerate(("33", "45")):
            cx = sx + i * 28
            hot = i == 0
            pygame.draw.circle(surf, (236, 226, 206) if hot else (150, 110, 80), (cx, sy), 10)
            pygame.draw.circle(surf, (96, 62, 42), (cx, sy), 10, 2)
            K.blit_text(surf, f, lab, (70, 44, 36) if hot else (230, 214, 190), (cx, sy))
        # tonearm (with a soft shadow on the record)
        ang = ARM_REST + (L["arm_play"] - ARM_REST) * self._ease(self.arm)
        ang += math.sin(self.clock * 1.7) * 0.25 * self.spin     # tracks the groove
        self._draw_arm(surf, L["pivot"], ang, tint)
        for x, y, _vx, life, mx, col in self.notes:
            k = life / mx
            _note(surf, x, y, col, int(255 * min(1.0, k * 2.0)), 11)

    @staticmethod
    def _ease(t):
        t = max(0.0, min(1.0, t))
        return t * t * (3 - 2 * t)

    def _draw_arm(self, surf, pivot, ang, tint):
        a = math.radians(ang)
        ux, uy = math.cos(a), math.sin(a)
        px, py = pivot
        end = (px + ux * ARM_LEN, py + uy * ARM_LEN)
        hs0 = (px + ux * (ARM_LEN - 30), py + uy * (ARM_LEN - 30))
        cw = (px - ux * 30, py - uy * 30)
        # rest post under the arm's resting spot
        rest = (px + math.cos(math.radians(ARM_REST)) * (ARM_LEN * 0.62),
                py + math.sin(math.radians(ARM_REST)) * (ARM_LEN * 0.62))
        pygame.draw.circle(surf, (96, 62, 42), (int(rest[0]) + 1, int(rest[1]) + 3), 9)
        pygame.draw.circle(surf, (150, 154, 166), (int(rest[0]), int(rest[1])), 8)
        pygame.draw.circle(surf, (200, 204, 214), (int(rest[0]), int(rest[1])), 5)
        # soft shadow on the record / plinth
        d = self.L["deck"]
        sh = _CACHE.get(("armshadow", d.size))
        if sh is None:
            sh = _CACHE[("armshadow", d.size)] = pygame.Surface(d.size, pygame.SRCALPHA)
        sh.fill((0, 0, 0, 0))
        o = (6 - d.x, 9 - d.y)
        pygame.draw.line(sh, (30, 16, 12, 90), (cw[0] + o[0], cw[1] + o[1]),
                         (end[0] + o[0], end[1] + o[1]), 7)
        surf.blit(sh, d.topleft)
        # counterweight
        n = (-uy, ux)
        cwp = [(cw[0] - ux * 14 + n[0] * 11, cw[1] - uy * 14 + n[1] * 11),
               (cw[0] + ux * 10 + n[0] * 11, cw[1] + uy * 10 + n[1] * 11),
               (cw[0] + ux * 10 - n[0] * 11, cw[1] + uy * 10 - n[1] * 11),
               (cw[0] - ux * 14 - n[0] * 11, cw[1] - uy * 14 - n[1] * 11)]
        pygame.draw.polygon(surf, (70, 72, 82), cwp)
        pygame.draw.polygon(surf, (40, 40, 48), cwp, 2)
        # the arm tube
        pygame.draw.line(surf, (82, 84, 96), cw, hs0, 9)
        pygame.draw.line(surf, (214, 218, 228), cw, hs0, 5)
        pygame.draw.line(surf, (250, 250, 255), (cw[0] + n[0] * -1.5, cw[1] + n[1] * -1.5),
                         (hs0[0] + n[0] * -1.5, hs0[1] + n[1] * -1.5), 1)
        # headshell, turned a little like a real S-arm, with a cartridge in the piece colour
        h = math.radians(ang + 24)
        hx, hy = math.cos(h), math.sin(h)
        hn = (-hy, hx)
        hc = ((hs0[0] + end[0]) / 2, (hs0[1] + end[1]) / 2)
        shell = [(hc[0] + hx * 20 + hn[0] * 9, hc[1] + hy * 20 + hn[1] * 9),
                 (hc[0] + hx * 20 - hn[0] * 9, hc[1] + hy * 20 - hn[1] * 9),
                 (hc[0] - hx * 16 - hn[0] * 7, hc[1] - hy * 16 - hn[1] * 7),
                 (hc[0] - hx * 16 + hn[0] * 7, hc[1] - hy * 16 + hn[1] * 7)]
        pygame.draw.polygon(surf, (58, 58, 68), shell)
        pygame.draw.polygon(surf, (30, 30, 38), shell, 2)
        cart = [(hc[0] + hx * 16 + hn[0] * 6, hc[1] + hy * 16 + hn[1] * 6),
                (hc[0] + hx * 16 - hn[0] * 6, hc[1] + hy * 16 - hn[1] * 6),
                (hc[0] + hx * 2 - hn[0] * 6, hc[1] + hy * 2 - hn[1] * 6),
                (hc[0] + hx * 2 + hn[0] * 6, hc[1] + hy * 2 + hn[1] * 6)]
        pygame.draw.polygon(surf, tint, cart)
        pygame.draw.polygon(surf, _dk(tint, 0.6), cart, 1)
        # pivot base
        pygame.draw.circle(surf, (96, 62, 42), (px + 2, py + 4), 24)
        pygame.draw.circle(surf, (150, 154, 166), (px, py), 22)
        pygame.draw.circle(surf, (206, 210, 220), (px, py), 15)
        pygame.draw.circle(surf, (120, 124, 136), (px, py), 15, 2)
        pygame.draw.circle(surf, (250, 250, 255), (px - 4, py - 5), 4)

    def _draw_info(self, surf, tint):
        L = self.L
        info, well = L["info"], L["well"]
        st = self.status()
        R = spotify.REMOTE
        last = st.song or R.last_song
        live = st.song is not None
        head = ("NOW PLAYING" if live else "PAUSED" if (st.ready and last)
                else "LAST PLAYED" if last else "NOTHING PLAYING")
        K.blit_text(surf, K.font(15, True), head, K.SPROUT if live else K.INK_SOFT,
                    (info.x + 4, info.y + 8), align="left")
        self._draw_eq(surf, info.right - 6, info.y + 17, live)
        K.well(surf, well, hot=live, radius=12)
        self._draw_song(surf, well, last, live)
        # status line with a little LED
        y = L["status_y"]
        if R.launching:
            text = "Opening Spotify" + "." * (1 + int(self.clock * 3) % 3)
            col, led = K.GOLD_TXT, (240, 190, 80) if int(self.clock * 4) % 2 else (200, 150, 60)
        elif st.running and st.playing:
            text, col, led = "Playing on Spotify", K.SPROUT, (120, 220, 120)
        elif st.running and not st.ready:
            text, col, led = "Spotify is starting up...", K.INK_SOFT, (240, 190, 80)
        elif st.running:
            text, col, led = "Spotify is paused", K.INK_SOFT, (236, 180, 84)
        elif R.web:
            text, col, led = ("Spotify opened in your browser - play it there",
                              K.INK_SOFT, (120, 170, 230))
        else:
            text, col, led = "Spotify isn't running -- press O to open it", K.WARN, (170, 150, 140)
        pygame.draw.circle(surf, _dk(led, 0.6), (info.x + 12, y), 8)
        pygame.draw.circle(surf, led, (info.x + 12, y), 6)
        pygame.draw.circle(surf, _lt(led, 1.3), (info.x + 10, y - 2), 2)
        f = K.fit_font(text, info.w - 34, (17, 16, 15, 14), bold=True)
        K.blit_text(surf, f, text, col, (info.x + 28, y), align="left")
        # transport buttons (pause bars whenever the record spins -- the
        # browser player counts as playing, like the platter)
        spinning = self.spinning()
        for b, (c, r) in L["buttons"].items():
            self._round_button(surf, b, c, r, spinning)
        # key pills (clickable) + the saved playlist + messages
        py = L["pills_y"]
        pills = [("open", "O", "Open Spotify", K.SPROUT), ("paste", "P", "Paste playlist",
                                                           (96, 124, 190)),
                 ("off", "X", "Switch off", K.WARN)]
        widths = []
        fnt = K.font(14, True)
        for _b, key, lab, _c in pills:
            widths.append(fnt.size(key)[0] + 12 + fnt.size(lab)[0] + 18 + 10)
        gap = 14
        x = info.centerx - (sum(widths) + gap * (len(widths) - 1)) // 2
        self._pills = {}
        for (b, key, lab, acc), w in zip(pills, widths):
            r = K.key_pill(surf, key, lab, (x + w // 2, py), accent=acc, fnt=fnt,
                           alpha=255 if (self.hover == b or b in self.flash) else 228)
            if self.hover == b or b in self.flash:
                pygame.draw.rect(surf, K.GOLD_RIM, r, 2, border_radius=r.h // 2)
            self._pills[b] = r
            x += w + gap
        uri = self.g._records_uri()
        if self.msg_t > 0 and self.msg:
            a = min(1.0, self.msg_t / 0.4)
            ln, col2 = self.msg, _mix(K.CREAM, K.GOLD_TXT, a)
        elif uri:
            ln = f"{spotify.link_kind(uri)} saved - press O to open it in Spotify"
            col2 = K.INK_SOFT
        else:
            ln, col2 = "Tip: copy a Spotify playlist link, then press P to keep it", K.INK_FAINT
        f = K.fit_font(ln, info.w, (14, 13, 12), bold=True)
        K.blit_text(surf, f, ln, col2, (info.centerx, py + 38))

    def _draw_song(self, surf, well, song, live):
        x0, maxw = well.x + 20, well.w - 40
        if not song:
            K.blit_text(surf, K.font(24, True), "No record on", K.INK_SOFT,
                        (x0, well.y + 50), align="left")
            K.blit_text(surf, K.font(15, True), "Press Action to put some music on",
                        K.INK_FAINT, (x0, well.y + 88), align="left")
            return
        # fitting / wrapping a long (Thai) title measures it dozens of times:
        # done once per song + width + colour, then just blitted each frame
        key = (tuple(song), maxw, well.h, bool(live))
        cached = getattr(self, "_song_cache", None)
        if cached is None or cached[0] != key:
            cached = self._song_cache = (key, song_layout(song, maxw, well.h, live))
        for img, dy in cached[1]:
            surf.blit(img, (x0, well.y + dy))

    def _draw_eq(self, surf, right, base, live):
        """Little bouncing level bars beside the header while music plays."""
        n = 7
        for i in range(n):
            if live:
                h = 3 + 15 * abs(math.sin(self.clock * (3.1 + i * 0.73) + i * 1.9)) \
                    * (0.55 + 0.45 * abs(math.sin(self.clock * 1.3 + i)))
            else:
                h = 3
            r = pygame.Rect(right - (n - i) * 8, base - int(h), 5, int(h))
            pygame.draw.rect(surf, K.LEAF if live else K.WELL_LINE, r, border_radius=2)

    def _round_button(self, surf, b, c, r, playing):
        hot = self.hover == b
        down = b in self.flash
        main = b == "play"
        sh = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(sh, (40, 20, 30, 80), (r + 2, r + 2), r)
        surf.blit(sh, (c[0] - r + 1, c[1] - r + 3))
        pygame.draw.circle(surf, K.GOLD_RIM if (hot or down) else K.WOOD, c, r)
        face = ((240, 206, 140) if down else (255, 232, 170) if (hot or main)
                else K.CREAM)
        pygame.draw.circle(surf, face, c, r - 5)
        pygame.draw.arc(surf, K.CREAM_HI, (c[0] - r + 9, c[1] - r + 8, 2 * r - 18, 2 * r - 18),
                        math.radians(40), math.radians(140), 3)
        ink = K.INK
        ox, oy = (1, 1) if down else (0, 0)
        cx, cy = c[0] + ox, c[1] + oy
        s = r * 0.42
        if b == "play":
            if playing:                                      # pause bars
                w_, h_ = s * 0.42, s * 1.7
                for dx in (-s * 0.5, s * 0.5):
                    pygame.draw.rect(surf, ink, (cx + dx - w_ / 2, cy - h_ / 2, w_, h_),
                                     border_radius=3)
            else:
                pygame.draw.polygon(surf, ink, [(cx - s * 0.6, cy - s * 0.95),
                                                (cx - s * 0.6, cy + s * 0.95),
                                                (cx + s * 1.05, cy)])
        else:
            d = -1 if b == "prev" else 1
            for k in (0, 1):
                tx = cx + d * (k * s * 0.9 - s * 0.2)
                pygame.draw.polygon(surf, ink, [(tx - d * s * 0.7, cy - s * 0.8),
                                                (tx - d * s * 0.7, cy + s * 0.8),
                                                (tx + d * s * 0.5, cy)])
            bx = cx + d * s * 1.05
            pygame.draw.rect(surf, ink, (bx - 2, cy - s * 0.8, 4, s * 1.6), border_radius=1)
