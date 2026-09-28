"""Procedurally synthesized audio — sound effects + looping ambient music.

No external audio files are needed: every sound is generated as 16-bit PCM with
the standard library and handed to pygame.mixer. The whole module degrades
gracefully to silence if the mixer cannot be initialised.
"""
import array
import math
import random
import pygame

# musical note frequencies (Hz)
NOTE = {
    "C3": 130.81, "D3": 146.83, "E3": 164.81, "F3": 174.61, "G3": 196.00,
    "A3": 220.00, "B3": 246.94,
    "C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23, "G4": 392.00,
    "A4": 440.00, "B4": 493.88, "C5": 523.25, "D5": 587.33, "E5": 659.25,
}


class Audio:
    def __init__(self):
        self.enabled = False
        self.freq = 44100
        self.channels = 1
        self.sfx = {}
        self.music = None
        self.tracks = {}
        self.cur_track = None
        self.music_chan = None
        self.master = 0.8
        self.sfx_vol = 0.9
        self.music_vol = 0.45
        # background-music duck (0..1): the record player sets it while real
        # Spotify plays; every music set_volume multiplies it in (1.0 = no-op)
        self.music_duck = 1.0
        self._song_duck = False
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            init = pygame.mixer.get_init()
            if init:
                self.freq, _fmt, self.channels = init
                self.enabled = True
        except Exception:
            self.enabled = False
        if self.enabled:
            try:
                pygame.mixer.set_num_channels(16)
                self._build_sfx()
                self._build_music()
                import threading                  # soft variation: off the startup path
                threading.Thread(target=self._build_soft, daemon=True).start()
            except Exception:
                self.enabled = False

    # ---------- synthesis ----------
    def _env(self, i, n, attack, release):
        a = max(1, int(n * attack))
        r = max(1, int(n * release))
        if i < a:
            return i / a
        if i > n - r:
            return max(0.0, (n - i) / r)
        return 1.0

    def _render(self, dur, freqs, wave="sine", vol=0.5, attack=0.01,
               release=0.06, sweep=0.0, noise=0.0, vibrato=0.0):
        n = max(1, int(self.freq * dur))
        out = [0.0] * n
        twopi = 2 * math.pi
        for i in range(n):
            t = i / self.freq
            env = self._env(i, n, attack, release)
            val = 0.0
            for f in freqs:
                ff = f * (1.0 + sweep * (t / dur))
                if vibrato:
                    ff *= 1.0 + 0.01 * math.sin(twopi * vibrato * t)
                ph = ff * t
                if wave == "sine":
                    val += math.sin(twopi * ph)
                elif wave == "square":
                    val += 1.0 if math.sin(twopi * ph) >= 0 else -1.0
                elif wave == "saw":
                    val += 2.0 * (ph - math.floor(ph + 0.5))
                elif wave == "tri":
                    val += 2.0 * abs(2.0 * (ph - math.floor(ph + 0.5))) - 1.0
            val /= len(freqs)
            if noise:
                val = val * (1.0 - noise) + (random.random() * 2 - 1) * noise
            out[i] = val * env * vol
        return out

    def _to_sound(self, samples):
        buf = array.array("h")
        mx = 32000
        if self.channels == 1:
            for s in samples:
                buf.append(int(max(-1.0, min(1.0, s)) * mx))
        else:
            for s in samples:
                v = int(max(-1.0, min(1.0, s)) * mx)
                for _ in range(self.channels):
                    buf.append(v)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _seq(self, *parts):
        out = []
        for p in parts:
            out.extend(p)
        return out

    def _build_sfx(self):
        S = self.sfx
        S["ui_move"] = self._to_sound(self._render(0.05, [NOTE["A4"]], "square", 0.25))
        S["ui_select"] = self._to_sound(self._seq(
            self._render(0.06, [NOTE["E4"]], "square", 0.3),
            self._render(0.09, [NOTE["A4"]], "square", 0.3)))
        S["ui_toggle"] = self._to_sound(self._render(0.07, [NOTE["C5"]], "tri", 0.3))
        S["till"] = self._to_sound(self._render(0.16, [90], "saw", 0.45, noise=0.6, sweep=-0.4))
        S["water"] = self._to_sound(self._render(0.22, [600], "sine", 0.3, noise=0.85, sweep=0.5))
        S["plant"] = self._to_sound(self._render(0.10, [NOTE["G4"], NOTE["C5"]], "tri", 0.35))
        S["mine"] = self._to_sound(self._render(0.12, [320], "square", 0.4, noise=0.5, sweep=-0.3))
        S["chop"] = self._to_sound(self._render(0.14, [150], "saw", 0.45, noise=0.4, sweep=-0.5))
        S["sword"] = self._to_sound(self._render(0.16, [800], "saw", 0.35, noise=0.7, sweep=-0.7))
        S["hit"] = self._to_sound(self._render(0.16, [120, 200], "square", 0.5, noise=0.6, sweep=-0.4))
        S["harvest"] = self._to_sound(self._seq(
            self._render(0.08, [NOTE["C5"]], "sine", 0.4),
            self._render(0.12, [NOTE["E5"]], "sine", 0.4)))
        S["cast"] = self._to_sound(self._render(0.25, [500], "sine", 0.3, noise=0.8, sweep=-0.6))
        S["catch"] = self._to_sound(self._seq(
            self._render(0.08, [NOTE["E4"]], "tri", 0.4),
            self._render(0.08, [NOTE["G4"]], "tri", 0.4),
            self._render(0.14, [NOTE["C5"]], "tri", 0.4)))
        S["sell"] = self._to_sound(self._seq(
            self._render(0.07, [NOTE["C5"]], "square", 0.3),
            self._render(0.07, [NOTE["E5"]], "square", 0.3),
            self._render(0.12, [NOTE["G4"]], "square", 0.3)))
        S["sleep"] = self._to_sound(self._render(0.5, [NOTE["A3"]], "sine", 0.4, sweep=-0.4, release=0.4))
        S["warp"] = self._to_sound(self._render(0.35, [300], "sine", 0.35, noise=0.3, sweep=1.5))
        S["step"] = self._to_sound(self._render(0.05, [70], "sine", 0.16, noise=0.3, release=0.6))
        S["levelup"] = self._to_sound(self._seq(
            self._render(0.08, [NOTE["C4"]], "tri", 0.35),
            self._render(0.08, [NOTE["E4"]], "tri", 0.35),
            self._render(0.08, [NOTE["G4"]], "tri", 0.35),
            self._render(0.18, [NOTE["C5"]], "tri", 0.40)))
        self._build_sfx_extra()

    def _silence(self, dur):
        return [0.0] * max(1, int(self.freq * dur))

    def _rumble(self, dur, vol=0.6, smooth=0.985, attack=0.04, release=0.7):
        """Brown-ish noise (a leaky random walk) = soft low rumble (thunder)."""
        n = max(1, int(self.freq * dur))
        out = [0.0] * n
        v = 0.0
        rnd = random.random
        a = max(1, int(n * attack))
        r = max(1, int(n * release))
        for i in range(n):
            v = v * smooth + (rnd() - 0.5) * 0.35
            env = i / a if i < a else (max(0.0, (n - i) / r) if i > n - r else 1.0)
            out[i] = v * env * vol
        return out

    def _mix(self, *layers):
        m = max(len(l) for l in layers)
        out = [0.0] * m
        for l in layers:
            for i, v in enumerate(l):
                out[i] += v
        return out

    def _build_sfx_extra(self):
        """2026-09 SFX set (emotes, gifts, weather, rewards...). Short sounds only,
        so the extra startup cost stays ~0.1 s."""
        S = self.sfx
        C6, E6, G5, B5 = 1046.5, 1318.5, 783.99, 987.77
        R = self._render
        S["emote"] = self._to_sound(self._seq(
            R(0.06, [NOTE["A4"]], "sine", 0.32, sweep=0.5),
            R(0.09, [NOTE["E5"]], "sine", 0.30, release=0.5)))
        # per-emote flavours (coop_system falls back to "emote")
        S["emote_happy"] = self._to_sound(self._seq(
            R(0.05, [NOTE["C5"]], "tri", 0.3), R(0.09, [NOTE["G4"] * 2], "tri", 0.3, release=0.5)))
        S["emote_note"] = self._to_sound(self._seq(
            R(0.08, [NOTE["E5"]], "sine", 0.3), R(0.08, [NOTE["D5"]], "sine", 0.3),
            R(0.14, [NOTE["C5"]], "sine", 0.3, release=0.6)))
        S["emote_exclaim"] = self._to_sound(R(0.09, [NOTE["A4"] * 2], "square", 0.2,
                                              sweep=0.3, release=0.4))
        S["emote_question"] = self._to_sound(self._seq(
            R(0.07, [NOTE["E4"]], "tri", 0.3), R(0.12, [NOTE["A4"]], "tri", 0.3, sweep=0.2,
                                                 release=0.5)))
        S["emote_zzz"] = self._to_sound(R(0.35, [NOTE["C4"]], "sine", 0.26, sweep=-0.3,
                                          vibrato=4, attack=0.2, release=0.6))
        S["gift"] = self._to_sound(self._seq(
            R(0.07, [NOTE["C5"]], "tri", 0.32), R(0.07, [NOTE["E5"]], "tri", 0.32),
            R(0.07, [G5], "tri", 0.32), R(0.22, [C6, NOTE["E5"]], "sine", 0.30, release=0.6)))
        S["thunder"] = self._to_sound(self._mix(
            self._rumble(1.6, 0.9, smooth=0.992, attack=0.02, release=0.8),
            R(0.25, [70], "saw", 0.25, noise=0.8, sweep=-0.4, release=0.8)))
        S["achievement"] = self._to_sound(self._seq(
            R(0.08, [NOTE["C5"]], "square", 0.22), R(0.08, [NOTE["E5"]], "square", 0.22),
            R(0.08, [G5], "square", 0.22),
            R(0.34, [C6, G5, NOTE["E5"]], "tri", 0.36, release=0.6, vibrato=6)))
        S["coin"] = self._to_sound(self._seq(
            R(0.05, [B5], "square", 0.18), R(0.12, [E6], "square", 0.18, release=0.7)))
        S["forage"] = self._to_sound(self._seq(
            R(0.05, [420], "sine", 0.35, sweep=1.2, noise=0.15),
            R(0.07, [NOTE["A4"] * 2], "sine", 0.25, release=0.7)))
        S["unlock"] = self._to_sound(self._seq(
            R(0.09, [NOTE["G4"]], "tri", 0.34), R(0.09, [NOTE["C5"]], "tri", 0.34),
            R(0.09, [NOTE["E5"]], "tri", 0.34),
            R(0.45, [G5, NOTE["C5"], NOTE["E5"]], "tri", 0.38, release=0.55, vibrato=5)))
        S["page"] = self._to_sound(R(0.14, [2400], "sine", 0.22, noise=0.95, sweep=-0.6,
                                     attack=0.3, release=0.5))
        S["bell"] = self._to_sound(R(0.9, [NOTE["E5"], NOTE["E5"] * 2.01, NOTE["E5"] * 2.99],
                                     "sine", 0.40, attack=0.005, release=0.92))
        S["crit"] = self._to_sound(self._mix(
            R(0.14, [1400], "square", 0.28, noise=0.55, sweep=-0.8),
            R(0.2, [160, 240], "square", 0.35, noise=0.4, sweep=-0.5)))
        S["boss_roar"] = self._to_sound(self._mix(
            R(0.95, [82, 123], "saw", 0.55, noise=0.35, sweep=-0.35, vibrato=9,
              attack=0.08, release=0.5),
            self._rumble(0.95, 0.5, smooth=0.97, attack=0.1, release=0.6)))
        S["craft"] = self._to_sound(self._seq(
            R(0.05, [1250], "square", 0.25, noise=0.5, release=0.8), self._silence(0.06),
            R(0.05, [1500], "square", 0.25, noise=0.5, release=0.8), self._silence(0.04),
            R(0.16, [NOTE["C5"], NOTE["E5"]], "tri", 0.28, release=0.7)))
        S["splash_big"] = self._to_sound(self._mix(
            R(0.5, [900], "sine", 0.45, noise=0.9, sweep=-0.7, attack=0.02, release=0.8),
            R(0.2, [180], "sine", 0.35, sweep=-0.5)))
        S["error"] = self._to_sound(self._seq(
            R(0.08, [NOTE["E4"] / 2], "square", 0.22), self._silence(0.03),
            R(0.12, [NOTE["C4"] / 2], "square", 0.22, release=0.4)))
        # --- fix round: names other domains already call (they fall back / no-op)
        S["fireball"] = self._to_sound(self._mix(
            R(0.32, [260], "saw", 0.30, noise=0.75, sweep=-0.5, attack=0.05, release=0.6),
            R(0.32, [520], "sine", 0.18, sweep=0.6, release=0.7)))
        S["explosion"] = self._to_sound(self._mix(
            self._rumble(0.55, 0.9, smooth=0.975, attack=0.01, release=0.75),
            R(0.18, [110], "square", 0.35, noise=0.85, sweep=-0.6, release=0.7)))
        S["fuse"] = self._to_sound(R(0.28, [3200], "sine", 0.16, noise=0.97,
                                     attack=0.05, release=0.3))
        S["slam"] = self._to_sound(self._mix(
            self._rumble(0.45, 0.8, smooth=0.96, attack=0.005, release=0.8),
            R(0.12, [70, 95], "square", 0.4, noise=0.5, sweep=-0.5, release=0.7)))
        S["whoosh"] = self._to_sound(R(0.2, [900], "sine", 0.22, noise=0.95, sweep=-0.7,
                                       attack=0.35, release=0.5))
        S["blink"] = self._to_sound(self._seq(
            R(0.06, [NOTE["E5"] * 2], "sine", 0.22, sweep=-0.5),
            R(0.1, [NOTE["A4"]], "sine", 0.22, sweep=1.0, release=0.6)))
        S["ladder"] = self._to_sound(self._seq(
            R(0.05, [180], "square", 0.22, noise=0.4, release=0.7), self._silence(0.05),
            R(0.05, [150], "square", 0.22, noise=0.4, release=0.7), self._silence(0.05),
            R(0.12, [NOTE["C5"], NOTE["G4"]], "tri", 0.26, release=0.6)))
        S["siren"] = self._to_sound(self._seq(
            R(0.36, [520], "tri", 0.26, sweep=0.6, attack=0.15, release=0.2),
            R(0.36, [830], "tri", 0.26, sweep=-0.35, attack=0.05, release=0.5)))
        S["bite"] = self._to_sound(self._seq(
            R(0.05, [700], "sine", 0.34, noise=0.6, release=0.6),
            R(0.08, [NOTE["A4"] * 2], "sine", 0.3, sweep=0.3, release=0.6)))
        S["flutter"] = self._to_sound(self._seq(*[
            R(0.035, [1100 + 90 * i], "sine", 0.15, noise=0.9, release=0.8)
            for i in range(5)]))

    def _make_track(self, prog, beat=0.32, padvol=0.10, arpvol=0.16, arpwave="tri"):
        """Build a looping arpeggio+pad track from a chord progression."""
        samples = []
        for chord in prog:
            pad = self._render(beat * 4, [NOTE[chord[0]], NOTE[chord[2]]], "sine",
                               padvol, attack=0.2, release=0.4)
            arp = []
            for nm in chord + chord[::-1]:
                arp.extend(self._render(beat / 2, [NOTE[nm]], arpwave, arpvol,
                                        attack=0.02, release=0.12))
            m = max(len(pad), len(arp))
            block = [0.0] * m
            for i in range(len(pad)):
                block[i] += pad[i]
            for i in range(len(arp)):
                block[i] += arp[i]
            samples.extend(block)
        return self._to_sound(samples)

    def _build_soft(self):
        try:
            farm_soft = [["A3", "C4", "E4", "A4"], ["F3", "A3", "C4", "F4"],
                         ["C4", "E4", "G4", "C5"], ["G3", "B3", "D4", "G4"]]
            self.soft_tracks = {"farm": self._make_track(farm_soft, beat=0.42, padvol=0.12,
                                                         arpvol=0.10, arpwave="sine")}
        except Exception:
            self.soft_tracks = {}

    def _build_music(self):
        # one looping procedural theme per area, each voiced + paced to its mood.
        # farm/home/coop -- gentle, pastoral, cosy (the default loop)
        farm = [["C4", "E4", "G4", "C5"], ["G3", "B3", "D4", "G4"],
                ["A3", "C4", "E4", "A4"], ["F3", "A3", "C4", "F4"]]
        # town -- livelier, busier, brighter
        town = [["C4", "E4", "G4", "C5"], ["F3", "A3", "C4", "F4"],
                ["G3", "B3", "D4", "G4"], ["C4", "E4", "G4", "C5"]]
        # mine -- tense dungeon crawl: faster pulse, dark minor, gritty saw arp
        mine = [["A3", "C4", "E4", "A4"], ["E3", "G3", "B3", "E4"],
                ["F3", "A3", "C4", "F4"], ["E3", "G3", "B3", "E4"]]
        # temple -- calm & meditative: slow, warm sustained pad, soft low sine arp
        temple = [["F3", "A3", "C4", "F4"], ["C4", "E4", "G4", "C5"],
                  ["A3", "C4", "E4", "A4"], ["G3", "B3", "D4", "G4"]]
        # forest -- relaxed but alive, a touch mysterious: minor-leaning, flowing
        forest = [["A3", "C4", "E4", "A4"], ["E3", "G3", "B3", "E4"],
                  ["F3", "A3", "C4", "F4"], ["G3", "B3", "D4", "G4"]]
        # beach -- airy & breezy: light pad, bright high sine arp
        beach = [["C4", "E4", "G4", "C5"], ["G3", "B3", "D4", "G4"],
                 ["F3", "A3", "C4", "F4"], ["C4", "E4", "G4", "C5"]]
        # mist city -- dread & drive: E-Phrygian (the creeping E<->F half-step)
        # snapping into a diminished spike (B-D-F tritone); fast gritty saw arp
        # over a heavy low pad = scary AND thrilling, never sleepy
        mist = [["E3", "G3", "B3", "E4"], ["F3", "A3", "C4", "F4"],
                ["E3", "G3", "B3", "E4"], ["B3", "D4", "F4", "B4"]]
        self.music = self._make_track(farm)
        # softer farm variation for rainy days / late evenings (slower, a sine
        # music-box arp over a warmer pad). Synthesised on a background thread so
        # it adds nothing to startup; play_mood() uses it once it's ready.
        self.soft_tracks = {}
        self.tracks = {
            "farm": self.music, "home": self.music, "coop": self.music,
            "town":   self._make_track(town,   beat=0.26, padvol=0.10, arpvol=0.18, arpwave="tri"),
            "mine":   self._make_track(mine,   beat=0.24, padvol=0.13, arpvol=0.12, arpwave="saw"),
            "temple": self._make_track(temple, beat=0.50, padvol=0.15, arpvol=0.08, arpwave="sine"),
            "forest": self._make_track(forest, beat=0.30, padvol=0.10, arpvol=0.14, arpwave="tri"),
            "beach":  self._make_track(beach,  beat=0.30, padvol=0.07, arpvol=0.15, arpwave="sine"),
            "mistcity": self._make_track(mist, beat=0.21, padvol=0.14, arpvol=0.13, arpwave="saw"),
        }

    # ---------- playback ----------
    def play(self, name):
        if not self.enabled:
            return
        s = self.sfx.get(name)
        if s is None:
            return
        try:
            s.set_volume(self.master * self.sfx_vol)
            s.play()
        except Exception:
            pass

    def start_music(self):
        if not self.enabled or self.music is None:
            return
        try:
            self.music_chan = self.music.play(loops=-1)
            if self.music_chan:
                self.music_chan.set_volume(self.master * self.music_vol * self.music_duck)
        except Exception:
            pass

    def play_area(self, name):
        """Switch the looping background track to the one for this area."""
        if not self.enabled:
            return
        track = self.tracks.get(name) or self.music
        if track is None or track is self.cur_track:
            return
        try:
            if self.music_chan:
                self.music_chan.stop()
            self.music_chan = track.play(loops=-1)
            self.cur_track = track
            if self.music_chan:
                self.music_chan.set_volume(self.master * self.music_vol * self.music_duck)
        except Exception:
            pass

    def play_mood(self, area, soft=False):
        """Cross-fade between an area's normal loop and its soft variation
        (rain / night). No-op when that track is already playing."""
        if not self.enabled:
            return
        base = self.tracks.get(area) or self.music
        track = (getattr(self, "soft_tracks", {}).get(
            "farm" if base is self.music else area) if soft else None) or base
        if track is None or track is self.cur_track:
            return
        try:
            if self.music_chan:
                self.music_chan.fadeout(900)
            self.music_chan = track.play(loops=-1, fade_ms=1200)
            self.cur_track = track
            if self.music_chan:
                self.music_chan.set_volume(self.master * self.music_vol * self.music_duck)
        except Exception:
            pass

    # ---------- weather ambience (looping rain / storm / wind bed) ----------
    _AMB_VOL = {"rain": 0.32, "storm": 0.55, "wind": 0.30}

    def _ambience_sound(self, kind):
        """Seamless noise loops, generated lazily the first time they're needed
        (~50 ms each) so they cost nothing at startup."""
        cache = self.__dict__.setdefault("_amb_cache", {})
        if kind in cache:
            return cache[kind]
        dur = 2.0
        n = int(self.freq * dur)
        rnd = random.random
        out = [0.0] * n
        if kind in ("rain", "storm"):
            a = 0.30 if kind == "rain" else 0.20       # one-pole low-pass: softer hiss
            lo = 0.0
            rum = 0.0
            for i in range(n):
                w = rnd() * 2 - 1
                lo += (w - lo) * a
                v = lo * 0.9
                if rnd() < (0.0009 if kind == "rain" else 0.0016):
                    v += (rnd() * 2 - 1) * 0.6       # a fat drop / patter
                if kind == "storm":
                    rum = rum * 0.996 + (rnd() - 0.5) * 0.05
                    v += rum * 1.6
                out[i] = v * 0.8
        else:                                        # wind: brown noise + slow swell
            v = 0.0
            tw = 2 * math.pi / n
            for i in range(n):
                v = v * 0.992 + (rnd() - 0.5) * 0.12
                swell = 0.55 + 0.45 * math.sin(i * tw)     # one full cycle per loop
                out[i] = v * swell * 1.6
        # crossfade the tail into the head so the loop point never clicks
        f = int(self.freq * 0.08)
        for i in range(f):
            k = i / f
            out[i] = out[i] * k + out[n - f + i] * (1 - k)
        snd = self._to_sound(out[:n - f])
        cache[kind] = snd
        return snd

    def set_ambience(self, kind, scale=1.0):
        """Loop a weather bed (None / "rain" / "storm" / "wind"); ``scale`` dims
        it (e.g. rain heard from indoors). Cheap to call every frame."""
        if not self.enabled:
            return
        cur = getattr(self, "_amb_kind", None)
        if kind == cur:
            if kind and abs(scale - getattr(self, "_amb_scale", 1.0)) > 0.01:
                self._amb_scale = scale
                self._refresh_amb()
            return
        self._amb_kind = kind
        self._amb_scale = scale
        ch = getattr(self, "_amb_chan", None)
        if ch:
            try:
                ch.fadeout(1200)
            except Exception:
                pass
        self._amb_chan = None
        if not kind or kind not in self._AMB_VOL:
            return
        try:
            self._amb_chan = self._ambience_sound(kind).play(loops=-1, fade_ms=1500)
            self._refresh_amb()
        except Exception:
            self._amb_chan = None

    def _refresh_amb(self):
        ch = getattr(self, "_amb_chan", None)
        kind = getattr(self, "_amb_kind", None)
        if ch and kind:
            try:
                ch.set_volume(self.master * self.sfx_vol * self._AMB_VOL.get(kind, 0.3)
                              * getattr(self, "_amb_scale", 1.0))
            except Exception:
                pass

    def play_song(self, path):
        """Play a real audio file (the anniversary song) on the streaming music
        channel, ducking the procedural background loop so they don't clash. Used by
        the hidden beach cabana gift; pygame.mixer.music is otherwise unused (the
        area themes run on Sound channels), so the two never fight."""
        if not self.enabled:
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(min(1.0, self.master * 0.9))
            pygame.mixer.music.play(loops=-1)
            self._song_duck = True
            if self.music_chan:
                self.music_chan.set_volume(self.master * self.music_vol * 0.10 * self.music_duck)
        except Exception:
            pass

    def stop_song(self):
        """Stop the streaming song (if any) and restore the background loop volume."""
        if not self.enabled:
            return
        self._song_duck = False
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        if self.music_chan:
            try:
                self.music_chan.set_volume(self.master * self.music_vol * self.music_duck)
            except Exception:
                pass

    def _refresh_music_volume(self):
        if self.music_chan:
            try:
                self.music_chan.set_volume(self.master * self.music_vol * self.music_duck)
            except Exception:
                pass

    def set_music_duck(self, f):
        """Scale the background loop (never sfx / ambience) by ``f`` (0..1) --
        the record player ducks it while real Spotify is playing. Keeps the
        anniversary song's own 10% duck if that song is on."""
        f = max(0.0, min(1.0, float(f)))
        if abs(f - self.music_duck) < 1e-4:
            return
        self.music_duck = f
        if self.music_chan:
            try:
                k = 0.10 if self._song_duck else 1.0
                self.music_chan.set_volume(self.master * self.music_vol * k * f)
            except Exception:
                pass

    def set_master(self, v):
        self.master = max(0.0, min(1.0, v))
        self._refresh_music_volume()
        self._refresh_amb()

    def set_sfx(self, v):
        self.sfx_vol = max(0.0, min(1.0, v))
        self._refresh_amb()

    def set_music(self, v):
        self.music_vol = max(0.0, min(1.0, v))
        self._refresh_music_volume()
