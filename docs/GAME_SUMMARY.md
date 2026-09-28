# Harvest Duo — สรุปเกมแบบละเอียด (สำหรับหาไอเดียเพิ่ม/ตัด)

อัปเดตล่าสุด: 2026-06-08 · เอนจิน: Python + Pygame · ศิลป์/เสียง: สร้างด้วยโค้ดทั้งหมด (ไม่มีไฟล์ asset)

> **ตัวเลขล่าสุดอยู่ท้ายไฟล์:** ดูส่วน **"อัปเดต 2026-09-26 — Level-Up"** (ส่วนบนเก็บไว้เทียบประวัติ)

---

## 1. ภาพรวม

เกมฟาร์มแนว Stardew Valley เล่น 2 คนแบบ co-op ตัวเกมเป็นมุมมอง top‑down 2D
โลกแบ่งเป็น "พื้นที่" (area) เดินทะลุกันด้วยประตู/ทางออก (warp) ทุกอย่างใช้ระบบ
ทะเบียนกลาง (single source of truth) — เพิ่มของที่ทะเบียนเดียว แล้ว gallery / ร้าน /
เควสต์ / ไกด์ เห็นเองทั้งหมด

### การควบคุม
- **Local (คีย์บอร์ดเดียว):** P1 = WASD + Space, สลับเครื่องมือ Q/E · P2 = ลูกศร + Enter, สลับ , / .
- **Online (LAN):** เครื่อง host เป็น P1, อีกเครื่อง join เป็น P2 คุมด้วย WASD + Space (กล้องแยกที่ตัวเอง)
- ปุ่มรวม: B = build (ในบ้าน), I = จัดกระเป๋า, F11 = เต็มจอ, Esc = เมนู/พัก

---

## 2. โหมดเล่น

| โหมด | รายละเอียด |
|---|---|
| Local co‑op | 2 คนจอเดียว คีย์บอร์ดเดียว กล้องตามจุดกึ่งกลางผู้เล่น |
| Online LAN | authoritative host: host รันเกมจริง + เป็น P1, client เป็นตัวเรนเดอร์บางๆ ส่ง input + รับ snapshot, กล้องล็อกที่ตัวเอง |
| Mist City | โหมด side‑scroller แยก (เมืองร้างซอมบี้) จับเวลา 5 นาที มีหมอก + ฮีล เข้าได้จากประตูร้างในป่า |

**Online — เมนูที่ client เปิดเองได้ (host ไม่ค้าง):** ร้านค้า, quest board, คุย NPC, ให้ของขวัญ,
ดูดวงพระ, ตู้ทำบุญ, ทำอาหาร, อัปเกรดเครื่องมือ, เฟอร์นิเจอร์, นอน
**ยังเป็น host‑side:** ตู้เก็บของ (chest), โหมด build

---

## 3. พื้นที่ (Areas) — มี 8 + Mist City

farm (ฟาร์ม) · town (เมือง) · mine (เหมือง ลึกไม่จำกัด) · home (บ้าน) ·
forest (ป่า) · temple (วัด) · coop (เล้าสัตว์) · beach (ชายหาด) · + Mist City (side‑scroller)

- **เหมือง:** ลึกไม่จำกัด, มอนสเตอร์แรงขึ้นตามชั้น, **บอสทุก 5 ชั้น**
- **ป่า:** ต้นไม้งอกใหม่ทุกเช้า, สัตว์ป่าให้ล่า, มีประตูสู่ Mist City
- **วัด:** ดูดวงรายวันจากพระ + ตู้ทำบุญ (merit เพิ่มโอกาสดวงดี)

---

## 4. Terrain (พื้นผิว) — ปัจจุบัน 15 ชนิด

| โค้ด | ชนิด | เดินผ่าน? |
|---|---|---|
| `.` `,` | หญ้า 2 เฉด | ได้ |
| `P` | ทางเดิน | ได้ |
| `d` | ดิน | ได้ |
| `W` | น้ำ | **ตัน** (ตกปลาได้) |
| `S` | หิน (เหมือง) | **ตัน** |
| `#` | กำแพง | **ตัน** |
| `F` | พื้นในอาคาร | ได้ |
| `T` `m` `@` | พื้นวัด / พรมแดง / กำแพงวัด(ตัน) | ได้/ได้/ตัน |
| `n` `N` | ทรายแห้ง / ทรายเปียก | ได้ |
| `k` `K` | ไม้กระดาน (ท่าเรือ) 2 เฉด | ได้ |

> ดินที่ขุด (tilled) / รดน้ำ (watered) เป็น "เลเยอร์ทับ" ไม่ใช่ tile แยก

### Terrain ที่น่าสร้างเพิ่ม (ช่องว่างที่เห็น)
1. **หิมะ / น้ำแข็งบนพื้น** — มี weather "snow" + พืชฤดูหนาวแล้ว แต่ "พื้น" ไม่เคยเปลี่ยนเป็นหิมะ (ฤดูหนาวหน้าตาเหมือนเดิม)
2. **ไบโอมเหมืองลึก** — ตอนนี้เหมืองมีแค่ หิน/กำแพง/พื้น เหมือนกันทุกชั้น → เพิ่ม lava/หินร้อน, น้ำแข็งถ้ำ, คริสตัล ตามความลึก
3. **หญ้ามีดอก / พุ่ม / ตอไม้** เป็น tile (ตอนนี้เป็น prop) เพื่อความหลากหลายของทุ่ง
4. **โคลน/หนองน้ำ, ทะเลทราย, ถ้ำมืด** ถ้าจะเพิ่ม area ใหม่
5. **พื้นในอาคารหลายแบบ** — พรม/ไม้/กระเบื้อง (ตอนนี้ build เปลี่ยนสีพื้น/ผนังได้ แต่ texture เดียว)
6. **สะพานไม้/หินข้ามน้ำ** (มี pier แล้ว ต่อยอดเป็นสะพานเชื่อม area)

---

## 5. Particle — ปัจจุบัน 8 ตัวปล่อย (emitter), รูปแบบเดียว (วงกลมจางหาย)

ระบบ particle เป็นวงกลมโปร่งใสจางตามอายุ + ตัวเลือก glow (โหมดเรืองแสง) เท่านั้น

| emitter | ใช้ตอน |
|---|---|
| `dust` | ขุดดิน / ก้าวเดิน / ปลูก |
| `splash` | ตกปลา / รดน้ำ / น้ำกระเซ็น |
| `sparkle` | เก็บเกี่ยว / เลเวลอัป / โต้ตอบ / ดวง |
| `hit` | ฟันมอนสเตอร์โดน |
| `chips` | ทุบหิน / ฟันต้นไม้ (เศษ) |
| `footstep` | ฝุ่นรอยเท้า |
| `mote` | ฝุ่นละออง (กลางวัน) / หิ่งห้อยเรืองแสง (กลางคืน) |
| `leaf` | ใบไม้ปลิว (ในป่า/ฟาร์ม/เมือง) |

### Particle ที่น่าสร้างเพิ่ม (ช่องว่างที่เห็น)
1. **ฝน / หิมะตก** — มี weather rain/snow แล้ว แต่ "ไม่มีอนุภาคฝน/หิมะตกให้เห็น" (ช่องว่างใหญ่สุด)
2. **ควัน/ไฟ** — เตาผิง, เตาทำอาหาร, คบไฟ, ไฟในเหมือง
3. **ฟองอากาศ / คลื่นวงกลมบนน้ำ** ตอนตกปลา/ปลากินเหยื่อ
4. **อนุภาครูปทรง** (ดาว/หัวใจ) แทนวงกลมล้วน — sparkle/gift/เลเวลอัปจะมีเอกลักษณ์ขึ้น
5. **เอฟเฟกต์เวทย์/วาร์ป** ตอนเดินทะลุ area หรือเข้า Mist City
6. **คอนเฟตตี/ดอกไม้ไฟ** ตอนงานเทศกาล (festival)
7. **เลือด/ฝุ่นตามชนิดมอนสเตอร์** (สไลม์กระเด็นเขียว, โครงกระดูกเป็นกระดูก ฯลฯ)
8. **หมอกพื้น/ไอน้ำ** เป็น particle (Mist City ใช้ overlay อยู่ แต่ยังไม่มี wisp ลอย)

---

## 6. เนื้อหา (จำนวนปัจจุบัน)

| หมวด | จำนวน | รายการ |
|---|---|---|
| **พืช (crops)** | 16 | parsnip, potato, cauliflower, green_bean, melon, tomato, blueberry, pepper, pumpkin, corn, cranberry, eggplant, winter_root, snow_yam, crocus, frost_melon |
| **ปลา (fish)** | 33 | น้ำจืด + น้ำเค็ม 5 เทียร์ (common→leviathan) |
| **อาหาร (foods)** | 14 | fried_egg, milk_tea, veg_stew, fish_dinner, pumpkin_soup, fruit_salad, roast_meat, cheese, veggie_omelette, corn_soup, steak_plate, pumpkin_pie, egg_custard, goat_cheese |
| **วัตถุดิบ/แร่/ดรอป (materials)** | 21 | stone, wood, copper, iron, gold_ore, iridium_ore, slime_goo, bat_wing, bone, essence, void_essence, meat, hide, pelt + ดรอป Mist City (scrap_iron, wire, old_coin, gear_scrap, old_battery, mutant_herb, tainted_crystal) |
| **มอนสเตอร์ (monsters)** | 16 | สไลม์/ค้างคาว/โครงกระดูก/ซอมบี้/โกเลม/วิญญาณ + บอส (slime_king, rock_titan, void_overlord) + สัตว์ป่า (boar, deer, wolf, bear, tiger, wild_man) |
| **ซอมบี้ Mist City** | 3 | walker, runner, worker |
| **สัตว์เลี้ยง (animals)** | 5 | chicken→egg, duck→duck_egg, sheep→wool, cow→milk, goat→goat_milk |
| **เฟอร์นิเจอร์ (furniture)** | 43 | Living 10 · Bedroom 7 · Kitchen 9 · Decor 15 · Crafting 2 |
| **props (ของตกแต่ง)** | 46 | วัด/ฟาร์ม/ชายหาด/เล้า ฯลฯ |
| **NPC** | 4 | Mira, Tomas, Elya, Luang Por (พระ) |

---

## 7. ระบบเกม (Systems)

- **เครื่องมือ 6 ชิ้น:** hoe, watering_can, pickaxe, axe, sword, fishing_rod
- **อัปเกรดเครื่องมือ 5 เทียร์:** Basic→Copper→Iron→Gold→Iridium (ที่ Workbench, ใช้แร่+เงิน)
- **สกิล 5 สาย:** farming, mining, foraging, fishing, combat (เก็บ XP → เลเวล → perk)
- **ตกปลา:** ระบบ reel 5 เทียร์, ปลาในตำนานต้องสับจังหวะ, มีปลาน้ำจืด/ทะเลแยก
- **ดวงรายวัน (วัด):** lucky/unlucky มีผลกับ loot/ตกปลา/เก็บเกี่ยว, ทำบุญเพิ่มโอกาส
- **เควสต์ (quest board):** สุ่มจากทะเบียนของ, ส่งของรับเงิน
- **NPC:** คุย/ให้ของขวัญ → เพิ่มหัวใจ → รางวัล
- **ปรุงอาหาร (stove):** 14 สูตร ฟื้น energy/HP
- **เลี้ยงสัตว์ (coop):** เก็บผลผลิตรายวัน + เครื่องเก็บอัตโนมัติ
- **Build mode:** วาง/หมุน/อัปเกรดเฟอร์นิเจอร์ในบ้าน, เปลี่ยนสีพื้น/ผนัง
- **In-Sync (เล่นคู่):** ผู้เล่นสองคนอยู่ใกล้กันต่อเนื่อง → หัวใจลอยระหว่างตัว + ฟื้นพลังงานช้าๆ ร่วมกัน + ป้าย "In Sync" บน HUD (ให้รางวัลการเล่นเคียงข้างกัน; อยู่ใน social_system.update_coop_bond)
- **เวลา/วัน/ฤดู:** นอนเพื่อข้ามวัน, พืชโตตามวัน
- **อากาศ 3 แบบ:** sunny / rain (รดน้ำให้ฟรี) / snow (ฤดูหนาว)
- **เทศกาล 4 ฤดู:** Flower Festival, Summer Luau, Harvest Fair, Star Festival (แผงรับรางวัล)
- **Gallery:** ดูโมเดลทุกตัว 9 หมวด (Tools/Items/Characters/Animals/Monsters/Props/Furniture/Terrain/Mist City) — เป็น "แหล่งความจริงของอาร์ต"
- **เสียง:** 6 แทร็กตามพื้นที่ (town/forest/mine/temple/beach/mistcity) + default, สังเคราะห์ด้วยโค้ด
- **เซฟ:** อัตโนมัติ, อยู่ที่ %APPDATA%\HarvestDuo (กันไฟล์เสียหาย)

---

## 8. ประเด็นชวนคิด: ควรเพิ่ม / ตัดอะไร

**จุดที่ "บาง" อยู่ (อาจเพิ่ม):**
- NPC แค่ 4 คน + ไม่มีระบบแต่งงาน/มิตรภาพลึก → เพิ่มคน + เนื้อเรื่อง/เควสต์ NPC
- อากาศไม่มีภาพ (ฝน/หิมะ/พายุ) → ผูกกับ particle/terrain ใหม่
- เหมืองหน้าตาเหมือนกันทุกชั้น → ไบโอมตามความลึก
- ฤดูหนาวไม่มีพื้นหิมะ
- ไม่มีระบบพลังงาน/หมดแรงที่ลงโทษชัด (energy มีแต่ผลเบา)
- ของตกแต่งนอกบ้าน / จัดสวนฟาร์มยังจำกัด

**จุดที่อาจ "ตัด/รวบ" ได้ (ถ้าจะคุมสโคป):**
- มอนสเตอร์ 16 ชนิด + สัตว์ป่า — ถ้าเน้นฟาร์มอาจรวบบางตัว
- Mist City เป็นโหมดแยกใหญ่ — ถ้าทรัพยากรจำกัด อาจโฟกัสฟาร์มก่อน
- ปลา 33 ชนิด เยอะมาก — เก็บได้ แต่ถ้าจะลดภาระ art ก็รวบเทียร์ได้

**ลำดับที่คุ้มสุด (ผลเยอะ แรงน้อย):**
1. particle ฝน/หิมะ + พื้นหิมะฤดูหนาว (ทำให้ฤดู/อากาศ "รู้สึกได้")
2. ควัน/ไฟจากเตา + ฟองน้ำตอนตกปลา (ชีวิตชีวาเล็กๆ ทั่วเกม)
3. ไบโอมเหมืองตามชั้น (ยืดอายุการเล่น late‑game)
4. NPC + เนื้อเรื่องเพิ่ม (เพิ่มเป้าหมายระยะยาว)

---

*ไฟล์นี้ดึงตัวเลขจากโค้ดจริง ณ วันที่ระบุด้านบน — แก้เกมแล้วตัวเลขอาจเปลี่ยน*

---

## อัปเดตสถานะ 2026-07-13 (สำคัญ: ส่วน "ที่น่าสร้างเพิ่ม" ด้านบนล้าสมัยไปหลายข้อ)

หลายช่องว่างที่ลิสต์ไว้ข้างบน **ทำเสร็จแล้ว** ในโค้ดจริง — เช็กโค้ดก่อนวางแผนเพิ่ม:

- **อากาศเห็นได้แล้ว:** ฝน (streak 2 เลเยอร์) + หิมะตก (flake 2 เลเยอร์) วาดใน `render_system._draw_weather`; ฤดูหนาว "พื้นเป็นหิมะ" ทับพื้นเปิดโล่งแล้ว (`_SNOW_GROUND`/`_snow_ov`)
- **particle ครบขึ้นมาก:** มี smoke (ควันปล่องไฟ), flame (เทียนวัด), ember (เหมืองลาวา), bubble+ripple (ตกปลา), warp burst (เดินข้าม area), confetti (เทศกาล), heart (คาบานาครบรอบ + In-Sync) — ทั้งหมดต่อสายใน `render_system._ambient_fx`
- **ไบโอมเหมืองตามชั้นมีแล้ว:** `world._mine_biome` → rock(1-4)/ice(5-9)/lava(10-14)/crystal(15+) มีพื้น/สีหิน/ore bias ต่างกัน + (ใหม่) ambient particle ครบทุกไบโอม
- **มีคาบานาครบรอบ (beach) + นั่งเฟอร์นิเจอร์ + In-Sync** สำหรับประสบการณ์เล่นคู่

**Frontier ที่ยังบางจริง (คุ้มทำต่อ):**
1. **Late-game เหมือง:** ไบโอมต่างกันแค่ผิว+ore เล็กน้อย → เพิ่ม "มอนสเตอร์/อันตราย/ของหายากเฉพาะไบโอม" และไบโอมที่ 5+ (ตอนนี้ 15+ เป็น crystal ตลอด)
2. **Co-op เพิ่ม:** ต่อยอดจาก In-Sync → อีโมทกดเอง, ให้ของขวัญกันเอง (P1↔P2), เควสต์/เป้าหมายคู่, ผูก memory gallery ให้เด่นขึ้น
3. **เนื้อเรื่อง/NPC:** ยังมี 4 คน ไม่มีเนื้อเรื่องหลัก/แต่งงาน

*(บันทึกโดยการอ่านโค้ดจริง 2026-07-13; ส่วนบนของไฟล์ยังไม่รื้อ เก็บไว้เทียบประวัติ)*

---

## อัปเดต 2026-09-26 — "Level-Up" (8 โดเมนอัปเกรดพร้อมกัน)

> ตัวเลขในส่วนนี้นับจาก **ทะเบียนในโค้ดจริง** (โหลดเกมแบบ headless แล้วนับ `crops.CROPS`, `fishing.FISH`, `cooking.FOODS`,
> `loot.MATERIALS`, `monsters.ARCHETYPES`, `npc.NPC_DATA`, `world.areas`, `assets.PROPS`, `furniture.CATALOG`,
> `progress.ACHIEVEMENTS`, `forage.FORAGE`, `weather.ALL` ฯลฯ) ณ วันที่ 2026-09-26 ระหว่างรอบแก้บั๊กหลังอัปเกรด — ตัวเลขอาจขยับเล็กน้อย
> รายละเอียดฟีเจอร์ + วิธีลองเล่น: `docs/WHATS_NEW_2026-09-26.md` · สัญญาร่วม/ความเป็นเจ้าของ: `docs/UPGRADE_2026-09.md`

### การควบคุม (ปุ่มใหม่)
- **F** (P1) / **/** (P2) = อีโมท (กดซ้ำเพื่อวน, เปลี่ยนปุ่มได้ใน Settings > Controls)
- **J** = Journal · **B บนฟาร์ม** = Decor mode (ในบ้านยังเป็น Build) · I = กระเป๋า · Esc · F11

### เนื้อหา (จำนวนปัจจุบัน)

| หมวด | 2026-06-08 | **2026-09-26** | รายละเอียด / ของใหม่ |
|---|---|---|---|
| **พืช (crops)** | 16 | **20** | + พืชพรีเมียมขายใน Farm Supplies: strawberry (Spring), starfruit (Summer), grape (Fall), ice_berry (Winter) |
| **ปลา (fish)** | 33 | **33** | เท่าเดิม แต่มีขนาด cm + สถิติต่อสายพันธุ์ + หีบสมบัติ + hot spot |
| **อาหาร (foods)** | 14 | **26** | + buff food 8 (spicy_curry, lucky_dumplings, miners_pie, sushi_roll, farmers_lunch, hero_stew, yam_porridge, honey_tea) + เมนูของป่า 4 (wild_salad, berry_tart, hazelnut_cookies, mushroom_soup) — เมนูที่ให้บัฟรวม **10** |
| **วัตถุดิบ/ไอเทม (loot.MATERIALS)** | 21 | **127** | แยกตาม cat ด้านล่าง |
| **มอนสเตอร์ (ARCHETYPES)** | 16 | **28** | ในเหมือง 17 (ใหม่ 10: ice_bat, snow_golem, magma_slime, fire_imp, crystal_golem, prism_wisp, shadow_stalker, abyss_wraith, ruin_guardian, cursed_knight) + **บอส 5** (slime_king, rock_titan, void_overlord + ใหม่ abyss_wyrm, ruin_colossus) + สัตว์ป่าล่าได้ 6 (boar, deer, wolf, bear, tiger, wild_man) |
| **ซอมบี้ Mist City** | 3 | **4 + บอส 1** | walker, runner, worker, **hazmat** + **The Bell Keeper** |
| **สัตว์เลี้ยง** | 5 | 5 | + ระบบ affection (หัวใจ 5 ดวง, ลูบ, ผลผลิต LARGE) |
| **NPC** | 4 | **8** | Mira, Tomas, Elya, Luang Por + **Fah, Kai, Somchai (Grandpa Somchai), Luna** — หัวใจสูงสุด 10 ดวง (500 แต้ม) |
| **Heart events** | 0 | **32** | 8 คน × ที่ 2/4/6/8 หัวใจ |
| **พื้นที่ (areas)** | 8 + Mist City | **9 + Mist City** | + **meadow** (Flower Meadow, 40×30) · Mist City มี **3 โซน** (Main Street, Old Factory, Clock Tower) |
| **ไบโอมเหมือง** | 4 | **6** | rock 1-4, ice 5-9, lava 10-14, crystal 15-19, **abyss 20-29**, **ruins 30+** (+ อันตรายพื้น: บ่อลาวา, รอยแยก void) |
| **Terrain tiles** | 15 | **23** | + ABYSS `v`, RUINS `u`, COBBLE `o`, SNOW `*`, SNOWPATH `~` (และพื้นไบโอม ice/lava/crystal ที่มีมาตั้งแต่ 07-13) |
| **props** | 46 | **103** | ฟาร์ม/ทุ่ง/Promise Tree/ซากโบราณ/กระดาน Restoration/ของตกแต่งจากการบูรณะ ฯลฯ ผ่าน `assets.register_prop` |
| **เฟอร์นิเจอร์ในบ้าน** | 43 | **56** | Living 11 · Bedroom 7 · Kitchen 9 · Decor 15 · Crafting 2 · Tabletop 12 |
| **ของตกแต่งนอกบ้าน (decor mode)** | 0 | **14** | wood/stone fence, stone/brick path, flower bed, lamp post, bench, garden arch, bird bath, garden gnome, pumpkin stack, lantern string, picnic blanket, deluxe scarecrow (10-200g) |
| **เครื่องแปรรูป (artisan machines)** | 0 | **5** | Preserves Jar, Keg, Cheese Press, Mayo Machine, Bee House |
| **Achievements** | 0 | **37** | เก็บเกี่ยว/ตกปลา/เหมือง/บอส/อัญมณี/คราฟต์/ทำอาหาร/มิตรภาพ/เล่นคู่/artisan/bundle/เทศกาล/Mist City/รายได้ |
| **Bundles (Valley Restoration)** | 0 | **7** | Spring Harvest, Summer Bounty, Angler's Catch, Miner's Haul, Forager's Basket, Chef's Table, Together |
| **ของป่า (forage.FORAGE)** | 0 | **19** | ฤดูละ 3-4 ชนิด + ชายหาด 5 ชนิด (+ ผลไม้จากสวนผลไม้ apple, persimmon = cat "forage" รวม 21) |
| **อากาศ (weather.ALL)** | 3 | **6** | sunny, rain, snow + **storm, fog, windy** (+ รุ้งเช้าหลังฝน, พยากรณ์ล่วงหน้า) |
| **เทศกาลที่มีมินิเกม** | 0 | **4** | Spring Egg Hunt, Summer Luau Potluck, Fall Harvest Fair, Winter Lantern Night |
| **Particle emitters** | 8 | **23** | + star_burst, coin_burst, ring, petal, poof, rain_splash (และชุดที่เพิ่มช่วง 07-13) |
| **เสียงเอฟเฟกต์ (SFX)** | – | **47** | + emote (5 แบบ), gift, thunder, achievement, coin, forage, unlock, page, bell, crit, boss_roar, craft, splash_big, error ฯลฯ + ambience ฝน/พายุ/ลม |
| **แท็บ Journal** | – | **9** | Guide, Achievements, Collection, Farm, Friends, Bundles, Places, Mist City, Stats |
| **Gallery** | 9 หมวด | Items 226 · Characters 9 · Animals 5 · Monsters 28 · Props 103 · Furniture 56 · Terrain 18 · Mist City 9 · Tools 6 | ดึงจากทะเบียนทั้งหมด (รวมชาวบ้านใหม่และโมเดล Mist City) |

**loot.MATERIALS แยกตาม cat (รวม 127):**

| cat | จำนวน | รายการ |
|---|---|---|
| resource | 2 | stone, wood |
| ore | 4 | copper, iron, gold_ore, iridium_ore |
| mat | 15 | ดรอปมอนสเตอร์ (slime_goo, bat_wing, bone, essence, void_essence, meat, hide, pelt) + ดรอป Mist City 7 (scrap_iron, wire, old_coin, gear_scrap, old_battery, mutant_herb, tainted_crystal) |
| **gem** | 5 | amethyst, ruby, emerald, diamond, prismatic_shard |
| **relic** | 4 | ancient_relic, cursed_gear, city_key, twin_locket |
| **bomb** | 2 | bomb, mega_bomb |
| **tool** | 1 | rope_ladder |
| **forage** | 21 | ของป่า 19 + apple, persimmon |
| **artisan** | 65 | jam_* / wine_* (ผลไม้ + ของป่า + ผลไม้สวน), pickles_* / juice_* (ผัก + เห็ด/wild leek), cheese_wheel, goat_cheese_wheel, mayonnaise, duck_mayonnaise, honey, wildflower_honey, mead |
| **machine** | 5 | machine_preserves_jar, machine_keg, machine_cheese_press, machine_mayo_machine, machine_bee_house |
| **farming** | 2 | fertilizer, quality_fertilizer |
| **trophy** | 1 | golden_egg |

### ระบบเกมที่เพิ่มในรอบนี้ (สรุป 1 บรรทัดต่อระบบ)
- **Co-op:** อีโมท 8 แบบ + emote wheel, Love boost, ให้ของ P1↔P2, การ์ด End of Day + สถิติตลอดชีพ (แท็บ Stats)
- **อากาศ/เสียง:** storm/fog/windy + รุ้ง + พยากรณ์ (TV), ambience วน, เพลง music box ตอนกลางคืน/ฝนตก
- **ต่อสู้:** คริติคอล, knockback, ตัวเลขดาเมจ, telegraph เรืองแสง, ระเบิด/Mega Bomb/Rope Ladder (แท็บ Crafting ที่ Workbench), บอส enrage
- **ฟาร์ม:** เครื่องแปรรูป, ปุ๋ย 2 แบบ, buff food (บัฟ 8 ชนิด: speed/luck/mining/fishing/farming/combat/defense/regen), ร้านแบ่งหมวด + "HOT TODAY +50%", affection สัตว์
- **ตกปลา/ของป่า:** ขนาดปลา + สถิติ, หีบสมบัติ, bite "!", hot spot, ของป่าสุ่มรายวัน (เซฟ), ของป่ากินได้, สัตว์ป่าประดับฉาก
- **เรื่องราว:** ตารางเวลาชาวบ้าน (+ ตารางวันฝน, ร่ม), บทพูดตามบริบท, ของขวัญชอบ/ไม่ชอบ + วันเกิด, heart events + ดูซ้ำ, Valley Restoration, เควสต์ผูกชาวบ้าน, บัฟ Blessed/Harmony ที่วัด
- **โลก:** ฟาร์มโฉมใหม่ (ทางหิน, ท่าเรือ, สวนผลไม้เขย่าได้, ไฟทาง, ป้ายชื่อฟาร์ม), Flower Meadow + Promise Tree (milestone 7/30/100), Decor mode
- **UI:** Journal, HUD ใหม่ (การ์ดนาฬิกา, แผงผู้เล่น, ชิปบัฟ), toast การ์ด, title screen เคลื่อนไหว, พื้นโลกตามฤดู + เร็วขึ้น ~4 เท่า (pre-render พื้น), iris + การ์ดชื่อพื้นที่
- **Mist City V2:** 3 โซน, บอส Bell Keeper, random events 4 แบบ, NOISE meter, threat level, สถิติถาวร + แท็บ Journal, RUN SUMMARY
- **โครงสร้างโค้ด:** hook bus (`src/systems/hooks.py`) + event bus (`self.emit`) ทำให้ 8 โดเมนเสียบระบบใหม่ได้โดยไม่แก้ไฟล์กลาง, เทสต์รายโดเมน `tools/tests/test_*.py`

### ช่องว่าง "Frontier" ที่ปิดไปแล้วจากรายการ 2026-07-13
1. ~~Late-game เหมือง~~ → มีมอนสเตอร์/อันตราย/อัญมณีเฉพาะไบโอม + ไบโอมที่ 5-6 (abyss, ruins) + บอสใหม่ 2 ตัว
2. ~~Co-op เพิ่ม~~ → อีโมท, ให้ของกันเอง, Love boost, Promise Tree, bundle "Together", day report
3. ~~เนื้อเรื่อง/NPC 4 คน~~ → 8 คน + heart events 32 ฉาก + Valley Restoration (เป้าหมายระยะยาว)

### Frontier ใหม่ (ยังบาง/คุ้มทำต่อ) — เรียงตามความคุ้ม
1. **LAN ให้เท่าเครื่องเดียว:** การ์ด End of Day / heart event / กระดาน Restoration / ผลล่าไข่ ยังโชว์เฉพาะ host, client ยังไม่เห็น telegraph
   และกระสุนมอนสเตอร์, Decor mode และ Mist City ยังเล่นบน client ไม่ได้, ของป่า/เครื่องแปรรูปฝั่ง client อัปเดตตามรอบ sync เท่านั้น
2. **ที่ใช้ของสะสม (item sink):** relic/gem/golden_egg/สถิติปลา ตอนนี้แค่ขายได้ → **พิพิธภัณฑ์/ตู้โชว์ในบ้าน** หรือบริจาคเข้ากระดานในเมือง
   (ต่อยอดจาก Collection + Achievements ที่มีอยู่แล้ว)
3. **Mist City V3 ที่เหลือ:** โซนโรงพยาบาล, ห้องลับ, โปสเตอร์/ของสะสมเข้าระบบแต่งบ้าน, สูตรคราฟต์จากชิ้นส่วน (รั้วเหล็ก/เครื่องปั่นไฟ),
   เควสต์ชาวบ้านผูกเมืองร้าง, วาร์ปถาวร, เนื้อเรื่องต้นกำเนิดหมอก (ดู `docs/TASK_mist_city.md`)
4. **หลัง Valley Restored:** ยังไม่มีเนื้อเรื่องหลัก/ฉากจบหรือเป้าหมายปีที่ 2 → ชุด bundle ปีสอง, เควสต์ยาวต่อเนื่อง, ความสัมพันธ์ระหว่างชาวบ้านด้วยกัน,
   pathfinding ของชาวบ้าน (ตอนนี้เดินตรงแล้ววาร์ปถ้าติด)
5. **ฟาร์มเชิงลึก:** คุณภาพผลผลิต (ดาว), เรือนกระจก/ปลูกข้ามฤดู, สัตว์ชนิดใหม่ (หมู/กระต่าย) + อัปเกรดเล้า, sprinkler หลายระดับ
6. **อากาศมีผลกับเนื้อหา:** ปลา/ของป่าเฉพาะพายุ-หมอก-ลมแรง, ว่าวในวันลมแรง, สายล่อฟ้า — ตอนนี้ storm/fog/windy เป็นภาพ + รดน้ำเป็นหลัก
7. **Decor เพิ่ม:** ของตกแต่งตามฤดู/เทศกาล, แสดงบน minimap, วางใน Meadow ได้, ของรางวัลจาก achievement เป็นชิ้นตกแต่ง
8. **เหมืองลึกมาก (75-100):** HP บอส/ruins สูงมาก → ปรับสมดุล หรือเพิ่มไบโอมที่ 7 (50+) พร้อมกลไก/ปริศนาในซากโบราณ
9. **ความทรงจำคู่:** อัลบั้มภาพ/photo mode ผูก Promise Tree milestone + วันครบรอบ (มี `anniversary.html`/`memories` อยู่แล้วนอกเกม)

*(ส่วนนี้เขียนโดยฝ่ายเอกสาร 2026-09-26 จาก build reports ของ 8 โดเมน + การนับทะเบียนในโค้ดจริง)*
