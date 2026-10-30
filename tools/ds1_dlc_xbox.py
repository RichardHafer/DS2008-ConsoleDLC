"""Xbox 360 -> PS3/PC converters for Dead Space 1 texture resources (Elite pack, Unitology prototype).

Xbox archives are big-endian like the PS3 ones (member names end in .XEN instead of .PS3), and SimGroups convert
with ds1_dlc_convert.simgroup as they are. Textures differ: tg4h_to_ps3 gives the PS3 header, which
ds1_dlc_convert.tg4h then turns into the PC header; tg4d_to_pc gives the PC pixel data.
See analysis/DS1_Unitology_DLC_Prototype_2026-10-23.md.
"""
import struct

# Xbox only hash/pair entry, always (1, 1)
XBOX_HASH = 0x927E6ABF
# Data size entry; Xbox stores its allocation size there
SIZE_HASH = 0x4F8B2A9F
FORMAT_HASH = 0xDEBA72DF


def _table(header, endian):
    hashes, pairs = struct.unpack_from(endian + "II", header, 0x28)
    count = (pairs - hashes) // 4
    keys = [struct.unpack_from(endian + "I", header, hashes + 4 * i)[0] for i in range(count)]
    values = [(header[pairs + 5 * i], struct.unpack_from(endian + "I", header, pairs + 5 * i + 1)[0])
              for i in range(count)]
    return hashes, pairs, keys, values


def tg4h_to_ps3(xbox: bytes) -> bytes:
    """Texture header. Drops the Xbox entry, puts the data size (+0x1C) into the size pair and moves every string
    offset (+0x00, +0x18 and the type 0 pairs) back by the removed bytes. +0x27 is the entry count."""
    hashes, pairs, keys, values = _table(xbox, ">")
    if XBOX_HASH not in keys:
        raise ValueError("not an Xbox tg4h")
    index = keys.index(XBOX_HASH)
    del keys[index], values[index]
    shift = 9
    strings = pairs + 5 * (len(keys) + 1)
    size = struct.unpack_from(">I", xbox, 0x1C)[0]
    values = [(kind, size if key == SIZE_HASH else value - shift if kind == 0 and value >= strings else value)
              for key, (kind, value) in zip(keys, values)]
    out = bytearray(xbox[:hashes])
    for offset in (0x00, 0x18):
        value = struct.unpack_from(">I", out, offset)[0]
        if value >= strings:
            struct.pack_into(">I", out, offset, value - shift)
    out[0x27] = len(keys)
    struct.pack_into(">I", out, 0x2C, hashes + 4 * len(keys))
    out += b"".join(struct.pack(">I", key) for key in keys)
    out += b"".join(struct.pack(">BI", kind, value) for kind, value in values)
    out += xbox[strings:]
    return bytes(out)


def texture_format(header: bytes) -> str:
    """Format name (DXT1c, DXT5, L8A8, ...) of a tg4h from any platform (+0x05 is 0 only on PC)."""
    endian = "<" if header[5] == 0 else ">"
    _, _, keys, values = _table(header, endian)
    kind, offset = values[keys.index(FORMAT_HASH)]
    return header[offset:header.index(b"\0", offset)].decode("ascii")


def _swap16(data):
    out = bytearray(data)
    out[0::2], out[1::2] = data[1::2], data[0::2]
    return bytes(out)


def tg4d_to_pc(xbox: bytes, header_or_format) -> bytes:
    """Pixel data. Not tiled; every 16-bit word is byte swapped for DXT and L8A8."""
    fmt = header_or_format if isinstance(header_or_format, str) else texture_format(header_or_format)
    if fmt.startswith("DXT") or fmt == "L8A8":
        return _swap16(xbox)
    raise ValueError("no Xbox rule for texture format %s" % fmt)
