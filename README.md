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

Not affiliated with Arrowhead Game Studios. Licence: MIT (see [LICENSE](LICENSE)).
