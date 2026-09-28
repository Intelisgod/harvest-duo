# งานส่งต่อ: แยกปลาบ่อ/แม่น้ำ (freshwater) ออกจากปลาทะเล/หาดใหม่ (saltwater)

> เตรียมโดย Chat 2 (Farming/Shop) — งานจริงอยู่ในโดเมน **Chat 3 (Fishing & Foraging)** + แก้ **1 บรรทัดใน Core**
> ก็อปบล็อก "PROMPT สำหรับ Chat 3" ด้านล่างไปวางใน chat ของ Chat 3 ได้เลย

---

## เป้าหมาย
ตอนนี้ระบบตกปลามีแค่ 2 แบบ: "บ่อป่า (forest pond)" กับ "น้ำธรรมดา" — `actions_system.py:359`
ส่ง `forest=(area.name == AREA_FOREST)` เป็น bool เดียว หาดใหม่ (`AREA_BEACH` มีใน settings.py แล้ว
สร้างโดย Chat 5) จึงตกได้ปลาชุดเดียวกับฟาร์ม/เมือง ไม่มีความเป็นทะเลเลย

ต้องการ: **3 ประเภทแหล่งน้ำ** — บ่อ/แม่น้ำ (น้ำจืดธรรมดา), บ่อป่า (น้ำจืด + ปลาระดับสูงสุด),
ทะเล/หาด (น้ำเค็ม + ปลาระดับสูงสุดของทะเล) และ **แต่ละแหล่งมีปลาหายาก/ปลาเทพเป็นของตัวเอง**

## การจัดประเภทปลาเดิม (อ้างอิงจริงจากชีววิทยา)

จาก USGS / Wikipedia / Sciencing (ลิงก์ท้ายเอกสาร): sunfish, bluegill, perch, largemouth
bass ล้วนเป็นปลาน้ำจืดวงศ์ Centrarchidae; catfish/sturgeon/pike/trout/salmon เป็นน้ำจืด
(salmon เป็นปลาอพยพ anadromous — โตในทะเลแต่ตกได้ในแม่น้ำตอนวางไข่ จึงจัดเป็น "แม่น้ำ");
anchovy/sardine/tuna/cod/mackerel/herring/snapper/eel(ทะเล)/pufferfish เป็นน้ำเค็ม

| ปลาเดิม | สี่งที่ควรเป็น | หมายเหตุ |
|---|---|---|
| carp, bluegill, sunfish, perch | **น้ำจืด** common | panfish/วงศ์ sunfish — น้ำจืดล้วน |
| bass, salmon, pike | **น้ำจืด** uncommon | bass=largemouth(จืด); salmon=แม่น้ำ(anadromous) |
| catfish, sturgeon, rainbow_trout | **น้ำจืด** rare | แม่น้ำ/ทะเลสาบ |
| anchovy, sardine | **ทะเล** common | ปลาฝูงทะเล |
| tuna | **ทะเล** uncommon | มหาสมุทรเปิด |
| pufferfish, eel | **ทะเล** rare | puffer ทะเลเป็นหลัก; eel ทะเล/น้ำกร่อย |
| crimson_bass, glacier_pike, the_legend | **บ่อป่า** legendary | ธีมน้ำจืด คงไว้ที่บ่อป่า |
| void_eel, phantom_carp, unseeing_maw | **บ่อป่า** leviathan | ธีม eldritch น้ำจืด คงไว้ที่บ่อป่า |
| the_leviathan | **ย้ายไปทะเล** leviathan | ธีมอสูรมหาสมุทร — เหมาะกับทะเลมากกว่า |

> ผลข้างเคียง: ทะเลจะมีปลาน้อย (common 2 / uncommon 1 / rare 2) จึง **เพิ่มปลาทะเลใหม่** ให้เต็มทีเออร์

## ปลาทะเลใหม่ที่ต้องเพิ่ม (ของจริง + แต่งสำหรับ apex)

| id | ชื่อ | ราคา | tier | reel |
|---|---|---|---|---|
| `herring` | Herring | 40 | common | 1 |
| `mackerel` | Mackerel | 50 | common | 1 |
| `cod` | Cod | 115 | uncommon | 2 |
| `red_snapper` | Red Snapper | 130 | uncommon | 2 |
| `halibut` | Halibut | 300 | rare | 3 |
| `swordfish` | Swordfish | 360 | rare | 3 |
| `coelacanth` | Coelacanth | 2400 | legendary | 5 |
| `golden_swordfish` | Golden Swordfish | 1700 | legendary | 5 |
| `abyssal_tuna` | Abyssal Tuna | 1900 | legendary | 5 |
| `kraken_spawn` | Kraken Spawn | 2600 | leviathan | 5 |
| `maelstrom_ray` | Maelstrom Ray | 3000 | leviathan | 5 |

(`the_leviathan` 4200 มีอยู่แล้ว — แค่ย้ายกลุ่มไปทะเล) ราคาอยู่ในแบนด์เดิมของแต่ละทีเออร์

## ปลาหายากเฉพาะแหล่ง (ตามที่ขอ: "แต่ละจุดมีปลาหายากของตัวเอง")

- **บ่อป่า (น้ำจืด)** legendary: crimson_bass, glacier_pike, the_legend · leviathan: void_eel, phantom_carp, unseeing_maw
- **ทะเล/หาด (น้ำเค็ม)** legendary: coelacanth, golden_swordfish, abyssal_tuna · leviathan: kraken_spawn, maelstrom_ray, the_leviathan

---

## PROMPT สำหรับ Chat 3 (ก็อปไปวาง)

```text
เกม Harvest Duo (Pygame). อ่าน docs/ARCHITECTURE.md ก่อน โดเมนนี้: Fishing & Foraging

งาน: แยกปลาน้ำจืด (บ่อ/แม่น้ำ/บ่อป่า) ออกจากปลาทะเล (หาด AREA_BEACH ที่เพิ่งสร้าง)
รายละเอียด+เหตุผล+ราคา/ทีเออร์ครบในไฟล์ docs/TASK_fish_pond_vs_sea.md (อ่านก่อน)

แก้ src/fishing.py:
1) เพิ่มปลาทะเลใหม่ลง FISH_DATA ตามตารางในเอกสาร (herring, mackerel, cod, red_snapper,
   halibut, swordfish, coelacanth, golden_swordfish, abyssal_tuna, kraken_spawn, maelstrom_ray)
2) แทนที่ลิสต์ _COMMON/_UNCOMMON/_RARE/_LEGENDARY/_LEVIATHAN เดิม ด้วยลิสต์แยกน้ำจืด/ทะเล:
   _FRESH_COMMON   = ["carp","bluegill","sunfish","perch"]
   _FRESH_UNCOMMON = ["bass","salmon","pike"]
   _FRESH_RARE     = ["catfish","sturgeon","rainbow_trout"]
   _FRESH_LEGENDARY= ["crimson_bass","glacier_pike","the_legend"]
   _FRESH_LEVIATHAN= ["void_eel","phantom_carp","unseeing_maw"]
   _SEA_COMMON     = ["anchovy","sardine","herring","mackerel"]
   _SEA_UNCOMMON   = ["tuna","cod","red_snapper"]
   _SEA_RARE       = ["pufferfish","eel","halibut","swordfish"]
   _SEA_LEGENDARY  = ["coelacanth","golden_swordfish","abyssal_tuna"]
   _SEA_LEVIATHAN  = ["kraken_spawn","maelstrom_ray","the_leviathan"]
3) เปลี่ยน random_fish(skill=0, forest=False) -> random_fish(skill=0, water="fresh") โดย
   water in {"fresh","pond","sea"} :
   - "pond": ตรรกะ forest เดิม แต่ดึงจาก _FRESH_* (รวม legendary/leviathan น้ำจืด)
   - "sea" : ตรรกะเดียวกับ pond แต่ดึงจาก _SEA_* (legendary/leviathan ทะเล)
   - "fresh": ตรรกะ ordinary water เดิม แต่จำกัดเฉพาะ _FRESH_COMMON/_UNCOMMON/_RARE (ไม่มี apex)
4) FishingState: เปลี่ยน field self.forest -> self.water (ค่าเริ่ม "fresh"), และใน update()
   เรียก random_fish(self.skill, self.water)
5) **COMPAT SHIM (สำคัญ ต้องลงก่อน Core):** ทำ cast() ให้รับได้ทั้ง forest= (เก่า) และ water= (ใหม่)
   เพื่อให้ build เขียวไม่ว่า merge ลำดับไหน:
       def cast(self, skill=0, water="fresh", forest=None):
           if forest is not None:                  # ผู้เรียกเก่ายังส่ง forest=True/False
               water = "pond" if forest else "fresh"
           self.skill = skill
           self.water = water
           ... (ที่เหลือเหมือนเดิม)
   วิธีนี้ทำให้ Core เดิม (ส่ง forest=) ยังทำงานหลัง Chat 3 ลงเสร็จ — Core ค่อยสลับเป็น water= ทีหลัง
   (ลบพารามิเตอร์ forest ทิ้งได้เมื่อ Core สลับครบแล้ว)

ฝั่ง _land_fish (fishing_system.py) ไม่ต้องแก้ตรรกะ — ใช้ tier_of/is_special เหมือนเดิม
ก่อนปิดงาน: py_compile + headless smoke test cast/hook/_land_fish ทั้ง water="fresh"/"pond"/"sea"
ทุกทีเออร์ และยืนยันว่าตกในบ่อป่าได้ปลาน้ำจืด ตกที่หาดได้ปลาทะเล
```

## งานที่ต้องขอ Core (Chat 0) — แก้ actions_system.py แค่บริเวณเดียว

> **ลำดับ:** Core ต้องสลับ **หลัง** Chat 3 ลง compat shim ใน fishing.py แล้วเท่านั้น
> (ถ้าสลับก่อน cast() จะยังไม่รับ water= → TypeError ตอนเหวี่ยงเบ็ด build แดง)

บรรทัด ~359 ปัจจุบัน:
```python
st.cast(eff, forest=(area.name == AREA_FOREST))
```
เปลี่ยนเป็น (และ import `AREA_BEACH` เพิ่มที่หัวไฟล์):
```python
water = ("pond" if area.name == AREA_FOREST
         else "sea" if area.name == AREA_BEACH
         else "fresh")
st.cast(eff, water=water)
```
> ขอ Core ช่วยยืนยันด้วยว่า branch การเหวี่ยงเบ็ดอนุญาตให้ตกที่ไทล์น้ำของ AREA_BEACH
> (ถ้าหาดยังไม่มีไทล์น้ำที่ fishable ต้องประสาน Chat 5/world.py)

## งานที่ต้องขอ Chat 6 (Assets) — ไอคอนปลาใหม่
ปลาทะเลใหม่ 11 ชนิดข้างบนต้องมีไอคอน/สีใน assets (FISH_LOOK / item_icon) ถ้ายังไม่มีจะ fallback
เป็นไอคอนปลา generic — เล่นได้แต่ภาพไม่เฉพาะตัว

## ฝั่ง Chat 2 (เรา/Shop) — ไม่ต้องแก้อะไร
`shop_system.sell_value()` ดึงราคาจาก `fishing.FISH` (= มาจาก FISH_DATA) อยู่แล้ว ปลาใหม่ทุกตัว
จะขายได้อัตโนมัติทันทีที่ Chat 3 ใส่ลง FISH_DATA — ไม่มี hard-code ราคาที่อื่น

---

### แหล่งอ้างอิง (การจัดน้ำจืด/น้ำเค็ม)
- USGS — Freshwater fish: yellow perch, bluegill sunfish, pumpkinseed sunfish, largemouth bass: https://www.usgs.gov/media/images/freshwater-fish-yellow-perch-bluegill-sunfish-pumpkinseed-sunfish-largemouth-bass-a
- Bluegill — Wikipedia: https://en.wikipedia.org/wiki/Bluegill
- Centrarchidae (sunfish family) — Wikipedia: https://en.wikipedia.org/wiki/Centrarchidae
- Freshwater vs Saltwater Fish — Sciencing: https://www.sciencing.com/different-freshwater-vs-saltwater-fish-6307253/
