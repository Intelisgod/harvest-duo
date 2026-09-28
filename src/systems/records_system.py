"""Record player -> the player's real Spotify (state "records").

Owner: Home (2026-09-28). The Record Player piece is a remote for the Spotify
app on THIS PC -- online, each PC drives its own Spotify, and the host never
launches anything because of the client's press (HomeMixin never routes the
remote farmer here; ``_records_open`` refuses it too).

* Using it when THIS PC isn't listening yet (``records_active``, an unsaved
  per-session flag -- NOT the shared, saved ``fr.on``) starts the music:
  Spotify is opened if it isn't running (and told to play once its window is
  up), un-paused if it is paused, left alone if it already plays. It also
  switches the piece on if it is off (``fr.on`` + the usual FURN_ACTION
  energy -- only then). A piece that is already on (saved on, bought on, or
  switched on by the partner) still starts THIS PC's Spotify on the first
  press. Using it while this PC listens just opens ``records.RecordScreen``.
* Loading a save never re-arms listening from a bare ``on`` flag: until
  someone here uses the record player, the game never ducks, toasts or
  pauses a Spotify the player started outside the game.
* While it's on and Spotify plays, the game's background music ducks to a
  whisper (``Audio.set_music_duck``) and each new song pops a "Now playing"
  toast. Switching it off, Spotify pausing or a new game restores the music.
  Switching it off pauses this PC's Spotify -- also when it happens elsewhere
  (the partner's X online, the piece picked up): the one shared record player
  stops the music on both PCs. That is a pause only, never a launch.
* No Spotify app (browser fallback): the page can't be read, so while the
  player is on it counts as playing (the record spins, the music ducks), and
  switching on again reopens the web player. Switching off can't reach the
  browser (a blind media key might start something else), so the player is
  told to pause it there instead.
* A new game / leaving a LAN session pauses this PC's Spotify first if it was
  listening (then the game music comes back).
* P pastes a Spotify playlist link; it is saved with the farm
  (``records_link``) and O opens it in Spotify (switching on opens it too when
  Spotify has to be started; a running Spotify just resumes). The LAN client keeps its
  own link in a small per-PC file instead (the host's save isn't its to write).
* Everything external lives in ``spotify.py`` (one daemon thread, safety-gated
  in tests); this mixin only decides WHEN. ``records_active`` = this PC is
  listening (it switched the player on / opened it); only then does it poll.

Contract (called from systems/home_system.py):
  _records_open(idx, fr, client=False)
      the player ``idx`` used the Placed record player ``fr``. True = handled.
      ``client``: running on the LAN client (the host owns ``fr.on``; the
      {"m": "furn", "kind": "record_player", "gx", "gy", "on": True/False}
      menu op SETS it -- never a blind toggle, which the 1 s world resync
      could turn the wrong way).
"""
import os

from ..settings import TILE, MAX_ENERGY, AREA_HOME

DUCK = 0.06                 # background music level while Spotify plays
DUCK_RATE = 1.6             # duck fade per second (a full swing in ~0.6 s)
ON_GRACE = 3.0              # LAN client: the host's copy of the switch may lag this long
_TOAST_COL = (150, 214, 150)


class RecordsMixin:
    """The Record Player: switch it on and real Spotify plays on this PC."""

    # ------------------------------------------------------------ lifecycle
    def _on_reset_records(self):
        if getattr(self, "records_active", False):
            # a new game / leaving a LAN session while this PC listens: the
            # game music comes back below, so the record stops first
            try:
                self._records_pause()
            except Exception:
                pass
        self.records_screen = None
        self.records_active = False      # this PC is listening (this session only, never saved)
        self.records_link = ""           # the farm's saved Spotify link (spotify: URI)
        self._rec_at = None              # (gx, gy) of the record player in use
        self._rec_obj = None             # ... and the Placed piece itself
        self._rec_home = None            # ... and the furniture list it was found in
        self._rec_song = None            # last song seen (a new one -> toast)
        self._rec_duck = 1.0
        self._rec_grace = 0.0
        self._rec_client_link = None     # LAN client's own link (read lazily)
        self._records_set_duck(1.0)
        try:
            from .. import spotify
            spotify.REMOTE.want(id(self), False)
        except Exception:
            pass

    def _on_area_enter_records(self):
        if self.world.current == AREA_HOME:
            self._records_build_sfx()

    def _on_save_records(self):
        return {"records_link": self.records_link or ""}

    def _on_load_records(self, d):
        if getattr(self, "net_mode", None) == "client":
            return                       # the host's save: its link, its switch
        from .. import spotify
        self.records_link = spotify.parse_link(d.get("records_link") or "") or ""
        # A piece saved switched ON is NOT a reason to listen: the player may
        # be playing their own Spotify outside the game. Nothing ducks, toasts
        # or pauses until someone here uses the record player this session --
        # and it doesn't pretend to play either (no spin, no notes): it loads OFF.
        if not getattr(self, "_net_applying_world", False):
            for q in self.world.home_furniture:
                if q.kind == "record_player":
                    q.on = False

    def _records_build_sfx(self):
        """Needle-drop / power-down sounds, synthesised off the main thread
        (callers fall back to stock sounds until they exist)."""
        a = getattr(self, "audio", None)
        a = getattr(a, "_real", None) or a      # inside an area context: the REAL audio
        if (not a or not getattr(a, "enabled", False)
                or a.sfx.get("records_needle") is not None
                or getattr(a, "_records_sfx_busy", False)):
            return
        a._records_sfx_busy = True
        import threading
        threading.Thread(target=self._records_synth_sfx, args=(a,), daemon=True).start()

    @staticmethod
    def _records_synth_sfx(a):
        try:
            R, S = a._render, a._to_sound
            a.sfx["records_needle"] = S(a._seq(
                R(0.05, [95], "sine", 0.34, noise=0.45, release=0.8),
                R(0.34, [2400], "sine", 0.05, noise=0.97, attack=0.2, release=0.7)))
            a.sfx["records_off"] = S(R(0.42, [240, 360], "sine", 0.16, sweep=-0.75,
                                       release=0.6))
        except Exception:
            pass
        finally:
            a._records_sfx_busy = False

    # ------------------------------------------------------------ helpers
    def _records_sfx(self, name, fallback):
        a = getattr(self.audio, "_real", None) or self.audio
        ready = getattr(a, "sfx", {}).get(name) is not None
        self.audio.play(name if ready else fallback)

    def _records_set_duck(self, f):
        fn = getattr(getattr(self, "audio", None), "set_music_duck", None)
        if fn:
            try:
                fn(f)
            except Exception:
                pass

    def _records_piece(self):
        """The live record player in use (None if it was picked up).

        Tracked as the Placed object itself, so moving it in Decorate mode
        (the same object, new gx/gy) keeps it. Gone from the SAME furniture
        list = sold / picked up (another record player that happens to be on
        is not this one). Only when the list itself was replaced (a LAN
        client's world resync, an undo: new Placed objects) is it looked up
        again: the one at the old spot, or failing that (moved AND replaced)
        any record player that is still on."""
        home = self.world.home_furniture
        obj = getattr(self, "_rec_obj", None)
        if obj is not None and any(q is obj for q in home):
            self._rec_at, self._rec_home = (obj.gx, obj.gy), home
            return obj
        at = getattr(self, "_rec_at", None)
        if at is None or home is getattr(self, "_rec_home", None):
            return None
        q = next((q for q in home if q.kind == "record_player" and (q.gx, q.gy) == at),
                 None)
        if q is None:
            q = next((q for q in home if q.kind == "record_player" and q.on), None)
        if q is not None:
            self._rec_obj, self._rec_at, self._rec_home = q, (q.gx, q.gy), home
        return q

    def _records_track(self, fr):
        """Remember ``fr`` as the record player in use."""
        self._rec_at, self._rec_obj = (fr.gx, fr.gy), fr
        self._rec_home = self.world.home_furniture

    def _records_pause(self):
        """Stop THIS PC's music (switched off / picked up / new game). The
        remote pauses the Spotify app only if it plays. The browser fallback
        can't be read or reached safely (a blind media key could start some
        other player instead), so the player is asked to pause it there."""
        from .. import spotify
        R = spotify.REMOTE
        R.send("pause")
        if R.web and not R.status.running:
            msg = "Spotify is still playing in your browser - pause it there"
            try:
                self.ui.log(f"Record Player off: {msg}")
            except Exception:
                pass
            t = getattr(self, "toast", None)
            if t:
                try:
                    from .. import records
                    t("Record Player off", msg, icon=records.record_icon(),
                      color=_TOAST_COL, seconds=5.0)
                except Exception:
                    pass

    def _records_link_path(self):
        from .. import savegame
        return os.path.join(os.path.dirname(savegame.SAVE_PATH), "records_link.txt")

    def _records_uri(self):
        """The Spotify link this PC opens (None = just the app)."""
        if getattr(self, "net_mode", None) == "client":
            if self._rec_client_link is None:
                from .. import spotify
                try:
                    with open(self._records_link_path(), encoding="utf-8") as f:
                        self._rec_client_link = spotify.parse_link(f.read(400)) or ""
                except Exception:
                    self._rec_client_link = ""
            return self._rec_client_link or None
        return self.records_link or None

    # ------------------------------------------------------------ open / controls
    def _records_open(self, idx, fr, client=False):
        if getattr(self, "net_mode", None) == "host" and idx == 1 and not client:
            return False                 # the remote farmer never drives THIS PC's Spotify
        from .. import records, spotify
        p = self.players[idx]
        # Start the music whenever THIS PC isn't listening yet -- decided by
        # the session flag, never by the shared (saved, partner-switched)
        # fr.on: a piece that is already on must still start Spotify here.
        start = not self.records_active or not fr.on
        switch_on = not fr.on
        self._records_track(fr)
        if start:
            if client:                   # the host owns the real switch: SET it
                self._net_send_menu({"m": "furn", "kind": "record_player",
                                     "gx": fr.gx, "gy": fr.gy, "on": True})
                if not switch_on:        # (switching on, the host logs it)
                    self.ui.log(f"{p.name}: puts a record on")
            elif switch_on:
                from .actions_system import FURN_ACTION
                verb, gain = FURN_ACTION.get("record_player", ("spin a record", 12))
                gain = int(gain * getattr(fr, "level", 1))
                p.energy = min(MAX_ENERGY, p.energy + gain)
                self.ui.log(f"{p.name}: turns the Record Player ON - {verb} (+{gain} energy)")
            else:
                self.ui.log(f"{p.name}: puts a record on")
            fr.on = True
            self._rec_grace = ON_GRACE if client else 0.0
            self.parts.sparkle(fr.gx * TILE + TILE / 2, fr.gy * TILE + TILE / 2, n=6,
                               color=(200, 226, 255))
            # "start" opens / un-pauses Spotify and leaves one that plays alone
            spotify.REMOTE.send("start", self._records_uri())
            self._records_sfx("records_needle", "ui_toggle")
        else:
            self.audio.play("ui_select")
        self.records_active = True
        self._rec_song = spotify.REMOTE.status.song     # no toast for what's already on
        self.records_screen = records.RecordScreen(self, idx, fr, client=client, fresh=start)
        self.state = "records"
        self._records_tick(0.0)
        return True

    def _records_cmd(self, cmd):
        """A screen control -> the Spotify remote ("toggle", "next", "prev", "open")."""
        from .. import spotify
        spotify.REMOTE.send(cmd, self._records_uri())

    def _records_paste(self):
        """P: keep the Spotify link on the clipboard. Returns (ok, message)."""
        from .. import spotify
        text = spotify.clipboard_text().strip()
        if not text:
            return False, "The clipboard is empty - copy a Spotify playlist link first"
        uri = spotify.parse_link(text)
        if uri is None:
            if "spotify.link" in text:
                return False, "Short spotify.link links won't work - copy the full link"
            return False, "That's not a Spotify link (open.spotify.com/... or spotify:...)"
        if getattr(self, "net_mode", None) == "client":
            self._rec_client_link = uri
            try:
                with open(self._records_link_path(), "w", encoding="utf-8") as f:
                    f.write(uri)
            except Exception:
                pass
        else:
            self.records_link = uri
        return True, f"{spotify.link_kind(uri)} saved! Press O to open it in Spotify"

    def _records_close(self, screen):
        """Esc: walk away -- the record keeps playing."""
        self.records_screen = None
        if self.state == "records":
            self.state = "play"
        self.audio.play("ui_move")

    def _records_power_off(self, screen):
        """X: switch the record player off (and pause Spotify if it plays)."""
        live = self._records_piece() or screen.fr
        if live is not None:
            if screen.client:
                # SET it off on the host (idempotent: the local copy may lag
                # the host's by a resync, a blind toggle could turn it ON)
                self._net_send_menu({"m": "furn", "kind": "record_player",
                                     "gx": live.gx, "gy": live.gy, "on": False})
            elif live.on:
                self.ui.log(f"{self.players[screen.pidx].name}: switches the Record Player off")
                if getattr(self, "net_mode", None) == "host":
                    self._net_toast(f"{self.players[screen.pidx].name} switched the Record Player off")
            live.on = False
        self._records_pause()
        self.records_active = False
        self._rec_grace = 0.0
        self._rec_duck = 1.0
        self._records_set_duck(1.0)
        self.records_screen = None
        if self.state == "records":
            self.state = "play"
        self._records_sfx("records_off", "ui_toggle")
        self._records_tick(0.0)

    # ------------------------------------------------------------ per frame
    def _records_tick(self, dt):
        """Poll while listening, duck the game music while Spotify plays, toast
        each new song. Called every frame from play / the screen / the client."""
        from .. import spotify
        R = spotify.REMOTE
        self._rec_grace = max(0.0, self._rec_grace - dt)
        live = self._records_piece()
        on = live is not None and live.on
        scr = self.records_screen if self.state == "records" else None
        if self.records_active and not on and self._rec_grace <= 0:
            # switched off elsewhere (online: the partner's X) or picked up:
            # the music stops here too. Pausing only -- nothing is ever
            # launched on this PC because of someone else's press.
            self.records_active = False
            self._records_pause()
            if scr is not None:
                self._records_close(scr)
                scr = None
        on = on or self._rec_grace > 0
        want = (self.records_active and on) or scr is not None
        R.want(id(self), want)
        st = R.status if want else spotify.NOT_RUNNING
        # browser fallback: its state can't be read, so like the spinning
        # record on the screen it counts as playing while the player is on
        web = R.web and not st.running
        playing = self.records_active and on and (st.playing or web)
        target = DUCK if playing else 1.0
        if self._rec_duck != target and dt > 0:
            step = DUCK_RATE * dt
            self._rec_duck = (min(target, self._rec_duck + step) if target > self._rec_duck
                              else max(target, self._rec_duck - step))
            self._records_set_duck(self._rec_duck)
        song = st.song if playing else None
        if song and song != self._rec_song:
            self._rec_song = song
            if self.state == "play":
                self._records_toast(song)

    def _records_tint(self):
        from .. import records
        live = self._records_piece()
        return records.piece_tint(live) if live is not None else None

    def _records_toast(self, song):
        artist, title = song
        t = getattr(self, "toast", None)
        if not t or not artist:              # ads / untitled: no toast
            return
        from .. import records
        # the toast draws text Consolas lacks (Thai, emoji...) in a face that
        # has it; a part with nothing drawable left becomes a note
        _f, title = records.song_face(title)
        _f, artist = records.song_face(artist, placeholder="")
        sub = f"{title} - {artist}" if artist else title
        icon = records.record_icon(self._records_tint())
        try:
            t("Now playing", sub, icon=icon, color=_TOAST_COL, seconds=4.0)
        except Exception:
            return

    def _on_update_records(self, dt):
        self._records_tick(dt)

    def _on_client_update_records(self, dt):
        if self.state != "records":              # the screen ticks it itself
            self._records_tick(dt)

    # ------------------------------------------------------------ custom state
    def _state_event_records(self, e):
        scr = self.records_screen
        if scr is None:
            self.state = "play"
            return
        scr.handle_event(e)

    def _state_update_records(self, dt):
        scr = self.records_screen
        if scr is None:
            self.state = "play"
            return
        scr.update(dt)
        self._records_tick(dt)

    def _state_draw_records(self):
        if self.records_screen is not None:
            self.records_screen.draw(self.screen)
