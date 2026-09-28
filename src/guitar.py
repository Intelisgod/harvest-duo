"""The Guitar: pick it up off its stand and REALLY play it -- a key is a chord.

Use a placed Guitar (``guitar_stand``). A steel-string acoustic fills the top
of a parchment page; under it sits an autoharp / omnichord style chord grid:
columns are roots in circle-of-fifths order, rows are the chord type.

            Bb   F    C    G    D    A    E
  Major     Q    W    E    R    T    Y    U
  minor     A    S    D    F    G    H    J
  7th       Z    X    C    V    B    N    M

  a chord key       strum it DOWN (low string -> high string)
  Shift + key       strum it UP (high -> low: lighter, brighter, bass barely brushed)
  Space             strum the last chord again (Shift + Space: up) -- rhythm!
  mouse             click a pad (right click: up-strum)
  Tab / Up / Down   free play <-> the song book     Enter   listen to the song first
  Esc / Bksp        put the guitar back

Every chord is a real 6-string open-position voicing in standard tuning
(E2 A2 D3 G3 B3 E4; ``SHAPES``, muted strings are not played; the Bb / F /
minor barre shapes are the usual ones). A strum plays its strings 10-22 ms
apart with a little random timing and touch, and damps the previous chord
first, like a strumming hand does. The strings on the drawn guitar vibrate,
the fingers show on the neck and a chord box shows the shape.

The song book holds chord charts of public-domain songs (``SONGS``): the
next chord's pad glows, the chart scrolls, the right chord moves on (a wrong
one only wiggles -- there is no way to fail). Finishing earns a celebration
(and, once a day per song, some energy -- GuitarMixin).

Sound (``GuitarSynth``): Karplus-Strong plucked strings. A pick-shaped
excitation (a triangle with its apex where the pick meets the string, plus a
little low-passed scrape noise) runs round a delay line with the classic
two-point averaging filter and a per-string loss; two slightly detuned
"polarisations" (one dying faster) give the ring its bloom, and a tiny body
knock (the top and the air inside) adds the wood. The loop runs a whole
period at a time as a list comprehension (no per-sample Python loop), at a
whole-sample delay, then the note is resampled to its exact pitch. Every
string pitch is baked ONCE per session and cached (~40 ms each, ~2.5-3 s of
ring ending in a soft 0.45 s fade), on a polite daemon thread as soon as
anyone walks into a house that has a guitar; a note needed before that is a
short stand-in baked on the spot. Strums are sample-accurate: each string's
Sound starts with its own few milliseconds of silence, so all six start on
one mixer tick yet sound staggered.

Loudness: SDL adds voices up and clamps; ``GuitarSynth._gain`` keeps a
6-string strum (with the partner's ringing too) under full scale at any
volume, and voices use their own mixer channels above the game's 16 (and
above the piano's). The background loop is hushed while you play
(GuitarMixin).

Pure UI + sound. The game side (energy, song rewards, LAN relays) lives in
``systems/guitar_system.GuitarMixin``; the screen calls back into it with
``_guitar_strum(screen, chord, down)``, ``_guitar_song_done(screen, song_id)``
and ``_guitar_closed(screen)``.
"""
import array
import math
import random
import threading
import time
import pygame

from . import ui_kit as K

OPEN_T = 0.36           # the guitar lifts into place, seconds
CLOSE_T = 0.24
TRAIL_LIFE = 20.0       # free play: seconds a strum stays in the queue on the page
_TRAIL_W = {}           # chip widths, measured when first drawn

# ------------------------------------------------------------------ music
NOTE_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B"]
TUNING = (40, 45, 50, 55, 59, 64)          # E2 A2 D3 G3 B3 E4, low string first
STRING_NAMES = ("E", "A", "D", "G", "B", "e")

ROOTS = ("Bb", "F", "C", "G", "D", "A", "E")          # columns: the circle of fifths
KINDS = ("", "m", "7")                                 # rows
ROW_NAMES = ("Major", "minor", "7th")
ROW_KEYS = ("qwertyu", "asdfghj", "zxcvbnm")
_KIND_LONG = {"": "major", "m": "minor", "7": "seventh"}
_ROOT_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "Bb": 10}
# what each chord type must contain (intervals above the root)
_KIND_PCS = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10)}

# fret per string, low E first; "x" = muted (not played)
SHAPES = {
    "Bb": "x13331", "F": "133211", "C": "x32010", "G": "320003",
    "D": "xx0232", "A": "x02220", "E": "022100",
    "Bbm": "x13321", "Fm": "133111", "Cm": "x35543", "Gm": "355333",
    "Dm": "xx0231", "Am": "x02210", "Em": "022000",
    "Bb7": "x13131", "F7": "131211", "C7": "x32310", "G7": "320001",
    "D7": "xx0212", "A7": "x02020", "E7": "020100",
}
# barre: (fret, from string, to string) -- the index finger across the neck
BARRES = {"Bb": (1, 1, 5), "F": (1, 0, 5), "Bbm": (1, 1, 5), "Fm": (1, 0, 5),
          "Cm": (3, 1, 5), "Gm": (3, 0, 5), "Bb7": (1, 1, 5), "F7": (1, 0, 5)}
GRID = [[r + k for r in ROOTS] for k in KINDS]         # GRID[row][col] -> chord id
CHORD_IDS = [c for row in GRID for c in row]


def frets(cid):
    """[fret or None] per string (low E first)."""
    return [None if ch == "x" else int(ch) for ch in SHAPES[cid]]


def voicing(cid):
    """[midi or None] per string (low E first) for chord ``cid``."""
    return [None if f is None else TUNING[i] + f for i, f in enumerate(frets(cid))]


def chord_root(cid):
    return cid[:2] if cid[:2] == "Bb" else cid[:1]


def chord_kind(cid):
    return cid[len(chord_root(cid)):]


def root_pc(cid):
    return _ROOT_PC[chord_root(cid)]


def chord_long(cid):
    """'G seventh', 'A minor', 'C major'."""
    return f"{chord_root(cid)} {_KIND_LONG[chord_kind(cid)]}"


def chord_pcs(cid):
    """The pitch classes chord ``cid`` must be made of."""
    r = root_pc(cid)
    return {(r + i) % 12 for i in _KIND_PCS[chord_kind(cid)]}


def note_name(midi):
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def chord_at(row, col):
    return GRID[row][col]


def grid_pos(cid):
    for r, row in enumerate(GRID):
        if cid in row:
            return r, row.index(cid)
    return None


def clean_chord(v):
    """A partner's chord id: only the ones on the grid."""
    return v if isinstance(v, str) and v in SHAPES else None


# key -> chord (keycodes, and SDL scancodes so a Thai layout still works)
KEY_CHORD = {}
SCAN_CHORD = {}
KEY_LABEL = {}
for _r, _keys in enumerate(ROW_KEYS):
    for _c, _ch in enumerate(_keys):
        _cid = GRID[_r][_c]
        KEY_CHORD[getattr(pygame, "K_" + _ch)] = _cid
        _sc = getattr(pygame, "KSCAN_" + _ch.upper(), None)
        if _sc:
            SCAN_CHORD[_sc] = _cid
        KEY_LABEL[_cid] = _ch.upper()

# pastel rainbow by pitch class (the pads, floating notes, finger dots)
_PC_COL = [(236, 96, 116), (238, 128, 92), (240, 160, 64), (226, 190, 56),
           (160, 196, 70), (92, 180, 100), (64, 176, 150), (64, 166, 204),
           (84, 136, 222), (112, 112, 226), (150, 100, 220), (206, 96, 186)]


def chord_color(cid):
    return _PC_COL[root_pc(cid) % 12]


# ------------------------------------------------------------------ song book
def _song(sid, tab, title, key, beat, steps):
    out = []
    for ch, beats, words in steps:
        assert ch in SHAPES, ch
        out.append((ch, float(beats), words))
    return {"id": sid, "tab": tab, "title": title, "key": key, "beat": beat, "steps": out}


# public-domain songs only; one chord per bar or half bar ("beats" = its length
# for Listen). "{partner}" is filled with the other farmer's name.
SONGS = [
    _song("twinkle", "Twinkle Twinkle", "Twinkle Twinkle Little Star", "C", 0.5, [
        ("C", 4, "Twinkle, twinkle"), ("F", 2, "little"), ("C", 2, "star,"),
        ("F", 2, "how I"), ("C", 2, "wonder"), ("G", 2, "what you"), ("C", 2, "are!"),
        ("C", 2, "Up a-"), ("F", 2, "-bove the"), ("C", 2, "world so"), ("G", 2, "high,"),
        ("C", 2, "like a"), ("F", 2, "dia-"), ("C", 2, "-mond in"), ("G", 2, "the sky."),
        ("C", 4, "Twinkle, twinkle"), ("F", 2, "little"), ("C", 2, "star,"),
        ("F", 2, "how I"), ("C", 2, "wonder"), ("G", 2, "what you"), ("C", 2, "are!")]),
    _song("birthday", "Happy Birthday", "Happy Birthday to You", "C", 0.46, [
        ("C", 3, "Happy birthday"), ("G7", 3, "to you,"), ("G7", 3, "happy birthday"),
        ("C", 3, "to you,"), ("C7", 3, "happy birthday"), ("F", 3, "dear {partner},"),
        ("C", 2, "happy birthday"), ("G7", 1, "to"), ("C", 3, "you!")]),
    _song("mary", "Mary Had a Lamb", "Mary Had a Little Lamb", "C", 0.46, [
        ("C", 4, "Mary had a"), ("C", 4, "little lamb,"), ("G", 4, "little lamb,"),
        ("C", 4, "little lamb,"), ("C", 4, "Mary had a"), ("C", 4, "little lamb, its"),
        ("G", 4, "fleece was white as"), ("C", 4, "snow.")]),
    _song("row", "Row Your Boat", "Row, Row, Row Your Boat", "C", 0.62, [
        ("C", 4, "Row, row, row your boat,"), ("C", 4, "gently down the stream."),
        ("C", 4, "Merrily, merrily, merrily, merrily,"), ("G7", 2, "life is but a"),
        ("C", 2, "dream.")]),
    _song("london", "London Bridge", "London Bridge Is Falling Down", "C", 0.46, [
        ("C", 2, "London Bridge is"), ("C", 2, "falling down,"), ("G7", 2, "falling down,"),
        ("C", 2, "falling down."), ("C", 4, "London Bridge is falling down,"),
        ("G7", 2, "my fair"), ("C", 2, "lady.")]),
    _song("ode", "Ode to Joy", "Ode to Joy (Beethoven)", "C", 0.5, [
        ("C", 4, "mi mi fa sol"), ("G", 4, "sol fa mi re"), ("C", 4, "do do re mi"),
        ("G", 4, "mi, re re"), ("C", 4, "mi mi fa sol"), ("G", 4, "sol fa mi re"),
        ("C", 4, "do do re mi"), ("G", 2, "re, do"), ("C", 2, "do"),
        ("G", 4, "re re mi do"), ("C", 4, "re mi-fa mi do"), ("G", 4, "re mi-fa mi re"),
        ("C", 2, "do re"), ("G", 2, "sol"), ("C", 4, "mi mi fa sol"), ("G", 4, "sol fa mi re"),
        ("C", 4, "do do re mi"), ("G", 2, "re, do"), ("C", 2, "do")]),
    _song("jingle", "Jingle Bells", "Jingle Bells", "G", 0.36, [
        ("G", 8, "Jingle bells, jingle bells,"), ("G", 8, "jingle all the way! Oh"),
        ("C", 4, "what fun it is to"), ("G", 4, "ride in a"), ("A7", 4, "one-horse open"),
        ("D7", 4, "sleigh, hey!"), ("G", 8, "Jingle bells, jingle bells,"),
        ("G", 8, "jingle all the way! Oh"), ("C", 4, "what fun it is to"),
        ("G", 4, "ride in a"), ("D7", 4, "one-horse open"), ("G", 4, "sleigh!")]),
    _song("susanna", "Oh! Susanna", "Oh! Susanna (Stephen Foster)", "C", 0.4, [
        ("C", 4, "I come from Alabama with my"), ("G7", 4, "banjo on my knee,"),
        ("C", 4, "I'm going to Louisiana, my"), ("G7", 2, "true love for to"),
        ("C", 2, "see."), ("F", 4, "Oh! Susanna,"), ("C", 2, "oh don't you cry for"),
        ("G7", 2, "me, for I"), ("C", 4, "come from Alabama with my"),
        ("G7", 2, "banjo on my"), ("C", 2, "knee!")]),
    _song("grace", "Amazing Grace", "Amazing Grace", "G", 0.55, [
        ("G", 3, "A-mazing"), ("G7", 3, "grace, how"), ("C", 3, "sweet the"),
        ("G", 6, "sound that saved a"), ("Em", 3, "wretch like"), ("D", 6, "me. I"),
        ("G", 3, "once was"), ("G7", 3, "lost, but"), ("C", 3, "now am"),
        ("G", 6, "found, was blind but"), ("D", 3, "now I"), ("G", 6, "see.")]),
    _song("auld", "Auld Lang Syne", "Auld Lang Syne", "G", 0.55, [
        ("G", 4, "Should auld acquaintance"), ("D7", 4, "be forgot, and"),
        ("G", 4, "never brought to"), ("C", 4, "mind? Should"),
        ("G", 4, "auld acquaintance"), ("D7", 4, "be forgot, and"),
        ("C", 2, "auld"), ("D7", 2, "lang"), ("G", 4, "syne?")]),
    _song("aura", "Aura Lee", "Aura Lee (1861)", "C", 0.6, [
        ("C", 4, "When the blackbird"), ("D7", 4, "in the spring,"),
        ("G7", 4, "on the willow"), ("C", 4, "tree,"), ("C", 4, "sat and rocked, I"),
        ("D7", 4, "heard him sing,"), ("G7", 4, "singing Aura"), ("C", 4, "Lee."),
        ("C", 4, "Aura Lee,"), ("E7", 4, "Aura Lee,"), ("Am", 4, "maid of golden"),
        ("C7", 4, "hair;"), ("F", 4, "sunshine came a-"), ("Fm", 4, "-long with thee,"),
        ("C", 2, "and swal-"), ("A7", 2, "-lows"), ("D7", 2, "in the"), ("G7", 2, "air."),
        ("C", 4, "(let it ring)")]),
    _song("green", "Greensleeves", "Greensleeves", "Am", 0.45, [
        ("Am", 3, "Alas, my"), ("C", 3, "love, you"), ("G", 3, "do me"), ("Em", 3, "wrong, to"),
        ("Am", 3, "cast me"), ("E", 6, "off discourteously."), ("Am", 3, "For I have"),
        ("C", 3, "loved you"), ("G", 3, "well and"), ("Em", 3, "long, de-"),
        ("Am", 3, "-lighting"), ("E", 3, "in your"), ("Am", 3, "company."),
        ("C", 3, "Greensleeves was"), ("G", 3, "all my"), ("Em", 3, "joy, and"),
        ("Am", 3, "Greensleeves was"), ("E", 3, "my delight;"), ("C", 3, "Greensleeves was my"),
        ("G", 3, "heart of"), ("Em", 3, "gold, and"), ("Am", 3, "who but my"),
        ("E", 3, "lady"), ("Am", 6, "Greensleeves?")]),
    _song("silent", "Silent Night", "Silent Night", "C", 0.55, [
        ("C", 6, "Silent night, holy night,"), ("G7", 6, "all is calm,"),
        ("C", 6, "all is bright."), ("F", 6, "Round yon virgin"), ("C", 6, "mother and child."),
        ("F", 6, "Holy infant so"), ("C", 6, "tender and mild,"), ("G7", 6, "sleep in heavenly"),
        ("C", 6, "peace,"), ("G7", 6, "sleep in heavenly"), ("C", 6, "peace.")]),
]
SONG_IDS = {s["id"]: s for s in SONGS}


def song_title(sid):
    s = SONG_IDS.get(sid)
    return s["title"] if s else "a song"


# ------------------------------------------------------------------ synth
PEAK = 9000             # one string's baked peak (int16) at full velocity and volume
FADE = 0.45             # every note ends in this soft fade (s)
QUICK_SECS = 0.9        # a note needed mid-frame before the prewarm got to it
DAMP_MS = 70            # a new strum mutes the old chord this fast
HEADROOM = 3.3          # single-string peaks the mix holds at full volume (with a margin)
FLOOR = 0.4             # a strum is never hushed below this ...
DUCK_MIN = 0.45         # ... what already rings (the partner's) may drop to this
NAP_IDLE, NAP_BUSY = 0.002, 0.0003   # prewarm work between GIL breaks (s): game idle / busy


def _t30(midi):
    """Seconds the main polarisation of a string needs to fall 30 dB
    (bass strings ring longer)."""
    return max(1.35, min(2.1, 2.1 - (midi - 40) / 24.0 * 0.65))


def note_secs(midi):
    """How long the baked note lasts (fade included)."""
    return max(2.4, min(3.0, 3.0 - (midi - 40) / 24.0 * 0.5))


def note_env(midi, age):
    """Roughly how loud a string still is ``age`` s after it was plucked
    (1 at the pluck; before it, 1 -- it's about to be)."""
    if age <= 0:
        return 1.0
    t = _t30(midi)
    return 0.72 * 10 ** (-1.5 * age / t) + 0.28 * 10 ** (-1.5 * age / (2.4 * t))


def strum_total(vels):
    """How many single-string peaks a strum with these velocities adds up
    to at its loudest (measured: the strings start 10-22 ms apart and their
    pitches differ, so the peaks never all line up)."""
    s = sum(vels)
    n = len(vels)
    return s * (1.0 if n <= 1 else max(0.52, 0.86 - 0.068 * (n - 2)))


def plan_strum(midis, down=True, vel=1.0, gap=None, rnd=random):
    """When and how hard each string of a strum sounds: [(string, delay s,
    velocity)] in the order the pick meets them. Down: low -> high; up: high
    -> low, quicker, lighter and brighter (the bass strings are only brushed).
    A little random timing and touch -- a person is playing."""
    order = [i for i, m in enumerate(midis) if m is not None]
    if not down:
        order.reverse()
    if gap is None:
        gap = rnd.uniform(0.013, 0.022) if down else rnd.uniform(0.010, 0.016)
    out, t = [], 0.0
    for k, i in enumerate(order):
        if k:
            t += gap * rnd.uniform(0.8, 1.2)
        v = vel * rnd.uniform(0.9, 1.0)
        if down:
            v *= 1.0 - 0.03 * k                      # the pick eases through the chord
        else:
            v *= 0.86 * (0.5, 0.58, 0.72, 0.9, 1.0, 1.0)[i]
        out.append((i, t, max(0.05, min(1.0, v))))
    return out


_CACHES = {}            # (sample rate, channels) -> {midi: Sound}
_RAWS = {}              # (sample rate, channels) -> {midi: bytes} (for delayed starts)
_QUICKS = {}            # (sample rate, channels) -> midis cached as a QUICK_SECS stand-in


def _cid(ch):
    return getattr(ch, "id", id(ch))


def _ks(exc, n_loop, g, total, nap=None):
    """Karplus-Strong, a whole period per step: y[n] = g * (y[n-N] + y[n-N-1])."""
    out = list(exc)
    prev = exc
    pp = 0.0                                    # y[n-N-1] for the period's first sample
    while len(out) < total:
        sh = [pp]
        sh += prev[:-1]
        cur = [g * (a + b) for a, b in zip(prev, sh)]
        pp = prev[-1]
        out += cur
        prev = cur
        if nap:
            nap()
    return out[:total]


def _resample(y, r, n):
    """``n`` samples of ``y`` read ``r`` times faster (linear interpolation)."""
    ks = [int(i * r) for i in range(n)]
    return [y[k] + (y[k + 1] - y[k]) * (i * r - k) for i, k in enumerate(ks)]


class GuitarSynth:
    """Baked, cached plucked strings + a voice pool on spare mixer channels."""
    VOICES = 18

    def __init__(self, audio):
        self.audio = audio
        init = pygame.mixer.get_init() if pygame.mixer.get_init() else None
        self.enabled = bool(getattr(audio, "enabled", False) and init)
        self.sr, _fmt, self.nch = init if init else (44100, -16, 1)
        self.cache = _CACHES.setdefault((self.sr, self.nch), {})
        self.raw = _RAWS.setdefault((self.sr, self.nch), {})
        self.quick = _QUICKS.setdefault((self.sr, self.nch), set())
        # lane -> [voice]; voice = [channel, sound, midi, starts at, level, None | (t, s)]
        self.lanes = {}
        self._chans = []
        self._base = None
        self._started = {}
        self._queue = []
        self._busy = False
        self._fg = 0
        self._nap_t, self._slice = 0.0, NAP_BUSY
        self._lock = threading.Lock()

    # ---- baking ----
    def _excite(self, midi, n_loop):
        """The pick: a triangle with its apex where the pick meets the string,
        plus a little scrape noise (low-passed: warmer on the bass strings)."""
        rnd = random.Random(midi * 31 + 7)
        a = max(1, int(0.17 * n_loop))
        tri = [j / a if j < a else (n_loop - j) / (n_loop - a) for j in range(n_loop)]
        k = 0.22 + 0.28 * min(1.0, max(0.0, (midi - 40) / 30.0))
        lp, nz = 0.0, []
        for _ in range(n_loop):
            lp += (rnd.uniform(-1.0, 1.0) - lp) * k
            nz.append(lp)
        ex = [0.8 * t + 0.7 * z for t, z in zip(tri, nz)]
        m = sum(ex) / n_loop
        return [v - m for v in ex]

    def render(self, midi, nice=False, secs=None):
        """Mono int16 samples for one string (no pygame calls: thread-safe).
        ``nice``: hand the GIL back every period or so (the prewarm thread).
        ``secs``: a shorter note (the quick stand-in: one polarisation)."""
        sr = self.sr
        f = 440.0 * 2 ** ((midi - 69) / 12.0)
        n = int(sr * min(secs or 99.0, note_secs(midi)))
        nap = self._nap if nice else None
        quick = secs is not None and secs < note_secs(midi)
        d = sr / f
        nl = max(4, int(d - 0.5))                  # the averager adds half a sample
        r1 = (nl + 0.5) / d                        # -> resample to the exact pitch
        ex = self._excite(midi, nl)
        t1 = _t30(midi)
        g1 = 0.5 * 10 ** (-1.5 / (f * t1))
        s = _resample(_ks(ex, nl, g1, int(n * r1) + 3, nap), r1, n)
        if not quick:                              # 2nd polarisation: +1.5 cents, rings on
            r2 = r1 * 2 ** (1.5 / 1200.0)
            g2 = 0.5 * 10 ** (-1.5 / (f * t1 * 2.4))
            s2 = _resample(_ks(ex, nl, g2, int(n * r2) + 3, nap), r2, n)
            s = [a + 0.28 * b for a, b in zip(s, s2)]
        if nap:
            nap()
        # the body: a soft knock of the top and the air inside
        pk = max(1e-6, max(abs(v) for v in s[:int(0.1 * sr)]))
        amt = pk * (0.16 - 0.08 * min(1.0, max(0.0, (midi - 40) / 24.0)))
        nb = min(n, int(0.3 * sr))
        tw = 2 * math.pi / sr
        ex_, sin = math.exp, math.sin
        for fr, tau, a in ((98.0, 0.075, 1.0), (196.0, 0.045, 0.55), (392.0, 0.02, 0.3)):
            w, k = tw * fr, 1.0 / (tau * sr)
            s[:nb] = [v + amt * a * ex_(-i * k) * sin(w * i) for i, v in enumerate(s[:nb])]
        # level: every string peaks at PEAK (the treble a touch lighter)
        top = PEAK * (1.0 - 0.1 * min(1.0, max(0.0, (midi - 52) / 16.0)))
        g = top / max(1e-6, max(abs(v) for v in s))
        fade = max(1, min(n // 2, int((0.25 if quick else FADE) * sr)))
        att = max(1, int(0.0004 * sr))
        cos, pi = math.cos, math.pi
        body = n - fade
        out = [int(v * g) for v in s[:body]]
        out += [int(v * g * (0.5 + 0.5 * cos(pi * j / fade))) for j, v in enumerate(s[body:])]
        for i in range(min(n, att)):
            out[i] = out[i] * i // att
        return out

    def _nap(self):
        """Prewarm thread manners (see PianoSynth._nap): tiny slices while the
        game draws, bigger ones while it idles; stand aside completely while
        the game thread bakes a stand-in of its own."""
        now = time.perf_counter()
        if now - self._nap_t < self._slice and not self._fg:
            return
        time.sleep(0.0005)
        while self._fg:
            time.sleep(0.001)
        t = time.perf_counter()
        self._slice = NAP_IDLE if t - now < 0.0025 else NAP_BUSY
        self._nap_t = t

    def _to_bytes(self, mono, nap=None):
        if nap:
            arr = array.array("h")
            for i in range(0, len(mono), 8192):
                arr.extend(mono[i:i + 8192])
                nap()
        else:
            arr = array.array("h", mono)
        if self.nch == 2:
            st = array.array("h", bytes(len(arr) * 4))
            st[0::2] = arr
            st[1::2] = arr
            arr = st
        elif self.nch > 2:
            st = array.array("h", bytes(len(arr) * 2 * self.nch))
            for c in range(self.nch):
                st[c::self.nch] = arr
            arr = st
        return arr.tobytes()

    def _store(self, midi, raw, quick):
        self.raw[midi] = raw
        self.cache[midi] = pygame.mixer.Sound(buffer=raw)
        if quick:
            self.quick.add(midi)
        else:
            self.quick.discard(midi)

    def baked(self, midi):
        return midi in self.cache and midi not in self.quick

    def sound(self, midi):
        """The cached Sound for ``midi``; not baked yet: a short stand-in
        baked right here (a few ms), the full note queued first."""
        s = self.cache.get(midi)
        if s is None and self.enabled:
            self._fg += 1
            try:
                self._store(midi, self._to_bytes(self.render(midi, secs=QUICK_SECS)), True)
                s = self.cache[midi]
            except Exception:
                s = None
            finally:
                self._fg -= 1
            if s is not None:
                self.prewarm([midi])
        return s

    def _delayed(self, midi, delay):
        """``midi`` starting ``delay`` samples late (its own leading silence:
        a strum's strings all start on one mixer tick, yet sound staggered)."""
        if delay <= 0:
            return self.cache[midi]
        raw = self.raw.get(midi)
        if raw is None:
            return self.cache[midi]
        return pygame.mixer.Sound(buffer=bytes(delay * 2 * self.nch) + raw)

    def _bake_full(self, midi):
        try:
            raw = self._to_bytes(self.render(midi, True), self._nap)
            self._store(midi, raw, False)
        except Exception:
            pass

    def prewarm(self, midis):
        """Bake ``midis`` (in order) on a daemon thread."""
        if not self.enabled:
            return
        midis = list(midis)
        with self._lock:
            want = set(midis)
            self._queue = ([m for m in midis if not self.baked(m)]
                           + [m for m in self._queue if m not in want])
            if self._busy or not self._queue:
                return
            self._busy = True
        threading.Thread(target=self._prewarm_run, daemon=True).start()

    def _prewarm_run(self):
        try:
            while True:
                with self._lock:
                    if not self._queue:
                        self._busy = False
                        return
                    m = self._queue.pop(0)
                if not self.baked(m):
                    self._bake_full(m)
                time.sleep(0.002)
        except Exception:
            with self._lock:
                self._busy = False

    # ---- voices ----
    def _pool(self):
        """Our own channels above everything allocated before us (the game's
        16, the piano's), so a strum never steals the music loop."""
        try:
            have = pygame.mixer.get_num_channels()
            if self._base is None:
                self._base = max(16, have)
            want = self._base + self.VOICES
            if have < want:
                pygame.mixer.set_num_channels(want)
                self._chans = []
            if not self._chans:
                self._chans = [pygame.mixer.Channel(i) for i in range(self._base, want)]
        except Exception:
            self._chans = []
        return self._chans

    def volume(self):
        a = getattr(self.audio, "_real", None) or self.audio
        return getattr(a, "master", 0.8) * getattr(a, "sfx_vol", 0.9)

    @staticmethod
    def _sounding(v):
        try:
            return bool(v[0].get_busy()) and v[0].get_sound() is v[1]
        except Exception:
            return False

    def _live(self):
        """Prune voices that ended; returns every live voice."""
        out = []
        for lane in list(self.lanes):
            keep = [v for v in self.lanes[lane] if self._sounding(v)]
            if keep:
                self.lanes[lane] = keep
                out += keep
            else:
                del self.lanes[lane]
        return out

    def _channel(self, taken):
        """A free channel; else the oldest fading one; else the oldest voice."""
        chans = [c for c in self._pool() if _cid(c) not in taken]
        if not chans:
            return None
        for c in chans:
            if not c.get_busy():
                return c
        fading = {_cid(v[0]) for vs in self.lanes.values() for v in vs if v[5] is not None}
        pick = [c for c in chans if _cid(c) in fading] or chans
        return min(pick, key=lambda c: self._started.get(_cid(c), 0.0))

    def _forget(self, ch):
        c = _cid(ch)
        for lane in list(self.lanes):
            self.lanes[lane] = [v for v in self.lanes[lane] if _cid(v[0]) != c]

    def _damp(self, v, ms):
        if v[5] is not None or not self._sounding(v):
            return
        try:
            v[0].fadeout(max(1, int(ms)))
        except Exception:
            return
        v[5] = (time.monotonic(), max(1, int(ms)) / 1000.0)

    def damp(self, lane, ms=DAMP_MS):
        """Mute ``lane``'s ringing strings (the palm comes down)."""
        for v in self.lanes.get(lane, []):
            self._damp(v, ms)

    def _level_now(self, v, now):
        lvl = v[4] * note_env(v[2], now - v[3])
        if v[5] is not None:
            lvl *= max(0.0, 1.0 - (now - v[5][0]) / v[5][1])
        return lvl

    def _gain(self, lane, vels, now):
        """One level for a whole strum, so the mix never clips (SDL just
        clamps the sum). What still rings counts at what it has decayed to
        (this lane's old chord only partly: it is being damped); if that is
        not enough, the partner's ring gives way a little first."""
        v = self.volume()
        mine, other, load = [], [], 0.0
        for e in self._live():
            lvl = self._level_now(e, now)
            if any(e is q for q in self.lanes.get(lane, [])):
                load += 0.5 * lvl                   # damped under the first strings
                mine.append(e)
            else:
                load += lvl
                if e[5] is None:
                    other.append(e)
        room = HEADROOM / max(v, 1e-3)
        want = strum_total(vels)
        over = want + 0.8 * load - room
        if over > 0 and other:
            sub = sum(self._level_now(e, now) for e in other)
            d = max(DUCK_MIN, 1.0 - over / (0.8 * sub)) if sub > 0 else 1.0
            if d < 1.0:
                for e in other:
                    e[4] *= d
                    self._set_vol(e, v)
                load -= sub * (1.0 - d)
        over = want + 0.8 * load - room
        if over <= 0:
            return 1.0
        return max(FLOOR, (room - 0.8 * load) / max(1e-6, want))

    @staticmethod
    def _set_vol(e, v):
        try:
            e[0].set_volume(max(0.0, min(1.0, e[4] * v)))
        except Exception:
            pass

    def strum(self, lane, midis, plan):
        """Play ``plan`` (from ``plan_strum``) on the strings ``midis`` of
        ``lane`` (("me",), ("remote",) ...): the lane's old chord is damped,
        the new one balanced and started -- every string on this mixer tick,
        each with its own lead-in of silence. Returns the gain it got."""
        if not self.enabled or not plan:
            return 0.0
        for i, _t, _v in plan:
            if self.sound(midis[i]) is None:
                return 0.0
        now = time.monotonic()
        gain = self._gain(lane, [v for _i, _t, v in plan], now)
        self.damp(lane)
        vol = self.volume()
        old = self.lanes.get(lane, [])
        new, taken = [], set()
        for i, t, vel in plan:
            m = midis[i]
            ch = self._channel(taken)
            if ch is None:
                break
            taken.add(_cid(ch))
            self._forget(ch)
            try:
                snd = self._delayed(m, int(t * self.sr))
                ent = [ch, snd, m, now + t, vel * gain, None]
                self._set_vol(ent, vol)
                ch.play(snd)
            except Exception:
                self._chans = []
                break
            self._started[_cid(ch)] = now
            new.append(ent)
        old = [v for v in old if self._sounding(v)]
        others = {k: vs for k, vs in self.lanes.items() if k != lane}
        # the damped strings stay listed (fading) until they end
        self.lanes = others
        self.lanes[lane] = new + [v for v in old if not any(v is q for q in new)]
        return gain

    def active(self, lane=None):
        """Strings really sounding (and not being damped) right now."""
        vs = self._live() if lane is None else [v for v in self.lanes.get(lane, [])
                                                if self._sounding(v)]
        return sum(1 for v in vs if v[5] is None)

    def release_all(self, lane, ms=380):
        """Put the guitar down: ``lane``'s strings die away gently."""
        self.damp(lane, ms)


def synth(audio):
    """The GuitarSynth that lives on ``audio`` (the baked strings are shared
    per mixer format, so they survive closing the guitar or a new Game)."""
    real = getattr(audio, "_real", None) or audio
    s = getattr(real, "_guitar_synth", None)
    if s is None:
        s = GuitarSynth(real)
        try:
            real._guitar_synth = s
        except Exception:
            pass
    return s


# the chords everybody reaches for first, then the rest of the grid
_WARM_FIRST = ("C", "G", "D", "A", "E", "Am", "Em", "Dm", "F", "G7", "D7", "A7", "E7", "C7")


def warm_order(first=()):
    """Every string pitch the grid uses: ``first`` chords', then the common
    open chords', then the rest."""
    order = []
    for cid in list(first) + list(_WARM_FIRST) + CHORD_IDS:
        order += [m for m in voicing(cid) if m is not None]
    return list(dict.fromkeys(order))


def prewarm_all(audio):
    """Bake every string pitch once per session (daemon thread)."""
    synth(audio).prewarm(warm_order())


# ------------------------------------------------------------------ art helpers
def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _dk(c, f=0.7):
    return tuple(max(0, int(v * f)) for v in c[:3])


def _lt(c, f=1.2):
    return tuple(min(255, int(v * f)) for v in c[:3])


_FONTS = {}
_GLYPHS = {}


def _serif(size, italic=True, bold=False):
    key = (size, italic, bold)
    f = _FONTS.get(key)
    if f is None:
        f = _FONTS[key] = pygame.font.SysFont("georgia,palatinolinotype,timesnewroman",
                                              size, bold=bold, italic=italic)
    return f


def _note_glyph(color, size):
    """A little quaver with a dark rim (floating notes)."""
    key = ("q", color, size)
    s = _GLYPHS.get(key)
    if s is not None:
        return s
    w, h = int(size * 2.2) + 4, int(size * 3.0) + 4

    def paint(surf, col, grow):
        head = pygame.Rect(0, 0, int(size * 1.3) + grow * 2, int(size * 0.95) + grow * 2)
        head.bottomleft = (2 - grow, h - 2 + grow)
        pygame.draw.ellipse(surf, col, head)
        sx = head.right - 2 - grow
        top = 3
        pygame.draw.line(surf, col, (sx, head.centery), (sx, top - grow), max(2, size // 4) + grow * 2)
        pygame.draw.polygon(surf, col, [(sx - grow, top - grow),
                                        (sx + size * 0.95 + grow, top + size * 0.95),
                                        (sx + size * 0.7, top + size * 1.3 + grow),
                                        (sx - grow, top + size * 0.62 + grow)])
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    paint(s, _dk(color, 0.45), 1)
    paint(s, color, 0)
    _GLYPHS[key] = s
    return s


def _heart(surf, cx, cy, r, color):
    rr = max(2, int(r * 0.55))
    pygame.draw.circle(surf, color, (int(cx - r * 0.45), int(cy - r * 0.2)), rr)
    pygame.draw.circle(surf, color, (int(cx + r * 0.45), int(cy - r * 0.2)), rr)
    pygame.draw.polygon(surf, color, [(cx - r * 0.98, cy - r * 0.05), (cx + r * 0.98, cy - r * 0.05),
                                      (cx, cy + r)])


def _heart_glyph(color, size):
    key = ("h", color, size)
    s = _GLYPHS.get(key)
    if s is None:
        s = pygame.Surface((size * 2 + 6, size * 2 + 6), pygame.SRCALPHA)
        c = size + 3
        _heart(s, c, c, size + 1, _dk(color, 0.6))
        _heart(s, c, c, size, color)
        _GLYPHS[key] = s
    return s


def _spark_glyph(color, size):
    key = ("s", color, size)
    s = _GLYPHS.get(key)
    if s is None:
        s = pygame.Surface((size * 2 + 2, size * 2 + 2), pygame.SRCALPHA)
        c = size + 1
        q = max(1, size // 3)
        pygame.draw.polygon(s, color, [(c, 0), (c + q, c - q), (size * 2 + 1, c), (c + q, c + q),
                                       (c, size * 2 + 1), (c - q, c + q), (0, c), (c - q, c - q)])
        _GLYPHS[key] = s
    return s


_SHADE = {}


def _shadow(w, h, radius, alpha):
    key = ("drop", w, h, radius, alpha)
    s = _SHADE.get(key)
    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(s, (40, 20, 30, alpha), s.get_rect(), border_radius=radius)
        _SHADE[key] = s
    return s


def _chaikin(pts, rounds=3):
    for _ in range(rounds):
        out = []
        n = len(pts)
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            out.append((a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25))
            out.append((a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75))
        pts = out
    return pts


# ------------------------------------------------------------------ layout
PANEL = pygame.Rect(40, 116, 1200, 568)
CY = 281                                     # the strings' centre line
BODY_X0 = 72                                 # tail of the body
BODY_L = 272                                 # tail -> neck joint (a cosy parlour guitar)
SADDLE_X = 186
PIN_X = 174
NUT_X = 526
SCALE = NUT_X - SADDLE_X
HOLE = (BODY_X0 + 198, CY, 27)               # sound hole centre + radius
BOARD_END = HOLE[0] + HOLE[2] + 5            # the fingerboard ends at the sound hole
PICK_X = 236                                 # where the strumming hand plays
STR_NUT = 6.6                                # string spacing at the nut / the saddle
STR_SAD = 10.6
INFO = pygame.Rect(648, 197, 568, 168)       # chord name + chord box
DIAG = pygame.Rect(INFO.right - 196, INFO.y + 10, 184, 148)
SHEET = pygame.Rect(64, 374, 1152, 68)
PLAY_X = SHEET.x + 196                       # song mode: where the next chord sits
PAD_W, PAD_H, PAD_GX, PAD_GY = 145, 44, 9, 8
PAD_X0 = SHEET.right - 7 * PAD_W - 6 * PAD_GX
PAD_Y0 = 454
# the body's half-outline: (share of the length from the tail, half height)
_BODY_HALF = [(0.0, 0), (0.006, 30), (0.03, 55), (0.075, 72), (0.14, 83), (0.23, 88),
              (0.33, 86), (0.43, 78), (0.51, 68), (0.57, 62), (0.62, 61), (0.68, 63),
              (0.76, 67), (0.83, 65), (0.9, 57), (0.95, 44), (0.98, 28), (0.995, 12), (1.0, 0)]


def fret_x(k):
    """Screen x of fret wire ``k`` (0 = the nut)."""
    return NUT_X - SCALE * (1.0 - 2.0 ** (-k / 12.0))


def string_y(i, x):
    """Screen y of string ``i`` (0 = low E, on top) at screen x."""
    s = (x - SADDLE_X) / float(NUT_X - SADDLE_X)
    sp = STR_SAD + (STR_NUT - STR_SAD) * s
    return CY + (i - 2.5) * sp


def board_half(x):
    """Half the fingerboard's width at screen x."""
    s = (x - BOARD_END) / float(NUT_X - BOARD_END)
    return 25 + (20 - 25) * s


def pad_rect(row, col):
    return pygame.Rect(PAD_X0 + col * (PAD_W + PAD_GX), PAD_Y0 + row * (PAD_H + PAD_GY), PAD_W, PAD_H)


PAD_RECTS = {GRID[r][c]: pad_rect(r, c) for r in range(3) for c in range(7)}


def _mode_rects():
    w_free = 118                                 # (no fonts at import time)
    w_song = 400
    arrow = 30
    gap = 8
    total = w_free + gap * 3 + arrow * 2 + w_song
    x = PANEL.centerx - total // 2
    free = pygame.Rect(x, 156, w_free, 28)
    left = pygame.Rect(free.right + gap, 156, arrow, 28)
    song = pygame.Rect(left.right + gap, 156, w_song, 28)
    right = pygame.Rect(song.right + gap, 156, arrow, 28)
    return free, left, song, right


MODE_FREE, MODE_PREV, MODE_SONG, MODE_NEXT = _mode_rects()


# ------------------------------------------------------------------ the guitar art
_ART = {}


def _body_outline():
    top = [(BODY_X0 + u * BODY_L, CY - h) for u, h in _BODY_HALF]
    bot = [(BODY_X0 + u * BODY_L, CY + h) for u, h in reversed(_BODY_HALF[1:-1])]
    return _chaikin(top + bot, 3)


def _scaled(pts, cx, cy, k, ky=None):
    ky = k if ky is None else ky
    return [(cx + (x - cx) * k, cy + (y - cy) * ky) for x, y in pts]


def guitar_art(color):
    """The still guitar (everything but the strings), cached per colour:
    (surface, its top-left)."""
    key = tuple(color)
    got = _ART.get(key)
    if got is not None:
        return got
    ox, oy = BODY_X0 - 14, CY - 112
    W, H = NUT_X + 124 - ox, 226
    s = pygame.Surface((W, H), pygame.SRCALPHA)

    def P(pts):
        return [(x - ox, y - oy) for x, y in pts]

    body = _body_outline()
    joint = BODY_X0 + BODY_L
    edge = _mix(_dk(color, 0.5), (70, 34, 22), 0.45)
    honey = (246, 204, 138)
    # drop shadow
    sh = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.polygon(sh, (40, 20, 30, 70), [(x + 5, y + 7) for x, y in P(body)])
    neck_sh = [(joint, CY - 22), (NUT_X + 104, CY - 30), (NUT_X + 104, CY + 30), (joint, CY + 22)]
    pygame.draw.polygon(sh, (40, 20, 30, 60), [(x + 5, y + 7) for x, y in P(neck_sh)])
    s.blit(sh, (0, 0))
    # sides peek out below the top (a little depth)
    pygame.draw.polygon(s, _dk(edge, 0.7), [(x, y + 5) for x, y in P(body)])
    # the top: a sunburst, the piece's colour at the rim fading to honey spruce
    cx, cy = BODY_X0 + 0.42 * BODY_L, CY
    steps = 16
    for j in range(steps):
        t = j / (steps - 1)
        k = 1.0 - 0.6 * t
        col = _mix(edge, honey, min(1.0, t * 1.7) ** 0.8)
        pygame.draw.polygon(s, col, P(_scaled(body, cx, cy, k, 1.0 - 0.55 * t)))
    # spruce grain: faint lines along the strings
    for gy in range(CY - 86, CY + 87, 5):
        xs = [x for x, y in _body_span(body, gy)]
        if len(xs) == 2:
            a = (gy * 37) % 11 / 11.0
            c = _mix(honey, (214, 164, 100), 0.18 + 0.12 * a)
            tmp = pygame.Surface((int(xs[1] - xs[0]) - 12, 1), pygame.SRCALPHA)
            tmp.fill((*c, 70))
            s.blit(tmp, (xs[0] + 6 - ox, gy - oy))
    # binding + purfling
    pygame.draw.polygon(s, (60, 34, 24), P(body), 3)
    pygame.draw.polygon(s, (240, 222, 190), P(_scaled(body, cx, cy, 0.975, 0.955)), 1)
    # pickguard: a tortoiseshell teardrop hugging the sound hole on the treble side
    hx, hy, hr = HOLE
    guard = []
    for a in range(0, 361, 10):
        rad = math.radians(a)
        down = max(0.0, math.sin(rad))                 # (drips toward the bridge side)
        left = max(0.0, -math.cos(rad))
        rr = hr + 12 + 16 * down * (0.4 + 0.6 * left)
        guard.append((hx - 4 + math.cos(rad) * rr, hy + 8 + math.sin(rad) * rr * 0.92))
    gs = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.polygon(gs, (104, 50, 32, 215), P(guard))
    for j in range(9):                                 # soft amber mottling
        rnd = random.Random(j * 13 + 5)
        gx_, gy_ = rnd.uniform(hx - 34, hx + 22), rnd.uniform(hy + 14, hy + 44)
        pygame.draw.ellipse(gs, (156, 86, 44, 70),
                            (int(gx_ - ox), int(gy_ - oy), rnd.randint(8, 16), rnd.randint(4, 8)))
    mask = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), P(guard))
    gs.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    s.blit(gs, (0, 0))
    pygame.draw.polygon(s, (72, 34, 22), P(guard), 1)
    # sound hole: rosette rings, the dark inside
    c0 = (hx - ox, hy - oy)
    pygame.draw.circle(s, (70, 40, 26), c0, hr + 13)
    pygame.draw.circle(s, (240, 222, 190), c0, hr + 11)
    for rr, col in ((hr + 9, (122, 70, 40)), (hr + 7, (206, 150, 92)), (hr + 5, (122, 70, 40)),
                    (hr + 3, (240, 222, 190))):
        pygame.draw.circle(s, col, c0, rr)
    pygame.draw.circle(s, (34, 20, 16), c0, hr)
    pygame.draw.circle(s, (54, 32, 22), (c0[0] + 6, c0[1] + 5), hr - 8)
    pygame.draw.circle(s, (26, 16, 12), (c0[0] - 3, c0[1] - 2), hr - 10)
    # the bridge (rosewood, with its moustache ends) + saddle + pins
    br = pygame.Rect(0, 0, 40, 84)
    br.center = (PIN_X + 4 - ox, CY - oy)
    pygame.draw.rect(s, (52, 30, 22), br.move(1, 2), border_radius=10)
    pygame.draw.rect(s, (84, 48, 32), br, border_radius=10)
    for side in (-1, 1):
        wing = pygame.Rect(0, 0, 30, 20)
        wing.center = (br.centerx - 4, br.centery + side * 46)
        pygame.draw.ellipse(s, (84, 48, 32), wing)
    pygame.draw.line(s, (120, 76, 50), (br.x + 5, br.y + 4), (br.x + 5, br.bottom - 5), 2)
    pygame.draw.line(s, (246, 238, 222), (SADDLE_X - ox, string_y(0, SADDLE_X) - 6 - oy),
                     (SADDLE_X - ox, string_y(5, SADDLE_X) + 6 - oy), 3)
    for i in range(6):
        y = string_y(i, SADDLE_X) - oy
        pygame.draw.circle(s, (236, 226, 204), (PIN_X - ox, int(y)), 3)
        pygame.draw.circle(s, (120, 96, 70), (PIN_X - ox, int(y)), 3, 1)
    # the neck (mahogany) under the fingerboard, the heel on the body
    neck = [(joint - 8, CY - board_half(joint) - 2), (NUT_X, CY - board_half(NUT_X) - 2),
            (NUT_X, CY + board_half(NUT_X) + 2), (joint - 8, CY + board_half(joint) + 2)]
    pygame.draw.polygon(s, (120, 70, 42), P(neck))
    heel = pygame.Rect(0, 0, 22, int(board_half(joint) * 2 + 8))
    heel.center = (joint - 2 - ox, CY - oy)
    pygame.draw.ellipse(s, (104, 60, 36), heel)
    # the fingerboard (rosewood), frets, inlays
    fb = [(BOARD_END, CY - board_half(BOARD_END)), (NUT_X, CY - board_half(NUT_X)),
          (NUT_X, CY + board_half(NUT_X)), (BOARD_END, CY + board_half(BOARD_END))]
    pygame.draw.polygon(s, (66, 40, 30), P(fb))
    pygame.draw.line(s, (98, 62, 44), P([(BOARD_END, CY - board_half(BOARD_END) + 1)])[0],
                     P([(NUT_X, CY - board_half(NUT_X) + 1)])[0], 1)
    for k in range(1, 20):
        x = fret_x(k)
        if x < BOARD_END + 2:
            break
        hb = board_half(x)
        pygame.draw.line(s, (150, 150, 158), (x - ox + 1, CY - hb - oy), (x - ox + 1, CY + hb - oy), 1)
        pygame.draw.line(s, (226, 226, 232), (x - ox, CY - hb - oy), (x - ox, CY + hb - oy), 2)
    for k in (3, 5, 7, 9, 12, 15, 17):
        x = (fret_x(k - 1) + fret_x(k)) / 2
        if x < BOARD_END + 4:
            continue
        ys = (CY - 9, CY + 9) if k == 12 else (CY,)
        for y in ys:
            pygame.draw.circle(s, (238, 232, 220), (int(x - ox), int(y - oy)), 3)
    # the nut (bone)
    nut = pygame.Rect(0, 0, 5, int(board_half(NUT_X) * 2 + 4))
    nut.center = (NUT_X + 1 - ox, CY - oy)
    pygame.draw.rect(s, (246, 240, 224), nut, border_radius=2)
    pygame.draw.rect(s, (190, 178, 150), nut, 1, border_radius=2)
    # the headstock + tuners
    hs = [(NUT_X + 3, CY - 23), (NUT_X + 90, CY - 29), (NUT_X + 104, CY - 24),
          (NUT_X + 106, CY), (NUT_X + 104, CY + 24), (NUT_X + 90, CY + 29), (NUT_X + 3, CY + 23)]
    for side in (-1, 1):
        for j in range(3):
            px = NUT_X + 24 + j * 26
            pygame.draw.line(s, (170, 170, 178), (px - ox, CY + side * 22 - oy),
                             (px - ox, CY + side * 36 - oy), 3)
            btn = pygame.Rect(0, 0, 13, 9)
            btn.center = (px - ox, CY + side * 39 - oy)
            pygame.draw.rect(s, (236, 226, 200), btn, border_radius=4)
            pygame.draw.rect(s, (160, 146, 120), btn, 1, border_radius=4)
    pygame.draw.polygon(s, (52, 30, 22), P([(x + 1, y + 2) for x, y in hs]))
    pygame.draw.polygon(s, _mix(edge, (64, 36, 26), 0.5), P(hs))
    pygame.draw.polygon(s, (36, 20, 16), P(hs), 2)
    pygame.draw.line(s, _lt(_mix(edge, (64, 36, 26), 0.5), 1.35),
                     (NUT_X + 12 - ox, CY - 19 - oy), (NUT_X + 88 - ox, CY - 24 - oy), 1)
    for i in range(6):
        px, py = _post(i)
        pygame.draw.circle(s, (120, 120, 128), (int(px - ox), int(py - oy)), 4)
        pygame.draw.circle(s, (214, 214, 222), (int(px - ox), int(py - oy)), 2)
    _ART[key] = (s, (ox, oy))
    return _ART[key]


def _body_span(body, y):
    """Where a horizontal line at ``y`` crosses the body (min x, max x)."""
    xs = []
    n = len(body)
    for i in range(n):
        (x1, y1), (x2, y2) = body[i], body[(i + 1) % n]
        if (y1 - y) * (y2 - y) < 0:
            xs.append(x1 + (x2 - x1) * (y - y1) / (y2 - y1))
    if len(xs) < 2:
        return []
    return [(min(xs), y), (max(xs), y)]


def _post(i):
    """Where string ``i`` winds onto its tuner (3 a side, E A D on top)."""
    if i < 3:
        return NUT_X + 24 + i * 26, CY - 14
    return NUT_X + 24 + (5 - i) * 26, CY + 14


def _string_style(i):
    """(colour, highlight, width): bronze wound strings, plain steel ones."""
    if i <= 3:
        return (196, 150, 84), (246, 214, 150), (3, 3, 2, 2)[i]
    return (206, 208, 216), (250, 250, 255), 2 if i == 4 else 1


# ------------------------------------------------------------------ the screen
class GuitarScreen:
    """The guitar off its stand: strings, chord grid and song book."""

    def __init__(self, game, pidx, stand, client=False):
        self.g = game
        self.pidx = pidx
        self._st = stand
        self.gx, self.gy = stand.gx, stand.gy
        self.client = client
        self.syn = synth(game.audio)
        self.mode = 0                   # 0 free play, 1.. = SONGS[mode - 1]
        self.last_song = 1
        self.chord = None               # the chord in the left hand
        self.down = True                # the last strum's direction
        self.shift = False
        self._keys = set()
        self.glow = {}                  # chord -> pad light 0..1
        self.vib = [None] * 6           # per string: [plucked at (clock), velocity, fret]
        self.pick = None                # the strumming hand: [started, [(y, t)], down]
        self.fx = []                    # [x, y, vx, vy, life, max, surf, phase]
        self.trail = []                 # free play: [chord, down, age]
        self.song_i = 0
        self.scroll = 0.0
        self.done_t = 0.0
        self.reward = ""
        self.demo = None                # listen: {"i", "beat", "t", "ups"}
        self.flourish = None            # [delay, chord]
        self.miss_t = 0.0
        self.phase, self.t, self.clock = "opening", 0.0, 0.0
        self.msg = ""
        self._chart = {}
        self._listen_rect = None
        self._set_msg()
        self.syn.prewarm(warm_order())

    # ---- data ----
    @property
    def p(self):
        return self.g.players[self.pidx]

    @property
    def partner(self):
        try:
            return self.g.players[1 - self.pidx].name
        except Exception:
            return "love"

    @property
    def piece(self):
        """The live stand (a LAN world resync replaces Placed objects)."""
        home = self.g.world.home_furniture
        if any(q is self._st for q in home):
            return self._st
        for q in home:
            if q.kind == "guitar_stand" and q.gx == self.gx and q.gy == self.gy:
                self._st = q
                return q
        return self._st

    @property
    def song(self):
        return SONGS[self.mode - 1] if self.mode else None

    def words(self, step):
        return step[2].replace("{partner}", self.partner)

    def target(self):
        """The chord the song wants next (None in free play / when done)."""
        s = self.song
        if s is None or self.done_t > 0 or self.demo or self.song_i >= len(s["steps"]):
            return None
        return s["steps"][self.song_i][0]

    def _set_msg(self):
        s = self.song
        if s is None:
            self.msg = (f"{self.p.name} picks up the guitar - every key strums a whole chord! "
                        "Hold Shift to strum up.")
        else:
            self.msg = f"{s['title']}: strum the glowing chord! (Enter to listen first)"

    # ---- playing ----
    def strum(self, cid, down=True, vel=None, src="k", gap=None):
        """Strum chord ``cid``: sound, strings, pads, song book, the room."""
        if self.phase == "closing" or cid not in SHAPES:
            return
        midis = voicing(cid)
        plan = plan_strum(midis, down, vel if vel is not None else random.uniform(0.9, 1.0), gap)
        self.syn.strum(("me",), midis, plan)
        self.chord, self.down = cid, down
        self.glow[cid] = 1.0
        now = self.clock
        fr = frets(cid)
        self.vib = [None] * 6
        for i, t, v in plan:
            self.vib[i] = [now + t, v, fr[i]]
        first = plan[0][1] if plan else 0.0
        last = plan[-1][1] if plan else 0.0
        self.pick = [now, [(string_y(i, PICK_X), now + t) for i, t, _v in plan], down]
        self.trail.append([cid, down, 0.0, None])
        self.trail = self.trail[-40:]
        self._spawn(cid, last - first)
        self.g._guitar_strum(self, cid, down)
        if src in ("k", "mouse"):
            if self.demo:
                self._stop_demo()
            self._song_check(cid)

    def again(self, down=True):
        """Space: the last chord once more (the song book's first chord if none yet)."""
        cid = self.chord or self.target() or "C"
        self.strum(cid, down)

    def _spawn(self, cid, spread):
        col = chord_color(cid)
        hx, hy, hr = HOLE
        for j in range(2):
            self.fx.append([hx + random.uniform(-hr, hr) * 0.6, hy - random.uniform(0, 10),
                            random.uniform(-40, 40), random.uniform(-150, -100), 1.4, 1.4,
                            _note_glyph(_mix(col, (255, 255, 255), 0.15 * j),
                                        random.choice((8, 9, 10))),
                            random.uniform(0, 6.28)])
        if random.random() < 0.35:
            self.fx.append([hx + random.uniform(-12, 12), hy - 12, random.uniform(-20, 20),
                            random.uniform(-110, -80), 1.5, 1.5,
                            _heart_glyph((255, 150, 180), random.choice((5, 6))), 0.0])

    # ---- song book ----
    def set_mode(self, mode):
        mode %= len(SONGS) + 1
        self._stop_demo()
        self.flourish = None
        self.mode = mode
        if mode:
            self.last_song = mode
        self.song_i, self.scroll, self.done_t, self.reward = 0, 0.0, 0.0, ""
        self._set_msg()
        if mode:
            self.syn.prewarm(warm_order([c for c, _b, _w in self.song["steps"]]))

    def _song_check(self, cid):
        want = self.target()
        if want is None:
            return
        if cid != want:
            self.miss_t = 0.45                          # a gentle wiggle, no penalty
            return
        x = PLAY_X + 30
        for _ in range(6):
            self.fx.append([x, SHEET.y + 48, random.uniform(-70, 70), random.uniform(-80, 10),
                            0.5, 0.5, _spark_glyph((255, 214, 110), 4), 0.0])
        self.song_i += 1
        if self.song_i >= len(self.song["steps"]):
            self._finish()

    def _finish(self):
        s = self.song
        self.done_t = 3.4
        self.reward = self.g._guitar_song_done(self, s["id"]) or ""
        self.msg = f"Bravo! {self.p.name} played {s['title']}."
        cx, cy = SHEET.centerx, SHEET.centery - 60
        for _ in range(26):
            side = random.choice((-1, 1))
            col = random.choice([(255, 110, 150), (255, 150, 180), (255, 190, 200), (240, 120, 120)])
            self.fx.append([cx + side * random.uniform(170, 250), cy + random.uniform(-24, 24),
                            side * random.uniform(30, 160), random.uniform(-200, -60), 1.6, 1.6,
                            _heart_glyph(col, random.choice((6, 7, 8))), 0.0])
        for _ in range(18):
            self.fx.append([random.uniform(80, NUT_X + 90), random.uniform(200, 360),
                            random.uniform(-30, 30), random.uniform(-60, -20), 1.2, 1.2,
                            _spark_glyph(random.choice([(255, 226, 120), (255, 255, 255),
                                                        (180, 230, 255)]), 5), 0.0])
        # the guitar answers with one slow, ringing strum of the home chord
        self.flourish = [0.35, s["steps"][-1][0]]

    def listen(self):
        if self.song is None:
            return
        if self.demo:
            self._stop_demo()
            self._set_msg()
            return
        self.flourish = None
        self.song_i, self.scroll, self.done_t = 0, 0.0, 0.0
        self.demo = {"i": 0, "beat": 0, "t": 0.3, "up": None, "show": 0}
        self.msg = f"Listen... then strum {self.song['title']} yourself!"

    def _stop_demo(self):
        if self.demo:
            self.demo = None
            self.song_i, self.scroll = 0, 0.0

    # ---- input ----
    def _shift_on(self, e=None):
        mod = getattr(e, "mod", 0) if e is not None else 0
        return bool(self.shift or (mod & pygame.KMOD_SHIFT))

    def handle_event(self, e):
        if self.phase == "closing":
            return
        t = e.type
        if t == pygame.KEYDOWN:
            self._keydown(e)
        elif t == pygame.KEYUP:
            if e.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                self.shift = False
            self._keys.discard(e.key)
        elif t == pygame.MOUSEBUTTONDOWN and getattr(e, "button", 1) in (1, 3):
            self._click(e.pos, getattr(e, "button", 1) == 3)
        elif t == getattr(pygame, "WINDOWFOCUSLOST", -1):
            self._keys.clear()
            self.shift = False

    def _keydown(self, e):
        k = e.key
        if k in self._keys:
            return                                      # key repeat: one strum per press
        self._keys.add(k)
        if k in (pygame.K_LSHIFT, pygame.K_RSHIFT):
            self.shift = True
        elif k in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.close()
        elif k == pygame.K_TAB:
            back = bool(getattr(e, "mod", 0) & pygame.KMOD_SHIFT)
            self.set_mode(self.mode + (-1 if back else 1))
            self._page_sfx()
        elif k in (pygame.K_UP, pygame.K_DOWN):
            self.set_mode(self.mode + (-1 if k == pygame.K_UP else 1))
            self._page_sfx()
        elif k == pygame.K_SPACE:
            self.again(not self._shift_on(e))
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.listen()
        else:
            cid = SCAN_CHORD.get(getattr(e, "scancode", 0) or -1) or KEY_CHORD.get(k)
            if cid is not None:
                self.strum(cid, not self._shift_on(e))

    def _page_sfx(self):
        self.g.audio.play("page" if "page" in getattr(self.g.audio, "sfx", {}) else "ui_move")

    def _click(self, pos, up=False):
        if MODE_FREE.collidepoint(pos):
            if self.mode:
                self.set_mode(0)
                self.g.audio.play("ui_move")
            return
        if MODE_SONG.collidepoint(pos):
            if not self.mode:
                self.set_mode(self.last_song)
                self.g.audio.play("ui_move")
            return
        if MODE_PREV.collidepoint(pos) or MODE_NEXT.collidepoint(pos):
            cur = self.mode or self.last_song
            d = -1 if MODE_PREV.collidepoint(pos) else 1
            self.set_mode((cur - 1 + d) % len(SONGS) + 1)
            self._page_sfx()
            return
        if self._listen_rect and self._listen_rect.collidepoint(pos) and self.song:
            self.listen()
            return
        for cid, r in PAD_RECTS.items():
            if r.collidepoint(pos):
                self.strum(cid, not up, src="mouse")
                return

    def close(self):
        if self.phase == "closing":
            return
        self._stop_demo()
        self.flourish = None
        self.syn.release_all(("me",))
        self.phase, self.t = "closing", 0.0

    # ---- update ----
    def update(self, dt):
        self.clock += dt
        self.t += dt
        if self.phase == "opening" and self.t >= OPEN_T:
            self.phase, self.t = "play", 0.0
        elif self.phase == "closing":
            if self.t >= CLOSE_T:
                self.g._guitar_closed(self)
            return
        for c in list(self.glow):
            self.glow[c] -= dt * 2.4
            if self.glow[c] <= 0:
                del self.glow[c]
        # the strum queue: each chip slides to its slot (newest at the right)
        x = SHEET.right - 36
        for tr in reversed(self.trail):
            tr[2] += dt
            w = _TRAIL_W.get(tr[0] + ("d" if tr[1] else "u")) or (len(tr[0]) * 8 + 34)
            want = x - w / 2
            tr[3] = want if tr[3] is None else tr[3] + (want - tr[3]) * min(1.0, dt * 14)
            x -= w + 6
        self.trail = [tr for tr in self.trail if tr[2] < TRAIL_LIFE][-40:]
        for f in self.fx:
            f[0] += f[2] * dt + math.sin(self.clock * 5 + f[7]) * 14 * dt
            f[1] += f[3] * dt
            f[3] += 30 * dt
            f[2] *= max(0.0, 1.0 - dt * 1.5)
            f[4] -= dt
        self.fx = [f for f in self.fx if f[4] > 0][-160:]
        self.miss_t = max(0.0, self.miss_t - dt)
        self._update_demo(dt)
        if self.flourish:
            self.flourish[0] -= dt
            if self.flourish[0] <= 0:
                cid = self.flourish[1]
                self.flourish = None
                self.strum(cid, True, vel=0.95, src="flourish", gap=0.055)
        if self.done_t > 0:
            self.done_t -= dt
            if self.done_t <= 0:
                self.done_t, self.song_i, self.scroll, self.reward = 0.0, 0, 0.0, ""
                self.msg = f"Play {self.song['title']} again, or Tab for the next song."
        view = self.demo["show"] if self.demo else self.song_i
        if self.done_t > 0 and self.song:
            view = len(self.song["steps"]) - 1
        self.scroll += (max(0, view) - self.scroll) * min(1.0, dt * 9)

    def _update_demo(self, dt):
        d = self.demo
        if not d:
            return
        steps = self.song["steps"]
        beat = self.song["beat"]
        if d["up"] is not None:
            d["up"] -= dt
            if d["up"] <= 0:
                d["up"] = None
                if self.chord:
                    self.strum(self.chord, False, vel=0.8, src="demo")
        d["t"] -= dt
        if d["t"] > 0:
            return
        if d["i"] >= len(steps):
            self.demo = None
            self.song_i, self.scroll = 0, 0.0
            self.msg = f"Your turn! Strum {self.song['title']} - follow the glowing chords."
            return
        cid, beats, _w = steps[d["i"]]
        b = d["beat"]
        d["show"] = d["i"]
        self.strum(cid, True, vel=0.95 if b == 0 else 0.82, src="demo")
        if b % 2 == 1 and beat >= 0.4:
            d["up"] = beat * 0.5                        # D - D U - D - D U
        d["beat"] += 1
        d["t"] = beat
        if d["beat"] >= beats:
            d["i"] += 1
            d["beat"] = 0

    # ---- draw ----
    def _color(self):
        from . import furniture as F
        try:
            c = F.PALETTE[self.piece.ci % len(F.PALETTE)][1]
        except Exception:
            c = (140, 96, 60)
        if sum(c) > 660:                                # a white guitar: warm cream
            c = (226, 212, 186)
        return c

    def _lift(self):
        if self.phase == "opening":
            k = 1 - (1 - min(1.0, self.t / OPEN_T)) ** 3
        elif self.phase == "closing":
            k = 1 - min(1.0, self.t / CLOSE_T) ** 2
        else:
            return 0
        return int(30 * (1 - k))

    def draw(self, surf):
        K.dim(surf, 150)
        P = K.modal(surf, PANEL, "Guitar", K.font(28, True))
        self._draw_modes(surf)
        oy = self._lift()
        self._draw_guitar(surf, oy)
        self._draw_info(surf)
        self._draw_sheet(surf)
        self._draw_pads(surf)
        self._draw_fx(surf)
        f = K.fit_font(self.msg, P.w - 80, (15, 14, 13, 12), bold=True)
        K.blit_text(surf, f, self.msg, K.GOLD_TXT if self.done_t > 0 else K.INK_SOFT,
                    (P.centerx, 628))
        self._draw_hints(surf, P)

    def _draw_modes(self, surf):
        s = self.song or SONGS[self.last_song - 1]
        n = self.mode or self.last_song
        label = f"Song book:  {s['tab']}   {n}/{len(SONGS)}"
        K.tabs(surf, [MODE_FREE, MODE_SONG], ["Free play", label], 0 if not self.mode else 1,
               fnt_sizes=(15, 14, 13, 12))
        for r_, ch in ((MODE_PREV, "<"), (MODE_NEXT, ">")):
            pygame.draw.rect(surf, K.WOOD_DK, r_, border_radius=6)
            pygame.draw.rect(surf, K.CREAM, r_.inflate(-4, -4), border_radius=5)
            K.blit_text(surf, K.font(15, True), ch, K.INK, r_.center)

    # -- the guitar
    def _draw_guitar(self, surf, oy=0):
        art, (ax, ay) = guitar_art(self._color())
        surf.blit(art, (ax, ay + oy))
        now = self.clock
        cid = self.chord
        fr = frets(cid) if cid else [0] * 6
        # the strings: still, or a blur of motion that dies away
        ghost = pygame.Surface((NUT_X - SADDLE_X + 8, 64), pygame.SRCALPHA)
        gx0, gy0 = SADDLE_X - 4, CY - 32 + oy
        lines = []
        for i in range(6):
            col, hi, w = _string_style(i)
            f = fr[i]
            muted = cid is not None and f is None
            stop = fret_x(f) if f else NUT_X
            y0, y1 = string_y(i, SADDLE_X) + oy, string_y(i, NUT_X) + oy
            v = self.vib[i]
            amp, ph = 0.0, 0.0
            pygame.draw.line(surf, col, (PIN_X, string_y(i, SADDLE_X) + oy), (SADDLE_X, y0), 1)
            if v is not None and now >= v[0]:
                age = now - v[0]
                amp = (6.4 - 0.6 * i) * v[1] * math.exp(-age / 1.1)
                ph = math.cos(2 * math.pi * (8.5 + 1.7 * i) * age)
            if muted:
                col, hi = _mix(col, (120, 100, 90), 0.5), _mix(hi, (140, 120, 110), 0.5)
            if amp < 0.25:
                pygame.draw.line(surf, _dk(col, 0.55), (SADDLE_X, y0 + 1), (NUT_X, y1 + 1), 1)
                pygame.draw.line(surf, col, (SADDLE_X, y0), (NUT_X, y1), w)
                if w >= 2:
                    pygame.draw.line(surf, hi, (SADDLE_X, y0 - (w > 2)), (NUT_X, y1 - (w > 2)), 1)
            else:
                pts, band_a, band_b = [], [], []
                n = 26
                for j in range(n + 1):
                    x = SADDLE_X + (stop - SADDLE_X) * j / n
                    yb = string_y(i, x) + oy
                    sh = math.sin(math.pi * j / n)
                    pts.append((x, yb + amp * ph * sh))
                    band_a.append((x - gx0, yb - amp * sh - gy0))
                    band_b.append((x - gx0, yb + amp * sh - gy0))
                band = band_a + band_b[::-1]
                if len(band) >= 3:
                    pygame.draw.polygon(ghost, (*hi, int(min(150, 60 + 30 * amp))), band)
                    pygame.draw.lines(ghost, (*_dk(col, 0.8), 110), False, band_a, 1)
                    pygame.draw.lines(ghost, (*_dk(col, 0.8), 110), False, band_b, 1)
                lines.append((pts, col, hi, w, (stop, string_y(i, stop) + oy), (NUT_X, y1)))
            # the part between the finger and the nut is still
        surf.blit(ghost, (gx0, gy0))
        for pts, col, hi, w, a, b in lines:
            pygame.draw.lines(surf, col, False, pts, w)
            if w >= 2:
                pygame.draw.lines(surf, hi, False, [(x, y - 1) for x, y in pts], 1)
            pygame.draw.line(surf, col, a, b, w)
        # strings past the nut to their tuners
        for i in range(6):
            col, hi, w = _string_style(i)
            px, py = _post(i)
            pygame.draw.line(surf, col, (NUT_X + 2, string_y(i, NUT_X) + oy), (px, py + oy), 1)
        # the fretting hand: dots on the neck (and the barre)
        if cid:
            self._draw_fingers(surf, cid, oy)
        self._draw_pick(surf, oy)

    def _draw_fingers(self, surf, cid, oy):
        col = chord_color(cid)
        rim = _dk(col, 0.5)
        fr = frets(cid)
        bar = BARRES.get(cid)
        if bar:
            f, a, b = bar
            x = fret_x(f) + (fret_x(f - 1) - fret_x(f)) * 0.42
            r = pygame.Rect(0, 0, 11, int(string_y(b, x) - string_y(a, x)) + 12)
            r.center = (int(x), int((string_y(a, x) + string_y(b, x)) / 2) + oy)
            pygame.draw.rect(surf, rim, r.inflate(2, 2), border_radius=6)
            pygame.draw.rect(surf, col, r, border_radius=5)
            pygame.draw.line(surf, _lt(col, 1.3), (r.x + 3, r.y + 4), (r.x + 3, r.bottom - 5), 2)
        for i, f in enumerate(fr):
            if f is None:                               # a muted string: x by the nut
                x, y = NUT_X + 10, string_y(i, NUT_X) + oy
                pygame.draw.line(surf, (236, 100, 90), (x - 3, y - 3), (x + 3, y + 3), 2)
                pygame.draw.line(surf, (236, 100, 90), (x - 3, y + 3), (x + 3, y - 3), 2)
                continue
            if not f or (bar and f == bar[0] and bar[1] <= i <= bar[2]):
                continue
            x = fret_x(f) + (fret_x(f - 1) - fret_x(f)) * 0.42
            y = string_y(i, x) + oy
            pygame.draw.circle(surf, rim, (int(x), int(y)), 6)
            pygame.draw.circle(surf, col, (int(x), int(y)), 5)
            pygame.draw.circle(surf, _lt(col, 1.35), (int(x) - 2, int(y) - 2), 2)

    def _draw_pick(self, surf, oy):
        """The strumming hand's pick sweeps across the strings in time."""
        now = self.clock
        rest_y = CY + 44
        y = rest_y
        a = 150
        pk = self.pick
        if pk is not None:
            path = pk[1]
            if path:
                first_y, t0 = path[0]
                last_y, t1 = path[-1]
                lead = 0.05
                d = -1 if pk[2] else 1                  # the side it comes from
                if now < t0:
                    k = max(0.0, (now - (t0 - lead)) / lead)
                    y = first_y + d * 14 * (1 - k)
                elif now <= t1:
                    y = first_y
                    for (ya, ta), (yb, tb) in zip(path, path[1:]):
                        if ta <= now <= tb:
                            y = ya + (yb - ya) * (now - ta) / max(1e-4, tb - ta)
                            break
                else:
                    k = min(1.0, (now - t1) / 0.35)
                    y = last_y - d * 12 * min(1.0, (now - t1) / 0.06)
                    y += (rest_y - y) * (k ** 2)
                a = 255 if now - t1 < 0.35 else 150
                if now - t1 > 0.6:
                    self.pick = None
        cx, cy = PICK_X, int(y) + oy
        pts = [(cx - 9, cy - 8), (cx + 9, cy - 8), (cx + 1, cy + 11)]
        pk_s = pygame.Surface((30, 30), pygame.SRCALPHA)
        loc = [(x - cx + 15, yy - cy + 15) for x, yy in pts]
        pygame.draw.polygon(pk_s, (140, 40, 70, a), [(x, yy + 1) for x, yy in loc])
        pygame.draw.polygon(pk_s, (236, 110, 150, a), loc)
        pygame.draw.polygon(pk_s, (255, 190, 210, a), [(loc[0][0] + 4, loc[0][1] + 2),
                                                       (loc[1][0] - 7, loc[1][1] + 2),
                                                       (loc[0][0] + 5, loc[0][1] + 5)])
        surf.blit(pk_s, (cx - 15, cy - 15))

    # -- chord name + chord box
    def _draw_info(self, surf):
        K.well(surf, INFO)
        cid = self.chord
        left = pygame.Rect(INFO.x + 12, INFO.y + 8, DIAG.x - INFO.x - 24, INFO.h - 16)
        ncx = left.x + 96 + (left.w - 96) // 2         # the name's centre (badge on the left)
        self._draw_badge(surf, left.x + 50, left.y + 58)
        if cid is None:
            K.blit_text(surf, _serif(30, italic=True, bold=True), "Pick a chord",
                        K.INK_FAINT, (ncx, left.y + 52))
            K.blit_text(surf, K.font(13, True), "press a key below, or click a pad",
                        K.INK_FAINT, (ncx, left.y + 92))
        else:
            col = chord_color(cid)
            pop = self.glow.get(cid, 0.0)
            f = _serif(66 + int(8 * pop), italic=True, bold=True)
            ink = _mix(_dk(col, 0.55), (70, 40, 34), 0.35)
            K.blit_text(surf, f, cid, ink, (ncx, left.y + 50))
            K.blit_text(surf, K.font(15, True), chord_long(cid), K.INK_SOFT, (ncx, left.y + 102))
            # what each string sounds (x = not played)
            vs = voicing(cid)
            rp = root_pc(cid)
            fs, fn = K.font(11, True), K.font(14, True)
            for i, m in enumerate(vs):
                x = ncx + (i - 2.5) * 34
                K.blit_text(surf, fs, STRING_NAMES[i], K.INK_FAINT, (x, left.y + 124))
                if m is None:
                    K.blit_text(surf, fn, "x", K.WARN, (x, left.y + 142))
                else:
                    nm = NOTE_NAMES[m % 12]
                    K.blit_text(surf, fn, nm, _dk(col, 0.6) if m % 12 == rp else K.INK_SOFT,
                                (x, left.y + 142))
        self._draw_diagram(surf, cid)

    def _draw_badge(self, surf, cx, cy):
        """The strumming hand: which way the last strum went (Shift shows up)."""
        up = (not self.down) if self.chord else False
        if self.shift:
            up = True
        col = (84, 136, 222) if up else K.SPROUT
        pop = self.glow.get(self.chord, 0.0) if self.chord else 0.0
        r = 30 + int(3 * pop)
        pygame.draw.circle(surf, _mix(col, (255, 255, 255), 0.78), (cx, cy), r)
        pygame.draw.circle(surf, col, (cx, cy), r, 3)
        d = -1 if up else 1
        shaft = pygame.Rect(0, 0, 8, 22)
        shaft.center = (cx, cy - d * 5)
        pygame.draw.rect(surf, col, shaft, border_radius=3)
        pygame.draw.polygon(surf, col, [(cx - 12, cy + d * 3), (cx + 12, cy + d * 3),
                                        (cx, cy + d * 17)])
        K.blit_text(surf, K.font(13, True), "UP" if up else "DOWN", col, (cx, cy + r + 16))

    def _draw_diagram(self, surf, cid):
        d = DIAG
        pygame.draw.rect(surf, (253, 250, 240), d, border_radius=8)
        pygame.draw.rect(surf, K.WELL_LINE, d, 2, border_radius=8)
        sp = 24
        sx0 = d.centerx - int(2.5 * sp) + 6
        fy0, fsp, nf = d.y + 34, 24, 4
        fr = frets(cid) if cid else [None] * 6
        played = [f for f in fr if f]
        base = 1
        if played and max(played) > 4:
            base = min(played)
        col = chord_color(cid) if cid else K.INK_FAINT
        ink = (110, 96, 88)
        for k in range(nf + 1):
            y = fy0 + k * fsp
            wdt = 4 if (k == 0 and base == 1) else 1
            pygame.draw.line(surf, ink, (sx0, y), (sx0 + 5 * sp, y), wdt)
        for i in range(6):
            x = sx0 + i * sp
            pygame.draw.line(surf, ink, (x, fy0), (x, fy0 + nf * fsp), 1 if i > 2 else 2)
        if base > 1:
            K.blit_text(surf, K.font(12, True), f"{base}fr", K.INK_SOFT,
                        (sx0 - 8, fy0 + fsp // 2), align="right")
        for i in range(6):
            x = sx0 + i * sp
            K.blit_text(surf, K.font(11, True), STRING_NAMES[i], K.INK_FAINT,
                        (x, fy0 + nf * fsp + 10))
        if not cid:
            return
        for i, f in enumerate(fr):
            x = sx0 + i * sp
            y = fy0 - 11
            if f is None:
                pygame.draw.line(surf, K.WARN, (x - 4, y - 4), (x + 4, y + 4), 2)
                pygame.draw.line(surf, K.WARN, (x - 4, y + 4), (x + 4, y - 4), 2)
            elif f == 0:
                pygame.draw.circle(surf, K.INK_SOFT, (x, y), 5, 2)
        bar = BARRES.get(cid)
        if bar:
            f, a, b = bar
            y = fy0 + (f - base) * fsp + fsp // 2
            r = pygame.Rect(sx0 + a * sp - 8, y - 8, (b - a) * sp + 16, 16)
            pygame.draw.rect(surf, _dk(col, 0.5), r.inflate(2, 2), border_radius=8)
            pygame.draw.rect(surf, col, r, border_radius=8)
        for i, f in enumerate(fr):
            if not f or (bar and f == bar[0] and bar[1] <= i <= bar[2]):
                continue
            x = sx0 + i * sp
            y = fy0 + (f - base) * fsp + fsp // 2
            pygame.draw.circle(surf, _dk(col, 0.5), (x, y), 8)
            pygame.draw.circle(surf, col, (x, y), 7)
            pygame.draw.circle(surf, _lt(col, 1.3), (x - 2, y - 2), 2)

    # -- the chart sheet
    def _draw_sheet(self, surf):
        sh = SHEET
        surf.blit(_shadow(sh.w, sh.h, 6, 60), sh.move(3, 4))
        pygame.draw.rect(surf, (253, 250, 240), sh, border_radius=8)
        pygame.draw.rect(surf, K.WELL_LINE, sh, 2, border_radius=8)
        self._listen_rect = None
        if self.song is None:
            self._draw_free_sheet(surf)
        else:
            self._draw_song_sheet(surf, self.song)
        if self.done_t > 0:
            self._draw_bravo(surf)

    def _draw_free_sheet(self, surf):
        sh = SHEET
        K.blit_text(surf, _serif(19), "Free play", K.INK, (sh.x + 18, sh.y + 18), align="left")
        K.blit_text(surf, K.font(13, True),
                    "Space strums again  -  Shift strums up  -  right-click a pad strums up",
                    K.INK_FAINT, (sh.right - 18, sh.y + 18), align="right")
        # recent strums queue up across the page, newest on the right
        y = sh.y + 48
        clip = surf.get_clip()
        surf.set_clip(sh.inflate(-6, -4))
        if not self.trail:
            K.blit_text(surf, K.font(13, True), "your strums will line up here", K.INK_FAINT,
                        (sh.centerx, y))
        for tr in self.trail:
            cid, down, age, x = tr[0], tr[1], tr[2], tr[3]
            if x is None or x < sh.x - 60:
                continue
            fade = max(0.0, min(1.0, (x - sh.x) / 90.0, (TRAIL_LIFE - age) / 2.0, age / 0.12))
            col = chord_color(cid)
            txt = cid + (" ↓" if down else " ↑")
            f = K.font(13, True)
            w = f.size(txt)[0] + 14
            _TRAIL_W[cid + ("d" if down else "u")] = w
            r = pygame.Rect(0, 0, w, 20)
            r.center = (int(x), y)
            chip = pygame.Surface(r.size, pygame.SRCALPHA)
            pygame.draw.rect(chip, (*_mix(col, (255, 255, 255), 0.62), 255), chip.get_rect(),
                             border_radius=10)
            pygame.draw.rect(chip, (*_dk(col, 0.75), 255), chip.get_rect(), 1, border_radius=10)
            t = f.render(txt, True, _dk(col, 0.45))
            chip.blit(t, t.get_rect(center=(w // 2, 10)))
            chip.set_alpha(int(255 * fade))
            surf.blit(chip, r)
        surf.set_clip(clip)

    def _chart_layout(self, s):
        """x offsets + widths of the song's chord pills (cached per song + partner)."""
        key = (s["id"], self.partner)
        lay = self._chart.get(key)
        if lay is None:
            fc, fw = K.font(16, True), K.font(12, True)
            xs, ws, x = [], [], 0
            for step in s["steps"]:
                w = fc.size(step[0])[0] + fw.size(self.words(step))[0] + 30
                xs.append(x)
                ws.append(w)
                x += w + 10
            lay = self._chart[key] = (xs, ws)
        return lay

    def _draw_song_sheet(self, surf, s):
        sh = SHEET
        steps = s["steps"]
        r = K.blit_text(surf, _serif(19), s["title"], K.INK, (sh.x + 18, sh.y + 18), align="left")
        K.blit_text(surf, K.font(12, True), f"key of {s['key']}", K.INK_FAINT,
                    (r.right + 12, sh.y + 19), align="left")
        done = len(steps) if self.done_t > 0 else self.song_i
        bar = pygame.Rect(sh.x + 640, sh.y + 13, 170, 10)
        pygame.draw.rect(surf, K.WELL, bar, border_radius=5)
        if done:
            pygame.draw.rect(surf, K.LEAF, (bar.x, bar.y, max(10, bar.w * done // len(steps)), bar.h),
                             border_radius=5)
        pygame.draw.rect(surf, K.WELL_LINE, bar, 1, border_radius=5)
        K.blit_text(surf, K.font(13, True), f"{done} / {len(steps)}", K.INK_SOFT,
                    (bar.right + 10, bar.centery), align="left")
        lab = "Stop" if self.demo else "Listen"
        self._listen_rect = K.key_pill(surf, "Enter", lab, (sh.right - 72, sh.y + 18),
                                       fnt=K.font(12, True))
        # the chart: chord pills scrolling past the play line
        xs, ws = self._chart_layout(s)
        cur = self.demo["show"] if self.demo else self.song_i
        sc = self.scroll
        i0 = int(sc)
        frac = sc - i0
        base = xs[min(i0, len(xs) - 1)]
        if i0 + 1 < len(xs):
            base += (xs[i0 + 1] - xs[i0]) * frac
        y = sh.y + 48
        band = pygame.Surface((ws[min(max(0, cur), len(ws) - 1)] + 16, 30), pygame.SRCALPHA)
        band.fill((255, 214, 110, 50))
        clip = surf.get_clip()
        inner = sh.inflate(-8, -4)
        surf.set_clip(inner)
        if self.done_t <= 0 and 0 <= cur < len(steps):
            surf.blit(band, (PLAY_X - 8, y - 15))
        wob = math.sin(self.clock * 42) * 4 * min(1.0, self.miss_t / 0.45)
        fc, fw = K.font(16, True), K.font(12, True)
        for j, step in enumerate(steps):
            x = PLAY_X + xs[j] - base
            w = ws[j]
            if x > inner.right or x + w < inner.x:
                continue
            edge = max(0.0, min(1.0, (x + w - inner.x) / 60.0, (inner.right - x) / 60.0))
            hot = j == cur and self.done_t <= 0
            past = j < cur or self.done_t > 0
            rr = pygame.Rect(int(x + (wob if hot and not self.demo else 0)), y - 11, w, 22)
            col = chord_color(step[0])
            if hot:
                pulse = 0.5 + 0.5 * math.sin(self.clock * 6)
                rr = rr.inflate(4, 6)
                fill, rim = K.HILITE, _mix(K.GOLD_RIM, (240, 192, 104), pulse)
            elif past:
                fill, rim = _mix((253, 250, 240), (214, 236, 196), 0.8), (170, 206, 150)
            else:
                fill, rim = _mix((253, 250, 240), K.WELL, 0.9), K.WELL_LINE
            chip = pygame.Surface(rr.size, pygame.SRCALPHA)
            pygame.draw.rect(chip, (*fill, 255), chip.get_rect(), border_radius=11)
            pygame.draw.rect(chip, (*rim, 255), chip.get_rect(), 2 if hot else 1, border_radius=11)
            ct = fc.render(step[0], True, _dk(col, 0.55) if not past else (110, 150, 96))
            chip.blit(ct, (10, (rr.h - ct.get_height()) // 2))
            wt = fw.render(self.words(step), True, K.INK if hot else K.INK_SOFT)
            chip.blit(wt, (10 + ct.get_width() + 8, (rr.h - wt.get_height()) // 2 + 1))
            chip.set_alpha(int(255 * (edge if not hot else 1.0) * (0.6 if past and not hot else 1.0)))
            surf.blit(chip, rr)
        surf.set_clip(clip)

    def _draw_bravo(self, surf):
        k = min(1.0, (3.4 - self.done_t) / 0.25)
        band = pygame.Rect(0, 0, 470, 58)
        band.center = (SHEET.centerx, SHEET.centery - int(10 * math.sin(k * math.pi)))
        s = pygame.Surface(band.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (*K.CREAM_HI, 244), s.get_rect(), border_radius=14)
        pygame.draw.rect(s, (*K.HEART, 255), s.get_rect(), 3, border_radius=14)
        s.set_alpha(int(255 * min(1.0, 0.35 + k)))
        surf.blit(s, band)
        K.blit_text(surf, _serif(24, italic=True, bold=True), "Bravo!", (200, 70, 110),
                    (band.centerx, band.y + 20))
        sub = f"{self.song['title']}  -  " + (self.reward or "lovely!")
        f = K.fit_font(sub, band.w - 28, (14, 13, 12, 11), bold=True)
        K.blit_text(surf, f, sub, K.INK_SOFT, (band.centerx, band.y + 43))

    # -- the chord pads
    def _draw_pads(self, surf):
        tgt = self.target()
        nxt = []
        s = self.song
        if s is not None and tgt is not None:
            for c, _b, _w in s["steps"][self.song_i + 1:self.song_i + 3]:
                if c != tgt and c not in nxt:
                    nxt.append(c)
        hover = None
        try:
            if pygame.mouse.get_focused():
                mp = pygame.mouse.get_pos()
                hover = next((c for c, r in PAD_RECTS.items() if r.collidepoint(mp)), None)
        except Exception:
            hover = None
        for row, name in enumerate(ROW_NAMES):
            y = PAD_Y0 + row * (PAD_H + PAD_GY) + PAD_H // 2
            K.blit_text(surf, K.font(15, True), name, K.INK_SOFT, (PAD_X0 - 12, y), align="right")
        fk = K.font(13, True)
        for cid, base in PAD_RECTS.items():
            g = self.glow.get(cid, 0.0)
            col = chord_color(cid)
            r = base.inflate(int(6 * g), int(4 * g))
            hot = cid == tgt
            if hot:
                wob = math.sin(self.clock * 42) * 3 * min(1.0, self.miss_t / 0.45)
                r = r.move(int(wob), 0)
            sh = _shadow(r.w, r.h, 10, 60)
            surf.blit(sh, (r.x + 2, r.y + 3))
            face = K.CREAM_HI if hover == cid else (250, 242, 222)
            if hot:
                pulse = 0.5 + 0.5 * math.sin(self.clock * 6)
                face = _mix(K.HILITE, (255, 240, 200), 0.3 * pulse)
            if g > 0:
                face = _mix(face, _mix(col, (255, 255, 255), 0.45), g * 0.85)
            pygame.draw.rect(surf, face, r, border_radius=10)
            strip = pygame.Rect(r.x, r.y, 8, r.h)
            pygame.draw.rect(surf, col, strip, border_top_left_radius=10, border_bottom_left_radius=10)
            if hot:
                pulse = 0.5 + 0.5 * math.sin(self.clock * 6)
                pygame.draw.rect(surf, _mix(K.GOLD_RIM, (240, 192, 104), pulse), r.inflate(4, 4), 3,
                                 border_radius=12)
            else:
                pygame.draw.rect(surf, _mix(K.WELL_LINE, _dk(col, 0.8), g), r, 2, border_radius=10)
            f = _serif(24, italic=True, bold=True)
            K.blit_text(surf, f, cid, _mix(_dk(col, 0.5), (70, 40, 34), 0.35),
                        (r.x + 20, r.centery), align="left")
            kb = pygame.Rect(0, 0, 26, 26)
            kb.midright = (r.right - 8, r.centery)
            pygame.draw.rect(surf, K.WOOD_DK, kb.move(0, 2), border_radius=6)
            pygame.draw.rect(surf, K.WOOD, kb, border_radius=6)
            K.blit_text(surf, fk, KEY_LABEL[cid], K.CREAM_HI, kb.center)
            if cid in nxt:
                n = nxt.index(cid) + 2
                c = (kb.x - 16, r.centery)
                pygame.draw.circle(surf, (206, 230, 186), c, 9)
                pygame.draw.circle(surf, K.SPROUT, c, 9, 2)
                K.blit_text(surf, K.font(11, True), str(n), K.INK, c)

    def _draw_fx(self, surf):
        for f in self.fx:
            spr = f[6]
            a = int(255 * max(0.0, min(1.0, f[4] / f[5] * 1.6)))
            spr.set_alpha(a)
            surf.blit(spr, (f[0] - spr.get_width() // 2, f[1] - spr.get_height() // 2))
            spr.set_alpha(255)

    def hint_pills(self):
        pills = [("Q-U  A-J  Z-M", "Strum"), ("Shift", "Up-strum"), ("Space", "Again"),
                 ("Tab", "Songs")]
        if self.song:
            pills.append(("Enter", "Stop" if self.demo else "Listen"))
        pills.append(("Esc", "Put it back"))
        return pills

    def _draw_hints(self, surf, P):
        pills = self.hint_pills()
        f = K.font(13, True)
        widths = [f.size(k)[0] + f.size(lab)[0] + 38 for k, lab in pills]
        gap = 14
        x = P.centerx - (sum(widths) + gap * (len(widths) - 1)) // 2
        for (key, lab), w in zip(pills, widths):
            K.key_pill(surf, key, lab, (x + w // 2, 662), fnt=f)
            x += w + gap
