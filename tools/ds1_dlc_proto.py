"""SimGroup fixes for the Xbox DLC prototypes of Aug 2008.

The prototypes ship the weapons retail never did, but with placeholders: every gun and GunProxy has item number
100 (Item 32), spare ammo has PickupItem 15 = 2, and the store archives lack the DLCWeaponStreamAttributes entity
that fills the weapon table at load. Their stats are the base values the retail packs later raised.

- gp_simgroup: the store archive's SimGroup rebuilt on the retail Military store archive of the same weapon
  (which has all three entities), with the prototype's GUIDs, names, text keys and values.
- fix: on the converted SimGroup, the real item number, retail spare ammo and the pack's retail tuning.
"""
import struct

import ds1_sg_be

PLACEHOLDER_NUMBER = 100
TEMPLATE_PACK = "Military_Pack"


def _pointer(group, at):
    """('guid', index) for a GUID table entry, ('data', offset) for out-of-line data, None for a plain value."""
    rel = group.i32(at)
    target = at + rel
    if -16 <= rel <= 0x1000 or not 0 <= target < len(group.data):
        return None
    if group.guid_base <= target < group.guid_base + 16 * group.count and (target - group.guid_base) % 16 == 0:
        return ("guid", (target - group.guid_base) // 16)
    return ("data", target)


def _fields(group, index):
    """{(class name, property index): value offset} of one entity."""
    out = {}
    for record_class, _, values in group.records(group.packets[index]):
        name = ds1_sg_be.cname(record_class)
        for prop, at in values:
            out[(name, prop)] = at
    return out


def _entity(group, cls):
    for i, p in enumerate(group.packets):
        if ds1_sg_be.cname(group.u32(p + 0x28)) == cls:
            return i
    raise ValueError("no %s entity" % cls)


def _string(group, at):
    return group.data[at:group.data.index(b"\0", at)]


def gp_simgroup(proto_gp, template_gp, proto_model, report, archive):
    """BE SimGroup bytes: template_gp (retail Military store archive) carrying the prototype's store entities."""
    t, p, m = ds1_sg_be.GroupBE(template_gp), ds1_sg_be.GroupBE(proto_gp), ds1_sg_be.GroupBE(proto_model)
    out = bytearray(template_gp)
    written = {}

    def put(offset, payload, what):
        # one out-of-line block may be shared by several fields; it must not take two different values
        if offset in written and written[offset] != payload:
            raise ValueError("%s: shared data block at %X needs two values (%s)" % (archive, offset, what))
        written[offset] = payload
        out[offset:offset + len(payload)] = payload

    proxy_t, proxy_p = _entity(t, "GunProxy"), _entity(p, "GunProxy")
    store_t, store_p = _entity(t, "DLCItemStoreList"), _entity(p, "DLCItemStoreList")
    attrs_t, attrs_m = _entity(t, "DLCWeaponStreamAttributes"), _entity(m, "DLCWeaponStreamAttributes")
    # entity GUIDs: the prototype's, and one of its own for the added entity
    guids = {proxy_t: p.guids[proxy_p], store_t: p.guids[store_p]}
    g = list(p.guids[proxy_p])
    g[1] ^= 0x00A5A500
    guids[attrs_t] = tuple(g)
    for index, words in guids.items():
        struct.pack_into(">4I", out, t.guid_base + 16 * index, *words)

    copied = kept = 0
    for ent_t, src, ent_s in ((proxy_t, p, proxy_p), (store_t, p, store_p), (attrs_t, m, attrs_m)):
        ft, fs = _fields(t, ent_t), _fields(src, ent_s)
        for key, at in sorted(ft.items(), key=lambda kv: kv[1]):
            if key not in fs:
                kept += 1
                report.append("%s: template %s %d kept (the prototype has none)" % (archive, key[0], key[1]))
                continue
            at_s = fs[key]
            kind_t, kind_s = _pointer(t, at), _pointer(src, at_s)
            if kind_t and kind_t[0] == "data" and kind_s and kind_s[0] == "guid":
                # the model archive names its own gun and ammo entities; the store archive needs their GUIDs
                put(kind_t[1], struct.pack(">4I", *src.guids[kind_s[1]]), "%s %d" % key)
                copied += 1
                continue
            if (kind_t is None) != (kind_s is None) or (kind_t and kind_t[0] != kind_s[0]):
                raise ValueError("%s: %s %d is a value in one SimGroup and a pointer in the other" % (archive, *key))
            if kind_t is None:
                out[at:at + 4] = src.data[at_s:at_s + 4]
            elif kind_t[0] == "guid":
                # internal references point at the same entity on both sides (PickupItem 17, the store list)
                pass
            else:
                text_t, text_s = _string(t, kind_t[1]), _string(src, kind_s[1])
                printable = len(text_s) >= 2 and all(0x20 <= c < 0x7F for c in text_s)
                if printable:
                    if len(text_s) > len(text_t):
                        raise ValueError("%s: string %r does not fit over %r" % (archive, text_s, text_t))
                    put(kind_t[1], text_s + b"\0" * (len(text_t) - len(text_s) + 1), "%s %d" % key)
                else:
                    put(kind_t[1], src.data[kind_s[1]:kind_s[1] + 16], "%s %d" % key)
            copied += 1
        for key in sorted(set(fs) - set(ft)):
            report.append("%s: prototype %s %d dropped (the template has no slot for it)" % (archive, *key))
    report.append("%s: store SimGroup on the retail Military template, %d field(s) from the prototype, %d kept"
                  % (archive, copied, kept))
    return bytes(out)


def fix(data, archive, number, tune, report):
    """The converted (PC) SimGroup with the real item number, retail spare ammo and the pack's tuning.
    tune: {(class, property): {old: new}} or {(class, property): ("scale", factor)}; scales apply to the gun in the
    model archive only."""
    out = bytearray(data)
    group = ds1_sg_be.GroupBE(data)
    changes = []
    for i, packet in enumerate(group.packets):
        fields = _fields(group, i)
        gun = ("PickupItem", 19) in fields and struct.unpack_from("<I", out, fields[("PickupItem", 19)])[0] == number
        at = fields.get(("Item", 32))
        if gun and at is not None and struct.unpack_from("<I", out, at)[0] == PLACEHOLDER_NUMBER:
            struct.pack_into("<I", out, at, number)
            changes.append("Item 32 %d -> %d" % (PLACEHOLDER_NUMBER, number))
        at = fields.get(("PickupItem", 15))
        if at is not None and struct.unpack_from("<I", out, at)[0] == 2:
            struct.pack_into("<I", out, at, 10)
            changes.append("PickupItem 15 2 -> 10")
        for key, rule in tune.items():
            at = fields.get(key)
            if at is None:
                continue
            value = struct.unpack_from("<f", out, at)[0]
            if isinstance(rule, tuple):
                if not gun or archive.startswith("gp_"):
                    continue   # the gun's own values; the store proxy keeps its generic ones
                new = value * rule[1]
            else:
                new = next((n for o, n in rule.items() if abs(value - o) < 1e-4), None)
                if new is None:
                    continue
            struct.pack_into("<f", out, at, new)
            changes.append("%s %d %g -> %g" % (key[0], key[1], value, new))
    report.append("%s: prototype fixes: %s" % (archive, "; ".join(changes) or "none"))
    return bytes(out)
