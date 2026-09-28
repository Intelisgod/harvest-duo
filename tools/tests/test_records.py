"""Record Player -> real Spotify (RecordsMixin + records.py + spotify.py).

Runs with the spotify SAFETY GATE on (HD_NO_EXTERNAL=1 and the dummy video
driver): launch / media keys are only recorded in ``spotify.CALLS`` and the
four real exits (startfile, browser, key events, window messages) are replaced
by spies that must never fire. Spotify's state is faked via FAKE_STATUS.

run(g, check, H) is called by tools/smoke_test.py (s_domain_tests)."""
import os
import time
import pygame


def run(g, check, H):
    os.environ["HD_NO_EXTERNAL"] = "1"               # belt and braces for the gate
    from src import spotify, records, furniture as F
    from src.settings import AREA_HOME, P1_KEYS, P2_KEYS

    S = spotify
    R = S.REMOTE
    leaks = []
    real = (S._startfile, S._open_web, S._key, S._post)
    S._startfile = lambda *a: leaks.append(("startfile", a))
    S._open_web = lambda *a: leaks.append(("web", a))
    S._key = lambda *a: leaks.append(("key", a))
    S._post = lambda *a: leaks.append(("post", a)) or True
    old = (S.AUTOPLAY_SETTLE, S.FAKE_STATUS, S.FAKE_CLIPBOARD)
    old_link = g.records_link                        # restored at the end (re-runnable)
    g.records_link = ""
    S.AUTOPLAY_SETTLE = 0.0
    ev = pygame.event.Event

    g.warp(AREA_HOME, H.spawns_by_area(g)[AREA_HOME])
    g.state = "play"
    p = g.players[0]
    rp = next((q for q in g.world.home_furniture if q.kind == "record_player"), None)
    if rp is None:
        rp = F.Placed("record_player", 7, 6, 0, 8)
        g.world.home_furniture.append(rp)

    def fake(running=False, playing=False, artist="", title=""):
        S.FAKE_STATUS = S.Status(running, playing, artist, title)
        R.poke()

    def wait(cond, secs=2.0):
        end = time.monotonic() + secs
        while time.monotonic() < end:
            R.flush(0.2)
            if cond():
                return True
            if g.state == "records":
                g._run_state("update", H.DT)
            else:
                g.update(H.DT)
            time.sleep(0.01)
        return cond()

    def key(k):
        g._run_state("event", ev(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))
        g._run_state("event", ev(pygame.KEYUP, key=k, mod=0, unicode="", scancode=0))
        R.flush()

    def media():
        return [c[1] for c in S.CALLS if c[0] == "media"]

    def cleanup():
        if g.state == "records":
            g.records_screen = None
            g.state = "play"
        if not any(q is rp for q in g.world.home_furniture):
            g.world.home_furniture.append(rp)
        rp.on = False
        g.records_active = False
        g._rec_duck = 1.0
        g._records_set_duck(1.0)
        R.want(id(g), False)
        R.web = False
        fake()

    # ------------------------------------------------------------ pure helpers
    def links_and_titles():
        pl = "37i9dQZF1DXcBWIGoYBM5M"
        assert S.parse_link(f"https://open.spotify.com/playlist/{pl}?si=abc123") == \
            f"spotify:playlist:{pl}"
        assert S.parse_link(f"open.spotify.com/intl-th/album/{pl}") == f"spotify:album:{pl}"
        assert S.parse_link(f"spotify:user:someone:playlist:{pl}") == f"spotify:playlist:{pl}"
        assert S.parse_link("https://open.spotify.com/collection/tracks") == \
            "spotify:collection:tracks"
        for bad in ("", "hello", "https://example.com/playlist/abc", "spotify:playlist:x;calc",
                    "https://spotify.link/AbCdEf", "C:\\Windows\\notepad.exe"):
            assert S.parse_link(bad) is None, bad
        assert S.clean_uri("spotify:") == "spotify:"
        for bad in ("notepad.exe", "spotify:..\\x", "spotify:a b", "http://x", None):
            assert S.clean_uri(bad) is None, bad
        assert S.web_url(f"spotify:playlist:{pl}") == f"https://open.spotify.com/playlist/{pl}"
        assert S.web_url("spotify:") == "https://open.spotify.com/"
        assert not S.parse_title("Spotify Premium").playing
        assert not S.parse_title("Spotify Free").playing and S.parse_title("Spotify").running
        st = S.parse_title("Queen - Bohemian Rhapsody - Remastered 2011")
        assert st.playing and st.artist == "Queen" and st.title == \
            "Bohemian Rhapsody - Remastered 2011", st
        assert not S.parse_title("DDE Server Window").playing
        assert S.gated(), "the safety gate must be on in tests"
        assert S.now_playing() == (S.FAKE_STATUS or S.NOT_RUNNING)
    check("records: link + window-title parsing, gate on", links_and_titles)

    def window_picker():
        """Spotify.exe owns hidden helper windows with titles of their own: the
        status must come from the player window, never from a helper."""
        main0 = S._MAIN[0]
        junk = [(11, "DDE Server Window", False, "DDEMLEvent"),
                (12, "GDI+ Window (Spotify.exe)", False, "GDI+ Hook Window Class"),
                (13, "Default IME", False, "IME"), (14, "MSCTFIME UI", False, "MSCTFIME UI"),
                (15, "Miniplayer", True, "Chrome_WidgetWin_1"),
                (16, "Some Helper", False, "Chrome_WidgetWin_1")]
        try:
            for cls in ("Chrome_WidgetWin_0", "SpotifyMainWindow", ""):
                st = S._status_from(junk + [(1, "Spotify Premium", True, cls)])
                assert st.running and st.ready and not st.playing, (cls, st)
                assert S._MAIN[0] == 1, (cls, S._MAIN[0])
                st = S._status_from(junk[:3] + [(1, "Queen - Bohemian Rhapsody", True, cls)])
                assert st.playing and st.song == ("Queen", "Bohemian Rhapsody"), (cls, st)
                assert S._MAIN[0] == 1
            # only helpers (starting up): running, idle, nothing to press yet
            st = S._status_from(junk)
            assert st.running and not st.playing and not st.ready and S._MAIN[0] is None, st
            assert S._status_from([]) == S.NOT_RUNNING
            # old-style rows without a class still skip the helpers
            st = S._status_from([r[:3] for r in junk] + [(1, "Spotify Free", True)])
            assert not st.playing and S._MAIN[0] == 1, st
            # closed to the tray: the hidden player window still reports its song
            st = S._status_from(junk + [(1, "Band - Song", False, "Chrome_WidgetWin_0")])
            assert st.playing and st.song == ("Band", "Song") and S._MAIN[0] == 1, st
            # the player's class beats a visible stranger with a song-like title
            st = S._status_from([(9, "Foo - Bar", True, "Chrome_WidgetWin_1"),
                                 (1, "Spotify Premium", True, "Chrome_WidgetWin_0")])
            assert not st.playing and S._MAIN[0] == 1, st
            # visible beats hidden among player-like windows
            st = S._status_from([(2, "Old - Tune", False, ""), (1, "Spotify", True, "")])
            assert not st.playing and S._MAIN[0] == 1, st
            # an ad in the player window (no artist) still counts as playing
            st = S._status_from([(1, "Advertisement", True, "Chrome_WidgetWin_0")])
            assert st.playing and not st.artist, st
        finally:
            S._MAIN[0] = main0
        return "helpers skipped, player window wins"
    check("records: Spotify status comes from the player window, not helpers",
          window_picker)

    # ------------------------------------------------------------ switch on (not running)
    def switch_on_launches():
        cleanup()
        S.CALLS.clear()
        rp.on = False
        p.energy = 10
        g.interact_furniture(p, rp)
        assert g.state == "records" and rp.on, (g.state, rp.on)
        assert p.energy > 10, "no energy for spinning a record"
        assert wait(lambda: ("launch", "spotify:") in S.CALLS), S.CALLS
        assert R.launching and R.alive, "not waiting for the app to show up"
        g._run_state("update", H.DT)
        g.draw()
        H.shot(g, "records_opening")
        fake(running=True)                           # the app window appears, idle
        assert wait(lambda: media() == ["play_pause"]), S.CALLS
        assert not R.launching
        fake(True, True, "Nong Mai", "A very long song name that just keeps on going "
                                     "and going until it has to wrap (Acoustic Version)")
        assert wait(lambda: R.status.playing)
        for _ in range(60):
            g._run_state("update", H.DT)
        assert g.audio.music_duck < 0.2, f"music not ducked ({g.audio.music_duck})"
        g.draw()
        H.shot(g, "records_playing")
        return f"calls {S.CALLS}"
    check("records: switch on -> opens Spotify, auto-plays, ducks music", switch_on_launches)

    # ------------------------------------------------------------ controls
    def controls():
        assert g.state == "records"
        S.CALLS.clear()
        key(P1_KEYS["action"])
        key(P2_KEYS["left"])
        key(P1_KEYS["right"])
        assert media() == ["play_pause", "prev", "next"], S.CALLS
        # a held key (auto-repeat, no KEYUP) is one press
        S.CALLS.clear()
        for _ in range(4):
            g._run_state("event", ev(pygame.KEYDOWN, key=P2_KEYS["right"], mod=0,
                                     unicode="", scancode=0))
        g._run_state("event", ev(pygame.KEYUP, key=P2_KEYS["right"], mod=0,
                                 unicode="", scancode=0))
        R.flush()
        assert media() == ["next"], S.CALLS
        # the round buttons are clickable (mouse is in logical coords: SCALED)
        S.CALLS.clear()
        scr = g.records_screen
        (cx, cy), _r = scr.L["buttons"]["prev"]
        g._run_state("event", ev(pygame.MOUSEMOTION, pos=(cx, cy), rel=(0, 0), buttons=(0, 0, 0)))
        g._run_state("event", ev(pygame.MOUSEBUTTONDOWN, pos=(cx, cy), button=1))
        R.flush()
        assert media() == ["prev"], S.CALLS
        g.draw()
    check("records: Action/Left/Right/click -> play_pause/prev/next", controls)

    # ------------------------------------------------------------ paste + open
    def paste_and_open():
        pl = "37i9dQZF1DXcBWIGoYBM5M"
        g.records_link = ""
        S.FAKE_CLIPBOARD = "not a link at all"
        key(pygame.K_p)
        assert g.records_link == "", g.records_link
        S.FAKE_CLIPBOARD = f"  https://open.spotify.com/playlist/{pl}?si=x1  "
        key(pygame.K_p)
        assert g.records_link == f"spotify:playlist:{pl}", g.records_link
        # the message says what really happens: O opens it (switching on
        # only does while Spotify isn't running, and then resumes the queue)
        msg = g.records_screen.msg
        assert "O to open it" in msg and "switching on" not in msg, msg
        S.CALLS.clear()
        key(pygame.K_o)
        assert ("launch", f"spotify:playlist:{pl}") in S.CALLS, S.CALLS
        d = g._on_save_records()
        g.records_link = ""
        was_on = rp.on
        g._on_load_records(d)
        assert g.records_link == f"spotify:playlist:{pl}", "link not restored from save"
        # a loaded record player is OFF (it must not look like it's playing)
        assert not rp.on, "a load left the record player looking switched on"
        g._on_load_records({"records_link": "notepad.exe"})
        assert g.records_link == "", "junk link survived a load"
        g.records_link = f"spotify:playlist:{pl}"
        rp.on = was_on                  # back to this session's state
        g.draw()
    check("records: P pastes a playlist link (saved), O opens it", paste_and_open)

    # ------------------------------------------------------------ Esc + toasts
    def esc_keeps_playing():
        key(pygame.K_ESCAPE)
        assert g.state == "play" and rp.on and g.records_active
        g.toasts = []
        fake(True, True, "The Band", "Second Song")
        assert wait(lambda: any(t[0] == "Now playing" for t in g.toasts)), g.toasts
        assert R.alive, "poller stopped while the record player is on"
        assert g.audio.music_duck < 0.2
        # a Thai title: the toast itself draws it with a Thai-capable face
        # (no pre-drawn card slipped into the toast list any more)
        g.toasts = []
        fake(True, True, "\u0e1b\u0e32\u0e25\u0e4c\u0e21\u0e21\u0e35\u0e48",
             "\u0e04\u0e27\u0e32\u0e21\u0e23\u0e31\u0e01\u0e17\u0e33\u0e43\u0e2b\u0e49"
             "\u0e04\u0e19\u0e15\u0e32\u0e1a\u0e2d\u0e14")
        assert wait(lambda: any(t[0] == "Now playing" for t in g.toasts)), g.toasts
        t = next(t for t in g.toasts if t[0] == "Now playing")
        assert t[6] is None, "records_system still injects its own toast card"
        assert g._toast_text("Now playing", 18, True) is None, "ASCII toast left Consolas"
        fb = g._toast_text(t[1], 14, False)
        if not records.consolas_ok(t[1]):
            assert fb is not None, "Thai toast text would be boxes in Consolas"
            if records._face_path("leelawadeeui") or records._face_path("tahoma"):
                assert fb[1] == records.clean_text(t[1]), f"Thai glyphs dropped: {fb[1]!r}"
        card = g._toast_card(list(t))
        assert card.get_width() >= 420 and card.get_height() >= 48
        for _ in range(30):                          # let it slide fully in
            g.update(H.DT)
        g.draw()
        H.shot(g, "records_toast_thai")
        # Spotify paused -> the music comes back up
        fake(True, False)
        assert wait(lambda: g.audio.music_duck >= 0.999), g.audio.music_duck
    check("records: Esc walks away (keeps playing), new song toasts", esc_keeps_playing)

    def reopen_when_on():
        S.CALLS.clear()
        g.interact_furniture(p, rp)
        R.flush()
        assert g.state == "records" and not any(c[0] == "launch" for c in S.CALLS), S.CALLS
        g._run_state("update", H.DT)
        g.draw()
        H.shot(g, "records_paused")
    check("records: using it while this PC listens just opens the screen", reopen_when_on)

    # ------------------------------------------------------------ off
    def x_switches_off():
        fake(True, True, "The Band", "Third Song")
        assert wait(lambda: R.status.playing)
        S.CALLS.clear()
        key(pygame.K_x)
        assert g.state == "play" and not rp.on and not g.records_active
        assert media() == ["play_pause"], f"X should pause a playing Spotify: {S.CALLS}"
        assert g.audio.music_duck == 1.0, g.audio.music_duck
        g.update(H.DT)
        assert R.join(1.5), "status poller still running with the record player off"
    check("records: X switches off, pauses Spotify, restores music, poller stops",
          x_switches_off)

    def paused_spotify_unpauses():
        cleanup()
        fake(running=True)                           # open but paused
        R.flush()
        S.CALLS.clear()
        g.interact_furniture(p, rp)
        assert wait(lambda: media() == ["play_pause"])
        assert not any(c[0] == "launch" for c in S.CALLS), S.CALLS
        fake(running=False)
        assert wait(lambda: not R.status.running)
        g._run_state("update", H.DT)
        g.draw()
        H.shot(g, "records_not_running")
        key(pygame.K_x)
        assert g.state == "play" and not rp.on
    check("records: switching on with Spotify paused just un-pauses it",
          paused_spotify_unpauses)

    # ------------------------------------------------------------ LAN
    def lan_paths():
        cleanup()
        sent = []
        g._net_send_menu = lambda m: sent.append(m)
        try:
            g.net_mode = "host"                      # the remote farmer never reaches Spotify
            S.CALLS.clear()
            assert g._records_open(1, rp) is False and not S.CALLS and g.state == "play"
            g.net_mode = "client"
            rp.on = False
            assert g._records_open(1, rp, client=True) is True
            assert g.state == "records" and rp.on
            assert sent == [{"m": "furn", "kind": "record_player", "gx": rp.gx, "gy": rp.gy,
                             "on": True}], sent
            assert wait(lambda: any(c[0] == "launch" for c in S.CALLS)), S.CALLS
            key(pygame.K_x)
            assert len(sent) == 2 and not rp.on and g.state == "play", sent
            assert sent[1] == {"m": "furn", "kind": "record_player", "gx": rp.gx,
                               "gy": rp.gy, "on": False}, sent
            # the partner switched it on (the host's copy says on): the
            # client's first press still starts ITS Spotify and SETS it on
            sent.clear()
            S.CALLS.clear()
            rp.on = True
            g.records_active = False
            assert g._records_open(1, rp, client=True) is True
            assert sent and sent[0].get("on") is True, sent
            assert wait(lambda: any(c[0] == "launch" for c in S.CALLS)), S.CALLS
            key(pygame.K_x)
            assert sent[-1].get("on") is False, sent
        finally:
            g.net_mode = None
            del g._net_send_menu
            cleanup()
        return f"sent {sent}"
    check("records: LAN host refuses P2's press, client sets on/off via the host", lan_paths)

    def lan_explicit_switch():
        """The client's op carries the state it wants ("on"): a stale press
        (its copy still off, the host just switched it on) can't flip the
        host's record player off -- the 1 s world resync race. Ops without
        "on" (old clients, lamps, the TV) still toggle."""
        cleanup()
        p2 = g.players[1]
        e_keep = p2.energy
        op = {"m": "furn", "kind": "record_player", "gx": rp.gx, "gy": rp.gy}
        try:
            fake(True, True, "The Band", "Race Song")
            R.flush()
            g.interact_furniture(p, rp)              # host P1 listens
            key(pygame.K_ESCAPE)
            g.net_mode = "host"
            S.CALLS.clear()
            p2.energy = 10
            g._net_apply_menu(dict(op, on=True))     # the client's stale "switch on"
            assert p2.energy == 10, "energy for switching on a piece that was already on"
            for _ in range(5):
                g.update(H.DT)
            R.flush()
            assert rp.on and g.records_active, "a stale switch-on flipped the host's player off"
            assert not S.CALLS, f"host Spotify touched by a no-op: {S.CALLS}"
            g._net_apply_menu(dict(op, on=False))    # the client's X
            assert not rp.on
            g._net_apply_menu(dict(op, on=False))    # ... twice: still off
            assert not rp.on
            g.update(H.DT)
            R.flush()
            assert not g.records_active and media() == ["play_pause"], S.CALLS
            p2.energy = 10
            g._net_apply_menu(dict(op, on=True))
            assert rp.on and p2.energy > 10, (rp.on, p2.energy)
            g._net_apply_menu(dict(op))              # an old client: a plain toggle
            assert not rp.on
            e = p2.energy
            g._net_apply_menu(dict(op, gx=-9, gy=-9, on=True))   # nothing there
            assert p2.energy == e, "a switch op for a missing piece paid energy"
        finally:
            g.net_mode = None
            p2.energy = e_keep
            cleanup()
        return "explicit on/off never flips the wrong way"
    check("records: LAN switch ops set the state (no toggle race)", lan_explicit_switch)

    # ------------------------------------------------------------ off elsewhere
    def off_elsewhere_pauses():
        """The partner's X online / the piece picked up: this PC's Spotify
        pauses too (the game music must never come back over it)."""
        out = []
        for how in ("partner", "picked up"):
            cleanup()
            fake(True, True, "The Band", "Fourth Song")
            R.flush()
            g.interact_furniture(p, rp)
            key(pygame.K_ESCAPE)
            for _ in range(4):
                g.update(H.DT)
            d0 = g.audio.music_duck
            assert d0 < 1.0, "music not ducking while Spotify plays"
            S.CALLS.clear()
            if how == "partner":
                rp.on = False                        # the host's copy went off
            else:
                g.world.home_furniture.remove(rp)
            g.update(H.DT)
            R.flush()
            assert not g.records_active
            assert media() == ["play_pause"], f"{how}: Spotify not paused {S.CALLS}"
            g.update(H.DT)
            assert g.audio.music_duck > d0, "the game music isn't coming back"
            out.append(how)
        cleanup()
        return "paused for " + ", ".join(out)
    check("records: switched off elsewhere / picked up -> pauses Spotify",
          off_elsewhere_pauses)

    def moved_keeps_playing():
        """Decorate mode drags the SAME Placed object (keeps .on): moving the
        playing record player must not count as switching it off. After a LAN
        resync / an undo replaced the objects, the one still on is found."""
        from src import furniture as FF
        home = g.world.home_furniture
        at0 = (rp.gx, rp.gy)
        copy = None
        try:
            cleanup()
            fake(True, True, "The Band", "Fifth Song")
            R.flush()
            g.interact_furniture(p, rp)
            key(pygame.K_ESCAPE)
            for _ in range(3):
                g.update(H.DT)
            S.CALLS.clear()
            rp.gx += 1                               # dragged one tile
            for _ in range(3):
                g.update(H.DT)
            R.flush()
            assert g.records_active and rp.on and not S.CALLS, S.CALLS
            assert g._records_piece() is rp and g._rec_at == (rp.gx, rp.gy)
            # moved AND replaced (the partner moved it; the LAN resync / an
            # undo rebuilt the whole furniture list with new Placed objects)
            copy = FF.Placed(**dict(rp.to_dict(), gx=rp.gx + 1))    # as build.py's undo
            assert copy.on
            g.world.home_furniture = [q for q in home if q is not rp] + [copy]
            for _ in range(3):
                g.update(H.DT)
            R.flush()
            assert g.records_active and not S.CALLS, S.CALLS
            assert g._records_piece() is copy, "lost the replaced record player"
            # ... and picking that one up still stops the music
            g.world.home_furniture.remove(copy)
            g.update(H.DT)
            R.flush()
            assert not g.records_active and media() == ["play_pause"], S.CALLS
        finally:
            g.world.home_furniture = home
            rp.gx, rp.gy = at0
            cleanup()
        return "moved: still on + playing"
    check("records: moving the playing record player keeps the music on",
          moved_keeps_playing)

    # ------------------------------------------------------------ browser fallback
    def browser_fallback():
        """No Spotify app: launch() opens the web player. The record spins, the
        music ducks, and switching on again reopens the page."""
        cleanup()
        opened = []
        real_launch = S.launch
        S.launch = lambda uri=None: opened.append(uri) or "web"
        try:
            g.interact_furniture(p, rp)
            assert wait(lambda: len(opened) == 1 and R.web), (opened, R.web)
            assert g.records_screen.spinning()
            # the big button agrees with the spinning record: pause bars (the
            # gap between them is at the centre, where a play triangle is ink)
            scr = g.records_screen
            scr.hover, scr.flash = None, {}
            g.draw()
            (cx, cy), _r = scr.L["buttons"]["play"]
            px = tuple(g.screen.get_at((cx, cy)))[:3]
            assert px != tuple(records.K.INK[:3]), "play triangle on a spinning record"
            H.shot(g, "records_browser")
            assert wait(lambda: g.audio.music_duck < 0.2), g.audio.music_duck
            S.CALLS.clear()
            g.toasts = []
            key(pygame.K_x)
            assert g.audio.music_duck == 1.0 and not rp.on
            # the web player can't be reached safely: no blind media key, the
            # player is told to pause it in the browser instead
            assert not media(), f"blind media key sent for the browser: {S.CALLS}"
            assert any(t[0] == "Record Player off" and "browser" in t[1] for t in g.toasts), \
                g.toasts
            assert any("pause it there" in m[0] for m in g.ui.messages), g.ui.messages
            for _ in range(30):
                g.update(H.DT)
            g.draw()
            H.shot(g, "records_browser_off")
            g.interact_furniture(p, rp)
            assert wait(lambda: len(opened) == 2), f"switching on again did nothing: {opened}"
            key(pygame.K_x)
        finally:
            S.launch = real_launch
            cleanup()
        return f"opened {opened}"
    check("records: browser fallback ducks the music, reopens on switch-on", browser_fallback)

    # ------------------------------------------------------------ already on
    def already_on_starts():
        """The real save has the record player saved ON (build mode / the
        partner can switch it on too): the first press this session must
        still start THIS PC's Spotify -- whether it is closed, paused or
        already playing. Energy only for really switching it on."""
        out = []
        try:
            # (a) Spotify closed -> opened (and played once it is up)
            cleanup()
            rp.on = True
            S.CALLS.clear()
            p.energy = 10
            g.interact_furniture(p, rp)
            assert p.energy == 10, "energy for a record player that was already on"
            assert g.state == "records" and rp.on and g.records_active, (g.state, rp.on)
            assert wait(lambda: any(c[0] == "launch" for c in S.CALLS)), \
                f"first press on a piece that is already on never started Spotify: {S.CALLS}"
            assert g.records_screen.msg.startswith("Dropping the needle"), g.records_screen.msg
            assert any("puts a record on" in m[0] for m in g.ui.messages), g.ui.messages
            g._run_state("update", H.DT)
            g.draw()
            H.shot(g, "records_already_on_start")
            out.append("closed->launch")
            # ... pressed again while this PC listens: just the screen
            key(pygame.K_ESCAPE)
            S.CALLS.clear()
            g.interact_furniture(p, rp)
            R.flush()
            assert g.state == "records" and not S.CALLS, S.CALLS
            key(pygame.K_ESCAPE)
            # (b) Spotify open but paused -> un-paused
            cleanup()
            rp.on = True
            fake(running=True)
            R.flush()
            S.CALLS.clear()
            g.interact_furniture(p, rp)
            assert wait(lambda: media() == ["play_pause"]), S.CALLS
            assert not any(c[0] == "launch" for c in S.CALLS), S.CALLS
            key(pygame.K_ESCAPE)
            out.append("paused->play")
            # (c) Spotify already playing -> left alone, but now this PC listens
            cleanup()
            rp.on = True
            fake(True, True, "Already", "Playing")
            R.flush()
            S.CALLS.clear()
            g.interact_furniture(p, rp)
            R.flush()
            time.sleep(0.05)
            R.flush()
            assert not S.CALLS, f"'start' pressed a Spotify that already plays: {S.CALLS}"
            key(pygame.K_ESCAPE)
            assert wait(lambda: g.audio.music_duck < 0.2), g.audio.music_duck
            out.append("playing->untouched")
        finally:
            cleanup()
        return ", ".join(out)
    check("records: a record player already ON still starts Spotify on first press",
          already_on_starts)

    def load_never_listens():
        """A save with the player ON must not make the game duck, toast or
        pause a Spotify the player started outside the game."""
        try:
            cleanup()
            rp.on = True
            fake(True, True, "Their Own", "Song Outside The Game")
            R.flush()
            g._on_load_records(g._on_save_records())
            assert not g.records_active, "loading re-armed listening from a bare on flag"
            g.toasts = []
            S.CALLS.clear()
            for _ in range(30):
                g.update(H.DT)
            R.flush()
            assert id(g) not in R._wants, "polling Spotify nobody here asked for"
            assert g.audio.music_duck >= 0.999, g.audio.music_duck
            assert not any(t[0] == "Now playing" for t in g.toasts), g.toasts
            rp.on = False                            # the partner switches it off
            g.update(H.DT)
            g.world.home_furniture.remove(rp)        # ... or it is picked up
            g.update(H.DT)
            R.flush()
            assert not S.CALLS, f"paused a Spotify the game never started: {S.CALLS}"
        finally:
            cleanup()
        return "no duck, no toast, no pause"
    check("records: loading a save with the player ON doesn't grab Spotify",
          load_never_listens)

    def reset_pauses():
        """A new game / leaving a LAN session brings the game music back: a
        Spotify this PC was listening to is paused first."""
        link = g.records_link
        try:
            cleanup()
            fake(True, True, "The Band", "Last Dance")
            R.flush()
            g.interact_furniture(p, rp)
            key(pygame.K_ESCAPE)
            for _ in range(3):
                g.update(H.DT)
            S.CALLS.clear()
            g._on_reset_records()                    # Game.reset(): new game / net leave
            R.flush()
            assert media() == ["play_pause"], f"Spotify left playing after a reset: {S.CALLS}"
            assert not g.records_active and g.audio.music_duck == 1.0
            S.CALLS.clear()
            g._on_reset_records()                    # not listening: hands off
            R.flush()
            assert not S.CALLS, S.CALLS
        finally:
            g.records_link = link
            cleanup()
    check("records: new game / leaving LAN pauses this PC's Spotify", reset_pauses)

    def two_players_sell_playing():
        """Two record players, both on: picking up / selling the one this PC
        listens to stops the music (the other one isn't 'the same piece')."""
        home = g.world.home_furniture
        taken = {c for q in home for c in q.cells()}
        spot = next(((x, y) for y in range(1, 9) for x in range(1, 13)
                     if (x, y) not in taken), (rp.gx + 2, rp.gy))
        rp2 = F.Placed("record_player", spot[0], spot[1], 0, 5, on=True)
        home.append(rp2)
        try:
            cleanup()
            fake(True, True, "The Band", "Seventh Song")
            R.flush()
            g.interact_furniture(p, rp)
            key(pygame.K_ESCAPE)
            for _ in range(3):
                g.update(H.DT)
            S.CALLS.clear()
            home.remove(rp)                          # Decorate mode: sold (same list)
            g.update(H.DT)
            R.flush()
            assert g._records_piece() is None, "fell back to the other record player"
            assert not g.records_active and media() == ["play_pause"], S.CALLS
        finally:
            g.world.home_furniture[:] = [q for q in g.world.home_furniture if q is not rp2]
            cleanup()
        return f"second player at {spot}"
    check("records: selling the playing one of two record players stops the music",
          two_players_sell_playing)

    def song_layout_cached():
        """Fitting / wrapping the title happens once per song, not per frame
        (a long Thai title measured ~50 Font.size calls every frame)."""
        scr = records.RecordScreen(g, 0, rp)
        well = scr.L["well"]
        thai = ("\u0e28\u0e34\u0e25\u0e1b\u0e34\u0e19",
                "\u0e04\u0e27\u0e32\u0e21\u0e23\u0e31\u0e01\u0e17\u0e33\u0e43\u0e2b\u0e49"
                "\u0e04\u0e19\u0e15\u0e32\u0e1a\u0e2d\u0e14 (OST) " * 3)
        calls = []
        real = records.song_layout
        records.song_layout = lambda *a: calls.append(a) or real(*a)
        try:
            for _ in range(30):
                scr._draw_song(g.screen, well, thai, True)
            assert len(calls) == 1, f"laid out {len(calls)} times in 30 frames"
            scr._draw_song(g.screen, well, ("B", "Another Song"), True)
            scr._draw_song(g.screen, well, thai, False)          # paused: other colours
            assert len(calls) == 3, len(calls)
            lay = real(thai, well.w - 40, well.h, True)
            assert 1 <= len(lay) <= 3 and all(img.get_width() <= well.w - 40
                                              for img, _y in lay), lay
            t0 = time.perf_counter()
            for _ in range(100):
                scr._draw_song(g.screen, well, thai, False)
            ms = (time.perf_counter() - t0) * 10.0
        finally:
            records.song_layout = real
        return f"cached song draw {ms:.3f} ms/frame"
    check("records: song title layout is cached per song", song_layout_cached)

    def bought_arrives_off():
        """A newly bought record player is placed switched OFF (switching it
        on is what starts the music); lights/appliances still arrive on."""
        from src import build as B
        assert not B._arrives_on("record_player") and B._arrives_on("lamp")
        bm = g.build
        home = g.world.home_furniture
        keep = (g.gold, list(home), len(bm.undo), bm.brush, bm.rot, bm.ci, bm.cur, bm.msg)
        got = {}
        try:
            g.gold = 99999
            for kind in ("record_player", "lamp"):
                bm.brush, bm.rot, bm.ci = kind, 0, 2
                for gy in range(1, 9):
                    for gx in range(1, 13):
                        bm.cur = (gx, gy)
                        n0 = len(g.world.home_furniture)
                        bm.place()
                        if len(g.world.home_furniture) > n0:
                            got[kind] = next(q for q in g.world.home_furniture
                                             if q.kind == kind
                                             and not any(q is k for k in keep[1]))
                            break
                    if kind in got:
                        break
                assert kind in got, f"couldn't place a {kind}: {bm.msg}"
            assert got["record_player"].on is False, "a bought record player arrives ON"
            assert got["lamp"].on is True, "lamps should still arrive switched on"
        finally:
            g.gold = keep[0]
            g.world.home_furniture = home
            home[:] = keep[1]
            del bm.undo[keep[2]:]
            bm.brush, bm.rot, bm.ci, bm.cur, bm.msg = keep[3:]
            g.world.refresh_home_solids()
        return "record player off, lamp on"
    check("records: a bought record player arrives switched off", bought_arrives_off)

    # ------------------------------------------------------------ press checks
    def press_checks():
        """The real (un-gated) press path of the remote, with every exit a
        recorder: a pause the window ignores falls back to the media key even
        after the player is switched off; prev is never double-pressed."""
        saved = (S.gated, S.now_playing, S.app_command, S.media, S.launch,
                 S.VERIFY_WAIT, S.FAST_POLL, S.AFTER_CMD, S.LINGER)
        S.VERIFY_WAIT, S.FAST_POLL, S.AFTER_CMD, S.LINGER = 0.12, 0.02, 0.02, 0.06
        R.want(id(g), False)
        assert R.join(1.0), "remote still busy"
        log = []
        state = [S.Status(True, True, "Artist", "Song A")]
        S.now_playing = lambda: state[0]
        S.app_command = lambda a: log.append(("app", a)) or True
        S.media = lambda a: log.append(("media", a)) or True
        S.launch = lambda uri=None: log.append(("launch", uri)) or "app"
        S.gated = lambda: False                      # every exit above is a recorder
        rs = []
        try:
            def until(cond, secs=1.0):
                end = time.monotonic() + secs
                while time.monotonic() < end and not cond():
                    time.sleep(0.005)
                return cond()
            # X on a playing Spotify whose window ignores the press: the
            # thread outlives the switch-off until the pause is confirmed
            rs.append(S.Remote())
            r = rs[-1]
            r.want("t", True)
            r.send("pause")
            r.want("t", False)
            assert until(lambda: ("media", "play_pause") in log), log
            assert log == [("app", "play_pause"), ("media", "play_pause")], log
            assert r.join(1.0)
            # prev with the song >3 s in: Spotify restarts it (same title)
            log.clear()
            rs.append(S.Remote())
            r = rs[-1]
            r.want("t", True)
            r.send("prev")
            time.sleep(0.2)
            assert log == [("app", "prev")], f"prev pressed twice: {log}"
            # next that changed nothing -> the global key ...
            r.send("next")
            assert until(lambda: ("media", "next") in log), log
            # ... and from then on prev skips the window
            log.clear()
            r.send("prev")
            r.flush()
            assert log == [("media", "prev")], log
            # a play press still unconfirmed at switch-off fires no late key
            log.clear()
            state[0] = S.Status(True, False)
            rs.append(S.Remote())
            r = rs[-1]
            r.want("t", True)
            r.send("toggle")
            r.send("pause")
            time.sleep(0.2)
            assert log == [("app", "play_pause")], f"a late key after switching off: {log}"
            # ... but if that play press still lands after X, it is paused
            # (once) -- the player is off, the music must stop
            log.clear()
            S.VERIFY_WAIT = 0.6
            state[0] = S.Status(True, False)
            rs.append(S.Remote())
            r = rs[-1]
            r.want("t", True)
            r.send("toggle")
            r.send("pause")
            r.want("t", False)
            assert r.flush(1.0)
            assert log == [("app", "play_pause")], log
            state[0] = S.Status(True, True, "Artist", "Late Song")     # the title catches up
            assert until(lambda: len(log) == 2), f"late play not paused: {log}"
            state[0] = S.Status(True, False)                           # the pause lands
            assert r.join(1.5), "thread outlived the late pause"
            assert log == [("app", "play_pause"), ("app", "play_pause")], log
            S.VERIFY_WAIT = 0.12
            # Spotify still starting up (only its helper windows): switching
            # on brings the window up and presses play only once it is there
            log.clear()
            state[0] = S.Status(True, False, ready=False)
            rs.append(S.Remote())
            r = rs[-1]
            r.want("t", True)
            r.send("start", "spotify:")
            assert r.flush(1.0)
            time.sleep(0.1)
            assert log == [("launch", "spotify:")], f"pressed before the window: {log}"
            state[0] = S.Status(True, False)                           # the window is up
            assert until(lambda: ("app", "play_pause") in log), log
        finally:
            for r in rs:
                r.want("t", False)
            for r in rs:
                r.join(1.0)
            (S.gated, S.now_playing, S.app_command, S.media, S.launch,
             S.VERIFY_WAIT, S.FAST_POLL, S.AFTER_CMD, S.LINGER) = saved
        assert S.gated()
    check("records: press checks fall back to media keys (pause even after off)",
          press_checks)

    # ------------------------------------------------------------ text + gate
    def thai_text():
        thai = "\u0e04\u0e27\u0e32\u0e21\u0e23\u0e31\u0e01" * 12
        face, txt = records.song_face(thai)
        if records._face_path("leelawadeeui") or records._face_path("tahoma"):
            assert face != "consolas", "Thai title would render as boxes"
        f = records.song_font(face, 22)
        lines = records.wrap_lines(f, txt, 300, 2)
        assert 1 <= len(lines) <= 2 and all(f.size(ln)[0] <= 300 for ln in lines), lines
        assert records.consolas_ok("Plain ASCII - Title")
        # emoji-only titles: an emoji face if there is one, never tofu; text
        # nothing can draw becomes a note (or nothing, for the artist line)
        emo = "\U0001F3B5\U0001F496"
        ef, et = records.song_face(emo)
        if records._face_path("segoeuiemoji"):
            assert ef == "segoeuiemoji" and et == emo, (ef, et)
        else:
            assert et == emo or et == records.PLACEHOLDER, (ef, et)
        nothing = "\U000F0001\U000F0002"               # private use: no face has these
        assert records.song_face(nothing) == ("consolas", records.PLACEHOLDER)
        assert records.song_face(nothing, placeholder="") == ("consolas", "")
        assert records.song_face("") == ("consolas", records.PLACEHOLDER)
        assert records.consolas_ok(records.PLACEHOLDER), "the note must be drawable"
        return f"face {face}, emoji {ef}"
    check("records: Thai / emoji song text picks a font that has it", thai_text)

    def label_heart():
        """The heart on the record label is solid (no pinhole in the notch)."""
        for w in (17, 40, 64):                       # 17 = the label's own size
            h = records._heart(w, (255, 255, 255))
            # the notch between the lobes, from the centre line down to the tip
            # (the old one let the label show through there: alpha 175..207)
            holes = [y for y in range(int(w * 0.36), int(w * 0.8))
                     if h.get_at((w // 2, y)).a < 250]
            assert not holes, f"{w}px heart has a hole at x={w // 2}, y={holes}"
        big = pygame.transform.scale(records._heart(96, (70, 44, 36)), (192, 192))
        bg = pygame.Surface((192, 192))
        bg.fill((230, 140, 160))
        bg.blit(big, (0, 0))
        g.screen.blit(bg, (0, 0))
        H.shot(g, "records_heart")
    check("records: label heart has no pinhole", label_heart)

    def nothing_external():
        assert not leaks, f"something external ran: {leaks}"
        assert all(c[0] in ("launch", "media", "app") for c in S.CALLS), S.CALLS
    check("records: the safety gate kept everything inside the game", nothing_external)

    S._startfile, S._open_web, S._key, S._post = real
    S.AUTOPLAY_SETTLE, S.FAKE_STATUS, S.FAKE_CLIPBOARD = old
    cleanup()
    S.FAKE_STATUS = old[1]
    g.records_link = old_link
