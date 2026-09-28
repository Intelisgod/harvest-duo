# Harvest Duo — "Level-Up" upgrade (2026-09-26)

A big parallel upgrade: one worker per domain (see `docs/ARCHITECTURE.md` ownership
map), all working at the same time in the same folder. This file is the **shared
contract** — read it fully before touching code.

## 0. Ground rules (all domains)

1. **Only edit files your domain owns** (table in §2). Never rewrite another
   domain's file. If you truly need a change elsewhere, don't make it: say so in
   your final report ("REQUEST: ...").
2. **Plug in through hooks, not seam edits.** `src/systems/hooks.py` documents
   the hook bus. Define methods with these prefixes in *your* mixin and they are
   called automatically:
   `_on_reset_*` (init your state) · `_on_area_enter_*` · `_on_new_day_*` ·
   `_on_update_*(dt)` · `_on_keydown_*(key)->bool` · `_interact_early_*(idx,p)->bool` ·
   `_interact_late_*(idx,p)->bool` · `_on_tool_*(idx,p,tool,gx,gy)->bool` ·
   `_on_save_*()->dict` · `_on_load_*(d)` · `_draw_world_*()` · `_draw_hud_*()` ·
   `_world_sprites_*()->list` · `_lights_*()->list` · `_on_event_*(event,data)` ·
   custom screens `_state_event_<name>(e)` / `_state_update_<name>(dt)` / `_state_draw_<name>()`
   · journal tabs `_journal_tab_<NN>_<domain>()->dict`.
   Name every hook `<prefix><domain>_<what>` (e.g. `_on_save_forage`) so names never
   collide. Numeric infix = order (`_interact_late_20_x` runs before `_interact_late_60_y`).
3. **Save keys** returned by `_on_save_*` must be unique and namespaced
   (`"forage_spawns"`, `"ach_unlocked"`...), JSON-serialisable (no tuples as dict
   keys — use "a|b|c" strings), and `_on_load_*` must use `d.get(key, default)` —
   old saves lack them. The smoke test does a JSON round-trip: `_collect_save()`
   before and after `reset()+_apply_save()` must be identical → load exactly
   what you saved (e.g. store lists sorted, restore sets from lists).
4. **Mixins have no `__init__`**; state is created in your `_on_reset_*` hook.
5. **No circular imports.** `src/assets/items.py` imports `crops`, `fishing`,
   `loot`, `cooking` → those four modules must NEVER import `assets` at module
   level. Register icons/props from your *system mixin file* or a new module of
   yours.
6. **All in-game text in English** (the pixel font has no Thai glyphs).
7. **Performance:** the frame budget is 16 ms (currently ~11 ms on the farm).
   Cache generated surfaces (`assets._base._cache` pattern or a module dict); never
   build big Surfaces or do per-pixel Python loops every frame.
8. **Art style:** everything is procedural pygame drawing in a cosy pastel pixel
   style. Match the existing palette/helpers (`src/assets/_base.py`: `_surf`,
   `_shade`, `_lt`, `_dk`, `IC=28` icon size, `TILE=48`).
9. **Definition of Done:** `py tools/smoke_test.py` green (run it with `py`,
   the Python that has pygame). It isolates saves (never touches the real save),
   sweeps every area / hotbar item / facing / interaction point, every custom
   state, every hotkey, every event, mine depths 1–100, all seasons & weathers,
   save round-trip + old saves. Add your own checks in
   **`tools/tests/test_<domain>.py`** defining `run(g, check, H)` (see
   `s_domain_tests` in the smoke test); don't edit `tools/smoke_test.py`.
   Use `--shots DIR` to save PNGs and LOOK at them (Read the PNG) to judge visuals.
   Other workers edit concurrently: if a failure comes from a file you don't own,
   wait ~1 min and re-run; don't "fix" their file.

## 1. Shared contracts (already implemented by the orchestrator — code against them)

| Contract | API |
|---|---|
| Hook bus | `src/systems/hooks.py` (see §0.2). `self.emit(event, **data)` broadcasts to `_on_event_*`. |
| Events vocabulary | `harvest(p,item,qty)`, `fish_caught(p,fish,size)`, `monster_killed(p,kind,boss)`, `item_sold(p,item,qty,gold)`, `gift_given(p,npc,item)`, `cooked(p,food)`, `crafted(p,what)`, `mine_depth(level)`, `day_started(day,season,year)`, `foraged(p,item)`, `quest_done(p,quest)`, `warp(area)`, `tool_upgraded(p,tool,tier)`, `animal_product(p,item)`, `emote(p,kind)`, `partner_gift(p,to,item)`, `bundle_done(name)`, `achievement(key)`, `rock_broken(p,area)`, `tree_chopped(p,area)`, `crop_planted(p,crop)`, `festival_won(p,name)`, `mist_run_end(kills,loot,reason,zone)`. Who emits: Core → harvest/warp/day_started/gift_given (NPC gift in actions_system)/mine_depth/rock_broken/tree_chopped/crop_planted/animal_product (coop interactions in actions_system)/emote/partner_gift; Combat → monster_killed/crafted/tool_upgraded/achievement; Farming → item_sold/cooked/animal_product (collector); Fishing → fish_caught/foraged; Story → quest_done/bundle_done/festival_won; Mist → mist_run_end (+ monster_killed for zombies/boss). **Emit the ones your domain produces** at the moment they happen (harvest/warp/day_started are already emitted by Core). Subscribers read `data.get(...)` defensively. |
| New items | `loot.register_item(item_id, label, sell, color, cat)` → label, sell price (`sell_value`), gallery, quest pools. Icon: `assets.register_item_icon(item_id, painter)` where `painter(surface28x28)` draws. |
| New props | `assets.register_prop(kind, painter)`; `painter()` returns a Surface (cache it). Areas list props as `area.props` entries `(kind, gx, gy)` → drawn (y-sorted) by the world renderer; unknown kinds fall back to a signpost. |
| New monster shapes / AI | `monsters.SHAPE_PAINTERS[shape] = fn(mon, surf, cx, cy)`; `monsters.BEHAVIORS[name] = fn(mon, dt, players, area, target, ux, uy, dist) -> (ux, uy) or None`. Archetype dicts reference them via `"shape"` / `"behavior"`. |
| Buffs | `p.add_buff(kind, seconds, amount, label)`; `p.buff(kind) -> float`. Kinds: `speed` (+fraction move speed, applied by Player), `luck`, `mining`, `fishing`, `farming`, `combat` (+fraction dmg), `defense` (fraction dmg reduced), `regen` (energy/sec, applied by Player). Each domain *reads* the buff kinds relevant to it (combat reads `combat`, fishing reads `fishing`...). |
| Lights | `_lights_*()` returns `[(world_x, world_y, radius_px, (r,g,b)), ...]` — glows at dusk/night and in the mine. |
| Y-sorted world objects | `_world_sprites_*()` returns `[(baseline_world_y, surface, (screen_x, screen_y)), ...]` or `(baseline_y, None, obj_with_draw(screen, cam))`; sorted together with players/NPCs/trees. Screen pos = world − `self.cam.x/y`. |
| Journal (key **J**, owned by UI) | Any domain adds a tab: `_journal_tab_<NN>_<domain>(self) -> {"title": str, "draw": fn(surf, rect)}` (+ optional `"key": fn(key)` for scrolling). `rect` is the content area on a **cream parchment page** (`ui_kit.CREAM`, since the 2026-09-26 polish pass): use `ui_kit` ink colours (`INK`, `INK_SOFT`, `SPROUT`, `GOLD_TXT`, `WARN`), `ui_kit.well()` for boxes, and `self.ui.font` / `self.ui.small`. Lay out across the full width (there is no centre gutter). Keep it readable at 1280×720. |
| Custom screens | set `self.state = "<name>"` and define `_state_event_<name>`, `_state_update_<name>`, `_state_draw_<name>` (drawn over the world+HUD). `self.state = "play"` to close. ESC should close your screen. |
| Hotkeys (only these new ones) | **J** journal (UI) · **F** P1 emote / **/** P2 emote (Core, rebindable via `KEY_ACTIONS`) · **B on the farm** outdoor decor mode (World). No other new global hotkeys. |
| Areas | New constant `AREA_MEADOW = "meadow"` (World builds it). Mine biomes (World ↔ Combat): `rock` 1–4, `ice` 5–9, `lava` 10–14, `crystal` 15–19, `abyss` 20–29, `ruins` 30+ — `area.biome` holds the name. |
| Town restoration board (World ↔ Story) | World adds `area.restoration_board = (gx, gy)` in town + a prop `"restoration_board"`; Story registers the prop painter and handles the interaction via `_interact_early_*`. |
| Farm objects | `world.farm_objects[(gx, gy)] = kind` (already saved by Core). Only sprinklers are drawn natively — any new kind must be drawn by its owner through `_world_sprites_*`, and is solid only if the owner handles it. Artisan machines (Farming) and outdoor decor (World) both live here; kinds must not overlap (`machine_*` for Farming, `decor_*` for World). |
| Toasts | `self.toast(title, subtitle="", icon=None, color=None, seconds=3.5)` — big notification card (icon = item id or Surface). Minimal version exists in `systems/ui_system.py`; UI restyles it, signature stays. For small messages keep using `self.ui.log(text)` / `self._popup(wx, wy, text, color)`. |
| Particles (existing) | `self.parts.` `dust, splash, sparkle, hit, chips, footstep, mote, leaf, smoke, flame, ember, bubble, ripple, warp, confetti, heart_float, heart_burst`. Core adds more (`star_burst`, `coin_burst`, `ring`, `petal`, `poof` ...) — call new ones via `getattr(self.parts, "star_burst", None)` guard since they land concurrently. |
| Damage taken | `Player.take_damage` already applies the `defense` buff. |
| Mine biome style (World → UI) | World exposes `world.BIOME_STYLE = {biome: {"floor": tile, "rock_tint": (r,g,b), "ambient": "dust"|"snow"|"ember"|"sparkle"|"void"|"ruin"}}`; the renderer reads it when present (fallback to its old dict). |
| Audio | `self.audio.play(name)` is a no-op for unknown names, so call it freely; Core adds new SFX: `emote, gift, thunder, achievement, coin, forage, unlock, page, bell, crit, boss_roar, craft, splash_big, error`. |

## 2. Who does what (this upgrade)

| Domain | Owns (edit only these + new files you create) | Features |
|---|---|---|
| **Core (0)** | `game.py`, `systems/actions_system.py`, `systems/save_system.py`, `systems/coop_system.py`, `systems/weather_system.py`, `systems/hooks.py`, `savegame.py`, `settings.py`, `timesystem.py`, `camera.py`, `inventory.py`, `entities.py`, `particles.py`, `audio.py`, `lighting.py`, `weather.py`, `systems/net_system.py` | emotes, partner gifting, day report + lifetime stats (+ journal "Stats" tab), storm/fog/wind weather, SFX & music upgrade, particle shapes, buff HUD |
| **Combat (1)** | `systems/combat_system.py`, `systems/progress_system.py`, `progress.py`, `monsters.py`, `loot.py`, `craft.py` | biome monsters + 2 new bosses, gems/relics, combat juice (crits, knockback, damage numbers), bombs, achievements (+ journal tab) |
| **Farming (2)** | `systems/farm_system.py`, `systems/shop_system.py`, `systems/artisan_system.py`, `crops.py`, `animals.py`, `cooking.py` | artisan machines, buff foods, shop specials/market, animal affection |
| **Fishing (3)** | `systems/fishing_system.py`, `systems/forage_system.py`, `fishing.py`, `critters.py` | forageables, ambient wildlife, fish sizes + records + treasure, collection (journal tab) |
| **Story (4)** | `systems/temple_system.py`, `systems/social_system.py`, `systems/story_system.py`, `npc.py`, `quests.py`, `festival.py` | 4 new villagers with schedules, gift tastes + birthdays, heart events, Valley Restoration bundles, festival mini-game, friends tab |
| **World (5)** | `world.py`, `systems/world_system.py`, `build.py`, `isofurn.py`, `homeiso.py`, `furniture.py`, `storage.py`, `creator.py` | farm beautification, flower meadow area, outdoor decor mode, abyss/ruins biomes + hazards, restoration board placement |
| **UI (6)** | `systems/render_system.py`, `systems/ui_system.py`, `ui.py`, `menu.py`, `gallery.py`, `inventory_screen.py`, `assets/*` | journal screen, HUD overhaul + toasts, animated title screen, world render polish, warp transition + area title cards |
| **Mist City (7)** | `src/mistcity/*` | V2: second zone, random events, Bell Keeper boss, run records |
