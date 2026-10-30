"""Collect the size of every property the decoders of the given record classes write, for the PS3 -> PC
SimGroup converter: a byte or 16-bit property sits at the start of its 4-byte slot and must not be swapped as a
32-bit word (a swapped CuttingShape[9]/[10] and Projectile[56] made every DLC weapon shot bounce off).

Needs a class property dumper for the decrypted image (not included); the table it writes,
data/DeadSpace1_PropertyKinds.json, is committed:
{"HASH": {"index": "byte" | "word" | "dword" | "float" | ...}}.

usage: python -I tools/ds1_property_kinds.py SIMGROUP...   (adds the classes of their records)
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ds1_sg_be  # noqa: E402

OUT = ROOT / "data" / "DeadSpace1_PropertyKinds.json"
LINE = re.compile(r"^\s+(\d+)\s+(?:\+0x[0-9A-F]+\s+)?(.+?)\s*$")


def kinds_of(class_hash):
    done = subprocess.run([sys.executable, "-I", str(ROOT / "trainer" / "ds1_class_properties.py"),
                           "0x%08X" % class_hash], capture_output=True, text=True)
    if done.returncode:
        return None
    out = {}
    for line in done.stdout.splitlines()[3:]:
        m = LINE.match(line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def load():
    return {int(k, 16): {int(i): v for i, v in props.items()} for k, props in json.loads(OUT.read_text()).items()} \
        if OUT.is_file() else {}


def main():
    table = json.loads(OUT.read_text()) if OUT.is_file() else {}
    classes = set()
    for path in sys.argv[1:]:
        group = ds1_sg_be.GroupBE(path)
        for packet in group.packets:
            for record_class, _, _ in group.records(packet):
                classes.add(record_class)
    for record_class in sorted(classes):
        key = "%08X" % record_class
        if key in table:
            continue
        kinds = kinds_of(record_class)
        table[key] = kinds or {}
        sizes = sorted({v for v in (kinds or {}).values() if v in ("byte", "word")})
        print("%s %-28s %s" % (key, ds1_sg_be.cname(record_class),
                               "no decoder found" if kinds is None else "%d properties %s" % (len(kinds), sizes)))
    OUT.write_text(json.dumps(table, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
