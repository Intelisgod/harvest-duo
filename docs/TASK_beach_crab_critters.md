# งานส่งต่อ: ปูบรรยากาศเดินซ้าย-ขวาบนหาด (ambient prop, ไม่ใช่ศัตรู)

> เตรียมโดย Chat 2 (Farming/Shop) — งานนี้ **ไม่ใช่โดเมน Chat 2** กินไฟล์ของ Chat 5 + Core + Chat 6
> ปูเป็น prop ตกแต่งที่ขยับได้: เดินซ้าย-ขวาช้าๆ หยุดเป็นพักๆ เลี้ยวกลับ — ไม่ไล่ผู้เล่น ไม่ชน ไม่ทำดาเมจ

## ทำไมไม่ใช่ Chat 2
Chat 2 = ฟาร์ม/ร้านค้า/พืช/สัตว์เลี้ยง(ปศุสัตว์ในเล้า)/อาหาร ปูบนหาดไม่เกี่ยวกับเศรษฐกิจ/การเก็บเกี่ยว
`critters.py` (Chat 3) เป็นแค่ตัววาดสไปรต์ ไม่มีลูปเคลื่อนไหว และยังไม่มีระบบ "critter บรรยากาศที่ขยับ" เลย
จึงต้องสร้างใหม่ ใช้ pattern เดิมของ `area.animal_spawns` (world.py:215 + Game._spawn_area_entities)

---

## ส่วนที่ 1 — Chat 5 (world.py): จุดเกิดปู

ในฟังก์ชันสร้าง AREA_BEACH (รอบบรรทัด ~338) เพิ่ม list จุดทรายที่ปูจะเดิน เลียนแบบ `animal_spawns`:

```python
# ปูบรรยากาศ: เลือกไทล์ทราย (เดินได้ ไม่ใช่ไทล์น้ำ) แถบใกล้ชายฝั่ง
area.crab_spawns = [(gx, gy) for (gx, gy) in <ไทล์ทรายที่เหมาะ>]  # ~4-6 จุด
```
ถ้าไม่อยาก compute ก็ฮาร์ดโค้ดได้ เช่น `area.crab_spawns = [(6,18),(11,20),(15,19),(20,21),(24,18)]`
(เลือกพิกัดที่เป็นทรายเดินได้จริงในแมป beach)

> ค่า default: ใน Area.__init__ เพิ่ม `self.crab_spawns = []` เพื่อให้ area อื่นไม่มีปูแล้วไม่พัง

---

## ส่วนที่ 2 — Core (game.py): สร้าง + ขยับปู

**(ก) เพิ่ม field** — ใน `_spawn_area_entities()` (รอบบรรทัด ~228) ท้ายฟังก์ชัน:
```python
import random as _r
self.beach_critters = []
for (gx, gy) in getattr(area, "crab_spawns", []):
    cx = gx * TILE + TILE / 2
    self.beach_critters.append({
        "x": cx, "y": gy * TILE + TILE * 0.7,
        "dir": _r.choice((-1, 1)), "spd": _r.uniform(14.0, 26.0),
        "flip_t": _r.uniform(1.5, 3.5), "pause_t": 0.0,
        "home_x": cx, "rng": TILE * 3.0, "bob": _r.uniform(0, 6.28),
    })
```
> `_spawn_area_entities` ถูกเรียกทั้งตอน __init__ และตอน warp อยู่แล้ว — ปูจะรีเซ็ตเมื่อเข้าหาดใหม่
> ไม่ต้องใส่ลง save schema (เป็นของตกแต่ง สุ่มใหม่ได้ทุกครั้งที่เข้า area)

**(ข) ขยับทุกเฟรม** — ใน `update(self, dt)` (รอบบรรทัด ~402) เพิ่มบล็อก:
```python
import random as _r
for c in self.beach_critters:
    c["bob"] += dt * 6.0
    if c["pause_t"] > 0:
        c["pause_t"] -= dt
        continue
    c["x"] += c["dir"] * c["spd"] * dt
    c["flip_t"] -= dt
    out = abs(c["x"] - c["home_x"]) > c["rng"]
    if c["flip_t"] <= 0 or out:                  # เลี้ยวกลับ / สุ่มหยุดเดินแบบปูจริง
        c["dir"] *= -1
        c["flip_t"] = _r.uniform(1.5, 3.5)
        if _r.random() < 0.3:
            c["pause_t"] = _r.uniform(0.4, 1.2)
        c["x"] = max(c["home_x"] - c["rng"], min(c["home_x"] + c["rng"], c["x"]))
```
> ปูไม่ชน/ไม่ทำดาเมจ — ไม่ต้องแตะ collision หรือ player update เลย

---

## ส่วนที่ 3 — Chat 6 (assets + render_system): สไปรต์ + วาด

**(ก) สไปรต์ปู** — เพิ่มใน assets (หมวด terrain.py หรือ items.py ก็ได้ ใช้ helper จาก _base เท่านั้น)
ตามคอนเวนชันเดียวกับ critters: `crab(s, cx, cy, sz, fl, col=(214, 92, 70))`
- ตัว: วงรีแบนกว้าง สีส้ม-แดง มีขอบเข้ม
- ตาก้าน 2 อันชี้ขึ้น (จุดดำปลายก้าน)
- ขา 3-4 คู่สองข้าง, ก้ามใหญ่ 2 อันด้านหน้า
- `fl` พลิกซ้าย/ขวา (mirror) ให้หันตามทิศเดิน; จะใช้ `c["bob"]` ทำขาขยับเล็กน้อยก็ได้

**(ข) วาดในลูป** — ใน render_system ส่วน draw_entities เพิ่ม pass วาดปู (ใช้ camera offset แบบเดียวกับ
entity อื่น) เรียงตาม y ให้ซ้อนถูก:
```python
for c in getattr(self, "beach_critters", []):
    sx, sy = self.cam.world_to_screen(c["x"], c["y"])   # ใช้คอนเวนชัน cam ของโปรเจกต์
    assets.crab(surf, sx, sy, sz=7, fl=c["dir"])
```
(ปรับชื่อ cam/helper ให้ตรงของจริงในเลเยอร์ render)

---

## ลำดับการทำ (build เขียวทุกขั้น)
1. **Chat 5** เพิ่ม `crab_spawns` + default ใน Area.__init__ → เขียว (ยังไม่มีใครอ่าน)
2. **Chat 6** เพิ่มสไปรต์ `crab()` → เขียว (ยังไม่มีใครเรียก)
3. **Core** เพิ่ม spawn + update + draw-hook → ปูเริ่มเดิน
   (Core ใช้ `getattr(area, "crab_spawns", [])` ไว้แล้ว จึงไม่พังถ้า Chat 5 ยังไม่ลง)

## Definition of Done
- py_compile ทุกไฟล์ผ่าน
- headless smoke test: เข้า AREA_BEACH, รัน update หลายเฟรม, ยืนยัน `beach_critters` ขยับ x และเลี้ยวทิศ
  ไม่หลุดออกนอก rng, ไม่กระทบ collision/HP ของผู้เล่น
- กวาดครบ 7 area + save/load ยังเขียว (ปูไม่อยู่ใน save schema — ต้องไม่ทำ save พัง)

## ฝั่ง Chat 2 (เรา) — ไม่ต้องแก้อะไร
ปูไม่มีราคา/ไม่เก็บ/ไม่ขาย จึงไม่แตะ shop/economy ของเราเลย
