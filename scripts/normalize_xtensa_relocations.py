"""Remove only trailing all-zero R_XTENSA_NONE linker padding.

GCC8.4/binutils2.35 reserves two unused dynamic relocations for some libgcc
helpers. The runtime accepts actionable relocations only. Do not alter any
relocation, address, symbol, instruction, or file offset; shrink its table and
matching DT_RELASZ. The ordinary runtime validator must still run afterwards.
"""
import struct
from pathlib import Path


def normalize(path):
    path = Path(path)
    data = bytearray(path.read_bytes())
    if data[:7] != b'\x7fELF\x01\x01\x01':
        raise ValueError('Expected little-endian ELF32')
    header = struct.unpack_from('<16sHHIIIIIHHHHHH', data)
    if header[1:3] != (3, 94) or header[11] != 40:
        raise ValueError('Expected Xtensa shared object')
    sections = [struct.unpack_from('<10I', data, header[6] + i * 40)
                for i in range(header[12])]
    removed = 0
    for index, section in enumerate(sections):
        if section[1] != 4 or not section[5] or section[5] % 12:
            continue
        size = section[5]
        while size and data[section[4]+size-12:section[4]+size] == bytes(12):
            size -= 12
        if size == section[5]:
            continue
        for dynamic in sections:
            if dynamic[1] != 6:
                continue
            entries = list(range(dynamic[4], dynamic[4]+dynamic[5], 8))
            if not any(struct.unpack_from('<II', data, p) == (7, section[3]) for p in entries):
                continue
            sizes = [p for p in entries if struct.unpack_from('<I', data, p)[0] == 8]
            if len(sizes) != 1 or struct.unpack_from('<I', data, sizes[0]+4)[0] != section[5]:
                raise ValueError('Inconsistent DT_RELASZ')
            struct.pack_into('<I', data, sizes[0]+4, size)
        struct.pack_into('<I', data, header[6]+index*40+20, size)
        removed += (section[5]-size)//12
    if removed:
        path.write_bytes(data)
    return removed
