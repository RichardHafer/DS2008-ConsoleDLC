"""PS3 -> PC conversion of Dead Space 1 skinned meshes (Mesh resources, "EAGM" version 2 -> "MGAE" version 3).

Layout (learned from the Scorpion suit against the PC level 5 suit, which share their geometry):
- header 0x80 bytes: 32-bit words, except six 16-bit values at 0x3C..0x47. Offsets: 0x20 strings, 0x34 sub-mesh
  count, 0x38 bone count, 0x48, 0x4C fixup table, 0x50 sub-meshes, 0x54, 0x60 bones (16 bytes each), 0x64 bone
  matrices (64 bytes each), 0x68 vertex stream descriptors, 0x6C index buffer descriptor, 0x78/0x7C small tables;
- sub-mesh 0xA0 bytes: name, 4 bytes, material id (CRC32 of the lower-case material short name on both
  platforms), bounding sphere, draw info pointer (+0x30), vertex block (+0x38), index buffer (+0x40);
- draw info: index count, vertex start/count (16-bit), primitive type (PS3 5 = PC 4, triangle list), triangles;
- vertex block, 32 bytes per vertex: position (3 floats), a packed 32-bit value, normal (PS3 four signed bytes,
  PC DEC3N 10:10:10), four bone indices (bytes), four 16-bit weights;
- index buffer: 16-bit; strings: bytes; fixup table: (field, target) pairs. Everything else is 32-bit.
"""
import struct


class MeshError(Exception):
    pass


def _dec3n(x, y, z):
    def q(v):
        return max(-511, min(511, int(round(v * 511)))) & 0x3FF
    return q(x) | q(y) << 10 | q(z) << 20


def mesh(ps3: bytes) -> bytes:
    src = bytes(ps3)
    if src[:4] != b"EAGM":
        raise MeshError("not a PS3 mesh")
    out = bytearray(src)
    done = bytearray(len(src))

    def be(o):
        return struct.unpack_from(">I", src, o)[0]

    def be16(o):
        return struct.unpack_from(">H", src, o)[0]

    def w32(o, n=1):
        for k in range(n):
            p = o + 4 * k
            if not done[p]:
                out[p:p + 4] = src[p:p + 4][::-1]
                done[p:p + 4] = b"\1\1\1\1"

    def w16(o, n=1):
        for k in range(n):
            p = o + 2 * k
            out[p:p + 2] = src[p:p + 2][::-1]
            done[p:p + 2] = b"\1\1"

    def raw(o, n):
        done[o:o + n] = b"\1" * n

    w32(0, 15)
    w16(0x3C, 6)
    w32(0x48, 14)
    struct.pack_into("<I", out, 8, 3)
    subs, bones = be(0x34), be(0x38)
    sub_at, bone_at, matrix_at = be(0x50), be(0x60), be(0x64)
    vb_desc, ib_desc = be(0x68), be(0x6C)
    # only the skinned layout is known: two streams of 20 and 8 bytes, a 32-byte CPU record per vertex
    strides = [struct.unpack_from(">H", src, d + 8)[0] for d in range(vb_desc, ib_desc, 0x10)]
    if strides != [0x14, 0x08]:
        raise MeshError("vertex layout %s not learned" % strides)
    for desc in range(vb_desc, ib_desc, 0x10):
        w32(desc, 2)
        w16(desc + 8)
        raw(desc + 10, 2)
        w32(desc + 12)
    w32(ib_desc, 2)
    w16(ib_desc + 8)
    raw(ib_desc + 10, 2)
    w32(ib_desc + 12)
    w32(bone_at, 4 * bones)
    w32(matrix_at, 16 * bones)
    extras = []
    for i in range(subs):
        s = sub_at + i * 0xA0
        w32(s)
        raw(s + 4, 4)
        w32(s + 8, 7)
        w16(s + 0x24, 2)
        raw(s + 0x28, 4)
        w16(s + 0x7C, 2)
        w32(s + 0x2C, 20)
        w32(s + 0x80, 8)
        info, vertices, indices, extra = be(s + 0x30), be(s + 0x38), be(s + 0x40), be(s + 0x48)
        index_count = be(info)
        w32(info, 2)
        w16(info + 8, 4)
        if be16(info + 12) == 5:
            struct.pack_into("<H", out, info + 12, 4)
        start, count = be16(info + 8), be16(info + 10)
        for v in range(count):
            r = vertices + 32 * v
            if r + 32 > len(src):
                raise MeshError("vertex block past the end")
            w32(r, 4)
            nx, ny, nz = (struct.unpack_from("b", src, r + 16 + k)[0] / 127.0 for k in (3, 2, 1))
            struct.pack_into("<I", out, r + 16, _dec3n(nx, ny, nz))
            raw(r + 16, 4)
            raw(r + 20, 4)
            w16(r + 24, 4)
        w16(indices, index_count)
        extras.append(extra)
    # fixup table: (field, target) pairs up to the end
    fixups = be(0x4C)
    for o in range(fixups, len(src) - 7, 8):
        if not any(src[o:o + 8]):
            break
        w32(o, 2)
    # strings: from 0x20's offset to the next region that starts after it
    strings = be(0x20)
    starts = sorted({be(o) for o in range(0x20, 0x80, 4)} | {be(d + 12) for d in range(vb_desc, ib_desc, 0x10)}
                    | {fixups})
    end = min([x for x in starts if x > strings] + [len(src)])
    raw(strings, end - strings)
    # sub-mesh +0x48: a byte block up to the next region
    for extra in extras:
        if extra:
            raw(extra, min([x for x in starts if x > extra] + [len(src)]) - extra)
    # the rest is 32-bit
    for o in range(0, len(src) - 3, 4):
        if not done[o] and any(src[o:o + 4]):
            w32(o)
    return bytes(out)


# MetaModel ("MMdl", version 14 on both): header with seven section offsets at 0x34, a float block offset at 0x50
# and eight section counts (16-bit) at 0x58; then the sections, pointer lists, a string table and the float block.
# Entry sizes and the 16-bit fields inside an entry, from the 55 MetaModels both platforms ship (all exact).
META_SECTIONS = {0: (0x20, ()), 1: (0x30, (0x20, 0x2C)), 2: (0x0C, (0x08,)), 3: (0x18, ()), 4: (0x0C, (0x08,)),
                 5: (0x24, (0x20,)), 6: (0x24, (0x20,))}


def _printable(chunk):
    return all(c == 0 or 32 <= c < 127 for c in chunk)


def metamodel(ps3: bytes) -> bytes:
    src = bytes(ps3)
    if src[:4] != b"MMdl":
        raise MeshError("not a PS3 MetaModel")
    out = bytearray(src)
    starts = [struct.unpack_from(">I", src, 0x34 + 4 * i)[0] for i in range(7)]
    counts = [struct.unpack_from(">H", src, 0x58 + 2 * i)[0] for i in range(8)]
    halves = {0x58, 0x5C, 0x60, 0x64}
    for index, (start, count) in enumerate(zip(starts, counts)):
        size, fields = META_SECTIONS[index]
        if start:
            for k in range(count):
                halves |= {start + k * size + f for f in fields}
    # the string table: the text that ends at the float block (or the end), back to the last 32-bit value
    end = struct.unpack_from(">I", src, 0x50)[0] or len(src)
    start = end
    while start > 0x68 and _printable(src[start - 1:start]):
        start -= 1
    start = (start + 3) & ~3
    text = set(range(start, end, 4))
    for o in range(0, len(src) - 3, 4):
        if o in text:
            continue
        if o in halves:
            out[o:o + 2] = src[o:o + 2][::-1]
            out[o + 2:o + 4] = src[o + 2:o + 4][::-1]
        else:
            out[o:o + 4] = src[o:o + 4][::-1]
    return bytes(out)


# Effects (VFX): a 16-byte name, a header (0x1C a byte count, 0x3C two 16-bit values), then records from
# a FourCC type (often after "####"): 32-bit values and 16-byte names. Learned for the record types of the suit visors (light
# ".lit", flare ".flc") from the effects both platforms ship; other record types hold 16-bit fields at places
# not covered here, so vfx() refuses them.
_TEXT = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")
VISOR_RECORDS = {b".lit", b".flc"}


def vfx_records(data):
    """FourCC record types (".lit", ".flc", ...); a record need not follow a "####"."""
    return {data[o:o + 4] for o in range(0x10, len(data) - 3, 4)
            if data[o] == 0x2E and all(0x61 <= c <= 0x7A for c in data[o + 1:o + 4])}


def vfx(ps3: bytes) -> bytes:
    src = bytes(ps3)
    unknown = vfx_records(src) - VISOR_RECORDS
    if unknown:
        raise MeshError("effect record types not learned: %s" % sorted(unknown))
    out = bytearray(src)
    in_name = False
    for o in range(0x10, len(src) - 3, 4):
        chunk = src[o:o + 4]
        if o == 0x1C:
            continue
        if o == 0x3C:
            out[o:o + 2] = chunk[1::-1]
            out[o + 2:o + 4] = chunk[:1:-1]
            continue
        letters = sum(c in _TEXT for c in chunk)
        name = chunk != b"####" and all(c in _TEXT or c == 0 for c in chunk) and             (letters >= 3 or (in_name and letters) or (in_name and not any(chunk)))
        in_name = name
        if not name:
            out[o:o + 4] = chunk[::-1]
    return bytes(out)


# Materials ("0AA0DEED", PS3 version 15, PC version 16): a parameter table of 0x1C-byte entries (name hash, type,
# string offset, ..., value offset at +0x14) up to the value block (PC header +0x44, PS3 +0x34). Both platforms
# use the same shaders; console_material() puts the PS3 material's values (shininess, normal map scale, skin
# parameters, texture ids) into a PC material of the same shader, parameter by parameter.
def _material_params(data, endian):
    table, block = (0x50, struct.unpack_from("<I", data, 0x44)[0]) if endian == "<" else \
        (0x40, struct.unpack_from(">I", data, 0x34)[0])
    entries = []
    for o in range(table, block - 0x1B, 0x1C):
        name, kind = struct.unpack_from(endian + "II", data, o)
        value = struct.unpack_from(endian + "I", data, o + 0x14)[0]
        entries.append((name, kind, value))
    offsets = sorted({v for _, _, v in entries if v})
    end = struct.unpack_from(endian + "I", data, 0x48 if endian == "<" else 0x38)[0] - block
    sizes = {v: (offsets[i + 1] if i + 1 < len(offsets) else end) - v for i, v in enumerate(offsets)}
    seen = {}
    params = {}
    for name, kind, value in entries:
        k = seen[name] = seen.get(name, -1) + 1
        if value:
            params[(name, k)] = (kind, block + value, sizes[value])
    return params


def console_material(pc_material: bytes, ps3_material: bytes):
    """The PC material with the values of the PS3 one; returns (bytes, copied, missing on PC)."""
    out = bytearray(pc_material)
    pc, ps3 = _material_params(pc_material, "<"), _material_params(ps3_material, ">")
    copied = 0
    for key, (kind, at, size) in pc.items():
        if key not in ps3 or ps3[key][0] != kind:
            continue
        _, src_at, src_size = ps3[key]
        for k in range(0, min(size, src_size) - 3, 4):
            out[at + k:at + k + 4] = ps3_material[src_at + k:src_at + k + 4][::-1]
        copied += 1
    return bytes(out), copied, len(set(ps3) - set(pc))
