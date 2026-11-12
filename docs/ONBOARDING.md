# Helldivers 2 Lua modding: how it works

Last checked on game build Steam 26251122 (2026-10-29, patch 7.2.2), engine string
`stingray:46805 437a3d445f9df7662b60086ac8ae3c65b5c95da6`, with Chef Shared Loader 1.5.3.

- [Since the 20 October 2026 patch](#since-the-20-october-2026-patch)
- [The toolchain](#the-toolchain)
- [The game's Lua environment](#the-games-lua-environment)
- [What ends the game](#what-ends-the-game)
- [Reading game state](#reading-game-state)
- [Drawing on screen](#drawing-on-screen)
- [Performance](#performance)
- [Testing outside the game](#testing-outside-the-game)

Related: [FIELDS.md](FIELDS.md) (the network objects' fields), [ICONS.md](ICONS.md) (textures and sprites),
[PATCHING.md](PATCHING.md) (what moves with a game patch).

## Since the 20 October 2026 patch

- The patch added Easy Anti-Cheat and replaced LuaJIT with plain PUC-Rio Lua 5.1. There is no FFI, no JIT and no
  `bit` library, so a mod cannot read game memory, and loaders built on LuaJIT (Bingus Shared Loader) do not run.
- A mod now runs through a loader that replaces the game's `boot` script, and uses the engine's own Lua API.
- Game state is available from five places: the network game objects, a unit's animation variables, the camera,
  the input devices, and the world's units.
- The stratagem cooldowns are in none of them: no field on the player or Helldiver types carries one, and hashing
  likely names against the whole network config matched nothing.

## The toolchain

Mods are plain Lua 5.1 scripts started by a boot-replacing loader, packed as Stingray patch archives that a mod
manager deploys. Only one loader can run: the game runs one `boot`, whichever patch is deployed last.

### Chef Shared Loader

https://github.com/Th3chef/Chef-Shared-Loader (all rights reserved). Its `docs/MODDING.md` is the reference.

- **Modules:** a script headed `-- HD2-Addon: mods/<author>/<name>` gets `local chef = ...` and returns
  `{ update(dt), render(), shutdown() }`.
- **Guarded engine calls:** `chef.call`, and `chef.call_kind` with a crash key of your choosing (one per unit kind or
  object type keeps a crash's cost to that one kind).
- **Units:** `chef.watch` by resource id (from 1.5.0 it hands back a handle with `items` / `pause` / `resume` /
  `refresh` / `stop`), `chef.unit_alive(u)`, `chef.ray_box` (1.4: a ray against a unit's box).
- **Camera:** `chef.camera()`, `chef.world_to_screen(x, y, z)`.
- **Drawing:** `chef.rect`, `chef.triangle`, `chef.text`, `chef.text_width`, `chef.sprite`, `chef.bitmap`,
  `chef.bitmap_uv`, `chef.color`, `chef.line` (world lines). Bottom-left origin; layers 880–960; the game's own
  font from 1.1 on; `chef.TOP` is the UI layer, where colours are exact.
- **The F9 menu:** `chef.option`, `chef.on_change`, `chef.bind` for keys. 1.4 adds `type='color'` rows, buttons,
  headings and folds. From 1.5.3 a held arrow key repeats, so a slider's `on_change` can fire ten times a second.
- **Storage and state:** `chef.load_table` / `chef.save_table` (any string keys, 256 KB), `chef.time`,
  `chef.world_id`, `chef.in_mission`, `chef.setting()`, `chef.mods()`, and `chef.own_log()`: one log per mod, started
  afresh each launch.
- **Watchdogs:** a performance monitor; a hang watchdog (a mod's call over 3 s is stopped and the mod switched off).
- **The trace:** `chef_loader_trace.txt` records the first call of each call kind a mod makes, `>` entered and `<`
  returned, flushed line by line. A `>` with no `<` names the call that killed the game, and the next launch's
  `chef_loader.log` says so.
- **Versions:** 1.1 blocked game object reads; 1.2 allowed them again. 1.3.0: a call that ended the game is skipped
  and the mod stays on (off only after 3 crashed launches). 1.4.0: `chef.bitmap` no longer strobes beside another
  mod's bitmaps. 1.5.0: a mod switched in F9 stops and starts in the same launch (an `on_stop` makes it a real
  stop), saved tables keep every byte up to 256 KB, a unit from an earlier world is refused for good, `chef.mods()`
  counts skipped calls.

### Chef's sandbox

- A mod's environment reaches the game's globals only through `__index`: `rawget(_G, 'stingray')` is nil.
- `require` works for the standard libraries only. There is no `os.execute`, `os.remove` or `os.exit`, no
  bytecode loading, and of `debug` only `traceback` and `getinfo`.
- Files can be read in `%APPDATA%\Arrowhead\Helldivers2` and the game's `data\` folder. Writing is limited to
  `.log .txt .json .csv .dat` files directly in `%APPDATA%\Arrowhead\Helldivers2`.
- A saved table is stored there as `chef_data_<author>_2f<mod>__<table>.lua`.

### Other pieces

| Piece | Facts |
| --- | --- |
| [Boot Mod Loader](https://github.com/pat-pat-patrick/boot-mod-loader) | MIT. Simpler than Chef, no sandbox. |
| [filediver](https://github.com/xypwn/filediver) | BSD-3. Extracts the game's files: the network config, unit meshes, textures. Its `hashes/hashes.txt` lists known resource paths (111,859 names); its `datalibrary/` has the game's component structs. |
| Stingray Lua reference | help.autodesk.com has the signature of most engine functions. |
| Settings file | `%APPDATA%\Arrowhead\Helldivers2\saves\<peer id without leading zeros>_user_settings.config` holds `hud_scale`, `hud_offset`, `hud_map_position` and the like. `Network.peer_id()` pads to 16 hex digits; the file name doesn't. `user_settings.config` has the render and screen resolution (`chef.setting()` reads them). |

### The patch archive

- Files: `9ba626afa44a3aa3.patch_N`, with an empty `.stream` and a `.gpu_resources` beside it, and `manifest.json`.
- Header: 72 bytes, magic `0xF0000011`. Type entry: `<IIQIIII` (32 bytes). Resource entry: `<7Q6I` (80 bytes; the
  fields are in [ICONS.md](ICONS.md), "The game's data folder").
- Names are hashed with MurmurHash64A, seed 0. The Lua type's hash is `0xA14E8DFA2CD117E2`.
- A Lua resource's body is `u32 length, u32 2, text`.
- Texture pixel data goes in `.gpu_resources`, aligned to 64 bytes (see [ICONS.md](ICONS.md)).
- `boot` is the name of the game's start script, which the loader replaces; a mod's resource cannot use it.
- `manifest.json` carries a GUID; a mod keeps the same one across its versions.

### The game build

`Application.build_identifier()` returns the engine string. `Network.object_info(type_name)` (Chef 1.2+) lists the
fields a type declares on the running build, so a mod can check at start that every field it reads is still there.

## The game's Lua environment

PUC-Rio Lua 5.1.4 inside `helldivers2.exe`, under Easy Anti-Cheat.

- **Missing:** `ffi`, `bit`, `jit`, `goto`. There are no 64-bit integers: 64-bit ids are compared as hex strings or
  as engine `IdString64` values.
- **Present:** `io`, `os`, `debug` and the whole `stingray` API (126 engine tables), through the loader's sandbox.
- **No game logic is in Lua.** `_G` holds the standard library, `stingray`, the print functions and boot's hooks.
  Gameplay is C++.
- **Lua's limits:** 200 locals a function (the main chunk counts as one) and 60 upvalues a function. A large mod
  hits both; modules as functions sharing one table stay under them. `tools/lua_check.py` reports how near each
  function is, and every global a file reads or assigns.
- **Worlds:** the ship and each mission are separate worlds with their own ids (`chef.world_id()`). Object ids
  start over in each world, and unit and GUI handles belong to one world.
- **Engine values are short-lived:** a colour or vector object is valid for the frame it was made in.

## What ends the game

A native fault is not a Lua error: `pcall` does not catch it and the process dies. Each item below ended the game
at least once unless it is marked as a precaution.

### Engine calls

- **A call given bad arguments.** Known: `Network.*` info calls without their argument, `Localizer.lookup`,
  position / rotation / mesh calls on runtime-built units, `Unit.has_camera` without a camera name, anything on a
  handle from a world that is gone.
- **A field of a game object that no longer exists.** This happens 4–8 s after a death, at the reinforce.
  `game_object_exists` and `game_object_is_type` in the same frame, before the read, prevent it. A check made
  earlier (a scan once a second) does not.
- **A field the object's type does not declare.** `game_object_field` for a field the type doesn't have ends the
  process on the spot. Example: the attachments list (98b4aaf0) read from the HMG emplacement's gun (type
  fa6ddf17), which has rounds but no such field. `Network.object_info` gives each type's own field list.
- **`Unit.box` on a dying unit** (a structure being destroyed). `chef.unit_alive(u)` in the same frame prevents it.
- **An animation variable read on a unit without a state machine.** A dead Helldiver's unit loses its state
  machine about 8 s after the death while still alive and listed. `Unit.has_animation_state_machine` before every
  read prevents it. Asking the variable's index afresh each time (`Unit.animation_has_variable`,
  `Unit.animation_find_variable`) is a precaution for seats and vehicles.
- **`game_object_field_batched`** has been recorded as the call a launch died in; the cause is not known.
- **A unit in its first seconds** (precaution, reported for freshly spawned stratagem units and not reproduced
  here): no `Unit.*` call on a unit until about 3 s after it appeared.
- A crash on every start, about 5 s into the ship, is an engine call with the wrong arguments, not a Lua error.

### Reading what happened

- **`chef_loader.log`, next launch.** "the last launch crashed in: mods/<author>/<mod>|<call>" names a call that
  was open. "(that call is skipped from now on)" follows repeats; a skipped call returns nil, and an update of the
  mod's file makes Chef try it again.
- **"the last launch ended without a clean shutdown ... its trace last saw it running at N s"** names nothing.
  The trace holds only the first call of each kind, so a crash in a later call of a kind already seen, or outside
  any mod call, looks the same.
- **A launch that ends with "shutdown (clean)" quit normally.**
- **A crash notice on quitting straight from a mission to the desktop**, with the trace showing the clean shutdown
  after every mod's shutdown returned, is the game's or loader's own. If the clean line is missing on such a quit,
  a mod was still running.
- **A last-call file.** A mod can write the name of each engine call to a file before making it, "idle" after each
  frame and a closing line at shutdown; the next launch then knows whether the last one ended inside one of its
  calls (and which), outside them, or cleanly.
- **Minidumps** are in `%APPDATA%\Arrowhead\Helldivers2\dumps\`. Lua VM frames on the main thread mean an engine
  call from a mod; a worker thread with only audio or runtime modules means the game.

## Reading game state

### Network game objects

- **Calls:** `Network.game_session()` (also solo, where you host), `GameSession.objects_owned_by(s, peer)`,
  `GameSession.game_object_is_type(s, id, type_name)`, `game_object_exists`,
  `game_object_field(s, id, field_name)`, `game_object_field_batched(s, id, { names })`,
  `Network.object_info(type_name)` (every field's id, kind, min / max / bits / tolerance), `Network.peer_id()`,
  `GameSession.game_session_host()`.
- **As host you own more:** the SEAF soldiers' and turrets' objects are the host's too.
- **Names are 32-bit hashes:** `murmur64(name) >> 32`. The engine only compares hashes, so any string with the same
  hash works as the name. A stand-in string for an id can be found by brute force (see [PATCHING.md](PATCHING.md)).
- **Real names found by hashing guesses:** health, max_health, stamina, state, position, map_marker_position /
  type / goid, active_emote, num_stims, num_throwables, stance, enabled_mask, is_firing, fire_mode,
  underbarrel_goid, armor_set, owner, original_owner, index, timer, stratagem_type, stratagem_index, peer_id. More
  are in [FIELDS.md](FIELDS.md).
- **`game_object_field_batched`** returns all of a type's fields at once. A type with more than 63 fields comes
  with the first 63 packed as a list in place 64. An object of an unknown type can be read by id alone, the values
  by index.
- **Your things:** the player type 803159b3 (36 fields), the Helldiver type 5d9752f9 (72 fields), weapons (23 to
  27 fields on the ones a Helldiver carries), backpacks. The tables are in [FIELDS.md](FIELDS.md).
- **Ids can change** when a game update changes the network config.

### What the fields don't say directly

- **The Helldiver's flags block 6ff0e58a** is three 64-bit words, read as hex strings. Word 1 bit 48: first-person
  view. Word 1 bit 23: hover-pack flight. Word 2 bit 18: aiming down the sights (a toggled aim counts; being
  knocked out of it ends it). Word 2 bit 22: the weapon settings wheel open. With no 64-bit integers the bits are
  read by hex digit (`floor(digit / 4) % 2` and the like).
- **No field says the map is open**, and none says which weapon is in your hand.
- **The weapon in hand** shows in the Helldiver unit's animation variable `weapon_selected` (the hand pose), read
  with `Unit.animation_find_variable` / `Unit.animation_get_variable`. The third-person Helldiver resource is
  4d1c334d294dfa97. Which pose goes with which weapon type has to be learnt, for example from the weapon whose
  `is_firing` goes true while the fire button is down.
- **`GameSession.unit_synchronizer` answers nil:** there is no object-to-unit map.
- **Other people's guns, seen as host:** a weapon whose aim pitch field (6f3ab277) moves is a soldier's, a
  turret's or a Guard Dog's. A weapon in a Helldiver's hands reads 0 there, though a constant one quantum off 0
  has been seen on a weapon taken from its hellpod, so the test is whether the field moves.
- **The heat field is dead-banded** (tolerance 15.62): the game sends a value only once the heat has moved by that
  much, so falls arrive in steps and a shot smaller than the band hides inside it. A smooth reading needs a model
  between values.
- **Attachments (98b4aaf0)** are a list of 64-bit ids, one per customization slot. The ids are not the hash of any
  known name, so a kit's effect (magazine size, overheat point) can only be learnt per combination of ids.
- **A weapon the map placed** (in a crate or a crashed flier) keeps its pickup link (c3a3f66c) set while in your
  hand; a called-down weapon's link clears when it is picked up.
- **Stratagems:** `stratagem_type` (on 102 types) and `stratagem_index` are both on types a02f5da5 (18 fields,
  with `peer_id`) and 089913db (10 fields, with `spawn_time`). Whether either type holds a countdown is untested.
- **The game's internal weapon names differ from the shop names:** CHEM GUN is the Sterilizer, LASER PULSE CANNON
  the Quasar, GRENADE LAUNCHER TACTICAL the De-Escalator, PLASMA BLASTER the Epoch. The Illuminate cognitive
  disruptor scrambles names into changing random capitals.

### Units

- `World.units(world)` gives every unit: 5,000–11,000 on a mission map.
- `Unit.debug_name(u)` carries the unit's kind as `#ID[<16 hex>]`: the murmur64 of the unit's content path, which is
  also filediver's hash for it.
- `chef.watch({ [resource id] = true }, every)` is Chef's own scan for a few kinds.
- `Unit.box(u)` gives a unit's box and pose. The engine's box is the mesh's box plus 0.00–0.06 m a side (a margin,
  not a scale; 0.25 m on one stump). The mesh's frame starts at the unit's root.

### The ground

There is no height query. The ground can be modelled from the map's own units (rocks, trees, props): a grid of
cells, each kind's height offset above the ground, calibrated by where Helldivers walk.

### Scenery: there is no raycast

No call says what a ray or an arc hits. `chef.ray_box` tests a ray against one unit's box. Finer shapes have to
come from the game's meshes, made offline and tested in the unit's frame in game:

- **Offline:** filediver exports a unit as `.glb`; its collision mesh, or else the LOD0 shell, is voxelised and a
  handful of boxes (8 to 16) fitted inside the solid, stored by the kind's hash.
- **In game:** the unit's pose from `Unit.box`, a line's segments tested against the kind's boxes in the unit's
  frame, the units found through a coarse grid (16 m cells) and held against one box round all their boxes first.
- **A collision mesh does not always cover the model.** The Illuminate ruins carry one for a piece of a wall or
  the foot of a pillar. Measured against the visible outline, whole collision meshes stand behind 87–100 % of it
  and partial ones behind 23–63 %.
- **Shells that enclose nothing** (ruined buildings, cars) have no inside to fill. The intersection of the model's
  three hole-filled silhouettes gives a usable solid.
- **A bottomless shell closed downward everywhere** turns the space under walkways and overhangs solid; closing it
  only where it is closed at the sides does not.
- **The Terminid caves** are solid rock pieces, not one hollow model. **Speedtree units** are small tree models.
- **Counts:** of 1,245 exported kinds of scenery, 878 ended up with boxes; the rest are low, small, or structures
  with a box of their own. On a small arctic map 2,147 of 4,280 listed units were of 143 such kinds; on a four-player
  city map
  5,377 units of 188 kinds.
- **Cost in plain Lua:** about 0.1 ms a frame for one line against the boxes of 1,000–1,300 units. The distance
  checks are the bulk, not the box tests.

### filediver commands

- `filediver -lf "%n %N" -T unit` lists every unit's hash and name without exporting.
- `filediver -T unit --model-format glb --model-include-lods -i "<glob>" -o <dir>` exports. `-x "<glob>"` excludes.
- The glob is matched against the name and the hash. `{a,b,c}` matches any of several. A glob with a "." in it is
  matched against "name.type" instead of the name.
- The glob library is github.com/gobwas/glob, used without separators, so `*` crosses "/".
- A unit with no known name is written as `0x<hash>.unit.glb`. The hash list named 219 of 231 unit kinds met on
  mission maps.
- `filediver -T network_config -o <dir>` extracts the network config.
- Exports are large, and the bulk is the meshes (every LOD with all its vertex attributes); the images are 1 % of
  the bytes. 200 units were 3.7 GB (1.7 GB as 7z). A scanned rock or debris pile is 24–36 MB, a hand-modelled wall
  1–2 MB.

### Camera, input, session

- **Camera:** `chef.camera()` gives `{ x, y, z, fx, fy, fz, yaw, fov }`. `chef.world_to_screen` projects a world
  point and returns nil behind the camera.
- **Input:** `Keyboard`, `Mouse` and `Pad1..` as the engine sees them; a pad's buttons by name through
  `Pad1.button_index`; `chef.bind` for configurable keys. Which key the game has bound to stratagems cannot be
  read.
- **Session:** your peer id, the host and the player count.

### Not readable

Anything that exists only on the HUD or in menus: the mission timer, objectives, the map or Esc menu being open,
pings, hit markers, the stratagem cooldowns.

## Drawing on screen

- **Calls:** `chef.rect(x, y, w, h, color, layer)`, `chef.triangle`, `chef.text(x, y, s, size, color, layer)`,
  `chef.text_width`, `chef.sprite` (rows of cells), `chef.bitmap` / `chef.bitmap_uv` (textures),
  `chef.color(r, g, b, a)`.
- **Coordinates:** bottom-left origin, in pixels.
- **Triangles** are the engine's own where it can draw them, else rows of rects, which cost more; Chef's log says
  which.
- **Colours and vectors** live one frame: they are made in the frame they are used.
- **Below native Render Scale** Chef draws in the UI world and says so in its log.
- **World lines:** `chef.line`. Given anything but a colour object it leaves its quick path and makes one guarded
  engine call per line; thousands of those a frame hang the game. An alpha above about 50 % looks solid.
- **The game's main world tone-maps** what is drawn in it: a tint comes out dimmer there than at `chef.TOP`.
- **F9 hints:** a hint over 200 characters gets no row.
- **The raw engine recipe** (what Chef does for you): a screen GUI on a world (`World.create_screen_gui`),
  `Gui.rect` / `Gui.text` with the game's font `b56d2abac5d17df2`, material `9f85b87d3ff20cbb` and sheet
  `d1ebb991c79f934b`, `Gui.text_extents` for measuring, `Gui.bitmap_uv` with a GUI material for textures.

## Performance

- Plain PUC Lua 5.1 with no JIT: Lua 5.1 on a desktop runs the same code at the same order of speed.
- Measured for a HUD mod that walks the world's units and tests lines against scenery: 0.8–1.0 ms a frame on a
  calm map, 1.2–1.6 ms on a busy one.
- What costs: table literals in draw loops, a table per guarded read, unbounded caches, engine calls per unit per
  frame.
- Spreading a walk over the world's units across frames (tens of units a frame) keeps it out of the frame time.

## Testing outside the game

- A Chef mod runs outside the game in `lupa.lua51` (Python) against a fake `chef` table and fake engine tables:
  objects as tables of fields, a fake camera, fake `Unit.box` and `chef.ray_box`, and every drawn rect, triangle
  and text recorded per frame.
- A fake `game_object_field` that raises on an object that is gone, or on a field its type doesn't declare, finds
  the reads that would end the game.
- A fake `chef.color` and draw calls that reject anything but a colour object find the slow `chef.line` path.
- What such a harness cannot show: the real font's glyph widths, the real field lists of a new game build, and
  timing that depends on the game's clock.
- A log recorded in game (every field's value and change) can be replayed through the same fake game.
- A field's meaning is found fastest by short missions that differ in one thing each (one attachment changed, one
  setting changed), with a key that writes a mark into the log at the moment of interest.
- Marks made by hand lag the event by about half a second, and some flags outlast the event they report.
