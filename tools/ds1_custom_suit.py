"""Custom suits: a PC suit repainted in the style of a DLC suit, sold in the store like a DLC suit.

A custom suit is two archives built like a converted DLC suit (tools/ds1_dlc_build.py):
- the suit (uniCustom...): the target suit's meshes, models, materials and textures under ids of its own, so it
  never collides with the original suit; the colour maps repainted by tools/ds1_suit_style.py; the style's visor
  glow; the style suit's SimGroup (DLCUniformStreamAttributes, DismemberableProp, ...) with new GUIDs, the new
  model, a slot of its own and the target suit's stats;
- the store item (uniform_custom...): the style's store SimGroup with new GUIDs, store number, slot and texts, its
  icons, and a text table of its own in every language.
"""
import json
import shutil
import struct
import zlib
from pathlib import Path

import ds1_dlc_build as b
import ds1_sg_be
import ds1_suit_style
import ds1_texture

# The level suits: archive, inventory slots and damage factor (UniformManager entries 0..5)
LEVELS = {1: ("unilvl1", 10, 1.0), 2: ("unilvl2", 13, 0.95), 3: ("unilvl3", 17, 0.9), 4: ("unilvl4", 20, 0.85),
          5: ("unilvl5", 25, 0.8), 6: ("uniMarine", 25, 0.7)}
# style: pack, suit archive, store archive, visor glow (None keeps the level's), code, names per language
STYLE_SOURCES = {
    "scorpion": ("Scorpion_Pack", "uniScorpion", "uniform_scorpion", "visor_scorpion.vfx", "sco",
                 {"en": "SCORPION SUIT", "fr": "TENUE SCORPION", "es": "TRAJE SCORPION", "ll": "SCORPION-ANZUG"}),
    "obsidian": ("Obsidian_Pack", "uniSony", "uniform_sony", "visor_glow_ps.vfx", "obs",
                 {"en": "OBSIDIAN SUIT", "fr": "TENUE OBSIDIENNE", "es": "TRAJE OBSIDIANA", "ll": "OBSIDIAN-ANZUG"}),
    "unitology": ("Tank_Pack", "uniUnitology", "uniform_unitology", "visor_unitology.vfx", "uni",
                  {"en": "UNITOLOGY SUIT", "fr": "TENUE UNITOLOGISTE", "es": "TRAJE UNITOLOGISTA",
                   "ll": "UNITOLOGEN-ANZUG"}),
    "elite": ("Elite_Pack", "uniMicrosoft", "uniform_microsoft", "visor_glow_ms.vfx", "eli",
              {"en": "ELITE SUIT", "fr": "TENUE D'ÉLITE", "es": "TRAJE DE ÉLITE", "ll": "ELITE-ANZUG"}),
    "astronaut": ("Astronaut_Pack", "uniAstronaut", "uniform_astronaut", None, "ast",
                  {"en": "ASTRONAUT SUIT", "fr": "TENUE D'ASTRONAUTE", "es": "TRAJE DE ASTRONAUTA",
                   "ll": "ASTRONAUTEN-ANZUG"}),
    # the level 6 suit (the console Military pack's): no DLC suit of its own, so its SimGroup and store item are
    # the Elite's (same suit entity layout)
    "military": (None, "uniMarine", "uniform_microsoft", "visor_glow6.vfx", "mil",
                 {"en": "MILITARY SUIT", "fr": "TENUE MILITAIRE", "es": "TRAJE MILITAR", "ll": "MILITÄR-ANZUG"}),
}
# Model suits: another character's whole model on a level suit (the Mining RIG of the miner corpses). The level
# suit keeps its helmet, RIG parts, dismemberment caps and physics; its cloth and armour meshes are hidden.
MODEL_DONORS = {
    "miner": b.GAME / "global_assets" / "global_assets" / "ds_assets" / "char_str" / "corp" / "miner_suit.str",
}
STYLE_SOURCES["miner"] = (None, "miner_suit", "uniform_microsoft", None, "min",
                          {"en": "MINING RIG", "fr": "RIG DE MINEUR", "es": "RIG DE MINERO", "ll": "BERGBAU-RIG"})
# the level suit meshes the donor model replaces: the first takes the donor, the others are hidden
MODEL_REPLACED = ["mesh_body_top_dism.dae", "mesh_body_bot_dism.dae", "mesh_larm00_dism.dae", "mesh_larm01_dism.dae",
                  "mesh_rarm00_dism.dae", "mesh_rarm01_dism.dae", "mesh_lleg00_dism.dae", "mesh_lleg01_dism.dae",
                  "mesh_rleg00_dism.dae", "mesh_rleg01_dism.dae", "mesh_hand_l_dism.dae", "mesh_hand_r_dism.dae",
                  "mesh_kneepad_l_dism.dae", "mesh_kneepad_r_dism.dae", "mesh_shoulder_plates_dism.dae",
                  "mesh_pocket_dism.dae", "mesh_chest_piece_dism.dae"]
# Body part -> rows a donor split by tools/ds1_model_import.py fills (the head ones are in the helmet MetaModel)
REGION_ROWS = {
    "torso": ["mesh_body_top_dism.dae", "mesh_body_bot_dism.dae", "mesh_shoulder_plates_dism.dae", "mesh_pocket_dism.dae",
              "mesh_chest_piece_dism.dae"],
    "larm": ["mesh_larm00_dism.dae", "mesh_larm01_dism.dae", "mesh_hand_l_dism.dae"],
    "rarm": ["mesh_rarm00_dism.dae", "mesh_rarm01_dism.dae", "mesh_hand_r_dism.dae"],
    "lleg": ["mesh_lleg00_dism.dae", "mesh_lleg01_dism.dae", "mesh_kneepad_l_dism.dae"],
    "rleg": ["mesh_rleg00_dism.dae", "mesh_rleg01_dism.dae", "mesh_kneepad_r_dism.dae"],
    "head": ["mesh_head_dism.dae", "mesh_head01_dism.dae", "mesh_head00_dism.dae"],
}
# Parts the donor model lacks (the hanging miner suit has no hands and feet), cut from a model wearing the same suit:
# (archive, mesh, axis, ">" or "<", edge, level suit row it takes). Only triangles reaching past the donor's own
# edge are kept, the rest become degenerate, so nothing doubles the donor's sleeves and trousers.
CORPSE_MINER = b.GAME / "global_assets" / "global_assets" / "ds_assets" / "char_str" / "corp" / "corpseminer_cct" /     "corpse_miner.str"
MODEL_EXTRAS = {
    "miner": [(CORPSE_MINER, "mesh_larm01_dism.dae", 0, ">", 0.32, "mesh_hand_l_dism.dae"),
              (CORPSE_MINER, "mesh_rarm01_dism.dae", 0, "<", -0.32, "mesh_hand_r_dism.dae"),
              (CORPSE_MINER, "mesh_lleg01_dism.dae", 1, "<", 0.14, "mesh_kneepad_l_dism.dae"),
              (CORPSE_MINER, "mesh_rleg01_dism.dae", 1, "<", 0.14, "mesh_kneepad_r_dism.dae")],
}
# A style without a DLC pack takes its suit SimGroup and store item from this pack
TEMPLATE_PACK = ("Elite_Pack", "uniMicrosoft")
# Styles in build order and the level each has no custom version of, because its own suit stands there (the
# level 5 reskins at 5, the Military at 6; the Astronaut has its own model and a custom on every level).
CUSTOM_STYLES = [("scorpion", 5), ("obsidian", 5), ("unitology", 5), ("elite", 5), ("astronaut", None),
                 ("military", 6)]


def suit_texts(style, level):
    names = STYLE_SOURCES[style][5]
    plain = names["en"].title().replace(" Suit", "")
    texts = {
        "en": ("*%s LV%d" % (names["en"], level),
               "Custom level %d suit in %s colours, with the level %d stats." % (level, plain, level)),
        "fr": ("*%s NIV. %d" % (names["fr"], level),
               "Tenue de niveau %d aux couleurs %s, avec ses statistiques." % (level, plain)),
        "es": ("*%s NV. %d" % (names["es"], level),
               "Traje de nivel %d con los colores %s y sus estadísticas." % (level, plain)),
        "ll": ("*%s STUFE %d" % (names["ll"], level),
               "Eigener Anzug Stufe %d in %s-Farben, mit den Werten der Stufe %d." % (level, plain, level)),
    }
    texts["ss"] = texts["en"]
    return texts


def custom_suits():
    """(name, style, target suit, store number, uniform slot (.store value), item number, inventory slots,
    damage factor, texts). csco3 keeps the numbers it was first installed with; the others follow in order."""
    suits = [("csco3", "scorpion", 3, 201, 12, 1101)]
    number, slot, item = 202, 13, 1102
    for style, own_level in CUSTOM_STYLES:
        for level in sorted(LEVELS):
            if level == own_level:
                continue
            name = "c%s%d" % (STYLE_SOURCES[style][4], level)
            if name == "csco3":
                continue
            suits.append((name, style, level, number, slot, item))
            number, slot, item = number + 1, slot + 1, item + 1
    out = []
    for name, style, level, number, slot, item in suits:
        target, inventory, damage = LEVELS[level]
        out.append((name, style, target, number, slot, item, inventory, damage, suit_texts(style, level)))
    return out


CUSTOM_SUITS = custom_suits()
# Model suit prototypes, numbered after the style suits
CUSTOM_SUITS.append(("cmin1", "miner", "unilvl1", 232, 43, 1132, 10, 1.0, suit_texts("miner", 1)))

# Model suits of your own: DLCs/private/models.json lists donor archives made from other models. They stay out of
# the release; HIDE_HELMET styles show the model's own head instead of Isaac's helmet and visor glow.
PRIVATE_DIR = b.DLC / "private"
PRIVATE_SUITS = set()
PRIVATE_STYLES = set()
HIDE_HELMET = set()
HIDE_RIG = set()
HIDE_CAPS = set()
if (PRIVATE_DIR / "models.json").is_file():
    for entry in json.loads((PRIVATE_DIR / "models.json").read_text(encoding="utf-8")):
        style = entry["style"]
        MODEL_DONORS[style] = PRIVATE_DIR / entry["donor"]
        names = {lang: entry["name"] for lang in ("en", "fr", "es", "ll")}
        STYLE_SOURCES[style] = (None, Path(entry["donor"]).stem, "uniform_microsoft", None, entry["code"], names)
        if entry.get("hide_helmet", True):
            HIDE_HELMET.add(style)
        if entry.get("hide_rig", False):
            HIDE_RIG.add(style)
        if entry.get("hide_caps", False):
            HIDE_CAPS.add(style)
        level = entry.get("level", 1)
        target, inventory, damage = LEVELS[level]
        texts = {lang: ("*" + entry["name"], entry.get("description", "A suit of your own.")) for lang in
                 ("en", "fr", "es", "ss", "ll")}
        CUSTOM_SUITS.append((entry["prefix"], style, target, entry["number"], entry["slot"], entry["item"],
                             inventory, damage, texts))
        PRIVATE_SUITS.add(entry["prefix"])
        PRIVATE_STYLES.add(style)

# Suit paths (a seed can replace the level suits with one style's line): the order the plugin and the configurator
# share, and the pack whose weapons come with each path.
PATH_ORDER = ["scorpion", "obsidian", "elite", "unitology", "astronaut", "military"]
PATH_WEAPON_PACK = {"military": "Military_Pack"}
# the level the style's own suit takes in its path (the Astronaut's is its own model, still level 5)
PATH_OWN_LEVEL = {"military": 6}


def suit_paths(installed):
    """[(style, [store number per level 1..6, 0 = the level's own suit], [weapon store numbers])] from the built
    lines (pack, weapon, number, store archive, model archive, key)."""
    by_name = {suit[0]: suit for suit in CUSTOM_SUITS}
    out = []
    for style in PATH_ORDER:
        pack = STYLE_SOURCES[style][0]
        own_level = PATH_OWN_LEVEL.get(style, 5)
        levels = []
        for level in sorted(LEVELS):
            name = "c%s%d" % (STYLE_SOURCES[style][4], level)
            if level == own_level:
                own = [line[2] for line in installed if line[0] == pack and not line[1]] if pack else []
                levels.append(own[0] if own else 0)
            else:
                levels.append(by_name[name][3])
        weapon_pack = PATH_WEAPON_PACK.get(style, pack)
        weapons = [line[2] for line in installed if line[0] == weapon_pack and line[1]]
        out.append((style, levels, weapons))
    return out


def weapon_packs(installed):
    """[(pack, [weapon store numbers])] of the packs with weapons only that no suit path brings along; a seed may
    roll one of them for its run."""
    taken = {PATH_WEAPON_PACK.get(style, STYLE_SOURCES[style][0]) for style in PATH_ORDER}
    with_suit = {line[0] for line in installed if not line[1]}
    out = []
    for line in installed:
        pack = line[0]
        if not line[1] or pack in taken or pack in with_suit:
            continue
        if not out or out[-1][0] != pack:
            out.append((pack, []))
        out[-1][1].append(line[2])
    return out


def new_id(prefix, name, used):
    value = zlib.crc32(("custom:%s:%s" % (prefix, name)).lower().encode()) & 0xFFFFFFFF
    while value in used or value < 0x10000:
        value = (value * 0x9E3779B1 + 1) & 0xFFFFFFFF
    used.add(value)
    return value


def hash65599(text):
    value = 0
    for c in text.lower():
        value = (value * 65599 + ord(c)) & 0xFFFFFFFF
    return value


def patch_simgroup(data, guid_words, values, blobs):
    """New entity GUIDs (second word), property values {(class, index): value} and 16-byte blobs."""
    out = bytearray(data)
    group = ds1_sg_be.GroupBE(bytes(data))
    for i in range(group.count):
        at = group.guid_base + 16 * i
        struct.pack_into("<I", out, at + 4, guid_words[i])
    for packet in group.packets:
        for record_class, _, fields in group.records(packet):
            name = ds1_sg_be.cname(record_class)
            for index, at in fields:
                if (name, index) in values:
                    struct.pack_into("<I", out, at, values[(name, index)])
    for old, new in blobs.items():
        out = bytearray(bytes(out).replace(struct.pack("<4I", *[old] * 4), struct.pack("<4I", *[new] * 4)))
    return bytes(out), [tuple(struct.unpack_from("<4I", out, group.guid_base + 16 * i)) for i in range(group.count)]


def guid_text(words):
    """Archive root name: {w0-w1lo-w1hi-bytes of w2 and w3}, as StrUnpack writes it."""
    tail = struct.pack("<II", words[2], words[3]).hex().upper()
    return "{%08X-%04X-%04X-%s-%s}" % (words[0], words[1] & 0xFFFF, words[1] >> 16, tail[:4], tail[4:])


def guid_words(text):
    parts = text.strip("{}").split("-")
    w2, w3 = struct.unpack("<II", bytes.fromhex(parts[3] + parts[4]))
    return int(parts[0], 16), int(parts[2], 16) << 16 | int(parts[1], 16), w2, w3


def lh2(strings):
    """PC text table: header, sorted hashes, absolute offsets, cp1252 strings."""
    keys = sorted(strings)
    count = len(keys)
    offset = 0x20 + 8 * count
    body = b""
    offsets = []
    for k in keys:
        offsets.append(offset + len(body))
        body += strings[k].encode("cp1252") + b"\0"
    total = offset + len(body)
    return struct.pack("<4sIIIIIII", b"LCH2", total, 1, 0, count, 1, 0, 0) + \
        struct.pack("<%dI" % count, *keys) + struct.pack("<%dI" % count, *offsets) + body


def write_archive(stage, rows_data, output):
    headers = {struct.unpack_from("<I", data, 0x14)[0] for attrs, data in rows_data if attrs["type_name"] == "tg4h"}
    orphans = [a["base_name"] for a, _ in rows_data if a["type_name"] == "tg4d" and int(a["u18"], 16) not in headers]
    if orphans:
        raise ValueError("%s: texture data without a header of the same id: %s" % (output.name, ", ".join(orphans)))
    stage.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, (attrs, data) in enumerate(rows_data):
        rel = "%s\\%04d_%s" % (attrs["type_name"], index, Path(attrs["file_name"].replace("\\", "/")).name)
        target = stage / rel.replace("\\", "/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        rows.append(b.row(attrs, rel))
    (stage / "@archive.xml").write_text(b.XML_HEAD + "\n".join(rows) + "\n" + b.XML_TAIL, encoding="utf-8")
    b.pack_folder(stage, output)


# Visor glows recoloured for a style's customs (the Military customs glow in the dark blue of their lenses)
VISOR_GLOW_COLOURS = {"military": (0.15, 0.35, 1.0)}


def recolour_visor(data, colour):
    """The RGB of a visor effect: in its light record (.lit, 0x54 after the record's '####') and in every flare
    record (.flc, 8 bytes after the -1.0 that follows its name)."""
    out = bytearray(data)
    done = 0
    for at in range(0, len(out) - 8, 4):
        if out[at:at + 8] == b"####til.":
            struct.pack_into("<3f", out, at + 0x54, *colour)
            done += 1
        elif out[at:at + 4] == b"clf.":
            for k in range(at, min(at + 0x40, len(out) - 4), 4):
                if struct.unpack_from("<f", out, k)[0] == -1.0:
                    struct.pack_into("<3f", out, k + 8, *colour)
                    done += 1
                    break
    if not done:
        raise ValueError("no colour found in the visor effect")
    return bytes(out)


def style_environment(members, style_members):
    """{level reflection id: style reflection id} and the style's texture rows the level lacks. The DLC suits
    swap level 5's yellowspecenviroment_e for one of their own (red, tight) or the plain specenviroment_e."""
    def envs(ms):
        return {m.attrs["base_name"]: struct.unpack_from("<I", m.data(), 0x14)[0]
                for m in ms if m.attrs["type_name"] == "tg4h" and m.attrs["base_name"].endswith("_e")}
    own, style = envs(members), envs(style_members)
    if "yellowspecenviroment_e" not in own:
        return {}, []
    special = [n for n in style if n not in ("specenviroment_e", "yellowspecenviroment_e")]
    if special:
        chosen = special[0]
    elif "yellowspecenviroment_e" not in style and "specenviroment_e" in style:
        chosen = "specenviroment_e"
    else:
        return {}, []
    rows = []
    if chosen not in own:
        rows = [(dict(m.attrs), m.data()) for m in style_members
                if m.attrs["base_name"] == chosen and m.attrs["type_name"] in ("tg4h", "tg4d")]
    return {own["yellowspecenviroment_e"]: style[chosen]}, rows


def model_donor(style):
    folder = b.WORK / "chars" / MODEL_DONORS[style].stem
    if style in PRIVATE_STYLES and folder.is_dir():
        shutil.rmtree(folder)   # a private donor is rebuilt often; the unpack cache would keep the old one
    return b.read_archive(b.unpack(MODEL_DONORS[style], folder))


def bone_rows(mesh):
    """(name hash, skeleton index, offset of the index) per bone of a mesh: 16-byte rows at [0x60], count [0x38]."""
    count, at = struct.unpack_from("<II", mesh, 0x38)[0], struct.unpack_from("<I", mesh, 0x60)[0]
    return [(struct.unpack_from("<I", mesh, at + 16 * i + 4)[0], struct.unpack_from("<I", mesh, at + 16 * i + 12)[0],
             at + 16 * i + 12) for i in range(count)]


def clean_blood(img):
    """Blood on a corpse texture turned into dark grey stains, the rest darkened to the clean suit."""
    import numpy as np
    from PIL import Image
    rgb = np.asarray(img.convert("RGB"), dtype=np.float64)
    h = np.asarray(img.convert("RGB").convert("HSV"), dtype=np.float64)
    hue, sat = h[..., 0] / 255 * 360, h[..., 1] / 255
    blood = np.clip((sat - 0.3) * 4, 0, 1) * (((hue < 25) | (hue > 330)).astype(np.float64))
    grey = (rgb @ np.array([0.299, 0.587, 0.114]))[..., None] * 0.55
    # darker overall: the corpse's gloves and boots are lighter than the clean suit they join
    out = (rgb * (1 - blood[..., None]) + grey * blood[..., None]) * 0.6
    result = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).convert("RGBA")
    result.putalpha(img.getchannel("A"))
    return result


def model_extras(rows, reference, extras, used, prefix):
    """The cut parts with their material and clean maps under ids of their own: [(row name, mesh id)]."""
    out = []
    done_archives = {}
    for archive, mesh_name, axis, direction, edge, row_name in extras:
        if archive not in done_archives:
            members = b.read_archive(b.unpack(archive, b.WORK / "chars" / ("corp_" + archive.stem)))
            by = {m.key: m for m in members}
            tex_ids, material_ids = {}, {}
            # maps: the colour maps cleaned, every map under a new id
            for m in members:
                if m.attrs["type_name"] != "tg4h":
                    continue
                name = m.attrs["base_name"]
                pixels = by.get((name, "tg4d"))
                if not pixels:
                    continue
                old = struct.unpack_from("<I", m.data(), 0x14)[0]
                tid = new_id(prefix, "extra " + name, used)
                tex_ids[old] = tid
                header = bytearray(m.data())
                struct.pack_into("<I", header, 0x14, tid)
                data = pixels.data()
                if name.endswith("_c"):
                    data = ds1_texture.write(clean_blood(ds1_suit_style.image((m, pixels))), m.data(), pixels.data())
                for src, payload in ((m, bytes(header)), (pixels, data)):
                    attrs = dict(src.attrs)
                    attrs["base_name"] = "%s_%s" % (prefix, name)
                    attrs["file_name"] = attrs["file_name"].replace(name, "%s_%s" % (prefix, name))
                    attrs["u18"] = "%08X" % tid
                    rows.append((attrs, payload))
            for m in members:
                if m.attrs["type_name"] != "Material":
                    continue
                data = m.data()
                short = b.short_name(data)
                old_crc = struct.unpack_from("<I", data, 8)[0]
                material_ids[old_crc] = b.crc_lower(prefix + short)
                data, _ = b.replace_words(data, tex_ids)
                data = bytearray(data)
                struct.pack_into("<II", data, 8, material_ids[old_crc], material_ids[old_crc])
                attrs = dict(m.attrs)
                attrs["base_name"] = "%s_extra_%s" % (prefix, m.attrs["base_name"])
                attrs["u0C"] = attrs["type2"] = attrs["u14"] = attrs["u18"] = "%08X" % new_id(prefix, attrs["base_name"],
                                                                                             used)
                rows.append((attrs, bytes(data)))
            done_archives[archive] = (members, material_ids)
        members, material_ids = done_archives[archive]
        mesh = next(m for m in members if m.attrs["base_name"] == mesh_name)
        data, _ = b.replace_words(mesh.data(), material_ids)
        data = bytearray(rebone(data, reference))
        # keep the triangles reaching past the edge, the others collapse
        subs, sub_at = struct.unpack_from("<I", data, 0x34)[0], struct.unpack_from("<I", data, 0x50)[0]
        kept = 0
        for i in range(subs):
            s = sub_at + i * 0xA0
            info, vertices, indices = (struct.unpack_from("<I", data, s + o)[0] for o in (0x30, 0x38, 0x40))
            count = struct.unpack_from("<I", data, info)[0]
            start = struct.unpack_from("<H", data, info + 8)[0]
            for tri in range(count // 3):
                idx = struct.unpack_from("<3H", data, indices + 6 * tri)
                coords = [struct.unpack_from("<f", data, vertices + 32 * (v - start) + 4 * axis)[0] for v in idx]
                if any(c > edge if direction == ">" else c < edge for c in coords):
                    kept += 1
                else:
                    struct.pack_into("<3H", data, indices + 6 * tri, idx[0], idx[0], idx[0])
        mesh_id = new_id(prefix, "extra " + mesh_name, used)
        attrs = dict(mesh.attrs)
        attrs["base_name"] = "%s_extra_%s" % (prefix, mesh_name)
        attrs["u0C"] = attrs["type2"] = attrs["u14"] = attrs["u18"] = "%08X" % mesh_id
        rows.append((attrs, bytes(data)))
        out.append((row_name, mesh_id))
    return out


def rebone(mesh, reference):
    """A donor mesh on Isaac's skeleton. Vertices name a bone through their sub-mesh palette (+0x48, two bytes per
    entry), a palette entry is a position in the mesh's bone table ([0x60], 16-byte rows: name, hash, 0, skeleton
    index; matrices at [0x64]), and Isaac's meshes all carry the same 110-row table. The donor gets that table
    (its own matrices where it has the bone, the bind poses are the same) appended, the palette moved to it, and
    the fixup table rebuilt behind it."""
    u = lambda d, o: struct.unpack_from("<I", d, o)[0]

    def table(d):
        n, at, mat = u(d, 0x38), u(d, 0x60), u(d, 0x64)
        rows = []
        for i in range(n):
            name_at = u(d, at + 16 * i)
            name = bytes(d[name_at:d.index(b"\0", name_at)])
            rows.append((name, u(d, at + 16 * i + 4), u(d, at + 16 * i + 8), u(d, at + 16 * i + 12),
                         bytes(d[mat + 64 * i:mat + 64 * i + 64])))
        return rows
    ref, own = table(reference), table(mesh)
    position = {row[1]: i for i, row in enumerate(ref)}
    missing = [row[0] for row in own if row[1] not in position]
    if missing:
        raise ValueError("bones not in Isaac's skeleton: %s" % missing[:5])
    own_matrix = {row[1]: row[4] for row in own}
    data = bytearray(mesh)
    # palette: donor table position -> Isaac's
    subs, sub_at = u(data, 0x34), u(data, 0x50)
    for s in range(subs):
        sa = sub_at + 0xA0 * s
        info, vertices, palette = u(data, sa + 0x30), u(data, sa + 0x38), u(data, sa + 0x48)
        count = struct.unpack_from("<H", data, info + 10)[0]
        used_entries = max(data[vertices + 32 * v + 20 + k] for v in range(count) for k in range(4)) + 1
        for e in range(2 * used_entries):
            data[palette + e] = position[own[data[palette + e]][1]]
    old_at, old_n = u(data, 0x60), u(data, 0x38)
    # fixups: drop the old table's name pointers
    fix = u(data, 0x4C)
    pairs = []
    o = fix
    while o + 8 <= len(data) and any(data[o:o + 8]):
        field, target = struct.unpack_from("<II", data, o)
        if not old_at <= field < old_at + 16 * old_n:
            pairs.append([field, target])
        o += 8
    align = lambda n: (n + 15) & ~15
    out = bytearray(data[:align(len(data))])
    new_table = len(out)
    out += bytes(16 * len(ref))
    new_matrices = align(len(out))
    out += bytes(new_matrices - len(out)) + bytes(64 * len(ref))
    names_at = len(out)
    for i, (name, hash_, zero, index, matrix) in enumerate(ref):
        name_at = len(out)
        out += name + b"\0"
        struct.pack_into("<IIII", out, new_table + 16 * i, name_at, hash_, zero, index)
        out[new_matrices + 64 * i:new_matrices + 64 * i + 64] = own_matrix.get(hash_, matrix)
        pairs.append([new_table + 16 * i, name_at])
    new_fix = align(len(out))
    out += bytes(new_fix - len(out))
    for pair in pairs:
        if pair[0] == 0x60:
            pair[1] = new_table
        elif pair[0] == 0x64:
            pair[1] = new_matrices
        elif pair[0] == 0x4C:
            pair[1] = new_fix
    for field, target in pairs:
        out += struct.pack("<II", field, target)
    out += bytes(8)
    out += bytes(align(len(out)) - len(out))
    struct.pack_into("<I", out, 0x38, len(ref))
    struct.pack_into("<I", out, 0x60, new_table)
    struct.pack_into("<I", out, 0x64, new_matrices)
    struct.pack_into("<I", out, 0x4C, new_fix)
    struct.pack_into("<I", out, 0x0C, len(out))
    return bytes(out)


def model_swap(rows, members, ids, donor, style, used, prefix, report):
    """The donor's mesh in place of the level suit's body, its skeleton indices moved to Isaac's."""
    skeleton = {}
    for m in members:
        if m.attrs["type_name"] == "Mesh":
            for name, index, _ in bone_rows(m.data()):
                if skeleton.setdefault(name, index) != index:
                    raise ValueError("%s: Isaac's meshes disagree on bone %08X" % (prefix, name))
    donor_meshes = [m for m in donor if m.attrs["type_name"] == "Mesh"]
    donor_mesh = donor_meshes[0]
    reference = next(m for m in members if m.attrs["base_name"] == "mesh_body_top_dism.dae").data()
    # its material and maps under names and ids of their own: the game finds a material by the CRC of its
    # name, and under the corpses' own name the mesh lost it whenever a level's miner corpses went, which
    # crashed the game on drawing (2026-10-24, primitive +0x58 null, material minersuit_01)
    by = {m.key: m for m in donor}
    tex_ids, material_ids = {}, {}
    for m in donor:
        if m.attrs["type_name"] != "tg4h" or (m.attrs["base_name"], "tg4d") not in by:
            continue
        name = m.attrs["base_name"]
        old = struct.unpack_from("<I", m.data(), 0x14)[0]
        tid = new_id(prefix, "model " + name, used)
        tex_ids[old] = tid
        header = bytearray(m.data())
        struct.pack_into("<I", header, 0x14, tid)
        for src, payload in ((m, bytes(header)), (by[(name, "tg4d")], by[(name, "tg4d")].data())):
            attrs = dict(src.attrs)
            attrs["base_name"] = "%s_%s" % (prefix, name)
            attrs["file_name"] = attrs["file_name"].replace(name, "%s_%s" % (prefix, name))
            attrs["u18"] = "%08X" % tid
            rows.append((attrs, payload))
    for m in donor:
        if m.attrs["type_name"] != "Material":
            continue
        mdata = m.data()
        old_crc = struct.unpack_from("<I", mdata, 8)[0]
        material_ids[old_crc] = b.crc_lower(prefix + "_" + m.attrs["base_name"])
        mdata, _ = b.replace_words(mdata, tex_ids)
        mdata = bytearray(mdata)
        struct.pack_into("<II", mdata, 8, material_ids[old_crc], material_ids[old_crc])
        attrs = dict(m.attrs)
        attrs["base_name"] = "%s_model_%s" % (prefix, m.attrs["base_name"])
        attrs["u0C"] = attrs["type2"] = attrs["u14"] = attrs["u18"] = "%08X" % new_id(prefix, attrs["base_name"], used)
        rows.append((attrs, bytes(mdata)))
    # one mesh, or several made by tools/ds1_model_import.py (<name>_<region>_<n>.dae, each within the size of the
    # game's own models), each into a row of its body part
    donor_ids = []
    for k, dm in enumerate(donor_meshes):
        data, _ = b.replace_words(dm.data(), material_ids)
        data = rebone(data, reference)
        mid = new_id(prefix, "model mesh" if k == 0 else "model mesh %d" % k, used)
        attrs = dict(dm.attrs)
        attrs["base_name"] = "%s_%s" % (prefix, dm.attrs["base_name"])
        attrs["u0C"] = attrs["type2"] = attrs["u14"] = attrs["u18"] = "%08X" % mid
        rows.append((attrs, bytes(data)))
        region = next((r for r in REGION_ROWS if "_%s_" % r in dm.attrs["base_name"]), "torso")
        donor_ids.append((region, mid, dm.attrs["base_name"]))
    model_id = donor_ids[0][1]
    # an invisible mesh for the hidden parts: a small one with every index 0 (degenerate triangles)
    small = next(m for m in members if m.attrs["base_name"] == "mesh_body_cap_head_dism.dae")
    null = bytearray(small.data())
    subs, sub_at = struct.unpack_from("<II", null, 0x34)[0], struct.unpack_from("<I", null, 0x50)[0]
    for i in range(subs):
        s = sub_at + i * 0xA0
        info, indices = struct.unpack_from("<I", null, s + 0x30)[0], struct.unpack_from("<I", null, s + 0x40)[0]
        count = struct.unpack_from("<I", null, info)[0]
        null[indices:indices + 2 * count] = bytes(2 * count)
    null_id = new_id(prefix, "hidden mesh", used)
    attrs = dict(small.attrs)
    attrs["base_name"] = "%s_hidden.dae" % prefix
    attrs["u0C"] = attrs["type2"] = attrs["u14"] = attrs["u18"] = "%08X" % null_id
    rows.append((attrs, bytes(null)))
    # the body MetaModel: its rows (32 bytes from [0x34], count [0x58]) name a resource in words 1 and 3..6
    by_name = {m.attrs["base_name"]: ids[m.rid] for m in members if m.rid in ids}
    swap = {by_name[n]: null_id for n in MODEL_REPLACED if n in by_name}
    head_swap = {}
    if len(donor_ids) == 1:
        swap[by_name[MODEL_REPLACED[0]]] = model_id
    else:
        free = {r: [n for n in names if n in by_name] for r, names in REGION_ROWS.items()}
        spare = [n for n in MODEL_REPLACED if n in by_name and not any(n in v for v in free.values())]
        for region, mid, name in donor_ids:
            row = (free[region] or free["torso"] or spare or [None]).pop(0)
            if row is None:
                raise ValueError("%s: no MetaModel row left for %s" % (prefix, name))
            for lst in free.values():
                if row in lst:
                    lst.remove(row)
            if row in REGION_ROWS["head"]:
                head_swap[by_name[row]] = mid
            else:
                swap[by_name[row]] = mid
            report.append("%s: %s into the row of %s" % (prefix, name, row))
    if style in HIDE_HELMET:
        # an outside body is slimmer than the armour: the RIG's belt and small parts floated around it; the spine
        # tube stays, it shows the health
        swap.update({ids[m.rid]: null_id for m in members
                     if m.attrs["base_name"].startswith("mesh_rig_parts_") and m.rid in ids})
    for row_name, extra_id in model_extras(rows, reference, MODEL_EXTRAS.get(style, []), used, prefix):
        swap[by_name[row_name]] = extra_id
    for k, (a, d) in enumerate(rows):
        if a["type_name"] == "MetaModel" and "helmet" not in a["base_name"] and                 a["base_name"] not in ("grip.meta.xml", "chest_vfx.meta.xml"):
            meta = bytearray(d)
            first, count = struct.unpack_from("<I", meta, 0x34)[0], struct.unpack_from("<H", meta, 0x58)[0]
            changed = 0
            for r in range(count):
                for w in (1, 3, 4, 5, 6):
                    at = first + 32 * r + 4 * w
                    value = struct.unpack_from("<I", meta, at)[0]
                    if value in swap:
                        struct.pack_into("<I", meta, at, swap[value])
                        changed += 1
            rows[k] = (a, bytes(meta))
            report.append("%s: model %s on %s, %d MetaModel references moved, %d bones mapped" % (
                prefix, donor_mesh.attrs["base_name"], a["base_name"], changed, len(bone_rows(data))))
    if style in HIDE_HELMET:
        # the model carries its own head: the helmet meshes take the hidden mesh, the visor glow its "off" effect
        mesh_ids = {ids[m.rid] for m in members if m.attrs["type_name"] == "Mesh" and m.rid in ids}
        visor_on = next((m.rid for m in members if m.attrs["base_name"].startswith("visor_glow") and
                         not m.attrs["base_name"].endswith("_off.vfx")), None)
        visor_off = next((m.rid for m in members if m.attrs["base_name"].startswith("visor_glow") and
                          m.attrs["base_name"].endswith("_off.vfx")), None)
        for k, (a, d) in enumerate(rows):
            if a["type_name"] != "MetaModel" or "helmet" not in a["base_name"]:
                continue
            meta = bytearray(d)
            first, count = struct.unpack_from("<I", meta, 0x34)[0], struct.unpack_from("<H", meta, 0x58)[0]
            hidden = 0
            for r in range(count):
                for w in (1, 3, 4, 5, 6):
                    at = first + 32 * r + 4 * w
                    value = struct.unpack_from("<I", meta, at)[0]
                    if value in head_swap:
                        struct.pack_into("<I", meta, at, head_swap[value])
                    elif value in mesh_ids:
                        struct.pack_into("<I", meta, at, null_id)
                        hidden += 1
                    elif visor_on is not None and visor_off is not None and value == visor_on:
                        struct.pack_into("<I", meta, at, visor_off)
                        hidden += 1
            rows[k] = (a, bytes(meta))
            report.append("%s: helmet %s hidden (%d references)" % (prefix, a["base_name"], hidden))
    if style in HIDE_RIG or style in HIDE_CAPS:
        # no RIG (spine tube, its parts, stasis and kinesis modules) and no chest HUD hologram on a model that wears
        # none of it; the health bar then shows nowhere on the body
        rig = {i for n, i in by_name.items() if style in HIDE_RIG and
               n.startswith(("mesh_rig_", "mesh_stasismodule", "mesh_kinesismodule"))}
        # the dismemberment caps and torn ends sit inside Isaac's armour; around a slimmer body the waist cap
        # showed as a khaki band
        rig |= {i for n, i in by_name.items() if style in HIDE_CAPS and
                (n.startswith("mesh_body_cap_") or n.endswith("_tc_dism.dae") or n == "mesh_body_hit_dism.dae")}
        # effects are named by their resource id, like the visor glow above
        off = next((m.rid for m in members if m.attrs["base_name"].startswith("visor_glow") and
                    m.attrs["base_name"].endswith("_off.vfx")), None)
        hud = {m.rid for m in members if m.attrs["base_name"] == "mini_hud.vfx"}             if off is not None and style in HIDE_RIG else set()
        hidden = 0
        for k, (a, d) in enumerate(rows):
            if a["type_name"] != "MetaModel":
                continue
            meta = bytearray(d)
            first, count = struct.unpack_from("<I", meta, 0x34)[0], struct.unpack_from("<H", meta, 0x58)[0]
            for r in range(count):
                for w in (1, 3, 4, 5, 6):
                    at = first + 32 * r + 4 * w
                    value = struct.unpack_from("<I", meta, at)[0]
                    if value in rig or value in hud:
                        struct.pack_into("<I", meta, at, null_id if value in rig else off)
                        hidden += 1
            rows[k] = (a, bytes(meta))
        report.append("%s: RIG, chest HUD or caps hidden: %d mesh(es), %d effect(s), %d references" % (
            prefix, len(rig), len(hud), hidden))


def suit_icon_image(prefix, target):
    """A repainted level suit's icon, or a model suit's own (rendered under DLCs/private)."""
    name = "uniform_custom_%s.png" % prefix
    own = b.DLC / "private" / "icon_work" / ("suit_" + prefix) / "icons" / name
    if own.is_file():
        return own
    level = next(k for k, v in LEVELS.items() if v[0] == target)
    return b.DLC / "icon_work" / ("suit_level%d" % level) / "icons" / name


def suit_icon(prefix, target, store_members, used, report):
    """The store icon of the suit itself (tools/ds1_icon_build.py) instead of the style suit's: a texture of its
    own and the effects naming the style's icon copied under ids of their own, pointed at it. Returns the texture
    rows and {old effect id: (attrs, data)}; the store SimGroup names the effects by id."""
    from PIL import Image
    image = suit_icon_image(prefix, target)
    by = {(m.attrs["base_name"], m.attrs["type_name"]): m for m in store_members}
    style_icon = next((n for (n, t) in by if t == "tg4h" and n.startswith("inv_") and n != "inv_icon_uniform"), None)
    if not image.is_file() or not style_icon:
        return [], {}
    name = "inv_suit_%s" % prefix
    tid = new_id(prefix, "store icon", used)
    header, pixels = by[(style_icon, "tg4h")], by[(style_icon, "tg4d")]
    head = b.renamed_texture_header(header.data(), name, tid)
    rows = []
    for src, data in ((header, head),
                      (pixels, ds1_texture.write(Image.open(image).convert("RGBA"), header.data(), pixels.data()))):
        attrs = dict(src.attrs)
        attrs["base_name"] = name
        attrs["file_name"] = attrs["file_name"].replace(style_icon, name)
        attrs["u18"] = "%08X" % tid
        rows.append((attrs, data))
    old = style_icon.encode() + b"\0"
    vfx = {}
    for m in store_members:
        if m.attrs["type_name"] != "VFX" or old not in m.data():
            continue
        data = bytearray(m.data())
        at = data.find(old)
        if data[at + len(old):at + len(name) + 1].strip(b"\0"):
            raise ValueError("%s: no room for %s in %s" % (prefix, name, m.attrs["base_name"]))
        data[at:at + len(name) + 1] = name.encode() + b"\0"
        attrs = dict(m.attrs)
        attrs["base_name"] = "%s_%s" % (prefix, m.attrs["base_name"])
        attrs["u0C"] = attrs["type2"] = attrs["u14"] = attrs["u18"] = "%08X" % new_id(prefix, "icon " + m.attrs["base_name"], used)
        vfx[m.attrs["u0C"]] = (attrs, bytes(data))
    report.append("%s: store icon %s (%08X) from %s, %d effect(s) moved" % (prefix, name, tid, image.name, len(vfx)))
    return rows, vfx


def build_custom(pc, spec, out_root, report):
    prefix, style, target, number, slot, item_number, inventory, damage, texts = spec
    pack, style_suit, style_store, style_visor = STYLE_SOURCES[style][:4]
    # one id pool for every custom suit, so two of them never share an id
    if not hasattr(pc, "custom_ids"):
        pc.custom_ids = set(pc.ids)
    used = pc.custom_ids
    suit_name, store_name = "uniCustom_%s" % prefix, "uniform_custom_%s" % prefix
    members = b.read_archive(b.WORK / "pc" / target)
    painted = {} if style in MODEL_DONORS else ds1_suit_style.stylize(style, target, out_root / "painted" / prefix)
    # textures: the repainted colour maps under new names and ids
    tex_ids = {}
    rows = []
    by = {m.key: m for m in members}
    # an uncoloured style's greys stay grey through the compression (the Obsidian's gloss showed green)
    neutral = style in ds1_suit_style.STYLES and ds1_suit_style.paint_tone(style)[1] < 8
    for name, image in painted.items():
        header, pixels = by[(name, "tg4h")], by[(name, "tg4d")]
        old = struct.unpack_from("<I", header.data(), 0x14)[0]
        tid = new_id(prefix, name, used)
        tex_ids[old] = tid
        h = bytearray(header.data())
        struct.pack_into("<I", h, 0x14, tid)
        for m, data in ((header, bytes(h)), (pixels, ds1_texture.write(image, header.data(), pixels.data(),
                                                                      neutral_greys=neutral))):
            attrs = dict(m.attrs)
            attrs["base_name"] = "%s_%s" % (prefix, name)
            attrs["file_name"] = attrs["file_name"].replace(name, "%s_%s" % (prefix, name))
            # the pixels find their header by u18; an unknown id leaves the upload pending and the stream at state 1
            attrs["u18"] = "%08X" % tid
            rows.append((attrs, data))
    # the other maps (normal, specular, occlusion, health bar ...) as they are
    for m in members:
        if m.attrs["type_name"] in ("tg4h", "tg4d") and m.attrs["base_name"] not in painted:
            rows.append((dict(m.attrs), m.data()))
    # the style's environment reflection replaces the level's yellow one, as on the DLC suits
    style_members = model_donor(style) if style in MODEL_DONORS else b.read_archive(ds1_suit_style.style_dir(style))
    # the suit SimGroup (DLCUniformStreamAttributes, ...) and the store item come from a DLC pack
    template_pack, template_suit = (pack, style_suit) if pack else TEMPLATE_PACK
    template_members = style_members if pack else b.read_archive(b.DLC / "build" / template_pack / "stage" /
                                                                  template_suit)
    env_map, env_rows = style_environment(members, style_members)
    tex_ids.update(env_map)
    rows += env_rows
    # materials using a repainted map or the swapped reflection: new names, ids and texture ids
    material_ids = {}
    for m in members:
        if m.attrs["type_name"] != "Material":
            continue
        data = m.data()
        if not any(t in tex_ids for t in b.words(data)):
            rows.append((dict(m.attrs), data))
            continue
        short = b.short_name(data)
        new_short = prefix + short
        old_crc = struct.unpack_from("<I", data, 8)[0]
        material_ids[old_crc] = b.crc_lower(new_short)
        data, _ = b.replace_words(data, tex_ids)
        data = bytearray(data)
        struct.pack_into("<II", data, 8, material_ids[old_crc], material_ids[old_crc])
        attrs = dict(m.attrs)
        attrs["base_name"] = prefix + "_" + m.attrs["base_name"]
        attrs["u0C"] = attrs["type2"] = attrs["u14"] = attrs["u18"] = "%08X" % new_id(prefix, attrs["base_name"], used)
        rows.append((attrs, bytes(data)))
    # meshes and models: ids of their own, material slots and references moved
    ids = {}
    for m in members:
        if m.attrs["type_name"] in ("Mesh", "MetaModel"):
            ids[m.rid] = new_id(prefix, m.attrs["base_name"], used)
    # the style's visor glow replaces the level's; a style without one of its own keeps the level's
    visor = next(m for m in style_members if m.attrs["base_name"] == style_visor) if style_visor else None
    old_visor = next((m for m in members if m.attrs["base_name"].startswith("visor_glow") and
                      not m.attrs["base_name"].endswith("_off.vfx")), None) if visor else None
    visor_attrs, visor_data = (dict(visor.attrs), visor.data()) if visor else (None, None)
    if visor and style in VISOR_GLOW_COLOURS:
        # a glow of the style's own colour under an id of its own
        visor_data = recolour_visor(visor_data, VISOR_GLOW_COLOURS[style])
        visor_attrs["base_name"] = "%s_%s" % (prefix, visor.attrs["base_name"])
        visor_attrs["u0C"] = visor_attrs["type2"] = visor_attrs["u14"] = visor_attrs["u18"] =             "%08X" % new_id(prefix, "visor glow", used)
    if old_visor:
        ids[old_visor.rid] = int(visor_attrs["u0C"], 16)
    body_model = None
    for m in members:
        kind = m.attrs["type_name"]
        if kind in ("Mesh", "MetaModel"):
            data, _ = b.replace_words(m.data(), material_ids if kind == "Mesh" else ids)
            attrs = dict(m.attrs)
            attrs["u0C"] = attrs["type2"] = attrs["u14"] = attrs["u18"] = "%08X" % ids[m.rid]
            rows.append((attrs, data))
            if kind == "MetaModel" and "helmet" not in m.attrs["base_name"] and \
                    m.attrs["base_name"] not in ("grip.meta.xml", "chest_vfx.meta.xml"):
                body_model = ids[m.rid]
        elif kind in ("VFX", "HKX") and m is not old_visor:
            rows.append((dict(m.attrs), m.data()))
    if style in MODEL_DONORS:
        model_swap(rows, members, ids, style_members, style, used, prefix, report)
    if visor:
        rows.append((visor_attrs, visor_data))
    # the suit's SimGroup: the style suit's, with new GUIDs, model, slot and stats
    style_sg = next(m for m in template_members if m.attrs["type_name"] == "SimGroup")
    group = ds1_sg_be.GroupBE(style_sg.data())
    style_model = next(m.rid for m in template_members if m.attrs["type_name"] == "MetaModel" and
                       "helmet" not in m.attrs["base_name"] and
                       m.attrs["base_name"] not in ("grip.meta.xml", "chest_vfx.meta.xml"))
    name_key, desc_key = hash65599(prefix + "_name"), hash65599(prefix + "_desc")
    guids = [new_id(prefix, "entity%d" % i, used) for i in range(group.count)]
    data, _ = patch_simgroup(style_sg.data(), guids, {
        ("DLCUniformStreamAttributes", 0): slot, ("DLCUniformStreamAttributes", 3): inventory,
        ("DLCUniformStreamAttributes", 4): struct.unpack("<I", struct.pack("<f", damage))[0]},
        {style_model: body_model})
    attrs = dict(style_sg.attrs)
    root = guid_words(style_sg.attrs["base_name"])
    attrs["base_name"] = guid_text((root[0], new_id(prefix, "suit root", used), root[2], root[3]))
    rows.append((attrs, data))
    write_archive(out_root / "stage" / suit_name, rows, out_root / (suit_name + ".str"))
    report.append("%s: %d members, body model %08X, slot %d" % (suit_name, len(rows), body_model, slot))
    # store item
    store_members = b.read_archive(b.DLC / "build" / template_pack / "stage" / style_store)
    icon_rows, icon_vfx = suit_icon(prefix, target, store_members, used, report)
    text_names = {}
    store_rows = list(icon_rows)
    for m in store_members:
        if m.attrs["type_name"] == "VFX" and m.attrs["u0C"] in icon_vfx:
            store_rows.append(icon_vfx[m.attrs["u0C"]])
        elif m.attrs["type_name"] == "SimGroup":
            g = ds1_sg_be.GroupBE(m.data())
            moved = {int(old, 16): int(row[0]["u0C"], 16) for old, row in icon_vfx.items()}
            data, _ = patch_simgroup(m.data(), [new_id(prefix, "store%d" % i, used) for i in range(g.count)], {
                ("DLCItemStoreList", 1): number, ("Uniform", 0): slot, ("Item", 28): name_key,
                ("Item", 29): desc_key, ("Item", 32): item_number, ("PickupItem", 19): item_number}, moved)
            attrs = dict(m.attrs)
            root = guid_words(m.attrs["base_name"])
            attrs["base_name"] = guid_text((root[0], new_id(prefix, "store root", used), root[2], root[3]))
            store_rows.append((attrs, data))
        elif m.attrs["type_name"] == "LHR":
            lines = ["2"]
            for lang in ("en", "fr", "es", "ss", "ll"):
                text_id = hash65599("%s.%s" % (prefix, lang))
                text_names[lang] = "%08X" % text_id
                lines += [lang, b.TEXT_DIR + text_names[lang], str(struct.unpack("<i", struct.pack("<I", text_id))[0])]
            # an LHR under the style's id is taken for the style's and never loads our tables
            attrs = dict(m.attrs)
            attrs["base_name"] = "deadspace_custom_%s_uniform.lcl" % prefix
            lhr_id = new_id(prefix, attrs["base_name"], used)
            attrs["u0C"] = attrs["type2"] = attrs["u14"] = attrs["u18"] = "%08X" % lhr_id
            attrs["file_name"] = "%slocalereftable%08X.txt" % (attrs["file_name"].rsplit("localereftable", 1)[0], lhr_id)
            store_rows.append((attrs, ("\n".join(lines) + "\n").encode()))
        else:
            store_rows.append((dict(m.attrs), m.data()))
    write_archive(out_root / "stage" / store_name, store_rows, out_root / (store_name + ".str"))
    # text tables
    template = next(m for m in b.read_archive(b.DLC / "build" / template_pack / "stage" / "text" /
                                              sorted(p.name for p in (b.DLC / "build" / template_pack / "stage" / "text")
                                                     .iterdir())[0]))
    for lang, (name_text, desc_text) in texts.items():
        attrs = dict(template.attrs)
        attrs["base_name"] = "deadspace_custom_%s.%s.LH2" % (prefix, lang)
        attrs["file_name"] = "shared\\localization\\" + attrs["base_name"]
        attrs["u0C"] = attrs["type2"] = attrs["u14"] = attrs["u18"] = "%08X" % new_id(prefix, attrs["base_name"], used)
        write_archive(out_root / "stage" / "text" / text_names[lang],
                      [(attrs, lh2({name_key: name_text, desc_key: desc_text}))],
                      out_root / "text" / (text_names[lang] + ".str"))
    report.append("%s: store number %d, item %d, texts %s" % (store_name, number, item_number,
                                                              ", ".join(text_names.values())))
    return (False, number, store_name, suit_name, slot)
