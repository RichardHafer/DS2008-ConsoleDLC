"""Which PC resource each DLC-only resource of a console DLC pack is built from (tools/ds1_dlc_build.py).

Every console weapon skin is the PC weapon with other textures, and every suit but the Astronaut is the level 5
suit with other textures, so the rules are by weapon type and by the role of a suit material. Packs that bundle
others come first; a pack whose archives another one already covers is left out.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / "DLCs" / "extracted"

# Bundles first: Scorpion_Pack holds Scorpion_Weapon_Pack, Obsidian_Pack holds the Obsidian suit and weapons.
PACK_ORDER = ["Scorpion_Pack", "Obsidian_Pack", "Elite_Pack", "Tank_Pack", "Astronaut_Pack", "Military_Pack",
              "Heavy_Damage_Pack", "Hot_Rod_Pack", "Pedestrian_Pack", "Speed_Kills_Pack", "Big_Gun_Pack",
              "Scorpion_Weapon_Pack", "Obsidian_Suit", "Obsidian_Weapon_Pack"]

WEAPONS = {
    "plasma_cutter": {"mesh": "plasma_cutter.dae", "meta": "plasma_cutter.meta.xml", "sbk": "plasmacutr.sbk",
                      "vfx": "plasma", "materials": {"main": "skinned_plasma_cutter_mat_plasmacutter_01",
                                                     "ammo": "skinned_plasma_cutter_mat_plasmacutter_ammo_01"}},
    "line_gun": {"mesh": "linegunb.dae", "meta": "line_gun.meta.xml", "sbk": "linegun.sbk", "vfx": "linegun",
                 "materials": {"main": "skinned_linegunb_mat_linegunb_01"}},
    "force_gun": {"mesh": "forcegun.dae", "meta": "forcegun.meta.xml", "sbk": "frcegun.sbk", "vfx": "forcegun",
                  "materials": {"main": "skinned_forcegun_mat_forcegun"}},
    "pulse_rifle": {"mesh": "pulse_rifle.dae", "meta": "pulse_rifle.meta.xml", "sbk": "pulserifl.sbk",
                    "vfx": "pulse", "materials": {"main": "skinned_pulse_rifle_mat_pulse_rifle_01"}},
    "ripper": {"mesh": "yoyocutter.dae", "meta": "yoyocutter.meta.xml", "sbk": "ripper.sbk", "vfx": "ripper",
               "materials": {"main": "skinned_yoyocutter_mat_yoyocutter_01"}},
    "contact_beam": {"mesh": "contactbeam.dae", "meta": "contactbeam.meta.xml", "sbk": "cntactbeam.sbk",
                     "vfx": "cbeam", "materials": {"main": "skinned_contactbeam_mat_contactbeam"}},
    "flamethrower": {"mesh": "flamethrower.dae", "meta": "flamethrower.meta.xml", "sbk": "flmthrowr.sbk",
                     "vfx": "flame", "materials": {"main": "skinned_flamethrower_mat_flame_thrower",
                                                   "flame_ring": "skinned_flamethrower_mat_flame_ring",
                                                   "flame_cannister": "skinned_flamethrower_mat_flame_cannister"}},
}

# Xbox packs (archives like the PS3 ones, textures need ds1_dlc_xbox)
XBOX_PACKS = {"Elite_Pack"}
# The Xbox Elite pack is the Microsoft twin of the PS3 Obsidian pack and uses the same store numbers, weapon
# indices and uniform slot; it moves to free ones so both can be installed.
REMAP = {"Elite_Pack": {"numbers": {133: 136, 134: 137, 135: 138, 3: 5, 1003: 1005}, "keys": {34: 37, 35: 38, 36: 39, 9: 11}}}
# SimGroup properties that hold a store number or a weapon index / uniform slot
NUMBER_PROPERTIES = {("DLCItemStoreList", 1), ("Item", 32), ("PickupItem", 19)}
KEY_PROPERTIES = {("DLCWeaponStreamAttributes", 2), ("GunProxy", 0), ("Gun", 42), ("Uniform", 0),
                  ("DLCUniformStreamAttributes", 0)}

# Level 5 suit, the base of the reskins; roles in the order they are tested (captorso before cap)
SUIT_MATERIALS = [("captorso", "skinned_isaaclevel5_mat_isaacl5captorso"),
                  ("cap", "skinned_isaaclevel5_mat_isaacl5cap"),
                  ("lowe", "skinned_isaaclevel5_mat_isaacl5lower"),
                  ("upper", "skinned_isaaclevel5_mat_isaacl5upper"),
                  ("screen", "skinned_isaaclevel5_mat_isaaclevel5screen"),
                  ("helmet", "skinned_isaaclevel5_mat_isaacl5helmet")]
SUIT_PC_TEXTURE_STEM = "isaaclevel5"


def source_dir(pack):
    usrdir = EXTRACTED / pack / "pkg" / "USRDIR"
    return next(d for d in usrdir.iterdir() if d.is_dir())


def read_store(path):
    """The console loader list: a version, then per weapon gp archive, item number, model archive, weapon index;
    then the same for suits with the uniform slot."""
    words = path.read_text(encoding="ascii").split()
    out = []
    at = 1
    for weapon in (True, False):
        count = int(words[at])
        at += 1
        for _ in range(count):
            gp, number, stream, key = words[at:at + 4]
            at += 4
            out.append((weapon, int(number), gp, stream, int(key)))
    return out


def store_lines(pack):
    return [line for store in sorted(source_dir(pack).glob("*.store")) for line in read_store(store)]


def weapon_of(archive):
    for name in sorted(WEAPONS, key=len, reverse=True):
        if archive.endswith(name) or archive.endswith(name.replace("_", "")):
            return name
    return None


def sibling(archive, name, kind, pc_keys):
    """The PC resource (name) a DLC-only resource of this archive is built from, or None."""
    weapon = weapon_of(archive)
    if kind == "VFX":
        m = re.match(r"inv_wpn_[^_]+_(.+)$", name)
        if m and ("inv_wpn_" + m.group(1), "VFX") in pc_keys:
            return "inv_wpn_" + m.group(1)
        m = re.match(r"inv_suit_[^_]+_(.+)$", name)
        if m:
            return "inv_suit_level5_" + m.group(1)
        if name.startswith("visor_"):
            return "visor_glow5.vfx"
        return None
    if weapon:
        rules = WEAPONS[weapon]
        if kind == "Mesh":
            return rules["mesh"]
        if kind == "MetaModel":
            return rules["meta"]
        if kind == "SBK":
            return rules["sbk"]
        if kind == "Material":
            for role, material in rules["materials"].items():
                if role != "main" and name.endswith(role):
                    return material
            return rules["materials"]["main"]
        return None
    if kind == "Material":
        tail = name.rsplit("_mat_", 1)[-1]
        for role, material in SUIT_MATERIALS:
            if role in tail[-14:]:
                return material
        return None
    if kind == "MetaModel":
        return "isaaclv5_helmet.meta.xml" if "helmet" in name else "isaaclevel5.meta.xml"
    return None


def texture_for(pc_name, dlc_names, suit_stem):
    """The DLC texture that takes the place of a PC texture inside a derived material."""
    if suit_stem and pc_name.startswith(SUIT_PC_TEXTURE_STEM):
        candidate = suit_stem + pc_name[len(SUIT_PC_TEXTURE_STEM):]
        return candidate if candidate in dlc_names else None
    flat = pc_name.replace("_", "")
    matches = [n for n in dlc_names if n != pc_name and n.replace("_", "").endswith(flat)
               and n.replace("_", "").startswith("pdlc")]
    if pc_name.endswith("specenviroment_e") and pc_name not in dlc_names:
        matches = [n for n in dlc_names if n.endswith("specenviroment_e")]
    return min(matches, key=len) if matches else None


def suit_stem(dlc_names):
    """isaacscorpion, pdlcisaacsony, ...: the part before cap_c of the suit's cap texture."""
    for name in dlc_names:
        if name.endswith("captorso_c"):
            return name[:-len("captorso_c")]
    return None


def pack_rules(pack):
    lines = store_lines(pack)
    archives = []
    for weapon, number, gp, stream, key in lines:
        archives += [gp, stream]
    prefer = {}
    derived = {}
    for weapon, number, gp, stream, key in lines:
        if not weapon:
            prefer[gp] = prefer[stream] = "unilvl5"
            derived[stream] = "Mesh"
    remap = REMAP.get(pack, {"numbers": {}, "keys": {}})
    lines = [(weapon, remap["numbers"].get(number, number), gp, stream, remap["keys"].get(key, key))
             for weapon, number, gp, stream, key in lines]
    return {"source": source_dir(pack), "archives": archives, "lines": lines, "prefer": prefer,
            "derived_same_name": derived, "xbox": pack in XBOX_PACKS, "remap": remap}
