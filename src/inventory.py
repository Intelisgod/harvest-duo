"""Per-player inventory: fixed tools + stackable items, with a player-arrangeable
hotbar locked to 10 slots. Entries are ("tool", name) / ("item", id).

``hotbar_order`` is the player's preferred ordering of ALL entries; the first
HOTBAR_SIZE are the hotbar, the rest are the "backpack" (visible on the
inventory screen, not on the hotbar). The order is reconciled against the real
contents on every read, so code that mutates ``items``/``item_order`` directly
(shop sell-all, save load) can never desync the hotbar.

UI contract (inventory_screen.py): hotbar(), backpack(), move_slot(a, b),
stow(slot), equip(bp_index, slot). set_slot(slot, entry) is also provided.
"""

TOOLS = ["hoe", "watering_can", "pickaxe", "axe", "sword", "fishing_rod"]
TOOL_LABEL = {
    "hoe": "Hoe", "watering_can": "Can", "pickaxe": "Pick",
    "axe": "Axe", "sword": "Sword", "fishing_rod": "Rod",
}

HOTBAR_SIZE = 10                    # locked: the hotbar never shows more slots


class Inventory:
    def __init__(self):
        # ordered item ids so stacking / the default layout is stable
        self.item_order = []
        self.items = {}                 # id -> qty
        self.selected = 0               # index into hotbar() (<= HOTBAR_SIZE)
        # player-arrangeable order of every entry (tools first by default);
        # add() appends new items, so they land on the hotbar while it has
        # room and spill into the backpack afterwards.
        self.hotbar_order = [("tool", t) for t in TOOLS]
        # starting seeds
        self.add("seed:parsnip", 15)

    # ---- items ----
    def add(self, item_id, qty=1):
        if item_id not in self.items:
            self.items[item_id] = 0
            self.item_order.append(item_id)
            # new entry goes to the end: hotbar if < HOTBAR_SIZE, else backpack
            self.hotbar_order.append(("item", item_id))
        self.items[item_id] += qty

    def remove(self, item_id, qty=1):
        if self.items.get(item_id, 0) >= qty:
            self.items[item_id] -= qty
            if self.items[item_id] <= 0:
                del self.items[item_id]
                self.item_order.remove(item_id)
                try:
                    self.hotbar_order.remove(("item", item_id))
                except ValueError:
                    pass
            return True
        return False

    def count(self, item_id):
        return self.items.get(item_id, 0)

    # ---- ordering (self-healing) ----
    def _entries(self):
        """Every entry the player actually owns right now."""
        return [("tool", t) for t in TOOLS] + [("item", i) for i in self.item_order]

    def _reconciled(self):
        """hotbar_order, healed: keep the player's arrangement for entries that
        still exist, drop stale ones, append newly-acquired ones at the end."""
        valid = self._entries()
        vset = set(valid)
        seen = set()
        order = []
        for e in self.hotbar_order:
            if e in vset and e not in seen:
                order.append(e)
                seen.add(e)
        for e in valid:
            if e not in seen:
                order.append(e)
                seen.add(e)
        self.hotbar_order = order
        return order

    def reconcile(self):
        """Public hook (save-load) to heal hotbar_order against real contents."""
        self._reconciled()

    # ---- hotbar / backpack views ----
    def hotbar(self):
        return self._reconciled()[:HOTBAR_SIZE]

    def backpack(self):
        return self._reconciled()[HOTBAR_SIZE:]

    def selected_entry(self):
        bar = self.hotbar()
        if not bar:
            return None
        self.selected %= len(bar)
        return bar[self.selected]

    def cycle(self, delta):
        bar = self.hotbar()
        if bar:
            self.selected = (self.selected + delta) % len(bar)

    # ---- rearranging (called by the inventory screen) ----
    def move_slot(self, src, dst):
        """Swap two hotbar slots (also accepts any two valid positions)."""
        order = self._reconciled()
        n = len(order)
        if 0 <= src < n and 0 <= dst < n and src != dst:
            order[src], order[dst] = order[dst], order[src]
            self.hotbar_order = order

    def stow(self, slot):
        """Send hotbar[slot] to the back of the backpack; whatever was first in
        the backpack shifts up into the freed hotbar slot."""
        order = self._reconciled()
        if 0 <= slot < min(HOTBAR_SIZE, len(order)):
            order.append(order.pop(slot))
            self.hotbar_order = order

    def equip(self, bp_index, slot):
        """Put backpack[bp_index] into hotbar `slot`; the displaced hotbar entry
        takes the backpack spot (a straight swap)."""
        order = self._reconciled()
        src = HOTBAR_SIZE + bp_index
        if 0 <= slot < min(HOTBAR_SIZE, len(order)) and HOTBAR_SIZE <= src < len(order):
            order[slot], order[src] = order[src], order[slot]
            self.hotbar_order = order

    def set_slot(self, slot, entry):
        """Place `entry` (wherever it currently is) into hotbar `slot`, swapping
        with the current occupant. No-op if the entry isn't owned."""
        order = self._reconciled()
        try:
            i = order.index(tuple(entry))
        except ValueError:
            return
        if 0 <= slot < min(HOTBAR_SIZE, len(order)) and i != slot:
            order[slot], order[i] = order[i], order[slot]
            self.hotbar_order = order

    @staticmethod
    def label(entry):
        """Player-facing display name ('Parsnip Seeds', 'Wildflower Honey').
        Drawers that are short on room trim by pixel width themselves."""
        kind, name = entry
        if kind == "tool":
            return TOOL_LABEL[name]
        name = str(name)
        if name in ITEM_LABELS:
            return ITEM_LABELS[name]
        if name.startswith("seed:"):
            crop = name.split(":", 1)[1]
            try:
                from .crops import crop_label
                return crop_label(crop) + " Seeds"
            except Exception:
                return crop.replace("_", " ").title() + " Seeds"
        try:
            from .cooking import FOODS
            if name in FOODS:
                return FOODS[name].get("label", name)
        except Exception:
            pass
        try:
            from . import loot
            return loot.label(name)
        except Exception:
            return name.replace("_", " ").title()


# display-name overrides for ids whose generic name would be ambiguous (the
# premium sprinkler would otherwise read "Sprinkler2")
ITEM_LABELS = {"sprinkler2": "Premium Sprinkler"}
