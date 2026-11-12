"""Checks Lua 5.1 source the way the game's own compiler sees it: the globals it reads and assigns, and how near
each function is to Lua's limits of 60 upvalues and 200 local variables.

    python3 tools/lua_check.py mod.lua [more.lua ...]
    python3 tools/lua_check.py mod.lua --allow stingray,Keyboard,Mouse
    python3 tools/lua_check.py mod.lua --allow-file names.txt --near 50

Each file is compiled by a real PUC-Rio Lua 5.1 (the `lupa` package: `pip install lupa`), never run, and the
compiled chunk is read back:

  file:line: global NAME read          a name that is no local, no upvalue and not an allowed global: a typo, a
  file:line: global NAME assigned      missing `local`, or a value the mod expects the game to provide
  file:line: function has N upvalues   at or above --near per cent of the limit (default 80: 48 of 60, 160 of 200)
  file:line: function has N locals     the most local variables alive at once, loop variables counted as Lua does
  file:line: <the compiler's message>  the file does not compile; past a limit the message says which

Allowed without being asked: Lua 5.1's standard globals. --allow adds names (comma-separated), --allow-file a file
of names, one per line. A mod under a loader that hands it a table as `...` needs none for that table: a local is
not a global.

Exit code 1 when a file does not compile or a global outside the allowed names is found; the lines about limits
are notes and do not change it.
"""
import struct
import sys

STANDARD = set('''_G _VERSION assert collectgarbage dofile error getfenv getmetatable ipairs load loadfile loadstring
module next pairs pcall print rawequal rawget rawset require select setfenv setmetatable tonumber tostring type
unpack xpcall coroutine debug io math os package string table'''.split())
MAX_UPVALUES, MAX_LOCALS = 60, 200
GETGLOBAL, SETGLOBAL = 5, 7


class Reader:
    """a compiled Lua 5.1 chunk (string.dump's bytes), read function by function"""

    def __init__(self, data):
        self.d, self.p = data, 12
        if data[:4] != b'\x1bLua' or data[4] != 0x51:
            raise ValueError('not a Lua 5.1 chunk')
        self.end = '<' if data[6] else '>'
        self.int = {4: 'i', 8: 'q'}[data[7]]
        self.size_t = {4: 'I', 8: 'Q'}[data[8]]
        self.instr = {4: 'I'}[data[9]]
        self.number = data[10]

    def take(self, fmt):
        v = struct.unpack_from(self.end + fmt, self.d, self.p)
        self.p += struct.calcsize(self.end + fmt)
        return v[0] if len(v) == 1 else v

    def string(self):
        n = self.take(self.size_t)
        s = self.d[self.p:self.p + n]
        self.p += n
        return s[:-1].decode('utf-8', 'replace') if n else None

    def function(self, out):
        """one function and those inside it, appended to out as dicts"""
        self.string()
        line, last = self.take(self.int), self.take(self.int)
        nups, nparams, vararg, stack = self.take('4B')
        code = [self.take(self.instr) for _ in range(self.take(self.int))]
        consts = []
        for _ in range(self.take(self.int)):
            t = self.take('B')
            if t == 1:
                consts.append(bool(self.take('B')))
            elif t == 3:
                self.p += self.number
                consts.append(0)
            elif t == 4:
                consts.append(self.string())
            else:
                consts.append(None)
        me = dict(line=line, last=last, upvalues=nups, globals=[])
        out.append(me)
        for _ in range(self.take(self.int)):
            self.function(out)
        lines = [self.take(self.int) for _ in range(self.take(self.int))]
        spans = []
        for _ in range(self.take(self.int)):
            self.string()
            spans.append((self.take(self.int), self.take(self.int)))
        for _ in range(self.take(self.int)):
            self.string()
        # the most locals alive at once. The list is in the order of declaration, each with the instruction it
        # starts at and the one its block ends at; blocks nest, so the locals alive are a stack, and those whose
        # block has ended by the time the next one is declared come off its top. (A local declared at the very
        # instruction another's block ends at is inside that block only if it ends there too.)
        stack, most = [], 0
        for start, end in spans:
            while stack and (stack[-1] < start or (stack[-1] == start and stack[-1] < end)):
                stack.pop()
            stack.append(end)
            most = max(most, len(stack))
        me['locals'] = most
        for pc, ins in enumerate(code):
            op = ins & 0x3F
            if op in (GETGLOBAL, SETGLOBAL):
                me['globals'].append((lines[pc] if pc < len(lines) else line, consts[ins >> 14], op == SETGLOBAL))
        return out


def compiled(lua, source, name):
    """string.dump's bytes of the source compiled as a chunk, or (None, the compiler's message)"""
    load = lua.eval('function(src, name) local f, err = loadstring(src, name) if not f then return nil, err end '
                    'return string.dump(f) end')
    got = load(source, b'=' + name.encode('utf-8'))
    if isinstance(got, tuple):
        return None, got[1].decode('utf-8', 'replace')
    return got, None


def check(path, lua, allowed, near):
    """the lines to print for one file, and whether any of them is a fault"""
    source = open(path, 'rb').read()
    if source[:1] == b'#':                       # a first line starting with # is skipped by Lua's loader too
        source = b'--' + source
    data, err = compiled(lua, source, path)
    if err:
        return [err if err.startswith(path + ':') else '%s: %s' % (path, err)], True
    out, fault = [], False
    seen = set()
    functions = Reader(data).function([])
    for f in functions:
        for line, name, assigned in f['globals']:
            if name not in allowed and (line, name, assigned) not in seen:
                seen.add((line, name, assigned))
                out.append((line, '%s:%d: global %s %s' % (path, line, name, 'assigned' if assigned else 'read')))
                fault = True
    for f in functions:
        what = 'the main chunk' if f['line'] == 0 else 'function'
        at = max(f['line'], 1)
        if f['upvalues'] * 100 >= near * MAX_UPVALUES:
            out.append((at, '%s:%d: %s has %d upvalues (the limit is %d)' % (path, at, what, f['upvalues'], MAX_UPVALUES)))
        if f['locals'] * 100 >= near * MAX_LOCALS:
            out.append((at, '%s:%d: %s has %d locals alive at once (the limit is %d)' % (path, at, what, f['locals'], MAX_LOCALS)))
    return [text for _, text in sorted(out, key=lambda o: o[0])], fault


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


def main():
    allow, allow_file, near = option('--allow'), option('--allow-file'), option('--near')
    files = sys.argv[1:]
    if not files:
        sys.exit(__doc__)
    try:
        from lupa import lua51
    except ImportError:
        sys.exit('this needs the lupa package with Lua 5.1: pip install lupa')
    allowed = set(STANDARD)
    if allow:
        allowed |= {n.strip() for n in allow.split(',') if n.strip()}
    if allow_file:
        allowed |= {n.strip() for n in open(allow_file, encoding='utf-8') if n.strip() and not n.startswith('#')}
    lua = lua51.LuaRuntime(encoding=None)
    faults = False
    for path in files:
        lines, fault = check(path, lua, allowed, float(near) if near else 80.0)
        faults = faults or fault
        if lines:
            print('\n'.join(lines))
    return 1 if faults else 0


if __name__ == '__main__':
    sys.exit(main())
