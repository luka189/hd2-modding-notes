"""What changed in the game object types between two builds' network configs.

    python3 tools/netcfg_diff.py old_types.json new_types.json
    python3 tools/netcfg_diff.py old_types.json new_types.json 0x5d9752f9 0x803159b3

Both files are the lists tools/parse_netcfg.py writes. Prints the types added and removed, and for every type in
both builds whose fields differ: the fields added, removed, and whether the order of the rest changed. With type ids
after the files, only those types are compared (and each is reported, changed or not). Exit code 1 when anything
differs.
"""
import json
import sys


def changes(old, new):
    """the lines that say how one type's field list changed; none when it did not"""
    out = []
    if old['fields'] == new['fields'] and old['types'] == new['types']:
        return out
    was, now = set(old['fields']), set(new['fields'])
    added = [f for f in new['fields'] if f not in was]
    removed = [f for f in old['fields'] if f not in now]
    if added:
        out.append('  fields added: ' + ' '.join('%08x (#%d)' % (f, new['fields'].index(f) + 1) for f in added))
    if removed:
        out.append('  fields removed: ' + ' '.join('%08x (was #%d)' % (f, old['fields'].index(f) + 1) for f in removed))
    kept_old = [f for f in old['fields'] if f in now]
    kept_new = [f for f in new['fields'] if f in was]
    if kept_old != kept_new:
        out.append('  the order of the fields kept changed')
    kind_old = dict(zip(old['fields'], old['types']))
    kind_new = dict(zip(new['fields'], new['types']))
    moved = [f for f in kept_new if kind_old[f] != kind_new[f]]
    if moved:
        out.append('  type index changed: ' + ' '.join('%08x (%d > %d)' % (f, kind_old[f], kind_new[f]) for f in moved))
    return out


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    old = {t['id']: t for t in json.load(open(sys.argv[1]))}
    new = {t['id']: t for t in json.load(open(sys.argv[2]))}
    only = [int(a, 16) for a in sys.argv[3:]]
    differs = False
    if only:
        for tid in only:
            if tid not in old or tid not in new:
                differs = True
                print('%08x: %s' % (tid, 'in neither build' if tid not in old and tid not in new
                                    else 'added' if tid not in old else 'removed'))
                continue
            lines = changes(old[tid], new[tid])
            differs = differs or bool(lines)
            print('%08x: %d fields, %s' % (tid, len(new[tid]['fields']), 'changed' if lines else 'unchanged'))
            print('\n'.join(lines), end='\n' if lines else '')
        return 1 if differs else 0
    added = [t for t in new if t not in old]
    removed = [t for t in old if t not in new]
    print('%d types before, %d after: %d added, %d removed' % (len(old), len(new), len(added), len(removed)))
    for label, ids, where in (('added', added, new), ('removed', removed, old)):
        for tid in ids:
            print('%s: %08x (%d fields)' % (label, tid, len(where[tid]['fields'])))
    changed = 0
    for tid in new:
        if tid in old:
            lines = changes(old[tid], new[tid])
            if lines:
                changed += 1
                print('changed: %08x (%d > %d fields)' % (tid, len(old[tid]['fields']), len(new[tid]['fields'])))
                print('\n'.join(lines))
    print('%d types changed' % changed)
    return 1 if added or removed or changed else 0


if __name__ == '__main__':
    sys.exit(main())
