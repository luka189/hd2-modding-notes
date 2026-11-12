"""The 32-bit id of a type or field name, and where that id is in the game's network config.

    python3 tools/thin_hash.py health max_health stamina
    python3 tools/thin_hash.py --in types.json health rounds_remaining 0x5d9752f9
    python3 tools/thin_hash.py --in types.json --type 0x5d9752f9 --names names.txt

An id is the upper 32 bits of MurmurHash64A, seed 0, of the name. An argument written 0x........ is taken as an id.
With --in (the list tools/parse_netcfg.py writes) each id is followed by what it is in that build: a type with its
field count, a field with the number of types that declare it, or nothing found. A guessed name whose id is in the
config is a real name.
--type lists one type's fields in their order, each with the name from --names (a file of names, one per line)
whose hash matches, if any.
"""
import json
import struct
import sys


def murmur64(name):
    data = name.encode('utf-8')
    mask, mix = (1 << 64) - 1, 0xC6A4A7935BD1E995
    value = len(data) * mix & mask
    end = len(data) // 8 * 8
    for (word,) in struct.iter_unpack('<Q', data[:end]):
        word = word * mix & mask
        word ^= word >> 47
        value = (value ^ (word * mix & mask)) * mix & mask
    if data[end:]:
        value = (value ^ int.from_bytes(data[end:], 'little')) * mix & mask
    value ^= value >> 47
    value = value * mix & mask
    return value ^ (value >> 47)


def thin(name):
    return murmur64(name) >> 32


def option(flag):
    """the value after a flag, taken out of the arguments, or None"""
    if flag not in sys.argv:
        return None
    i = sys.argv.index(flag)
    if i + 1 >= len(sys.argv):
        sys.exit(f'{flag} needs a value')
    value = sys.argv[i + 1]
    del sys.argv[i:i + 2]
    return value


def as_id(arg):
    """(id, name): an argument written 0x... is an id, anything else a name"""
    if arg.lower().startswith('0x'):
        return int(arg, 16), None
    return thin(arg), arg


def main():
    config, one_type, names_file = option('--in'), option('--type'), option('--names')
    args = sys.argv[1:]
    if not args and not one_type:
        sys.exit(__doc__)
    types = json.load(open(config)) if config else None
    if one_type:
        if types is None:
            sys.exit('--type needs --in types.json')
        tid = int(one_type, 16)
        found = [t for t in types if t['id'] == tid]
        if not found:
            sys.exit('no type %08x in %s' % (tid, config))
        known = {}
        if names_file:
            for line in open(names_file, encoding='utf-8'):
                if line.strip() and not line.startswith('#'):
                    known[thin(line.strip())] = line.strip()
        fields = found[0]['fields']
        print('type %08x, %d fields' % (tid, len(fields)))
        for i, (f, kind) in enumerate(zip(fields, found[0]['types']), 1):
            print(('%3d  %08x  type index %-4d %s' % (i, f, kind, known.get(f, ''))).rstrip())
        return
    by_type = {t['id']: t for t in types} if types else {}
    declared = {}
    for t in types or []:
        for f in t['fields']:
            declared[f] = declared.get(f, 0) + 1
    for arg in args:
        value, name = as_id(arg)
        line = '%08x' % value + (' ' + name if name else '')
        if types is not None:
            what = []
            if value in by_type:
                what.append('a type with %d fields' % len(by_type[value]['fields']))
            if value in declared:
                what.append('a field of %d type(s)' % declared[value])
            line += ': ' + (', '.join(what) or 'not in the config')
        print(line)


if __name__ == '__main__':
    main()
