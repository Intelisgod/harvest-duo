"""Piano domain checks (Home, 2026-09-28): the playable piano screen, its
synth, the song book and the LAN note relays.

run(g, check, H) is called by tools/smoke_test.py (s_domain_tests)."""
import pygame


def run(g, check, H):
    from src.settings import AREA_HOME, MAX_ENERGY
    from src import furniture as F
    from src import piano as PN
    from src.systems import piano_system as PS
    ev = pygame.event.Event
    area0 = g.world.current
    added = []

    def key(k, up=False, scancode=0):
        g._run_state("event", ev(pygame.KEYUP if up else pygame.KEYDOWN, key=k, mod=0,
                                 unicode="", scancode=scancode))

    def tap(k, frames=1):
        key(k)
        for _ in range(frames):
            g._run_state("update", H.DT)
        key(k, up=True)

    def mouse(kind, pos, **kw):
        g._run_state("event", ev(kind, pos=pos, **kw))

    def home_piano():
        if g.world.current != AREA_HOME:
            g.warp(AREA_HOME, H.spawns_by_area(g)[AREA_HOME])
        g.state = "play"
        q = next((q for q in g.world.home_furniture if q.kind == "piano"), None)
        if q is None:
            q = F.Placed("piano", 6, 3, 0, 10)
            g.world.home_furniture.append(q)
            added.append(q)
        return q

    # ---------------------------------------------------------------- play it
    def open_and_play():
        pn = home_piano()
        p = g.players[0]
        p.sitting = None
        p.energy = 10
        g._piano_open(0, pn)
        assert g.state == "piano" and g.piano_ui is not None, g.state
        assert p.energy > 10, "no energy for sitting down to play"
        ui = g.piano_ui
        lo = ui.low
        key(pygame.K_z)
        key(pygame.K_z)                                   # key repeat: no second strike
        assert ui.held == {lo: 1}, ui.held
        key(pygame.K_c)
        key(pygame.K_b)                                   # a C major chord
        assert set(ui.held) == {lo, lo + 4, lo + 7}, ui.held
        assert PN.chord_name(ui.held) == "C major", PN.chord_name(ui.held)
        for _ in range(6):
            g._run_state("update", H.DT)
        g.draw()
        H.shot(g, "piano_chord")
        for k in (pygame.K_z, pygame.K_c, pygame.K_b):
            key(k, up=True)
        assert not ui.held and ui.glow, "keys should light up, then fade"
        # the same note from two keys (',' and Q): released only when both are up
        key(pygame.K_COMMA)
        key(pygame.K_q)
        key(pygame.K_COMMA, up=True)
        assert ui.held.get(lo + 12) == 1
        key(pygame.K_q, up=True)
        assert not ui.held
        # octave shift
        tap(pygame.K_RIGHT)
        assert ui.low == lo + 12, ui.low
        key(pygame.K_q)
        assert lo + 24 in ui.held
        key(pygame.K_q, up=True)
        tap(pygame.K_LEFT)
        assert ui.low == lo
        # a non-Latin layout: the scancode still finds the key cap
        key(0x0E21, scancode=pygame.KSCAN_COMMA)
        assert lo + 12 in ui.held, ui.held
        key(0x0E21, up=True, scancode=pygame.KSCAN_COMMA)
        assert not ui.held
        # mouse: press a black key, drag onto a white one (glissando), let go
        br = ui.key_rect(lo + 6)
        mouse(pygame.MOUSEBUTTONDOWN, br.center, button=1)
        assert lo + 6 in ui.held, ui.held
        wr = ui.key_rect(lo + 9)
        mouse(pygame.MOUSEMOTION, (wr.centerx, wr.bottom - 12), rel=(0, 0), buttons=(1, 0, 0))
        assert lo + 9 in ui.held and lo + 6 not in ui.held, ui.held
        mouse(pygame.MOUSEBUTTONUP, (wr.centerx, wr.bottom - 12), button=1)
        assert not ui.held
        # sustain pedal: released notes keep ringing until the pedal lifts
        key(pygame.K_SPACE)
        tap(pygame.K_x)
        assert ui.pedal and lo + 2 in ui.sus
        key(pygame.K_SPACE, up=True)
        assert not ui.pedal and not ui.sus
        s = ui.syn
        return (f"range {PN.note_name(ui.low)}-{PN.note_name(ui.low + PN.SPAN)}, "
                f"synth {'on' if s.enabled else 'silent'}, {len(s.cache)} notes baked")
    check("piano: keys, chord, octave, mouse, pedal", open_and_play)

    # ---------------------------------------------------------------- the synth
    def synth_fast():
        import time
        s = PN.synth(g.audio)
        t0 = time.perf_counter()
        pcm = s.render(61)
        ms = (time.perf_counter() - t0) * 1000
        assert len(pcm) > s.sr and max(abs(v) for v in pcm) < 32767, "note length / clipping"
        head = max(abs(v) for v in pcm[:4000])
        tail = max(abs(v) for v in pcm[-4000:])
        assert tail < head * 0.2, "a piano note must decay"
        return f"C#4 baked in {ms:.1f} ms"
    check("piano: synth bakes a decaying note", synth_fast)

    # ---------------------------------------------------------------- song book
    def song_book():
        ui = g.piano_ui
        p = g.players[0]
        tap(pygame.K_TAB)
        assert ui.mode == 1 and ui.song["id"] == "twinkle", ui.mode
        g._piano_songs.clear()
        p.energy = 50
        tap(pygame.K_m)                                   # a wrong key: no penalty, no step
        assert ui.song_i == 0
        n = 0
        while ui.target() is not None and n < 200:
            tap(ui.key_for(ui.shown(ui.target())))
            n += 1
            if n == 9:
                g.draw()
                H.shot(g, "piano_song")
        assert n == len(ui.song["notes"]) and ui.done_t > 0, (n, ui.done_t)
        assert p.energy == min(MAX_ENERGY, 50 + PS.SONG_REWARD), p.energy
        g.draw()
        H.shot(g, "piano_song_done")
        for _ in range(240):                              # celebration, then it starts over
            g._run_state("update", H.DT)
        assert ui.done_t == 0 and ui.song_i == 0
        # the same song again today: lovely, but no more energy
        assert g._piano_reward(0, "twinkle") == "" and p.energy == min(MAX_ENERGY, 50 + PS.SONG_REWARD)
        # listen first: the piano plays the melody itself
        tap(pygame.K_TAB)
        tap(pygame.K_RETURN)
        assert ui.demo is not None
        for _ in range(75):
            g._run_state("update", H.DT)
        assert ui.demo["i"] >= 2, ui.demo
        tap(pygame.K_z)                                   # playing yourself stops the demo
        assert ui.demo is None and ui.song_i == 0
        tap(pygame.K_TAB)
        tap(pygame.K_TAB)
        tap(pygame.K_TAB)
        assert ui.mode == 0, ui.mode
        return f"twinkle: {n} notes"
    check("piano: song book (play one through, listen)", song_book)

    def roll_cut_short():
        """A new page / Listen / Esc while the finished-song chord is still
        rolling lets its keys come up (nothing held, glowing or named on the
        sheet); the song's hearts wait for the lid -- the room is frozen under
        the page -- and then burst once."""
        if g.piano_ui is None or g.state != "piano":
            g._piano_open(0, home_piano())
        ui = g.piano_ui
        s = ui.syn

        def finish(mode):
            ui.set_mode(mode)
            n = 0
            while ui.target() is not None and n < 200:
                tap(ui.key_for(ui.shown(ui.target())))
                n += 1
            assert ui.done_t > 0, ("song not finished", n)
            for _ in range(18):                           # ~0.3 s: the chord is half rolled
                g._run_state("update", H.DT)
            down = [r[1] for r in ui.roll if r[2] == 1]
            assert down and set(down) <= set(ui.held), (ui.roll, ui.held)
            return down

        def hearts():
            return sum(1 for q in g.parts.items if getattr(q, "heart", False))
        g._piano_hearts = None
        h0 = hearts()
        # a new page mid-flourish (Up: back to free play, whose sheet names chords)
        down = finish(1)
        key(pygame.K_UP)
        key(pygame.K_UP, up=True)
        assert ui.mode == 0 and not ui.roll, (ui.mode, ui.roll)
        assert not ui.held and not ui.src, ("roll keys stuck down", ui.held, ui.src)
        if s.enabled:
            assert not any(m in s.voices for m in down), ("roll notes still sounding", s.voices)
        for _ in range(30):
            g._run_state("update", H.DT)
        assert not ui.held and not ui.glow, (ui.held, ui.glow)
        assert PN.chord_name(ui.held) == "", "the sheet still names the celebration chord"
        g.draw()
        H.shot(g, "piano_roll_cut")
        # Listen mid-flourish: the melody plays on its own
        finish(3)
        tap(pygame.K_RETURN)
        assert ui.demo is not None and not ui.roll, (ui.demo, ui.roll)
        assert not any(k[0] == "roll" for k in ui.src), ui.src
        ui.listen()                                       # (stop the demo again)
        # the room stayed frozen: no hearts piled up in it meanwhile
        assert hearts() == h0, ("hearts spawned into the frozen room", h0, hearts())
        assert g._piano_hearts == 0, g._piano_hearts
        # Esc mid-flourish: the keys come up, then ONE burst as the lid shuts
        finish(1)
        key(pygame.K_ESCAPE)
        assert not ui.held and not ui.roll, (ui.held, ui.roll)
        for _ in range(30):
            if g.state != "piano":
                break
            g._run_state("update", H.DT)
        assert g.state == "play" and g.piano_ui is None, g.state
        assert g._piano_hearts is None
        if g.world.current == AREA_HOME and hasattr(g.parts, "heart_burst"):
            assert hearts() == h0 + 12, ("one burst of 12 hearts on close", h0, hearts())
        return f"page / listen / Esc mid-roll: keys up; {hearts() - h0} hearts on close"
    check("piano: celebration chord cut short (no stuck keys), hearts on close", roll_cut_short)

    # ---------------------------------------------------------------- LAN relays
    def lan_relays():
        pn = home_piano()
        p2 = g.players[1]
        p2_was = (p2.x, p2.y, p2.sitting, p2.fx, p2.fy)
        try:
            return _lan_relays(pn)
        finally:                                          # (an "open" may seat P2)
            p2.x, p2.y, p2.sitting, p2.fx, p2.fy = p2_was

    def _lan_relays(pn):
        menu, fx = [], []
        g._piano_rate = {}
        g._net_send_menu = lambda d: menu.append(dict(d))
        g._net_send_fx = lambda kind, **d: fx.append((kind, d))
        mode0 = g.net_mode
        try:
            # client: notes go to the host as menu ops
            cui = PN.PianoScreen(g, 1, pn, client=True)
            cui.press(64, ("k", pygame.K_e))
            cui.release(("k", pygame.K_e))
            assert {"m": "piano", "n": 64, "gx": pn.gx, "gy": pn.gy} in menu, menu
            assert {"m": "piano", "off": 64} in menu, menu
            # host: P1's notes go to the client as fx
            g.net_mode = "host"
            hui = PN.PianoScreen(g, 0, pn)
            hui.press(67, ("k", pygame.K_t))
            hui.release(("k", pygame.K_t))
            assert ("piano", {"n": 67, "gx": pn.gx, "gy": pn.gy}) in fx, fx
            assert ("piano", {"off": 67}) in fx, fx
            # host: P1 sitting down tells the client to warm up its synth
            g._piano_open(0, pn)
            assert ("piano", {"op": "open"}) in fx, fx
            g.piano_ui.close()
            for _ in range(30):
                g._run_state("update", H.DT)
            assert g.state == "play" and g.piano_ui is None, g.state
        finally:
            g.net_mode = mode0
            del g._net_send_menu
            del g._net_send_fx
        # receiving: only piano ops are ours, junk is ignored, numbers clamped
        assert g._net_menu_piano("fridge", {}) is False
        assert g._net_menu_piano("piano", {"m": "piano", "n": "junk"}) is True
        assert g._net_menu_piano("piano", {"m": "piano", "n": 10 ** 9}) is True
        assert g._net_menu_piano("piano", {"m": "piano", "off": None}) is True
        assert g._net_fx_piano({"kind": "boom"}) is False
        assert g._net_fx_piano({"kind": "piano", "n": 60, "gx": pn.gx, "gy": pn.gy}) is True
        assert g._net_fx_piano({"kind": "piano", "off": 60}) is True
        assert PN.clamp_midi(10 ** 9) == PN.HIGH_MIDI and PN.clamp_midi(-5) == PN.LOW_MIDI
        assert PN.clamp_midi("60") is None and PN.clamp_midi(True) is None
        # the partner sitting down prewarms THIS machine's synth (host: menu op,
        # client: fx), but only for a farmer in the house who will hear it
        s = PN.synth(g.audio)
        warm = []
        s.prewarm = lambda ms: warm.append(list(ms))      # (the real one: a daemon thread)
        try:
            g._net_menu_piano("piano", {"m": "piano", "op": "open", "gx": pn.gx, "gy": pn.gy})
            assert len(warm) == 1 and warm[0] == PN.warm_order(), warm
            assert g._net_fx_piano({"kind": "piano", "op": "open"}) is True
            assert len(warm) == 2, "the client didn't prewarm when P1 sat down"
            order = warm[0]
            assert order[0] == PN.midi_of("D4") and len(order) == len(set(order)), order
            assert set(PN.ROLL_CHORD) <= set(order), "the celebration chord isn't warmed"
            g._piano_can_hear = lambda: False             # out in the fields
            try:
                g._net_menu_piano("piano", {"m": "piano", "op": "open", "gx": pn.gx, "gy": pn.gy})
                g._net_fx_piano({"kind": "piano", "op": "open"})
            finally:
                del g._piano_can_hear
            assert len(warm) == 2, "prewarmed for a farmer who can't hear the piano"
            # walked in while they were already playing: the first cold note warms
            # the rest, from that very note outwards (see bake_on_enter too)
            cold = [m for m in range(PN.LOW_MIDI, PN.HIGH_MIDI + 1) if m not in s.cache]
            if s.enabled and cold:
                g._piano_hear(cold[0], True, pn)
                g._piano_hear(cold[0], False)
                assert warm[-1] == PN.warm_around(cold[0]), warm[2:]
                n = len(warm)
                g._piano_hear(cold[0], True, pn)          # baked now: nothing more to do
                g._piano_hear(cold[0], False)
                assert len(warm) == n, warm[n:]
        finally:
            del s.prewarm
        # a flood of notes is rate-limited
        g._piano_rate = {}
        ok = sum(1 for _ in range(200) if g._piano_rate_ok("in"))
        assert ok <= PS._BURST + 2, ok
        # the host pays P2's energy: sitting down, and a song once a day
        p2 = g.players[1]
        p2.energy = 40
        g._net_menu_piano("piano", {"m": "piano", "op": "open", "gx": pn.gx, "gy": pn.gy})
        assert p2.energy > 40, "no energy for the client sitting down to play"
        g._piano_songs.clear()
        p2.energy = 40
        g._net_menu_piano("piano", {"m": "piano", "op": "song", "song": "mary"})
        g._net_menu_piano("piano", {"m": "piano", "op": "song", "song": "mary"})
        g._net_menu_piano("piano", {"m": "piano", "op": "song", "song": "<junk>"})
        assert p2.energy == 40 + PS.SONG_REWARD, p2.energy
        return f"{len(menu)} menu ops, {len(fx)} fx, flood capped at {ok}"
    check("piano: LAN relays (client menu / host fx / junk / flood)", lan_relays)

    # ---------------------------------------------------------------- leaving
    def leave():
        pn = home_piano()
        p = g.players[0]
        bench = F.Placed("piano_bench", pn.gx, pn.gy + 1, 0, 10)
        seat = (bench, pn.gx + 0.5, pn.gy + 1.5)
        p.sitting = seat
        g.state = "play"                                  # left without closing the lid above:
        g._on_update_piano(H.DT)                          # the safety net un-ducks the music
        assert not g._piano_hushed
        ch = getattr(g.audio, "music_chan", None)
        v0 = ch.get_volume() if ch is not None else None
        g._piano_open(0, pn, seated=True)
        assert g.state == "piano"
        if v0:
            assert ch.get_volume() < v0 * 0.5, "the background loop should hush while playing"
        tap(pygame.K_z)
        key(pygame.K_ESCAPE)
        for _ in range(30):
            g._run_state("update", H.DT)
        assert g.state == "play" and g.piano_ui is None, g.state
        assert p.sitting is seat, "Esc must leave the farmer on the bench"
        if v0:
            assert abs(ch.get_volume() - v0) < 0.02, (ch.get_volume(), v0)
        p.sitting = None
        g._piano_open(0, pn)
        key(pygame.K_BACKSPACE)
        for _ in range(30):
            g._run_state("update", H.DT)
        assert g.state == "play"
        g.state = "piano"                                 # no screen: falls back to play
        g._run_state("event", ev(pygame.KEYDOWN, key=pygame.K_z, mod=0, unicode="", scancode=0))
        assert g.state == "play"
    check("piano: Esc / Backspace close (seated stays seated)", leave)

    # ---------------------------------------------------------------- review fixes
    def pedal_voices():
        """Under the pedal only rings that still sound count (no fading
        piano), and lifting it never damps a key that is held down."""
        pn = home_piano()
        g._piano_open(0, pn)
        ui, s = g.piano_ui, g.piano_ui.syn
        lo = ui.low
        out = "synth silent: voice checks skipped"
        if s.enabled and s._pool():
            for k in list(s.voices):                      # the LAN junk check never sent
                s.note_off(k, 1)                          # its partner's note-off
            key(pygame.K_SPACE)
            vols = []
            for k in (pygame.K_q, pygame.K_w, pygame.K_e, pygame.K_r, pygame.K_t, pygame.K_y) * 4:
                key(k)
                m = ui.src[("k", k)]
                ch = s.voices[m][0]
                vols.append(ch.get_volume())
                key(k, up=True)
                ch.stop()                                 # ... and that ring has died away
            assert s.active() == 0, (s.active(), s.voices, s.ringing)
            assert min(vols) >= max(vols) * 0.8 - 2 / 128, ("pedal made the piano fade", vols)
            # a string rung out under the pedal, struck again and HELD: pedal-up keeps it
            key(pygame.K_q)
            m = lo + 12
            v1 = s.voices[m]
            key(pygame.K_q, up=True)
            v1[0].stop()
            key(pygame.K_q)
            v2 = s.voices[m]
            assert all(PN._cid(r[0]) != PN._cid(v2[0]) for r in s.ringing), \
                "a stale ring still points at the held key's channel"
            key(pygame.K_SPACE, up=True)
            assert s._sounding(v2), "pedal-up damped a key that is still held"
            key(pygame.K_q, up=True)
            # re-striking a pedalled string replaces its ring (one voice per string)
            key(pygame.K_SPACE)
            tap(pygame.K_e)
            tap(pygame.K_e)
            assert len([v for v in s.ringing if s._sounding(v)]) <= 1, s.ringing
            key(pygame.K_SPACE, up=True)
            out = f"{len(vols)} pedalled notes, vol {min(vols):.3f}..{max(vols):.3f}"
        # the room is frozen under the piano screen: no notes pile up there
        n0 = len(g.parts.items)
        for k in (pygame.K_z, pygame.K_x, pygame.K_c, pygame.K_v) * 5:
            tap(k)
        assert len(g.parts.items) <= n0, (n0, len(g.parts.items))
        # Enter stops the demo: the bottom hint says so too
        tap(pygame.K_TAB)
        ui.listen()
        assert ("Enter", "Stop") in ui.hint_pills(), ui.hint_pills()
        ui.listen()
        assert ("Enter", "Listen") in ui.hint_pills(), ui.hint_pills()
        key(pygame.K_ESCAPE)
        for _ in range(30):
            g._run_state("update", H.DT)
        assert g.state == "play"
        # ... while out in the room, a partner's note does float off the lid
        n0 = len(g.parts.items)
        g._piano_hear(60, True, pn)
        g._piano_hear(60, False)
        assert len(g.parts.items) > n0, "no note over the piano"
        return out
    check("piano: pedal voices, frozen-room notes, hint pills", pedal_voices)

    def music_duck():
        """The hush follows the record player's Spotify duck, and a reset
        (the host quitting mid-song) gives the loop back."""
        pn = home_piano()
        a = g.audio
        ch = getattr(a, "music_chan", None)
        sd = getattr(a, "set_music_duck", None)
        if ch is None or sd is None:
            return "no music channel: skipped"

        def level():
            k = 0.10 if getattr(a, "_song_duck", False) else 1.0
            return a.master * a.music_vol * a.music_duck * k
        full = level()
        g._piano_open(0, pn)
        assert abs(ch.get_volume() - full * PS._HUSH) < 0.01, (ch.get_volume(), full)
        sd(0.25)                                          # Spotify starts meanwhile
        g._run_state("update", H.DT)
        assert abs(ch.get_volume() - level() * PS._HUSH) < 0.01, ch.get_volume()
        key(pygame.K_ESCAPE)
        for _ in range(30):
            g._run_state("update", H.DT)
        assert g.state == "play"
        assert abs(ch.get_volume() - level()) < 0.01, ("lid closed over Spotify", ch.get_volume())
        sd(1.0)
        assert abs(ch.get_volume() - full) < 0.01, ch.get_volume()
        # a reset while playing (LAN host quit) must not leave the loop hushed
        songs = dict(g._piano_songs)
        g._piano_open(0, pn)
        assert ch.get_volume() < full * 0.5
        g._on_reset_piano()
        g._piano_songs.update(songs)
        g.state = "play"
        assert abs(ch.get_volume() - full) < 0.01, ("still hushed after reset", ch.get_volume())
        assert g.piano_ui is None and not g._piano_hushed
        return f"loop {full:.3f} -> {full * PS._HUSH:.3f} while playing"
    check("piano: music hush follows Spotify duck, survives reset", music_duck)

    # ---------------------------------------------------------------- round-2 fixes
    def lan_seat():
        """LAN client's Action at the piano: the host seats P2 on the free
        bench right at it, facing the keys (like a local press); the SIT
        snapshot carries the seat and the client's screen follows it (Esc
        then keeps P2 sitting). No free bench / too far away: P2 stays up,
        and the log never claims they sat."""
        from src.settings import TILE
        pn = home_piano()
        p1, p2 = g.players
        was = [(p.x, p.y, p.sitting, p.fx, p.fy, p.energy) for p in (p1, p2)]
        mode0 = g.net_mode
        bench = g._home_bench_for(pn)
        if bench is None:
            bench = F.Placed("piano_bench", pn.gx + 1, pn.gy + 1, 0, 10)
            bench.ox = -0.5
            g.world.home_furniture.append(bench)
            added.append(bench)
        p1.sitting = p2.sitting = None
        stand = ((bench.gx + bench.ox + 0.5) * TILE, (bench.gy + bench.oy + 1.5) * TILE)
        g._net_send_menu = lambda d: None
        g._net_send_fx = lambda kind, **d: None

        def last_logs(n=3):
            return [m[0] for m in g.ui.messages[-n:]]
        try:
            g.net_mode = "host"
            p2.x, p2.y = stand
            g._net_menu_piano("piano", {"m": "piano", "op": "open", "gx": pn.gx, "gy": pn.gy})
            sit = p2.sitting
            assert sit and sit[0] is bench, ("P2 was not seated on the bench", sit)
            assert g._home_piano_by(sit[1], sit[2])[0] is pn
            assert any(f"{p2.name} sits down to" in t for t in last_logs()), last_logs()
            rows = g._net_snap_out_home()["SIT"]
            assert any(r[0] == 1 and (r[1], r[2]) == (bench.gx, bench.gy) for r in rows), rows
            # the client's screen: seated once the seat arrives -> Esc keeps it
            cui = PN.PianoScreen(g, 1, pn, client=True)
            assert not cui.seated
            cui.update(H.DT)
            assert cui.seated and ("Esc", "Stop playing") in cui.hint_pills(), cui.hint_pills()
            cui.close()
            for _ in range(20):
                cui.update(H.DT)
            assert p2.sitting is sit, "Esc stood the seated client farmer up"
            # no free bench: P2 plays standing, and the log says so
            p2.sitting = None
            p2.x, p2.y = stand
            g._home_bench_for = lambda piano, p=None: None
            try:
                g._net_menu_piano("piano", {"m": "piano", "op": "open", "gx": pn.gx, "gy": pn.gy})
            finally:
                del g._home_bench_for
            assert p2.sitting is None
            logs = last_logs(1)
            assert "sits down" not in logs[0] and f"{p2.name} steps up to" in logs[0], logs
            # a stale "open" from across the room never teleports P2 onto the bench
            p2.x, p2.y = stand[0] + 9 * TILE, stand[1] + 6 * TILE
            g._net_menu_piano("piano", {"m": "piano", "op": "open", "gx": pn.gx, "gy": pn.gy})
            assert p2.sitting is None, p2.sitting
            # client side: a free bench -> "sits down" is the guess, and the screen
            # stands corrected if the seat never arrives
            g.net_mode = "client"
            p2.x, p2.y = stand
            g._piano_open(1, pn, client=True)
            ui = g.piano_ui
            assert ui.client and ui.seated and "sits down" in last_logs(1)[0], last_logs()
            for _ in range(int(2.5 / H.DT)):
                g._run_state("update", H.DT)
            assert not ui.seated and ("Esc", "Leave") in ui.hint_pills(), ui.hint_pills()
            key(pygame.K_ESCAPE)
            for _ in range(30):
                g._run_state("update", H.DT)
            assert g.state == "play" and g.piano_ui is None, g.state
        finally:
            g.net_mode = mode0
            del g._net_send_menu
            del g._net_send_fx
            for p, w in zip((p1, p2), was):
                p.x, p.y, p.sitting, p.fx, p.fy, p.energy = w
        return "P2 seated on the bench facing the keys; standing / far away: not seated"
    check("piano: LAN client sits on the bench (host seats P2), Esc keeps sitting", lan_seat)

    def bake_on_enter():
        """Walking into a house with a piano bakes EVERY key once, on the
        daemon thread (keys on screen first) -- also inside an area context,
        whose audio is a no-op sink. A partner's cold note warms the piano
        from that note outwards; mid-frame, a cold note is a quick stand-in."""
        import time
        from src.systems import areactx_system as AX
        from src.settings import AREA_FARM
        pn = home_piano()
        s = PN.synth(g.audio)
        t0 = time.monotonic()
        while s._busy and time.monotonic() - t0 < 15:     # the house's own bake: let it end
            time.sleep(0.02)
        real = g.audio
        calls = []
        s.prewarm = lambda ms: calls.append(list(ms))
        m = 90
        saved = s.cache.pop(m, None)
        was_quick = m in s.quick
        s.quick.discard(m)
        try:
            g._on_area_enter_piano()
            assert len(calls) == 1, calls
            order = calls[0]
            assert order == PN.warm_order(), order[:8]
            assert sorted(order) == list(range(PN.LOW_MIDI, PN.HIGH_MIDI + 1)), "not the whole piano"
            vis = PN.warm_order(full=False)
            assert order[:len(vis)] == vis, "the keys on screen must bake first"
            g.audio = AX._Sink(real)                      # a partner's area context
            g._on_area_enter_piano()
            g.audio = real
            assert len(calls) == 2, "the area context's sink swallowed the bake"
            sp = H.spawns_by_area(g)
            g.warp(AREA_FARM, sp[AREA_FARM])
            assert len(calls) == 2, "baked the piano out on the farm"
            g.warp(AREA_HOME, sp[AREA_HOME])
            assert len(calls) == 3 and calls[2] == PN.warm_order(), "entering the house didn't bake"
            # the partner plays a note we haven't baked (walked in mid-song)
            n0 = len(calls)
            g._piano_hear(m, True, pn)
            g._piano_hear(m, False)
            assert calls[-1] == PN.warm_around(m), calls[n0:]
            near = calls[-1][:13]
            assert near[0] == m and set(range(84, 96)) <= set(near), near  # its octave first
            if s.enabled:
                assert m in s.cache and m in s.quick and not s.baked(m), "no quick stand-in"
                assert [m] in calls[n0:], "the full note wasn't queued first"
                sr = s.sr
                q = s.render(m, secs=PN.QUICK_SECS)
                assert len(q) == int(sr * PN.QUICK_SECS) and abs(q[-1]) < 50, len(q)
        finally:
            g.audio = real
            del s.prewarm
            s.quick.discard(m)
            if saved is not None:
                s.cache[m] = saved
            else:
                s.cache.pop(m, None)
            if was_quick:
                s.quick.add(m)
        return f"{len(calls[0])} keys queued on entering the house; cold F#6 -> {calls[-1][:5]}..."
    check("piano: whole piano baked on entering the house; listener warms around a cold note",
          bake_on_enter)

    def headroom():
        """At master 1.0 x sfx 1.0 a 6-note chord stays under 0 dBFS (SDL
        just clamps the sum of the voices); the notes of a chord share one
        level; a single note is untouched and still nicely loud."""
        import math
        s = PN.synth(g.audio)
        if not (s.enabled and s._pool()):
            return "synth silent: skipped"
        a = getattr(g.audio, "_real", None) or g.audio
        vol0 = (a.master, a.sfx_vol)
        pcm = {}
        N = 4000

        def quiet():
            s.voices.clear()
            s.ringing = []
            for c in s._pool():
                c.stop()

        def strike(ms):
            quiet()
            for m in ms:
                assert s.note_on(("hr", m), m, 1.0)
            vols = {m: s.voices[("hr", m)][0].get_volume() for m in ms}
            quiet()
            out = [0.0] * N
            for m in ms:
                p = pcm.get(m)
                if p is None:
                    p = pcm[m] = s.render(m, secs=0.5)[:N]
                for i, x in enumerate(p):
                    out[i] += x * vols[m]
            return max(abs(x) for x in out), vols
        try:
            a.master, a.sfx_vol = 1.0, 1.0
            assert s.render(60, secs=0.5)[:N] == s.render(60)[:N]   # (the quick render is exact)
            pk1, v1 = strike([60])
            assert v1[60] > 0.99, ("a lone note got quieter", v1)
            assert pk1 > 8000, ("a single note is too quiet", pk1)
            worst = 0.0
            for ch in ((48, 55, 60, 64, 67, 72), (65, 66, 67, 68, 69, 70),
                       (36, 48, 60, 72, 84, 96), (60, 64, 67, 72, 76, 79), (55, 59, 62, 65, 67, 71)):
                pk, vols = strike(ch)
                assert len(set(vols.values())) == 1, ("a chord's notes got different levels", vols)
                assert pk < 32767 * 0.95, ("6-note chord clips at full volume",
                                           [PN.note_name(m) for m in ch], pk)
                worst = max(worst, pk)
            # at the default volume the same chord is barely touched
            a.master, a.sfx_vol = 0.8, 0.9
            pk, vols = strike((60, 64, 67))
            assert min(vols.values()) >= 0.8 * 0.9 - 2 / 128, ("a triad was hushed", vols)
        finally:
            a.master, a.sfx_vol = vol0
            quiet()
        return (f"single C4 peak {20 * math.log10(pk1 / 32767):+.1f} dBFS at full volume; "
                f"worst 6-note chord {20 * math.log10(worst / 32767):+.1f} dBFS")
    check("piano: headroom (6-note chord at full volume never clips)", headroom)

    def tails():
        """Held / pedalled notes ring out and fade gently (no 60 ms cut while
        still loud); the whole piano stays a sensible size."""
        import math
        s = PN.synth(g.audio)
        sr = s.sr

        def rms(x):
            return math.sqrt(sum(v * v for v in x) / max(1, len(x)))
        for m in (PN.LOW_MIDI, 60, 84, PN.HIGH_MIDI):
            assert 0.3 <= PN.note_fade(m) <= 0.5, (m, PN.note_fade(m))
            assert PN.note_secs(m) >= PN.TAIL_MIN
        mb = sum(PN.note_secs(m) for m in range(PN.LOW_MIDI, PN.HIGH_MIDI + 1)) * 44100 * 2 / 1e6
        assert mb < 32, f"the baked piano is {mb:.0f} MB (mono)"
        out = []
        for m in (48, 60, 79):
            pcm = s.render(m)
            n, W, fl = len(pcm), int(0.05 * sr), int(PN.note_fade(m) * sr)
            assert n >= 3.0 * sr, (m, n / sr)
            db = 20 * math.log10(rms(pcm[n - fl - W:n - fl]) / rms(pcm[:W]))
            assert db < -24, (PN.note_name(m), f"still {db:.1f} dB when the fade starts")
            q = fl // 4
            assert rms(pcm[n - q:]) < 0.3 * rms(pcm[n - fl:n - fl + q]), "the end fade is a cut"
            assert max(abs(v) for v in pcm[-int(0.005 * sr):]) < 40
            out.append(f"{PN.note_name(m)} {n / sr:.1f}s {db:+.0f}dB")
        return ", ".join(out) + f"; whole piano {mb:.0f} MB mono"
    check("piano: long natural tails with a soft final fade", tails)

    def labels():
        """A lone note never reads like a chord symbol (C7, C6...)."""
        assert PN.held_label({96: 1}) == ("note", "note C7"), PN.held_label({96: 1})
        assert PN.held_label({84: 1}) == ("note", "note C6")
        assert PN.held_label({60: 1, 64: 1, 67: 1}) == ("chord", "C major")
        assert PN.held_label({60: 1, 67: 1}) == ("chord", "perfect 5th")
        assert PN.held_label({60: 1, 61: 1, 62: 1}) == ("notes", "notes C4  C#4  D4")
        assert PN.held_label({}) == ("", "")
        pn = home_piano()
        g._piano_open(0, pn)
        ui = g.piano_ui
        while ui.base < PN.BASE_MAX:
            tap(pygame.K_RIGHT)
        key(pygame.K_i)                                   # the top row's I: C7
        assert set(ui.held) == {96}, ui.held
        for _ in range(25):                               # (the lid all the way open)
            g._run_state("update", H.DT)
        g.draw()
        H.shot(g, "piano_single_note")
        key(pygame.K_i, up=True)
        key(pygame.K_ESCAPE)
        for _ in range(30):
            g._run_state("update", H.DT)
        assert g.state == "play"
        return "note C7 / C major / notes C4 C#4 D4"
    check("piano: single notes are labelled as notes, not chords", labels)

    for q in added:
        if q in g.world.home_furniture:
            g.world.home_furniture.remove(q)
    if g.world.current != area0:
        sp = H.spawns_by_area(g).get(area0)
        if sp:
            g.warp(area0, sp)
    g.state = "play"
