"""LAN online play (authoritative host) -- the NetMixin glued onto Game.

Model
-----
* HOST runs the real simulation and is Player 1. Each frame it ingests the
  client's input (applied to Player 2), runs ``update`` as usual, then broadcasts
  a compact per-frame *snapshot* of the moving entities. Heavier *world* state
  (tiles, crops, inventories, gold, time) is sent less often and on every area
  change, reusing the save schema (`_collect_save` / `_apply_save`).
* CLIENT does not simulate. It sends its local WASD+Space input to the host and
  renders whatever snapshots arrive, with its camera locked to Player 2 so each
  machine "looks from its own corner".

Overlay menus (shop / quest / cook / craft / journal) open LOCALLY on the client
and relay their result to the host; the client's action key still drives Player
2's world interactions (harvest, tools). While P1 has a screen open on the host
(journal, shop, decor...) Player 2 keeps walking, fishing and using tools.

Sync rules (2026-09 fix round): the 1 Hz world resync never re-runs area entry on
the client (only a real area / mine-floor change respawns entities); snapshots
also carry fishing state, food buffs, the catch banner, villager names and
monster telegraphs. A LAN client NEVER saves: the joiner's own farm is banked on
join and reloaded from disk when the session ends (see _net_restore_local).

Owner: networking. Pure glue -- the rest of the game is unaware it's online,
except for a few guarded hooks in game.py (run / update / _update_camera).
"""
import pygame

from ..settings import (P1_KEYS, P2_KEYS, BUILD_KEY, TILE, JOURNAL_KEY,
                        AREA_HOME, AREA_COOP, AREA_TOWN, AREA_MINE)
from ..net import Host, Client, PORT
from ..net.transport import local_ip

# The client player drives Player 2 but uses comfortable, familiar keys.
CLIENT_KEYS = {
    "up": pygame.K_w, "down": pygame.K_s, "left": pygame.K_a, "right": pygame.K_d,
    "action": pygame.K_SPACE, "prev": pygame.K_q, "next": pygame.K_e,
    "inv": pygame.K_i, "build": BUILD_KEY, "emote": pygame.K_f,
}

_SNAP_HZ = 30.0           # entity snapshots per second (host -> client)
_WORLD_EVERY = 1.0        # full world resync interval (seconds)
# host screens during which the online Player 2 is frozen (the whole farm
# stops: a new day, dressing up, a Mist City run). On every other screen --
# journal, shop, decor, even the pause menu -- P2's world keeps running.
_HOST_FROZEN_STATES = ("play", "sleep", "create", "mistcity", "day_report")
# FishingState fields mirrored to the client (bobber, bite, reel pips)
_FISH_FIELDS = ("state", "timer", "fish", "water", "reel_done", "reel_needed", "hotspot")


class _Keystate:
    """Mimics pygame.key.get_pressed(): truthy for held key codes."""
    __slots__ = ("down",)

    def __init__(self, down):
        self.down = down

    def __getitem__(self, code):
        return code in self.down


class NetMixin:
    # ---------------- lifecycle ----------------
    def _net_init_fields(self):
        self.net = None
        self.net_mode = None          # None | "host" | "client"
        self.cam_focus = None         # which player index the camera follows (net)
        self.net_status = ""          # human-readable line for the HUD
        self._remote_dirs = [False, False, False, False]   # u,d,l,r from client
        self._client_events = []      # outbound action/cycle events (client side)
        self._net_snap_t = 0.0
        self._net_world_t = 0.0
        self._net_synced = False
        self._net_last_area = None
        self._net_host_seen_conn = False      # join / drop notices (host)
        self._net_host_notified_state = None
        self._net_dr_sent = False
        self._net_bomb_seen = None

    def start_host(self):
        if self.net or getattr(self, "_net_client_session", False):
            self.net_stop()                  # leave any session we were in first
        self._net_init_fields()
        self.net = Host(PORT)
        self.net_mode = "host"
        self.cam_focus = 0
        self.net_status = f"Hosting on {local_ip()}:{PORT} — waiting for P2..."
        self.begin_play()
        self.ui.log(self.net_status)

    def start_client(self, ip):
        if (self.net_mode == "client" and self.net and self.net.connected
                and getattr(self.net, "ip", None) == ip):
            # a double Enter / second Join on the live link: keep it
            self.begin_play()
            self.ui.log("Already connected - have fun!")
            return
        if self.net and self.net_mode == "host":
            self.net_stop()
        elif self.net:
            # a second Join (double Enter / click) while a link is up: close the
            # old socket, or the host keeps serving it and the new one is never
            # accepted. The session guard below keeps the own farm banked once.
            try:
                self.net.close()
            except Exception:
                pass
            self.net = None
        if not getattr(self, "_net_client_session", False):
            # bank the joiner's OWN farm first: from here on the world in memory
            # is the host's, and _save() refuses to write until it is restored
            self._save()
            self._net_own_look = [dict(l) for l in self.look]
            self._net_own_started = self.started
        self._net_init_fields()
        self._net_client_session = True
        self._net_world_seen = False     # the first host world respawns + shows its card
        self._net_was_connected = False
        self._net_host_state = "play"
        self._card_welcome = False       # never greet with OUR pre-sync area's card
        self._area_card = None
        self.net = Client(ip, PORT)
        self.net_mode = "client"
        self.cam_focus = 1
        self.net_status = f"Connecting to {ip}:{PORT}..."
        self.begin_play()
        self.ui.log(self.net_status)

    def net_stop(self):
        if self.net:
            try:
                self.net.close()
            except Exception:
                pass
        was_host = self.net_mode == "host"
        self.net = None
        self.net_mode = None
        self.cam_focus = None
        self._remote_dirs = [False, False, False, False]
        if was_host and getattr(self, "p_area", None) and self.p_area[1] != self.world.current:
            self._regroup_p2()           # local co-op again: Player 2 rejoins Player 1
        self._sleep_pending, self._sleep_ready = False, None
        if getattr(self, "_net_client_session", False):
            self._net_restore_local()

    def _net_restore_local(self):
        """End of a LAN-client session: throw away the host's world and put the
        joiner's own farm back from disk, so the host's farm is never played on
        or saved locally. If that fails, saving stays locked for the session."""
        from .. import savegame
        try:
            look = getattr(self, "_net_own_look", None)
            if look:
                self.look = [dict(l) for l in look]
            data = savegame.load_game() if savegame.has_save() else None
            self.reset()
            if data:
                self._apply_save(data)
            self.started = bool(data) and getattr(self, "_net_own_started", False)
            self.has_save = savegame.has_save()
            self._net_world_seen = False
            self._net_client_session = False
        except Exception:
            try:
                import traceback
                savegame.log_error(traceback.format_exc())
            except Exception:
                pass
            self.load_failed = True        # keeps _save() locked: disk copy stays intact
            try:
                self.reset()               # never keep playing on the host's world
            except Exception:
                pass

    def net_leave(self):
        """Menu 'Leave online game': a client goes back to its own farm, a host
        stops hosting. Safe to call in any mode."""
        was = self.net_mode
        self.net_stop()
        if was == "client":
            self.net_status = "Left the online game."
            if getattr(self, "started", False):
                self.begin_play()
                self.ui.log("You left the online game - back to your own farm.")
            else:
                self.state = "menu"     # no own farm yet: Start Game opens the creator
                self.ui.log("You left the online game.")
        elif was == "host":
            self.net_status = "Stopped hosting."
            self.ui.log("Stopped hosting - Player 2 is local again.")

    def net_active(self):
        return self.net_mode in ("host", "client")

    # ---------------- per-player input routing (host) ----------------
    def _player_inputs(self, pressed):
        """Return the keystate to drive each player. Local co-op shares the
        keyboard; an online host feeds Player 2 from the remote client."""
        if self.net_mode == "host":
            return [pressed, self._remote_keystate()]
        return [pressed, pressed]

    def _remote_keystate(self):
        d = self._remote_dirs
        down = set()
        if d[0]:
            down.add(P2_KEYS["up"])
        if d[1]:
            down.add(P2_KEYS["down"])
        if d[2]:
            down.add(P2_KEYS["left"])
        if d[3]:
            down.add(P2_KEYS["right"])
        return _Keystate(down)

    def _apply_remote_event(self, ev):
        """A discrete action the client pressed, applied to Player 2 on the host."""
        if self.state == "day_report" and ev == "action":
            f = getattr(self, "_close_day_report", None)   # P2 may dismiss the card too
            if f and getattr(self, "_dr_done", lambda: True)():
                f()
            elif getattr(self, "_dr_ensure", None):
                r = self._dr_ensure()                      # first press: skip count-up
                r["t"] = max(r.get("t", 0), 2.4)
                r["star_shown"] = r.get("stars", 0)
            return
        apart = self.apart()
        if self.state != "play":
            if self.state in _HOST_FROZEN_STATES:
                return
            if not apart:
                self._net_overlay_event(ev)      # beside P1's open screen: tools only
                return
            # in another area P2 plays on normally while P1 reads a menu
        if ev == "action":
            st, txt = self.state, self.dialogue_text
            self.player_action(1)
            if self.state == "dialogue" and st != "dialogue":
                # a line meant for Player 2: show it on THEIR screen, and don't
                # freeze the host behind a dialogue box P1 never asked for
                self._net_toast(self.dialogue_text.strip())
                self.state, self.dialogue_text = st, txt
            elif self.state != st and self.state != "sleep":
                if apart or st != "play":
                    # never pop a screen up in front of Player 1 from another area
                    self.state, self.dialogue_text = st, txt
                    self._net_toast("That one opens on the host's screen - "
                                    "try it together with Player 1.")
                else:
                    self._net_toast("Opened on the host's screen.")
        elif ev == "prev":
            self.players[1].inv.cycle(-1)
        elif ev == "next":
            self.players[1].inv.cycle(1)
        elif ev == "emote":
            f = getattr(self, "_emote_press", None)     # CoopMixin
            if f:
                f(1)
        elif (ev == "build" and self.world.current == AREA_HOME and not apart
              and self.state == "play"):
            self.state = "build"
            self.audio.play("ui_select")

    def _net_overlay_event(self, ev):
        """P1 has a screen open on the host (journal, shop, decor...): Player 2
        still cycles items, emotes and uses tools, but never opens host screens."""
        p = self.players[1]
        if ev == "prev":
            p.inv.cycle(-1)
        elif ev == "next":
            p.inv.cycle(1)
        elif ev == "emote":
            f = getattr(self, "_emote_press", None)
            if f:
                f(1)
        elif ev == "action":
            seat = getattr(self, "_home_overlay_seat", None)
            if seat and seat(p):                  # sit down / stand up beside P1's screen
                return
            entry = p.inv.selected_entry() if p.inv else None
            if not entry or entry[0] != "tool":
                return
            st = self.state
            try:
                self.use_tool(1, p.target_tile())
            finally:
                if self.state != st:          # a tool never takes over P1's screen
                    self.state = st

    def _net_host_overlay_step(self, dt):
        """Host-side: Player 2's area keeps running while P1 has a non-blocking
        screen open (Game.run only calls update() in "play") -- P2 walks, fishes,
        fights, and the monsters / villagers around them carry on."""
        if (self.net_mode != "host" or not self.net or not self.net.connected
                or self.state in _HOST_FROZEN_STATES):
            return
        try:
            self.partner_update(dt)
        except Exception:
            import os
            if os.environ.get("HD_STRICT_HOOKS") == "1":
                raise

    # ---------------- host: receive input + broadcast ----------------
    def _net_host_ingest(self):
        if not self.net:
            return
        for m in self.net.poll():
            t = m.get("t")
            if t == "input":
                d = m.get("d")
                if isinstance(d, list) and len(d) == 4:
                    self._remote_dirs = [bool(x) for x in d]
                for ev in m.get("ev", []):
                    with self.area_ctx(self.p_area[1]):
                        self._apply_remote_event(ev)
            elif t == "menu":
                with self.area_ctx(self.p_area[1]):
                    self._net_apply_menu(m)

    # ---------------- host: apply a client menu action for Player 2 ----------
    def _net_toast(self, text):
        """Host -> client: a one-off line for the client's message log."""
        if self.net and self.net_mode == "host" and text:
            self.net.send({"t": "toast", "text": text})

    def _net_log(self, text):
        """Log on the host AND mirror it to the client."""
        self.ui.log(text)
        self._net_toast(text)

    def _net_apply_menu(self, m):
        mm = m.get("m")
        if mm == "shop":
            self._net_shop_op(m.get("kind", ""), m.get("price"), buyer=1,
                              n=m.get("n", 1))
        elif mm == "quest":
            self._net_quest_op(m.get("op", ""), m.get("q", {}), buyer=1)
        elif mm == "cook":
            self._net_cook_op(m.get("food", ""), buyer=1)
        elif mm == "craft":
            self._net_craft_op(m.get("tool", ""), buyer=1)
        elif mm == "talk":
            self._net_talk_op(m.get("npc", ""), buyer=1)
        elif mm == "gift":
            self._net_gift_op(m.get("npc", ""), m.get("item", ""), buyer=1)
        elif mm == "monk":
            self._net_monk_op(buyer=1)
        elif mm == "donate":
            self._net_donate_op(buyer=1)
        elif mm == "sleep":
            self._net_sleep_op()
        elif mm == "furn":
            self._net_furn_op(m.get("kind", ""), m.get("gx"), m.get("gy"), buyer=1,
                              on=m.get("on"))
        elif isinstance(mm, str):
            self._first_hook("_net_menu_", mm, m)       # domain ops (fridge, outfit...)

    def _net_cook_op(self, fid, buyer=1):
        from .. import cooking
        if fid not in cooking.RECIPES:
            return
        p = self.players[buyer]
        need = cooking.RECIPES[fid]
        count = getattr(self, "_kitchen_count", None) or self._count_all
        remove = getattr(self, "_kitchen_remove", None) or self._remove_all
        if all(count(i) >= q for i, q in need.items()):
            for i, q in need.items():
                remove(i, q)
            p.inv.add(fid, 1)
            self.audio.play("harvest")
            self.parts.sparkle(p.x, p.y - 10, n=10, color=(255, 210, 140))
            self._net_log(f"{p.name} cooked {cooking.FOODS[fid]['label']}!")
            self.emit("cooked", p=p, food=fid)
        else:
            self._net_toast("Not enough ingredients to cook that.")

    def _net_craft_op(self, tool, buyer=1):
        from .. import craft
        p = self.players[buyer]
        if tool in getattr(craft, "CRAFTABLES", {}):
            if craft.craft_item(self, p, tool):
                self.audio.play("craft")
                self._net_log(f"{p.name} crafted {craft.CRAFTABLES[tool]['label']}!")
            else:
                self._net_toast("Missing materials for that.")
            return
        if tool not in craft.UPGRADABLE:
            return
        tier = p.tool_tiers.get(tool, 0)
        if craft.apply_upgrade(self, p, tool):
            self.audio.play("sell")
            self._net_log(f"{p.name}'s {craft.TOOL_LABEL[tool]} -> {craft.TIER_NAMES[tier + 1]}!")
        else:
            self._net_toast("Can't afford that tool upgrade yet.")

    def _net_talk_op(self, name, buyer=1):
        p = self.players[buyer]
        npc = next((n for n in self.npcs if n.name == name), None)
        if not npc:
            return
        self._story_talker = buyer
        if getattr(self, "_interact_early_40_story_npc", None):
            # the same Story rules as local co-op: heart events, the monk's daily
            # friendship, the couple line. The hook finds the NPC by P2's position.
            st, txt = self.state, self.dialogue_text
            if self._call_hook("_interact_early_40_story_npc", buyer, p):
                if self.state == "dialogue":         # a line meant for P2 only
                    self._net_toast(self.dialogue_text.strip())
                    self.state, self.dialogue_text = st, txt
                elif self.state != st and (self.apart() or st != "play"):
                    # a heart event plays on the host's screen: only when P1 is
                    # right there (it stays ready for later, nothing is used up)
                    self.state, self.dialogue_text = st, txt
                    self._net_toast(f"{npc.name} has something special to share with you "
                                    "both - come back together with Player 1!")
                elif self.state != st:
                    self._net_toast(f"{npc.name} has something to share - look at the host's screen!")
                return
        try:
            npc.talk()        # host-side bookkeeping: first chat of the day (+friendship)
        except Exception:
            pass
        self.dialogue_text = ""          # _talk_reward appends a gift note here
        self._talk_reward(p, npc)
        if self.dialogue_text:
            self._net_toast(self.dialogue_text.strip())
        self.dialogue_text = ""

    def _net_gift_op(self, name, item, buyer=1):
        p = self.players[buyer]
        npc = next((n for n in self.npcs if n.name == name), None)
        if not npc or p.inv.count(item) <= 0:
            return
        self._story_talker = buyer               # Story credits the gift to P2
        if f"{npc.name}|{buyer}" in getattr(self, "story_gifted_today", ()):
            self._net_toast(f"{npc.name}: You already gave me something today, "
                            f"{p.name}. Come see me tomorrow!")
            return
        before = npc.heart_count
        msg = npc.give_gift(item)
        p.inv.remove(item, 1)
        self.parts.sparkle(npc.x, npc.y - 6, n=6, color=(235, 130, 150))
        self._net_log(msg)
        self.emit("gift_given", p=p, npc=npc.name, item=item)
        if npc.heart_count > before:
            self._friendship_reward(p, npc)

    def _net_monk_op(self, buyer=1):
        self._net_toast(self._monk_fortune(buyer, self.players[buyer]))

    def _net_donate_op(self, buyer=1):
        self._net_toast(self._donate(buyer, self.players[buyer]))

    def _net_sleep_op(self):
        if self.state in ("sleep", "day_report"):
            return                                # already asleep / on the report
        self.request_sleep(1)                     # both at home -> the day ends

    def _net_furn_op(self, kind, gx=None, gy=None, buyer=1, on=None):
        from ..settings import MAX_ENERGY
        from .actions_system import FURN_ACTION
        from .. import furniture
        p = self.players[buyer]
        # appliances: the client's press toggles the real piece on the host --
        # or SETS it when the op says which way ("on": the record player), so
        # a press built from the client's stale copy can't flip it back
        if kind in furniture.TOGGLE and gx is not None:
            fr = next((q for q in self.world.home_furniture
                       if q.kind == kind and (gx, gy) in q.cells()), None)
            if fr is not None:
                grp = [fr]
                if kind in furniture.MERGE:
                    grp = next((g for g in furniture.merge_groups(self.world.home_furniture)
                                if any(q is fr for q in g)), [fr])
                if isinstance(on, bool):
                    new = on
                    if all(q.on == new for q in grp):
                        return                # already that way: nothing to do
                else:
                    new = not fr.on
                for q in grp:
                    q.on = new
                label = furniture.CAT[kind]["label"]
                if new:
                    verb, gain = FURN_ACTION.get(kind, ("enjoy it", 4))
                    p.energy = min(MAX_ENERGY, p.energy + gain)
                    self._net_log(f"{p.name}: turns the {label} ON — {verb} (+{gain} energy)")
                    fc = getattr(self, "forecast_text", None)
                    if kind == "tv" and fc:
                        self._net_log(f"Weather report: tomorrow looks {fc().lower()}.")
                else:
                    self._net_log(f"{p.name}: turns the {label} off")
                return
            if isinstance(on, bool):
                return                        # a switch op for a piece that isn't there
        verb, gain = FURN_ACTION.get(kind, ("admire it", 3))
        p.energy = min(MAX_ENERGY, p.energy + gain)
        self._net_log(f"{p.name}: {verb} (+{gain} energy)")

    def _net_shop_op(self, kind, price, buyer=1, n=1):
        from ..crops import CROPS
        from ..animals import Animal
        from .. import animals as A
        p = self.players[buyer]
        try:
            n = max(1, min(99, int(n or 1)))
        except (TypeError, ValueError):
            n = 1
        if kind.startswith("sellitem:"):
            # per-item sell from the client's sell list; _sell_items clamps n
            # to what the player actually holds (the client's view may lag)
            self._sell_items(p, kind.split(":", 1)[1], n)
            return
        if kind.startswith("buy:") or kind.startswith("buyitem:"):
            it = kind.split(":", 1)[1]
            if kind.startswith("buy:"):
                if it not in CROPS:
                    return
                cost = CROPS[it]["seed"]
                from ..crops import crop_label
                give, label = "seed:" + it, f"{crop_label(it)} Seeds"
            else:
                try:
                    cost = max(0, int(price or 0))
                except (TypeError, ValueError):
                    cost = 0
                from ..inventory import Inventory
                give, label = it, Inventory.label(("item", it))
            k = min(n, self.gold // cost) if cost > 0 else n
            if k >= 1:
                self.gold -= cost * k
                p.inv.add(give, k)
                self._net_log(f"{p.name} bought {label}" + (f" x{k}" if k > 1 else "")
                              + f" (-{cost * k}g)")
                self.audio.play("sell")
            else:
                self._net_log(f"{p.name}: not enough gold!")
        elif kind.startswith("animal:"):
            akind = kind.split(":", 1)[1]
            if akind in A.ANIMALS:
                cost = A.ANIMALS[akind]["cost"]
                if self.gold >= cost:
                    self.gold -= cost
                    na = len(self.animals)
                    self.animals.append(Animal(akind, 3 + na % 5, 3 + (na // 5)))
                    if self.world.current == AREA_COOP:
                        self._rehome_animals()
                    self._net_log(f"{p.name} bought a {A.ANIMALS[akind]['label']} (-{cost}g)")
                    self.audio.play("sell")
                else:
                    self._net_log(f"{p.name}: not enough gold!")
        elif kind == "sell":
            self.sell_all()

    def _net_quest_op(self, op, q, buyer=1):
        def find(lst):
            for x in lst:
                if (x.get("item") == q.get("item") and x.get("qty") == q.get("qty")
                        and x.get("reward") == q.get("reward")):
                    return x
            return None
        p = self.players[buyer]
        if op == "accept":
            x = find(self.quest_offers)
            if x and len(self.active_quests) < 4:
                self.quest_offers.remove(x)
                self.active_quests.append(x)
                self.audio.play("ui_select")
                self.ui.log(f"{p.name} accepted a quest.")
        elif op == "turnin":
            x = find(self.active_quests)
            if x and self._count_all(x["item"]) >= x["qty"]:
                self._remove_all(x["item"], x["qty"])
                self.gold += x["reward"]
                self.active_quests.remove(x)
                self.audio.play("sell")
                self._popup(p.x, p.y - 12, f"+{x['reward']}g", (255, 220, 120))
                self._net_log(f"Quest complete! +{x['reward']}g")
                from .. import quests
                who = x.get("npc")
                friend = getattr(self.world, "friend", None)
                if who and isinstance(friend, dict):      # same as QuestMenu.confirm
                    pts = getattr(quests, "QUEST_FRIEND_PTS", 25)
                    friend[who] = min(500, int(friend.get(who, 0)) + pts)
                    try:
                        nm = quests.requester_name(x)
                        self._net_log(f"{nm} thanks you for the "
                                      f"{quests.label(x['item'])}! (+friendship)")
                    except Exception:
                        pass
                self.parts.sparkle(p.x, p.y - 10, n=14, color=(255, 222, 130))
                self.emit("quest_done", p=p, quest=quests.to_dict(x))
        elif op == "cancel":
            x = find(self.active_quests)
            if x:
                self.active_quests.remove(x)
                if x not in self.quest_offers:
                    self.quest_offers.append(x)
                self.audio.play("ui_move")

    def _net_host_broadcast(self, dt):
        if not self.net:
            return
        if self.net.error:
            self.net_status = f"Net error: {self.net.error}"
        was = getattr(self, "_net_host_seen_conn", False)
        if self.net.connected != was:
            self._net_host_seen_conn = self.net.connected
            self._net_host_notified_state = None
            self._net_dr_sent = False      # a rejoining P2 gets the End-of-Day card again
            if self.net.connected:
                self.ui.log("Player 2 joined online!")
                self.audio.play("unlock")
            else:
                self.ui.log("Player 2 disconnected - waiting for them to rejoin...")
                self.net_status = "P2 disconnected - waiting for them to rejoin..."
                self.audio.play("ui_move")
        if not self.net.connected:
            # link gone: drop P2's latched input so they don't walk forever
            self._net_synced = False
            self._remote_dirs = [False, False, False, False]
            return
        # everything the client sees is Player 2's OWN area (which may not be
        # the one on the host's screen)
        with self.area_ctx(self.p_area[1]):
            # (re)send the heavy world state on connect, on area change (a new
            # mine floor counts), or on a timer
            self._net_world_t += dt
            key = (self.world.current, id(self.world.area))
            area_changed = (key != self._net_last_area)
            sent_world = False
            if (not self._net_synced) or area_changed or self._net_world_t >= _WORLD_EVERY:
                self.net.send(self._collect_world())
                self._net_world_t = 0.0
                self._net_synced = True
                self._net_last_area = key
                self.net_status = f"P2 connected — {self.world.current.upper()}"
                sent_world = True
            self._net_host_state_notice()
            self._net_host_bomb_fx()
            # high-rate entity snapshot (always right after a world message, so the
            # client never draws a world message's fresh spawns without positions)
            self._net_snap_t += dt
            if sent_world or self._net_snap_t >= 1.0 / _SNAP_HZ:
                self._net_snap_t = 0.0
                self.net.send(self._collect_snapshot())

    def _net_host_state_notice(self):
        """One line to P2 when P1's screen freezes the farm (Mist City, pause
        menu...) and another when play resumes -- P2 otherwise just sees nothing
        respond. Also ships the End-of-Day report once so P2 sees the card."""
        st = self.state
        if st == "day_report" and getattr(self, "_dr", None):
            if not getattr(self, "_net_dr_sent", False):
                self._net_dr_sent = True
                self._net_send_report()
        else:
            self._net_dr_sent = False
        key = st if st in ("mistcity", "create") else "play"
        prev = getattr(self, "_net_host_notified_state", None)
        if prev is None:                         # first frame of a link: no notice
            self._net_host_notified_state = key
            return
        if key == prev:
            return
        self._net_host_notified_state = key
        msg = {"mistcity": "Player 1 is exploring Mist City - the farm is paused.",
               "create": "Player 1 is dressing up - the farm is paused."}.get(key)
        self._net_toast(msg or "Player 1 is back - the farm is running again!")

    def _net_send_report(self):
        """Host -> client: the built day report (plain data, no surfaces)."""
        import json
        r = {k: v for k, v in (self._dr or {}).items()
             if k not in ("t", "coin_t", "star_shown")}
        try:
            r = json.loads(json.dumps(r))
        except (TypeError, ValueError):
            return
        self.net.send({"t": "dr", "r": r})

    def _net_show_report(self, r):
        """Client: show the host's End-of-Day card (read-only copy)."""
        if not isinstance(r, dict) or not isinstance(r.get("rows"), list):
            return
        if self.state != "play":
            return                     # a local screen is open: the log line covers it
        r = dict(r)
        r.update(t=0.0, coin_t=0.0, star_shown=0)
        r.setdefault("stars", 0)
        self._dr = r
        self._dr_cache = {}
        self.state = "day_report"
        self.audio.play("bell")

    # ---------------- client: send input + apply state ----------------
    def _client_capture_key(self, key):
        K = CLIENT_KEYS
        if key == K["action"] and getattr(self, "_net_host_state", "play") in (
                "day_report", "sleep"):
            # the host shows the End-of-Day card: the press dismisses it (never
            # a second bed / menu request just because P2 woke beside the bed)
            self._client_events.append("action")
            return
        if key == K["action"]:
            # a shop / quest board opens its menu LOCALLY on the client (so the
            # host keeps simulating); everything else is relayed to the host.
            if self._client_try_open_menu():
                return
            self._client_events.append("action")
            return
        for name in ("prev", "next", "emote"):
            if key == K.get(name):
                self._client_events.append(name)
                return
        if key == JOURNAL_KEY and hasattr(self, "journal_open"):
            self.journal_open()               # read-only view of the synced save
            return
        if key == K["build"]:
            self.ui.log("Build mode is host-side in this version.")
            self.audio.play("ui_move")
            return

    def _net_send_menu(self, d):
        """Client -> host: a menu action for Player 2 (host owns the mutation)."""
        d["t"] = "menu"
        if self.net:
            self.net.send(d)

    def _client_try_open_menu(self):
        """Player 2 (on the client) opens any interaction menu LOCALLY so the host
        keeps simulating. Menu confirms / NPC actions are relayed to the host,
        which applies the real mutation for Player 2. Returns True if handled."""
        from .. import quests, cooking, craft
        area = self.world.area
        p = self.players[1]
        if p.inv is None:
            return False
        if getattr(p, "sitting", None):          # seated: watch TV or stand up (host)
            seated = getattr(self, "_home_client_seated", None)
            return bool(seated and seated())
        pgx, pgy = int(p.x // TILE), int(p.y // TILE)

        # NPC: gift (holding an item) / monk fortune / chat
        for npc in self.npcs:
            if abs(npc.x - p.x) < TILE * 1.1 and abs(npc.y - p.y) < TILE * 1.1:
                entry = p.inv.selected_entry()
                if entry and entry[0] == "item" and not entry[1].startswith("seed:"):
                    self._net_send_menu({"m": "gift", "npc": npc.name, "item": entry[1]})
                    self.dialogue_text = f"You offer {npc.name} a gift."
                elif npc.name == "Luang Por":
                    self._net_send_menu({"m": "monk"})
                    self.dialogue_text = "Luang Por closes his eyes and reads your fortune..."
                else:
                    self._net_send_menu({"m": "talk", "npc": npc.name})
                    self._story_talker = 1            # greet Player 2, not P1
                    self.dialogue_text = npc.talk()
                self.state = "dialogue"
                self.audio.play("ui_select")
                return True

        db = getattr(area, "donation_box", None)
        if db and abs(pgx - db[0]) <= 1 and abs(pgy - db[1]) <= 1:
            self._net_send_menu({"m": "donate"})
            self.dialogue_text = "You step up to the alms box..."
            self.state = "dialogue"
            self.audio.play("ui_select")
            return True

        qb = getattr(area, "quest_board", None)
        if area.name == AREA_TOWN and qb and abs(pgx - qb[0]) <= 1 and abs(pgy - qb[1]) <= 1:
            self.quest = quests.QuestMenu(self, p)
            self.state = "quest"
            self.audio.play("ui_select")
            return True

        if area.shop and abs(pgx - area.shop[0]) <= 1 and abs(pgy - area.shop[1]) <= 1:
            self.shop_buyer = 1
            town = area.name == AREA_TOWN
            self.shop.build(self.time.season, allow_buy=town,
                            title="General Store" if town else "Shipping Bin")
            self.shop.sel = 0
            self.state = "shop"
            self.audio.play("ui_select")
            return True

        # home furniture FIRST (mirrors actions_system order) so wall decor near
        # the bed corner stays clickable; the bed itself maps to sleep.
        if area.name == AREA_HOME:
            fr = self.world.furniture_at(*p.target_tile()) or self.world.furniture_at(pgx, pgy)
            if fr:
                if fr.kind == "bed":
                    # global day advance on the host; the host confirms (toast)
                    facing = self.world.furniture_at(*p.target_tile()) is fr
                    if self._bed_confirmed(1, p, facing=facing):
                        self._net_send_menu({"m": "sleep"})
                    return True
                if fr.kind == "workbench":
                    self.craft = craft.UpgradeMenu(self, p)
                    self.state = "craft"
                    self.audio.play("ui_select")
                    return True
                if fr.kind == "stove":
                    self.cook = cooking.CookingMenu(self, p)
                    self.state = "cook"
                    self.audio.play("ui_select")
                    return True
                home = getattr(self, "_home_client_interact", None)
                if home:
                    r = home(p, fr)
                    if r is None:
                        return False              # a seat: the host sits Player 2 down
                    if r:
                        return True
                if fr.kind in ("chest", "toy_chest"):
                    self.ui.log("Storage is host-side in this version.")
                    self.audio.play("ui_move")
                    return True
                self._net_send_menu({"m": "furn", "kind": fr.kind,    # buff and/or
                                     "gx": fr.gx, "gy": fr.gy})       # appliance toggle
                return True

        # standing beside the bed without facing it: ask first (same rule as
        # local play); with a tool in hand it's a tool swing, not a nap
        if area.bed and abs(pgx - area.bed[0]) <= 1 and abs(pgy - area.bed[1]) <= 1:
            entry = p.inv.selected_entry()
            if entry and entry[0] == "tool":
                return False
            if self._bed_confirmed(1, p, facing=False):
                self._net_send_menu({"m": "sleep"})
            return True
        return False

    def _client_shop_confirm(self):
        """Client picked a shop row: send the op to the host (which owns gold +
        inventories) instead of mutating locally."""
        if not self.shop.options:
            return
        _label, price, kind = self.shop.options[self.shop.sel]
        if kind in ("leave", "none"):
            self.state = "play"
            self.audio.play("ui_move")
            return
        if kind == "sellmenu":                    # sell list is navigated locally
            self.shop.build_sell(self.players[1])
            self.audio.play("ui_select")
            return
        if kind == "sellback":
            self.shop.build(*self.shop._args)
            self.shop.sel = 0
            self.audio.play("ui_move")
            return
        import pygame as _pg
        if kind.startswith("sellitem:"):
            # ask the host to sell n of this item from P2's bag; our local copy
            # of the inventory refreshes with the next world-sync (~1s)
            item_id = kind.split(":", 1)[1]
            whole = bool(_pg.key.get_mods() & _pg.KMOD_SHIFT)
            n = self.players[1].inv.count(item_id) if whole else 1
            if self.net:
                self.net.send({"t": "menu", "m": "shop", "kind": kind,
                               "price": price, "n": n})
            self.audio.play("ui_select")
            return
        n = 1
        if kind.startswith(("buy:", "buyitem:")) and _pg.key.get_mods() & _pg.KMOD_SHIFT:
            n = 5                                     # matches the "(Shift: buy 5)" hint
        if self.net:
            self.net.send({"t": "menu", "m": "shop", "kind": kind, "price": price, "n": n})
        self.audio.play("ui_select")

    def _net_client_step(self, dt):
        # P2 closed their copy of the day report: dismiss the host's card too
        if (getattr(self, "_net_prev_state", None) == "day_report" and self.state == "play"
                and getattr(self, "_net_host_state", "play") == "day_report"):
            self._client_events.append("action")
        # cosmetic clocks still tick locally so water/trees animate and text fades
        self.anim_t += dt
        if self.fade > 0:
            self.fade = max(0.0, self.fade - dt * 2.2)
        self.parts.update(dt)
        self.ui.update(dt)
        wu = getattr(self, "_on_update_weather", None)   # cosmetic weather fx locally
        if wu:
            try:
                wu(dt)
            except Exception:
                pass
        # purely cosmetic timers update() owns on the host (the client never
        # runs update): shake, hurt flash, popups, toasts, area cards (the catch
        # banner and fishing state arrive in every snapshot instead)
        self.shake = max(0.0, self.shake - dt * 38)
        self.hurt_flash = max(0.0, self.hurt_flash - dt * 1.6)
        for pu in self.popups:
            pu[1] -= dt * 26
            pu[4] -= dt
        self.popups = [pu for pu in self.popups if pu[4] > 0]
        for n in ("_on_update_ui_toasts", "_on_update_ui_card"):
            if getattr(self, n, None):
                self._call_hook(n, dt)
        self._run_hooks("_on_client_update_", dt)        # domain cosmetic ticks
        if self.state not in ("play", "menu", "sleep"):
            self._run_state("update", dt)                # client-local screens

        if self.net and self.net.error:
            self.net_status = f"Disconnected: {self.net.error}"

        # send our input every frame; while a local menu is open we send a
        # neutral (no-movement) input so Player 2 stands still on the host.
        if self.net and self.net.connected:
            if self.state == "play":
                pressed = pygame.key.get_pressed()
                K = CLIENT_KEYS
                dirs = [bool(pressed[K["up"]]), bool(pressed[K["down"]]),
                        bool(pressed[K["left"]]), bool(pressed[K["right"]])]
                evs = self._client_events
                self._client_events = []
            else:
                dirs = [False, False, False, False]
                evs = []
            self.net.send({"t": "input", "d": dirs, "ev": evs})

        # apply whatever the host sent
        if self.net:
            for m in self.net.poll():
                t = m.get("t")
                if t == "world":
                    self._apply_world(m)
                elif t == "snap":
                    self._apply_snapshot(m)
                elif t == "toast":
                    self.ui.log(m.get("text", ""))
                    if m.get("text", "").startswith("Sleeping..."):
                        self.audio.play("sleep")
                elif t == "fx":
                    self._net_apply_fx(m)
                elif t == "dr":
                    self._net_show_report(m.get("r"))

        self._net_prev_state = self.state          # read by the next step (card closed?)
        if self._net_client_link_lost():
            return
        # our camera follows Player 2
        self._update_camera(self.world.area)

    def _net_client_link_lost(self):
        """The host quit / crashed / the join failed: leave the session (the
        joiner's own farm comes back from disk) instead of freezing on a dead
        copy of the host's world. Returns True if the session ended."""
        net = self.net
        if net is None:
            return False
        if net.connected:
            self._net_was_connected = True
            return False
        seen = getattr(self, "_net_world_seen", False)
        if not (getattr(self, "_net_was_connected", False) or net.error):
            return False                          # still connecting
        err = net.error
        self.net_stop()                           # restores the joiner's own farm
        if seen or getattr(self, "_net_was_connected", False):
            self.net_status = "The host left the game."
            msg = "The host left the game - back to your own farm."
        else:
            self.net_status = f"Could not connect: {err}" if err else "Could not connect."
            msg = "Could not reach the host - back to your own farm."
        self._net_was_connected = False
        if self.state != "menu" and getattr(self, "started", False):
            self.begin_play()                     # straight back onto our own farm
        else:
            self.state = "menu"                   # (a paused player stays in the menu)
        try:
            self.ui.log(msg)
            self.audio.play("ui_move")
        except Exception:
            pass
        return True

    # ---------------- world state (heavy, infrequent) ----------------
    def _collect_world(self):
        area = self.world.area
        msg = {"t": "world", "save": self._collect_save(),
               "area": self.world.current,
               "grid": ["".join(row) for row in area.grid],
               "trees": [[gx, gy] for (gx, gy) in area.trees],
               "rocks": [[gx, gy, ore] for (gx, gy), ore in area.rocks.items()],
               "buildings": [list(b) for b in area.buildings],
               "props": [list(p) for p in area.props]}
        return msg

    def _apply_world(self, m):
        save = m.get("save")
        if save:
            # The 1 Hz resync must not re-run area entry (boss intro, critter
            # re-rolls, monsters flashing back): only rebuild area entities when
            # the area / mine floor really changed or on the first sync.
            respawn = (save.get("current") != self.world.current
                       or (save.get("current") == AREA_MINE
                           and save.get("mine_level", 1) != self.world.mine_level)
                       or not getattr(self, "_net_world_seen", False))
            self._net_applying_world = True
            try:
                self._apply_save(save, respawn=respawn)   # world/players/crops/etc.
                self._net_world_seen = True
                if respawn and getattr(self, "_net_world_seen_area", None) != self.world.current:
                    self._net_world_seen_area = self.world.current
                    self.fade = 1.0                          # the warp iris, on OUR screen
                    self.parts.items.clear()
                    self.popups.clear()
                    try:
                        self.audio.play("warp")
                        self.audio.play_area(self.world.current)
                    except Exception:
                        pass
                if respawn and getattr(self, "_on_event_ui_card", None):
                    # UI-only: the client's own title card for the host's area
                    # (never self.emit('warp') -- stats/achievements would count it)
                    self._call_hook("_on_event_ui_card", "warp",
                                    {"area": self.world.current})
                if not respawn:
                    # kept villagers must read the freshly synced friendship dict
                    fr = self.world.friend
                    for n in self.npcs:
                        if hasattr(n, "_friend"):
                            n._friend = fr
                            fr.setdefault(n.name, 0)
            except Exception:
                pass
            finally:
                self._net_applying_world = False
        area = self.world.area
        grid = m.get("grid")
        if grid:
            area.grid = [list(row) for row in grid]
            area.h = len(area.grid)
            area.w = len(area.grid[0]) if area.grid else area.w
        area.trees = set((gx, gy) for gx, gy in m.get("trees", []))
        area.rocks = {(r[0], r[1]): r[2] for r in m.get("rocks", [])}
        if m.get("buildings") is not None:
            blds = []
            for b in m["buildings"]:
                b = list(b)                       # (gx,gy,w,h,wall,roof,label)
                # JSON turned the wall/roof colour tuples into lists; building_sprite
                # caches on them, so they must be hashable tuples again.
                if len(b) >= 5 and isinstance(b[4], list):
                    b[4] = tuple(b[4])
                if len(b) >= 6 and isinstance(b[5], list):
                    b[5] = tuple(b[5])
                blds.append(tuple(b))
            area.buildings = blds
        if m.get("props") is not None:
            area.props = [tuple(p) for p in m["props"]]
        self.net_status = f"Online — {self.world.current.upper()}"

    # ---------------- entity snapshot (light, ~30Hz) ----------------
    def _collect_snapshot(self):
        P = []
        for p in self.players:
            sel = p.inv.selected if p.inv else 0
            P.append([round(p.x, 1), round(p.y, 1), p.fx, p.fy, p.dirname, p.frame,
                      1 if p.moving else 0, round(p.idle_t, 2), round(p.hurt_cd, 2),
                      round(p.swing, 3), round(p.item_use, 3), round(p.item_use_dur, 3),
                      p.item_use_kind, p.item_use_name, p.energy, p.health, sel])
        try:
            from .. import monster_ai as _mai
            pack = getattr(_mai, "net_pack", None)
        except Exception:
            pack = None
        M = []
        for m in self.monsters:
            row = [round(m.x, 1), round(m.y, 1), round(m.anim_t, 2), m.hp, m.max_hp,
                   m.name, 1 if m.facing_left else 0]
            if pack:
                try:
                    row.append(pack(m))            # telegraphs + projectiles
                except Exception:
                    pass
            M.append(row)
        N = [[round(n.x, 1), round(n.y, 1), round(getattr(n, "anim_t", 0.0), 2), n.name]
             for n in self.npcs]
        A = [[round(a.x, 1), round(a.y, 1), round(a.anim_t, 2),
              1 if a.moving else 0, a.dirname, 1 if a.has_produce else 0]
             for a in self.animals]
        snap = {"t": "snap", "area": self.world.current, "P": P, "M": M, "N": N, "A": A,
                "gold": self.gold, "min": round(self.time.minutes, 1),
                "day": self.time.day, "season": self.time.season_idx,
                "night": round(self.night, 3), "W": getattr(self, "weather", "sunny"),
                "hs": self.state, "PA": list(getattr(self, "p_area", ()))}
        bm = self._net_pack_bombs()
        if bm is not None:
            snap["BM"] = bm
        es = getattr(self, "_emote_snapshot", None)          # CoopMixin bubbles
        if es:
            snap["E"] = es()
        # per-player fishing (bobber / bite / reel pips), food buffs, catch banner
        F = []
        for i in (0, 1):
            st = self.fishing.get(i) if isinstance(self.fishing, dict) else None
            F.append([getattr(st, k, None) for k in _FISH_FIELDS] if st else None)
        snap["F"] = F
        B = []
        for p in self.players:
            row = {}
            for k, v in (getattr(p, "buffs", None) or {}).items():
                try:
                    row[str(k)] = [round(float(v[0]), 3), round(float(v[1]), 1), str(v[2])]
                except Exception:
                    pass
            B.append(row)
        snap["B"] = B
        fb = self.fishing_banner
        snap["FB"] = [fb[0], list(fb[1])[:3], round(fb[2], 2)] if fb else None
        snap.update(self._gather_hooks("_net_snap_out_"))   # e.g. seated farmers
        return snap

    def _apply_snapshot(self, d):
        hs = d.get("hs")
        if isinstance(hs, str):
            prev = getattr(self, "_net_host_state", "play")
            self._net_host_state = hs
            if hs == "day_report" and prev != "day_report" and self.state != "day_report":
                from ..ui import key_label
                self.ui.log("The End-of-Day report is on Player 1's screen - press "
                            f"{key_label(CLIENT_KEYS['action'])} to continue.")
        pa = d.get("PA")
        if (isinstance(pa, list) and len(pa) == 2
                and all(isinstance(a, str) and a in self.world.areas for a in pa)):
            self.p_area = list(pa)          # who stands where (hides P1 when apart)
        if d.get("area") != self.world.current:
            return            # geometry not in sync yet; wait for the next world msg
        if "BM" in d:
            self._net_unpack_bombs(d.get("BM"))
        for i, pd in enumerate(d.get("P", [])[:2]):
            p = self.players[i]
            (x, y, fx, fy, dn, fr, mv, it, hc, sw, iu, iud, iuk, iun, en, hp, sel) = pd
            p.x, p.y, p.fx, p.fy = x, y, fx, fy
            p.dirname, p.frame, p.moving = dn, fr, bool(mv)
            p.idle_t, p.hurt_cd, p.swing = it, hc, sw
            p.item_use, p.item_use_dur = iu, iud
            p.item_use_kind, p.item_use_name = iuk, iun
            p.energy, p.health = en, hp
            if p.inv and p.inv.hotbar_order:
                p.inv.selected = max(0, min(sel, len(p.inv.hotbar_order) - 1))
        # monsters: rebuild the list when its shape changes, else just move them
        md = d.get("M", [])
        if (len(md) != len(self.monsters) or
                any(self.monsters[i].name != md[i][5] for i in range(len(md)))):
            from ..entities import Monster
            self.monsters = [Monster(0, 0, m[5]) for m in md]
        unpack = None
        if any(len(m) > 7 for m in md):
            try:
                from .. import monster_ai as _mai
                unpack = getattr(_mai, "net_unpack", None)
            except Exception:
                unpack = None
        for m, obj in zip(md, self.monsters):
            obj.x, obj.y, obj.anim_t = m[0], m[1], m[2]
            obj.hp, obj.max_hp = m[3], m[4]
            obj.facing_left = bool(m[6])
            if unpack and len(m) > 7:
                try:
                    unpack(obj, m[7])
                except Exception:
                    pass
        nd_all = d.get("N", [])
        names = [r[3] for r in nd_all if len(r) > 3]
        if len(names) == len(nd_all) and names != [n.name for n in self.npcs]:
            # villagers come and go on the host's schedule (Story): mirror the
            # host's list by name instead of re-running area entry
            from ..npc import NPC
            have = {n.name: n for n in self.npcs}
            fresh = []
            for r in nd_all:
                n = have.get(r[3])
                if n is None:
                    try:
                        n = NPC(r[3], int(r[0] // TILE), int(r[1] // TILE),
                                friend=self.world.friend)
                        n.game = self
                    except Exception:
                        continue
                fresh.append(n)
            self.npcs = fresh
        for nd, n in zip(nd_all, self.npcs):
            n.x, n.y = nd[0], nd[1]
            if hasattr(n, "anim_t"):
                n.anim_t = nd[2]
        for ad, a in zip(d.get("A", []), self.animals):
            a.x, a.y, a.anim_t = ad[0], ad[1], ad[2]
            a.moving, a.dirname, a.has_produce = bool(ad[3]), ad[4], bool(ad[5])
        self.gold = d.get("gold", self.gold)
        self.time.minutes = d.get("min", self.time.minutes)
        self.time.day = d.get("day", self.time.day)
        self.time.season_idx = d.get("season", self.time.season_idx)
        self.night = d.get("night", self.night)
        if isinstance(d.get("W"), str):
            self.weather = d["W"]
        ea = getattr(self, "_emote_apply_snapshot", None)
        if ea and "E" in d:
            ea(d["E"])
        for i, fd in enumerate((d.get("F") or [])[:2]):
            st = self.fishing.get(i) if isinstance(self.fishing, dict) else None
            if st is None or not isinstance(fd, list):
                continue
            for k, v in zip(_FISH_FIELDS, fd):
                setattr(st, k, v)
        for i, bd in enumerate((d.get("B") or [])[:2]):
            p = self.players[i]
            if isinstance(bd, dict) and hasattr(p, "buffs"):
                p.buffs = {k: list(v) for k, v in bd.items()
                           if isinstance(v, list) and len(v) == 3}
        if "FB" in d:
            fb = d["FB"]
            self.fishing_banner = ((fb[0], tuple(fb[1]), fb[2])
                                   if isinstance(fb, list) and len(fb) == 3 else None)
        self._run_hooks("_net_snap_in_", d)

    # ---------------- bombs (lit fuses + blasts) for the client --------------
    def _net_pack_bombs(self):
        """[[x, y, t, kind, owner], ...] for every lit bomb (Combat's list of
        {x, y, t, owner, kind} dicts), or None when Combat is absent."""
        f = getattr(self, "_cb_net_pack_bombs", None)
        if f:
            try:
                return f()
            except Exception:
                return None
        bombs = getattr(self, "_cb_bombs", None)
        if bombs is None:
            return None
        out = []
        for b in bombs:
            try:
                out.append([round(float(b["x"]), 1), round(float(b["y"]), 1),
                            round(float(b["t"]), 2), str(b.get("kind", "bomb")),
                            int(b.get("owner", 0))])
            except Exception:
                pass
        return out

    def _net_unpack_bombs(self, rows):
        """Client: rebuild Combat's lit-bomb list so its world pass draws the
        fuses (the host owns the real bombs and their blasts)."""
        if not isinstance(rows, list) or getattr(self, "_cb_bombs", None) is None:
            return
        f = getattr(self, "_cb_net_unpack_bombs", None)
        if f:
            try:
                f(rows)
            except Exception:
                pass
            return
        new = []
        for r in rows:
            if isinstance(r, list) and len(r) >= 5:
                new.append({"x": r[0], "y": r[1], "t": r[2], "kind": str(r[3]),
                            "owner": r[4]})
        self._cb_bombs = new

    def _net_host_bomb_fx(self):
        """Host: a lit bomb that vanished at the end of its fuse just blew up --
        replay the blast (shake, burst, sound) on the client too."""
        bombs = getattr(self, "_cb_bombs", None)
        if bombs is None:
            return
        area = self.world.current
        prev = getattr(self, "_net_bomb_seen", None)
        now = {id(b): (b.get("x", 0), b.get("y", 0), b.get("t", 0), b.get("kind", "bomb"))
               for b in bombs if isinstance(b, dict)}
        if prev and prev[0] == area:
            for bid, (x, y, t, kind) in prev[1].items():
                if bid not in now and t <= 0.15:
                    self._net_send_fx("boom", x=round(x, 1), y=round(y, 1),
                                      mega=1 if kind == "mega_bomb" else 0)
        self._net_bomb_seen = (area, now)

    def _net_send_fx(self, kind, **data):
        """Host -> client: a one-shot visual/audio effect (e.g. a bomb blast)."""
        if self.net and self.net_mode == "host" and self.net.connected:
            msg = {"t": "fx", "kind": kind}
            msg.update(data)
            self.net.send(msg)

    def _net_apply_fx(self, m):
        """Client: replay a host effect locally (shake, burst, sound)."""
        if m.get("kind") != "boom":
            self._first_hook("_net_fx_", m)             # domain effects (piano notes...)
            return
        try:
            x, y = float(m.get("x", 0)), float(m.get("y", 0))
        except (TypeError, ValueError):
            return
        mega = bool(m.get("mega"))
        f = getattr(self, "_cb_net_boom_fx", None)     # Combat's own blast visuals
        if f:
            try:
                f(x, y, mega)
                return
            except Exception:
                pass
        self.add_shake(15 if mega else 9)
        pt = self.parts
        for name, args, kw in (("ring", (x, y), {"color": (255, 220, 150), "radius": 14}),
                               ("ring", (x, y), {"color": (255, 150, 80),
                                                 "radius": 30 if mega else 22}),
                               ("star_burst", (x, y), {"color": (255, 190, 90),
                                                       "n": 26 if mega else 16}),
                               ("smoke", (x, y), {"n": 10, "color": (120, 116, 124)}),
                               ("chips", (x, y), {"n": 14, "color": (150, 140, 130)})):
            f = getattr(pt, name, None)
            if f:
                try:
                    f(*args, **kw)
                except Exception:
                    pass
        bank = getattr(self.audio, "sfx", None) or {}
        self.audio.play(next((n for n in ("explosion", "bomb", "thunder") if n in bank),
                             "mine"))
