"""PC Dead Space 1 textures (tg4h header + tg4d pixels) to and from Pillow images.

Only DXT1 and DXT5 (with DXT5_NM read like DXT5) are handled; the pixel data is the full mip chain, largest first.
Writing keeps the header: same size, format and mip count, so a texture can be replaced in place.
"""
import io
import struct

from PIL import Image

import ds1_dlc_xbox


def info(tg4h):
    width, height = struct.unpack_from("<HH", tg4h, 0x20)
    fmt = ds1_dlc_xbox.texture_format(tg4h)
    if fmt.startswith("DXT1"):
        block, fourcc = 8, b"DXT1"
    elif fmt.startswith("DXT5"):
        block, fourcc = 16, b"DXT5"
    else:
        raise ValueError("texture format %s not handled" % fmt)
    return width, height, fmt, block, fourcc


def mip_sizes(width, height, block, total):
    sizes = []
    w, h = width, height
    while sum(sizes) < total:
        sizes.append(max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * block)
        w, h = max(1, w // 2), max(1, h // 2)
    if sum(sizes) != total:
        raise ValueError("pixel data %d does not match a mip chain" % total)
    return sizes


def _dds(width, height, fourcc, data):
    header = struct.pack("<4sIIIIIII44xII4s20xI16x", b"DDS ", 124, 0x81007, height, width, len(data), 0, 1, 32, 4,
                         fourcc, 0x1000)
    return header + data


def read(tg4h, tg4d):
    width, height, fmt, block, fourcc = info(tg4h)
    first = mip_sizes(width, height, block, len(tg4d))[0]
    return Image.open(io.BytesIO(_dds(width, height, fourcc, tg4d[:first]))).convert("RGBA")


def write(image, tg4h, tg4d_template):
    """Pixel data for image in the layout of the template (size, format, mip count)."""
    width, height, fmt, block, fourcc = info(tg4h)
    sizes = mip_sizes(width, height, block, len(tg4d_template))
    image = image.convert("RGBA").resize((width, height), Image.LANCZOS)
    out = b""
    w, h = width, height
    for size in sizes:
        mip = image.resize((w, h), Image.LANCZOS) if (w, h) != image.size else image
        buf = io.BytesIO()
        mip.save(buf, "DDS", pixel_format=fourcc.decode())
        data = buf.getvalue()[128:]
        if len(data) != size:
            # Pillow pads tiny mips to whole blocks the same way; anything else is an error
            raise ValueError("mip %dx%d: %d bytes, expected %d" % (w, h, len(data), size))
        out += data
        w, h = max(1, w // 2), max(1, h // 2)
    return out


def chain_size(width, height, block):
    """Bytes of a full mip chain (down to 1x1, the way retail headers count it)."""
    levels = max(width, height).bit_length()
    total, w, h = 0, width, height
    for _ in range(levels):
        total += max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * block
        w, h = max(1, w // 2), max(1, h // 2)
    return total, levels


def header_for(tg4h, width, height):
    """A copy of a tg4h header (same format and folder string) resized to width x height with a full mip chain:
    +0x1C pixel bytes, +0x20/+0x22 size, +0x26 mip count, +0x47 pixel bytes again. Retail headers of every size
    follow this layout; a stale +0x47 left the zone stuck loading or overran the texture buffer (26.10.)."""
    if width & (width - 1) or height & (height - 1):
        raise ValueError("texture sides must be powers of two (%dx%d)" % (width, height))
    _, _, _, block, _ = info(tg4h)
    total, levels = chain_size(width, height, block)
    out = bytearray(tg4h)
    struct.pack_into("<IHH", out, 0x1C, total, width, height)
    out[0x26] = levels
    struct.pack_into("<I", out, 0x47, total)
    return bytes(out), bytes(total)
