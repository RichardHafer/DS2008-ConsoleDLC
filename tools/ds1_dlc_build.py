"""Build PC archives for the Dead Space 1 console DLC packs from their PS3 archives.

Per member of each PS3 archive:
- SimGroup: converted (ds1_dlc_convert.simgroup, byte and 16-bit properties from ds1_property_kinds).
- A resource the PC ships under the same name and type (rigs, Havok, animation banks, shared effects and
  textures): the PC file and its PC row, id included.
- A DLC-only texture: header converted, pixel data copied (DLC textures are DXT, the same on both platforms).
- A DLC-only resource with a PC sibling (ds1_dlc_rules): the sibling's bytes, registered under the DLC id, with
  - Material: its id (CRC32 of the lower-case short name, header +0x08/+0x0C) and texture ids (each texture's
    tg4h +0x14) moved to the DLC ones, the short name written when it fits;
  - Mesh: its material slots (material ids) moved to the DLC materials;
  - MetaModel: its own id and the ids of the meshes, models and effects it lists moved to the DLC ones;
  - SBK: the bank's name hash (+0x5C) set to the DLC bank's;
  - VFX: equal size: the values that differ taken from the DLC file in the layout of the PC word.
- Anything else is reported and left out. An archive whose models still name a left-out resource is not
  installed, and its .store line is left out of the plugin table.

usage: python -I tools/ds1_dlc_build.py [PACK...]   (default: every pack in ds1_dlc_rules.PACK_ORDER)
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from ds1_dlc_convert import simgroup, tg4h  # noqa: E402
from ds1_dlc_rules import (KEY_PROPERTIES, NUMBER_PROPERTIES, PACK_ORDER, pack_rules, sibling,  # noqa: E402
                           source_dir, suit_stem, texture_for, weapon_of)
from ds1_dlc_xbox import texture_format, tg4d_to_pc, tg4h_to_ps3  # noqa: E402
import ds1_texture  # noqa: E402
import ds1_mesh_convert  # noqa: E402
import ds1_sg_be  # noqa: E402
import ds1_dlc_proto  # noqa: E402
from ds1_property_kinds import load as load_property_kinds  # noqa: E402

DLC = ROOT / "DLCs"
WORK = DLC / "work"
ASSETS = ROOT / "assets_dlc"
TABLE = ROOT / "src" / "console_dlc_generated.inc"
PATHS_TABLE = ROOT / "src" / "suit_paths_generated.inc"
PACKS_TABLE = ROOT / "src" / "weapon_packs_generated.inc"
# In the DLC plugin only: private suit names never reach the host's sources
NAMES_TABLE = ROOT / "src" / "dlc" / "dlc_names_generated.inc"
GIBBED = Path(os.environ.get("GIBBED_VISCERAL_DIR", str(ROOT / "tools" / "gibbed")))
UNPACK = GIBBED / "Gibbed.Visceral.StrUnpack.exe"
PACK = GIBBED / "Gibbed.Visceral.StrPack.exe"
GAME = Path(os.environ.get("DEAD_SPACE_DIR", r"C:/Program Files (x86)/Steam/steamapps/common/Dead Space"))
ATTR_ORDER = ("build", "alignment", "flags", "type", "u0C", "type2", "u14", "u18", "base_name", "file_name",
              "type_name")
# Where the plugin installs the packs, relative to the game folder
INSTALL_DIR = "ds1_randomizer_assets\\dlc\\"
TEXT_DIR = INSTALL_DIR + "text\\"
XML_HEAD = '\ufeff<?xml version="1.0" encoding="utf-8"?>\n<streams>\n'
XML_TAIL = "</streams>\n"

PC_ARCHIVES = {
    "global_assets": GAME / "global_assets/global_assets.str",
    "frontend": GAME / "frontend/frontend.str",
}
for _w in ("plasmacutr", "frcegun", "linegun", "pulserifl", "ripper", "cntactbeam", "flmthrowr"):
    PC_ARCHIVES[_w] = GAME / "global_assets/global_assets/ds_assets/logs/weapn_str" / (_w + ".str")
for _u in ("unilvl1", "unilvl2", "unilvl3", "unilvl4", "unilvl5", "unilvl555", "uniMarine"):
    PC_ARCHIVES[_u] = GAME / "global_assets/global_assets/ds_assets/char_str/plyr" / (_u + ".str")

PROPERTY_KINDS = load_property_kinds()


def crc_lower(text):
    return zlib.crc32(text.lower().encode()) & 0xFFFFFFFF


class Member:
    def __init__(self, attrs, path, archive=""):
        self.attrs = attrs
        self.path = path
        self.archive = archive

    @property
    def key(self):
        return self.attrs["base_name"], self.attrs["type_name"]

    @property
    def rid(self):
        return int(self.attrs["u0C"], 16)

    def data(self):
        return self.path.read_bytes()


def read_archive(folder):
    text = (folder / "@archive.xml").read_text(encoding="utf-8-sig")
    out = []
    for m in re.finditer(r"<stream ([^>]*)>([^<]+)</stream>", text):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        out.append(Member(attrs, folder / m.group(2).replace("\\", "/"), folder.name))
    return out


def unpack(archive, folder):
    if (folder / "@archive.xml").is_file():
        return folder
    folder.mkdir(parents=True, exist_ok=True)
    done = subprocess.run([str(UNPACK), str(archive), str(folder)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if done.returncode or not (folder / "@archive.xml").is_file():
        raise SystemExit("unpack failed: %s" % archive)
    return folder


def pack_folder(stage, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    done = subprocess.run([str(PACK), str(stage), str(output)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if done.returncode or not output.is_file():
        raise SystemExit("pack failed: %s\n%s" % (stage, done.stdout.decode(errors="replace")))


def material_samplers(material):
    """{sampler: texture name}: a material lists each texture path followed by its sampler's name."""
    strings = [t.decode("latin1") for t in re.findall(rb"[ -~]{4,}", material)]
    out = {}
    for i, text in enumerate(strings):
        if text.startswith("s:/") and text.endswith("_tdf.xml"):
            sampler = next((t for t in strings[i + 1:] if t.endswith("Sampler")), None)
            if sampler:
                out[sampler] = text.rsplit("/", 1)[-1][:-len("_tdf.xml")]
    return out


def short_name(material):
    stripped = material.rstrip(b"\0")
    return stripped[stripped.rfind(b"\0") + 1:].decode("ascii", "replace")


def words(data):
    return {struct.unpack_from("<I", data, o)[0] for o in range(0, len(data) - 3, 4)}


def replace_words(data, mapping):
    out = bytearray(data)
    hits = 0
    for offset in range(0, len(out) - 3, 4):
        value = struct.unpack_from("<I", out, offset)[0]
        if value in mapping:
            struct.pack_into("<I", out, offset, mapping[value])
            hits += 1
    return bytes(out), hits


def looks_text(chunk):
    return all(c == 0 or 0x20 <= c < 0x7F for c in chunk) and any(c for c in chunk)


def row(attrs, rel):
    fields = " ".join('%s="%s"' % (k, attrs[k]) for k in ATTR_ORDER if k in attrs)
    return "  <stream %s>%s</stream>" % (fields, rel)


class PC:
    """Every PC archive the DLC resources are matched against."""

    def __init__(self):
        self.members = []
        for name, archive in PC_ARCHIVES.items():
            folder = WORK / ("pc_frontend" if name == "frontend" else "pc/" + name)
            self.members += read_archive(unpack(archive, folder))
        self.by_key = {}
        for m in self.members:
            self.by_key.setdefault(m.key, []).append(m)
        self.tex_name = {}
        self.tex_member = {}
        for m in self.members:
            if m.attrs["type_name"] == "tg4h":
                tid = struct.unpack_from("<I", m.data(), 0x14)[0]
                self.tex_name[tid] = m.attrs["base_name"]
                self.tex_member[tid] = m
        self.global_ids = {m.rid for m in self.members if m.archive == "global_assets"}
        self.ids = {m.rid for m in self.members}


def derive_vfx(base, target, text_keys=frozenset()):
    """Learned from VFX both platforms ship: most words are 32-bit, some are two 16-bit values, some a 16-bit value
    and two bytes; the first 16 bytes are a byte string. A word that matches the PC file in any of these readings
    is the same value and stays; a changed one keeps the layout of the PC word (the closest reading, 32-bit on a
    tie). A 32-bit reading that is one of the pack's text keys always wins: the closest reading turned the Tank
    suit's name key in inv_suit_uni_stat.vfx into two swapped halves, and its inventory showed no name (2026-10-26)."""
    data = bytearray(base)
    data[:0x10] = target[:0x10]
    taken = 1
    for offset in range(0x10, len(base) - 3, 4):
        raw = target[offset:offset + 4]
        readings = (raw[::-1], raw[1::-1] + raw[:1:-1], raw[1::-1] + raw[2:], raw)
        old = base[offset:offset + 4]
        if old in readings:
            continue
        if struct.unpack(">I", raw)[0] in text_keys:
            data[offset:offset + 4] = raw[::-1]
            taken += 1
            continue
        best = max(readings[:3], key=lambda r: sum(a == b for a, b in zip(r, old)))
        data[offset:offset + 4] = raw if looks_text(raw) else best
        taken += 1
    return bytes(data), taken


_text_keys = {}


def pack_text_keys(pack_name, rules):
    """Every string key of the pack's text tables (LH2, big-endian: count at 0x10, keys from 0x20)."""
    if pack_name not in _text_keys:
        keys = set()
        for archive in sorted((rules["source"] / "pdlc_streams" / "text").glob("*.str")):
            for m in read_archive(unpack(archive, WORK / "ps3" / pack_name / "text" / archive.stem)):
                data = m.data()
                count = struct.unpack_from(">I", data, 0x10)[0]
                keys.update(struct.unpack_from(">%dI" % count, data, 0x20))
        _text_keys[pack_name] = frozenset(keys)
    return _text_keys[pack_name]


def remap_simgroup(data, remap):
    """Move store numbers and weapon indices / uniform slots of a converted SimGroup (REMAP in ds1_dlc_rules)."""
    if not remap["numbers"] and not remap["keys"]:
        return data, 0
    out = bytearray(data)
    group = ds1_sg_be.GroupBE(data)
    moved = 0
    for packet in group.packets:
        for record_class, _, values in group.records(packet):
            name = ds1_sg_be.cname(record_class)
            for index, at in values:
                table = remap["numbers"] if (name, index) in NUMBER_PROPERTIES else                     remap["keys"] if (name, index) in KEY_PROPERTIES else None
                if table is None:
                    continue
                value = struct.unpack_from("<I", out, at)[0]
                if value in table:
                    struct.pack_into("<I", out, at, table[value])
                    moved += 1
    return bytes(out), moved


def own_store_effects(pc, archive_name, plan, report):
    """The prototypes name the base weapon's store effects (inv_wpn_cbeam, ...) and the SimGroups reference them by
    the PC ids. Under those ids our copies would stand in for the base weapons' and the icon patch would reach
    them; so each gets a name and id of its own (inv_wpn_uni_cbeam), the same in store and model archive."""
    stem = archive_name[3:] if archive_name.startswith("gp_") else archive_name
    code = stem.split("_")[1]
    moved = {}
    for index, entry in enumerate(plan):
        if len(entry) != 4:
            continue   # MetaModels still waiting for their ids
        m, data, attrs, how = entry
        name = attrs["base_name"]
        if attrs["type_name"] != "VFX" or not name.startswith("inv_wpn_") or name.startswith("inv_wpn_%s_" % code):
            continue
        attrs = dict(attrs)
        new_name = "inv_wpn_%s_%s" % (code, name[len("inv_wpn_"):])
        old_id, new_id = int(attrs["u0C"], 16), crc_lower(new_name)
        if new_id in pc.ids:
            raise SystemExit("%s: effect id %08X of %s is taken" % (archive_name, new_id, new_name))
        attrs["file_name"] = attrs["file_name"].replace(name.rsplit(".", 1)[0], new_name.rsplit(".", 1)[0])
        attrs["base_name"] = new_name
        attrs["u0C"] = attrs["type2"] = attrs["u14"] = attrs["u18"] = "%08X" % new_id
        moved[old_id] = new_id
        plan[index] = (m, data, attrs, how + ", as " + new_name)
    relinked = 0
    for index, entry in enumerate(plan):
        if len(entry) != 4 or entry[2]["type_name"] != "SimGroup":
            continue
        out = entry[1]
        for old_id, new_id in moved.items():
            blob = struct.pack("<4I", *[old_id] * 4)
            relinked += out.count(blob)
            out = out.replace(blob, struct.pack("<4I", *[new_id] * 4))
        plan[index] = (entry[0], out, entry[2], entry[3])
    report.append("%s: %d store effect(s) under names of their own, %d SimGroup reference(s) moved"
                  % (archive_name, len(moved), relinked))


def prototype_store_simgroup(raw, pack_name, rules, archive_name, report):
    """A prototype store archive's SimGroup on the retail Military one of the same weapon (ds1_dlc_proto)."""
    weapon = weapon_of(archive_name)
    template_name = "gp_pdlc_mar_" + weapon
    template = unpack(source_dir(ds1_dlc_proto.TEMPLATE_PACK) / (template_name + ".str"),
                      WORK / "ps3" / ds1_dlc_proto.TEMPLATE_PACK / template_name)
    model_name = archive_name[len("gp_"):]
    model = unpack(rules["source"] / (model_name + ".str"), WORK / "ps3" / pack_name / model_name)

    def simgroup_of(folder):
        return next(m for m in read_archive(folder) if m.attrs["type_name"] == "SimGroup").data()
    return ds1_dlc_proto.gp_simgroup(raw, simgroup_of(template), simgroup_of(model), report, archive_name)


def build_archive(pc, pack_name, rules, archive_name, out_root, report):
    """Build one archive; returns True when it is complete."""
    src = unpack(rules["source"] / (archive_name + ".str"), WORK / "ps3" / pack_name / archive_name)
    members = read_archive(src)
    pc_keys = set(pc.by_key)
    dlc_tex = {}
    headers = {}
    for m in members:
        if m.attrs["type_name"] == "tg4h":
            raw = m.data()
            headers[m.attrs["base_name"]] = raw
            dlc_tex[m.attrs["base_name"]] = struct.unpack(">I", raw[0x14:0x18])[0]
    stem = suit_stem(dlc_tex)
    preferred = rules["prefer"].get(archive_name)
    derived_mesh_type = rules["derived_same_name"].get(archive_name)

    # DLC geometry is converted from the PS3 files (tools/ds1_mesh_convert.py) wherever the DLC ships a model of
    # its own: every weapon skin (the Big Gun has a mesh of its own, the others their own UV seams) and the
    # Astronaut suit. Suits that reuse the level 5 meshes keep the PC ones. Xbox meshes are another format.
    native = any(m.key[1] == "Mesh" and m.key not in pc_keys for m in members) and not rules["xbox"]

    meshes = {}

    def converted_mesh(m):
        """The PC bytes of a PS3 mesh, or None for a layout the converter does not know (static meshes)."""
        if m.key not in meshes:
            try:
                meshes[m.key] = ds1_mesh_convert.mesh(m.data())
            except ds1_mesh_convert.MeshError:
                meshes[m.key] = None
        return meshes[m.key]

    def sibling_of(m):
        if native and m.key[1] in ("Mesh", "MetaModel"):
            return None
        return None if m.key in pc_keys else sibling(archive_name, m.key[0], m.key[1], pc_keys)

    console = {}            # material key -> the PC material with the PS3 values
    material_ids = {}       # PC material id -> DLC material id
    derived_ids = {}        # PC resource id -> DLC resource id
    for m in members:
        name = sibling_of(m)
        if m.key[1] == "Material" and name and (name, "Material") in pc.by_key:
            pc_material = pc.by_key[(name, "Material")][0]
            material_ids[crc_lower(short_name(pc_material.data()))] = crc_lower(short_name(m.data()))
    stage = out_root / "stage" / archive_name
    stage.mkdir(parents=True)
    plan = []
    left_out = set()
    for m in members:
        key = m.key
        kind = key[1]
        name = sibling_of(m)
        same = sorted(pc.by_key.get(key, []), key=lambda x: (x.archive != preferred, x.rid != m.rid))
        attrs = dict(m.attrs)
        attrs["file_name"] = attrs["file_name"].replace(".PS3", ".WIN").replace(".XEN", ".WIN")
        if kind == "SimGroup":
            raw = m.data()
            prototype = rules["prototype"]
            if prototype and archive_name.startswith("gp_"):
                raw = prototype_store_simgroup(raw, pack_name, rules, archive_name, report)
            data, moved = remap_simgroup(simgroup(raw, kinds=PROPERTY_KINDS), rules["remap"])
            how = "converted" + (", %d store number(s)/index(es) moved" % moved if moved else "")
            if prototype:
                data = ds1_dlc_proto.fix(data, archive_name, rules["numbers"][archive_name],
                                         prototype["tune"].get(weapon_of(archive_name), {}), report)
                how += ", prototype fixes"
        elif kind in ("tg4h", "tg4d") and same:
            # A texture the PC ships too: its PC file. Pixel data is the same on both platforms only for DXT;
            # the rig's L8A8 health bar lines came out swapped and vanished after a death.
            attrs = dict(same[0].attrs)
            data, how = same[0].data(), "PC file"
        elif kind == "tg4h":
            raw = m.data()
            data, how = tg4h(tg4h_to_ps3(raw) if rules["xbox"] else raw), "converted"
            if b"DXT" not in data:
                report.append("%s: WARNING texture %s is not DXT, its pixels may need swapping"
                              % (archive_name, key[0]))
        elif kind == "tg4d" and rules["xbox"]:
            data = tg4d_to_pc(m.data(), texture_format(headers[key[0]]))
            how = "16-bit words swapped (Xbox)"
        elif kind == "tg4d":
            data, how = m.data(), "copied"
        elif kind == "LHR":
            data = m.data().replace(b"pdlc_streams\\text\\", TEXT_DIR.encode())
            how = "copied, text paths moved to %s" % TEXT_DIR
        elif kind == "LUA":
            data, how = m.data(), "copied"
        elif native and kind == "Mesh" and converted_mesh(m):
            # every mesh in the learned skinned layout, also under a PC name (the Astronaut's body parts are
            # named like the level 5 ones but have their own shape; its right hand is part of its arm)
            data, how = converted_mesh(m), "converted (PS3 geometry)"
            attrs["build"] = "Default"
        elif native and kind == "MetaModel" and not same:
            data, how = ds1_mesh_convert.metamodel(m.data()), "converted (PS3 model)"
            attrs["build"] = "Default"
        elif kind == "Mesh" and derived_mesh_type == "Mesh" and same:
            data, hits = replace_words(same[0].data(), material_ids)
            derived_ids[same[0].rid] = m.rid
            how = "PC mesh, %d material slot(s) moved" % hits
        elif name:
            candidates = pc.by_key.get((name, kind))
            if not candidates:
                report.append("%s: %s %s left out (PC sibling %s missing)" % (archive_name, kind, key[0], name))
                left_out.add(m.rid)
                continue
            base_member = sorted(candidates, key=lambda x: x.archive != preferred)[0]
            base = base_member.data()
            if kind == "Material":
                pc_short, dlc_short = short_name(base), short_name(m.data())
                data = bytearray(base)
                struct.pack_into("<II", data, 8, crc_lower(dlc_short), crc_lower(dlc_short))
                tex_map = {}
                # each sampler takes the texture the DLC material names for it (the Obsidian suit uses a
                # tighter environment map than level 5); by name where a sampler is not listed
                pc_samplers, dlc_samplers = material_samplers(base), material_samplers(m.data())
                for tid in words(base):
                    pc_name = pc.tex_name.get(tid)
                    if not pc_name:
                        continue
                    sampler = next((s for s, t in pc_samplers.items() if t == pc_name), None)
                    dlc_name = dlc_samplers.get(sampler) if sampler else None
                    if dlc_name not in dlc_tex:
                        dlc_name = texture_for(pc_name, dlc_tex, stem)
                    if dlc_name:
                        tex_map[tid] = dlc_tex[dlc_name]
                data, hits = replace_words(bytes(data), tex_map)
                data = bytearray(data)
                start = len(base.rstrip(b"\0")) - len(pc_short)
                room = len(data) - start
                if len(dlc_short) < room:
                    data[start:] = dlc_short.encode() + b"\0" * (room - len(dlc_short))
                data = bytes(data)
                how = "PC %s, %d texture id(s) moved, name %s" % (name, hits, dlc_short)
                if not rules["xbox"]:
                    console[m.key] = ds1_mesh_convert.console_material(data, m.data())[0]
            elif kind == "Mesh":
                data, hits = replace_words(base, material_ids)
                derived_ids[base_member.rid] = m.rid
                how = "PC %s, %d material slot(s) moved" % (name, hits)
            elif kind == "MetaModel":
                plan.append((m, base_member, attrs))
                continue
            elif kind == "SBK":
                data = bytearray(base)
                data[0x5C:0x60] = m.data()[0x5C:0x60][::-1]
                data = bytes(data)
                how = "PC %s, bank hash moved" % name
            elif kind == "VFX":
                target = m.data()
                if len(target) == len(base):
                    data, taken = derive_vfx(base, target, pack_text_keys(pack_name, rules))
                    how = "PC %s, %d word(s) from the DLC file" % (name, taken)
                elif not ds1_mesh_convert.vfx_records(target) - ds1_mesh_convert.VISOR_RECORDS:
                    # a visor of its own (lights and flares): converted, so it keeps its colour
                    data, how = ds1_mesh_convert.vfx(target), "converted (lights and flares)"
                else:
                    data, how = base, "PC %s as it is (other size)" % name
                derived_ids[base_member.rid] = m.rid   # MetaModels name their effects by id
            else:
                report.append("%s: %s %s left out (no rule for its kind)" % (archive_name, kind, key[0]))
                left_out.add(m.rid)
                continue
            attrs["build"] = base_member.attrs.get("build", attrs["build"])
        elif same:
            base_member = same[0]
            attrs = dict(base_member.attrs)
            data, how = base_member.data(), "PC file"
        else:
            report.append("%s: %s %s left out (no PC counterpart)" % (archive_name, kind, key[0]))
            left_out.add(m.rid)
            continue
        plan.append((m, data, attrs, how))
    if rules["prototype"]:
        own_store_effects(pc, archive_name, plan, report)
    # PC textures a derived material still uses (the DLC dropped that map): shipped with their PC rows
    own_tex = set(dlc_tex.values())
    extra = {}
    for entry in plan:
        if len(entry) == 4 and entry[2]["type_name"] == "Material" and entry[3].startswith("PC "):
            for tid in words(entry[1]):
                if tid in pc.tex_member and tid not in own_tex:
                    extra[tid] = pc.tex_member[tid]
    shipped = {(e[2]["base_name"], e[2]["type_name"]) for e in plan if len(e) == 4}
    for tid, header in extra.items():
        pixels = [x for x in pc.by_key.get((header.attrs["base_name"], "tg4d"), []) if x.archive == header.archive]
        for extra_member in [header] + pixels[:1]:
            if extra_member.key not in shipped:
                plan.append((extra_member, extra_member.data(), dict(extra_member.attrs),
                             "PC file from %s, still used by a material" % extra_member.archive))
    # MetaModels last: they need the ids of the derived meshes, and of the derived MetaModels they nest (the
    # suit holds its helmet; a nested id left on the PC model crashed at 0x006F1F80)
    for entry in plan:
        if len(entry) == 3:
            derived_ids[entry[1].rid] = entry[0].rid
    for index, entry in enumerate(plan):
        if len(entry) == 3:
            m, base_member, attrs = entry
            data, hits = replace_words(base_member.data(), derived_ids)
            attrs["build"] = base_member.attrs.get("build", attrs["build"])
            plan[index] = (m, data, attrs, "PC %s, %d id(s) moved" % (base_member.attrs["base_name"], hits))
    # PC parts a derived model names that the DLC dropped (the Obsidian suit has no knee pads): shipped from the
    # PC archive under their PC ids, meshes with their materials moved like the others
    own_ids = {e[2]["u0C"] for e in plan}
    by_id = {}
    for member in pc.members:
        if member.archive == preferred or member.rid not in by_id:
            by_id[member.rid] = member
    for entry in list(plan):
        if entry[2]["type_name"] != "MetaModel" or not entry[3].startswith("PC "):
            continue
        for ref in sorted(words(entry[1])):
            part = by_id.get(ref)
            if not ref or not part or "%08X" % ref in own_ids or ref in pc.global_ids:
                continue
            if part.attrs["type_name"] == "Mesh":
                data, hits = replace_words(part.data(), material_ids)
                how = "PC part from %s the DLC dropped, %d material slot(s) moved" % (part.archive, hits)
            elif part.attrs["type_name"] in ("VFX", "HKX", "RCB", "BNK"):
                data, how = part.data(), "PC part from %s the DLC dropped" % part.archive
            else:
                continue
            plan.append((part, data, dict(part.attrs), how))
            own_ids.add("%08X" % ref)
    # Complete only when no model still names a resource that was left out or a PC one nothing loads, and no
    # DLC model or mesh was left out (the Astronaut suit has meshes of its own)
    complete = not any(line.startswith(archive_name + ": Mesh") or line.startswith(archive_name + ": MetaModel")
                       for line in report if "left out" in line)
    if not complete:
        report.append("%s: INCOMPLETE, a DLC mesh or model has no PC counterpart" % archive_name)
    for m, data, attrs, how in plan:
        if attrs["type_name"] != "MetaModel":
            continue
        refs = words(data)
        missing = [r for r in refs if r and r in left_out]
        foreign = [r for r in refs if r and r in pc.ids and "%08X" % r not in own_ids and r not in pc.global_ids]
        if missing or foreign:
            complete = False
            report.append("%s: INCOMPLETE, %s names %d left-out and %d unloaded PC resource(s)"
                          % (archive_name, attrs["base_name"], len(missing), len(foreign)))
    add_weapon_icon(pc, archive_name, plan, report)
    rows = []
    for index, (m, data, attrs, how) in enumerate(plan):
        rel = "%s\\%04d_%s" % (attrs["type_name"], index, Path(attrs["file_name"].replace("\\", "/")).name)
        target = stage / rel.replace("\\", "/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        rows.append(row(attrs, rel))
        report.append("%s: %-9s %-55s %s" % (archive_name, attrs["type_name"], attrs["base_name"], how))
    (stage / "@archive.xml").write_text(XML_HEAD + "\n".join(rows) + "\n" + XML_TAIL, encoding="utf-8")
    output = out_root / (archive_name + ".str")
    pack_folder(stage, output)
    report.append("%s: packed %d members, %d bytes%s" % (archive_name, len(rows), output.stat().st_size,
                                                         "" if complete else ", NOT installed"))
    # suits: a second archive with the console material values (ConsoleDlcMaterials=1 loads it)
    if console and archive_name.startswith("uni") and not archive_name.startswith("uniform"):
        variant = out_root / "stage" / (archive_name + "_cm")
        shutil.copytree(stage, variant)
        for index, (m, data, attrs, how) in enumerate(plan):
            if m.key in console and attrs["type_name"] == "Material":
                rel = "%s/%04d_%s" % (attrs["type_name"], index, Path(attrs["file_name"].replace("\\", "/")).name)
                (variant / rel).write_bytes(console[m.key])
        pack_folder(variant, out_root / (archive_name + "_cm.str"))
        report.append("%s: console material variant, %d material(s)" % (archive_name, len(console)))
    return complete


ICON_WORK = DLC / "icon_work"
RETAIL_ICONS = {"plasma_cutter": "inv_pcutter", "pulse_rifle": "inv_pulse", "line_gun": "inv_linegun",
                "ripper": "inv_yoyo", "flamethrower": "inv_flame", "force_gun": "inv_forcegun",
                "contact_beam": "inv_cbeam"}


def renamed_texture_header(header, name, tid):
    """A tg4h under another name and id. The name is also a string at the header's end ([0x18] points at it);
    the game registers the texture by that one, so with the template's left in, a new icon replaced the retail
    one and the effects asking for the new name found nothing (2026-10-24)."""
    at = struct.unpack_from("<I", header, 0x18)[0]
    if header[at:].rstrip(b"\0").find(b"\0") >= 0:
        raise ValueError("tg4h name is not the last field")
    head = bytearray(header[:at]) + name.encode() + b"\0"
    struct.pack_into("<I", head, 0x14, tid)
    return bytes(head)


def add_weapon_icon(pc, archive_name, plan, report):
    """A DLC weapon's own inventory icon (tools/ds1_icon_build.py): a texture in the retail icon's format and the
    weapon's icon effects pointed at it by name. The DLC ships none; its effects name the retail icon."""
    stem = archive_name[3:] if archive_name.startswith("gp_") else archive_name
    weapon = weapon_of(stem)
    image = ICON_WORK / weapon / "icons" / (stem + ".png") if weapon in RETAIL_ICONS else None
    if not image or not image.is_file():
        return
    retail = RETAIL_ICONS[weapon]
    # the prototypes write pulserifle without the underscore
    suffix = weapon if stem.endswith("_" + weapon) else weapon.replace("_", "")
    code = stem[len("pdlc_"):-len(suffix) - 1]
    name = "%s_%s" % (retail, code)
    header, pixels = pc.by_key[(retail, "tg4h")][0], pc.by_key[(retail, "tg4d")][0]
    tid = crc_lower(name)
    if tid in pc.ids:
        raise SystemExit("icon id %08X of %s is taken" % (tid, name))
    head = renamed_texture_header(header.data(), name, tid)
    from PIL import Image
    for src, data in ((header, bytes(head)),
                      (pixels, ds1_texture.write(Image.open(image).convert("RGBA"), header.data(), pixels.data()))):
        attrs = dict(src.attrs)
        attrs["base_name"] = name
        attrs["file_name"] = attrs["file_name"].replace(retail, name)
        attrs["u18"] = "%08X" % tid
        plan.append((src, data, attrs, "own icon from %s" % image.name))
    old = retail.encode() + b"\0"
    patched = 0
    moved_ids = {}
    for index, (m, data, attrs, how) in enumerate(plan):
        if attrs["type_name"] != "VFX" or old not in data or \
                not attrs["base_name"].startswith(("inv_wpn_", "ui_wep_", "pickup_ui_")):
            continue
        out = bytearray(data)
        at = out.find(old)
        while at >= 0:
            if out[at + len(old):at + len(name) + 1].strip(b"\0"):
                raise SystemExit("%s: no room for %s in %s" % (archive_name, name, attrs["base_name"]))
            out[at:at + len(name) + 1] = name.encode() + b"\0"
            patched += 1
            at = out.find(old, at + len(name) + 1)
        if not attrs["base_name"].startswith("inv_wpn_"):
            # the weapon wheel's and the pickup prompt's effects keep the retail name and id in the DLC archive, so
            # the retail one won (vanilla icons in the wheel, 2026-10-25): under an id of their own, named by the
            # weapon's SimGroup
            attrs = dict(attrs)
            old_id = int(attrs["u0C"], 16)
            attrs["base_name"] = "%s_%s" % (code, attrs["base_name"])
            new_vid = crc_lower(attrs["base_name"])
            attrs["u0C"] = attrs["type2"] = attrs["u14"] = attrs["u18"] = "%08X" % new_vid
            moved_ids[old_id] = new_vid
        plan[index] = (m, bytes(out), attrs, how + ", icon " + name)
    relinked = 0
    for index, (m, data, attrs, how) in enumerate(plan):
        if attrs["type_name"] != "SimGroup" or not moved_ids:
            continue
        out = data
        for old_id, new_vid in moved_ids.items():
            blob = struct.pack("<4I", *[old_id] * 4)
            relinked += out.count(blob)
            out = out.replace(blob, struct.pack("<4I", *[new_vid] * 4))
        plan[index] = (m, out, attrs, how)
    report.append("%s: icon %s (%08X) from %s, %d effect name(s) moved, %d effect(s) under ids of their own, %d "
                  "SimGroup reference(s) moved" % (archive_name, name, tid, image.name, patched, len(moved_ids),
                                                   relinked))


def build_texts(pack_name, rules, out_root, report):
    """One LH2 table per language: header, hashes and offsets swapped, strings kept."""
    text_src = rules["source"] / "pdlc_streams" / "text"
    for archive in sorted(text_src.glob("*.str")):
        members = read_archive(unpack(archive, WORK / "ps3" / pack_name / "text" / archive.stem))
        stage = out_root / "stage" / "text" / archive.stem
        stage.mkdir(parents=True)
        rows = []
        for index, m in enumerate(members):
            if m.attrs["type_name"] != "LH2":
                raise SystemExit("unexpected text member %s" % m.attrs["base_name"])
            data = bytearray(m.data())
            count = struct.unpack_from(">I", data, 0x10)[0]
            for offset in list(range(0, 0x20, 4)) + list(range(0x20, 0x20 + 8 * count, 4)):
                data[offset:offset + 4] = data[offset:offset + 4][::-1]
            attrs = dict(m.attrs)
            rel = "LH2\\%04d_%s" % (index, attrs["base_name"])
            (stage / "LH2").mkdir(exist_ok=True)
            (stage / rel.replace("\\", "/")).write_bytes(bytes(data))
            rows.append(row(attrs, rel))
            report.append("text %s: %s, %d strings" % (archive.stem, attrs["base_name"], count))
        (stage / "@archive.xml").write_text(XML_HEAD + "\n".join(rows) + "\n" + XML_TAIL, encoding="utf-8")
        pack_folder(stage, out_root / "text" / archive.name)


def build_pack(pc, pack_name, covered):
    """Build the lines of a pack no earlier pack covered; returns the lines to install."""
    rules = pack_rules(pack_name)
    lines = [line for line in rules["lines"] if line[1] not in covered]
    out_root = DLC / "build" / pack_name
    if not lines:
        if out_root.exists():
            shutil.rmtree(out_root)
        print("%s: covered by an earlier pack" % pack_name)
        return []
    if out_root.exists():
        shutil.rmtree(out_root)
    report = []
    complete = {}
    for weapon, number, gp, stream, key in lines:
        for archive_name in (gp, stream):
            if archive_name not in complete:
                complete[archive_name] = build_archive(pc, pack_name, rules, archive_name, out_root, report)
    build_texts(pack_name, rules, out_root, report)
    (out_root / "report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    good = [line for line in lines if complete[line[2]] and complete[line[3]]]
    for line in lines:
        if line not in good:
            print("%s: %s left out (incomplete archive)" % (pack_name, line[3]))
    for name in [name for name, ok in complete.items() if ok]:
        for built in (out_root / (name + ".str"), out_root / (name + "_cm.str")):
            if built.exists():
                shutil.copy2(built, ASSETS / built.name)
    for built in (out_root / "text").glob("*.str"):
        shutil.copy2(built, ASSETS / "text" / built.name)
    print("%s: %d of %d line(s) built, %s" % (pack_name, len(good), len(lines),
                                              "; ".join(l for l in report if "INCOMPLETE" in l or "WARNING" in l)
                                              or "no warnings"))
    # prototype lines join the retail pack of their suit (suit paths, names)
    joined = rules["prototype"]["pack"] if rules["prototype"] else pack_name
    return [(joined,) + line for line in good]


def write_table(installed):
    lines = ["// Generated by tools/ds1_dlc_build.py from the console .store lists of the built packs:",
             "// {weapon, store number, store archive, model archive, weapon index or uniform slot}"]
    for pack_name, weapon, number, gp, stream, key in installed:
        lines.append('{%s, %d, "%s", "%s", %d},   // %s' % ("true" if weapon else "false", number, gp, stream, key,
                                                          pack_name))
    TABLE.write_bytes(("\n".join(lines) + "\n").encode("ascii"))
    import ds1_custom_suit
    paths = ["// Generated by tools/ds1_dlc_build.py: per suit path the store numbers of levels 1..6 (0 = the level's",
             "// own suit) and the store numbers of the weapons that come with it."]
    for style, levels, weapons in ds1_custom_suit.suit_paths(installed):
        paths.append('{"%s", {%s}, {%s}, %d},' % (style, ", ".join(str(n) for n in levels),
                                                  ", ".join(str(n) for n in weapons) or "0", len(weapons)))
    PATHS_TABLE.write_bytes(("\n".join(paths) + "\n").encode("ascii"))
    packs = ["// Generated by tools/ds1_dlc_build.py: the weapon-only packs a seed may roll, with their weapons' store",
             "// numbers."]
    for pack, weapons in ds1_custom_suit.weapon_packs(installed):
        packs.append('{"%s", {%s}, %d},' % (pack, ", ".join(str(n) for n in weapons), len(weapons)))
    PACKS_TABLE.write_bytes(("\n".join(packs) + "\n").encode("ascii"))
    write_names(installed)


def c_string(text):
    # octal, so a following digit never extends the escape; the menu draws cp1252
    return "".join(chr(b) if 32 <= b < 127 and chr(b) not in '"\\' else "\\%03o" % b
                   for b in text.encode("cp1252", "replace"))


def write_names(installed):
    """Display names by model archive for the host's F9 cheat menu: the suits' English store names, the weapons
    as pack and weapon."""
    import ds1_custom_suit as cs
    suits = {source[1]: source[5]["en"] for source in cs.STYLE_SOURCES.values() if source[0]}
    customs = {"uniCustom_" + spec[0]: spec[8]["en"][0].lstrip("*") for spec in cs.CUSTOM_SUITS}
    lines = ["// Generated by tools/ds1_dlc_build.py: {model archive, display name} of every installed DLC line."]
    for pack_name, weapon, number, gp, stream, key in installed:
        if weapon:
            kind = (weapon_of(gp) or gp.split("_", 3)[-1]).replace("_", " ").title()
            name = "%s %s" % (pack_name.replace("_Pack", "").replace("_", " "), kind)
        else:
            name = customs.get(stream) or suits.get(stream) or stream
        lines.append('{"%s", "%s"},' % (stream, c_string(name)))
    NAMES_TABLE.write_bytes(("\n".join(lines) + "\n").encode("ascii"))


def table_lines():
    """The lines console_dlc_generated.inc holds now, as (pack, weapon, number, store, model, key)."""
    lines = []
    for text in TABLE.read_text(encoding="ascii").splitlines():
        m = re.match(r'\{(true|false), (\d+), "([^"]+)", "([^"]+)", (\d+)\},\s+// (\S+)', text)
        if m:
            lines.append((m.group(6), m.group(1) == "true", int(m.group(2)), m.group(3), m.group(4), int(m.group(5))))
    return lines


def main():
    if sys.argv[1:2] == ["--custom"]:
        build_custom_only(sys.argv[2:])
        return
    if sys.argv[1:2] == ["--names"]:
        lines = table_lines()
        write_names(lines)
        print("%d name(s) in %s" % (len(lines), NAMES_TABLE.name))
        return
    packs = sys.argv[1:] or PACK_ORDER
    if ASSETS.exists():
        shutil.rmtree(ASSETS)
    (ASSETS / "text").mkdir(parents=True)
    pc = PC()
    covered = set()
    installed = []
    for pack_name in packs:
        built = build_pack(pc, pack_name, covered)
        covered |= {line[2] for line in built}
        installed += built
    if not sys.argv[1:]:
        installed += build_custom_suits(pc)
    write_table(installed)
    print("%d line(s) in %s" % (len(installed), TABLE.name))


CUSTOM_ROOT = DLC / "build" / "Custom_Suits"
FINGERPRINTS = CUSTOM_ROOT / "fingerprints.json"


def custom_fingerprint(spec):
    """What a custom suit is built from: its line, the tools' code and its source archives' listings."""
    import hashlib
    import ds1_custom_suit
    import ds1_suit_style
    h = hashlib.sha1(repr(spec[:8]).encode() + repr(sorted(spec[8].items())).encode())
    for tool in ("ds1_suit_style.py", "ds1_custom_suit.py", "ds1_texture.py", "ds1_suit_emblem.py"):
        h.update((ROOT / "tools" / tool).read_bytes())
    prefix, style, target = spec[:3]
    sources = [WORK / "pc" / target / "@archive.xml"]
    if style in ds1_custom_suit.MODEL_DONORS:
        sources.append(Path(str(ds1_custom_suit.MODEL_DONORS[style])))
    else:
        sources.append(ds1_suit_style.style_dir(style) / "@archive.xml")
    icon = ds1_custom_suit.suit_icon_image(prefix, target)
    if icon.is_file():
        sources.append(icon)
    for source in sources:
        # a donor .str by its contents: a re-imported model under the same name was "unchanged" (2026-10-25)
        h.update(source.read_bytes() if source.suffix in (".xml", ".png", ".str") and source.is_file()
                 else str(source).encode())
    h.update(repr([style in ds1_custom_suit.HIDE_HELMET, style in getattr(ds1_custom_suit, "HIDE_RIG", ()),
                   style in getattr(ds1_custom_suit, "HIDE_CAPS", ())]).encode())
    return h.hexdigest()


def save_fingerprints(prints):
    import json
    FINGERPRINTS.write_text(json.dumps(prints, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def custom_line(spec):
    return ("Custom_Suits", False, spec[3], "uniform_custom_" + spec[0], "uniCustom_" + spec[0], spec[4])


def write_leg_table(specs):
    """legs.txt for the host plugin (LegLengthCorrection): the model suits built with own leg lengths, by the suit
    archive the suit change loads."""
    import ds1_custom_suit
    lines = ["# suit_archive s_thigh s_shin raise_at_rest ankle_offset  (tools/ds1_dlc_build.py)"]
    for spec in specs:
        donor = ds1_custom_suit.MODEL_DONORS.get(spec[1])
        legs = Path(str(donor)).with_suffix(".legs.txt") if donor else None
        if legs and legs.is_file():
            values = [l for l in legs.read_text(encoding="ascii").splitlines() if l and not l.startswith("#")][0]
            lines.append("uniCustom_%s %s" % (spec[0], values))
    (ASSETS / "legs.txt").write_bytes(("\n".join(lines) + "\n").encode("ascii"))
    print("legs.txt: %d suit(s) with own leg lengths" % (len(lines) - 1))


def build_custom_only(names):
    """Rebuild only the named custom suits (prefixes or styles), or, without names, those whose fingerprint
    changed; everything else in the output stays. The tables are rewritten from the pack lines already built."""
    import json
    import ds1_custom_suit
    prints = json.loads(FINGERPRINTS.read_text(encoding="utf-8")) if FINGERPRINTS.is_file() else {}
    specs = ds1_custom_suit.CUSTOM_SUITS
    if names:
        chosen = [s for s in specs if s[0] in names or s[1] in names]
    else:
        chosen = [s for s in specs if prints.get(s[0]) != custom_fingerprint(s) or
                  not (CUSTOM_ROOT / ("uniCustom_%s.str" % s[0])).is_file()]
    if not chosen:
        print("Custom_Suits: nothing changed")
    pc = PC()
    # ids the kept suits already hold stay taken
    pc.custom_ids = set(pc.ids)
    rebuilt = {s[0] for s in chosen}
    stage = CUSTOM_ROOT / "stage"
    if stage.is_dir():
        for folder in stage.iterdir():
            if (folder / "@archive.xml").is_file() and folder.name.split("_")[-1] not in rebuilt:
                for m in read_archive(folder):
                    for key in ("u0C", "u18"):
                        pc.custom_ids.add(int(m.attrs[key], 16))
    report = []
    for spec in chosen:
        for name in ("uniCustom_" + spec[0], "uniform_custom_" + spec[0]):
            if (stage / name).is_dir():
                shutil.rmtree(stage / name)
        ds1_custom_suit.build_custom(pc, spec, CUSTOM_ROOT, report)
        for name in ("uniCustom_" + spec[0], "uniform_custom_" + spec[0]):
            shutil.copy2(CUSTOM_ROOT / (name + ".str"), ASSETS / (name + ".str"))
        # after every suit, so an interrupted run resumes where it stopped
        prints[spec[0]] = custom_fingerprint(spec)
        save_fingerprints(prints)
        print("Custom_Suits: %s rebuilt" % spec[0], flush=True)
    for built in (CUSTOM_ROOT / "text").glob("*.str"):
        shutil.copy2(built, ASSETS / "text" / built.name)
    save_fingerprints(prints)
    write_leg_table(specs)
    lines = []
    for text in TABLE.read_text(encoding="ascii").splitlines():
        m = re.match(r'\{(true|false), (\d+), "([^"]+)", "([^"]+)", (\d+)\},\s+// (\S+)', text)
        if m and m.group(6) != "Custom_Suits":
            lines.append((m.group(6), m.group(1) == "true", int(m.group(2)), m.group(3), m.group(4), int(m.group(5))))
    lines += [custom_line(s) for s in specs]
    write_table(lines)
    print("%d custom suit(s) rebuilt, %d line(s) in %s" % (len(chosen), len(lines), TABLE.name))


def build_custom_suits(pc):
    """Custom suits (tools/ds1_custom_suit.py): PC suits repainted in a DLC suit's style."""
    import ds1_custom_suit
    out_root = DLC / "build" / "Custom_Suits"
    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True)
    report = []
    lines = []
    for spec in ds1_custom_suit.CUSTOM_SUITS:
        lines.append(("Custom_Suits",) + ds1_custom_suit.build_custom(pc, spec, out_root, report))
    for built in out_root.glob("*.str"):
        shutil.copy2(built, ASSETS / built.name)
    for built in (out_root / "text").glob("*.str"):
        shutil.copy2(built, ASSETS / "text" / built.name)
    (out_root / "report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    save_fingerprints({spec[0]: custom_fingerprint(spec) for spec in ds1_custom_suit.CUSTOM_SUITS})
    print("Custom_Suits: " + "; ".join(report))
    return lines


if __name__ == "__main__":
    main()
