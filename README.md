# 🌾 Harvest Duo — Two-Player Co-op Farm

A Stardew Valley–style farming game built in **Python + Pygame**, designed for **two people on one keyboard** (or two PCs on the same LAN). Farm together, befriend the villagers, fish, forage, dive into an endless mine, restore the valley, and survive the zombie-filled **Mist City** as a team. Every graphic and sound is generated in code — there are no art or audio files.

> **New in the 2026-09-26 "Level-Up" update:** emotes and partner gifts, a day report, storms / fog / wind, two new mine biomes and bosses, gems and achievements, artisan machines and buff foods, foraging and wildlife, four new villagers with heart events, the Valley Restoration board, festival mini-games, the Flower Meadow and Promise Tree, outdoor decor, a Journal, a new HUD and an expanded Mist City. Full walkthrough (in Thai): [`docs/WHATS_NEW_2026-09-26.md`](docs/WHATS_NEW_2026-09-26.md).

## 🧑‍🎨 Make your farmers
Starting a **new game** opens a **Character Creator** for both players. For P1 and P2 you can **type a name** and pick **skin tone, hairstyle (7 styles), hair colour and shirt colour**, with a live animated preview. Your choices are saved with the game. (Choosing **Continue** skips this and loads your saved farmers.)

Whatever tool or item is selected is **held in your character's hand** and **swings when you use it** — hoe, watering can, pickaxe, axe, sword and fishing rod all show in-hand and animate with the action.

## ▶️ How to run

```bash
pip install pygame-ce
python main.py
```

On Windows you can also double-click **`start_game.bat`** / **`Play HarvestDuo.bat`**, or run `py main.py`. (If `python` doesn't work, try `py` or `python3`.)

## 🎮 Controls (shared keyboard)

| Action                       | Player 1   | Player 2      |
|------------------------------|------------|---------------|
| Move                         | W A S D    | Arrow keys    |
| Use / Talk / Pick up / Give  | **Space**  | **Enter**     |
| Prev tool / item             | Q          | , (comma)     |
| Next tool / item             | E          | . (period)    |
| **Emote** (press again to cycle) | **F**  | **/** (slash) |

| Shared key | What it does |
|------------|--------------|
| **J**      | Open / close the **Journal** |
| **B**      | On the **farm**: outdoor **Decor mode** · inside the **house**: **Build & Buy** |
| **I**      | Inventory / arrange hotbars |
| `Esc`      | Pause / main menu (also closes any open screen) |
| `F11`      | Toggle fullscreen |

P1/P2 keys, including **Emote**, can be rebound in **Settings > Controls**. The camera follows **both players**, so stay reasonably close to each other.

## 🖥️ Main menu, settings & sound
The game opens on an **animated title screen** — a day-to-sunset sky, drifting clouds, parallax hills, a farmhouse and *your own two farmers* standing together. Menu: **Continue / New Game**, **Online (LAN)**, **Gallery / Models**, **Settings**, **How to Play**, **Quit** — use arrows/WASD + Enter, or the mouse. Pressing `Esc` in play returns here as a pause menu.

**Settings** has a **Fullscreen** toggle, **Master / Sound Effects / Music** volume sliders and a **Controls** page for rebinding keys.

All audio is **synthesized inside the game**: per-area music (with a softer music-box version on the farm after 20:00 and on rainy days), looping rain / storm / wind ambience, and sound effects for everything from tilling and sword hits to emotes, gifts, thunder, achievements and boss roars. If a machine can't open its sound device the game simply runs silently.

**Gallery / Models** shows every item, character, monster, prop, piece of furniture, terrain tile and Mist City model, drawn by the real game code.

## 🧑‍🌾 What you can do

**Farm** (your starting area)
1. Select the **Hoe** → face empty ground → Use to till soil.
2. Select a **seed** → Use on tilled soil to plant.
3. Select the **Watering Can** → Use to water. Water daily! (Rain and storms water for you.)
4. Crops grow over in-game **days**. Face a ripe crop and press Use to harvest.
5. Sleep in the **bed** at your house to start the next day (restores energy & health).

The farm has cobbled paths, a pond with a small **fishing dock**, a picnic spot, an **orchard** you can shake for fruit in summer and fall, lamp posts that glow at night and a welcome sign with both your names. The new **north gate** leads to the Flower Meadow.

**Town** (walk down the path from the farm)
- **Eight villagers** — Mira, Tomas, Elya, Luang Por (at the temple) and the newcomers **Fah**, **Kai**, **Grandpa Somchai** and **Luna** — each with a daily schedule, gift tastes and a birthday.
- Visit the **General Store** to buy seeds, livestock and farm supplies and to **sell** your goods.
- Take requests from the **quest board** and help restore the valley at the **Restoration board**.

**Mine** (bottom-left of town)
- **Pickaxe** breaks rocks → stone, copper/iron/gold/iridium ore and, deeper down, **gems**.
- **Sword** fights monsters (contact hurts — watch your HP). Step on the **ladder** to go deeper.
- Six biomes by depth, each with its own monsters: rock (1–4), ice (5–9), lava (10–14), crystal (15–19), **abyss (20–29)** and **ancient ruins (30+)**. Watch out for lava pools and void rifts. A **boss** waits every 5 floors.

## 💞 Playing together
- **Emotes:** press **F** / **/** for a heart bubble; press again to cycle happy, note, wave, !, ?, zzz and sparkle.
- **Love boost:** stand close and both send a heart within 1.5 s → heart burst, +15 energy each and a short regen buff (60 s cooldown).
- **Partner gifts:** select an item, face your partner and press Use to hand them one. The first gift of the day gives you both +8 energy.
- **In Sync:** staying close together slowly restores energy, and doing things side by side pays off — a chance of extra artisan goods ("Made together!"), bonus foraging XP, and bigger fish and more treasure when you fish together.
- **End of Day report:** after sleeping, a card sums up the day for each farmer — gold earned (with a NEW BEST! badge), a star rating and tomorrow's forecast. Lifetime totals live in the Journal's **Stats** tab.

## 📖 Journal (J)
A leather book with a tab for every part of the game: **Guide** (both players' controls + tips), **Achievements**, **Collection** (fish + forage), **Farm**, **Friends**, **Bundles**, **Places**, **Mist City** and **Stats**. Turn pages with Q/E, comma/period, the arrow keys, number keys 1–9 or by clicking a tab; J or Esc closes it.

## 🌦️ Weather & seasons
- Four **28-day seasons**. Seeds only grow in their season; the shop stocks what's currently plantable.
- Six weather kinds: **sunny, rain, snow, storm** (lightning and thunder; waters crops), **fog** (clears by noon) and **windy** (petals or leaves blow across the screen). A **rainbow** appears the morning after rain.
- Tomorrow's weather is rolled in advance — **turn on a TV** at home for the forecast.
- Time flows automatically; the day ends at **2:00 AM** (you pass out — sleep in bed instead). Tools cost **energy**; **gold is shared**.

## ⚔️ Combat, bosses & achievements
- Hits show damage numbers; **critical hits** do double damage; monsters get knocked back. Monsters telegraph their attacks — watch for aim lines and glowing rings.
- Five bosses: Slime King, Rock Titan, Void Overlord, **Abyss Wyrm** (floors 20/25) and **Ruin Colossus** (floors 30+). Below half health they become **ENRAGED**.
- Gems (**Amethyst, Ruby, Emerald, Diamond, Prismatic Shard**) and **Ancient Relics** drop from rocks, monsters and bosses.
- The Workbench has a **Crafting** tab: **Bomb**, **Mega Bomb** (blast rocks and monsters in the mine — keep clear!) and **Rope Ladder** (drop straight to the next floor).
- **37 achievements** with gold rewards, shown in the Journal.

## 🧺 Farming, cooking & the market
- **Artisan machines** (General Store → Farm Supplies): **Preserves Jar** (jam, pickles), **Keg** (wine, juice, mead), **Cheese Press**, **Mayo Machine** and **Bee House** (honey / wildflower honey). Place one on open grass, fill it, and collect the goods later — 65 artisan goods in all.
- **Fertilizer** (faster growth) and **Quality Fertilizer** (chance of a double harvest).
- **Premium seeds** each season: Strawberry, Starfruit, Grape, Ice Berry.
- **Buff foods** from the stove: Spicy Curry (speed), Lucky Dumplings (luck), Miner's Pie (mining), Sushi Roll (fishing), Farmer's Lunch (farming), Hero Stew (combat), Snow Yam Porridge (defense), Honey Tea (regen), plus dishes made from forage finds. Active buffs show as chips above your player panel.
- **HOT TODAY:** one item a day sells for **+50%** — check the top row of the shop or the morning "Market news".
- **Animals:** pet them daily for affection hearts; happy animals sometimes give LARGE produce.

## 🎣 Fishing, foraging & wildlife
- Select the **Rod**, face water, Use to cast, then Use again when the **!** pops up. Every fish has a **size in cm** — beat your records! Some catches drag up a **treasure chest**, and bubbling **hot spots** make bites come faster.
- **19 forageables** appear each morning in the Forest, Meadow, Beach and farm edges (plus orchard fruit). Many are edible straight from the hotbar.
- Butterflies, dragonflies, ducks, birds, frogs, bunnies and fireflies bring the outdoors to life.

## 💌 Villagers, heart events & festivals
- Talk daily and give gifts (one per villager per day). Loved gifts count much more, and **birthdays** count x4. Friendship goes up to **10 hearts**.
- At **2, 4, 6 and 8 hearts** each villager has a **heart event** scene (32 in all). Replay them from Journal > Friends.
- **Valley Restoration:** deliver items to the board in town to complete 7 **bundles** (one needs both farmers). Each bundle adds new decorations to the valley — finish them all for a golden statue of the two of you.
- **Festivals** on day 14 of each season: the **Spring Egg Hunt** (P1 vs P2), the **Summer Luau Potluck**, the **Fall Harvest Fair** and **Winter Lantern Night**.
- At the **temple**, fortunes can grant a **Blessed** luck buff, and ringing the bells together gives a **Harmony** buff.

## 🌸 Flower Meadow & the Promise Tree
Walk north through the farm's new gate to the **Flower Meadow**: seasonal flower drifts, a lily pond to fish, a rope swing, a love bench and a lookout deck. At the big **Promise Tree**, both farmers press Use together for a daily energy boost; the first time, your initials are carved into the trunk, and the tree gets more decorated as your promises add up.

## 🏡 Decor mode (farm)
Press **B on the farm** to decorate outdoors: fences, stone and brick paths, flower beds, lamp posts, benches, a garden arch, bird bath, gnome, pumpkin stack, lantern string, picnic blanket and a deluxe scarecrow. Move the cursor with WASD/arrows/mouse, pick with Q/E (or , . / mouse wheel), place with Space/Enter/click, sell back for half with X/Delete/right-click, and leave with B or Esc.

## 🏠 Your house + Build & Buy mode (Sims-style)
Walk up to the **front door** of the farmhouse to step **inside**. The interior has your **bed** (sleep here to start the next day) and is yours to decorate.

Press **B** inside the house to open **Build & Buy**:

- **Catalogue** (right panel) with 50+ items across **Living / Bedroom / Kitchen / Decor / Crafting / Tabletop** tabs — sofas, beds, dressers, fridges, stoves, dining sets, bookshelves, rugs, plants, lamps, TVs, fireplaces, pianos, aquariums, tabletop knick-knacks and more.
- **Click an item, then click in the room** to place it (costs gold). A green/red ghost shows if the spot is valid.
- **R** (or the Rotate button) turns furniture to face any of 4 directions.
- **Colour swatches** recolour the selected piece or your next placement.
- **Wall Color / Floor Color** buttons recolour the whole house.
- With no item picked, **click a piece** to select it — drag to move, recolour, or **Sell** for half its price.
- Mouse-driven, with keyboard fallbacks (WASD cursor, Q/E catalogue, Space place, Del sell, Esc back).

Placed furniture is **solid**. Inside the house, face any piece and press **Use** to **interact with it, Sims-style** — relax on the sofa, watch TV (and get the weather forecast), cook at the stove, craft at the Workbench, store items in a chest, nap on a bed, warm up by the fire.

## 🌫️ Mist City
A ruined gate deep in the **Forest** leads to **Mist City**, a side-scrolling zombie town (left/right to move, **up** to jump, **Use** to attack, **down** to go through doors). You have 5 minutes before the mist swallows the streets.
- Fight through three zones: **Main Street → Old Factory** (conveyors, acid pools, collapsing catwalks, live wires) **→ Clock Tower**, where **The Bell Keeper** boss attacks to the rhythm of its bell. Both living players must reach a zone door together.
- One random event per run: **Power Outage**, **Acid Rain**, **Siren Horde** or **Supply Drop**.
- Keep an eye on the **NOISE** meter — running and smashing draws more zombies; rooftops and catwalks are quiet routes.
- If a partner falls they become a ghost — stand beside it to revive them. Salvage parts sell in the main world; beating the boss can drop a **Cursed Gear** and a **City Key**. Your best runs are recorded in the Journal.

## 🌐 Online (LAN)
Choose **Online (LAN)** from the menu: one PC hosts (and plays P1), the other joins as P2 and plays with WASD + Space (F to emote). The host runs the real game; the client sends input and draws what the host sends back. Some full-screen moments (day report, heart events, restoration board) appear on the host's screen only, and Mist City is local co-op only.

## 💾 Auto-save & persistent settings
The game **auto-saves** whenever you sleep (and on quit) — gold, date, both inventories, crops, machines, decor, furniture, villager friendship, records, achievements and more. **Settings** (volumes, fullscreen, key bindings) are saved separately. Older saves load fine; new features start fresh.

The main menu shows **Continue** when a save exists (and **New Game** to start fresh). Saves live in **`%APPDATA%\HarvestDuo\`** on Windows (`~/.local/share/HarvestDuo/` on Linux), with an automatic backup (`savegame.bak`) of the previous good save.

## 📍 Interaction spots & HUD
- Every interaction spot is a **real object** with a floating bubble and a **key prompt** built from your current key bindings.
- **Minimap** (top-left) with the area name in its header, exit labels, and dots for both players and villagers.
- **Clock card** (top-right): season, date, day/night dial, weather icon and gold.
- **Player panels** (bottom corners): energy/HP bars, selected item, skills, fortune and active buffs. Hotbars sit at the top with item icons and stack counts.
- **Toasts** slide in from the right for achievements, records, birthdays and other big moments.

## 🗂️ Project structure
```
main.py                 entry point (launcher.py / start_game.bat for Windows)
requirements.txt
src/
  game.py               thin Game controller: loop, reset, warp, new day, update
  systems/              one mixin per domain, mixed into Game
    hooks.py              hook bus: _on_reset_/_on_save_/_on_update_/_draw_hud_... + emit()
    actions_system.py     player_action / use_tool dispatch
    save_system.py        save + load (merges every domain's _on_save_/_on_load_)
    coop_system.py        emotes, partner gifts, love boost, day report, stats
    weather_system.py     storm/fog/wind visuals, forecast, rainbow, ambience
    net_system.py         LAN host/client glue
    combat_system.py      sword, crits, bombs, gems, bosses
    progress_system.py    achievements (+ journal tab)
    farm_system.py        animals, affection, collector
    artisan_system.py     artisan machines, fertilizer, buff foods
    shop_system.py        store, market "HOT TODAY", selling
    fishing_system.py     fish sizes, records, treasure, hot spots
    forage_system.py      forageables, wild snacks, wildlife, collection tab
    story_system.py       villagers, schedules, gifts, heart events, friends tab
    story_restore.py      Valley Restoration board + festival mini-games
    social_system.py      talking, friendship, In Sync
    temple_system.py      fortunes, merit, Blessed buff, harmony bells
    world_system.py       farm props, meadow, Promise Tree, decor mode, hazards
    ui_system.py          journal, toasts, area title cards, hotbar tags
    render_system.py      world + HUD drawing pipeline
  assets/               procedural graphics package (no art files)
    _base.py chars.py terrain.py items.py props.py hud.py
  mistcity/             Mist City side-scroller mode
    mist_system.py world2d.py zones.py player2d.py zombies.py boss.py events.py items.py
  net/                  LAN transport (protocol.py, transport.py)
  settings.py           constants, colours, key bindings
  world.py world_art.py areas, tilemaps, biomes, hazards + their art
  entities.py           Player & Monster
  monsters.py monster_ai.py monster_shapes.py   monster registry, behaviours, art
  loot.py craft.py progress.py                  materials/drops, workbench, skills + achievements
  crops.py cooking.py animals.py                crops, recipes + buffs, livestock
  fishing.py forage.py forage_art.py critters.py
  npc.py story_data.py story_art.py quests.py festival.py
  ui.py menu.py menu_scene.py gallery.py inventory_screen.py
  furniture.py build.py isofurn.py homeiso.py storage.py creator.py
  timesystem.py camera.py inventory.py particles.py lighting.py weather.py audio.py savegame.py
tools/
  smoke_test.py         headless test of the whole game
  tests/test_*.py       per-domain checks (core, combat, farming, fishing, story, world, ui, mist)
docs/                   architecture, upgrade contracts, design notes, what's new
```

## 🧪 Testing
```bash
py tools/smoke_test.py                  # full headless sweep (~20 s), must end with "0 failed"
py tools/smoke_test.py --shots DIR      # also save PNG frames to DIR
py tools/smoke_test.py --only mine,save # run a subset of sections
```
The smoke test redirects saves to a temporary folder, so it never touches your real save.

## 💡 Tips for expanding
The code is registry-driven: add crops in `crops.py`, fish in `fishing.py`, items with `loot.register_item`, props with `assets.register_prop`, monsters in `monsters.py`, villagers in `story_data.py`, or areas in `world.py` — the gallery, shop, quests and Journal pick them up automatically. New features plug in through the hook bus in `src/systems/hooks.py` without editing the core files; see `docs/ARCHITECTURE.md` and `docs/UPGRADE_2026-09.md`.

Built as a co-op recreation — have fun farming together! 🧑‍🌾👩‍🌾
