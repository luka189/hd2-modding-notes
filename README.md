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

- The Python tools need Python 3.8 or newer. `lua_check.py` also needs the `lupa` package; `lz4` is optional and
  makes the bundle reading faster.
- `crack_thin.c` needs a C compiler with OpenMP.
- The tools that read the installed game only read it. `atlas_sprites.py` and `material_dump.py` were last run
  against game build 26088801.

Not affiliated with Arrowhead Game Studios. Licence: MIT (see [LICENSE](LICENSE)).
