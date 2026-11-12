# Helldivers 2 modding notes

Reference notes for writing Lua mods for Helldivers 2 since the 20 October 2026 patch (Easy Anti-Cheat, plain
Lua 5.1): the loader and its sandbox, the engine calls that end the game, the network game objects and their
fields, units and scenery, drawing, textures and icons.

Last checked on game build Steam 26251122 (patch 7.2.2, 2026-10-29) with Chef Shared Loader 1.5.3.

| File | What is in it |
| --- | --- |
| [docs/ONBOARDING.md](docs/ONBOARDING.md) | The toolchain, the Lua environment, what ends the game, reading game state, units and scenery, drawing, performance, testing outside the game |
| [docs/FIELDS.md](docs/FIELDS.md) | The fields of the Helldiver, the player object, weapons and backpacks: ids, real names, values |
| [docs/ICONS.md](docs/ICONS.md) | The game's HUD textures and atlas sprites, the icon materials, the texture layouts the game accepts, the data folder's formats |
| [docs/PATCHING.md](docs/PATCHING.md) | What a game patch can move, the network config's format, names for new ids |
| [CREDITS.md](CREDITS.md) | Where the findings came from |

In the notes a meaning marked "guess" fits what was seen but is not confirmed, and "precaution" marks a rule that
has not been tied to a crash.

## Tools

| Tool | What it does |
| --- | --- |
| [tools/parse_netcfg.py](tools/parse_netcfg.py) | Lists every game object type and its fields from the game's network config (extracted with filediver) |
| [tools/netcfg_diff.py](tools/netcfg_diff.py) | Compares two builds' lists: types added and removed, fields added, removed or reordered |
| [tools/thin_hash.py](tools/thin_hash.py) | A name's 32-bit id; whether an id is a type or a field in a build; one type's fields in order |
| [tools/crack_thin.c](tools/crack_thin.c) | Finds a stand-in name for any 32-bit id by brute force |
| [tools/atlas_sprites.py](tools/atlas_sprites.py) | Reads the texture atlas records from the installed game: each icon's page and uv rectangle, with pictures |
| [tools/material_dump.py](tools/material_dump.py) | Dumps a material's shader template, texture slots and settings, and a shader library's variable names |
| [tools/lua_check.py](tools/lua_check.py) | Compiles Lua 5.1 source without running it and reports stray globals and the functions near Lua's limits of 60 upvalues and 200 locals |
| [tools/scenery_boxes.py](tools/scenery_boxes.py) | Makes boxes for each kind of scenery from filediver's unit exports (boxes inside the solid, plates on flat faces, boxes over thin walls), as JSON or a Lua table |
| [tools/scenery_review.py](tools/scenery_review.py), [scenery_review.html](tools/scenery_review.html) | The page `scenery_boxes.py --review` writes: every kind drawn with its boxes, to pick each kind's fill and leave kinds out by eye |

- The Python tools need Python 3.8 or newer. `lua_check.py` also needs the `lupa` package; the scenery tools need
  `trimesh`, `numpy`, `scipy` and `pillow`; `lz4` is optional and makes the bundle reading faster.
- `crack_thin.c` needs a C compiler with OpenMP.
- The tools that read the installed game only read it. `atlas_sprites.py` and `material_dump.py` were last run
  against game build 26088801.

## Data

| File | What is in it |
| --- | --- |
| [data/scenery_boxes.json](data/scenery_boxes.json) | Boxes for 878 kinds of scenery (13,909 boxes, 2,332 of them turned about z), made with `tools/scenery_boxes.py` from exports of 1,245 kinds on game build 26251122, each kind's fill chosen by eye. The file's `about` line gives the layout |

Not in the scenery data: enemy structures, kinds whose boxes reach less than 0.5 m above their root, kinds a round
passes through (wire, banners, posters), and a set of intact city towers seen in game that was not among the exports.
The data is older than the tool's last fix to its plates: a fresh run gives some kinds (1 of 63 checked) a few more.

Not affiliated with Arrowhead Game Studios. Licence: MIT (see [LICENSE](LICENSE)).
