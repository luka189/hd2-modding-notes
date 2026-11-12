# Icons and textures

How the game stores and draws its HUD icons, how a mod can draw them without shipping anything, and what a
shipped texture has to look like.

## Drawing a texture through Chef

- `chef.bitmap(id, x, y, w, h, color, layer)` draws a whole texture; `chef.bitmap_uv(id, u0, v0, u1, v1, x, y, w,
  h, color, layer)` draws a rectangle of one. The id is the texture's resource hash as 16 hex digits.
- Inside Chef each texture gets one immediate screen GUI in the game's world (`World.create_screen_gui`), with a
  copy of the game's UI material `e2d6ed90906c1e8b` (`content/ui/shared/misc/yellow_logo`). The texture is bound
  with `Material.set_texture` once a frame and drawn with `Gui.bitmap`.
- The GUI is made at the first draw after `Application.can_get` says the texture is loaded, and kept for that
  world.
- Below native render scale Chef uses the UI world instead.
- Drawn in the game's main world a tint comes out dim (the world's tone mapping); at `chef.TOP` and above it is
  bright and over the game's HUD and map.
- Before Chef 1.4.0, `chef.bitmap` strobed to a white square when another mod drew bitmaps in the same frame;
  `chef.bitmap_uv` with the whole texture (0, 0, 1, 1) did not.

## The game's icons, nothing shipped

### By texture id

- `chef.bitmap('<murmur64 of the texture's path>', ...)` draws any texture the game has loaded.
- The standalone `content/ui/mission/hud/weapon_function/firemode_*` textures are **not** loaded in a mission: the
  HUD draws those icons from atlas sprites.
- Ids of textures other mods draw in a mission: `map/waypoint` ea6c3908c95dd015, `misc/objective_primary`
  230be372b3e9baac, `weapon_function/firemode_deploy_c4` 38adabc6a32af014, `firemode_detonate_c4`
  55374383474193f8.

### By atlas sprite

- Every HUD icon is a sprite on a texture atlas page. The pages are large BC1 / BC3 textures in
  `packages/content/atlas_mission` and `atlas_shared`, loaded whenever the HUD is.
- A `texture_atlas` resource (type `murmur64('texture_atlas')`) is a `u32` count, then 40-byte records: `u64`
  sprite name, `u64` page texture name, `u32` width, `u32` height, `f32` u0, v0, du, dv.
- A sprite's name is the murmur64 of the icon's path: `content/ui/mission/hud/weapon_function/firemode_single` is
  3efff09cd12fb89a, the same id as the standalone texture of that path.
- Drawn with `chef.bitmap_uv(page_id, u0, v0, u0 + du, v0 + dv, x, y, w, h, color, layer)`.
- Build 26088801 has 1,502 sprite records. The fire modes and ammo kinds are 128 px sprites on page
  **f9a3f22a93eedcbd** (4096x2048 BC1, 13 mips, in archive `9ba626afa44a3aa3.patch_53`; the atlas record is in
  `d88cc00669d53c0c`). Other mission pages: 10a081… (2048x1024 BC1, 4 mips) and 7b1eef… (256x256).
- The pages f9a3f2… and 10a081… draw in a mission. The page 18edbed388a3d706 is not loaded in one.
- Sprites with no known path name, found by eye: a0e91aa5… (one stim, 64 px, page 18edbed388a3d706), 55decfa1…
  (three stims, 128 px, page 1667261d881bd08a), e1ebfa9b… (a grenade can, 64 px, page f9a3f22a93eedcbd).
- The fire-mode sprites carry a lot of padding: a fire mode's bullets fill about 0.48 x 0.17 of the sprite's
  square. Aligning an icon by its drawn pixels needs the ink box per sprite.
- The rectangles change when an atlas is repacked. `tools/atlas_sprites.py <game>\data out` reads them from the
  installed game: every sprite record, the pages, and a picture of each named sprite and each small unnamed one.

### The icon materials

- A sprite is a mask, not a picture: black is empty, R and G hold the icon, B its shadow.
- Through Chef's plain UI material (the UI image shader, template **ba25de35**, which paints the texture's RGBA)
  the mask's black background is painted: a dark square.
- The HUD draws each sprite through an icon material named by the sprite's own id. The fire-mode icon materials
  use shader template **5f8113d2**; the stratagem icons use 3461ff0d.
- A GUI icon material is 160 bytes with no settings, the shader template's id at 0x80, and one `diffuse_map` slot
  (slot hash 3aa8b87e) pointing at the standalone texture of its own name. That texture is not loaded in a
  mission; the atlas page has to be bound to the slot at draw time.
- The material layout: a 136-byte header (base material / shader template at 24, texture count at 64, setting count at
  104), the
  texture slot hashes (`u32` each) and their textures (`u64` each), the setting definitions (`u32` type, count,
  name hash, offset, stride) and their float data.
- The 5f8113d2 shader's library (2807be7ec0203571) declares for the pixel program: the texture `diffuse_map`, a
  per-object `c0`, `glow_color` / `glow_range` / `glow_alpha_mul`, `shadow_color` / `shadow_offset` /
  `shadow_range` / `shadow_alpha_mul`, `scissor_rect`, `scissor_rect_offsets`, `scissor_mode`, `atlas_scissor`.
- `tools/material_dump.py` writes a material's parse and a shader library's variable names from the installed
  game.
- **The icon's colour is the vertex colour:** the Color given to `Gui.bitmap_uv`. Setting `c0` changes nothing.
- The recipe that draws them clean: a screen GUI, `Gui.material` for the GUI's own copy of the icon material,
  `Material.set_texture` of the page to slot 3aa8b87e every frame, `Gui.bitmap_uv` with the sprite's rectangle
  and the colour.

## Shipping a texture

### The resource

- A texture resource is a 192-byte (0xC0) Stingray header, then a DDS header with the DX10 extension. The pixels,
  mip 0 first, are in `.gpu_resources`, aligned to 64 bytes.
- The third word of the Stingray header is FFFFFFFF for a texture with nothing streamed.

Two layouts the game accepts:

| | One mip, RGBA8 | The game's own icon layout |
|---|---|---|
| Stingray header | `0, 0, FFFFFFFF`, zeros | `FCE7DA44, 0, FFFFFFFF`, zeros |
| DDS flags | 0x100F | 0x21007 |
| Pitch | set | 0 |
| Depth | | 0 |
| Caps | 0x1000 | 0x401008 |
| DX10 misc2 | | 0 |
| Format | RGBA8 (DXGI 28) | BC3 (DXGI 77) |
| Mips | 1 | the full chain, the mip count in the DDS header |

A layout the game does not accept: BC3 with no class word (FCE7DA44), flags 0xA1007 with the linear size in the
pitch field, depth 1 and misc2 4. The engine draws its `core/fallback_resources/missing_texture` instead: a solid
white square.

### Size and count

- A one-mip texture drawn much smaller than it is looks stair-stepped. `chef.texture_sizes` registers a ladder of
  sizes of one icon and Chef picks the nearest; a texture with a full mip chain needs no ladder.
- 1,054 small textures in one mod crashed the game on quitting. About 100 small textures are fine, and so are two
  2048 px atlases drawn by UV.
- A texture the game streams needs its streamed part laid out as the game's own, or the game crashes on quit.

## The game's HUD textures by name

Standalone textures, named by filediver's hash list. The same paths name the atlas sprites.

- `content/ui/mission/hud/weapon_function/` (47): `firemode_auto`, `firemode_burst`, `firemode_single`,
  `firemode_triple`, `firemode_volley`, `firemode_all_barrels`, `firemode_underbarrel`,
  `firemode_underbarrel_flamer`, `firemode_underbarrel_shotgun`, `firemode_no_underbarrel`, `firemode_deploy_c4`,
  `firemode_detonate_c4`, `firemode_smoke`, `firemode_caltrops_narrow/wide`, `ammo_aphet`, `ammo_flak`, `ammo_he`,
  `ammo_heat`, `ammo_frag`, `ammo_slug`, `ammo_buckshot`, `ammo_flechettes`, `ammo_stun`, `guidance_on/off`,
  `rof_low/medium/high`, `velocity_low/medium/high`, `zeroing_low/medium/high`, `prism_low/medium/high`,
  `flashlight_on/off/auto`, `laser_on/off`, `heat`, `bullet`, `burst_fire`, `airstrike`.
- `content/ui/mission/hud/map/` (25): `waypoint` (the map pin), `arrow`, `player_dot`, `enemy_dot`,
  `mapicon_backpack_ammo/generic/medical/shield`, `mapicon_sample_low/medium/high`,
  `mapicon_supportweapon(_ap/_at)`, `objective_area`, `pulse`, `map_ring`, `map_unknown`, `discoverable_*`,
  `destroyer_dot`, `terrain_grid`.
- `content/ui/mission/hud/misc/` (14): `objective_primary`, `stratagem`, `hud_marker_generic`,
  `destroyer_marker`, `arrows`, `credits_icon`, `item_bracket`, `decor_*`, `wing`, `wing_l`, `hud_static`,
  `hud_climbing_blocked`.
- Also `hud/wheel/` (5) and `hud/compass/` (2).
- Of 69 of these names looked up among the atlas records, 64 are sprites. Not sprites: `prism_*`, `map/arrow`,
  `objective_area`.
- The stim and grenade icons and the stratagem icons are not standalone textures: they exist only as atlas
  sprites.

## The game's data folder

- **The old layout:** an archive per file, named by 16 hex digits with no extension, the pixels in a
  `.gpu_resources` beside it.
- **The slim layout:** `bundles.nxa` plus DSAR bundle files, with loose `.patch_N` archives beside them.
- **A DSAR bundle** is a 32-byte head (`u32` chunk count at 8) and 32-byte chunk records: `u64` uncompressed
  offset, `u64` offset in the file, `u32` uncompressed size, `u32` size, `u8` compression (0 none, 3 LZ4 block).
- **`bundles.nxa`** is a DSAR bundle whose contents are a DSAA index: at 12 a `u32` bundle count and a `u32` item
  count; at 24 the items (`u64` size, `u32` name offset, `u32` entry count, `u64` entries offset); then `u32` name
  offsets of the bundles, the strings NUL-ended. An item's 16-byte entries (`u32` offset in the item at 0, `u32`
  chunk offset in the bundle at 8, `u8` bundle index at 15) say which bundle chunk holds its bytes from that
  offset on.
- **An archive** is `u32` magic F0000011, `u32` type count, `u32` resource count, 60 more header bytes, then 32
  bytes per type, then 80 bytes per resource: `u64` name, `u64` type, `u64` main offset, `u64` stream offset,
  `u64` gpu offset, two `u64`, `u32` main size, `u32` stream size, `u32` gpu size, three `u32`.
- The material resource type is `0xEAC0B497876ADEDF`; a shader library's is `murmur64('shader_library')`.
