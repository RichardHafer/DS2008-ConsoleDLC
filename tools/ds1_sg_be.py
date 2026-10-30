"""Read a Dead Space 1 SimGroup, PS3 (big-endian) or PC; list entities and records.

usage: python -I tools/ds1_sg_be.py SIMGROUP [entity index]
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from ds1_records import load_classes  # noqa: E402

CLASSES = load_classes()


def hash_name(name):
    v = 0
    for c in name.lower():
        v = (v * 65599 + ord(c)) & 0xFFFFFFFF
    return v


for extra in ("Entity", "Base", "Item", "StoreItem", "Weapon", "ItemStoreList", "DLCItemStoreList", "Animated",
              "DLCUniformStreamAttributes", "DLCWeaponStreamAttributes", "DLCNPCStreamAttributes", "PickupItem",
              "GunProxy", "Uniform", "Gun", "PlasmaCutter", "LineGun", "ForceGun", "Schematic", "UniformProxy"):
    CLASSES.setdefault(hash_name(extra), extra)


def cname(h):
    return CLASSES.get(h, "%08X" % h)


class GroupBE:
    def __init__(self, path):
        d = bytes(path) if isinstance(path, (bytes, bytearray)) else Path(path).read_bytes()
        self.data = d
        assert d[8:12] in (b"SimG", b"GmiS"), path
        self.e = ">" if d[8:12] == b"SimG" else "<"
        self.count = self.u32(0x18)
        self.guid_base = 0x30 + 4 * self.count
        self.packets = [self.u32(0x30 + 4 * i) for i in range(self.count)]
        self.guids = [struct.unpack_from(self.e + "4I", d, self.guid_base + 16 * i) for i in range(self.count)]

    def u32(self, o):
        return struct.unpack_from(self.e + "I", self.data, o)[0]

    def i32(self, o):
        return struct.unpack_from(self.e + "i", self.data, o)[0]

    def u16(self, o):
        return struct.unpack_from(self.e + "H", self.data, o)[0]

    def records(self, p):
        d = self.data
        # Single bytes, not a 32-bit field: the same offsets on both platforms.
        skip = d[p + 0x1E]
        count = d[p + 0x1F]
        base = p + 0x2C + skip * 4
        out = []
        for k in range(count):
            slot = base + 4 * k
            rec = slot + self.i32(slot)
            if not 0 <= rec < len(d) - 8:
                continue
            ch = self.u32(rec)
            n = self.u16(rec + 4)
            if not n or n > 4096:
                continue
            bitmap = rec + 6
            stream = (bitmap + ((n + 7) >> 3) + 3) & ~3
            vals = []
            at = stream
            for idx in range(n):
                absent = d[bitmap + (idx >> 3)] & (1 << (idx & 7))
                if absent:
                    continue
                vals.append((idx, at))
                at += 4
            out.append((ch, n, vals))
        return out

    def describe(self, at):
        raw = self.u32(at)
        rel = self.i32(at)
        target = at + rel
        d = self.data
        txt = "%08X" % raw
        if (rel < -16 or rel > 0x1000) and 0 <= target < len(d):
            if self.guid_base <= target < self.guid_base + 16 * self.count and (target - self.guid_base) % 16 == 0:
                g = self.guids[(target - self.guid_base) // 16]
                return "-> GUID %s" % "-".join("%08X" % w for w in g)
            s = d[target:target + 80].split(b"\0", 1)[0]
            if len(s) >= 2 and all(0x20 <= c < 0x7F for c in s):
                return "-> '%s'" % s.decode()
            if target + 16 <= len(d):
                return "-> [%s]" % " ".join("%08X" % w for w in struct.unpack_from(self.e + "4I", d, target))
        f = struct.unpack(self.e + "f", d[at:at + 4])[0]
        if raw and 1e-4 < abs(f) < 1e7:
            txt += " (%g)" % f
        return txt


def main():
    g = GroupBE(sys.argv[1])
    only = int(sys.argv[2]) if len(sys.argv) > 2 else None
    print("%d entities" % g.count)
    for i, p in enumerate(g.packets):
        if only is not None and i != only:
            continue
        cls = cname(g.u32(p + 0x28))
        print("%3d %-28s %s" % (i, cls, "-".join("%08X" % w for w in g.guids[i])))
        if only is None:
            continue
        for ch, n, vals in g.records(p):
            for idx, at in vals:
                print("    %-26s %3d %s" % (cname(ch), idx, g.describe(at)))


if __name__ == "__main__":
    main()
