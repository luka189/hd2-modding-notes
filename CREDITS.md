# Credits

Where the findings in these notes came from. The notes themselves carry no attributions; they are all here.

## Origin

The notes were written while building [NarrowHUD](https://www.nexusmods.com/helldivers2/mods/17882)
([source](https://github.com/luka189/NarrowHUD)), a HUD mod by luka189, from its in-game logs, crash traces and
measurements between October and November 2026. Anything not listed below comes from that work.

## Tools the work rests on

| Tool | Author | Used for |
| --- | --- | --- |
| [Chef Shared Loader](https://github.com/Th3chef/Chef-Shared-Loader) | Th3chef | The loader the notes describe; its `docs/MODDING.md` and changelog are the source for its API and version notes |
| [filediver](https://github.com/xypwn/filediver) (BSD-3) | xypwn | Extracting the network config, unit meshes and textures; its hash list names units and textures; its documentation of the archive and material formats |
| [HD2Runtime](https://github.com/SkyeShade/HD2Runtime) | SkyeShade | Research on the game's texture and icon layout, the texture atlas records, the bundle formats, and the icon mask shader |
| [gobwas/glob](https://github.com/gobwas/glob) | gobwas | The glob syntax filediver's patterns follow |
| Stingray Lua API reference | Autodesk | Engine call signatures |

## Findings from other mods and modders

| Finding | From |
| --- | --- |
| The rule of leaving a freshly spawned unit alone for about 3 s; the minidump folder and how to read a dump; the crash notice on quitting being the game's or loader's own | Rosensterner (HUDdle, Nexus 18108, and the hd2-chef-mod field guide) |
| Mech facts in the field tables (on-foot flags, per-part `zone_health`); the player object holding no stratagem cooldowns; drawing the game's own textures by id; the limits on shipped textures (many small textures, streamed textures) | Rosensterner (HUDdle) |
| `look_at_position` and the smoothed hit point field bdc1cb8a | Blast & Trajectory Markers (Nexus 18214) |
| The heat field's dead band | Reticle Ammo HUD by Garage001 |
| The Helldiver's field 20efbed4 holding the vehicle | Integrated HUD |
| The one-mip RGBA8 texture layout and the patch archive layout that the game accepts | Treasure Radar by Th3chef |

Ideas and facts only: no code from any of these is reproduced here.
