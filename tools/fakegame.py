"""A fake Helldivers 2 for testing a Chef Shared Loader mod's own logic: your mod runs in Lua 5.1 (lupa) against a
stand-in `chef` and stand-in engine tables, you set the game's state from Python (network objects, units, the
camera, keys), step frames, and look at what the mod drew and logged. See docs/TESTING.md.

    from fakegame import Game, GameCrash, RuleBroken
    g = Game()
    g.declare_type('my_player', ['avatar', 'health'])
    g.add_object(1, 'my_player', {'avatar': 2, 'health': 125})
    g.load('my_mod.lua')
    g.run(1.0)
    assert 'HP 125' in g.texts()

The engine calls known to end the game raise GameCrash; the rules that keep a mod out of them (a field read only
after the object was checked the same frame, Unit.box only after the unit was asked alive the same frame, a colour
only in the frame it was made) raise RuleBroken. Each rule can be turned off in Game.rules.

Needs: pip install lupa
"""
import struct
from pathlib import Path

try:
    from lupa import lua51
except ImportError:                                    # pragma: no cover
    raise SystemExit('fakegame needs the lupa package: pip install lupa')


class GameCrash(Exception):
    """An engine call the game would have died in."""


class RuleBroken(Exception):
    """A rule that keeps a mod out of a crash (or a white draw) was broken; the name is in .rule."""

    def __init__(self, rule, message):
        super().__init__(message)
        self.rule = rule


class ModError(Exception):
    """A plain Lua error in the mod (in the game: logged, and the mod is switched off after 20)."""


def murmur64(name):
    """MurmurHash64A, seed 0: the engine's hash of resource paths and names."""
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
    """A network type's or field's 32-bit id: the upper half of murmur64(name). An int, or '0x...', is taken as it is."""
    if isinstance(name, int):
        return name
    if name.lower().startswith('0x'):
        return int(name, 16)
    return murmur64(name) >> 32


RULES = {
    'gone_object': True,         # crash: a field of an object that no longer exists
    'undeclared_field': True,    # crash: a field the object's type does not declare
    'dead_unit_box': True,       # crash: Unit.box (or a mesh call) on a destroyed unit
    'no_state_machine': True,    # crash: an animation variable read on a unit without a state machine
    'old_world_unit': True,      # crash: a direct engine call on a unit from a world that is gone
    'bad_argument': True,        # crash: the engine calls known to end the game on a missing argument
    'unchecked_read': True,      # rule: game_object_field without game_object_exists and _is_type on it this frame
    'unchecked_box': True,       # rule: Unit.box without chef.unit_alive (or Unit.alive) on it this frame
    'old_colour': True,          # rule: a colour made in another frame (the game draws it white)
    'not_a_colour': True,        # rule: a draw given something that is not a colour
    'long_hint': True,           # rule: an option's hint or heading over 200 characters
    'fresh_unit': False,         # rule (a precaution): an engine call on a unit in its first 3 seconds
}
CRASHES = {'gone_object', 'undeclared_field', 'dead_unit_box', 'no_state_machine', 'old_world_unit', 'bad_argument'}

LUA = r'''
local G = FAKE
local function crash(rule, msg)
  if G.rules[rule] then error('GAME CRASH (' .. rule .. '): ' .. msg, 0) end
end
local function rule(rule, msg)
  if G.rules[rule] then error('RULE BROKEN (' .. rule .. '): ' .. msg, 0) end
end
local THINS = {}
local function thin(name)
  if type(name) == 'number' then return name end
  if type(name) ~= 'string' then return nil end
  local v = THINS[name]
  if v == nil then v = G.thin(name) THINS[name] = v end
  return v
end
local function hex(n) return string.format('%x', n) end

-- values ---------------------------------------------------------------------------------------------------------
local VEC = {}
VEC.__index = function(v, k)
  if k == 1 then return rawget(v, 'x') elseif k == 2 then return rawget(v, 'y') elseif k == 3 then return rawget(v, 'z') end
end
VEC.__tostring = function(v) return string.format('Vector3(%g, %g, %g)', v.x, v.y, v.z) end
local function vec(x, y, z) return setmetatable({ x = x or 0, y = y or 0, z = z or 0, vector3 = true }, VEC) end
G.vec = vec
local function xyz(v)
  if type(v) ~= 'table' then return nil end
  if v.x ~= nil then return v.x, v.y, v.z end
  return v[1], v[2], v[3]
end

-- units ----------------------------------------------------------------------------------------------------------
local function unit_of(u, name, guarded)
  local e = G.units[u]
  if e == nil then
    if guarded then return nil, 'no unit' end
    crash('bad_argument', name .. ' given something that is not a unit (' .. tostring(u) .. ')')
    return nil, 'no unit'
  end
  if e.world ~= G.world then
    if guarded then return nil, 'a unit from a world that is gone' end
    crash('old_world_unit', name .. ' on a unit from a world that is gone (' .. tostring(u) .. ')')
    return nil, 'a unit from a world that is gone'
  end
  if G.T - e.born < 3 then rule('fresh_unit', name .. ' on ' .. tostring(u) .. ', ' .. string.format('%.2f', G.T - e.born) .. ' s after it appeared') end
  return e
end

-- the engine calls: E['Table.function'](guarded, ...) ------------------------------------------------------------
local E = {}
G.E = E
E['Unit.alive'] = function(g, u)
  local e, why = unit_of(u, 'Unit.alive', g)
  if not e then return nil, why end
  G.alive_asked[u] = G.frame
  return not e.dead
end
E['Unit.debug_name'] = function(g, u)
  local e, why = unit_of(u, 'Unit.debug_name', g)
  if not e then return nil, why end
  return '#ID[' .. e.kind .. ']'
end
E['Unit.world_position'] = function(g, u, node)
  local e, why = unit_of(u, 'Unit.world_position', g)
  if not e then return nil, why end
  if type(node) ~= 'number' then crash('bad_argument', 'Unit.world_position without its node index') return nil end
  if e.dead then return nil, 'dead' end
  return vec(e.x, e.y, e.z)
end
local function quat(e) return { quaternion = true, R = e.R } end
E['Unit.world_rotation'] = function(g, u, node)
  local e, why = unit_of(u, 'Unit.world_rotation', g)
  if not e then return nil, why end
  if type(node) ~= 'number' then crash('bad_argument', 'Unit.world_rotation without its node index') return nil end
  return quat(e)
end
E['Unit.box'] = function(g, u)
  local e, why = unit_of(u, 'Unit.box', g)
  if not e then return nil, why end
  if e.dead then crash('dead_unit_box', 'Unit.box of a destroyed unit (' .. tostring(u) .. ')') return nil end
  if G.alive_asked[u] ~= G.frame then rule('unchecked_box', 'Unit.box of ' .. tostring(u) .. ' with no chef.unit_alive on it this frame') end
  if not e.half then return nil, 'no box' end
  local R = e.R
  local mx = e.x + R[1][1] * e.mid[1] + R[2][1] * e.mid[2] + R[3][1] * e.mid[3]
  local my = e.y + R[1][2] * e.mid[1] + R[2][2] * e.mid[2] + R[3][2] * e.mid[3]
  local mz = e.z + R[1][3] * e.mid[1] + R[2][3] * e.mid[2] + R[3][3] * e.mid[3]
  return { matrix = true, R = R, t = { mx, my, mz } }, vec(e.half[1], e.half[2], e.half[3])
end
E['Unit.mesh'] = function(g, u)
  local e, why = unit_of(u, 'Unit.mesh', g)
  if not e then return nil, why end
  if e.dead then crash('dead_unit_box', 'Unit.mesh of a destroyed unit (' .. tostring(u) .. ')') end
  return nil, 'no mesh in the fake game'
end
E['Unit.has_animation_state_machine'] = function(g, u)
  local e, why = unit_of(u, 'Unit.has_animation_state_machine', g)
  if not e then return nil, why end
  return e.sm ~= false
end
E['Unit.animation_has_variable'] = function(g, u, name)
  local e, why = unit_of(u, 'Unit.animation_has_variable', g)
  if not e then return nil, why end
  return e.sm ~= false and e.vars[name] ~= nil
end
E['Unit.animation_find_variable'] = function(g, u, name)
  local e, why = unit_of(u, 'Unit.animation_find_variable', g)
  if not e then return nil, why end
  if e.sm == false or e.vars[name] == nil then return nil end
  return e.var_index[name]
end
E['Unit.animation_get_variable'] = function(g, u, index)
  local e, why = unit_of(u, 'Unit.animation_get_variable', g)
  if not e then return nil, why end
  if e.sm == false then crash('no_state_machine', 'an animation variable read on ' .. tostring(u) .. ', which has no state machine') return nil end
  local name = e.var_names[index]
  if name == nil then crash('bad_argument', 'Unit.animation_get_variable with an index the unit does not have') return nil end
  return e.vars[name]
end
E['Unit.has_node'] = function(g, u, name)
  local e, why = unit_of(u, 'Unit.has_node', g)
  if not e then return nil, why end
  return e.nodes[name] ~= nil
end
E['Unit.node'] = function(g, u, name)
  local e, why = unit_of(u, 'Unit.node', g)
  if not e then return nil, why end
  if e.nodes[name] == nil then crash('bad_argument', 'Unit.node: ' .. tostring(u) .. ' has no node ' .. tostring(name)) return nil end
  return e.nodes[name]
end
E['Unit.has_camera'] = function(g, u, name)
  local e, why = unit_of(u, 'Unit.has_camera', g)
  if not e then return nil, why end
  if name == nil then if g then return nil, 'refused' end crash('bad_argument', 'Unit.has_camera without a camera name') end
  return false
end
E['World.units'] = function(g, w)
  if w ~= G.world_handle then crash('bad_argument', 'World.units of ' .. tostring(w) .. ', not the current world') return nil end
  local l = {}
  for _, u in ipairs(G.unit_order) do local e = G.units[u] if e.world == G.world and not e.dead then l[#l + 1] = u end end
  return l
end
E['Matrix4x4.x'] = function(g, m) if type(m) ~= 'table' or not m.matrix then crash('bad_argument', 'Matrix4x4.x given no matrix') return nil end return vec(m.R[1][1], m.R[1][2], m.R[1][3]) end
E['Matrix4x4.y'] = function(g, m) if type(m) ~= 'table' or not m.matrix then crash('bad_argument', 'Matrix4x4.y given no matrix') return nil end return vec(m.R[2][1], m.R[2][2], m.R[2][3]) end
E['Matrix4x4.z'] = function(g, m) if type(m) ~= 'table' or not m.matrix then crash('bad_argument', 'Matrix4x4.z given no matrix') return nil end return vec(m.R[3][1], m.R[3][2], m.R[3][3]) end
E['Matrix4x4.translation'] = function(g, m) if type(m) ~= 'table' or not m.matrix then crash('bad_argument', 'Matrix4x4.translation given no matrix') return nil end return vec(m.t[1], m.t[2], m.t[3]) end
E['Quaternion.right'] = function(g, q) if type(q) ~= 'table' or not q.quaternion then crash('bad_argument', 'Quaternion.right given no quaternion') return nil end return vec(q.R[1][1], q.R[1][2], q.R[1][3]) end
E['Quaternion.forward'] = function(g, q) if type(q) ~= 'table' or not q.quaternion then crash('bad_argument', 'Quaternion.forward given no quaternion') return nil end return vec(q.R[2][1], q.R[2][2], q.R[2][3]) end
E['Quaternion.up'] = function(g, q) if type(q) ~= 'table' or not q.quaternion then crash('bad_argument', 'Quaternion.up given no quaternion') return nil end return vec(q.R[3][1], q.R[3][2], q.R[3][3]) end
E['Vector3'] = function(g, x, y, z) return vec(x, y, z) end
E['Vector3.to_elements'] = function(g, v) if type(v) ~= 'table' or not v.vector3 then crash('bad_argument', 'Vector3.to_elements given no vector') return nil end return v.x, v.y, v.z end
E['Application.build_identifier'] = function(g) return G.build end
-- the input devices as the engine has them (Keyboard and Mouse by button index; no controller connected)
local MOUSE = { 'left', 'right', 'middle', 'extra_1', 'extra_2' }
local KEYS = {}
for i, k in ipairs({ 'escape', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12', 'tab', 'enter',
                     'space', 'backspace', 'left shift', 'right shift', 'left ctrl', 'right ctrl', 'left alt', 'right alt',
                     'up', 'down', 'left', 'right', 'insert', 'delete', 'home', 'end', 'page up', 'page down',
                     'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't',
                     'u', 'v', 'w', 'x', 'y', 'z', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9' }) do KEYS[i - 1] = k KEYS[k] = i - 1 end
E['Mouse.button_index'] = function(g, name) for i, n in ipairs(MOUSE) do if n == name then return i - 1 end end return nil end
E['Mouse.button'] = function(g, i) local n = MOUSE[(i or -1) + 1] return (n and G.keys['mouse ' .. n]) and 1 or 0 end
E['Mouse.pressed'] = function(g, i) local n = MOUSE[(i or -1) + 1] return n ~= nil and G.pressed['mouse ' .. n] == true end
E['Keyboard.button_index'] = function(g, name) return KEYS[name] end
E['Keyboard.button'] = function(g, i) local n = KEYS[i] return (n and G.keys[n]) and 1 or 0 end
E['Keyboard.pressed'] = function(g, i) local n = KEYS[i] return n ~= nil and G.pressed[n] == true end
for p = 1, 8 do
  E['Pad' .. p .. '.active'] = function(g) return false end
  E['Pad' .. p .. '.connected'] = function(g) return false end
end
E['Window.get_main_window'] = function(g) return 'window' end
E['Localizer.lookup'] = function(g) if g then return nil, 'refused' end crash('bad_argument', 'Localizer.lookup ends the game') end
E['Network.game_session'] = function(g) if not G.in_session then return nil end return 'session' end
E['Network.peer_id'] = function(g) return G.peer end
E['Network.object_info'] = function(g, name)
  if name == nil then crash('bad_argument', 'Network.object_info without its argument') return nil end
  local t = G.types[thin(name)]
  if not t then return nil end
  local fields = {}
  for i, f in ipairs(t.order) do
    local k = t.kinds[f]
    fields[i] = { id = hex(f), type = k.type, min = k.min, max = k.max, bits = k.bits, tolerance = k.tolerance }
  end
  return { fields = fields }
end
local function session(s, name) if s ~= 'session' then crash('bad_argument', name .. ' given no session') return false end return true end
E['GameSession.game_session_host'] = function(g, s) if not session(s, 'GameSession.game_session_host') then return nil end return G.host end
E['GameSession.objects_owned_by'] = function(g, s, peer)
  if not session(s, 'GameSession.objects_owned_by') then return nil end
  local l = {}
  for _, id in ipairs(G.object_order) do local o = G.objects[id] if o and o.owner == peer then l[#l + 1] = id end end
  return l
end
E['GameSession.game_object_exists'] = function(g, s, id)
  if not session(s, 'GameSession.game_object_exists') then return nil end
  local yes = G.objects[id] ~= nil
  if yes then local c = G.checked[id] or {} c.exists = G.frame G.checked[id] = c end
  return yes
end
E['GameSession.game_object_is_type'] = function(g, s, id, name)
  if not session(s, 'GameSession.game_object_is_type') then return nil end
  local o = G.objects[id]
  if o == nil then return false end
  local yes = o.type == thin(name)
  if yes then local c = G.checked[id] or {} c.is_type = G.frame G.checked[id] = c end
  return yes
end
E['GameSession.game_object_field'] = function(g, s, id, name)
  if not session(s, 'GameSession.game_object_field') then return nil end
  local o = G.objects[id]
  if o == nil then crash('gone_object', 'a field of object ' .. tostring(id) .. ', which no longer exists') return nil end
  local f = thin(name)
  local t = G.types[o.type]
  if t and not t.kinds[f] then crash('undeclared_field', 'field ' .. tostring(name) .. ' of object ' .. tostring(id) .. ', whose type does not declare it') return nil end
  local c = G.checked[id]
  if not (c and c.exists == G.frame and c.is_type == G.frame) then
    rule('unchecked_read', 'field ' .. tostring(name) .. ' of object ' .. tostring(id) .. ' with no game_object_exists and game_object_is_type on it this frame')
  end
  G.reads[name] = (G.reads[name] or 0) + 1
  return o.fields[f]
end

-- chef -------------------------------------------------------------------------------------------------------------
local chef = {}
G.chef = chef
local function colour(c, what)
  if type(c) ~= 'table' or not c.colour then rule('not_a_colour', what .. ' given ' .. type(c) .. ' ' .. tostring(c) .. ' for a colour') return { 255, 255, 255, 255 } end
  if c.frame ~= G.frame then rule('old_colour', what .. ' given a colour made ' .. (G.frame - c.frame) .. ' frame(s) ago (the game draws it white)') end
  return c
end
local function rec(d) G.draws[#G.draws + 1] = d end
chef.api, chef.loader_version, chef.TOP = 3, '1.5.4', 2000
chef.log_directory = 'C:\\Users\\player\\AppData\\Roaming\\Arrowhead\\Helldivers2'
chef.log = function(fmt, ...)
  local ok, s = pcall(string.format, tostring(fmt), ...)
  G.logs[#G.logs + 1] = { t = G.T, file = G.log_file, text = ok and s or tostring(fmt) }
end
chef.own_log = function(name) G.log_file = name return true end
chef.time = function() return G.T end
chef.world = function() if not G.settled then return nil end return G.world_handle end
chef.world_id = function() if not G.settled then return 0 end return G.world end
chef.in_mission = function() return G.settled and G.mission end
chef.screen = function() return G.screen_w, G.screen_h end
chef.setting = function(path) return G.settings[path] end
chef.in_session = function() return G.in_session end
chef.is_host = function() return G.host == G.peer end
chef.players = function() return G.players end
chef.joining = function() return G.joining end
chef.peer_id = function() return G.peer end
chef.has = function(name) return G.caps[name] == true end
chef.capabilities = G.caps
chef.title = function(t) G.title = t end
chef.camera = function()
  local c = G.cam
  if not c then return nil end
  return { x = c.x, y = c.y, z = c.z, fx = c.fx, fy = c.fy, fz = c.fz, yaw = math.atan2(c.fx, c.fy), fov = c.fov }
end
chef.world_to_screen = function(x, y, z)
  local c = G.cam
  if not c or type(x) ~= 'number' or type(y) ~= 'number' or type(z) ~= 'number' then return nil end
  local fx, fy, fz = c.fx, c.fy, c.fz
  local rx, ry, rz = fy, -fx, 0                         -- right: forward x up
  local rl = math.sqrt(rx * rx + ry * ry)
  if rl < 1e-9 then rx, ry, rl = 1, 0, 1 end
  rx, ry = rx / rl, ry / rl
  local ux, uy, uz = ry * fz - rz * fy, rz * fx - rx * fz, rx * fy - ry * fx   -- up: right x forward
  local dx, dy, dz = x - c.x, y - c.y, z - c.z
  local d = dx * fx + dy * fy + dz * fz
  if d <= 0.01 then return nil end
  local k = (G.screen_h / 2) / math.tan(c.fov / 2) / d
  return G.screen_w / 2 + (dx * rx + dy * ry + dz * rz) * k, G.screen_h / 2 + (dx * ux + dy * uy + dz * uz) * k
end
chef.color = function(r, g, b, a) return { r, g, b, a == nil and 255 or a, colour = true, frame = G.frame } end
chef.rect = function(x, y, w, h, c, layer) c = colour(c, 'chef.rect') rec({ kind = 'rect', x = x, y = y, w = w, h = h, r = c[1], g = c[2], b = c[3], a = c[4], layer = layer or 900 }) end
chef.triangle = function(x1, y1, x2, y2, x3, y3, c, layer) c = colour(c, 'chef.triangle') rec({ kind = 'triangle', x = x1, y = y1, x2 = x2, y2 = y2, x3 = x3, y3 = y3, r = c[1], g = c[2], b = c[3], a = c[4], layer = layer or 900 }) return true end
chef.text_width = function(s, px) s = tostring(s) return (#s * 6 - 1) * (px or 1) end
chef.text = function(x, y, s, px, c, layer)
  c = colour(c, 'chef.text')
  s = string.upper(tostring(s))
  rec({ kind = 'text', x = x, y = y, text = s, size = px or 1, r = c[1], g = c[2], b = c[3], a = c[4], layer = layer or 900 })
  return chef.text_width(s, px)
end
chef.text_fit = function(s, px, w)
  s = tostring(s)
  if chef.text_width(s, px) <= w then return s end
  while #s > 0 and chef.text_width(s .. '...', px) > w do s = string.sub(s, 1, -2) end
  return s .. '...'
end
chef.sprite = function(x, y, rows, cell, colors, layer)
  for r, line in ipairs(rows) do
    for i = 1, #line do
      local c = colors[string.sub(line, i, i)]
      if c then c = colour(c, 'chef.sprite') rec({ kind = 'cell', x = x + (i - 1) * cell, y = y + (#rows - r) * cell, w = cell, h = cell, r = c[1], g = c[2], b = c[3], a = c[4], layer = layer or 900 }) end
    end
  end
end
chef.bitmap = function(tex, x, y, w, h, c, layer)
  c = colour(c, 'chef.bitmap')
  if G.textures[tex] == false then return false end
  rec({ kind = 'bitmap', texture = tex, x = x, y = y, w = w, h = h, r = c[1], g = c[2], b = c[3], a = c[4], layer = layer or 900 })
  return true
end
chef.bitmap_uv = function(tex, u0, v0, u1, v1, x, y, w, h, c, layer)
  c = colour(c, 'chef.bitmap_uv')
  if G.textures[tex] == false then return false end
  rec({ kind = 'bitmap', texture = tex, u0 = u0, v0 = v0, u1 = u1, v1 = v1, x = x, y = y, w = w, h = h, r = c[1], g = c[2], b = c[3], a = c[4], layer = layer or 900 })
  return true
end
chef.texture_sizes = function(map) G.texture_sizes = map end
chef.ui_textures = function(map) end
chef.line = function(x1, y1, z1, x2, y2, z2, c)
  c = colour(c, 'chef.line')
  rec({ kind = 'line', x = x1, y = y1, z = z1, x2 = x2, y2 = y2, z2 = z2, r = c[1], g = c[2], b = c[3], a = c[4] })
end
-- input
chef.key_down = function(k) return G.keys[string.lower(tostring(k))] == true end
chef.key_pressed = function(k) return G.pressed[string.lower(tostring(k))] == true end
chef.key_known = function(k) return true end
chef.mouse_down = function(b) return G.keys['mouse ' .. tostring(b)] == true end
chef.cursor = function() return G.screen_w / 2, G.screen_h / 2 end
chef.wheel = function() return G.wheel end
chef.menu_open = function() return G.menu_open == true end
-- the options menu
chef.option = function(id, spec)
  if type(id) ~= 'string' or not string.match(id, '^[%w_%.%-]+$') then return nil, 'an id is letters, digits, _ . -' end
  if type(spec) ~= 'table' then return nil, 'no spec' end
  for _, k in ipairs({ 'hint', 'heading' }) do
    if type(spec[k]) == 'string' and #spec[k] > 200 then rule('long_hint', 'option ' .. id .. ': its ' .. k .. ' is ' .. #spec[k] .. ' characters (200 at most)') end
  end
  local copy = {}
  for k, v in pairs(spec) do copy[k] = v end
  copy.id = id
  G.specs[#G.specs + 1] = copy
  G.spec_of[id] = copy
  if G.values[id] == nil then G.values[id] = spec.default end
  return G.values[id]
end
chef.get = function(id) return G.values[id] end
chef.set = function(id, v)
  G.values[id] = v
  for _, f in ipairs(G.on_change[id] or {}) do f(v) end
  return v
end
chef.on_change = function(id, f) local l = G.on_change[id] or {} l[#l + 1] = f G.on_change[id] = l end
chef.button = function(id, label, fn, text) chef.option(id, { type = 'button', label = label, run = fn, text = text }) chef.on_change(id, function() fn() end) end
chef.bind = function(id, key, label)
  if type(id) ~= 'string' or not string.match(id, '^[%w_%.%-]+$') then return nil, 'an id is letters, digits, _ . -' end
  chef.option(id, { type = 'key', label = label, default = string.lower(tostring(key)) })
  local b = {}
  b.key = function() return G.values[id] end
  b.pressed = function() local k = G.values[id] return k ~= 'off' and G.pressed[k] == true end
  b.down = function() local k = G.values[id] return k ~= 'off' and G.keys[k] == true end
  return b
end
-- saving
chef.save = function(k, v) G.saved[k] = v return true end
chef.load = function(k, d) local v = G.saved[k] if v == nil then return d end return v end
local function copy(t, depth)
  if type(t) ~= 'table' then return t end
  if depth > 16 then error('chef.save_table: more than 16 deep') end
  local o = {}
  for k, v in pairs(t) do
    if type(v) == 'function' or type(v) == 'userdata' then error('chef.save_table: plain data only (' .. type(v) .. ')') end
    o[k] = copy(v, depth + 1)
  end
  return o
end
chef.save_table = function(name, t) G.tables[name] = copy(t, 0) return true end
chef.load_table = function(name) local t = G.tables[name] if t == nil then return nil, 'none saved' end return copy(t, 0) end
-- units
chef.unit_alive = function(u)
  local e = G.units[u]
  if not e or e.world ~= G.world then return false end
  G.alive_asked[u] = G.frame
  return not e.dead
end
chef.unit_kind = function(u) local e = G.units[u] if not e or e.world ~= G.world then return nil end return e.kind end
chef.unit_position = function(u, node)
  local e = G.units[u]
  if not e or e.world ~= G.world or e.dead then return nil end
  return e.x, e.y, e.z
end
chef.unit_rotation = function(u)
  local e = G.units[u]
  if not e or e.world ~= G.world or e.dead then return nil end
  local f = e.R[2]
  return f[1], f[2], f[3], math.atan2(f[1], f[2])
end
chef.unit_node = function(u, name) local e = G.units[u] if not e or e.world ~= G.world then return nil end return e.nodes[name] end
chef.watch = function(kinds, every)
  local w = { items = {}, generation = 0, active = true }
  local own = { kinds = kinds, every = every or 5, next = 0, w = w }
  w.refresh = function() own.next = 0 end
  w.pause = function() w.active = false end
  w.resume = function() w.active = true end
  w.stop = function() w.active = false own.stopped = true end
  G.watches[#G.watches + 1] = own
  return w
end
local function watch_tick()
  for _, own in ipairs(G.watches) do
    if own.w.active and not own.stopped and G.T >= own.next and G.settled then
      own.next = G.T + own.every
      local wanted = {}
      for k in pairs(own.kinds) do wanted[string.lower(k)] = true end
      local items = {}
      for _, u in ipairs(G.unit_order) do
        local e = G.units[u]
        if e.world == G.world and not e.dead and wanted[e.kind] and e.kind ~= '46cab355bd8d4d37' then
          items[#items + 1] = { unit = u, kind = e.kind, x = e.x, y = e.y, z = e.z }
        end
      end
      own.w.items = items
      own.w.generation = own.w.generation + 1
    end
  end
end
chef.ray_box = function(from, dir, box, ext)
  local ox, oy, oz = xyz(from)
  local dx, dy, dz = xyz(dir)
  if not (ox and dx) then return nil, 'from and dir' end
  local R, cx, cy, cz, hx, hy, hz
  if ext then
    local bx, by, bz = xyz(box)
    local yaw = type(box) == 'table' and box.yaw or 0
    local c, s = math.cos(yaw), math.sin(yaw)
    R = { { c, -s, 0 }, { s, c, 0 }, { 0, 0, 1 } }
    cx, cy, cz = bx, by, bz
    hx, hy, hz = xyz(ext)
  else
    if not chef.unit_alive(box) then return nil, 'no unit' end
    local m, half = E['Unit.box'](true, box)
    if not m then return nil, half end
    R, cx, cy, cz, hx, hy, hz = m.R, m.t[1], m.t[2], m.t[3], half.x, half.y, half.z
  end
  local l = math.sqrt(dx * dx + dy * dy + dz * dz)
  if l < 1e-12 then return nil, 'dir' end
  dx, dy, dz = dx / l, dy / l, dz / l
  local px, py, pz = ox - cx, oy - cy, oz - cz
  local t0, t1 = -math.huge, math.huge
  local hs = { hx, hy, hz }
  for i = 1, 3 do
    local a = R[i]
    local p, d = px * a[1] + py * a[2] + pz * a[3], dx * a[1] + dy * a[2] + dz * a[3]
    if math.abs(d) < 1e-12 then
      if math.abs(p) > hs[i] then return nil end
    else
      local ta, tb = (-hs[i] - p) / d, (hs[i] - p) / d
      if ta > tb then ta, tb = tb, ta end
      if ta > t0 then t0 = ta end
      if tb < t1 then t1 = tb end
      if t0 > t1 then return nil end
    end
  end
  if t1 < 0 then return nil end
  return math.max(t0, 0)
end
-- timers, events
chef.after = function(s, fn) local t = { at = G.T + s, fn = fn, live = true } G.timers[#G.timers + 1] = t return { cancel = function() t.live = false end, active = function() return t.live end } end
chef.every = function(s, fn) local t = { at = G.T + s, every = s, fn = fn, live = true } G.timers[#G.timers + 1] = t return { cancel = function() t.live = false end, active = function() return t.live end } end
chef.after_startup = function(fn) G.startup[#G.startup + 1] = fn end
chef.on = function(ev, fn) local l = G.listeners[ev] or {} l[#l + 1] = fn G.listeners[ev] = l end
chef.emit = function(ev, ...) for _, f in ipairs(G.listeners[ev] or {}) do f(...) end end
local function timer_tick()
  local due = {}
  for _, t in ipairs(G.timers) do if t.live and G.T >= t.at then due[#due + 1] = t end end
  for _, t in ipairs(due) do
    if t.every then t.at = t.at + t.every else t.live = false end
    t.fn()
  end
  local keep = {}
  for _, t in ipairs(G.timers) do if t.live then keep[#keep + 1] = t end end
  G.timers = keep
end
-- engine calls through chef
chef.call = function(name, ...)
  local f = E[name]
  if f == nil then G.missing_calls[name] = (G.missing_calls[name] or 0) + 1 return nil, 'missing' end
  G.calls[name] = (G.calls[name] or 0) + 1
  return f(true, ...)
end
chef.call_kind = function(name, kind, ...) return chef.call(name, ...) end
setmetatable(chef, { __index = function(t, k) G.missing_chef[k] = (G.missing_chef[k] or 0) + 1 return nil end })

-- the mod's environment ------------------------------------------------------------------------------------------
local function bit32_lib()
  local function tobit(x) x = math.floor(x) % 4294967296 if x >= 2147483648 then x = x - 4294967296 end return x end
  local function u(x) return math.floor(x) % 4294967296 end
  local function op(a, b, f)
    a, b = u(a), u(b)
    local r, p = 0, 1
    for _ = 1, 32 do
      local x, y = a % 2, b % 2
      if f(x, y) then r = r + p end
      a, b, p = (a - x) / 2, (b - y) / 2, p * 2
    end
    return tobit(r)
  end
  local B = {}
  B.tobit = tobit
  B.band = function(a, b, ...) local r = op(a, b, function(x, y) return x == 1 and y == 1 end) if ... then return B.band(r, ...) end return r end
  B.bor = function(a, b, ...) local r = op(a, b, function(x, y) return x == 1 or y == 1 end) if ... then return B.bor(r, ...) end return r end
  B.bxor = function(a, b, ...) local r = op(a, b, function(x, y) return x ~= y end) if ... then return B.bxor(r, ...) end return r end
  B.bnot = function(a) return tobit(4294967295 - u(a)) end
  B.lshift = function(a, n) return tobit(u(a) * 2 ^ (n % 32)) end
  B.rshift = function(a, n) return tobit(math.floor(u(a) / 2 ^ (n % 32))) end
  B.arshift = function(a, n) return tobit(math.floor(tobit(a) / 2 ^ (n % 32))) end
  B.tohex = function(a, n) n = n or 8 return string.sub(string.format('%08x', u(a)), -n) end
  return B
end
local function tables()
  local base = {}
  for _, k in ipairs({ 'assert', 'error', 'ipairs', 'next', 'pairs', 'pcall', 'print', 'rawequal', 'rawget', 'rawset',
                       'select', 'setmetatable', 'getmetatable', 'tonumber', 'tostring', 'type', 'unpack', 'xpcall',
                       'loadstring', 'setfenv', 'getfenv', 'collectgarbage', '_VERSION' }) do base[k] = _G[k] end
  base.load = function(s, name) if type(s) ~= 'string' then return nil, 'load: a string only' end return loadstring(s, name) end
  base.string, base.math, base.coroutine = string, math, coroutine
  base.table = setmetatable({ new = function() return {} end, clear = function(t) for k in pairs(t) do t[k] = nil end end, unpack = unpack }, { __index = table })
  base.os = { time = os.time, clock = os.clock, date = os.date, difftime = os.difftime }
  base.io = { open = function() return nil, 'no files in the fake game' end }
  base.debug = { traceback = debug.traceback, getinfo = debug.getinfo }
  base.bit = bit32_lib()
  local stingray = {}
  for name, f in pairs(E) do
    local tab, fn = string.match(name, '^(%w+)%.([%w_]+)$')
    if tab then
      stingray[tab] = stingray[tab] or {}
      stingray[tab][fn] = function(...) return f(false, ...) end
    end
  end
  stingray.Vector3 = setmetatable(stingray.Vector3 or {}, { __call = function(_, x, y, z) return vec(x, y, z) end })
  base.stingray = stingray
  return base, stingray
end
function FAKE_LOAD(src, chunk, boot)
  local f, err = loadstring(src, '=' .. chunk)
  if not f then error('MOD ERROR: ' .. err, 0) end
  local base, stingray = tables()
  if boot then base.chef = chef end
  local env = setmetatable({}, { __index = function(t, k) local v = base[k] if v ~= nil then return v end return stingray[k] end })
  rawset(env, '_G', env)
  setfenv(f, env)
  local ok, mod = xpcall(function() return f(chef) end, debug.traceback)
  if not ok then error(mod, 0) end
  if boot then
    mod = { init = rawget(env, 'init'), update = rawget(env, 'update'), render = rawget(env, 'render'), shutdown = rawget(env, 'shutdown') }
    if mod.init then local ok2, e2 = xpcall(mod.init, debug.traceback) if not ok2 then error(e2, 0) end end
  end
  if type(mod) ~= 'table' then error('MOD ERROR: the mod returned ' .. type(mod) .. ', not a table with update', 0) end
  G.mod, G.env = mod, env
  for _, fn in ipairs(G.startup) do local ok3, e3 = xpcall(fn, debug.traceback) if not ok3 then error(e3, 0) end end
  G.startup = {}
  return mod
end
function FAKE_RUN(n)
  local mod = G.mod
  for _ = 1, n do
    G.frame = G.frame + 1
    G.T = G.T + G.dt
    G.draws = {}
    for k in pairs(G.release_after) do if not G.held[k] then G.keys[k] = nil end end
    G.pressed, G.next_pressed = G.next_pressed, {}
    for k in pairs(G.pressed) do G.keys[k] = true end
    G.release_after = G.pressed
    G.wheel, G.next_wheel = G.next_wheel, 0
    if not G.settled and G.T >= G.settle_at then
      G.settled = true
      chef.emit('world', G.world)
      if G.mission then chef.emit('mission_start', G.world) end
    end
    local ok, err = xpcall(function()
      watch_tick()
      timer_tick()
      if mod.update then mod.update(G.dt) end
      if mod.render then mod.render() end
    end, debug.traceback)
    if not ok then error(err, 0) end
  end
end
function FAKE_SHUTDOWN()
  local mod = G.mod
  if mod and mod.on_stop then mod.on_stop() end
  if mod and mod.shutdown then mod.shutdown() end
end
'''


def _lua_value(rt, v):
    if isinstance(v, tuple) and len(v) == 3 and all(isinstance(x, (int, float)) for x in v):
        return rt.globals().FAKE.vec(*[float(x) for x in v])
    if isinstance(v, (list, tuple)):
        return rt.table_from([_lua_value(rt, x) for x in v])
    if isinstance(v, dict):
        return rt.table_from({k: _lua_value(rt, x) for k, x in v.items()})
    return v


def _py(v):
    """a Lua table as a Python dict or list (plain values only)"""
    if hasattr(v, 'items') and not isinstance(v, (str, bytes, dict)):
        d = {k: _py(x) for k, x in v.items()}
        if d and all(isinstance(k, int) for k in d) and sorted(d) == list(range(1, len(d) + 1)):
            return [d[i] for i in range(1, len(d) + 1)]
        return d
    return v


class Game:
    """One fake game. Units, objects and the camera can be set before or after load(); run() steps frames."""

    def __init__(self, fps=60, screen=(2560, 1440), mission=True, peer='0000000000000001'):
        self.rt = lua51.LuaRuntime(unpack_returned_tuples=True)
        self.rules = dict(RULES)
        g = self.rt.table_from({})
        self.rt.globals().FAKE = g
        self.G = g
        g.thin = lambda name: murmur64(name) >> 32     # (the mod's names are hashed as they are, as the engine does)
        g.rules = self.rt.table_from(self.rules)
        g.T, g.frame, g.dt = 0.0, 0, 1.0 / fps
        g.world, g.mission, g.settled, g.settle_at = 1, mission, True, 0.0
        g.world_handle = 'world1'
        g.screen_w, g.screen_h = screen
        g.cam = self.rt.table_from({'x': 0.0, 'y': 0.0, 'z': 1.8, 'fx': 0.0, 'fy': 1.0, 'fz': 0.0, 'fov': 0.9})
        for name in ('objects', 'types', 'checked', 'units', 'alive_asked', 'draws', 'specs', 'spec_of', 'values',
                     'on_change', 'saved', 'tables', 'keys', 'held', 'pressed', 'next_pressed', 'release_after',
                     'timers', 'startup', 'listeners', 'watches', 'textures', 'calls', 'missing_calls', 'missing_chef',
                     'reads', 'settings'):
            g[name] = self.rt.table_from({})
        g.logs = self.rt.table_from([])
        g.object_order, g.unit_order = self.rt.table_from([]), self.rt.table_from([])
        g.wheel, g.next_wheel = 0, 0
        g.peer = g.host = peer
        g.in_session, g.players, g.joining = True, 1, 0
        g.build = 'stingray:46805 437a3d445f9df7662b60086ac8ae3c65b5c95da6'
        g.log_file = 'chef_loader'
        g.settings['screen_resolution'] = self.rt.table_from(list(screen))
        g.settings['render_settings.render_resolution'] = self.rt.table_from(list(screen))
        caps = ['api', 'after_startup', 'settings', 'share', 'events', 'require', 'bind', 'menu', 'shims', 'logs',
                'own_log', 'units', 'spawn', 'timers', 'budget', 'session', 'settings_file', 'shapes', 'sprite_sheets',
                'notify', 'typed', 'key_labels', 'save_table', 'mods', 'health', 'index', 'joining', 'mouse_hold',
                'players_event', 'option_buttons', 'option_colors', 'option_headings', 'option_folds', 'menu_state',
                'mod_stopped_event', 'bind_combos', 'ray_box', 'hang_watchdog']
        g.caps = self.rt.table_from({c: True for c in caps})
        self.rt.execute(LUA)
        self._units = 0
        self.mod = None

    # --- the mod ---------------------------------------------------------------------------------------------------
    def load(self, path=None, source=None, options=None):
        """Runs the mod's file (or source text) as Chef would start it: an addon gets `chef` as `...` and returns its
        table; a boot-style script (`-- HD2-Boot:`) gets `chef` as a global and its init() is run. options: the F9 rows'
        values to start with ({ id: value }), as a player's saved ones."""
        if source is None:
            source = Path(path).read_text(encoding='utf-8')
        name = Path(path).name if path else 'mod'
        for k, v in (options or {}).items():
            self.G['values'][k] = _lua_value(self.rt, v)
        boot = source.lstrip().startswith('-- HD2-Boot:')
        self.chunk = name
        self.mod = self._lua(lambda: self.rt.globals().FAKE_LOAD(source, name, boot))
        return self

    def run(self, seconds=None, frames=None):
        """Steps the game: update(dt) then render() each frame."""
        n = frames if frames is not None else max(1, int(round((seconds or 0) / self.G.dt)))
        self.G.rules = self.rt.table_from(self.rules)
        self._lua(lambda: self.rt.globals().FAKE_RUN(n))
        return self

    def shutdown(self):
        self._lua(lambda: self.rt.globals().FAKE_SHUTDOWN())

    def lua(self, code):
        """Runs Lua in the mod's environment (its globals; for a look at a boot-style mod's state)."""
        f = self.rt.eval('function(code, env) local f = assert(loadstring(code)) setfenv(f, env) return f() end')
        return self._lua(lambda: f(code, self.G.env))

    def _lua(self, fn):
        try:
            return fn()
        except lua51.LuaError as e:
            msg = str(e)
            # the message, and where in the mod it came from (the traceback's lines in the mod's own file)
            where = [l.strip() for l in msg.split('\n') if l.strip().startswith(getattr(self, 'chunk', 'mod') + ':')]
            first = msg.split('\nstack traceback')[0]
            text = first + (('\n  in the mod: ' + '; '.join(dict.fromkeys(where))) if where else '')
            if 'GAME CRASH (' in first:
                raise GameCrash(text[text.index('GAME CRASH ('):]) from None
            if 'RULE BROKEN (' in first:
                part = text[text.index('RULE BROKEN ('):]
                raise RuleBroken(part[len('RULE BROKEN ('):part.index(')')], part) from None
            raise ModError(text) from None

    # --- network objects -------------------------------------------------------------------------------------------
    def declare_type(self, name, fields, kinds=None):
        """A network object type and the fields it declares, in order: names (any string with the right hash works,
        as in the game) or ids ('0x...' or ints). kinds: { field: {'type': 1, 'min': 0, 'max': 255, 'bits': 8,
        'tolerance': 0} } for Network.object_info (type 0 bool, 1 whole number, 2 decimal, 3 Vector3, 4 rotation,
        9 64-bit id, 10 list)."""
        order = [thin(f) for f in fields]
        kk = {}
        for f, fid in zip(fields, order):
            info = (kinds or {}).get(f, {})
            kk[fid] = self.rt.table_from(dict({'type': 1}, **info))
        self.G.types[thin(name)] = self.rt.table_from({'name': name, 'order': self.rt.table_from(order),
                                                        'kinds': self.rt.table_from(kk)})
        return thin(name)

    def add_object(self, oid, type_name, fields=None, owner=None):
        """A network object: its id, its type (a name or an id), its fields' values by name. owner: a peer id (yours by
        default). A tuple of three numbers becomes a Vector3, a list a Lua list."""
        f = {thin(k): _lua_value(self.rt, v) for k, v in (fields or {}).items()}
        self.G.objects[oid] = self.rt.table_from({'type': thin(type_name), 'fields': self.rt.table_from(f),
                                                  'owner': owner or self.G.peer})
        self.G.object_order[len(self.G.object_order) + 1] = oid
        return oid

    def set_field(self, oid, field, value):
        self.G.objects[oid].fields[thin(field)] = _lua_value(self.rt, value)

    def field(self, oid, field):
        return _py(self.G.objects[oid].fields[thin(field)])

    def remove_object(self, oid):
        self.G.objects[oid] = None

    def reads(self):
        """{ field name as the mod asked: reads } since the start."""
        return _py(self.G.reads) or {}

    # --- units -----------------------------------------------------------------------------------------------------
    def add_unit(self, kind, pos=(0.0, 0.0, 0.0), yaw=0.0, axes=None, box=None, box_middle=(0.0, 0.0, 0.0),
                 anim=None, state_machine=True, nodes=None, handle=None):
        """A unit in the current world: its kind (16 hex digits: the murmur64 of its path, or a path), its root's
        position, its facing (yaw in radians, 0 = +y; or axes: its x, y and z axes in the world), its box (half
        sizes; Unit.box's pose has the unit's axes and the box's middle, box_middle from the root in the unit's
        frame), its animation variables ({ name: value }), its nodes ({ name: index }). Returns its handle."""
        if not (len(kind) == 16 and all(c in '0123456789abcdef' for c in kind.lower())):
            kind = '%016x' % murmur64(kind)
        self._units += 1
        u = handle or 'unit%d' % self._units
        if axes is None:
            import math
            c, s = math.cos(yaw), math.sin(yaw)
            axes = ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))
        names = list((anim or {}).keys())
        e = {'kind': kind.lower(), 'x': float(pos[0]), 'y': float(pos[1]), 'z': float(pos[2]),
             'R': [[float(a) for a in ax] for ax in axes], 'half': [float(b) for b in box] if box else None,
             'mid': [float(b) for b in box_middle], 'sm': bool(state_machine),
             'vars': dict(anim or {}), 'var_index': {n: i + 1 for i, n in enumerate(names)},
             'var_names': {i + 1: n for i, n in enumerate(names)}, 'nodes': dict(nodes or {'root': 1}),
             'world': self.G.world, 'born': self.G.T, 'dead': False}
        self.G.units[u] = self.rt.table_from(e, recursive=True)
        self.G.unit_order[len(self.G.unit_order) + 1] = u
        return u

    def move_unit(self, u, pos):
        e = self.G.units[u]
        e.x, e.y, e.z = (float(p) for p in pos)

    def set_anim(self, u, name, value):
        e = self.G.units[u]
        if e.var_index[name] is None:
            n = len(e.var_names) + 1
            e.var_index[name], e.var_names[n] = n, name
        e.vars[name] = value

    def lose_state_machine(self, u):
        self.G.units[u].sm = False

    def destroy_unit(self, u):
        self.G.units[u].dead = True

    def units(self):
        return [u for u in self.G.unit_order.values()]

    # --- the world, the camera, input ------------------------------------------------------------------------------
    def new_world(self, mission=True, settle=3.0):
        """A new world (the ship, or a mission): its id goes up, every unit of the old one is gone (a call on one ends
        the game, chef.call refuses it). chef.world() is nil until it settles, settle seconds on."""
        g = self.G
        g.world = g.world + 1
        g.world_handle = 'world%d' % g.world
        g.mission, g.settled, g.settle_at = mission, settle <= 0, g.T + settle
        return g.world

    def camera(self, pos=None, forward=None, fov=None):
        """The view camera: its position, its forward direction (made unit length) and its vertical field of view in
        radians. chef.world_to_screen projects through it onto the screen, bottom-left origin."""
        c = self.G.cam
        if pos is not None:
            c.x, c.y, c.z = (float(p) for p in pos)
        if forward is not None:
            import math
            l = math.sqrt(sum(f * f for f in forward)) or 1.0
            c.fx, c.fy, c.fz = (float(f) / l for f in forward)
        if fov is not None:
            c.fov = float(fov)

    def press(self, key):
        """A key (the engine's name: 'f6', 'left ctrl', 'mouse left') pressed for the next frame."""
        self.G.next_pressed[key.lower()] = True

    def hold(self, key):
        self.G.held[key.lower()] = True
        self.G['keys'][key.lower()] = True

    def release(self, key):
        self.G.held[key.lower()] = None
        self.G['keys'][key.lower()] = None

    def scroll(self, n=1):
        self.G.next_wheel = n

    def set_option(self, oid, value):
        """A change of an F9 row, as the player makes it: its on_change handlers run."""
        self._lua(lambda: self.G.chef.set(oid, _lua_value(self.rt, value)))

    def option(self, oid):
        return _py(self.G['values'][oid])

    def options(self):
        """The rows the mod registered, in order: each its spec as a dict, with 'id'."""
        return [_py(s) for s in self.G.specs.values()]

    def emit(self, event, *args):
        self._lua(lambda: self.G.chef.emit(event, *args))

    def missing_texture(self, tex):
        """chef.bitmap and bitmap_uv answer false for this texture, as for one that is not loaded."""
        self.G.textures[tex] = False

    # --- what the mod did ------------------------------------------------------------------------------------------
    @property
    def T(self):
        return self.G.T

    @property
    def draws(self):
        """What the last frame drew: dicts with 'kind' (rect, triangle, text, cell, bitmap, line) and its numbers."""
        return [_py(d) for d in self.G.draws.values()]

    def texts(self):
        """The texts the last frame drew, in order, joined by ' | ' (chef.text draws in capitals)."""
        return ' | '.join(d['text'] for d in self.draws if d['kind'] == 'text')

    def count(self, kind):
        return sum(1 for d in self.draws if d['kind'] == kind)

    @property
    def logs(self):
        """Every chef.log line so far, as text."""
        return [l.text for l in self.G.logs.values()]

    def calls(self):
        """{ engine call: how often } made through chef.call, and the ones the fake does not have (they answered
        nil, 'missing', as Chef answers for a function the game lacks)."""
        return _py(self.G.calls) or {}, _py(self.G.missing_calls) or {}

    def missing_chef(self):
        """The chef helpers the mod asked for that the fake does not have (they read as nil)."""
        return _py(self.G.missing_chef) or {}

    def saved_table(self, name):
        return _py(self.G.tables[name])
