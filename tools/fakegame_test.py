"""The fake game's own tests: every rule, the projection, the units, the objects, the menu, the timers.

    python3 tools/fakegame_test.py
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fakegame import Game, GameCrash, RuleBroken, ModError, thin  # noqa: E402

HEAD = '-- HD2-Addon: mods/test/t\nlocal chef = ...\nlocal M = {}\n'


def mod(body, update='', g=None, **kw):
    """a mod whose update runs `update` each frame; `body` runs once at load. Its globals are reachable with g.lua."""
    g = g or Game(**kw)
    g.load(source=HEAD + body + '\nfunction M.update(dt)\n' + update + '\nend\nreturn M\n')
    return g


def raises(exc, fn, rule=None):
    try:
        fn()
    except exc as e:
        if rule:
            assert getattr(e, 'rule', None) == rule or rule in str(e), (rule, str(e))
        return e
    raise AssertionError('%s not raised' % exc.__name__)


def test_projection():
    g = mod('')
    g.camera(pos=(0, 0, 2), forward=(0, 1, 0), fov=math.radians(60))
    w2s = g.rt.eval('FAKE.chef.world_to_screen')
    x, y = w2s(0, 10, 2)
    assert abs(x - 1280) < 1e-9 and abs(y - 720) < 1e-9, (x, y)
    assert w2s(0, -5, 2) is None                                    # behind
    x, y = w2s(1, 10, 2)                                           # 1 m right at 10 m: (720 / tan 30) / 10 px
    assert abs(x - (1280 + 720 / math.tan(math.radians(30)) / 10)) < 1e-6, x
    x, y = w2s(0, 10, 3)                                           # up is up (bottom-left origin)
    assert y > 720
    g.camera(forward=(1, 0, 0))                                    # facing +x: a point at +x is ahead
    assert w2s(10, 0, 2) is not None and w2s(0, 10, 2) is None
    cam = g.rt.eval('FAKE.chef.camera()')
    assert abs(cam.yaw - math.pi / 2) < 1e-9, cam.yaw               # yaw 0 = +y, +x is a quarter turn


def test_field_reads_and_their_rules():
    g = mod('', '''
      local s = chef.call('Network.game_session')
      if chef.call('GameSession.game_object_exists', s, 1) and chef.call('GameSession.game_object_is_type', s, 1, 'my_type') then
        HP = chef.call('GameSession.game_object_field', s, 1, 'health')
        ALT = chef.call('GameSession.game_object_field', s, 1, 'u4d1h9a')   -- (a stand-in name: hashes to 0f27c68e)
      end''')
    g.declare_type('my_type', ['health', '0x0f27c68e'])
    g.add_object(1, 'my_type', {'health': 100, '0x0f27c68e': 7})
    g.run(frames=1)
    assert g.lua('return HP') == 100 and g.lua('return ALT') == 7
    assert g.reads() == {'health': 1, 'u4d1h9a': 1}
    # a field the type does not declare
    g2 = mod('', '''local s = chef.call('Network.game_session')
      if chef.call('GameSession.game_object_exists', s, 1) and chef.call('GameSession.game_object_is_type', s, 1, 'my_type') then
        chef.call('GameSession.game_object_field', s, 1, 'stamina') end''')
    g2.declare_type('my_type', ['health'])
    g2.add_object(1, 'my_type', {'health': 100})
    raises(GameCrash, lambda: g2.run(frames=1), 'undeclared_field')
    # a gone object; and a read with no check this frame (checked last frame does not count)
    g3 = mod('N = 0', '''N = N + 1 local s = chef.call('Network.game_session')
      if N == 1 then chef.call('GameSession.game_object_exists', s, 1) chef.call('GameSession.game_object_is_type', s, 1, 'my_type') end
      chef.call('GameSession.game_object_field', s, 1, 'health')''')
    g3.declare_type('my_type', ['health'])
    g3.add_object(1, 'my_type', {'health': 100})
    g3.run(frames=1)
    raises(RuleBroken, lambda: g3.run(frames=1), 'unchecked_read')
    g3.rules['unchecked_read'] = False
    g3.run(frames=1)
    g3.remove_object(1)
    raises(GameCrash, lambda: g3.run(frames=1), 'gone_object')
    # is_type of a gone object only says no
    g4 = mod('', "R = chef.call('GameSession.game_object_is_type', chef.call('Network.game_session'), 9, 'my_type')")
    g4.run(frames=1)
    assert g4.lua('return R') is False


def test_object_info_and_owners():
    g = mod('', '''local s = chef.call('Network.game_session')
      INFO = chef.call('Network.object_info', 'my_type')
      MINE = chef.call('GameSession.objects_owned_by', s, chef.call('Network.peer_id'))
      HOST = chef.call('GameSession.game_session_host', s)''')
    g.declare_type('my_type', ['health', '0x0f27c68e'], kinds={'health': {'type': 2, 'min': 0, 'max': 1000, 'bits': 16, 'tolerance': 0.5}})
    g.add_object(1, 'my_type', {})
    g.add_object(2, 'my_type', {}, owner='00000000000000ff')
    g.run(frames=1)
    f = g.lua('return INFO.fields[1]')
    assert f['id'] == '%x' % thin('health') and f['type'] == 2 and f['tolerance'] == 0.5
    assert g.lua('return INFO.fields[2].id') == 'f27c68e'                 # (no leading zeros)
    assert list(g.lua('return MINE').values()) == [1] and g.lua('return HOST') == g.G.peer
    raises(GameCrash, lambda: mod('', "chef.call('Network.object_info')").run(frames=1), 'bad_argument')


def test_units_box_pose_and_rules():
    g = mod('', '''
      local u = 'unit1'
      if chef.unit_alive(u) then
        local pose, half = chef.call('Unit.box', u)
        X = { chef.call('Vector3.to_elements', chef.call('Matrix4x4.x', pose)) }
        T = { chef.call('Vector3.to_elements', chef.call('Matrix4x4.translation', pose)) }
        H = { chef.call('Vector3.to_elements', half) }
        P = { chef.call('Vector3.to_elements', chef.call('Unit.world_position', u, 1)) }
        NAME = chef.call('Unit.debug_name', u)
      end''')
    g.add_unit('content/env/rocks/rock_01', pos=(10, 20, 1), yaw=math.pi / 2, box=(1, 2, 3), box_middle=(0, 1, 0.5))
    g.run(frames=1)
    x = g.lua('return X')
    assert abs(x[1]) < 1e-9 and abs(x[2] + 1) < 1e-9, list(x.values())   # turned a quarter (yaw 0 = +y): it faces +x, its x is -y
    t = g.lua('return T')                                              # the box's middle: the root + 1 m along the unit's y (now +x)
    assert abs(t[1] - 11) < 1e-9 and abs(t[2] - 20) < 1e-9 and abs(t[3] - 1.5) < 1e-9, list(t.values())
    assert [round(v, 9) for v in g.rt.eval('{ FAKE.chef.unit_rotation("unit1") }').values()] == [1.0, 0.0, 0.0, round(math.pi / 2, 9)]
    assert list(g.lua('return H').values()) == [1.0, 2.0, 3.0] and list(g.lua('return P').values()) == [10.0, 20.0, 1.0]
    assert g.lua('return NAME') == '#ID[%016x]' % __import__('fakegame').murmur64('content/env/rocks/rock_01')
    # Unit.box with no alive check this frame; on a destroyed unit
    g2 = mod('', "chef.call('Unit.box', 'unit1')")
    g2.add_unit('aaaaaaaaaaaaaaaa', box=(1, 1, 1))
    raises(RuleBroken, lambda: g2.run(frames=1), 'unchecked_box')
    g3 = mod('', "chef.unit_alive('unit1') chef.call('Unit.box', 'unit1')")
    g3.add_unit('aaaaaaaaaaaaaaaa', box=(1, 1, 1))
    g3.run(frames=1)
    g3.destroy_unit('unit1')
    raises(GameCrash, lambda: g3.run(frames=1), 'dead_unit_box')
    # a unit from a world that is gone: chef.call refuses it, a direct call ends the game
    g4 = mod('', "R = { chef.call('Unit.alive', 'unit1') }")
    g4.add_unit('aaaaaaaaaaaaaaaa')
    g4.new_world(settle=0)
    g4.run(frames=1)
    assert list(g4.lua('return R').values()) == [None, 'a unit from a world that is gone'] or g4.lua('return R[2]') == 'a unit from a world that is gone'
    g5 = mod('', "Unit.alive('unit1')")
    g5.add_unit('aaaaaaaaaaaaaaaa')
    g5.new_world(settle=0)
    raises(GameCrash, lambda: g5.run(frames=1), 'old_world_unit')
    # the first seconds (off by default)
    g6 = mod('', "chef.call('Unit.debug_name', 'unit1')")
    g6.add_unit('aaaaaaaaaaaaaaaa')
    g6.run(frames=1)
    g6.rules['fresh_unit'] = True
    g7 = mod('', "chef.call('Unit.debug_name', 'unit1')")
    g7.rules['fresh_unit'] = True
    g7.add_unit('aaaaaaaaaaaaaaaa')
    raises(RuleBroken, lambda: g7.run(frames=1), 'fresh_unit')
    g8 = mod('N = 0', "N = N + 1 if N > 200 then chef.call('Unit.debug_name', 'unit1') end")
    g8.rules['fresh_unit'] = True
    g8.add_unit('aaaaaaaaaaaaaaaa')
    g8.run(4)                                                          # asked first at 3.3 s: allowed


def test_animation_variables():
    g = mod('', '''local u = 'unit1'
      if chef.call('Unit.has_animation_state_machine', u) and chef.call('Unit.animation_has_variable', u, 'weapon_selected') then
        V = chef.call('Unit.animation_get_variable', u, chef.call('Unit.animation_find_variable', u, 'weapon_selected'))
      else V = nil end''')
    u = g.add_unit('4d1c334d294dfa97', anim={'weapon_selected': 3, 'aim': 0.5})
    g.run(frames=1)
    assert g.lua('return V') == 3
    g.set_anim(u, 'weapon_selected', 5)
    g.run(frames=1)
    assert g.lua('return V') == 5
    g.lose_state_machine(u)
    g.run(frames=1)                                                    # the mod asks first: fine
    assert g.lua('return V') is None
    g2 = mod('', "chef.call('Unit.animation_get_variable', 'unit1', 1)")
    u2 = g2.add_unit('4d1c334d294dfa97', anim={'weapon_selected': 3})
    g2.lose_state_machine(u2)
    raises(GameCrash, lambda: g2.run(frames=1), 'no_state_machine')


def test_colours_and_draws():
    g = mod('', '''chef.rect(1, 2, 3, 4, chef.color(10, 20, 30, 40), 905)
      chef.triangle(0, 0, 1, 0, 0, 1, chef.color(1, 2, 3))
      chef.line(0, 0, 0, 1, 1, 1, chef.color(9, 9, 9, 9))
      chef.sprite(100, 100, { 'ab', '.a' }, 2, { a = chef.color(255, 0, 0), b = chef.color(0, 255, 0) })
      chef.bitmap('0123456789abcdef', 0, 0, 8, 8, chef.color(1, 1, 1))''')
    g.run(frames=2)
    kinds = [d['kind'] for d in g.draws]
    assert kinds == ['rect', 'triangle', 'line', 'cell', 'cell', 'cell', 'bitmap'], kinds
    r = g.draws[0]
    assert (r['x'], r['y'], r['w'], r['h'], r['r'], r['a'], r['layer']) == (1, 2, 3, 4, 10, 40, 905)
    cells = [(d['x'], d['y']) for d in g.draws if d['kind'] == 'cell']
    assert cells == [(100, 102), (102, 102), (102, 100)], cells        # the top row drawn highest
    g.missing_texture('0123456789abcdef')
    g.run(frames=1)
    assert g.count('bitmap') == 0
    raises(RuleBroken, lambda: mod('C = nil', "C = C or chef.color(1, 1, 1) chef.rect(0, 0, 1, 1, C)").run(frames=2), 'old_colour')
    raises(RuleBroken, lambda: mod('', "chef.line(0, 0, 0, 1, 1, 1, 0.5)").run(frames=1), 'not_a_colour')


def test_text():
    g = mod('', "W = chef.text(10, 20, 'ammo 30', 2, chef.color(255, 255, 255)) FIT = chef.text_fit('a long text', 1, 30)")
    g.run(frames=1)
    assert g.texts() == 'AMMO 30' and g.lua('return W') == (7 * 6 - 1) * 2
    fit = g.lua('return FIT')
    assert fit.endswith('...') and g.rt.eval('FAKE.chef.text_width')(fit, 1) <= 30 and len(fit) < len('a long text'), fit


def test_options_binds_and_keys():
    src = '''
      SIZE = chef.option('size', { type = 'choice', label = 'Size', choices = { 'Small', 'Large' }, default = 1 })
      chef.on_change('size', function(v) SIZE = v CHANGED = (CHANGED or 0) + 1 end)
      B = chef.bind('ping', 'F6', 'Ping')
      PRESSES = 0'''
    g = mod(src, "if B.pressed() then PRESSES = PRESSES + 1 end DOWN = B.down() K = chef.key_down('tab')")
    assert g.lua('return SIZE') == 1 and g.options()[0]['id'] == 'size' and g.options()[1]['default'] == 'f6'
    g.set_option('size', 2)
    assert g.lua('return SIZE') == 2 and g.lua('return CHANGED') == 1
    g.press('f6')
    g.run(frames=3)
    assert g.lua('return PRESSES') == 1 and g.lua('return DOWN') is False
    g.hold('f6')
    g.hold('tab')
    g.run(frames=3)
    assert g.lua('return PRESSES') == 1 and g.lua('return DOWN') is True and g.lua('return K') is True
    g.release('f6')
    g.run(frames=1)
    assert g.lua('return DOWN') is False
    g2 = Game()
    g2.load(source=HEAD + src + '\nreturn M', options={'size': 2})
    assert g2.lua('return SIZE') == 2                                    # a saved value
    raises(RuleBroken, lambda: mod("chef.option('x', { type = 'toggle', label = 'X', default = true, hint = string.rep('a', 201) })"), 'long_hint')
    mod("chef.option('x', { type = 'toggle', label = 'X', default = true, hint = string.rep('a', 200) })")


def test_watch_timers_and_worlds():
    src = '''W = chef.watch({ ['AAAAAAAAAAAAAAAA'] = true, ['46cab355bd8d4d37'] = true }, 2)
      TICKS, ONCE = 0, 0
      chef.every(0.5, function() TICKS = TICKS + 1 end)
      chef.after(1, function() ONCE = ONCE + 1 end)
      EVENTS = {}
      chef.on('world', function(id) EVENTS[#EVENTS + 1] = 'world ' .. id end)
      chef.on('mission_start', function(id) EVENTS[#EVENTS + 1] = 'mission ' .. id end)'''
    g = mod(src, 'N = #W.items GEN = W.generation WID = chef.world_id()')
    g.add_unit('aaaaaaaaaaaaaaaa', pos=(1, 2, 3))
    g.add_unit('46cab355bd8d4d37')                                      # runtime-built: never listed
    g.add_unit('bbbbbbbbbbbbbbbb')
    g.run(frames=1)
    assert g.lua('return N') == 1 and g.lua('return W.items[1].x') == 1.0 and g.lua('return W.items[1].kind') == 'aaaaaaaaaaaaaaaa'
    g.add_unit('aaaaaaaaaaaaaaaa')
    g.run(1.0)
    assert g.lua('return N') == 1                                       # the next list comes at 2 s
    g.run(1.1)
    assert g.lua('return N') == 2 and g.lua('return GEN') == 2
    assert g.lua('return TICKS') == 4 and g.lua('return ONCE') == 1, (g.lua('return TICKS'), g.lua('return ONCE'))
    g.new_world(mission=True, settle=3)
    g.run(1)
    assert g.lua('return WID') == 0 and g.lua("return chef and 1") is None   # (chef is the mod's local, not a global)
    g.run(2.5)
    assert g.lua('return WID') == 2 and list(g.lua('return EVENTS').values()) == ['world 2', 'mission 2']
    assert g.lua('return N') == 0                                       # the old world's units are gone


def test_ray_box():
    g = mod('', '''chef.unit_alive('unit1')
      D = chef.ray_box({ 0, -10, 1 }, { 0, 1, 0 }, 'unit1')
      MISS = chef.ray_box({ 5, -10, 1 }, { 0, 1, 0 }, 'unit1')
      OWN = chef.ray_box({ x = 0, y = 0, z = 0 }, { x = 1, y = 0, z = 0 }, { x = 10, y = 0, z = 0, yaw = 0.3 }, { 1, 1, 1 })''')
    g.add_unit('aaaaaaaaaaaaaaaa', pos=(0, 0, 0), yaw=math.pi / 4, box=(1, 1, 1), box_middle=(0, 0, 1))
    g.run(frames=1)
    assert abs(g.lua('return D') - (10 - math.sqrt(2))) < 1e-9, g.lua('return D')   # a box turned 45 degrees: its corner
    assert g.lua('return MISS') is None
    own = g.lua('return OWN')
    assert 8.5 < own < 9.0, own


def test_boot_style_and_errors():
    g = Game()
    g.load(source='-- HD2-Boot: mods/test/boot\nN = 0\nfunction init() STARTED = chef.time() end\nfunction update(dt) N = N + 1 end\n')
    g.run(frames=5)
    assert g.lua('return N') == 5 and g.lua('return STARTED') == 0
    e = raises(ModError, lambda: mod('', 'local t = nil\nlocal x = t.field').run(frames=1))
    assert 'attempt to index' in str(e) and 'in the mod: mod:' in str(e), str(e)
    e = raises(ModError, lambda: Game().load(source='this is not lua'))


def test_missing_things_and_saves():
    g = mod("X = chef.no_such_helper", '''R = { chef.call('Nothing.here', 1) }
      chef.save('k', 5) K = chef.load('k') D = chef.load('nope', 9)
      chef.save_table('t', { a = { 1, 2 }, b = 'x' }) T = chef.load_table('t') NONE = { chef.load_table('other') }''')
    g.run(frames=1)
    assert g.missing_chef() == {'no_such_helper': 1}
    assert g.lua('return R[2]') == 'missing' and g.calls()[1] == {'Nothing.here': 1}
    assert g.lua('return K') == 5 and g.lua('return D') == 9 and g.saved_table('t') == {'a': [1, 2], 'b': 'x'}
    assert g.lua('return T.a[2]') == 2 and g.lua('return NONE[2]') == 'none saved'
    raises(ModError, lambda: mod('', "chef.save_table('t', { f = function() end })").run(frames=1))


def test_engine_input():
    g = mod('L = chef.call("Mouse.button_index", "left") K = chef.call("Keyboard.button_index", "f6")',
            'MB = chef.call("Mouse.button", L) KP = chef.call("Keyboard.pressed", K) PAD = chef.call("Pad1.active") MENU = chef.menu_open()')
    g.hold('mouse left')
    g.press('f6')
    g.run(frames=1)
    assert g.lua('return MB') == 1 and g.lua('return KP') is True and g.lua('return PAD') is False and g.lua('return MENU') is False
    g.release('mouse left')
    g.run(frames=1)
    assert g.lua('return MB') == 0 and g.lua('return KP') is False   # (M is the mod's own local: the test's globals are named apart)
    assert mod('', 'X = Mouse.button(0)').run(frames=1).lua('return X') == 0     # (the engine tables are the mod's globals too)


def test_bit():
    g = mod('')
    bit = g.lua('return bit')
    random.seed(3)

    def s32(v):
        v &= 0xFFFFFFFF
        return v - (1 << 32) if v & 0x80000000 else v
    for _ in range(300):
        a, b, n = random.randint(-2 ** 31, 2 ** 31 - 1), random.randint(-2 ** 31, 2 ** 31 - 1), random.randint(0, 31)
        assert bit.band(a, b) == s32(a & b) and bit.bor(a, b) == s32(a | b) and bit.bxor(a, b) == s32(a ^ b)
        assert bit.bnot(a) == s32(~a) and bit.lshift(a, n) == s32(a << n)
        assert bit.rshift(a, n) == s32((a & 0xFFFFFFFF) >> n) and bit.arshift(a, n) == s32(a >> n)
        assert bit.tohex(a) == '%08x' % (a & 0xFFFFFFFF)
    assert bit.tobit(2 ** 32 + 5) == 5 and bit.band(0xff, 0x0f, 0x3) == 3


if __name__ == '__main__':
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print('ok    ', name)
            except Exception as e:                          # noqa: BLE001
                failed += 1
                print('FAILED', name, type(e).__name__, e)
    print('%d failed' % failed)
    sys.exit(1 if failed else 0)
