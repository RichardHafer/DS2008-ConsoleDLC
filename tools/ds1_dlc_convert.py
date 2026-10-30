"""PS3 -> PC converters for Dead Space 1 resources (console DLC port).

Each function takes the PS3 bytes and returns the PC bytes. Layouts were read from PS3/PC pairs of the same
resource (both platforms ship some identical assets); see analysis/DeadSpace1_DLC_Research_2026-10-23.md.
"""
import struct


def _swap32(data, offset):
    data[offset:offset + 4] = data[offset:offset + 4][::-1]


def _swap16(data, offset):
    data[offset:offset + 2] = data[offset:offset + 2][::-1]


def tg4h(ps3: bytes) -> bytes:
    """Texture header. Fixed part, then a hash list from +0x28's offset to +0x2C's offset, then as many
    (u8, u32) pairs (unaligned), then strings. +0x05 is the platform: 1 PS3, 0 PC. The pixel data (tg4d) is
    the same on both platforms."""
    out = bytearray(ps3)
    for offset in (0x00, 0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C, 0x28, 0x2C):
        _swap32(out, offset)
    out[0x05] = 0
    for offset in (0x06, 0x20, 0x22):
        _swap16(out, offset)
    hashes, pairs = struct.unpack_from("<II", out, 0x28)
    for offset in range(hashes, pairs, 4):
        _swap32(out, offset)
    for index in range((pairs - hashes) // 4):
        _swap32(out, pairs + index * 5 + 1)
    return bytes(out)


class ConversionGap(Exception):
    pass


def simgroup(ps3: bytes, report=None, kinds=None) -> bytes:
    """SimGroup. Header (12 words); packet offset table; GUID and 16-byte blob area (+0x20 bytes, all words);
    string area (+0x24 bytes, kept); then records and packets. A packet: 7 words, the bytes +0x1C..+0x1F
    (+0x1E pointer slots to skip, +0x1F record count), +0x20 a self-relative pointer to its component list
    (class, u32 count, count hashes), +0x24 its GUID slot, +0x28 class, then skip + count record pointers. A
    record: class, u16 property count, a presence bitmap (bytes, a set bit = absent), padding to 4, one word per
    present property. Every word in the record area that is not reached is reported. kinds ({class: {index:
    size}}, tools/ds1_property_kinds.py) names the byte and 16-bit properties: those sit at the start of their slot
    and are not swapped as words."""
    kinds = kinds or {}
    src = bytes(ps3)
    out = bytearray(ps3)
    covered = bytearray(len(src))
    if src[8:12] != b"SimG":
        raise ConversionGap("not a big-endian SimGroup")

    def be32(offset):
        return struct.unpack_from(">I", src, offset)[0]

    def bei32(offset):
        return struct.unpack_from(">i", src, offset)[0]

    def word(offset):
        if covered[offset]:
            return
        _swap32(out, offset)
        covered[offset:offset + 4] = b"\1\1\1\1"

    def keep(offset, size):
        covered[offset:offset + size] = b"\1" * size

    for offset in range(0, 0x30, 4):
        word(offset)
    count = be32(0x18)
    table = be32(0x28)
    packets = [be32(table + 4 * i) for i in range(count)]
    for i in range(count):
        word(table + 4 * i)
    area = table + 4 * count
    guid_size, string_size = be32(0x20), be32(0x24)
    for offset in range(area, area + guid_size, 4):
        word(offset)
    keep(area + guid_size, string_size)

    def record(at):
        if covered[at]:
            return
        sizes = kinds.get(be32(at), {})
        word(at)
        n = struct.unpack_from(">H", src, at + 4)[0]
        _swap16(out, at + 4)
        bitmap = at + 6
        size = (n + 7) >> 3
        stream = (bitmap + size + 3) & ~3
        keep(at + 4, stream - at - 4)
        cursor = stream
        for index in range(n):
            if src[bitmap + (index >> 3)] & (1 << (index & 7)):
                continue
            # The PS3 data holds a small property (a byte, or a flag bit set from a byte) either as its
            # bytes at the start of the slot or as a 32-bit value; the PC decoder reads the start of the slot.
            size = sizes.get(index)
            slot = src[cursor:cursor + 4]
            if size and (size == "byte" or size.startswith("flag")) and slot[0] and not any(slot[1:]):
                keep(cursor, 4)
            elif size == "word" and any(slot[:2]) and not any(slot[2:]):
                _swap16(out, cursor)
                keep(cursor, 4)
            else:
                word(cursor)
            cursor += 4

    def components(at):
        if covered[at]:
            return
        word(at)
        n = be32(at + 4)
        word(at + 4)
        for k in range(n):
            word(at + 8 + 4 * k)

    for p in packets:
        for offset in range(p, p + 0x1C, 4):
            word(offset)
        keep(p + 0x1C, 4)
        skip, n = src[p + 0x1E], src[p + 0x1F]
        list_rel = bei32(p + 0x20)
        word(p + 0x20)
        word(p + 0x24)
        word(p + 0x28)
        if list_rel:
            components(p + 0x20 + list_rel)
        for k in range(skip + n):
            slot = p + 0x2C + 4 * k
            rel = bei32(slot)
            word(slot)
            if k >= skip and rel:
                record(slot + rel)

    gaps = []
    for offset in range(0, len(src) - 3, 4):
        if not covered[offset] and src[offset:offset + 4] != b"\0\0\0\0":
            gaps.append(offset)
    if report is not None:
        report.extend(gaps)
    return bytes(out)
