#!/usr/bin/env python3
"""Read and write authored property values inside a SimGroup packet.

The record format, from the iterator setup at 0x0073ADD0:

    packet+0x1C  byte at +0x1E  pointer slots to skip
                 byte at +0x1F  how many records follow
    packet+0x2C + skip*4        the record pointer array, self-relative

    record+0     class name hash
    record+4     word: how many properties the class has
    record+6     presence bitmap, ceil(count/8) bytes, a SET bit means the
                 property is ABSENT and the constructor default applies,
                 padded up to the next 4-byte boundary
                 then one dword per present property, in index order

The property index is the case index in the class's decoder jump table, so
property n is whatever case n writes.

The one rule that must hold for every edit: values may change, the *number* of
present properties may not.  Adding a property would move every value after it
and every self-relative pointer into the packet.

Used by ds1_variant.py and usable on its own.  Read-only unless a caller asks
for a write.
"""

from __future__ import annotations

import csv
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLASS_TABLE = ROOT / "data" / "DeadSpace1_ClassTable.tsv"


class Record:
    __slots__ = ("class_hash", "offset", "count", "values")

    def __init__(self, class_hash: int, offset: int, count: int, values):
        self.class_hash = class_hash
        self.offset = offset
        self.count = count
        self.values = values          # [(index, absolute value offset)]

    def offset_of(self, index: int):
        for present, at in self.values:
            if present == index:
                return at
        return None


def hash_name(name: str) -> int:
    """The class name hash: sdbm over the lowercased name."""
    value = 0
    for char in name.lower():
        value = (value * 65599 + ord(char)) & 0xFFFFFFFF
    return value


COMPONENTS = (
    "HealthComponent", "DismemberableHealthComponent", "KillComponent",
    "FearComponent", "AwarenessComponent", "ThreatenedComponent",
    "RagdollComponent", "RoutingComponent", "RouteOcclusionComponent",
    "CharacterMovementComponent", "DSNPCGrapplerComponent",
    "DSNPCSpawningComponent", "DSNPCVentComponent", "CadaverousNPCVentComponent",
    "CameraInteractionComponent", "StasisComponent", "TKComponent", "TKData",
    "HavokComponent", "HavokVFXComponent", "TentacleComponent",
    "DeadSpaceNPC", "CadaverousNPC", "Animated", "Entity", "Base",
)


def load_classes() -> dict:
    """Entity classes from the table, plus the components an enemy carries.

    The class table only holds entity classes; the tuning knobs live in
    components, so their names are folded in here and the hash is computed the
    same way the game does.
    """
    out = {}
    if CLASS_TABLE.exists():
        with CLASS_TABLE.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                out[int(row["id"], 16)] = row["class"]
    for name in COMPONENTS:
        out.setdefault(hash_name(name), name)
    return out


def class_id(name: str, classes: dict | None = None) -> int:
    """Accept a class name, a raw 0x-prefixed hash, or a bare hash."""
    text = str(name).strip()
    if text.lower().startswith("0x"):
        return int(text, 16)
    if classes:
        for value, known in classes.items():
            if known == text:
                return value
    if len(text) == 8:
        try:
            return int(text, 16)
        except ValueError:
            pass
    return hash_name(text)


def records_of(data: bytes, packet: int):
    """Every record in one entity's packet, with absolute value offsets."""
    if packet + 0x2C > len(data):
        return []
    header = struct.unpack_from("<I", data, packet + 0x1C)[0]
    skip = (header >> 16) & 0xFF
    count = (header >> 24) & 0xFF
    base = packet + 0x2C + skip * 4
    out = []
    for index in range(count):
        slot = base + index * 4
        if slot + 4 > len(data):
            break
        record = slot + struct.unpack_from("<i", data, slot)[0]
        if record < 0 or record + 8 > len(data):
            continue
        parsed = _parse(data, record)
        if parsed is not None:
            out.append(parsed)
    return out


_LAYOUTS = {}


def _parse(data: bytes, record: int):
    # the value layout depends only on the header, the presence bitmap and the alignment; editors reparse whole
    # groups after every edit, so the layouts are cached (relative to the record)
    if record + 6 <= len(data):
        count = struct.unpack_from("<H", data, record + 4)[0]
        if 0 < count <= 4096:
            key = (bytes(data[record:record + 6 + ((count + 7) >> 3)]), record & 3)
            hit = _LAYOUTS.get(key)
            if hit is not None and record + hit[1] <= len(data):
                return Record(hit[0], record, count, [(i, record + rel) for i, rel in hit[2]])
            parsed = _parse_uncached(data, record)
            bits = key[0][6:]
            present = sum(1 for i in range(count) if not (bits[i >> 3] >> (i & 7)) & 1)
            if parsed is not None and len(parsed.values) == present and len(_LAYOUTS) < 200000:
                end = (parsed.values[-1][1] + 4 - record) if parsed.values else 0
                if len(key[0]) == 6 + ((count + 7) >> 3):
                    _LAYOUTS[key] = (parsed.class_hash, end,
                                     tuple((i, at - record) for i, at in parsed.values))
            return parsed
    return _parse_uncached(data, record)


def _parse_uncached(data: bytes, record: int):
    class_hash = struct.unpack_from("<I", data, record)[0]
    count = struct.unpack_from("<H", data, record + 4)[0]
    if not count or count > 4096:
        return None
    bitmap = record + 6
    stream = (bitmap + ((count + 7) >> 3) + 3) & ~3
    if stream > len(data):
        return None
    values = []
    at = stream
    for index in range(count):
        byte_at = bitmap + (index >> 3)
        if byte_at >= len(data):
            break
        if (data[byte_at] >> (index & 7)) & 1:
            continue                     # set bit means absent
        if at + 4 > len(data):
            break
        values.append((index, at))
        at += 4
    return Record(class_hash, record, count, values)


# The three helpers the record surgery in build_ds1_ordinary_enemy_pool.py and
# build_ds1_super_exploder_donor.py has always used.  They are kept as free
# functions rather than folded into Record so those callers read unchanged.


def value_offset(record: Record, index: int):
    """Absolute offset of one property's dword, or None when it is absent."""
    return record.offset_of(index)


def target_of(data: bytes, at: int):
    """Follow a self-relative pointer stored at `at`."""
    if at is None or at + 4 > len(data):
        return None
    return at + struct.unpack_from("<i", data, at)[0]


def read_string(data: bytes, at: int) -> str:
    """The NUL-terminated string at `at`."""
    if at is None or at < 0 or at >= len(data):
        return ""
    end = data.find(bytes(1), at)
    if end < 0:
        end = len(data)
    return data[at:end].decode("latin1")


def read_value(data: bytes, at: int):
    """The raw dword and its float reading, when the float looks sane."""
    raw = struct.unpack_from("<I", data, at)[0]
    number = struct.unpack("<f", struct.pack("<I", raw))[0]
    if number == 0.0 or 1e-4 < abs(number) < 1e7:
        return raw, number
    return raw, None


class Change:
    __slots__ = ("class_name", "index", "offset", "before", "after", "kind")

    def __init__(self, class_name, index, offset, before, after, kind):
        self.class_name = class_name
        self.index = index
        self.offset = offset
        self.before = before
        self.after = after
        self.kind = kind

    def __str__(self):
        return (f"{self.class_name}[{self.index}] at 0x{self.offset:X}: "
                f"{self.before} -> {self.after}")


def plan(data: bytes, packet: int, overrides: dict, classes: dict | None = None):
    """What a set of overrides would change in one packet, and what is missing.

    ``overrides`` maps a class name (or hash) to {property index: value}.  A
    value may be a number, or a string like "x2" or "x0.5" to scale whatever
    is authored - scaling is what a variant usually wants, because the base
    number differs per creature.
    """
    classes = classes if classes is not None else load_classes()
    wanted = {class_id(name, classes): {int(k): v for k, v in props.items()}
              for name, props in overrides.items()}
    changes, missing = [], []
    seen = set()
    for record in records_of(data, packet):
        if record.class_hash not in wanted:
            continue
        seen.add(record.class_hash)
        name = classes.get(record.class_hash, f"{record.class_hash:08X}")
        for index, target in sorted(wanted[record.class_hash].items()):
            at = record.offset_of(index)
            if at is None:
                missing.append(f"{name}[{index}] is not authored on this "
                               f"entity - only present properties can change")
                continue
            raw, number = read_value(data, at)
            after, kind = _resolve(target, raw, number)
            if after is None:
                missing.append(f"{name}[{index}] holds {raw:08X}, which does "
                               f"not read as a number, so {target!r} cannot "
                               f"be applied")
                continue
            changes.append(Change(name, index, at,
                                  number if kind == "float" else raw,
                                  after, kind))
            if kind == "float" and number is None:
                missing.append(f"{name}[{index}] holds {raw:08X}, which does "
                               f"not read as a float - check the class "
                               f"decoder before writing one")
    for class_hash in wanted:
        if class_hash not in seen:
            name = classes.get(class_hash, f"{class_hash:08X}")
            missing.append(f"{name} is not on this entity")
    return changes, missing


def _resolve(target, raw: int, number):
    """A literal, or a scale of what is authored.

    The dword is typeless, so the type has to come from what is already there:
    a field that reads as a plausible float keeps taking floats, everything
    else takes a raw dword.  Writing a JSON integer into a float field is the
    trap this avoids - KillComponent[1] holds 6.0, and a plain -1 written as
    an integer would land as 0xFFFFFFFF, which reads back as a NaN.

    A spec can force the raw form with a string like "i3" when a field is a
    genuine enum or a count.
    """
    if isinstance(target, str):
        text = target.strip()
        if text.lower().startswith("x"):
            if number is None:
                return None, None
            return number * float(text[1:]), "float"
        if text.lower().startswith("i"):
            return int(text[1:], 0), "int"
        target = float(text)
    if number is None:
        return int(target), "int"
    return float(target), "float"


def apply(data: bytearray, changes) -> None:
    """Write a plan.  Length preserving by construction: dword for dword."""
    for change in changes:
        if change.kind == "float":
            struct.pack_into("<f", data, change.offset, float(change.after))
        else:
            struct.pack_into("<I", data, change.offset,
                             int(change.after) & 0xFFFFFFFF)
