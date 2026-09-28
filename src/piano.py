"""The Piano: sit down and REALLY play it.

Use a placed Piano (or press Action while seated on the bench in front of one).
The fallboard slides open on a little upright: two octaves and a bit of ivory
and ebony keys, each labelled with its computer key (tracker layout), a music
desk whose sheet notates what you play, candles, and a small song book.

  Z S X D C V G B H N J M ,        lower octave  (white Z..M ,   black S D G H J)
  Q 2 W 3 E R 5 T 6 Y 7 U I 9 O 0 P  upper octave and a bit (white Q..P, black 2 3 5 6 7 9 0)
  Left / Right    shift the octave range        Space   sustain pedal (hold)
  Tab / Up/Down   free play <-> the song book   Enter   listen to the song first
  mouse           press keys (drag across them for a glissando)
  Esc / Bksp      stop playing (a seated farmer stays on the bench)

Song mode highlights the next key (and previews the next few); any octave of
the right note counts, there is no way to fail. Finishing a song earns a
little celebration (and, once a day per song, some energy -- PianoMixin).

Sound (``PianoSynth``): every note is baked once per MIDI number and cached --
two slightly detuned "strings" of a mellow wavetable (a slow two-stage decay,
the gentle beat between them is the piano shimmer) plus a bright hammer
wavetable that dies away fast, and a tiny felt thump. Loop tables hold a whole
number of cycles, so there is no per-sample ``math.sin``; each note starts at
its own point of the period, so a chord's peaks don't all line up. A note
rings 2.6 s (treble) .. 5.5 s (bass) and ends in a 0.35-0.5 s soft fade that
starts at -27..-31 dB (-23 in the deep bass), so held keys and the pedal die
away naturally (~25 MB for the whole piano, mono; a note bakes in ~10-27 ms).
The whole piano is baked once per session on a polite daemon thread as soon
as anyone walks into a house that has one (PianoMixin; ~3 s while the game
runs), the keys on screen first; opening the piano moves those to the front
again, and the LAN partner's machine does the same (``prewarm_listener`` --
around the very note it heard, when it walks in mid-song). A note needed
before that is baked on the spot as a short stand-in (~6 ms; the thread
stands aside meanwhile) and the full note follows from the thread.

Loudness: SDL adds the voices up and clamps, so ``_balance`` keeps the sum
under full scale at any volume -- notes struck together share one level
(``chord_total``) and what already rings counts at what it has decayed to.
Only when the sum would clip do rings drop (a re-struck string's first, then
the others a little) and the new chord give way. A 6-note chord at master 1.0
x sfx 1.0 peaks around -1.5 dBFS; a single note is untouched. The background
loop is ducked while you play (PianoMixin), and voices use their own mixer
channels above the game's 16; one voice per string (a re-strike under the
pedal replaces its old ring).

Pure UI + sound. The game side (energy, song rewards, LAN relays) lives in
``systems/piano_system.PianoMixin``; this screen calls back into it with
``_piano_note(screen, midi, on)``, ``_piano_song_done(screen, song_id)`` and
``_piano_closed(screen)``.
"""
import array
import math
import random
import threading
import time
import pygame

from .settings import SCREEN_W
from . import ui_kit as K

OPEN_T = 0.36           # fallboard slides open, seconds
CLOSE_T = 0.24
RELEASE_MS = 460        # a released key rings out this long
BASE_MIN, BASE_MAX = 2, 5
BASE_DEFAULT = 3        # octave of the lower row's C: C3, so Q is middle C
LOW_MIDI = 12 * (BASE_MIN + 1)          # C2  (36)
HIGH_MIDI = 12 * (BASE_MAX + 1) + 28    # E7 (100)
TRAIL_LIFE = 7.5        # free play: seconds a note drifts across the sheet

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_BLACK_PC = {1, 3, 6, 8, 10}

# tracker layout: computer key -> semitones above the lower row's C
_KEYMAP = [
    (pygame.K_z, 0), (pygame.K_s, 1), (pygame.K_x, 2), (pygame.K_d, 3), (pygame.K_c, 4),
    (pygame.K_v, 5), (pygame.K_g, 6), (pygame.K_b, 7), (pygame.K_h, 8), (pygame.K_n, 9),
    (pygame.K_j, 10), (pygame.K_m, 11), (pygame.K_COMMA, 12), (pygame.K_l, 13),
    (pygame.K_PERIOD, 14), (pygame.K_SEMICOLON, 15), (pygame.K_SLASH, 16),
    (pygame.K_q, 12), (pygame.K_2, 13), (pygame.K_w, 14), (pygame.K_3, 15), (pygame.K_e, 16),
    (pygame.K_r, 17), (pygame.K_5, 18), (pygame.K_t, 19), (pygame.K_6, 20), (pygame.K_y, 21),
    (pygame.K_7, 22), (pygame.K_u, 23), (pygame.K_i, 24), (pygame.K_9, 25), (pygame.K_o, 26),
    (pygame.K_0, 27), (pygame.K_p, 28),
]
KEY_OFFSET = dict(_KEYMAP)
# physical key positions too (SDL scancodes): with a Thai (or any non-Latin)
# layout active the number row / punctuation report non-Latin keycodes, but
# the scancode still says which key cap was pressed
_SCAN_NAMES = {"z": 0, "s": 1, "x": 2, "d": 3, "c": 4, "v": 5, "g": 6, "b": 7, "h": 8,
               "n": 9, "j": 10, "m": 11, "COMMA": 12, "l": 13, "PERIOD": 14,
               "SEMICOLON": 15, "SLASH": 16, "q": 12, "2": 13, "w": 14, "3": 15, "e": 16,
               "r": 17, "5": 18, "t": 19, "6": 20, "y": 21, "7": 22, "u": 23, "i": 24,
               "9": 25, "o": 26, "0": 27, "p": 28}
SCAN_OFFSET = {}
for _n, _o in _SCAN_NAMES.items():
    _sc = getattr(pygame, "KSCAN_" + _n.upper(), None)
    if _sc:
        SCAN_OFFSET[_sc] = _o
# the key that plays each shown offset (lower row first, then the upper row)
KEY_FOR_OFFSET = {}
for _k, _o in _KEYMAP:
    KEY_FOR_OFFSET.setdefault(_o, _k)
_LABEL = {0: "Z", 1: "S", 2: "X", 3: "D", 4: "C", 5: "V", 6: "G", 7: "B", 8: "H", 9: "N",
          10: "J", 11: "M", 12: "Q", 13: "2", 14: "W", 15: "3", 16: "E", 17: "R", 18: "5",
          19: "T", 20: "6", 21: "Y", 22: "7", 23: "U", 24: "I", 25: "9", 26: "O", 27: "0",
          28: "P"}
_WHITE_OFFS = [0, 2, 4, 5, 7, 9, 11, 12, 14, 16, 17, 19, 21, 23, 24, 26, 28]
_BLACK_OFFS = [1, 3, 6, 8, 10, 13, 15, 18, 20, 22, 25, 27]
SPAN = 28               # offsets 0..28 are on screen (17 white + 12 black keys)


# ------------------------------------------------------------------ music
def note_name(midi):
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def midi_of(name):
    """'C#4' -> 61."""
    pc = NOTE_NAMES.index(name[:-1])
    return 12 * (int(name[-1]) + 1) + pc


def clamp_midi(v):
    """A partner's note number: junk -> None, numbers clamped to the piano."""
    if isinstance(v, bool):
        return None
    if isinstance(v, float) and math.isfinite(v):
        v = int(v)
    if not isinstance(v, int):
        return None
    return max(LOW_MIDI, min(HIGH_MIDI, v))


# pastel rainbow by pitch class (key glow, floating notes)
_PC_COL = [(236, 96, 116), (238, 128, 92), (240, 160, 64), (226, 190, 56),
           (160, 196, 70), (92, 180, 100), (64, 176, 150), (64, 166, 204),
           (84, 136, 222), (112, 112, 226), (150, 100, 220), (206, 96, 186)]


def pitch_color(midi):
    return _PC_COL[midi % 12]


def _song(sid, tab, title, beat, text, stars=1, shelf="Nursery"):
    notes = []
    for tok in text.split():
        nm, _, b = tok.partition(":")
        notes.append((midi_of(nm), float(b) if b else 1.0))
    return {"id": sid, "tab": tab, "title": title, "beat": beat, "notes": notes,
            "stars": stars, "shelf": shelf}


# public-domain melodies (beats: 1 = quarter note)
SONGS = [
    _song("twinkle", "Twinkle Twinkle", "Twinkle Twinkle Little Star", 0.46,
          "C4 C4 G4 G4 A4 A4 G4:2 F4 F4 E4 E4 D4 D4 C4:2 G4 G4 F4 F4 E4 E4 D4:2 "
          "G4 G4 F4 F4 E4 E4 D4:2 C4 C4 G4 G4 A4 A4 G4:2 F4 F4 E4 E4 D4 D4 C4:2"),
    _song("ode", "Ode to Joy", "Ode to Joy", 0.42,
          "E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 E4:1.5 D4:0.5 D4:2 "
          "E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 D4:1.5 C4:0.5 C4:2 "
          "D4 D4 E4 C4 D4 E4:0.5 F4:0.5 E4 C4 D4 E4:0.5 F4:0.5 E4 D4 C4 D4 G3:2 "
          "E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 D4:1.5 C4:0.5 C4:2"),
    _song("mary", "Mary Had a Little Lamb", "Mary Had a Little Lamb", 0.42,
          "E4 D4 C4 D4 E4 E4 E4:2 D4 D4 D4:2 E4 G4 G4:2 "
          "E4 D4 C4 D4 E4 E4 E4 E4 D4 D4 E4 D4 C4:4"),
    _song("birthday", "Happy Birthday", "Happy Birthday to You", 0.46,
          "G3:0.75 G3:0.25 A3 G3 C4 B3:2 G3:0.75 G3:0.25 A3 G3 D4 C4:2 "
          "G3:0.75 G3:0.25 G4 E4 C4 B3 A3:2 F4:0.75 F4:0.25 E4 C4 D4 C4:3"),
    # ---- 2026-09-28 song book expansion (all public domain) ----
    _song("frere", "Frere Jacques", "Frere Jacques", 0.40,
          "C4 D4 E4 C4 C4 D4 E4 C4 E4 F4 G4:2 E4 F4 G4:2 "
          "G4:0.5 A4:0.5 G4:0.5 F4:0.5 E4 C4 G4:0.5 A4:0.5 G4:0.5 F4:0.5 E4 C4 "
          "C4 G3 C4:2 C4 G3 C4:2"),
    _song("rowboat", "Row Your Boat", "Row, Row, Row Your Boat", 0.34,
          "C4:1.5 C4:1.5 C4 D4:0.5 E4:1.5 E4 D4:0.5 E4 F4:0.5 G4:3 "
          "C5:0.5 C5:0.5 C5:0.5 G4:0.5 G4:0.5 G4:0.5 E4:0.5 E4:0.5 E4:0.5 "
          "C4:0.5 C4:0.5 C4:0.5 G4 F4:0.5 E4 D4:0.5 C4:3"),
    _song("london", "London Bridge", "London Bridge Is Falling Down", 0.40,
          "G4:1.5 A4:0.5 G4 F4 E4 F4 G4:2 D4 E4 F4:2 E4 F4 G4:2 "
          "G4:1.5 A4:0.5 G4 F4 E4 F4 G4:2 D4:2 G4:2 E4 C4:2"),
    _song("macdonald", "Old MacDonald", "Old MacDonald Had a Farm", 0.36,
          "C4 C4 C4 G3 A3 A3 G3:2 E4 E4 D4 D4 C4:3 G3 "
          "C4 C4 C4 G3 A3 A3 G3:2 E4 E4 D4 D4 C4:3"),
    _song("susanna", "Oh Susanna", "Oh! Susanna", 0.34,
          "C4:0.5 D4:0.5 E4 G4 G4:1.5 A4:0.5 G4 E4 C4:1.5 D4:0.5 E4 E4 D4 C4 D4:3 "
          "C4:0.5 D4:0.5 E4 G4 G4:1.5 A4:0.5 G4 E4 C4:1.5 D4:0.5 E4 E4 D4 D4 C4:3",
          stars=2, shelf="Folk"),
    _song("jingle", "Jingle Bells", "Jingle Bells", 0.30,
          "E4 E4 E4:2 E4 E4 E4:2 E4 G4 C4:1.5 D4:0.5 E4:4 "
          "F4 F4 F4:1.5 F4:0.5 F4 E4 E4 E4:0.5 E4:0.5 E4 D4 D4 E4 D4:2 G4:2 "
          "E4 E4 E4:2 E4 E4 E4:2 E4 G4 C4:1.5 D4:0.5 E4:4 "
          "F4 F4 F4:1.5 F4:0.5 F4 E4 E4 E4:0.5 E4:0.5 G4 G4 F4 D4 C4:4",
          stars=2, shelf="Holiday"),
    _song("merryxmas", "Merry Christmas", "We Wish You a Merry Christmas", 0.34,
          "G3 C4 C4:0.5 D4:0.5 C4:0.5 B3:0.5 A3 A3 A3 D4 D4:0.5 E4:0.5 D4:0.5 C4:0.5 "
          "B3 G3 G3 E4 E4:0.5 F4:0.5 E4:0.5 D4:0.5 C4 A3 G3:0.5 G3:0.5 A3 D4 B3 C4:2",
          stars=2, shelf="Holiday"),
    _song("auldlang", "Auld Lang Syne", "Auld Lang Syne", 0.44,
          "G3 C4:1.5 C4:0.5 C4 E4 D4:1.5 C4:0.5 D4 E4 C4:1.5 C4:0.5 E4 G4 A4:3 "
          "A4 G4:1.5 E4:0.5 E4 C4 D4:1.5 C4:0.5 D4 E4 C4:1.5 A3:0.5 A3 G3 C4:3",
          stars=2, shelf="Holiday"),
    _song("lullaby", "Brahms' Lullaby", "Brahms' Lullaby", 0.40,
          "E4:0.5 E4:0.5 G4:2 E4:0.5 E4:0.5 G4:2 E4:0.5 G4:0.5 C5 B4:1.5 A4:0.5 A4 G4 "
          "D4:0.5 E4:0.5 F4 D4 D4:0.5 E4:0.5 F4:2 D4:0.5 F4:0.5 B4:0.5 A4:0.5 G4 B4 C5:3 "
          "C4:0.5 C4:0.5 C5:2 A4:0.5 F4:0.5 G4:2 E4:0.5 C4:0.5 F4 G4 A4 G4:2 "
          "C4:0.5 C4:0.5 C5:2 A4:0.5 F4:0.5 G4:2 E4:0.5 C4:0.5 F4 E4 D4 C4:3",
          stars=2, shelf="Classics"),
    _song("amazing", "Amazing Grace", "Amazing Grace", 0.40,
          "G3 C4:2 E4:0.5 C4:0.5 E4:2 D4 C4:2 A3 G3:2 G3 C4:2 E4:0.5 C4:0.5 E4:2 D4 G4:3 "
          "E4:0.5 G4:0.5 G4:2 E4:0.5 G4:0.5 E4:2 D4 C4:2 A3 G3:2 G3 "
          "C4:2 E4:0.5 C4:0.5 E4:2 D4 C4:3",
          stars=2, shelf="Folk"),
    _song("aura", "Aura Lee", "Aura Lee (the Love Me Tender tune)", 0.46,
          "G3 C4 B3 C4 D4 A3 D4:2 C4 B3 A3 B3 C4:4 "
          "G3 C4 B3 C4 D4 A3 D4:2 C4 B3 A3 B3 C4:4 "
          "E4 E4 E4 E4 E4 E4 E4:2 E4 D4 C4 D4 E4:4 "
          "E4 E4 F4 E4 D4 A3 D4:2 C4 B3 E4 D4 C4:4",
          stars=2, shelf="Love songs"),
    _song("bridal", "Bridal Chorus", "Bridal Chorus (Here Comes the Bride)", 0.44,
          "G3 C4:1.5 C4:0.5 C4:2 G3 D4:1.5 B3:0.5 C4:2 "
          "G3 C4:1.5 F4:0.5 F4:1.5 E4:0.5 D4:1.5 C4:0.5 B3:1.5 C4:0.5 D4:2 "
          "G3 C4:1.5 C4:0.5 C4:2 G3 D4:1.5 B3:0.5 C4:2 "
          "G3 C4:1.5 E4:0.5 G4:1.5 E4:0.5 C4:1.5 G3:0.5 A3:1.5 B3:0.5 C4:4",
          stars=2, shelf="Love songs"),
    _song("greensleeves", "Greensleeves", "Greensleeves", 0.30,
          "A3 C4:2 D4 E4:1.5 F4:0.5 E4 D4:2 B3 G3:1.5 A3:0.5 B3 "
          "C4:2 A3 A3:1.5 G#3:0.5 A3 B3:2 G#3 E3:2 A3 "
          "C4:2 D4 E4:1.5 F4:0.5 E4 D4:2 B3 G3:1.5 A3:0.5 B3 "
          "C4:1.5 B3:0.5 A3 G#3:1.5 F#3:0.5 G#3 A3:3",
          stars=3, shelf="Classics"),
    _song("minuet", "Minuet in G", "Minuet in G (Petzold)", 0.34,
          "D4 G3:0.5 A3:0.5 B3:0.5 C4:0.5 D4 G3 G3 E4 C4:0.5 D4:0.5 E4:0.5 F#4:0.5 G4 G3 G3 "
          "C4 D4:0.5 C4:0.5 B3:0.5 A3:0.5 B3 C4:0.5 B3:0.5 A3:0.5 G3:0.5 "
          "F#3 G3:0.5 A3:0.5 B3:0.5 G3:0.5 A3:3 "
          "D4 G3:0.5 A3:0.5 B3:0.5 C4:0.5 D4 G3 G3 E4 C4:0.5 D4:0.5 E4:0.5 F#4:0.5 G4 G3 G3 "
          "C4 D4:0.5 C4:0.5 B3:0.5 A3:0.5 B3 C4:0.5 B3:0.5 A3:0.5 G3:0.5 "
          "A3 B3:0.5 A3:0.5 G3:0.5 F#3:0.5 G3:3",
          stars=3, shelf="Classics"),
    _song("elise", "Fur Elise", "Fur Elise (Beethoven)", 0.30,
          "E5:0.5 D#5:0.5 E5:0.5 D#5:0.5 E5:0.5 B4:0.5 D5:0.5 C5:0.5 A4:1.5 "
          "C4:0.5 E4:0.5 A4:0.5 B4:1.5 E4:0.5 G#4:0.5 B4:0.5 C5:1.5 "
          "E4:0.5 E5:0.5 D#5:0.5 E5:0.5 D#5:0.5 E5:0.5 B4:0.5 D5:0.5 C5:0.5 A4:1.5 "
          "C4:0.5 E4:0.5 A4:0.5 B4:1.5 E4:0.5 C5:0.5 B4:0.5 A4:3",
          stars=3, shelf="Classics"),
    _song("canon", "Canon in D", "Canon in D (Pachelbel)", 0.40,
          "F#4:2 E4:2 D4:2 C#4:2 B3:2 A3:2 B3:2 C#4:2 "
          "D4:2 C#4:2 B3:2 A3:2 G3:2 F#3:2 G3:2 E3:2 "
          "D4:0.5 F#4:0.5 A4:0.5 G4:0.5 F#4:0.5 D4:0.5 F#4:0.5 E4:0.5 "
          "D4:0.5 B3:0.5 D4:0.5 A4:0.5 G4:0.5 B4:0.5 A4:0.5 G4:0.5 "
          "F#4:2 E4:2 D4:4",
          stars=3, shelf="Love songs"),
]
for _s0 in SONGS[:4]:                    # the original four: first steps
    _s0["stars"] = 2 if _s0["id"] == "birthday" else 1
    _s0["shelf"] = "Nursery" if _s0["id"] != "ode" else "Classics"
SHELVES = ["Nursery", "Folk", "Holiday", "Love songs", "Classics"]
SONG_IDS = {s["id"]: s for s in SONGS}


def song_title(sid):
    s = SONG_IDS.get(sid)
    return s["title"] if s else "a tune"


_CHORDS = [((0, 4, 7), " major"), ((0, 3, 7), " minor"), ((0, 3, 6), " dim"),
           ((0, 4, 8), " aug"), ((0, 2, 7), "sus2"), ((0, 5, 7), "sus4"),
           ((0, 4, 7, 10), "7"), ((0, 4, 7, 11), "maj7"), ((0, 3, 7, 10), "m7"),
           ((0, 3, 6, 10), "m7b5"), ((0, 3, 6, 9), "dim7"), ((0, 4, 7, 9), "6"),
           ((0, 3, 7, 9), "m6"), ((0, 2, 4, 7), "add9"), ((0, 7), "5 (power chord)")]
_INTERVALS = {0: "octave", 1: "minor 2nd", 2: "major 2nd", 3: "minor 3rd",
              4: "major 3rd", 5: "perfect 4th", 6: "tritone", 7: "perfect 5th",
              8: "minor 6th", 9: "major 6th", 10: "minor 7th", 11: "major 7th"}


def chord_name(midis):
    """'C major', 'Am7', 'G/B', 'perfect 5th' ... for the keys held together."""
    ms = sorted(set(midis))
    if len(ms) < 2:
        return ""
    pcs = sorted({m % 12 for m in ms})
    if len(pcs) == 1:
        return "octave"
    if len(ms) == 2:
        return _INTERVALS[(ms[1] - ms[0]) % 12]
    bass = ms[0] % 12
    found = None
    for root in pcs:
        rel = tuple(sorted((p - root) % 12 for p in pcs))
        for tpl, suf in _CHORDS:
            if rel == tpl:
                name = NOTE_NAMES[root] + suf
                if root != bass:
                    name += "/" + NOTE_NAMES[bass]
                if found is None or root == bass:
                    found = name
    return found or ""


def held_label(midis):
    """What the music desk says about the keys held: ("chord", "Am7") /
    ("chord", "perfect 5th"), else ("note", "note C7") / ("notes", "notes
    C4  D6") -- a lone note is never written like a chord symbol (C7 or C6
    would read as chords) -- or ("", "") for nothing held."""
    name = chord_name(midis)
    if name:
        return "chord", name
    ms = sorted(set(midis))
    if not ms:
        return "", ""
    if len(ms) == 1:
        return "note", "note " + note_name(ms[0])
    return "notes", "notes " + "  ".join(note_name(m) for m in ms[:8])


# ------------------------------------------------------------------ synth
_TAB_N = 4096           # one period of a timbre, high resolution
_TAB_M = _TAB_N - 1
_WAVES = {}
_HARM = {
    # partial amplitudes; brighter registers keep fewer (see _wave's cap)
    "bass": [0.62, 0.86, 0.62, 0.44, 0.33, 0.24, 0.16, 0.11, 0.08, 0.05],
    "body": [1.0, 0.52, 0.27, 0.15, 0.09, 0.055, 0.035, 0.02],
    "treble": [1.0, 0.34, 0.11, 0.045, 0.02],
    # the hammer: bright (the body carries the fundamental), ~1/n up high, with
    # the notch where the hammer strikes the string (1/8 of its length)
    "hammer": [0.25, 0.6] + [0.95 / n ** 0.7 * (0.2 if n % 8 == 0 else 0.6 if n % 8 in (1, 7)
                                               else 1.0) for n in range(3, 17)],
}


def _wave(kind, nmax, nap=None):
    """One normalised period (``_TAB_N`` samples) of ``kind`` with at most
    ``nmax`` partials (cached; keeps every partial under Nyquist). ``nap`` is
    called between partials (the prewarm thread's manners)."""
    amps = _HARM[kind][:max(1, nmax)]
    key = (kind, len(amps))
    w = _WAVES.get(key)
    if w is not None:
        return w
    tw = 2 * math.pi / _TAB_N
    sin_t = _WAVES.get("sin")
    if sin_t is None:
        sin_t = _WAVES["sin"] = [math.sin(tw * i) for i in range(_TAB_N)]
    w = [0.0] * _TAB_N
    for n, a in enumerate(amps, 1):
        off = (n * 409) & _TAB_M                 # fixed phase spread: a rounder peak
        w = [x + a * sin_t[(n * i + off) & _TAB_M] for i, x in enumerate(w)]
        if nap:
            nap()
    pk = max(1e-6, max(abs(v) for v in w))
    w = [v / pk for v in w]
    _WAVES[key] = w
    return w


def _loop(w, cyc, length, amp, n, ph=0):
    """``n`` samples of ``w`` looped: ``length`` samples hold exactly ``cyc``
    periods, so the loop point is seamless and the pitch is cyc*sr/length.
    ``ph``: where in the period the note starts (table units)."""
    step = cyc * _TAB_N
    tab = [w[(i * step // length + ph) & _TAB_M] * amp for i in range(length)]
    return (tab * (n // length + 1))[:n]


# -- how long a note rings, and how loud it may be
PEAK = 11500            # one note's nominal peak (int16) at full velocity and volume
TAIL_MIN, TAIL_MAX = 2.6, 5.5   # seconds a note rings out (treble .. bass)


def _decay_k(midi):
    """Low notes ring longer: the time scale of a note's decay (C4 = 1)."""
    return min(1.6, max(0.42, 2 ** (-(midi - 60) / 24.0)))


def note_secs(midi):
    """How long the baked note lasts (its tail is ~-28 dB or quieter by the
    time the last, gentle fade starts)."""
    return min(TAIL_MAX, max(TAIL_MIN, 5.0 * _decay_k(midi) + 0.5))


def note_fade(midi):
    """The final fade (seconds): long enough to sound like the dampers
    settling, never a cut."""
    return 0.3 + 0.12 * _decay_k(midi)


def note_env(midi, age):
    """Roughly how loud ``midi`` still is ``age`` seconds after the strike
    (1 at the strike; body and hammer as ``render`` bakes them)."""
    k = _decay_k(midi)
    age = max(0.0, age)
    body = 0.6 * math.exp(-age / (0.5 * k)) + 0.4 * math.exp(-age / (2.4 * k))
    return 0.55 * body + 0.45 * math.exp(-age / max(0.04, 0.11 * k))


# -- the mix never clips: SDL adds the voices up and simply clamps the sum
CHORD_WIN = 0.05        # strikes this close together are one chord (s)
HEADROOM = 2.9          # single-note peaks the mix holds at full volume, with a margin
DUCK_MIN = 0.4          # a big new chord may hush what is already ringing to this ...
FLOOR = 0.35            # ... and itself down to this much, no further
RESTRIKE = 0.35         # a re-struck string's old ring may drop to this first


def chord_total(n):
    """How much louder ``n`` notes struck together are than one (in
    single notes): fingers ease off a little in a big chord."""
    return n / (1.0 + 0.06 * max(0, n - 3))


def _coh(n):
    """How much of their peaks ``n`` notes struck on the same sample can
    line up (measured, with the per-note start phases of ``render``)."""
    return 1.0 if n <= 2 else max(0.85, 1.0 - 0.04 * (n - 2))


NAP_IDLE, NAP_BUSY = 0.002, 0.0003   # prewarm work between GIL breaks (s): game idle / busy

QUICK_SECS = 1.2        # a note needed mid-frame before the prewarm got to it
_CACHES = {}            # (sample rate, channels) -> {midi: Sound}
_QUICKS = {}            # (sample rate, channels) -> midis cached as a QUICK_SECS stand-in


def _cid(ch):
    """A channel's mixer index (pygame hands out a new Channel object per
    ``Channel(i)`` call, so identity can't tell two of them apart)."""
    return getattr(ch, "id", id(ch))


class PianoSynth:
    """Baked, cached piano notes + a small voice pool on spare mixer channels."""
    VOICES = 12

    def __init__(self, audio):
        self.audio = audio
        init = pygame.mixer.get_init() if pygame.mixer.get_init() else None
        self.enabled = bool(getattr(audio, "enabled", False) and init)
        self.sr, _fmt, self.nch = init if init else (44100, -16, 1)
        self.cache = _CACHES.setdefault((self.sr, self.nch), {})     # midi -> Sound
        self.quick = _QUICKS.setdefault((self.sr, self.nch), set())  # short stand-ins
        # voices + ringing never share a channel: a channel that starts a new
        # note drops whatever pointed at it before (see _forget)
        self.voices = {}                # key -> (channel, sound)
        self.ringing = []               # released under the pedal: (channel, sound)
        # every voice still sounding at a level we set: channel id -> [channel,
        # sound, midi, struck at, velocity, gain, None | (released at, fade s)]
        self._lv = {}
        self._grp, self._grp_t = [], -1.0    # the chord being struck right now
        self._chans = []
        self._base = None
        self._started = {}
        self._queue = []
        self._busy = False
        self._fg = 0                    # >0 while the game thread bakes a note itself
        self._nap_t, self._slice = 0.0, NAP_BUSY  # the prewarm thread's manners (_nap)
        self._lock = threading.Lock()
        self._ramp = [i / 256.0 for i in range(256)]

    # ---- baking ----
    def render(self, midi, nice=False, secs=None):
        """Mono int16 samples for one note (no pygame calls: thread-safe).
        ``nice``: hand the GIL back every few blocks (the prewarm thread) so
        the game's frames never wait on a whole note. ``secs``: a shorter
        note than ``note_secs`` (the quick stand-in)."""
        sr = self.sr
        f = 440.0 * 2 ** ((midi - 69) / 12.0)
        k = _decay_k(midi)                       # low notes ring longer
        n = int(sr * min(secs or 99.0, note_secs(midi)))
        cyc = max(1, int(round(3600 * f / sr)))
        l1 = max(8, int(round(cyc * sr / f)))
        l2 = max(8, int(round(cyc * sr / (f + 0.12 + f * 0.0012))))  # 2nd string, ~3 cents
        if l2 == l1:
            l2 -= 1
        nap = self._nap if nice else None
        reg = "bass" if f < 180 else "body" if f < 700 else "treble"
        body = _wave(reg, int(15000 / f), nap)
        ham = _wave("hammer", int(15000 / f), nap)
        # each note starts at its own point of the period (golden-ratio
        # spread): a chord struck on one sample no longer lines all its
        # peaks up at the attack
        ph = int((midi * 0.6180339887) % 1.0 * _TAB_N)
        s1 = _loop(body, cyc, l1, 1.0, n, ph)
        s2 = _loop(body, cyc, l2, 0.26, n, ph)
        hm = _loop(ham, cyc, l1, 1.0, n, ph)
        peak = PEAK * (1.0 - max(0, midi - 76) * 0.012)
        ga, gh = peak * 0.55 / 1.26, peak * 0.45
        ta, tb, ts = 0.5 * k, 2.4 * k, max(0.04, 0.11 * k)
        fade = max(1, min(n // 2, int(note_fade(midi) * sr)))
        ex, cos, pi = math.exp, math.cos, math.pi

        def g_body(i):
            t = i / sr
            g = ga * (0.6 * ex(-t / ta) + 0.4 * ex(-t / tb))
            if i > n - fade:                     # the dampers settle: a soft S-curve
                g *= 0.5 + 0.5 * cos(pi * (i - (n - fade)) / fade)
            return g

        def g_ham(i):
            return gh * ex(-i / sr / ts)

        cut = min(n, int(sr * ts * 7))           # the hammer layer is gone by then
        out = []
        bs, ramp = 256, self._ramp
        for s in range(0, n, bs):
            if nap and not s & 511:
                nap()
            e = min(n, s + bs)
            g0 = g_body(s)
            dg = g_body(e) - g0
            if s < cut:
                h0 = g_ham(s)
                dh = g_ham(e) - h0
                out += [int((a + b) * (g0 + dg * r) + c * (h0 + dh * r))
                        for a, b, c, r in zip(s1[s:e], s2[s:e], hm[s:e], ramp)]
            else:
                out += [int((a + b) * (g0 + dg * r)) for a, b, r in zip(s1[s:e], s2[s:e], ramp)]
        # felt thump + a click-free attack
        rnd = random.Random(midi * 7 + 1)
        lp, a = 0.0, min(0.9, 0.12 + f / 3000.0)
        amp, tau = peak * 0.16, 0.004 * sr
        for i in range(min(n, int(0.02 * sr))):
            lp += (rnd.uniform(-1.0, 1.0) - lp) * a
            out[i] += int(lp * amp * ex(-i / tau))
        att = max(1, int(0.0015 * sr))
        for i in range(min(n, att)):
            out[i] = out[i] * i // att
        return out

    def _nap(self):
        """Prewarm thread: every little slice of work, really let go of the
        GIL for a moment (and stand aside completely while the game thread
        bakes a note of its own). The slice adapts: when the GIL comes
        straight back the game is idle between frames, so take bigger bites;
        when we had to wait for it the game is busy drawing, so keep them
        tiny (its frames must never wait on us)."""
        now = time.perf_counter()
        if now - self._nap_t < self._slice and not self._fg:
            return
        time.sleep(0.0005)
        while self._fg:
            time.sleep(0.001)
        t = time.perf_counter()
        self._slice = NAP_IDLE if t - now < 0.0025 else NAP_BUSY
        self._nap_t = t

    def _to_sound(self, mono, nap=None):
        if nap:                                  # in slices: never hold the GIL long
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
        return pygame.mixer.Sound(buffer=arr.tobytes())

    def baked(self, midi):
        """Is the full note for ``midi`` ready (not just a quick stand-in)?"""
        return midi in self.cache and midi not in self.quick

    def sound(self, midi, nice=False):
        """The cached Sound for ``midi``. Not baked yet: the prewarm thread
        (``nice``) bakes the full note; the game thread, mid-frame, bakes a
        short stand-in (a few ms, not ~25 for a ringing bass note) and puts
        the full one at the front of the prewarm queue."""
        s = self.cache.get(midi)
        if s is None and self.enabled:
            if not nice:
                self._fg += 1
            try:
                if nice:
                    s = self._to_sound(self.render(midi, True), self._nap)
                else:
                    s = self._to_sound(self.render(midi, secs=QUICK_SECS))
            except Exception:
                s = None
            finally:
                if not nice:
                    self._fg -= 1
            if s is not None:
                self.cache[midi] = s
                if not nice:
                    self.quick.add(midi)
                    self.prewarm([midi])
        return s

    def _bake_full(self, midi):
        """Prewarm thread: the full note (replacing a quick stand-in)."""
        try:
            s = self._to_sound(self.render(midi, True), self._nap)
        except Exception:
            return
        self.cache[midi] = s
        self.quick.discard(midi)

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
                time.sleep(0.002)                # let the game thread breathe
        except Exception:
            with self._lock:
                self._busy = False

    # ---- voices ----
    def _pool(self):
        """Our own channels ABOVE the game's 16, so a chord never steals the
        music loop or the weather bed (find_channel(True) would)."""
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

    def _channel(self):
        chans = self._pool()
        if not chans:
            return None
        for c in chans:
            if not c.get_busy():
                return c
        return min(chans, key=lambda c: self._started.get(_cid(c), 0.0))  # oldest voice

    def volume(self):
        a = getattr(self.audio, "_real", None) or self.audio
        return getattr(a, "master", 0.8) * getattr(a, "sfx_vol", 0.9)

    def note_on(self, key, midi, vel=1.0):
        """Strike ``midi``; ``key`` names the voice for its note_off. How loud
        it really sounds is up to ``_balance`` (chords share the headroom)."""
        if not self.enabled:
            return False
        snd = self.sound(midi)
        if snd is None:
            return False
        # a re-strike: the hammer stops the string's old ring -- the one still
        # held under this key, and the one the pedal holds (one voice per string)
        again, keep = [], []
        old = self.voices.pop(key, None)
        if old is not None:
            again.append(old)
        for v in self.ringing:
            if v[1] is snd:
                again.append(v)
            elif self._sounding(v):
                keep.append(v)
        self.ringing = keep
        ch = self._channel()
        if ch is None:
            for v in again:
                self._damp(v, 70)
            return False
        self._forget(ch)
        again = [v for v in again if _cid(v[0]) != _cid(ch)]     # (stolen for the new one)
        now = time.monotonic()
        ent = [ch, snd, midi, now, max(0.0, min(1.0, float(vel))), 1.0, None]
        try:
            self._balance(ent, now, again)      # the levels first: no loud blip ...
            for v in again:
                self._damp(v, 70)               # ... the old rings fade from theirs
            ch.play(snd)
        except Exception:
            self._chans = []
            return False
        self._lv[_cid(ch)] = ent
        self._started[_cid(ch)] = now
        self.voices[key] = (ch, snd)
        return True

    def _balance(self, new, now, again=()):
        """Set the level of the note being struck -- and of the chord it
        joins -- so the mix never clips (SDL just clamps the sum). Notes
        struck within ``CHORD_WIN`` are one chord and share one level; what
        is still ringing from before counts at what it has decayed to. Only
        when that would clip: the rings of the strings struck ``again`` drop
        first (they are about to fade anyway), then the other rings a little,
        then the new chord itself. (A volume step is a tiny tick under the
        new hammer; a clamped mix is an ugly crackle.)"""
        v = self.volume()
        live = {}
        for c, e in self._lv.items():
            if not self._sounding((e[0], e[1])):
                continue
            if e[6] is not None and now - e[6][0] >= e[6][1]:
                continue                         # faded out (the channel may lag)
            live[c] = e
        self._lv = live
        hush = []
        for q in again:
            e = live.get(_cid(q[0]))
            if e is not None and e[1] is q[1] and e[6] is None:
                hush.append(e)
        if now - self._grp_t > CHORD_WIN:
            self._grp, self._grp_t = [], now
        grp = [live[c] for c in self._grp
               if c in live and live[c][6] is None and not any(live[c] is h for h in hush)]
        chord = grp + [new]
        n = len(chord)

        def level(e):
            return e[4] * e[5] * note_env(e[2], now - e[3])
        old, load = [], 0.0
        for e in live.values():
            if any(e is q for q in chord):
                continue
            lvl = level(e)
            if e[6] is not None:                 # released: fading away linearly
                lvl *= max(0.0, 1.0 - (now - e[6][0]) / e[6][1])
            elif not any(e is h for h in hush):
                old.append(e)
            load += lvl
        room = HEADROOM / max(v, 1e-3)           # in single notes at this volume
        c = _coh(n)
        want = chord_total(n)
        for group, floor in ((hush, RESTRIKE), (old, DUCK_MIN)):
            over = c * want + 0.8 * load - room  # old rings: partly out of phase
            if over <= 0 or not group:
                continue
            sub = sum(level(e) for e in group)
            d = max(floor, 1.0 - over / (0.8 * sub)) if sub > 0 else 1.0
            if d < 1.0:
                for e in group:
                    e[5] *= d
                    self._set_vol(e, v)
                load -= sub * (1.0 - d)
        over = c * want + 0.8 * load - room
        if over > 0:
            want = max(want * FLOOR, (room - 0.8 * load) / c)
        g = want / n
        for e in chord:
            e[5] = g
            self._set_vol(e, v)
        self._grp = [_cid(e[0]) for e in chord]

    @staticmethod
    def _set_vol(e, v):
        try:
            e[0].set_volume(max(0.0, min(1.0, e[4] * e[5] * v)))
        except Exception:
            pass

    def note_off(self, key, ms=RELEASE_MS, pedal=False):
        v = self.voices.pop(key, None)
        if v is None:
            return
        if pedal:
            self.ringing.append(v)               # the dampers stay up
        else:
            self._damp(v, ms)

    def pedal_up(self, ms=RELEASE_MS):
        for v in self.ringing:
            self._damp(v, ms)
        self.ringing = []

    def _forget(self, ch):
        """``ch`` is about to play a new note: drop every voice still pointing
        at it (that note ended, or was the oldest and got stolen), so a later
        note_off / pedal-up can't damp the NEW note by mistake."""
        c = _cid(ch)
        self.ringing = [v for v in self.ringing if _cid(v[0]) != c]
        for k in [k for k, v in self.voices.items() if _cid(v[0]) == c]:
            del self.voices[k]
        self._lv.pop(c, None)

    @staticmethod
    def _sounding(v):
        """Is voice ``v`` = (channel, sound) still playing its own note?"""
        ch, snd = v
        try:
            return bool(ch.get_busy()) and ch.get_sound() is snd
        except Exception:
            return False

    def _damp(self, v, ms):
        """Let voice ``v`` die away over ``ms`` (SDL's fade starts from the
        channel's level and ignores volume changes after that)."""
        if not self._sounding(v):
            return
        try:
            v[0].fadeout(max(1, int(ms)))
        except Exception:
            return
        e = self._lv.get(_cid(v[0]))
        if e is not None and e[1] is v[1] and e[6] is None:
            e[6] = (time.monotonic(), max(1, int(ms)) / 1000.0)

    def active(self):
        """Notes really sounding right now (held or ringing under the pedal;
        rings that already died away don't count)."""
        self.ringing = [v for v in self.ringing if self._sounding(v)]
        return sum(1 for v in self.voices.values() if self._sounding(v)) + len(self.ringing)


def synth(audio):
    """The PianoSynth that lives on ``audio`` (baked notes are shared per
    mixer format, so they survive closing the piano or a new Game)."""
    real = getattr(audio, "_real", None) or audio        # an area-context sink
    s = getattr(real, "_piano_synth", None)
    if s is None:
        s = PianoSynth(real)
        try:
            real._piano_synth = s
        except Exception:
            pass
    return s


ROLL_CHORD = (60, 67, 72, 76, 79, 84)   # the piano's answer to a finished song


def warm_order(base=BASE_DEFAULT, first=(), full=True):
    """The notes worth baking ahead for a keyboard whose lower row starts at
    octave ``base``: ``first``, then the keys on screen from the middle
    outwards, then the celebration chord (two of its notes sit above them)
    and -- ``full`` -- the rest of the piano, nearest first."""
    lo = 12 * (base + 1)
    mid = lo + 14
    order = list(first) + sorted(range(lo, lo + SPAN + 1), key=lambda m: abs(m - mid))
    order += ROLL_CHORD
    if full:
        order += sorted(range(LOW_MIDI, HIGH_MIDI + 1), key=lambda m: abs(m - mid))
    return list(dict.fromkeys(m for m in order if LOW_MIDI <= m <= HIGH_MIDI))


def warm_around(midi):
    """The whole piano, nearest ``midi`` first (its own octave straight away)."""
    return sorted(range(LOW_MIDI, HIGH_MIDI + 1), key=lambda m: (abs(m - midi), m))


def prewarm_all(audio):
    """Bake every key once per session, on the synth's daemon thread (the
    keys on screen first). Called on entering the house, so the piano is
    ready long before anyone sits down."""
    synth(audio).prewarm(warm_order())


def prewarm_listener(audio, around=None):
    """The partner sat down at their piano (``around`` None) or played a note
    we haven't baked yet (``around`` = that note): bake the keys HERE as
    well, on the synth's daemon thread, so their music doesn't stall our
    frames."""
    synth(audio).prewarm(warm_order() if around is None else warm_around(around))


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
        pygame.draw.line(surf, col, (sx, head.centery), (sx, top - grow),
                         max(2, size // 4) + grow * 2)
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


_CLEF = {}


def _clef(height):
    """A treble clef: Segoe UI Symbol's when the font has it, else drawn."""
    s = _CLEF.get(height)
    if s is not None:
        return s
    s = None
    try:
        f = pygame.font.SysFont("segoeuisymbol,seguisym,notomusic,dejavusans", height)
        m = f.metrics("\U0001D11E")
        if m and m[0] is not None:
            s = f.render("\U0001D11E", True, K.INK)
    except Exception:
        s = None
    if s is None:                                   # simple drawn fallback
        w = height // 2
        s = pygame.Surface((w, height), pygame.SRCALPHA)
        cx = w // 2
        pygame.draw.line(s, K.INK, (cx, 2), (cx - 2, height - 6), 3)
        pygame.draw.ellipse(s, K.INK, (2, height // 2 - 2, w - 4, height // 3), 3)
        pygame.draw.arc(s, K.INK, (cx - 2, 0, w // 2, height // 3), -1.2, 3.2, 3)
        pygame.draw.circle(s, K.INK, (cx - 5, height - 6), 4)
    _CLEF[height] = s
    return s


# ------------------------------------------------------------------ layout
PANEL = pygame.Rect(40, 116, 1200, 568)
CASE = pygame.Rect(92, 192, 1096, 420)          # the upright's front
SHEET = pygame.Rect(286, 210, 708, 130)         # the music on the desk
WK, WH = 60, 196                                # white keys
BK, BH = 36, 122                                # black keys
KB_X = SCREEN_W // 2 - len(_WHITE_OFFS) * WK // 2
KB_Y = 396
NAME = pygame.Rect(CASE.x + 18, 354, CASE.w - 36, 32)     # the nameboard strip
LS = 9                                          # staff line spacing
STAFF_TOP = SHEET.y + 40                        # F5 line (E4 = STAFF_TOP + 4 * LS)
STAFF_X0 = SHEET.x + 62
PLAY_X = STAFF_X0 + 118                         # song mode: where the next note sits
NOTE_DX = 50
_NUDGE = {1: -5, 3: 5, 6: -6, 8: 0, 10: 6}      # black keys sit off-centre, like real ones
_DIA = [0, 0, 1, 1, 2, 3, 3, 4, 4, 5, 5, 6]     # pitch class -> staff step (sharps share)


def _key_rects():
    out = {}
    for i, o in enumerate(_WHITE_OFFS):
        out[o] = pygame.Rect(KB_X + i * WK, KB_Y, WK, WH)
    for o in _BLACK_OFFS:
        i = _WHITE_OFFS.index(o - 1)
        cx = KB_X + (i + 1) * WK + _NUDGE[o % 12]
        out[o] = pygame.Rect(cx - BK // 2, KB_Y, BK, BH)
    return out


KEY_RECTS = _key_rects()


def _tab_rects():
    """Top bar: two tabs (Free play | Song book) on the left, the song
    picker (< title >) in the middle and the 'All songs' button right."""
    labels = ["Free play", "Song book"]
    out = [pygame.Rect(96, 156, 128, 28), pygame.Rect(232, 156, 128, 28)]
    return labels, out


PICK_L = pygame.Rect(400, 156, 30, 28)          # previous song
PICK = pygame.Rect(436, 154, 408, 32)           # the song on the stand
PICK_R = pygame.Rect(850, 156, 30, 28)          # next song
ALL_BTN = pygame.Rect(1004, 156, 180, 28)       # the song list
BOOK = pygame.Rect(128, 196, 1024, 420)         # the open song list
BOOK_COLS = 3


OCT_L = pygame.Rect(NAME.right - 196, NAME.y + 5, 26, 22)
OCT_R = pygame.Rect(NAME.right - 34, NAME.y + 5, 26, 22)


# ------------------------------------------------------------------ the screen
class PianoScreen:
    """The open piano: keyboard, music desk and song book."""

    def __init__(self, game, pidx, piano, seated=False, client=False):
        self.g = game
        self.pidx = pidx
        self._pc = piano
        self.gx, self.gy = piano.gx, piano.gy
        self.seated = seated
        self.client = client            # LAN client: notes are relayed to the host
        # LAN client: the HOST seats P2 on the bench; the snapshot brings the
        # seat here a moment later. ``seated`` was our guess till then.
        self._seat_wait = 2.0 if client and seated else 0.0
        self.syn = synth(game.audio)
        self.base = BASE_DEFAULT
        self.mode = 0                   # 0 free play, 1.. = SONGS[mode - 1]
        self.last_song = 1              # the page the song book opens on
        self.book = None                # open song list: {"sel": index, "t": age}
        self.src = {}                   # input source -> the midi it holds down
        self._keys = set()              # computer keys down (to ignore key repeat)
        self.held = {}                  # midi -> how many sources hold it
        self.glow = {}                  # midi -> key light 0..1 (fades after release)
        self.pedal = False
        self.sus = set()                # released while the pedal was down
        self.trail = []                 # free play: [midi, age] drifting on the sheet
        self.fx = []                    # screen particles [x, y, vx, vy, life, max, surf]
        self.song_i = 0
        self.scroll = 0.0
        self.done_t = 0.0
        self.reward = ""
        self.demo = None                # listen: {"i", "t", "off", "m"}
        self.roll = []                  # celebration flourish [t, midi, stage]
        self.miss_t = 0.0
        self.oct_pop = 0.0
        self.phase, self.t, self.clock = "opening", 0.0, 0.0
        self._tabs = _tab_rects()
        self._listen_rect = None
        self.msg = ""
        self._set_msg()
        self._prewarm()

    # ---- data ----
    @property
    def p(self):
        return self.g.players[self.pidx]

    @property
    def piece(self):
        """The live piano piece (a LAN world resync replaces Placed objects)."""
        home = self.g.world.home_furniture
        if any(q is self._pc for q in home):
            return self._pc
        for q in home:
            if q.kind == "piano" and q.gx == self.gx and q.gy == self.gy:
                self._pc = q
                return q
        return self._pc

    @property
    def low(self):
        return 12 * (self.base + 1)

    @property
    def song(self):
        return SONGS[self.mode - 1] if self.mode else None

    def target(self):
        """The midi the song wants next (None in free play / when done)."""
        s = self.song
        if s is None or self.done_t > 0 or self.demo or self.song_i >= len(s["notes"]):
            return None
        return s["notes"][self.song_i][0]

    def shown(self, midi):
        """``midi`` moved by whole octaves onto the visible keys (song hints)."""
        lo = self.low
        while midi < lo:
            midi += 12
        while midi > lo + SPAN:
            midi -= 12
        return midi

    def key_rect(self, midi):
        o = midi - self.low
        return KEY_RECTS.get(o) if 0 <= o <= SPAN else None

    def key_at(self, pos):
        for o in _BLACK_OFFS:                       # black keys lie on top
            if KEY_RECTS[o].collidepoint(pos):
                return self.low + o
        for o in _WHITE_OFFS:
            if KEY_RECTS[o].collidepoint(pos):
                return self.low + o
        return None

    def key_for(self, midi):
        """The computer key that plays ``midi`` right now (None if off-range)."""
        return KEY_FOR_OFFSET.get(midi - self.low)

    def _midi_for_event(self, e):
        off = SCAN_OFFSET.get(getattr(e, "scancode", 0) or -1)
        if off is None:
            off = KEY_OFFSET.get(e.key)
        return None if off is None else self.low + off

    def _prewarm(self, first=()):
        self.syn.prewarm(warm_order(self.base, first))      # the keys on screen first

    def sits_here(self):
        """Is the pianist sitting on a seat right at this piano?"""
        sit = getattr(self.p, "sitting", None)
        if not sit:
            return False
        by = getattr(self.g, "_home_piano_by", None)
        if by is None:
            return True
        try:
            q = by(sit[1], sit[2])[0]
        except Exception:
            return True
        return q is not None and q.gx == self.gx and q.gy == self.gy

    def _follow_seat(self, dt):
        """LAN client: sat down on the host's side (or got up) -> the screen
        says so (Esc leaves a seated farmer on the bench)."""
        if self.sits_here():
            self.seated, self._seat_wait = True, 0.0
        elif self._seat_wait > 0:
            self._seat_wait -= dt
        else:
            self.seated = False

    def _set_msg(self):
        s = self.song
        if s is None:
            self.msg = (f"{self.p.name} at the piano - play anything, chords too! "
                        "Hold Space for the sustain pedal.")
        else:
            self.msg = f"{s['title']}: press the glowing key! (Enter to listen first)"

    # ---- notes ----
    def press(self, midi, src):
        if self.phase == "closing" or src in self.src:
            return                                      # key repeat / already down
        self.src[src] = midi
        self.held[midi] = self.held.get(midi, 0) + 1
        self.sus.discard(midi)
        self.syn.note_on(midi, midi, random.uniform(0.9, 1.0))  # (chords: the synth balances)
        self.glow[midi] = 1.0
        self.trail.append([midi - 12 * (self.base - BASE_DEFAULT), 0.0])
        self._spawn_note(midi)
        self.g._piano_note(self, midi, True)
        if src[0] in ("k", "mouse"):
            if self.demo:
                self._stop_demo()
            self._song_check(midi)

    def release(self, src):
        midi = self.src.pop(src, None)
        if midi is None:
            return
        c = self.held.get(midi, 0) - 1
        if c > 0:
            self.held[midi] = c
            return
        self.held.pop(midi, None)
        self.syn.note_off(midi, pedal=self.pedal)
        if self.pedal:
            self.sus.add(midi)                          # keeps ringing: off on pedal up
        else:
            self.g._piano_note(self, midi, False)

    def release_all(self):
        for s in list(self.src):
            self.release(s)
        self.set_pedal(False)

    def set_pedal(self, down):
        if down == self.pedal:
            return
        self.pedal = down
        if not down:
            self.syn.pedal_up()
            for m in sorted(self.sus):
                if m not in self.held:
                    self.g._piano_note(self, m, False)
            self.sus = set()

    def _spawn_note(self, midi):
        r = self.key_rect(midi)
        if r is None:
            return
        size = random.choice((8, 9, 10))
        y = r.y + (r.h * 0.55 if r.h == WH else r.h * 0.5)
        self.fx.append([r.centerx + random.uniform(-6, 6), y, random.uniform(-22, 22),
                        random.uniform(-120, -90), 1.5, 1.5,
                        _note_glyph(pitch_color(midi), size), random.uniform(0, 6.28)])

    # ---- song book ----
    def set_mode(self, mode):
        mode %= len(SONGS) + 1
        self._stop_demo()
        self._stop_roll()                               # a new page mid-flourish: let go
        self.mode = mode
        if mode:
            self.last_song = mode
        self.song_i, self.scroll, self.done_t, self.reward = 0, 0.0, 0.0, ""
        if mode and self.base != BASE_DEFAULT:
            self.base = BASE_DEFAULT                    # every song sits on these keys
            self.oct_pop = 1.0
        self._set_msg()
        if mode:
            self._prewarm([m for m, _b in self.song["notes"]])

    def played(self, sid):
        """Has anyone finished this song before (any day, either farmer)?"""
        done = getattr(self.g, "_piano_songs", {}) or {}
        return any(k.endswith(":" + sid) for k in done)

    def step_song(self, d):
        """Up / Down and the < > arrows: the previous / next page of the book
        (page 0 is free play, so it cycles through it like the old tabs)."""
        self.set_mode(self.mode + d)                    # free play is page 0

    def open_book(self):
        self._stop_demo()
        self.book = {"sel": (self.mode or self.last_song) - 1, "t": 0.0}
        self.g.audio.play("page" if "page" in getattr(self.g.audio, "sfx", {}) else "ui_move")

    def close_book(self, pick=None):
        self.book = None
        if pick is not None:
            self.set_mode(pick + 1)
            self.g.audio.play("ui_select")

    def _book_cells(self):
        """(song index, rect) for every card in the open song list."""
        rows = (len(SONGS) + BOOK_COLS - 1) // BOOK_COLS
        gap = 10
        top = BOOK.y + 58
        cw = (BOOK.w - 48 - gap * (BOOK_COLS - 1)) // BOOK_COLS
        ch = min(52, (BOOK.bottom - 20 - top - gap * (rows - 1)) // rows)
        out = []
        for i in range(len(SONGS)):
            c, r = i % BOOK_COLS, i // BOOK_COLS
            out.append((i, pygame.Rect(BOOK.x + 24 + c * (cw + gap), top + r * (ch + gap),
                                       cw, ch)))
        return out

    def _book_key(self, k):
        n = len(SONGS)
        sel = self.book["sel"]
        if k in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_TAB):
            self.close_book()
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.close_book(sel)
        elif k == pygame.K_LEFT:
            self.book["sel"] = (sel - 1) % n
        elif k == pygame.K_RIGHT:
            self.book["sel"] = (sel + 1) % n
        elif k == pygame.K_UP:
            self.book["sel"] = (sel - BOOK_COLS) % n
        elif k == pygame.K_DOWN:
            self.book["sel"] = min(n - 1, sel + BOOK_COLS) if sel + BOOK_COLS < n else sel % BOOK_COLS
        else:
            return
        self.g.audio.play("ui_move")

    def _song_check(self, midi):
        want = self.target()
        if want is None:
            return
        if (midi - want) % 12:
            self.miss_t = 0.4                           # the right key gives a little wave
            return
        x = PLAY_X
        y = self._staff_y(self._staff_pos(want)[0])
        for _ in range(5):
            self.fx.append([x, y, random.uniform(-70, 70), random.uniform(-80, 10), 0.5, 0.5,
                            _spark_glyph((255, 214, 110), 4), 0.0])
        self.song_i += 1
        if self.song_i >= len(self.song["notes"]):
            self._finish()

    def _finish(self):
        s = self.song
        self.done_t = 3.4
        self.reward = self.g._piano_song_done(self, s["id"]) or ""
        self.msg = f"Bravo! {self.p.name} played {s['title']}."
        cx, cy = SHEET.centerx, SHEET.y + 72
        for _ in range(26):                             # hearts fly off both ends of the banner
            side = random.choice((-1, 1))
            col = random.choice([(255, 110, 150), (255, 150, 180), (255, 190, 200),
                                 (240, 120, 120)])
            self.fx.append([cx + side * random.uniform(170, 250), cy + random.uniform(-24, 24),
                            side * random.uniform(30, 160), random.uniform(-200, -60), 1.6, 1.6,
                            _heart_glyph(col, random.choice((6, 7, 8))), 0.0])
        for _ in range(18):
            self.fx.append([random.uniform(SHEET.x, SHEET.right), random.uniform(SHEET.y, KB_Y),
                            random.uniform(-30, 30), random.uniform(-60, -20), 1.2, 1.2,
                            _spark_glyph(random.choice([(255, 226, 120), (255, 255, 255),
                                                        (180, 230, 255)]), 5), 0.0])
        # the piano answers with a rolled chord
        self.roll = [[0.12 + i * 0.07, m, 0] for i, m in
                     enumerate(ROLL_CHORD) if LOW_MIDI <= m <= HIGH_MIDI]

    def listen(self):
        if self.song is None:
            return
        if self.demo:
            self._stop_demo()
            self._set_msg()
            return
        self._stop_roll()                               # the melody, not over the flourish
        self.song_i, self.scroll, self.done_t = 0, 0.0, 0.0
        if self.base != BASE_DEFAULT:                   # so the demo lights up on screen
            self.base = BASE_DEFAULT
            self.oct_pop = 1.0
        self.demo = {"i": 0, "t": 0.35, "off": None, "m": None}
        self.msg = f"Listen... then play {self.song['title']} yourself!"

    def _stop_demo(self):
        if self.demo:
            self.release(("demo",))
            self.demo = None
            self.song_i, self.scroll = 0, 0.0

    def _stop_roll(self):
        """Cut the celebration chord short: the keys it already struck come
        up (their sources would otherwise hold them down until the lid shuts)
        and the ones still waiting never play."""
        roll, self.roll = self.roll, []
        for r in roll:
            if r[2] == 1:
                self.release(("roll", r[1]))

    def _shift_octave(self, d):
        nb = max(BASE_MIN, min(BASE_MAX, self.base + d))
        if nb != self.base:
            self.base = nb
            self.oct_pop = 1.0
            self._prewarm()

    # ---- input ----
    def handle_event(self, e):
        if self.phase == "closing":
            return
        t = e.type
        if t == pygame.KEYDOWN:
            self._keydown(e)
        elif t == pygame.KEYUP:
            if e.key == pygame.K_SPACE:
                self.set_pedal(False)
            self.release(("k", e.key))
            self._keys.discard(e.key)
        elif t == pygame.MOUSEBUTTONDOWN and getattr(e, "button", 1) == 1:
            self._click(e.pos)
        elif t == pygame.MOUSEMOTION:
            if ("mouse",) in self.src and getattr(e, "buttons", (0,))[0]:
                m = self.key_at(e.pos)
                if m is not None and m != self.src[("mouse",)]:
                    self.release(("mouse",))            # glissando
                    self.press(m, ("mouse",))
        elif t == pygame.MOUSEBUTTONUP and getattr(e, "button", 1) == 1:
            self.release(("mouse",))
        elif t == getattr(pygame, "WINDOWLEAVE", -1):
            self.release(("mouse",))
        elif t == getattr(pygame, "WINDOWFOCUSLOST", -1):
            self.release_all()                          # the KEYUPs will never come
            self._keys.clear()

    def _keydown(self, e):
        k = e.key
        if k in self._keys:
            return                                      # key repeat: a piano doesn't
        self._keys.add(k)
        if self.book is not None:
            self._book_key(k)                           # the song list has the keys
            return
        if k in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.close()
        elif k == pygame.K_TAB:
            # Free play <-> the song book (it opens on the last page played);
            # Shift+Tab (or the button) opens the list of every song
            if getattr(e, "mod", 0) & pygame.KMOD_SHIFT:
                self.open_book()
                return
            self.set_mode(0 if self.mode else self.last_song)
            self.g.audio.play("page" if "page" in getattr(self.g.audio, "sfx", {}) else "ui_move")
        elif k in (pygame.K_UP, pygame.K_DOWN):
            self.step_song(-1 if k == pygame.K_UP else 1)
            self.g.audio.play("page" if "page" in getattr(self.g.audio, "sfx", {}) else "ui_move")
        elif k in (pygame.K_LEFT, pygame.K_RIGHT):
            self._shift_octave(-1 if k == pygame.K_LEFT else 1)
        elif k == pygame.K_SPACE:
            self.set_pedal(True)
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.listen()
        else:
            m = self._midi_for_event(e)
            if m is not None:
                self.press(m, ("k", k))

    def _click(self, pos):
        if self.book is not None:
            for i, r in self._book_cells():
                if r.collidepoint(pos):
                    self.close_book(i)
                    return
            if not BOOK.collidepoint(pos):
                self.close_book()                       # clicked outside: put it away
            return
        labels, rects = self._tabs
        for i, r in enumerate(rects):
            if r.collidepoint(pos):
                want = self.last_song if i else 0
                if want != self.mode:
                    self.set_mode(want)
                    self.g.audio.play("ui_move")
                return
        if ALL_BTN.collidepoint(pos):
            self.open_book()
            return
        if PICK.collidepoint(pos):
            self.open_book()
            return
        if PICK_L.collidepoint(pos) or PICK_R.collidepoint(pos):
            self.step_song(-1 if PICK_L.collidepoint(pos) else 1)
            self.g.audio.play("ui_move")
            return
        if OCT_L.collidepoint(pos) or OCT_R.collidepoint(pos):
            self._shift_octave(-1 if OCT_L.collidepoint(pos) else 1)
            return
        if self._listen_rect and self._listen_rect.collidepoint(pos) and self.song:
            self.listen()
            return
        m = self.key_at(pos)
        if m is not None:
            self.press(m, ("mouse",))

    def close(self):
        if self.phase == "closing":
            return
        self._stop_demo()
        self._stop_roll()
        self.release_all()
        self.phase, self.t = "closing", 0.0

    # ---- update ----
    def update(self, dt):
        self.clock += dt
        self.t += dt
        if self.client:
            self._follow_seat(dt)
        if self.phase == "opening" and self.t >= OPEN_T:
            self.phase, self.t = "play", 0.0
        elif self.phase == "closing":
            if self.t >= CLOSE_T:
                self.g._piano_closed(self)
            return
        for m in list(self.glow):
            if m not in self.held:
                self.glow[m] -= dt * 3.2
                if self.glow[m] <= 0:
                    del self.glow[m]
        for tr in self.trail:
            tr[1] += dt
        self.trail = [tr for tr in self.trail if tr[1] < TRAIL_LIFE][-48:]
        for f in self.fx:
            f[0] += f[2] * dt + math.sin(self.clock * 5 + f[7]) * 14 * dt
            f[1] += f[3] * dt
            f[3] += 30 * dt
            f[2] *= max(0.0, 1.0 - dt * 1.5)
            f[4] -= dt
        self.fx = [f for f in self.fx if f[4] > 0][-160:]
        self.miss_t = max(0.0, self.miss_t - dt)
        if self.book is not None:
            self.book["t"] += dt
        self.oct_pop = max(0.0, self.oct_pop - dt * 3)
        self._update_demo(dt)
        for r in self.roll:
            r[0] -= dt
            if r[0] <= 0 and r[2] == 0:
                self.press(r[1], ("roll", r[1]))
                r[0], r[2] = 1.3, 1
            elif r[0] <= 0 and r[2] == 1:
                self.release(("roll", r[1]))
                r[2] = 2
        self.roll = [r for r in self.roll if r[2] < 2]
        if self.done_t > 0:
            self.done_t -= dt
            if self.done_t <= 0:
                self.done_t, self.song_i, self.scroll, self.reward = 0.0, 0, 0.0, ""
                self.msg = f"Play {self.song['title']} again, or Down for the next song."
        view = self.demo["i"] - 1 if self.demo else self.song_i
        self.scroll += (max(0, view) - self.scroll) * min(1.0, dt * 10)

    def _update_demo(self, dt):
        d = self.demo
        if not d:
            return
        notes = self.song["notes"]
        if d["off"] is not None:
            d["off"] -= dt
            if d["off"] <= 0:
                self.release(("demo",))
                d["off"] = None
        d["t"] -= dt
        if d["t"] > 0:
            return
        self.release(("demo",))
        if d["i"] >= len(notes):
            self.demo = None
            self.song_i, self.scroll = 0, 0.0
            self.msg = f"Your turn! Play {self.song['title']} - follow the glowing keys."
            return
        m, beats = notes[d["i"]]
        dur = beats * self.song["beat"]
        self.press(m, ("demo",))
        d["m"], d["i"], d["t"], d["off"] = m, d["i"] + 1, dur, dur * 0.85

    # ---- draw ----
    def draw(self, surf):
        K.dim(surf, 150)
        P = K.modal(surf, PANEL, "Piano", K.font(28, True))
        self._draw_tabs(surf)
        color = self._case_color()
        self._draw_case(surf, color)
        self._draw_sheet(surf)
        self._draw_nameboard(surf, color)
        self._draw_keys(surf)
        self._draw_fallboard(surf, color)
        self._draw_fx(surf)
        if self.book is not None:
            self._draw_book(surf)
        f = K.fit_font(self.msg, P.w - 80, (15, 14, 13, 12), bold=True)
        K.blit_text(surf, f, self.msg, K.GOLD_TXT if self.done_t > 0 else K.INK_SOFT,
                    (P.centerx, 630))
        self._draw_hints(surf, P)

    def _case_color(self):
        from . import furniture as F
        try:
            c = F.PALETTE[self.piece.ci % len(F.PALETTE)][1]
        except Exception:
            c = (138, 94, 64)
        if sum(c) > 660:                       # a white piano: warm it up a touch
            c = _mix(c, (246, 238, 222), 0.5)
        return c

    def _draw_tabs(self, surf):
        labels, rects = self._tabs
        K.tabs(surf, rects, labels, 1 if self.mode else 0, fnt_sizes=(15, 14, 13, 12),
               t=self.clock)
        # the song on the stand: < title  n/N  stars >
        s = SONGS[(self.mode or self.last_song) - 1]
        live = bool(self.mode)
        for r, ch in ((PICK_L, "<"), (PICK_R, ">")):
            pygame.draw.rect(surf, K.WOOD_DK, r, border_radius=7)
            pygame.draw.rect(surf, K.CREAM, r.inflate(-4, -4), border_radius=6)
            K.blit_text(surf, K.font(16, True), ch, K.INK, r.center)
        well = PICK
        pygame.draw.rect(surf, (222, 200, 166) if live else (236, 222, 196), well, border_radius=9)
        pygame.draw.rect(surf, K.WOOD_DK if live else K.WELL_LINE, well, 2, border_radius=9)
        idx = f"{(self.mode or self.last_song)}/{len(SONGS)}"
        fi = K.font(12, True)
        K.blit_text(surf, fi, idx, K.INK_SOFT, (well.x + 12, well.centery), align="left")
        self._stars(surf, well.right - 14, well.centery, s["stars"], right=True)
        room = well.w - 170
        ft = K.fit_font(s["title"], room, (16, 15, 14, 13), bold=True)
        tr = K.blit_text(surf, ft, K.ellipsize(ft, s["title"], room),
                         K.INK if live else K.INK_SOFT, (well.centerx - 6, well.centery))
        if self.played(s["id"]):                        # a little green tick: played
            x, y = tr.right + 10, well.centery
            pygame.draw.lines(surf, K.SPROUT, False, [(x, y), (x + 4, y + 4), (x + 11, y - 5)], 3)
        K.button(surf, ALL_BTN, "All songs  (Shift+Tab)", self.book is not None,
                 K.font(13, True))

    def _stars(self, surf, x, y, n, right=False, size=5):
        """n of 3 little difficulty stars ending (right=True) or starting at x."""
        xs = [x - (2 - i) * (size * 2 + 3) if right else x + i * (size * 2 + 3)
              for i in range(3)]
        for i, cx in enumerate(xs):
            pts = []
            for j in range(10):
                a = -math.pi / 2 + j * math.pi / 5
                r = size if j % 2 == 0 else size * 0.45
                pts.append((cx + math.cos(a) * r, y + math.sin(a) * r))
            col = (236, 176, 60) if i < n else (214, 200, 176)
            pygame.draw.polygon(surf, col, pts)
            pygame.draw.polygon(surf, (150, 104, 40) if i < n else (190, 174, 150), pts, 1)

    def _draw_book(self, surf):
        """The song list: a parchment page over the piano, songs as cards
        (title, shelf, difficulty stars, a tick once played)."""
        k = min(1.0, self.book["t"] / 0.14)
        shade = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        shade.fill((30, 18, 24, int(120 * k)))
        surf.blit(shade, (0, 0))
        r = BOOK.move(0, int((1 - k) * 18))
        K.draw_card(surf, r, radius=14)
        K.ribbon(surf, K.font(20, True), "Song Book", (r.centerx, r.y + 4))
        K.blit_text(surf, K.font(13, True),
                    f"{len(SONGS)} songs  -  arrows choose, Enter plays, Esc closes",
                    K.INK_SOFT, (r.centerx, r.y + 40))
        dy = r.y - BOOK.y
        fa, fb = K.font(15, True), K.font(12, True)
        for i, cell in self._book_cells():
            c = cell.move(0, dy)
            s = SONGS[i]
            sel = i == self.book["sel"]
            cur = i + 1 == self.mode
            if sel:
                K.row_cursor(surf, c, self.clock)
            else:
                K.well(surf, c)
            num = pygame.Rect(c.x + 8, c.centery - 12, 24, 24)
            pygame.draw.rect(surf, K.WOOD_DK if cur else (222, 200, 166), num, border_radius=7)
            K.blit_text(surf, fb, str(i + 1), K.CREAM if cur else K.INK, num.center)
            tx = num.right + 10
            room = c.right - 70 - tx
            K.blit_text(surf, fa, K.ellipsize(fa, s["tab"], room), K.INK, (tx, c.y + 17),
                        align="left")
            K.blit_text(surf, fb, s["shelf"], K.INK_SOFT, (tx, c.y + 35), align="left")
            self._stars(surf, c.right - 14, c.y + 17, s["stars"], right=True, size=5)
            if self.played(s["id"]):
                K.blit_text(surf, fb, "played", K.SPROUT, (c.right - 12, c.y + 35),
                            align="right")

    def _draw_case(self, surf, c):
        lt, dk, dk2 = _lt(c, 1.1), _dk(c, 0.8), _dk(c, 0.55)
        surf.blit(_shadow(CASE.w + 16, CASE.h + 12, 22, 80), (CASE.x - 4, CASE.y + 4))
        pygame.draw.rect(surf, dk2, CASE.inflate(6, 6), border_radius=20)
        pygame.draw.rect(surf, c, CASE, border_radius=18)
        pygame.draw.rect(surf, lt, (CASE.x + 14, CASE.y + 6, CASE.w - 28, 6), border_radius=3)
        # carved panels either side of the music desk
        for px in (CASE.x + 20, SHEET.right + 44):
            pnl = pygame.Rect(px, CASE.y + 22, SHEET.x - 44 - CASE.x - 20, 128)
            pygame.draw.rect(surf, dk, pnl, 2, border_radius=12)
            pygame.draw.rect(surf, lt, pnl.inflate(-10, -10), 1, border_radius=9)
        # the music desk ledge
        ledge = pygame.Rect(SHEET.x - 26, SHEET.bottom + 2, SHEET.w + 52, 10)
        pygame.draw.rect(surf, dk2, ledge.move(0, 2), border_radius=4)
        pygame.draw.rect(surf, dk, ledge, border_radius=4)
        pygame.draw.line(surf, lt, (ledge.x + 6, ledge.y + 1), (ledge.right - 6, ledge.y + 1), 1)
        # candle sconces
        for cx in ((CASE.x + SHEET.x) // 2 - 2, (SHEET.right + CASE.right) // 2 + 2):
            self._draw_candle(surf, cx, CASE.y + 128)
        # key bed: cheek blocks, key slip
        kw = len(_WHITE_OFFS) * WK
        for x in (KB_X - 22, KB_X + kw + 2):
            cheek = pygame.Rect(x, NAME.bottom + 2, 20, KB_Y + WH - NAME.bottom + 12)
            pygame.draw.rect(surf, dk, cheek, border_radius=5)
            pygame.draw.rect(surf, lt, (cheek.x + 3, cheek.y + 3, cheek.w - 6, 3), border_radius=2)
        slip = pygame.Rect(NAME.x, KB_Y + WH, NAME.w, 14)
        pygame.draw.rect(surf, dk, slip, border_radius=4)
        pygame.draw.line(surf, lt, (slip.x + 8, slip.y + 2), (slip.right - 8, slip.y + 2), 1)
        pygame.draw.rect(surf, (32, 22, 26), (KB_X - 2, KB_Y - 10, kw + 4, WH + 10))  # key well

    def _draw_candle(self, surf, cx, cy):
        brass, brass_dk = (214, 176, 96), (150, 112, 52)
        pygame.draw.ellipse(surf, brass_dk, (cx - 14, cy + 30, 28, 12))
        pygame.draw.ellipse(surf, brass, (cx - 12, cy + 30, 24, 9))
        pygame.draw.arc(surf, brass_dk, (cx - 22, cy + 6, 26, 32), 4.4, 6.3, 4)
        pygame.draw.line(surf, brass_dk, (cx, cy + 34), (cx, cy + 20), 4)
        pygame.draw.ellipse(surf, brass, (cx - 11, cy + 14, 22, 8))
        pygame.draw.rect(surf, (248, 240, 222), (cx - 5, cy - 18, 10, 34), border_radius=3)
        pygame.draw.rect(surf, (222, 206, 180), (cx + 1, cy - 18, 4, 34), border_radius=2)
        fl = 1.0 + 0.12 * math.sin(self.clock * 11 + cx) + 0.06 * math.sin(self.clock * 23)
        glow = pygame.Surface((60, 60), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 200, 120, 46), (30, 30), int(26 * fl))
        pygame.draw.circle(glow, (255, 220, 150, 60), (30, 30), int(14 * fl))
        surf.blit(glow, (cx - 30, cy - 52))
        fh = int(13 * fl)
        pygame.draw.ellipse(surf, (255, 170, 60), (cx - 4, cy - 20 - fh, 8, fh + 4))
        pygame.draw.ellipse(surf, (255, 240, 180), (cx - 2, cy - 16 - fh // 2, 4, fh // 2 + 2))
        pygame.draw.line(surf, (60, 40, 30), (cx, cy - 18), (cx, cy - 21), 1)

    def _draw_nameboard(self, surf, c):
        pygame.draw.rect(surf, _dk(c, 0.86), NAME, border_radius=8)
        pygame.draw.rect(surf, _dk(c, 0.6), NAME, 2, border_radius=8)
        # the maker's nameplate: gold on a dark inlay (reads on any lacquer)
        f = _serif(20, italic=True, bold=True)
        t = "Harvest Duo"
        tx = f.render(t, True, (236, 196, 104))
        r = tx.get_rect(center=(NAME.centerx, NAME.centery))
        inlay = r.inflate(56, 0)
        inlay.h, inlay.centery = NAME.h - 8, NAME.centery
        pygame.draw.rect(surf, (58, 40, 36), inlay, border_radius=8)
        pygame.draw.rect(surf, (150, 112, 60), inlay, 1, border_radius=8)
        surf.blit(f.render(t, True, (20, 12, 10)), r.move(1, 1))
        surf.blit(tx, r)
        for dx in (-1, 1):
            x = NAME.centerx + dx * (r.w // 2 + 16)
            pygame.draw.circle(surf, (236, 196, 104), (x, NAME.centery), 3)
        # sustain pedal lamp
        lamp = (255, 214, 110) if self.pedal else _dk(c, 0.6)
        lx = NAME.x + 26
        if self.pedal:
            gl = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.circle(gl, (255, 214, 110, 70), (20, 20), 16)
            surf.blit(gl, (lx - 20, NAME.centery - 20))
        pygame.draw.circle(surf, _dk(c, 0.4), (lx, NAME.centery), 8)
        pygame.draw.circle(surf, lamp, (lx, NAME.centery), 6)
        ink = (250, 240, 220) if sum(c) < 420 else K.INK
        K.blit_text(surf, K.font(13, True), "PEDAL" + (" (held)" if self.pedal else "  Space"),
                    ink, (lx + 16, NAME.centery), align="left")
        # octave range: < C3 - E5 >
        for r_, ch in ((OCT_L, "<"), (OCT_R, ">")):
            can = (self.base > BASE_MIN) if ch == "<" else (self.base < BASE_MAX)
            pygame.draw.rect(surf, K.WOOD_DK if can else _dk(c, 0.7), r_, border_radius=6)
            pygame.draw.rect(surf, K.CREAM if can else _dk(c, 0.8), r_.inflate(-4, -4),
                             border_radius=5)
            K.blit_text(surf, K.font(15, True), ch, K.INK if can else K.INK_FAINT, r_.center)
        plaque = pygame.Rect(OCT_L.right + 6, NAME.y + 5, OCT_R.x - OCT_L.right - 12, 22)
        pop = self.oct_pop
        pygame.draw.rect(surf, _mix((58, 40, 36), (120, 80, 40), pop), plaque, border_radius=6)
        rng = f"{note_name(self.low)} - {note_name(self.low + SPAN)}"
        K.blit_text(surf, K.font(14, True), rng, _mix((250, 236, 206), (255, 220, 120), pop),
                    plaque.center)

    # -- the music desk
    def _staff_pos(self, midi):
        """(staff step, octave marks): E4 = 30. The sheet fits B2..A5 in free
        play (G3.. under the song book's key hints); anything further out is
        drawn 8va / 8vb."""
        p = _DIA[midi % 12] + 7 * (midi // 12 - 1)
        lo = 24 if self.song else 20
        k8 = 0
        while p > 40:
            p -= 7
            k8 += 1
        while p < lo:
            p += 7
            k8 -= 1
        return p, k8

    @staticmethod
    def _staff_y(p):
        return STAFF_TOP + 4 * LS - (p - 30) * LS / 2

    def _draw_sheet(self, surf):
        surf.blit(_shadow(SHEET.w, SHEET.h, 6, 70), SHEET.move(3, 4))
        pygame.draw.rect(surf, (253, 250, 240), SHEET, border_radius=6)
        pygame.draw.rect(surf, K.WELL_LINE, SHEET, 2, border_radius=6)
        pygame.draw.line(surf, (240, 232, 214), (SHEET.x + 8, SHEET.y + 4),
                         (SHEET.right - 8, SHEET.y + 4), 2)
        # staff + clef
        x1 = SHEET.right - 16
        for i in range(5):
            y = STAFF_TOP + i * LS
            pygame.draw.line(surf, (150, 132, 118), (SHEET.x + 14, y), (x1, y), 1)
        pygame.draw.line(surf, (150, 132, 118), (SHEET.x + 14, STAFF_TOP),
                         (SHEET.x + 14, STAFF_TOP + 4 * LS), 2)
        cl = _clef(58)
        if cl.get_height() > 70:
            cl = pygame.transform.smoothscale(cl, (int(cl.get_width() * 70 / cl.get_height()), 70))
        surf.blit(cl, cl.get_rect(center=(SHEET.x + 36, STAFF_TOP + 2 * LS + 2)))
        s = self.song
        if s is None:
            self._draw_free_sheet(surf)
        else:
            self._draw_song_sheet(surf, s)
        if self.done_t > 0:
            self._draw_bravo(surf)

    def _draw_free_sheet(self, surf):
        tr = K.blit_text(surf, _serif(19), "Free play", K.INK, (SHEET.x + 18, SHEET.y + 18),
                         align="left")
        shift = self.base - BASE_DEFAULT
        if shift:                     # written where it reads best, played 8va / 8vb
            cap = {1: "8va - sounds an octave higher", 2: "15ma - two octaves higher",
                   -1: "8vb - sounds an octave lower"}.get(shift, "")
            K.blit_text(surf, K.font(12, True), cap, K.INK_SOFT, (tr.right + 12, SHEET.y + 19),
                        align="left")
        kind, name = held_label(self.held)
        if kind == "chord":
            f = K.fit_font(name, 330, (17, 16, 15, 14), bold=True)
            K.blit_text(surf, f, name, K.SPROUT, (SHEET.right - 18, SHEET.y + 18), align="right")
        elif kind:                                        # no chord: the note(s), marked
            f = K.fit_font(name, 310, (15, 14, 13, 12), bold=True)   # as notes, so "C7"
            r = K.blit_text(surf, f, name, K.INK_SOFT,                # never reads as a chord
                            (SHEET.right - 18, SHEET.y + 18), align="right")
            gl = _note_glyph(pitch_color(min(self.held)), 6)
            surf.blit(gl, gl.get_rect(midright=(r.x - 5, r.centery - 1)))
        else:
            K.blit_text(surf, K.font(13, True), "hold a few keys for a chord", K.INK_FAINT,
                        (SHEET.right - 18, SHEET.y + 18), align="right")
        x0, x1 = STAFF_X0, SHEET.right - 30
        for m, age in self.trail:
            x = x1 - age * 86
            if x < x0:
                continue
            fade = min(1.0, (x - x0) / 60.0)
            self._note_head(surf, m, x, 1.0, pitch_color(m), fade, stem=False)

    def _draw_song_sheet(self, surf, s):
        notes = s["notes"]
        K.blit_text(surf, _serif(19), s["title"], K.INK, (SHEET.x + 18, SHEET.y + 18),
                    align="left")
        done = len(notes) if self.done_t > 0 else self.song_i
        bar = pygame.Rect(SHEET.x + 372, SHEET.y + 13, 150, 10)
        pygame.draw.rect(surf, K.WELL, bar, border_radius=5)
        if done:
            pygame.draw.rect(surf, K.LEAF, (bar.x, bar.y, max(10, bar.w * done // len(notes)),
                                            bar.h), border_radius=5)
        pygame.draw.rect(surf, K.WELL_LINE, bar, 1, border_radius=5)
        K.blit_text(surf, K.font(13, True), f"{done} / {len(notes)}", K.INK_SOFT,
                    (bar.right + 10, bar.centery), align="left")
        lab = "Stop" if self.demo else "Listen"
        self._listen_rect = K.key_pill(surf, "Enter", lab, (SHEET.right - 68, SHEET.y + 18),
                                       fnt=K.font(12, True))
        # play line + the melody scrolling past it
        pl = pygame.Surface((24, 4 * LS + 34), pygame.SRCALPHA)
        pl.fill((255, 214, 110, 60))
        surf.blit(pl, (PLAY_X - 12, STAFF_TOP - 16))
        cur = self.demo["i"] - 1 if self.demo else self.song_i
        lo_x, hi_x = STAFF_X0 - 4, SHEET.right - 24
        for j in range(max(0, int(self.scroll) - 3), min(len(notes), int(self.scroll) + 14)):
            m, beats = notes[j]
            x = PLAY_X + (j - self.scroll) * NOTE_DX
            if not lo_x <= x <= hi_x:
                continue
            edge = min(1.0, (x - lo_x) / 40.0, (hi_x - x) / 40.0)
            if j < cur or self.done_t > 0:
                col, a = K.LEAF, 0.55 * edge
            elif j == cur:
                col, a = K.GOLD_TXT, 1.0
            else:
                col, a = K.INK, edge
            if j == cur and self.done_t <= 0:
                pulse = 0.5 + 0.5 * math.sin(self.clock * 6)
                y = self._staff_y(self._staff_pos(m)[0])
                ring = pygame.Surface((34, 34), pygame.SRCALPHA)
                pygame.draw.circle(ring, (255, 214, 110, int(90 + 70 * pulse)), (17, 17), 15)
                surf.blit(ring, (x - 17, y - 17))
            self._note_head(surf, m, x, beats, col, a, stem=True)
            if cur <= j < cur + 6 and self.done_t <= 0:        # which key to press
                key = _LABEL.get(self.shown(m) - self.low, "?")
                r = pygame.Rect(0, 0, 20, 17)
                r.center = (int(x), SHEET.y + 118)
                hot = j == cur
                fill = K.HILITE if hot else _mix(K.WELL, (253, 250, 240), 1 - edge)
                pygame.draw.rect(surf, fill, r, border_radius=5)
                pygame.draw.rect(surf, K.GOLD_RIM if hot else K.WELL_LINE, r, 1, border_radius=5)
                K.blit_text(surf, K.font(12, True), key, K.INK if hot else K.INK_SOFT, r.center)

    def _note_head(self, surf, midi, x, beats, col, alpha, stem=True):
        """A note on the treble staff (ledger lines, sharp, stem, flags, dots)."""
        if alpha <= 0.02:
            return
        p, k8 = self._staff_pos(midi)
        y = self._staff_y(p)
        ink = _mix((253, 250, 240), (110, 96, 88), alpha)
        c = _mix((253, 250, 240), col, alpha)
        for lp in range(28, p - 1, -2):                   # ledger lines below
            ly = self._staff_y(lp)
            pygame.draw.line(surf, ink, (x - 10, ly), (x + 10, ly), 1)
        for lp in range(40, p + 1, 2):                    # ... and above
            ly = self._staff_y(lp)
            pygame.draw.line(surf, ink, (x - 10, ly), (x + 10, ly), 1)
        hollow = beats >= 2
        head = pygame.Rect(0, 0, 13, 9)
        head.center = (int(x), int(y))
        pygame.draw.ellipse(surf, c, head, 2 if hollow else 0)
        if midi % 12 in _BLACK_PC:
            K.blit_text(surf, K.font(12, True), "#", c, (x - 14, y))
        if beats >= 4 or not stem:
            pass
        elif p < 34:                                      # stem up, right side
            sx = head.right - 1
            pygame.draw.line(surf, c, (sx, y), (sx, y - 3 * LS - 2), 2)
            for fi in range(2 if beats <= 0.25 else 1 if beats <= 0.75 else 0):
                fy = y - 3 * LS - 2 + fi * 6
                pygame.draw.line(surf, c, (sx, fy), (sx + 7, fy + 9), 2)
        else:                                             # stem down, left side
            sx = head.x + 1
            pygame.draw.line(surf, c, (sx, y), (sx, y + 3 * LS + 2), 2)
            for fi in range(2 if beats <= 0.25 else 1 if beats <= 0.75 else 0):
                fy = y + 3 * LS + 2 - fi * 6
                pygame.draw.line(surf, c, (sx, fy), (sx + 7, fy - 9), 2)
        if beats in (0.75, 1.5, 3.0):                     # dotted
            pygame.draw.circle(surf, c, (head.right + 4, int(y) - (0 if p % 2 else 3)), 2)
        if k8:
            mark = ("8" if abs(k8) == 1 else "15") + ("va" if k8 > 0 else "vb")
            K.blit_text(surf, K.font(10, True), mark, ink,
                        (x, y - 14 if k8 > 0 else y + 14))

    def _draw_bravo(self, surf):
        k = min(1.0, (3.4 - self.done_t) / 0.25)
        band = pygame.Rect(0, 0, 470, 58)                 # a little hop as it lands
        band.center = (SHEET.centerx, SHEET.y + 72 - int(10 * math.sin(k * math.pi)))
        s = pygame.Surface(band.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (*K.CREAM_HI, 240), s.get_rect(), border_radius=14)
        pygame.draw.rect(s, (*K.HEART, 255), s.get_rect(), 3, border_radius=14)
        s.set_alpha(int(255 * min(1.0, 0.35 + k)))
        surf.blit(s, band)
        K.blit_text(surf, _serif(24, italic=True, bold=True), "Bravo!", (200, 70, 110),
                    (band.centerx, band.y + 20))
        sub = f"{self.song['title']}  -  " + (self.reward or "lovely!")
        f = K.fit_font(sub, band.w - 28, (14, 13, 12, 11), bold=True)
        K.blit_text(surf, f, sub, K.INK_SOFT, (band.centerx, band.y + 43))

    # -- the keys
    def _draw_keys(self, surf):
        lo = self.low
        tgt = self.target()
        tgt = self.shown(tgt) if tgt is not None else None
        nxt = []
        s = self.song
        if s is not None and tgt is not None:
            for m, _b in s["notes"][self.song_i + 1:self.song_i + 3]:
                nxt.append(self.shown(m))
        hover = None
        try:
            if pygame.mouse.get_focused():
                hover = self.key_at(pygame.mouse.get_pos())
        except Exception:
            hover = None
        # felt strip over the key backs
        kw = len(_WHITE_OFFS) * WK
        for o in _WHITE_OFFS:
            self._white_key(surf, o, lo + o, tgt, nxt, hover)
        for o in _BLACK_OFFS:
            self._black_key(surf, o, lo + o, tgt, nxt, hover)
        pygame.draw.rect(surf, (150, 38, 52), (KB_X - 2, KB_Y - 10, kw + 4, 8))
        pygame.draw.line(surf, (96, 22, 34), (KB_X - 2, KB_Y - 3), (KB_X + kw + 1, KB_Y - 3), 2)

    def _key_glow(self, surf, r, midi, strength):
        if strength <= 0:
            return
        col = pitch_color(midi)
        g = pygame.Surface(r.size, pygame.SRCALPHA)
        g.fill((*col, int(110 * strength)))
        surf.blit(g, r.topleft)
        pygame.draw.rect(surf, col, (r.x + 3, r.bottom - 5, r.w - 6, 3), border_radius=2)

    def _white_key(self, surf, o, midi, tgt, nxt, hover):
        base = KEY_RECTS[o]
        down = midi in self.held
        g = self.glow.get(midi, 0.0)
        r = base.move(0, 3) if down else base
        face = (236, 228, 208) if down else (252, 248, 236)
        if hover == midi and not down:
            face = (255, 252, 244)
        lip = 5 if down else 9
        pygame.draw.rect(surf, (224, 214, 192), (r.x + 1, r.y, r.w - 2, r.h),
                         border_bottom_left_radius=5, border_bottom_right_radius=5)
        pygame.draw.rect(surf, face, (r.x + 1, r.y, r.w - 2, r.h - lip),
                         border_bottom_left_radius=3, border_bottom_right_radius=3)
        shade = _cached_shade(r.w - 2, 18)
        surf.blit(shade, (r.x + 1, r.y))
        if midi == tgt:
            pulse = 0.5 + 0.5 * math.sin(self.clock * 6)
            wob = math.sin(self.clock * 40) * 3 * min(1.0, self.miss_t / 0.4)
            tint = pygame.Surface((r.w - 2, r.h - lip), pygame.SRCALPHA)
            tint.fill((255, 214, 110, int(60 + 60 * pulse)))
            surf.blit(tint, (r.x + 1, r.y))
            hl = pygame.Rect(r.x + 7, r.bottom - 55, r.w - 14, 46).move(wob, 0)
            pygame.draw.rect(surf, K.HILITE, hl, border_radius=9)
            pygame.draw.rect(surf, _mix(K.GOLD_RIM, (240, 192, 104), pulse), hl, 3,
                             border_radius=9)
        self._key_glow(surf, pygame.Rect(r.x + 1, r.y, r.w - 2, r.h - lip), midi, g)
        pygame.draw.line(surf, (150, 136, 118), (r.x, r.y), (r.x, r.bottom - 3), 1)
        pygame.draw.line(surf, (150, 136, 118), (r.right - 1, r.y), (r.right - 1, r.bottom - 3), 1)
        lab = _LABEL.get(o, "")
        K.blit_text(surf, K.font(18, True), lab, K.INK, (r.centerx, r.bottom - 38))
        if midi in nxt:                                   # "2" / "3": the notes after it
            n = nxt.index(midi) + 2
            c = (r.centerx, r.bottom - 20)
            pygame.draw.circle(surf, (206, 230, 186), c, 8)
            pygame.draw.circle(surf, K.SPROUT, c, 8, 2)
            K.blit_text(surf, K.font(11, True), str(n), K.INK, c)
        elif o == 12:
            K.blit_text(surf, K.font(12, True), "or ,", K.INK_SOFT, (r.centerx, r.bottom - 20))
        if midi % 12 == 0:
            nm = note_name(midi)
            col = K.SPROUT if midi == 60 else K.INK_FAINT
            K.blit_text(surf, K.font(12, True), nm, col, (r.centerx, r.bottom - 64))

    def _black_key(self, surf, o, midi, tgt, nxt, hover):
        base = KEY_RECTS[o]
        down = midi in self.held
        g = self.glow.get(midi, 0.0)
        r = base.move(0, 2) if down else base
        surf.blit(_black_shadow(), (base.x + 2, base.y + 2))
        body = (46, 40, 48) if hover == midi and not down else (34, 30, 36)
        pygame.draw.rect(surf, (16, 14, 18), r, border_bottom_left_radius=4,
                         border_bottom_right_radius=4)
        top = pygame.Rect(r.x + 3, r.y, r.w - 6, r.h - (8 if down else 13))
        pygame.draw.rect(surf, body, top, border_bottom_left_radius=3,
                         border_bottom_right_radius=3)
        pygame.draw.line(surf, (92, 84, 96) if not down else (70, 64, 74),
                         (top.x + 4, top.y + 4), (top.x + 4, top.bottom - 8), 2)
        if midi == tgt:
            pulse = 0.5 + 0.5 * math.sin(self.clock * 6)
            wob = math.sin(self.clock * 40) * 3 * min(1.0, self.miss_t / 0.4)
            tint = pygame.Surface(top.size, pygame.SRCALPHA)
            tint.fill((255, 214, 110, int(70 + 60 * pulse)))
            surf.blit(tint, top.topleft)
            pygame.draw.rect(surf, _mix(K.GOLD_RIM, (255, 226, 130), pulse),
                             r.inflate(4, 4).move(wob, 0), 3, border_radius=5)
        self._key_glow(surf, top, midi, g)
        if midi in nxt:
            n = nxt.index(midi) + 2
            c = (r.centerx, r.y + 30)
            pygame.draw.circle(surf, (200, 226, 180), c, 9)
            pygame.draw.circle(surf, K.SPROUT, c, 9, 2)
            K.blit_text(surf, K.font(11, True), str(n), K.INK, c)
        K.blit_text(surf, K.font(14, True), _LABEL.get(o, ""), (240, 228, 206),
                    (r.centerx, r.bottom - 26))

    def _draw_fallboard(self, surf, c):
        if self.phase == "opening":
            k = 1 - (1 - min(1.0, self.t / OPEN_T)) ** 3
        elif self.phase == "closing":
            k = 1 - min(1.0, self.t / CLOSE_T) ** 2
        else:
            return
        h = int((WH + 12) * (1 - k))
        if h <= 0:
            return
        kw = len(_WHITE_OFFS) * WK
        fb = pygame.Rect(KB_X - 4, KB_Y - 10, kw + 8, h)
        pygame.draw.rect(surf, c, fb, border_bottom_left_radius=6, border_bottom_right_radius=6)
        pygame.draw.rect(surf, _dk(c, 0.6), fb, 2, border_bottom_left_radius=6,
                         border_bottom_right_radius=6)
        pygame.draw.line(surf, _lt(c, 1.15), (fb.x + 6, fb.bottom - 5), (fb.right - 6, fb.bottom - 5), 2)

    def _draw_fx(self, surf):
        for f in self.fx:
            spr = f[6]
            a = int(255 * max(0.0, min(1.0, f[4] / f[5] * 1.6)))
            spr.set_alpha(a)
            surf.blit(spr, (f[0] - spr.get_width() // 2, f[1] - spr.get_height() // 2))
            spr.set_alpha(255)

    def hint_pills(self):
        """The key hints along the bottom (they follow the Listen button)."""
        if self.book is not None:
            return [("Arrows", "Choose"), ("Enter", "Play it"), ("Esc", "Close list")]
        pills = [("Z-M  Q-P", "Play"), ("← →", "Octave"), ("Space", "Pedal"),
                 ("Tab", "Song book"), ("↑ ↓", "Songs")]
        if self.song:
            pills.append(("Enter", "Stop" if self.demo else "Listen"))
        pills.append(("Esc", "Stop playing" if self.seated else "Leave"))
        return pills

    def _draw_hints(self, surf, P):
        pills = self.hint_pills()
        f = K.font(13, True)
        widths = []
        for key, lab in pills:
            widths.append(f.size(key)[0] + f.size(lab)[0] + 38)
        gap = 14
        x = P.centerx - (sum(widths) + gap * (len(widths) - 1)) // 2
        for (key, lab), w in zip(pills, widths):
            K.key_pill(surf, key, lab, (x + w // 2, 662), fnt=f)
            x += w + gap


_SHADE = {}


def _shadow(w, h, radius, alpha):
    """A soft rounded drop shadow (cached)."""
    key = ("drop", w, h, radius, alpha)
    s = _SHADE.get(key)
    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(s, (40, 20, 30, alpha), s.get_rect(), border_radius=radius)
        _SHADE[key] = s
    return s


def _black_shadow():
    s = _SHADE.get("black")
    if s is None:
        s = pygame.Surface((BK + 3, BH + 3), pygame.SRCALPHA)
        pygame.draw.rect(s, (30, 20, 20, 70), s.get_rect(), border_radius=5)
        _SHADE["black"] = s
    return s


def _cached_shade(w, h):
    """The soft shadow the felt casts on the back of a white key."""
    s = _SHADE.get((w, h))
    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(h):
            s.fill((90, 60, 40, int(70 * (1 - y / h) ** 2)), (0, y, w, 1))
        _SHADE[(w, h)] = s
    return s
