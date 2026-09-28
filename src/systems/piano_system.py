"""A really playable piano (state "piano").

Owner: Home. Glue between the game and ``piano.PianoScreen`` / ``PianoSynth``
(src/piano.py): opening it (energy, like the other furniture), the song
book's once-a-day reward, notes floating off the piano in the room, and the
LAN relays so the other farmer hears the music too.

Contract (called from systems/home_system.py):
  _piano_open(idx, piano, seated=False, client=False)
      open the playable piano for player ``idx`` at the Placed ``piano`` piece.
      ``seated``: the farmer is already sitting at a bench in front of it
      (Esc leaves them seated). ``client``: running on the LAN client.

LAN (the host owns energy and the song-reward days):
  client -> host   menu {"m": "piano", "n": midi, "gx", "gy"}   note on
                   menu {"m": "piano", "off": midi}             note off
                   menu {"m": "piano", "op": "open" | "song", ...}
  host -> client   fx "piano" n=midi gx gy  /  fx "piano" off=midi
                   fx "piano" op="open"                         P1 sat down
A farmer only hears notes while standing in the house. Incoming note numbers
are clamped to the piano's range, junk is ignored and bursts are rate-limited.
The client's "open" seats P2 on the host, on the free bench right at that
piano (as Action does locally); the SIT snapshot brings the seat back and the
client's screen follows it (Esc then leaves P2 sitting). The log only says
"sits down" when they really did.

Baking: walking into a house with a piano bakes every key on the synth's
daemon thread (``_on_area_enter_piano``, once per session -- on the real
Audio even inside a partner's area context). An "open" from the partner, or
a partner's note we haven't baked yet (walked in mid-song: from that note
outwards), prewarms this machine's synth too, only when we're in the house.

The song-finished heart burst goes into the room right away only where the
room is live (LAN client, or state "play"); under the host's / local piano
page the room is frozen, so one burst waits for the lid to close.

The background loop is hushed while the lid is open. The level is always
worked out from Audio's own numbers (master x music x the record player's
Spotify duck x the anniversary song's hush), never from a remembered volume,
so a duck that changes meanwhile -- or a reset -- can't leave it wrong.
"""
import random
import time

from ..settings import TILE, MAX_ENERGY, AREA_HOME

SONG_REWARD = 20        # energy for finishing a song (once per song, per farmer, per day)
_RATE = 20.0            # partner notes per second (sustained) ...
_BURST = 30.0           # ... with this much burst allowance (fast chords, glissandi)
_HUSH = 0.25            # the background loop's share while the piano is open


class PianoMixin:
    """Open the piano screen, reward songs, relay notes between farmers."""

    # ------------------------------------------------------------ lifecycle
    def _on_reset_piano(self):
        if getattr(self, "_piano_hushed", False):
            self._piano_duck(False)     # e.g. the host quit while we were playing
        self.piano_ui = None
        self._piano_songs = {}          # "pidx:song" -> [year, season, day] last rewarded
        self._piano_rate = {}           # lane -> (tokens, last time)
        self._piano_hushed = False      # the background loop is ducked for us
        self._piano_hearts = None       # pidx: a song was finished in a frozen room

    def _on_save_piano(self):
        return {"piano_songs": {k: list(v) for k, v in self._piano_songs.items()}}

    def _on_load_piano(self, d):
        self._piano_songs = {}
        raw = d.get("piano_songs")
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(k, str) and isinstance(v, (list, tuple)) and len(v) == 3:
                    try:
                        self._piano_songs[k] = [int(x) for x in v]
                    except (TypeError, ValueError):
                        pass

    def _on_area_enter_piano(self):
        """Walked into a house with a piano: bake every key now, once per
        session, on the synth's daemon thread -- long before anyone sits
        down, so the first chord never waits on the baking. (Inside a
        partner's area context ``self.audio`` is a no-op sink: the synth
        lives on the real Audio.)"""
        if self.world.current != AREA_HOME:
            return
        if not any(q.kind == "piano" for q in self.world.home_furniture):
            return
        from .. import piano as PN
        try:
            PN.prewarm_all(getattr(self.audio, "_real", None) or self.audio)
        except Exception:
            pass

    # ------------------------------------------------------------ open / close
    def _piano_open(self, idx, piano, seated=False, client=False):
        p = self.players[idx]
        if getattr(self, "net_mode", None) == "host" and idx == 1:
            self._home_piano(p, piano)          # the client opens its own keyboard
            return
        from .. import piano as PN
        if client:
            # the HOST seats P2 on the bench (the snapshot brings the seat
            # back); till then, a free bench by the piano is a safe guess
            if not seated:
                bench_for = getattr(self, "_home_bench_for", None)
                seated = bool(bench_for and bench_for(piano, p) is not None)
            self._net_send_menu({"m": "piano", "op": "open", "gx": piano.gx, "gy": piano.gy})
            self.ui.log(f"{p.name} sits down at the piano" if seated
                        else f"{p.name} opens the piano")
        else:
            self._piano_energy(idx, piano, seated=seated)
            if getattr(self, "net_mode", None) == "host":
                self._net_send_fx("piano", op="open")   # the client warms up its synth
        old = getattr(self, "piano_ui", None)
        if old is not None:
            old.release_all()                   # opened over itself: let its keys go
        self.piano_ui = PN.PianoScreen(self, idx, piano, seated=seated, client=client)
        self.state = "piano"
        self.audio.play("ui_toggle")
        self._piano_duck(True)

    def _piano_energy(self, idx, piano, seated=True):
        from .actions_system import FURN_ACTION
        verb, gain = FURN_ACTION.get("piano", ("play a tune on the piano", 18))
        gain = int(gain * getattr(piano, "level", 1))
        p = self.players[idx]
        p.energy = min(MAX_ENERGY, p.energy + gain)
        if seated:
            self.ui.log(f"{p.name} sits down to {verb} (+{gain} energy)")
        else:                                   # (no free bench: plays standing up)
            self.ui.log(f"{p.name} steps up to {verb} (+{gain} energy)")

    def _piano_seat(self, idx, piano):
        """Seat farmer ``idx`` on the free bench right at ``piano``, facing
        the keys, like Action does locally (``HomeMixin._home_play_piano``).
        True = they sit at this piano now."""
        p = self.players[idx]
        by = getattr(self, "_home_piano_by", None)
        sit = getattr(p, "sitting", None)
        if sit and by:
            try:
                if by(sit[1], sit[2])[0] is piano:
                    return True
            except Exception:
                pass
        bench_for = getattr(self, "_home_bench_for", None)
        if self.world.current != AREA_HOME or bench_for is None:
            return False
        try:                                    # a stale "open" from across the room
            from .. import furniture as F      # must not teleport anyone
            fw, fh = F.footprint(piano.kind, piano.rot)
            cx = (piano.gx + getattr(piano, "ox", 0.0) + fw / 2) * TILE
            cy = (piano.gy + getattr(piano, "oy", 0.0) + fh / 2) * TILE
            if (p.x - cx) ** 2 + (p.y - cy) ** 2 > (3.5 * TILE) ** 2:
                return False
        except Exception:
            pass
        bench = bench_for(piano, p)
        if bench is None:
            return False
        self.interact_furniture(p, bench)       # sits + turns to the keys
        sit = getattr(p, "sitting", None)
        return bool(sit) and sit[0] is bench

    def _piano_closed(self, screen):
        if getattr(self, "piano_ui", None) is screen:
            self.piano_ui = None
        if self.state == "piano":
            self.state = "play"
        self._piano_duck(False)
        pidx, self._piano_hearts = getattr(self, "_piano_hearts", None), None
        if pidx is not None:
            self._piano_heart_burst(pidx)       # the song's hearts, now the room moves again

    @staticmethod
    def _piano_loop_level(a):
        """The background loop's volume as Audio itself would set it right now
        (the record player's duck and the anniversary song's hush included)."""
        k = 0.10 if getattr(a, "_song_duck", False) else 1.0
        return (getattr(a, "master", 0.8) * getattr(a, "music_vol", 0.45)
                * getattr(a, "music_duck", 1.0) * k)

    def _piano_duck(self, on):
        """Hush the background loop while playing (its arpeggios would clash
        with yours); give it back at Audio's current level when the lid closes.
        Called every frame while open too: if the record player's Spotify duck
        moves meanwhile, the hush follows it instead of being overwritten."""
        self._piano_hushed = bool(on)
        a = getattr(self, "audio", None)
        a = getattr(a, "_real", None) or a              # an area-context sink
        ch = getattr(a, "music_chan", None)
        if ch is None:
            return
        try:
            want = self._piano_loop_level(a) * (_HUSH if on else 1.0)
            if not on or abs(ch.get_volume() - want) > 0.01:   # (volumes step by 1/128)
                ch.set_volume(want)
        except Exception:
            pass

    def _on_update_piano(self, dt):
        """Safety net: left the piano some other way (a state reset)? Un-duck."""
        if self._piano_hushed and self.state != "piano":
            self._piano_duck(False)

    _on_client_update_piano = _on_update_piano

    # ------------------------------------------------------------ screen callbacks
    def _piano_note(self, screen, midi, on):
        """The screen struck / released ``midi`` (its own sound already plays):
        a note floats off the piano in the room and the partner hears it."""
        piano = screen.piece
        if screen.client:
            if on and not self._piano_rate_ok("out"):
                return
            msg = {"m": "piano", "n": midi, "gx": piano.gx, "gy": piano.gy} if on else \
                {"m": "piano", "off": midi}
            self._net_send_menu(msg)
        elif getattr(self, "net_mode", None) == "host":
            if on and self._piano_rate_ok("out"):
                self._net_send_fx("piano", n=midi, gx=piano.gx, gy=piano.gy)
            elif not on:
                self._net_send_fx("piano", off=midi)
        if on:
            self._piano_world_note(piano, midi)

    def _piano_song_done(self, screen, sid):
        """A song from the book was played to the end. Returns the reward line
        for the screen's banner ("" when it was already rewarded today)."""
        from .. import piano as PN
        p = self.players[screen.pidx]
        title = PN.song_title(sid)
        if screen.client:
            self._net_send_menu({"m": "piano", "op": "song", "song": sid})
            fresh = self._piano_mark(screen.pidx, sid)      # the host decides for real
            reward = f"+{SONG_REWARD} energy" if fresh else ""
        else:
            reward = self._piano_reward(screen.pidx, sid)
        icon = None
        try:
            from .coop_system import _misc_icon
            icon = _misc_icon("heart")
        except Exception:
            pass
        toast = getattr(self, "toast", None)
        if toast:
            try:
                toast("Bravo!", f"{p.name} played {title}" + (f"  {reward}" if reward else ""),
                      icon=icon, color=(255, 170, 200))
            except Exception:
                pass
        if getattr(self, "net_mode", None) == "client" or self.state == "play":
            self._piano_heart_burst(screen.pidx)
        else:
            self._piano_hearts = screen.pidx    # frozen under the page: one burst on close
        return reward

    def _piano_heart_burst(self, pidx):
        """Hearts over the pianist -- at the bench when seated (the iso room
        draws a sitter at the seat point, not at their standing spot)."""
        hb = getattr(self.parts, "heart_burst", None)
        if not hb or self.world.current != AREA_HOME:
            return
        p = self.players[pidx]
        x, y = p.x, p.y
        sit = getattr(p, "sitting", None)
        try:
            if sit:
                x, y = float(sit[1]) * TILE, float(sit[2]) * TILE
        except (TypeError, ValueError, IndexError):
            pass
        hb(x, y - 20, n=12)

    def _piano_mark(self, pidx, sid):
        """Record today's reward for (farmer, song). True = first time today."""
        today = [self.time.year, self.time.season_idx, self.time.day]
        key = f"{pidx}:{sid}"
        if self._piano_songs.get(key) == today:
            return False
        self._piano_songs[key] = today
        return True

    def _piano_reward(self, pidx, sid):
        from .. import piano as PN
        p = self.players[pidx]
        title = PN.song_title(sid)
        if not self._piano_mark(pidx, sid):
            self.ui.log(f"{p.name} plays {title} once more - lovely!")
            return ""
        p.energy = min(MAX_ENERGY, p.energy + SONG_REWARD)
        self.ui.log(f"{p.name} played {title} on the piano! (+{SONG_REWARD} energy)")
        self.emit("piano_song", p=p, song=sid)
        return f"+{SONG_REWARD} energy"

    # ------------------------------------------------------------ sound + room fx
    def _piano_can_hear(self):
        """Only a farmer standing in the house hears the piano."""
        va = getattr(self, "view_area", None)
        try:
            area = va() if va else self.world.current
        except Exception:
            area = self.world.current
        return area == AREA_HOME

    def _piano_piece(self, gx, gy):
        pianos = [q for q in self.world.home_furniture if q.kind == "piano"]
        return next((q for q in pianos if q.gx == gx and q.gy == gy),
                    pianos[0] if pianos else None)

    def _piano_world_note(self, piano, midi):
        """A little note floats up off the piano lid in the iso room."""
        if piano is None or self.world.current != AREA_HOME:
            return
        if getattr(self, "net_mode", None) != "client" and self.state != "play":
            return      # this room is frozen under a full-screen page: notes would pile up
        from .. import furniture as F
        from .. import piano as PN
        try:
            fw, fh = F.footprint(piano.kind, piano.rot)
        except Exception:
            fw, fh = 2, 1
        wx = (piano.gx + getattr(piano, "ox", 0.0) + fw / 2) * TILE + random.uniform(-10, 10)
        wy = (piano.gy + getattr(piano, "oy", 0.0) + fh / 2) * TILE
        items = getattr(self.parts, "items", None)
        n0 = len(items) if isinstance(items, list) else 0
        col = PN.pitch_color(midi)
        nf = getattr(self.parts, "note_float", None)
        if nf:
            nf(wx, wy, color=col)
        else:
            self.parts.sparkle(wx, wy, n=2, color=col)
        if isinstance(items, list):
            for q in items[n0:]:
                q.y -= 44                      # up off the floor, over the lid

    def _piano_prewarm(self, around=None):
        """The partner sat down at the piano (or played a note we haven't
        baked: ``around``): bake its notes on this machine too (the synth's
        daemon thread), so their chords -- a fresh bass chord bakes for
        ~60-80 ms -- never stall our frames. Only when we can hear it: a
        farmer out in the fields never will. (Usually a no-op by now:
        walking into the house already baked the lot.)"""
        if not self._piano_can_hear():
            return
        from .. import piano as PN
        try:
            PN.prewarm_listener(self.audio, around)
        except Exception:
            pass

    def _piano_hear(self, midi, on, piano=None):
        """A partner's note: play it here (if we're in the house) + room fx."""
        from .. import piano as PN
        if on:
            if self._piano_can_hear():
                syn = PN.synth(self.audio)
                cold = midi not in syn.cache
                syn.note_on(("remote", midi), midi, random.uniform(0.85, 0.95))
                if cold:        # walked in mid-song: warm the rest, from THIS note out
                    self._piano_prewarm(around=midi)
            self._piano_world_note(piano, midi)
        else:
            PN.synth(self.audio).note_off(("remote", midi))

    def _piano_rate_ok(self, lane):
        now = time.monotonic()
        tok, last = self._piano_rate.get(lane, (_BURST, now))
        tok = min(_BURST, tok + (now - last) * _RATE)
        ok = tok >= 1.0
        self._piano_rate[lane] = (tok - 1.0 if ok else tok, now)
        return ok

    def _piano_remote(self, m, lane):
        """Shared by host (menu) and client (fx): a note on / off message."""
        from .. import piano as PN
        if "n" in m:
            midi = PN.clamp_midi(m.get("n"))
            if midi is None or not self._piano_rate_ok(lane):
                return
            self._piano_hear(midi, True, self._piano_piece(m.get("gx"), m.get("gy")))
        elif "off" in m:
            midi = PN.clamp_midi(m.get("off"))
            if midi is not None:
                self._piano_hear(midi, False)

    # ------------------------------------------------------------ LAN
    def _net_menu_piano(self, mm, m):
        """Host: Player 2 plays the piano on the client machine."""
        if mm != "piano":
            return False
        from .. import piano as PN
        op = m.get("op")
        if op == "open":
            piano = self._piano_piece(m.get("gx"), m.get("gy"))
            if piano is not None:
                # P2 sits down on the bench, facing the keys, like Action does
                # locally -- the SIT snapshot carries the seat to the client
                seated = self._piano_seat(1, piano)
                self._piano_energy(1, piano, seated=seated)   # rides back in the snapshot
                self._piano_prewarm()                 # P1 is about to hear them play
        elif op == "song":
            sid = m.get("song")
            if isinstance(sid, str) and sid in PN.SONG_IDS:
                reward = self._piano_reward(1, sid)
                if reward:
                    self._net_toast(f"{PN.song_title(sid)}: {reward}!")
        else:
            self._piano_remote(m, "in")
        return True

    def _net_fx_piano(self, m):
        """Client: Player 1 plays the piano on the host machine."""
        if m.get("kind") != "piano":
            return False
        if m.get("op") == "open":
            self._piano_prewarm()                     # P1 sat down: warm our synth up
        else:
            self._piano_remote(m, "fx")
        return True

    # ------------------------------------------------------------ custom state
    def _state_event_piano(self, e):
        ui = getattr(self, "piano_ui", None)
        if ui is None:
            self.state = "play"
            return
        ui.handle_event(e)

    def _state_update_piano(self, dt):
        ui = getattr(self, "piano_ui", None)
        if ui is None:
            self.state = "play"
            return
        if self._piano_hushed:
            self._piano_duck(True)          # keep the hush if the Spotify duck moved
        ui.update(dt)

    def _state_draw_piano(self):
        ui = getattr(self, "piano_ui", None)
        if ui is not None:
            ui.draw(self.screen)
