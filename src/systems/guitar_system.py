"""A really playable guitar (state "guitar").

Owner: Guitar (2026-09-28). Glue between the game and ``guitar.GuitarScreen``
/ ``GuitarSynth`` (src/guitar.py): picking the guitar up off its stand
(energy, once a day per farmer), the song book's once-a-day reward, notes
floating off the stand in the room, and the LAN relays so the other farmer
hears the strums too.

Seams (one hand-off each):
  host / local : ``_interact_early_42_guitar`` (a hook -- no seam edit): Action
                 facing a ``guitar_stand`` in the house opens the guitar.
  LAN client   : ``HomeMixin._home_client_interact`` -> ``_guitar_client_interact``.

LAN (the host owns energy and the song-reward days):
  client -> host   menu {"m": "guitar", "c": chord, "d": 1 | 0, "gx", "gy"}  a strum
                   menu {"m": "guitar", "op": "open" | "song", ...}
  host -> client   fx "guitar" c=chord d=1|0 gx gy   /   fx "guitar" op="open"
Whole strums travel (a chord id + its direction), never single strings: the
listener's synth plays its own humanised strum. A farmer only hears it while
standing in the house; unknown chord ids are ignored and bursts are rate-
limited. Walking into a house with a guitar bakes its strings on the synth's
daemon thread (``_on_area_enter_guitar``); the partner picking the guitar up
does the same on this machine.

The background loop is hushed while the guitar is out (same rule as the
piano: always recomputed from Audio's own numbers).
"""
import random
import time

from ..settings import TILE, MAX_ENERGY, AREA_HOME

SONG_REWARD = 20        # energy for finishing a song (once per song, per farmer, per day)
_RATE = 8.0             # partner strums per second (sustained) ...
_BURST = 12.0           # ... with this much burst allowance
_HUSH = 0.25            # the background loop's share while the guitar is out


class GuitarMixin:
    """Open the guitar screen, reward songs, relay strums between farmers."""

    # ------------------------------------------------------------ lifecycle
    def _on_reset_guitar(self):
        if getattr(self, "_guitar_hushed", False):
            self._guitar_duck(False)
        self.guitar_ui = None
        self._guitar_songs = {}         # "pidx:song" -> [year, season, day] last rewarded
        self._guitar_days = {}          # "pidx" -> [year, season, day] of the day's energy
        self._guitar_rate = {}
        self._guitar_hushed = False
        self._guitar_hearts = None

    def _on_save_guitar(self):
        return {"guitar_songs": {k: list(v) for k, v in self._guitar_songs.items()},
                "guitar_days": {k: list(v) for k, v in self._guitar_days.items()}}

    def _on_load_guitar(self, d):
        self._guitar_songs = self._guitar_day_map(d.get("guitar_songs"))
        self._guitar_days = self._guitar_day_map(d.get("guitar_days"))

    @staticmethod
    def _guitar_day_map(raw):
        out = {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(k, str) and isinstance(v, (list, tuple)) and len(v) == 3:
                    try:
                        out[k] = [int(x) for x in v]
                    except (TypeError, ValueError):
                        pass
        return out

    def _on_area_enter_guitar(self):
        """Walked into a house with a guitar: bake its strings now, once per
        session, on the synth's daemon thread."""
        if self.world.current != AREA_HOME:
            return
        if not any(q.kind == "guitar_stand" for q in self.world.home_furniture):
            return
        from .. import guitar as GT
        try:
            GT.prewarm_all(getattr(self.audio, "_real", None) or self.audio)
        except Exception:
            pass

    def _guitar_today(self):
        return [self.time.year, self.time.season_idx, self.time.day]

    # ------------------------------------------------------------ open / close
    def _guitar_facing(self, p):
        facing = self.world.furniture_at(*p.target_tile())
        pgx, pgy = int(p.x // TILE), int(p.y // TILE)
        return facing or self.world.furniture_at(pgx, pgy)

    def _interact_early_42_guitar(self, idx, p):
        if self.world.current != AREA_HOME or getattr(p, "sitting", None):
            return False
        fr = self._guitar_facing(p)
        if fr is None or fr.kind != "guitar_stand":
            return False
        if getattr(self, "net_mode", None) == "host" and idx == 1:
            return False                        # the client opens its own guitar
        self._guitar_open(idx, fr)
        return True

    def _guitar_client_interact(self, p, fr):
        """LAN client: the guitar opens right here. True = handled."""
        if fr.kind != "guitar_stand":
            return False
        self._guitar_open(1, fr, client=True)
        return True

    def _guitar_open(self, idx, stand, client=False):
        from .. import guitar as GT
        p = self.players[idx]
        if client:
            self._net_send_menu({"m": "guitar", "op": "open", "gx": stand.gx, "gy": stand.gy})
            self.ui.log(f"{p.name} picks up the guitar")
        else:
            self._guitar_energy(idx, stand)
            if getattr(self, "net_mode", None) == "host":
                self._net_send_fx("guitar", op="open")    # the client warms up its strings
        old = getattr(self, "guitar_ui", None)
        if old is not None:
            old.syn.release_all(("me",))
        self.guitar_ui = GT.GuitarScreen(self, idx, stand, client=client)
        self.state = "guitar"
        self.audio.play("ui_toggle")
        self._guitar_duck(True)

    def _guitar_energy(self, idx, stand):
        """Picking the guitar up lifts the mood -- once a day per farmer."""
        from .actions_system import FURN_ACTION
        verb, gain = FURN_ACTION.get("guitar_stand", ("strum a little song", 14))
        gain = int(gain * getattr(stand, "level", 1))
        p = self.players[idx]
        key, today = str(idx), self._guitar_today()
        if self._guitar_days.get(key) == today:
            self.ui.log(f"{p.name} picks up the guitar again")
            return False
        self._guitar_days[key] = today
        p.energy = min(MAX_ENERGY, p.energy + gain)
        self.ui.log(f"{p.name} picks up the guitar to {verb} (+{gain} energy)")
        return True

    def _guitar_closed(self, screen):
        if getattr(self, "guitar_ui", None) is screen:
            self.guitar_ui = None
        if self.state == "guitar":
            self.state = "play"
        self._guitar_duck(False)
        pidx, self._guitar_hearts = getattr(self, "_guitar_hearts", None), None
        if pidx is not None:
            self._guitar_heart_burst(pidx)
        self.audio.play("ui_toggle")

    @staticmethod
    def _guitar_loop_level(a):
        k = 0.10 if getattr(a, "_song_duck", False) else 1.0
        return (getattr(a, "master", 0.8) * getattr(a, "music_vol", 0.45)
                * getattr(a, "music_duck", 1.0) * k)

    def _guitar_duck(self, on):
        """Hush the background loop while playing; give it back at Audio's
        current level when the guitar goes back on its stand."""
        self._guitar_hushed = bool(on)
        a = getattr(self, "audio", None)
        a = getattr(a, "_real", None) or a
        ch = getattr(a, "music_chan", None)
        if ch is None:
            return
        try:
            want = self._guitar_loop_level(a) * (_HUSH if on else 1.0)
            if not on or abs(ch.get_volume() - want) > 0.01:
                ch.set_volume(want)
        except Exception:
            pass

    def _on_update_guitar(self, dt):
        """Safety net: left the guitar some other way (a state reset)? Un-duck."""
        if self._guitar_hushed and self.state != "guitar":
            self._guitar_duck(False)

    _on_client_update_guitar = _on_update_guitar

    # ------------------------------------------------------------ screen callbacks
    def _guitar_strum(self, screen, cid, down):
        """The screen strummed ``cid`` (its own sound already plays): a note
        floats off the stand in the room and the partner hears it."""
        stand = screen.piece
        d = 1 if down else 0
        if screen.client:
            if self._guitar_rate_ok("out"):
                self._net_send_menu({"m": "guitar", "c": cid, "d": d,
                                     "gx": stand.gx, "gy": stand.gy})
        elif getattr(self, "net_mode", None) == "host":
            if self._guitar_rate_ok("out"):
                self._net_send_fx("guitar", c=cid, d=d, gx=stand.gx, gy=stand.gy)
        self._guitar_world_note(stand, cid)

    def _guitar_song_done(self, screen, sid):
        """A song from the book was strummed to the end. Returns the reward
        line for the screen's banner ("" when it was already rewarded today)."""
        from .. import guitar as GT
        p = self.players[screen.pidx]
        title = GT.song_title(sid)
        if screen.client:
            self._net_send_menu({"m": "guitar", "op": "song", "song": sid})
            fresh = self._guitar_mark(screen.pidx, sid)     # the host decides for real
            reward = f"+{SONG_REWARD} energy" if fresh else ""
        else:
            reward = self._guitar_reward(screen.pidx, sid)
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
            self._guitar_heart_burst(screen.pidx)
        else:
            self._guitar_hearts = screen.pidx       # frozen under the page: one burst on close
        return reward

    def _guitar_heart_burst(self, pidx):
        hb = getattr(self.parts, "heart_burst", None)
        if not hb or self.world.current != AREA_HOME:
            return
        p = self.players[pidx]
        hb(p.x, p.y - 20, n=12)

    def _guitar_mark(self, pidx, sid):
        today = self._guitar_today()
        key = f"{pidx}:{sid}"
        if self._guitar_songs.get(key) == today:
            return False
        self._guitar_songs[key] = today
        return True

    def _guitar_reward(self, pidx, sid):
        from .. import guitar as GT
        p = self.players[pidx]
        title = GT.song_title(sid)
        if not self._guitar_mark(pidx, sid):
            self.ui.log(f"{p.name} strums {title} once more - lovely!")
            return ""
        p.energy = min(MAX_ENERGY, p.energy + SONG_REWARD)
        self.ui.log(f"{p.name} played {title} on the guitar! (+{SONG_REWARD} energy)")
        self.emit("guitar_song", p=p, song=sid)
        return f"+{SONG_REWARD} energy"

    # ------------------------------------------------------------ sound + room fx
    def _guitar_can_hear(self):
        va = getattr(self, "view_area", None)
        try:
            area = va() if va else self.world.current
        except Exception:
            area = self.world.current
        return area == AREA_HOME

    def _guitar_piece(self, gx, gy):
        stands = [q for q in self.world.home_furniture if q.kind == "guitar_stand"]
        return next((q for q in stands if q.gx == gx and q.gy == gy),
                    stands[0] if stands else None)

    def _guitar_world_note(self, stand, cid):
        """A little note floats up off the guitar on its stand."""
        if stand is None or self.world.current != AREA_HOME:
            return
        if getattr(self, "net_mode", None) != "client" and self.state != "play":
            return      # the room is frozen under a full-screen page: notes would pile up
        from .. import furniture as F
        from .. import guitar as GT
        try:
            fw, fh = F.footprint(stand.kind, stand.rot)
        except Exception:
            fw, fh = 1, 1
        wx = (stand.gx + getattr(stand, "ox", 0.0) + fw / 2) * TILE + random.uniform(-8, 8)
        wy = (stand.gy + getattr(stand, "oy", 0.0) + fh / 2) * TILE
        items = getattr(self.parts, "items", None)
        n0 = len(items) if isinstance(items, list) else 0
        col = GT.chord_color(cid) if cid in GT.SHAPES else (200, 160, 90)
        nf = getattr(self.parts, "note_float", None)
        if nf:
            nf(wx, wy, color=col)
        else:
            self.parts.sparkle(wx, wy, n=2, color=col)
        if isinstance(items, list):
            for q in items[n0:]:
                q.y -= 40                      # up off the floor, over the guitar

    def _guitar_prewarm(self):
        """The partner picked up the guitar: bake its strings here too."""
        if not self._guitar_can_hear():
            return
        from .. import guitar as GT
        try:
            GT.prewarm_all(self.audio)
        except Exception:
            pass

    def _guitar_hear(self, cid, down, stand=None):
        """A partner's strum: play it here (if we're in the house) + room fx."""
        from .. import guitar as GT
        if self._guitar_can_hear():
            syn = GT.synth(self.audio)
            midis = GT.voicing(cid)
            cold = any(m is not None and not syn.baked(m) for m in midis)
            syn.strum(("remote",), midis, GT.plan_strum(midis, down, random.uniform(0.8, 0.9)))
            if cold:
                self._guitar_prewarm()
        self._guitar_world_note(stand, cid)

    def _guitar_rate_ok(self, lane):
        now = time.monotonic()
        tok, last = self._guitar_rate.get(lane, (_BURST, now))
        tok = min(_BURST, tok + (now - last) * _RATE)
        ok = tok >= 1.0
        self._guitar_rate[lane] = (tok - 1.0 if ok else tok, now)
        return ok

    def _guitar_remote(self, m, lane):
        """Shared by host (menu) and client (fx): a strum message."""
        from .. import guitar as GT
        cid = GT.clean_chord(m.get("c"))
        if cid is None or not self._guitar_rate_ok(lane):
            return
        d = m.get("d", 1)
        down = not (d == 0 or d is False)
        self._guitar_hear(cid, down, self._guitar_piece(m.get("gx"), m.get("gy")))

    # ------------------------------------------------------------ LAN
    def _net_menu_guitar(self, mm, m):
        """Host: Player 2 plays the guitar on the client machine."""
        if mm != "guitar":
            return False
        from .. import guitar as GT
        op = m.get("op")
        if op == "open":
            stand = self._guitar_piece(m.get("gx"), m.get("gy"))
            if stand is not None:
                self._guitar_energy(1, stand)             # rides back in the snapshot
                self._guitar_prewarm()                    # P1 is about to hear them play
        elif op == "song":
            sid = m.get("song")
            if isinstance(sid, str) and sid in GT.SONG_IDS:
                reward = self._guitar_reward(1, sid)
                if reward:
                    self._net_toast(f"{GT.song_title(sid)}: {reward}!")
        elif "c" in m:
            self._guitar_remote(m, "in")
        return True

    def _net_fx_guitar(self, m):
        """Client: Player 1 plays the guitar on the host machine."""
        if m.get("kind") != "guitar":
            return False
        if m.get("op") == "open":
            self._guitar_prewarm()
        else:
            self._guitar_remote(m, "fx")
        return True

    # ------------------------------------------------------------ custom state
    def _state_event_guitar(self, e):
        ui = getattr(self, "guitar_ui", None)
        if ui is None:
            self.state = "play"
            return
        ui.handle_event(e)

    def _state_update_guitar(self, dt):
        ui = getattr(self, "guitar_ui", None)
        if ui is None:
            self.state = "play"
            return
        if self._guitar_hushed:
            self._guitar_duck(True)
        ui.update(dt)

    def _state_draw_guitar(self):
        ui = getattr(self, "guitar_ui", None)
        if ui is not None:
            ui.draw(self.screen)
