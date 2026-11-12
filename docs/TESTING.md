# Testing a mod outside the game

`tools/fakegame.py` runs a Chef Shared Loader mod in Lua 5.1 against a fake game you set up from Python: network
objects with their fields, units with boxes and animation variables, the camera, keys. You step frames and look at
what the mod drew and logged. The engine calls known to end the game raise an error instead.

    pip install lupa
    python3 tools/fakegame_test.py                                # the fake's own tests
    python3 examples/health_readout/test_health_readout.py        # an example mod and its tests

- [Two tools, two jobs](#two-tools-two-jobs)
- [A first test](#a-first-test)
- [Setting up the game](#setting-up-the-game)
- [Running and looking](#running-and-looking)
- [The rules](#the-rules)
- [What is faked, and how](#what-is-faked-and-how)
- [What is not](#what-is-not)

## Two tools, two jobs

| | Chef's `tools/modsim` | `tools/fakegame.py` |
|---|---|---|
| Runs | The real loader, built from Chef's source, through a scripted session: title screen, ship, mission | Your mod alone, with a stand-in `chef` |
| Game state | No gameplay: units of a few kinds, no network objects | What you put in: network objects and their fields, units, animation variables, the camera, keys |
| You get | The loader's log, the health file, a summary of what was drawn | A Python object to assert on: every draw of the last frame, every log line, every engine call |
| Good for | Does the mod start, does the loader accept its options and calls | Does the mod read the game right and draw the right thing |

Both are in plain Lua 5.1. Neither replaces a run in the game.

## A first test

```python
import sys
sys.path.insert(0, 'tools')
from fakegame import Game

g = Game()
g.declare_type('un6y1d', ['u4d1h9a'])                 # the player type and its avatar field
g.declare_type('vvhx8ga', ['health', 'max_health'])   # the Helldiver type
g.add_object(1, 'un6y1d', {'u4d1h9a': 2})
g.add_object(2, 'vvhx8ga', {'health': 125, 'max_health': 125})
g.load('my_mod.lua')
g.run(0.5)
assert g.texts() == 'HP 125'

g.set_field(2, 'health', 20)
g.run(0.1)
assert g.texts() == 'HP 20'
```

`examples/health_readout/` is that mod in full, with tests for damage, a key held, an F9 option, a reinforce and a
new world.

## Setting up the game

### Loading the mod

| Call | What it does |
|---|---|
| `g.load('mod.lua')` | Runs the file as Chef starts it. An addon (`-- HD2-Addon:`) gets `chef` as `...` and returns its table. A boot-style script (`-- HD2-Boot:`) gets `chef` as a global, and its `init()` runs. `chef.after_startup` functions run after it. |
| `g.load(source=text)` | The same, from a string. |
| `g.load(..., options={'size': 2})` | F9 values as a player's saved ones. |

The mod runs in its own environment: its globals are its own, and the engine tables (`Unit`, `World`,
`GameSession`, ...) are reachable as globals and under `stingray`. Chef's `bit`, `table.new`, `table.clear`,
`table.unpack` and `load` from a string are there. `io.open` answers nil.

### Network objects

| Call | What it does |
|---|---|
| `g.declare_type(name, fields, kinds=None)` | A type and the fields it declares, in order. |
| `g.add_object(id, type, fields, owner=None)` | An object of a type, with its fields' values. `owner` is a peer id; yours by default. |
| `g.set_field(id, field, value)`, `g.field(id, field)` | A field's value, set or read. |
| `g.remove_object(id)` | The object is gone (a reinforce, a weapon used up). |

- **Names are hashes.** A type or field is known by the 32-bit hash of its name, as in the game. In `declare_type`
  and `add_object` a name can be given as itself, or as its id: `'0xcb0453ea'` or `0xcb0453ea`. A mod's string is
  hashed as it is, so any string with the right hash works for it, as in the game.
- **`kinds`** gives `Network.object_info` its answer per field: `{'health': {'type': 2, 'min': 0, 'max': 1000,
  'bits': 16, 'tolerance': 0.5}}`. The kinds are in [FIELDS.md](FIELDS.md). A field with none given is a whole number.
- **Values:** a tuple of three numbers becomes a Vector3, a list a Lua list, `None` nil. "No object" in a field
  that holds an object id is 32767.

### Units

`g.add_unit(kind, pos, yaw=0, axes=None, box=None, box_middle=(0,0,0), anim=None, state_machine=True, nodes=None)`
returns the unit's handle.

| Argument | What it is |
|---|---|
| `kind` | 16 hex digits, or a content path (hashed with murmur64). `Unit.debug_name` gives `#ID[<kind>]`. |
| `pos` | The unit's root in the world. |
| `yaw` or `axes` | Its facing: yaw in radians, 0 = +y, a quarter turn = +x. Or its x, y and z axes in the world. |
| `box`, `box_middle` | `Unit.box`'s half sizes, and the box's middle from the root in the unit's frame. |
| `anim` | Its animation variables, `{'weapon_selected': 3}`. |
| `state_machine` | False: it has none, and a variable read ends the game. |
| `nodes` | `{'root': 1, 'head': 7}` for `Unit.node` and `chef.unit_node`. |

Then `g.move_unit(u, pos)`, `g.set_anim(u, name, value)`, `g.lose_state_machine(u)` and `g.destroy_unit(u)`.

### The world, the camera, input

| Call | What it does |
|---|---|
| `g.new_world(mission=True, settle=3.0)` | A new world: its id goes up, every unit of the old one is gone. `chef.world()` is nil and `chef.world_id()` 0 until it settles; then the `world` and `mission_start` events fire. |
| `g.camera(pos, forward, fov)` | The view camera; `fov` is vertical, in radians. |
| `g.press(key)` | A key down for the next frame: the engine's names, `'f6'`, `'left ctrl'`, `'mouse left'`. |
| `g.hold(key)`, `g.release(key)` | A key held until released. |
| `g.scroll(n)` | The mouse wheel, next frame. |
| `g.set_option(id, value)` | An F9 row changed as a player changes it: its `on_change` functions run. |
| `g.emit(event, ...)` | An event to the mod's `chef.on` listeners. |
| `g.missing_texture(id)` | `chef.bitmap` and `bitmap_uv` answer false for it. |

`Game(fps=60, screen=(2560, 1440), mission=True, peer='0000000000000001')` sets the rest.

## Running and looking

| Call | What it gives |
|---|---|
| `g.run(seconds)`, `g.run(frames=n)` | Steps the game: each frame `update(dt)`, then `render()`. |
| `g.draws` | The last frame's draws: dicts with `kind` (`rect`, `triangle`, `text`, `cell`, `bitmap`, `line`), the position and size, `r g b a`, `layer`. |
| `g.texts()` | The last frame's texts, joined by `' | '`. `chef.text` draws in capitals. |
| `g.count(kind)` | How many draws of a kind the last frame made. |
| `g.logs` | Every `chef.log` line. |
| `g.calls()` | The engine calls made through `chef.call`, and those the fake does not have. |
| `g.reads()` | Field reads by the name the mod used. |
| `g.missing_chef()` | `chef` helpers the mod asked for that the fake does not have. |
| `g.options()`, `g.option(id)` | The F9 rows registered, and a row's value. |
| `g.saved_table(name)` | What `chef.save_table` saved. |
| `g.lua(code)` | Lua run in the mod's environment: `g.lua('return COUNT')` reads a global of the mod. |
| `g.T` | The fake clock. |

A Lua error in the mod raises `ModError`, with the line in the mod it came from. In the game Chef logs it and
switches the mod off after 20.

## The rules

Each is on unless switched off with `g.rules['name'] = False`. A crash raises `GameCrash`; a rule raises
`RuleBroken`, its name in `.rule`. The crashes are the ones in [ONBOARDING.md](ONBOARDING.md#what-ends-the-game).

| Name | Kind | What triggers it |
|---|---|---|
| `gone_object` | crash | `game_object_field` of an object that no longer exists |
| `undeclared_field` | crash | `game_object_field` of a field the object's type does not declare |
| `dead_unit_box` | crash | `Unit.box` or `Unit.mesh` on a destroyed unit |
| `no_state_machine` | crash | `Unit.animation_get_variable` on a unit without a state machine |
| `old_world_unit` | crash | A direct engine call on a unit from a world that is gone. Through `chef.call` it answers nil and why, as Chef refuses it |
| `bad_argument` | crash | `Network.object_info` without its argument, `Unit.world_position` without its node, `Localizer.lookup`, `Unit.has_camera` without a name (directly), and the fake's other functions given the wrong thing |
| `unchecked_read` | rule | `game_object_field` on an object that had no `game_object_exists` and `game_object_is_type` the same frame |
| `unchecked_box` | rule | `Unit.box` on a unit with no `chef.unit_alive` (or `Unit.alive`) the same frame |
| `old_colour` | rule | A draw with a colour made in an earlier frame: the game draws it white |
| `not_a_colour` | rule | A draw given anything but a colour: `chef.line` then takes a slow path per line |
| `long_hint` | rule | An F9 row's `hint` or `heading` over 200 characters |
| `fresh_unit` | rule, off | An engine call on a unit in its first 3 seconds (a precaution) |

A check made in an earlier frame does not count: the object or unit can go between two frames.

## What is faked, and how

- **Frames:** 60 a second by default, `update(dt)` then `render()`. `chef.time()` is the fake clock.
- **`chef.call` and `chef.call_kind`:** the fake's engine functions. A function the fake does not have answers
  `nil, 'missing'`, as Chef answers for one the game lacks, and is counted in `g.calls()`.
- **Engine functions:** `Unit.alive`, `debug_name`, `world_position`, `world_rotation`, `box`, `mesh`,
  `has_animation_state_machine`, `animation_has_variable`, `animation_find_variable`, `animation_get_variable`,
  `has_node`, `node`, `has_camera`; `World.units`; `Matrix4x4.x`, `y`, `z`, `translation`; `Quaternion.right`,
  `forward`, `up`; `Vector3`, `Vector3.to_elements`; `Network.game_session`, `peer_id`, `object_info`;
  `GameSession.game_session_host`, `objects_owned_by`, `game_object_exists`, `game_object_is_type`,
  `game_object_field`; `Application.build_identifier`; `Mouse` and `Keyboard` `button_index`, `button`,
  `pressed`; `Pad1`–`Pad8` `active` and `connected` (always false); `Window.get_main_window`; `Localizer.lookup`.
- **`Unit.box`** returns a pose and the half sizes. The pose's axes are the unit's; its translation is the box's
  middle in the world.
- **`chef.world_to_screen`** is a perspective projection through the camera onto the screen, bottom-left origin;
  nil behind the camera. **`chef.camera()`**'s yaw is `atan2(fx, fy)`: 0 = +y.
- **`chef.text_width`** is `(characters × 6 − 1) × px`: the loader's pixel font, not the game's proportional one.
- **`chef.watch`** lists the current world's live units of the given kinds at once and then every `every`
  seconds (5 by default); runtime-built units (`46cab355bd8d4d37`) are never listed.
- **`chef.ray_box`** is a ray against a unit's oriented box, or a box you name with its middle, `yaw` and
  extents. From inside the box it answers 0.
- **Also there:** `chef.log`, `own_log`, `time`, `world`, `world_id`, `in_mission`, `screen`, `setting`,
  `in_session`, `is_host`, `players`, `joining`, `peer_id`, `has`, `capabilities`, `title`, `color`, `rect`,
  `triangle`, `text`, `text_fit`, `sprite`, `bitmap`, `bitmap_uv`, `texture_sizes`, `line`, `key_down`,
  `key_pressed`, `mouse_down`, `cursor`, `wheel`, `menu_open`, `option`, `get`, `set`, `on_change`, `button`,
  `bind`, `save`, `load`, `save_table`, `load_table`, `unit_alive`, `unit_kind`, `unit_position`,
  `unit_rotation`, `unit_node`, `after`, `every`, `after_startup`, `on`, `emit`.

## What is not

- How anything looks: nothing is drawn. Sizes, colours and placement need the game.
- The game's font: text widths are the pixel font's.
- Gameplay: nothing moves or changes unless the test changes it.
- The loader itself: no crash guard, no skipped calls, no budget or hang watchdog, no load order between mods.
  Chef's `tools/modsim` runs the real loader.
- `game_object_field_batched`, spawning, particles, lights, `chef.spread`, `chef.share` and the other services
  between mods.
- Performance: Lua runs at the computer's speed. Plain Lua 5.1 is the game's Lua too, so the order of the
  numbers carries over; the game's own load does not.
- A mod that passes here can still fail in the game: the rules cover the crashes that are known.
