# Scenery: boxes in place of a raycast

The engine gives a mod no call that says what a line or an arc hits. This is the way round it: a handful of boxes
for each kind of scenery, made offline from the game's meshes, and a test of a line against them in plain Lua.

- [The data](#the-data): `data/scenery_boxes.json`, boxes for 878 kinds
- [Making the boxes](#making-the-boxes): `tools/scenery_boxes.py` and its review page
- [In the game](#in-the-game): listing units, a unit's pose, the test (`lua/scenery.lua`)

## The data

`data/scenery_boxes.json` has one entry per kind of unit:

    "956d43fe3e09760a": {
      "name": "root_wall_01",
      "path": "content/planet_forest_swamp/assets/organic/root_walls/root_wall_01",
      "box": [4.01, 5.9, 2.79, 0.08, -0.22, 0.92],
      "boxes": [[1.36, 1.3, 1.3, -0.69, -1.75, 0.61], [1.12, 1.24, 1.12, -1.51, 0.79, 0.78], ...]
    }

- **The key** is the unit's resource hash: the murmur64 of its content path, and the 16 hex digits in
  `Unit.debug_name(u)`'s `#ID[...]`. A unit whose path is not known has its hash as its name and an empty path.
- **The frame** is the unit's own: metres from the unit's root, x right, y forward, z up.
- **`box`** is the mesh's bounding box: half sizes `hx, hy, hz`, then its middle `cx, cy, cz`.
- **`boxes`** are what a line is tested against, each `hx, hy, hz, cx, cy, cz`. A box with a seventh number is
  turned about z by that angle, in radians.
- Numbers are rounded to the centimetre, a yaw to four places.

### What the boxes are

| Kind of box | Where it is | Can it stand outside the thing? |
|---|---|---|
| Inside boxes | In the solid, a voxel in from the surface; each the biggest that fits in what the others left | No |
| Plates | On a flat face of a man-made thing (a wall, a deck, a roof), 0.2 m thick behind the face | Only by its thickness, where the wall is thinner |
| Covering boxes | Over what is left of a thin sheet, turned to lie along it | By the sheet's own unevenness |

In an entry the inside boxes come first, then the plates and covering boxes. Only those two can carry a yaw.

### What is in it

| | |
|---|---|
| Kinds exported and run | 1,245 |
| Kinds with boxes in the file | 878 |
| Boxes | 13,909 (2,332 turned); 1 to 48 a kind, 16 on average |
| A kind's largest side | 0.8 m to 195 m, median 7 m |
| Solid taken from a collision mesh | 106 kinds |
| Solid taken from the LOD0 shell | 772 kinds |
| Fill: as modelled / whole / by the outline | 611 / 48 / 219 kinds |
| Game build | 26251122 |

What the other 367 kinds are:

| Left out | Kinds |
|---|---|
| Under 0.8 m across | 88 |
| By name: wire, banners, posters, spikes and the like (a round passes) | 37 |
| Over 300 m across (a backdrop) | 6 |
| Boxes reach less than 0.5 m above the root | 131 |
| No box fits inside (too thin) | 46 |
| Left out by eye | 42 |
| Enemy structures | 17 |

Also missing: a set of intact city towers seen in game that was not among the exports.

## Making the boxes

### The exports

    filediver -T unit --model-format glb --model-include-lods -i "<glob>" -o exports

- `--model-include-lods` brings the collision meshes along.
- The exports are large: 200 units are about 3.7 GB. The glob rules are in
  [ONBOARDING.md](ONBOARDING.md#filediver-commands).

### The run

    python3 tools/scenery_boxes.py exports --cache cache --json boxes.json --lua boxes.lua

- `--cache` keeps each kind's result, so a second run does only new files and the exports can be deleted.
  `--cached` then counts every kind in the cache.
- `--lua` writes the same data as a Lua table, keyed and laid out as the JSON.
- 200 units take about 3 minutes; a second run from the cache takes seconds.

### How a kind's solid is found

1. **The mesh goes into the game's frame.** glTF is y-up: game x = x, game y = -z, game z = y.
2. **The LODs are told apart by their bounding boxes.** Groups whose boxes match within 10 % are one thing at
   several LODs; the one with the most vertices is LOD0.
3. **The collision meshes are the solid**, where the unit has them (material `m_collision`; the navigation mesh
   is not one). A convex piece is taken as its hull. A piece that wraps nine tenths of all the others is a coarse
   hull round them and is dropped.
4. **A collision mesh that is not the whole thing is not used.** Seen from the two sides and from above, it must
   stand behind 80 % of the LOD0 mesh's outline with no more than 25 % of its own outline outside. Whole ones
   measure 87–100 %, partial ones (a piece of a ruined wall, the foot of a pillar) 23–63 %.
5. **Otherwise the LOD0 shell is the solid**, filled.
6. **Voxels:** the pitch is the kind's largest side over 100, kept between 0.1 and 1 m, and no more than an eighth
   of its thinnest side (down to 0.04 m).

### The three fills

A shell has no inside until it is closed, and how to close it depends on the thing:

| Fill | What counts as solid | Right for |
|---|---|---|
| As modelled | The enclosed space; a bottomless shell is closed downward only where it is closed at the sides | Rocks, walls, anything with open space under it that a round passes: an arch, a walkway on stilts, an overhang |
| Whole | Everything under the shell, down to its lowest point | Things open as modelled and solid in the game: a wall of roots, a debris cover |
| By the outline | What lies behind the thing's outline from both sides and from above at once | Shells that enclose nothing: a ruined building, a car |

The tool makes each fill where it differs enough from the others. Which one a kind gets is a choice by eye.

### The review page and the choices file

    python3 tools/scenery_boxes.py exports --cache cache --review page.html

- The page shows every kind as a card: its side view with a 1.8 m figure, its top view, the boxes drawn over the
  mesh (inside boxes blue; plates and covering boxes green).
- A click leaves a kind out. A switch on the card picks the fill. A slider sets the height rule: kinds whose boxes
  reach less than that above the root are left out.
- Each card says how much of the thing's outline has a box in front of it ("outline covered") and how much of the
  boxes' outline has nothing behind it ("spill").
- The list at the bottom of the page is the choices file:

      reach 0.5              # the height rule, metres
      956d43fe3e09760a       # a kind left out (a hash or a name)
      +0123456789abcdef      # kept although under the height rule
      =0123456789abcdef      # the whole fill
      ~0123456789abcdef      # the outline fill

- `--choices choices.txt` on the next run writes the boxes by it.
- `--reviewed file` lists the hashes already been through; every other kind is marked new on the page, and the
  page opens on those. `--add-reviewed` adds a run's kinds to the file.
- The picks made on the page are kept in the browser, for that page's file.

## In the game

### Listing the units

- `World.units(world)` gives every unit: 5,000–11,000 on a mission map.
- `Unit.debug_name(u)` carries the kind as `#ID[<16 hex>]`: the key into the data.
- `Unit.world_position(u, 1)` is the unit's root: the origin of the boxes' frame.
- On a small arctic map 2,147 of 4,280 listed units were of 143 kinds in the data; on a four-player city map
  5,377 units of 188 kinds.
- The calls that end the game when made on the wrong unit are in
  [ONBOARDING.md](ONBOARDING.md#what-ends-the-game): `Unit.box` on a dying unit and, as a precaution, any call
  on a unit in its first seconds.

### A unit's pose

- `Unit.box(u)` returns a pose (a `Matrix4x4`) and the box's half sizes. `chef.unit_alive(u)` in the same frame,
  before it.
- The unit's axes in the world are `Matrix4x4.x(pose)`, `Matrix4x4.y(pose)` and `Matrix4x4.z(pose)`. Where those
  are not to be had, `Unit.world_rotation(u, 1)` with `Quaternion.right`, `Quaternion.forward` and `Quaternion.up`
  gives the same three.
- The pose's translation is the engine box's middle, not the unit's root. The boxes are placed from the root.
- The engine's box is the mesh's box plus 0.00–0.06 m a side: a margin, not a scale. On a thin axis the ratio of
  the two reads as a scale of 1.1 and is not one.
- Scenery is not scaled as a rule: over 55 poses of 23 kinds every axis was 1.00 long.
- A unit of scenery does not move, so its pose is asked once and kept until the world changes.

### The test

`lua/scenery.lua` holds it, with no engine calls:

    local S = scenery                              -- the table lua/scenery.lua returns
    local kind = BOXES[hash]                       -- { box = {...}, boxes = {...} } from the data
    local pose = { x = rx, y = ry, z = rz,         -- the unit's root in the world
                   R = { { xx, xy, xz }, { yx, yy, yz }, { zx, zy, zz } } }   -- its axes, unit length
    local t, i = S.segment(kind, pose, x1, y1, z1, x2, y2, z2)
    if t then hx, hy, hz = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, z1 + (z2 - z1) * t end

1. The segment's two ends go into the unit's frame: the offset from the root, dotted with each axis.
2. The segment is held against one box round all of the kind's boxes (`S.envelope`). Most segments near a unit
   miss it, and the kind's 16 boxes are never looked at.
3. Each box is a slab test on three axes. For a turned box the segment is first turned about the box's middle by
   minus its yaw.
4. The smallest entry `t` over the boxes is the hit. A segment that starts inside a box gets no hit from that box.

An arc is a row of segments, tested in order until one hits.

### Finding the units near a line

- A grid of 16 m cells, each unit listed in every cell its boxes' world rectangle covers (`S.world_box`), keeps a
  segment to the units in the cells it crosses.
- A long thing has to be listed by its rectangle, not by a circle round its middle: an 86 m curb is otherwise
  "near" everything within 43 m.
- A unit destroyed since the listing is caught by `chef.unit_alive` on the unit a segment hit.
- A line that grazes a box's edge flickers between the box and the ground behind it as the aim sways. Growing the
  box that was hit last frame by 0.3 m steadies it.

### Cost

- Plain Lua, no JIT: about 0.1 ms a frame for one line against the boxes of 1,000–1,300 units.
- The distance checks are the bulk of it, not the box tests.
- The data as a Lua table is 700 KB of source, loads in about 20 ms and takes about 3 MB of Lua memory.
- `Unit.box` is an engine call per unit: spread over frames (a few a frame), asked only for units a line comes
  near.
