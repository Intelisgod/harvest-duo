"""UI & Rendering domain checks (Chat 6): journal, HUD, toasts, warp card,
title screen, world render caches, gallery registries.

run(g, check, H) is called by tools/smoke_test.py (s_domain_tests)."""
import pygame


def _key(g, k):
    g._run_state("event", pygame.event.Event(pygame.KEYDOWN, key=k, mod=0,
                                             unicode="", scancode=0))


def run(g, check, H):
    from src.settings import JOURNAL_KEY, SCREEN_W, SCREEN_H

    # ---------------------------------------------------------------- journal
    def journal_open_close():
        g.state = "play"
        assert g._first_hook("_on_keydown_", JOURNAL_KEY), "J not consumed"
        assert g.state == "journal", g.state
        tabs = g._journal_tabs()
        assert tabs and tabs[0]["title"] == "Guide", [t["title"] for t in tabs]
        g._run_state("update", H.DT)
        g.draw()
        H.shot(g, "ui_journal_guide")
        _key(g, pygame.K_ESCAPE)
        assert g.state == "play", g.state
        return f"{len(tabs)} tabs: {[t['title'] for t in tabs]}"
    check("journal open/close", journal_open_close)

    def journal_tabs_cycle():
        g.journal_open()
        n = len(g._journal_tabs())
        seen = set()
        for k in (pygame.K_e, pygame.K_PERIOD, pygame.K_RIGHT, pygame.K_q,
                  pygame.K_COMMA, pygame.K_LEFT) * max(1, n):
            _key(g, k)
            for _ in range(3):
                g._run_state("update", H.DT)
            g.draw()
            seen.add(g._jr_idx)
            assert g.state == "journal"
        for i in range(n):
            g._jr_idx = i
            g._jr_flip = 0.0
            g.draw()
            H.shot(g, f"ui_journal_tab{i}")
        _key(g, JOURNAL_KEY)
        assert g.state == "play"
        return f"visited {len(seen)}/{n}"
    check("journal tab cycling", journal_tabs_cycle)

    def journal_bad_tab():
        import os
        g.journal_open()
        g._jr_tabs.append({"title": "Broken", "draw": lambda s, r: 1 / 0})
        g._jr_idx = len(g._jr_tabs) - 1
        old = os.environ.get("HD_STRICT_HOOKS")
        os.environ["HD_STRICT_HOOKS"] = "0"
        try:
            g.draw()                        # must not raise
        finally:
            if old is None:
                os.environ.pop("HD_STRICT_HOOKS", None)
            else:
                os.environ["HD_STRICT_HOOKS"] = old
        _key(g, pygame.K_ESCAPE)
        assert g.state == "play"
    check("journal tab error is contained", journal_bad_tab)

    # ---------------------------------------------------------------- HUD
    def hud_buffs_toasts_log():
        g.state = "play"
        p0, p1 = g.players
        p0.add_buff("speed", 30, 0.2, "Coffee")
        p0.add_buff("luck", 200, 0.1, "Clover")
        p1.add_buff("combat", 4, 0.2, "Spicy")
        p1.add_buff("mystery_kind", 12, 1.0, "???")
        g.fortune[0] = "lucky"
        g.fortune[1] = "unlucky"
        g.toast("Achievement!", "First harvest", icon="parsnip", color=(255, 214, 120))
        g.toast("New record", "Carp 42 cm", icon=None)
        g.toast("Unlocked", "", icon=pygame.Surface((10, 10)))
        for i in range(6):
            g.ui.log(f"Test message number {i} - the feed stays tidy")
        g.gold += 250
        H.frames(g, 20, draw_every=5)
        g.draw()
        H.shot(g, "ui_hud_busy")
        assert len(g.toasts) >= 1
        H.frames(g, 300)
        assert not g.toasts, "toasts should expire"
        p0.buffs.clear()
        p1.buffs.clear()
        g.fortune[0] = g.fortune[1] = None
    check("hud buffs + toasts + log feed", hud_buffs_toasts_log)

    def weather_icons():
        from src import assets
        for w in ("sunny", "rain", "snow", "storm", "fog", "windy", "weird"):
            assert assets.hud.weather_icon(w, 22).get_width() == 22
        for s in ("Spring", "Summer", "Fall", "Winter"):
            assets.hud.season_icon(s)
        old = g.weather
        for w in ("storm", "fog", "windy"):
            g.weather = w
            g.draw()
        g.weather = old
    check("weather + season icons", weather_icons)

    def hotbar_tag():
        g.state = "play"
        p = g.players[0]
        p.inv.cycle(1)
        H.frames(g, 3)
        assert 0 in g._sel_tags, "selection change should show a name tag"
        g.draw()
        p.inv.cycle(-1)
        H.frames(g, 120)
        assert 0 not in g._sel_tags
    check("hotbar selection name tag", hotbar_tag)

    def sleep_and_crops():
        from src import assets
        for st in range(4):
            assets.crop_sprite(st, (200, 120, 90))
        assets.crop_sprite(1, (200, 120, 90), dead=True)
        for s in ("Spring", "Summer", "Fall", "Winter", None):
            assert len(assets.tree_frames(s)) == 5
        g.state = "play"
        g.ui.draw_center_banner(g.screen, "Sleeping...", "Spring 2   6:00 AM")
        H.shot(g, "ui_sleep_banner")
        # the cached ground layer rebuilds per season without errors
        old = g.time.season_idx
        for si in range(4):
            g.time.season_idx = si
            g.draw()
        g.time.season_idx = old
        g.draw()
    check("sleep banner + crop/tree sprites + seasonal ground", sleep_and_crops)

    # ---------------------------------------------------------------- warp card
    def warp_card():
        sp = H.spawns_by_area(g)
        for area in list(sp)[:3]:
            g.warp(area, sp[area])
            assert g._area_card and g._area_card[0] == area.replace("_", " ").title()
            H.frames(g, 8)
            g.draw()                       # iris still opening
        H.shot(g, "ui_warp_card")
        H.frames(g, 200)
        assert g._area_card is None, "title card must fade out"
        g.emit("warp", area="some_new_area")
        assert g._area_card[1], "generic subtitle fallback"
        g._area_card = None
    check("warp iris + area title card", warp_card)

    # ---------------------------------------------------------------- menu / gallery
    def title_screen():
        g.state = "menu"
        g.menu.page = "main"
        g.menu.trans = 1.0
        g.menu.update(H.DT)
        g.draw()
        # first frame must already be bright (no black fade-in)
        px = g.screen.get_at((SCREEN_W // 2, 40))
        assert sum(px[:3]) > 200, f"menu first frame too dark: {px}"
        for _ in range(30):
            g.menu.update(0.5)
        g.draw()
        H.shot(g, "ui_menu_later")
        g.state = "play"
    check("title screen bright + animated", title_screen)

    def gallery_registries():
        from src import gallery, assets, loot
        gal = gallery.GalleryScreen(g, on_close=lambda: None)
        names = {n for c in gal._entries.values() for n, *_ in c}
        miss = [k for k in assets.PROPS if gallery._title(k) not in names]
        assert not miss, f"props missing from gallery: {miss[:5]}"
        missm = [k for k in loot.MATERIALS if gallery._title(k) not in names
                 and loot.MATERIALS[k].get("label") not in names]
        assert not missm, f"materials missing: {missm[:5]}"
        return f"{sum(len(v) for v in gal._entries.values())} models"
    check("gallery derives from registries", gallery_registries)

    # ---------------------------------------------------------------- fix round (review findings)
    from src.settings import P1_KEYS, P2_KEYS

    def journal_yields_to_bindings():
        g.state = "play"
        old = P1_KEYS["action"]
        P1_KEYS["action"] = JOURNAL_KEY               # WASD + J for Use
        try:
            assert not g._on_keydown_ui_journal(JOURNAL_KEY), "journal stole a bound key"
            assert g.state == "play", g.state
        finally:
            P1_KEYS["action"] = old
        old = P2_KEYS.get("emote")
        P2_KEYS["emote"] = JOURNAL_KEY
        try:
            assert not g._on_keydown_ui_journal(JOURNAL_KEY)
        finally:
            if old is None:
                P2_KEYS.pop("emote", None)
            else:
                P2_KEYS["emote"] = old
        assert g._on_keydown_ui_journal(JOURNAL_KEY) and g.state == "journal"
        _key(g, pygame.K_ESCAPE)
        assert g.state == "play"
    check("journal hotkey yields to player bindings", journal_yields_to_bindings)

    def menu_rejects_reserved_keys():
        from src.settings import BUILD_KEY
        m = g.menu
        old = P1_KEYS["action"]
        try:
            for k in (JOURNAL_KEY, BUILD_KEY, pygame.K_i, pygame.K_F11):
                m.binding = (P1_KEYS, "action")
                m.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0,
                                                  unicode="", scancode=0))
                assert P1_KEYS["action"] == old, f"bound reserved key {pygame.key.name(k)}"
                assert m.binding is not None, "should keep waiting for a valid key"
            m.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0,
                                              unicode="", scancode=0))
            assert m.binding is None
        finally:
            P1_KEYS["action"] = old
            m.binding = None
    check("controls menu rejects reserved keys", menu_rejects_reserved_keys)

    def controls_and_online_layout():
        from src.settings import KEY_ACTIONS
        m = g.menu
        old_page = m.page
        try:
            m.page = "controls"
            rows = m.layout()
            reb = [r for r in rows if r["kind"] == "rebind"]
            btn = [r for r in rows if r["kind"] == "button"]
            assert len(reb) == 2 * len(KEY_ACTIONS), len(reb)
            low = max(r["hit"].bottom for r in reb)
            assert all(b["hit"].top > low for b in btn), "buttons cover a binding row"
            assert max(b["hit"].bottom for b in btn) < SCREEN_H - 50, "buttons under footer"
            m.page = "online"
            rows = m.layout()
            host = next(r for r in rows if r.get("action") == "host")["hit"]
            ip = next(r for r in rows if r["kind"] == "ipfield")["hit"]
            # selected-button glow reaches ~16 px below; the caption sits 26 px above
            assert host.bottom + 16 < ip.y - 26, (host, ip)
        finally:
            m.page = old_page
    check("controls rows + online spacing", controls_and_online_layout)

    def hud_cards_opaque():
        c = g.ui._card(200, 80, (200, 120, 90))
        a = c.get_at((100, 12))[3]
        assert a >= 200, f"card top band see-through (alpha {a})"
        card = g._toast_card(["Title", "Subtitle here", None, (255, 200, 120), 3.0, 3.0, None])
        a = card.get_at((card.get_width() // 2, 8))[3]
        assert a >= 200, f"toast top band see-through (alpha {a})"
    check("HUD card + toast sheen keeps the body opaque", hud_cards_opaque)

    def journal_arrows_browse_tab():
        g.state = "play"
        g.journal_open("Achievements")
        tabs = g._journal_tabs()
        if tabs[g._jr_idx]["title"] != "Achievements":
            _key(g, pygame.K_ESCAPE)
            return "no achievements tab (skipped)"
        g._ach_sel = 0
        _key(g, pygame.K_RIGHT)
        assert tabs[g._jr_idx]["title"] == "Achievements", "RIGHT turned the page"
        assert g._ach_sel == 1, g._ach_sel
        _key(g, pygame.K_e)                                  # Q/E still turn pages
        assert tabs[g._jr_idx]["title"] != "Achievements"
        _key(g, pygame.K_ESCAPE)
        assert g.state == "play"
    check("journal arrows go to the tab first", journal_arrows_browse_tab)

    def feed_wraps_long_lines():
        long = ("Fah: EEK! This is SO good! I'm putting it on the menu! (loves it! +heart)"
                " -- a birthday gift! They're overjoyed!")
        lines = g.ui._wrap(g.ui.small, long, SCREEN_W - 2 * 272 - 24)
        assert 1 < len(lines) <= 2, lines
        assert "birthday gift" in " ".join(lines), lines
        huge = "x" * 400
        lines = g.ui._wrap(g.ui.small, huge, 300)
        assert len(lines) == 2 and lines[-1].endswith("..."), lines
        assert all(g.ui.small.size(ln)[0] <= 300 for ln in lines)
        g.ui.messages = []
        g.ui.log(long)
        g.ui.draw_messages(g.screen, avoid=[pygame.Rect(0, SCREEN_H - 120, SCREEN_W, 120)])
        g.ui.draw_messages(g.screen, avoid=[pygame.Rect(0, 0, SCREEN_W, SCREEN_H)])
        g.ui.messages = []
    check("message feed wraps + avoids farmers", feed_wraps_long_lines)

    def arrival_not_hidden():
        from src.settings import AREA_TOWN
        sp = H.spawns_by_area(g)
        if AREA_TOWN not in sp:
            return "no town spawn"
        g.warp(AREA_TOWN, sp[AREA_TOWN])
        g.in_sync = True
        H.frames(g, 30)
        g.draw()
        g.draw()                     # the faded-HUD layer must survive re-use
        H.shot(g, "ui_town_arrival")
        prs = g._player_screen_rects()
        assert len(prs) == 2
        lay = g.__dict__.get("_hud_layer")
        if lay is not None:
            assert lay.get_flags() & pygame.SRCALPHA, "HUD fade layer lost per-pixel alpha"
        H.frames(g, 200)
    check("town arrival draws (HUD fades over farmers)", arrival_not_hidden)

    def seltags_apart():
        g.state = "play"
        p0, p1 = g.players
        saved = [(p.x, p.y) for p in g.players]
        p1.x, p1.y = p0.x + 30, p0.y
        g._sel_tags = {0: ["Watering Can", ("tool", "watering_can"), 0.5],
                       1: ["Watering Can", ("tool", "watering_can"), 0.5]}
        g._draw_hud_ui_seltags()
        r = g._seltag_last
        assert len(r) == 2 and not r[0].colliderect(r[1]), f"tags overlap: {r}"
        # a farmer at the bottom edge: the tag stays off the player panel
        from src.settings import SCREEN_H as _SH
        p0.y, p1.y = g.cam.y + _SH - 10, g.cam.y + 200
        p0.x = g.cam.x + 120
        g._sel_tags = {0: ["Sword", ("tool", "sword"), 0.5]}
        g._draw_hud_ui_seltags()
        panel = pygame.Rect(8, _SH - 128, 256, 128)
        assert not g._seltag_last[0].colliderect(panel), g._seltag_last
        g._sel_tags = {}
        for p, (x, y) in zip(g.players, saved):
            p.x, p.y = x, y
    check("select tags side by side + off the panels", seltags_apart)

    def inventory_names():
        from src.inventory_screen import InventoryScreen
        scr = InventoryScreen(g)
        pane = scr.panes[0]
        lab, det = pane._entry_info(("tool", "hoe"))
        assert lab and lab != "hoe", lab
        inv = g.players[0].inv
        for iid in ("parsnip", "stone"):
            try:
                inv.add(iid, 1)
            except Exception:
                pass
        lab, det = pane._entry_info(("item", "stone"))
        assert lab == "Stone" and det.startswith("x"), (lab, det)
        lab, _ = pane._entry_info(("item", "seed:parsnip"))
        assert lab == "Parsnip Seeds", lab
        pane.cursor = ("hot", 0)
        scr.draw(g.screen)
        H.shot(g, "ui_inventory_names")
    check("inventory names the cursor item", inventory_names)

    def gallery_monsters_clean():
        from src import gallery, monsters
        gal = gallery.GalleryScreen(g, on_close=lambda: None)
        bars = 0
        for key in monsters.ARCHETYPES:
            s = gal._monster(key)
            w, h = s.get_size()
            for y in range(h):
                for x in range(0, w, 2):
                    if tuple(s.get_at((x, y)))[:3] == (40, 0, 0):
                        bars += 1
        assert bars == 0, f"{bars} HP-bar pixels in gallery monsters"
    check("gallery monsters have no HP bars", gallery_monsters_clean)

    def minimap_labels_clear_dots():
        from src.settings import AREA_FARM, TILE
        sp = H.spawns_by_area(g)
        if AREA_FARM in sp:
            g.warp(AREA_FARM, sp[AREA_FARM])
        area = g.world.area
        w = area.warps[0]
        for i, p in enumerate(g.players):             # stand right on an exit
            p.x, p.y = w["gx"] * TILE + TILE / 2 + i * 8, w["gy"] * TILE + TILE / 2
        g.ui.draw_minimap(g.screen, area, g.players, g.npcs, "FARM")
        mm = g.ui._mm_last
        hits = [r for r in mm["labels"] if any(r.colliderect(d) for d in mm["dots"])]
        assert not hits, f"exit label covers a player dot: {hits}"
        H.frames(g, 200)
    check("minimap draws with farmers on an exit", minimap_labels_clear_dots)

    def shop_rows_styled():
        from types import SimpleNamespace
        shop = SimpleNamespace(title="General Store", mode="main", sel=2,
                               options=[("* HOT TODAY: Blueberry +50% *", None, "hot"),
                                        ("~ Seeds ~", None, "header"),
                                        ("Parsnip seeds", 20, "buy"),
                                        ("Sell all", None, "sell")])
        g.ui.draw_shop(g.screen, shop)
    check("shop hot/header rows draw", shop_rows_styled)

    # ------------------------------------------------ fix round 2 (2026-09-26)
    def toast_titles_never_clipped():
        from src.systems import ui_system as U
        titles = ["Grandpa Somchai loves Pickled Snow Mushroom!",
                  "Grandpa Somchai loves Wildflower Honey!",
                  "Grandpa Somchai: The One That Got Away",
                  "Not enough ingredients to cook that.",
                  "Can't afford that tool upgrade yet."]
        for t in titles:
            lines = g._toast_title_lines(t, U._TOAST_TITLE_MAX)
            assert 1 <= len(lines) <= 2, (t, lines)
            for f, ln in lines:
                assert f.size(ln)[0] <= U._TOAST_TITLE_MAX, (t, ln)
            joined = " ".join(ln for _, ln in lines)
            assert joined == t, f"title lost text: {t!r} -> {joined!r}"
            card = g._toast_card([t, "a subtitle", None, (255, 222, 140), 3.0, 3.0, None])
            assert card.get_width() <= U._TOAST_TITLE_MAX + 90, card.get_size()
        return f"{len(titles)} long titles fit"
    check("toast titles wrap instead of clipping", toast_titles_never_clipped)

    def gallery_labels_and_crisp_detail():
        from src import gallery
        gal = gallery.GalleryScreen(g, on_close=lambda: None)
        maxw = gallery.CELL_W - 16
        cut = []
        for cat in gallery.CATEGORIES:
            for name, _fn in gal._entries.get(cat, ()):
                surfs = gal._card_label(name)
                assert 1 <= len(surfs) <= 2, name
                assert all(s.get_width() <= maxw for s in surfs), name
                if len(name) > 16 and len(name.split()) <= 3:
                    cut.append(name)
        # the detail view must upscale pixel art with NEAREST neighbour
        calls = []
        real = pygame.transform.smoothscale
        pygame.transform.smoothscale = lambda *a, **k: (calls.append(1), real(*a, **k))[1]
        try:
            gal.tab = gallery.CATEGORIES.index("Items")
            gal._open_detail(0)
            gal._draw_detail(g.screen)
        finally:
            pygame.transform.smoothscale = real
        assert not calls, "gallery detail smooth-scaled pixel art (blurry)"
        return f"{len(cut)} long names fitted by pixel width"
    check("gallery labels fit by pixels + crisp detail", gallery_labels_and_crisp_detail)

    def help_player_lines_share_font():
        m = g.menu
        a = "PLAYER 1:  Move W A S D  Use KEYPAD ENTER  Prev Q  Next E  Emote BACKSPACE"
        b = "PLAYER 2:  Move Arrows  Use RIGHT SHIFT  Prev ,  Next .  Emote /"
        f = m._help_player_font((a, b), 616)
        assert f.size(a)[0] <= 616 and f.size(b)[0] <= 616
        assert m._help_player_font((a, b), 616) is f, "font not cached"
        old = m.page
        try:
            m.page = "help"
            g.state = "menu"
            g.draw()
        finally:
            m.page = old
            g.state = "play"
    check("how-to-play player lines share one font", help_player_lines_share_font)

    def gold_readout_snaps_in_overlays():
        gold0 = g.gold
        g.state = "play"
        g.gold = 66256
        g.draw()
        g.gold = 970
        try:
            g.journal_open()                  # any overlay state (decor is the same path)
            assert g.state != "play", g.state
            g.draw()
            assert int(round(g.ui._gold_disp)) == 970, g.ui._gold_disp
        finally:
            g.state = "play"
            g.gold = gold0
    check("HUD gold agrees with overlays (decor/journal)", gold_readout_snaps_in_overlays)

    def mine_walls_and_indoor_floors_textured():
        from src.settings import AREA_MINE, AREA_COOP, TILE, AREA_FARM as AREA_FARM_
        from src.world import WALL, TILE_COLORS
        walls = {}
        lvl0 = g.world.mine_level
        for lvl in (1, 7, 12, 17, 22, 33):
            g.world.mine_level = lvl
            g.world.regen_mine(lvl)
            g.warp(AREA_MINE, (5, 3))
            area = g.world.area
            gs = g._ground_cache(area)["surf"]
            assert area.tile(0, 8) == WALL
            px = [tuple(gs.get_at((x, y)))[:3] for x in range(2, TILE - 2, 3)
                  for y in range(8 * TILE + 3, 9 * TILE - 3, 3)]
            walls[area.biome] = max(set(px), key=px.count)       # dominant wall colour
            # the floor carries accent detail (not one flat colour) on every biome
            cols = {tuple(gs.get_at((x, y)))[:3]
                    for x in range(6 * TILE, 14 * TILE, 3) for y in range(4 * TILE, 8 * TILE, 3)}
            assert len(cols) > 2, (area.biome, len(cols))
        flat = TILE_COLORS[WALL]
        assert len(set(walls.values())) >= 5, walls
        assert flat not in walls.values(), walls
        sp = H.spawns_by_area(g)
        if AREA_COOP in sp:
            g.warp(AREA_COOP, sp[AREA_COOP])
            area = g.world.area
            gs = g._ground_cache(area)["surf"]
            x0, y0 = 2 * TILE, 2 * TILE
            cols = {tuple(gs.get_at((x, y)))[:3]
                    for x in range(x0, x0 + 400, 2) for y in range(y0, y0 + 160, 2)}
            assert len(cols) > 2, f"coop floor flat ({len(cols)} colours)"
        g.world.mine_level = lvl0
        if AREA_FARM_ in sp:
            g.warp(AREA_FARM_, sp[AREA_FARM_])
        H.frames(g, 5)
        return f"wall colours {walls}"
    check("mine walls follow biome + indoor floors textured", mine_walls_and_indoor_floors_textured)

    # ------------------------------------------------ final RC round (2026-09-26)
    def toasts_wait_behind_modal_menus():
        # 2026-09-26 polish pass: a toast no longer paints over an open panel
        # (it hid the quest board's reward column); it waits -- timer paused --
        # and slides in once the panel closes
        from src import quests, craft, cooking
        from src.systems import ui_system
        saved = (g.state, list(g.toasts), getattr(g, "quest", None),
                 getattr(g, "craft", None), getattr(g, "cook", None))
        p = g.players[0]
        col = (255, 214, 120)
        try:
            g.toasts = []
            g.toast("Quest complete!", "+424g", icon="parsnip", color=col)
            g.quest = quests.QuestMenu(g, p)
            g.craft = craft.UpgradeMenu(g, p)
            g.cook = cooking.CookingMenu(g, p)
            ttl0 = g.toasts[0][4]
            for st in ("shop", "quest", "craft", "cook", "journal"):
                g.state = st
                g._on_update_ui_toasts(0.5)
                g.draw()
                assert g.toasts and g.toasts[0][4] == ttl0, f"{st}: toast timer ran behind the panel"
                assert g.toasts[0][6] is None, f"{st}: toast was drawn over the panel"
            g.state = "play"
            g.toasts[0][4] = g.toasts[0][5] - 1.0          # fully slid in
            g.draw()
            card = g.toasts[0][6]
            assert card is not None and card.get_width() == ui_system._TOAST_W
            w, h = card.get_size()
            x = SCREEN_W - w - 12
            px = tuple(g.screen.get_at((x + 2, ui_system._TOAST_Y0 + h // 2)))[:3]
            assert px == col, f"toast rail {px} != {col} after the panel closed"
        finally:
            g.state, g.toasts = saved[0], saved[1]
            g.quest, g.craft, g.cook = saved[2], saved[3], saved[4]
        return "toast waits behind shop/quest/craft/cook/journal, then shows"
    check("toasts wait behind modal menus", toasts_wait_behind_modal_menus)

    g.state = "play"
    return "ui ok"
