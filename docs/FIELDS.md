# Network game object fields

Game build 26088801; build 26251122 moved nothing listed here.

- Names in **bold** are a field's real name: a string whose 32-bit hash (`murmur64(name) >> 32`) is the field's id,
  usable as it stands in `game_object_field`.
- Other fields are given by id, with a description. Any string with the same hash works as the name.
- "Guess" marks a meaning that fits what was seen but is not confirmed.
- Numbers (#) are the field's place in the type's own order, as `Network.object_info` and
  `game_object_field_batched` give it.

## How the calls answer

- **`game_object_field_batched`** returns a flat list in the type's field order. For a type with more than 63
  fields (the Helldiver has 72, the mechs 76) the first 63 come as one list in place 64, then 65 on; field 64's
  own value isn't given.
- **`Network.object_info`'s `type` per field:** 0 true / false, 1 whole number (min, max, bits), 2 decimal (min,
  max, bits, tolerance), 3 a Vector3, 4 a rotation (Vector4), 9 a 64-bit id (a peer id, a hash), 10 a list,
  11 unknown (field 64).
- **A decimal's tolerance is a dead band:** the game sends a new value only once the real one has moved by that
  much from the last value sent.
- **"No object"** in a field that holds an object id is 32767.

## The Helldiver (type 5d9752f9, 72 fields)

| # | Field | Values |
|---|---|---|
| 1 | 98b4aaf0 | a list of one 64-bit id, the same each life (on a weapon this field is the attachments) |
| 2 | cd889dbc | a state number: 80 in the drop pod, 82 standing, 74 / 88 / 90 moving, 86 with the map open, 72 in a vehicle seat; +32 for a moment at a scope zoom press (guess: a locomotion state id) |
| 3 | 6ff0e58a | three 64-bit bit sets of action flags, read as hex strings. Word 1 bit 48: first-person view. Word 1 bit 23: hover-pack flight. Word 2 bit 18: aiming down the sights (a toggled aim counts, a knock-out ends it). Word 2 bit 22: the weapon settings wheel open. The rest change with sprint, crouch, prone, throw, emote, vehicle, map, zoom |
| 4 | 5faee212 | 0 / 1 / 2 with the stance |
| 5 | **stamina** | 1 full; falls about 0.045 a second while sprinting |
| 6 | e3186939 | a rotation (changes all the time) |
| 7 | **look_at_position** | where the view's ray meets the world, following the view at once; 998 m out when it meets the sky |
| 8 | bdc1cb8a | the crosshair's hit point that the rounds fly to, smoothed (about 0.25 s behind the view) |
| 9 | **map_marker_position** | your map pin; your own position while none is placed. Whether z is the terrain's height is open (0 has been seen, and 20.8 / 23.2) |
| 10 | **map_marker_type** | 0 none, 7 a placed pin |
| 11 | **map_marker_goid** | the pin's object (32767 none) |
| 12 | **spawn_time** | 5 or 4 when you land, then -1 |
| 13, 14 | 913af9a2, 0c09236b | two objects on you (types 67e52a93 and 4b3aa0ac, 15 fields each; nothing seen to change) |
| 15 | **terminal_interact** | a terminal object (32767 none) |
| 16 | **player_goid** | your player object |
| 17 | **ragdoll_position** | |
| 18 | **network_mask** | 0 in a vehicle, 1 on foot, 13 for a moment getting out |
| 20, 61 | a09ccd0a, 4441caf8 | true on foot, false in a vehicle or a mech |
| 23 | **position** | |
| 25 | 20efbed4 | the object you're next to or looking at (a backpack on the ground, a pin), or your vehicle. An emplacement's seat while you sit (the HMG: its seat object; the AT emplacement: the gun itself). Not the FRV's turret |
| 26, 27 | **motion_mode**, **motion_enabled** | motion_enabled is false in the pod, in a vehicle and dead |
| 32 | **is_falling** | |
| 34 | 268ac291 | counts up by one at each vehicle exit and each emote (guess: an action counter) |
| 35 | **death_damage_type** | 10 from the start; one death did not change it |
| 38 | **state** | 0 alive, 2 dead |
| 39 | cad5b537 | 0, then 699050 after a reinforcement landed |
| 40 | **max_health** | 125 |
| 42 | **health** | 125 full, 0 dead; a stim brings 29 to 125 within about a second |
| 43 | **zone_health** | -1 (on a mech: per-part damage) |
| 45 | 8fd2d63e | -1, then 4095 after the first damage |
| 46 | **input** | 0 |
| 47 | **active_emote** | -1 none, an emote's hash while emoting |
| 48 | 95c46304 | the weapon's stance: 0 lowered; 3 raised (firing from the hip, overheated, a charge); 4 around a shot while aimed (for the shot's or charge's length only, not for as long as you aim); 1 around a throw. Not the stratagem input |
| 49 | **enabled_mask** | 5 alive, 7 while emoting, 0 dead |
| 56 | **num_throwables** | grenades |
| 57 | **num_stims** | stims |
| 58 | **stance** | 0 standing, 1 crouched, 2 prone |
| 59 | edbf0131 | -3.14 to 3.14: the way you face, in radians |
| 60 | 2932144a | 0 still, 1 walking, 1.2 sprinting, 0.65 crouched (guess: a speed step) |
| 67–69 | e4d00fe1, dae681f4, 6d976352 | 1, 100, 100 (never seen to change) |
| 70 | a33df340 | 0, 1, 2 at times; does not follow the stims; unknown |

## The player object (type 803159b3, 36 fields)

| # | Field | Values |
|---|---|---|
| 2 | 0f27c68e | the avatar: your Helldiver's object; 32767 between lives |
| 3 | cd889dbc | 257 alive, 256 dead, 0 after the mission |
| 4 | **loadout_state** | |
| 5 | **index** | |
| 10–14 | **body_type**, **helmet_set**, **cape_set**, **armor_set**, **booster** | |
| 16 | **voice_pack_set** | |
| 19 | **customization_seed** | |
| 21 | **player_title_index** | |
| 26 | 1733b7a0 | a list of six 32-bit ids (guess: the loadout) |
| 36 | **avatar_flags** | 5, then 7 after the first reinforcement |

Nothing on this type changes when a stratagem is called or a stim used: it holds no stratagem cooldowns.

## Weapons (331 types)

Counted here as weapons: the 331 types that declare rounds_remaining, the heat field or the two-ammo fields. They
include guns nobody carries (turrets, emplacements, vehicles). Not every type declares every field below; the
count is how many of the 331 do.

| Field | Types | Values |
|---|---|---|
| **fire_mode** (49c250a6) | 331 | `fire_mode % 8`: 1 auto, 2 semi, 3 burst, 4 volley, 5 safe, 6 unsafe, 7 total. Bit 8 set: the underbarrel is selected |
| 31f86165 | 331 | option bits, two bits per setting. At 4: the ammo type or guidance. At 16: the scope's zoom step, `(value / 16) % 4`, 0 the lowest. At 64: set on every weapon seen. At 256: the C4's deploy / detonate (80 / 336). At 4096: the fire mode |
| **is_firing** (3132608f) | 331 | true while the weapon fires |
| **magazines_remaining** (ec64918b) | 306 | on a heat weapon: its heat sinks |
| **spread_seed** (7030c54e) | 304 | a new random number each reload |
| **chamber_empty** (4a893e74) | 301 | |
| **rounds_remaining** (d7a5d63e) | 276 | |
| 6f3ab277 | 274 | the aim's pitch of a weapon that aims by itself (-0.5 to 1.58 radians, 7 bits). 0 on every weapon a Helldiver holds; changes all the time on SEAF soldiers' rifles, turrets, a Guard Dog's gun, tanks, emplacements. A support weapon taken from its hellpod has kept a constant 0.012 (one quantum off 0) |
| 4cbcc2a2 | 274 | the rate of fire setting, in rounds a minute; on a heat weapon it is not a rate of fire |
| cd889dbc | 247 | the reload stage. A tactical reload: 0, 1, 0. From empty: 0, 4, 5, 7, 0 (the Liberator) |
| **original_owner** (3ccffa7f) | 180 | |
| **position**, **rotation**, **is_moving** | 173, 149, 143 | (0, 0, 0) while carried; a dropped weapon gets a position and is_moving true |
| 98b4aaf0 | 172 | the attachments: one 64-bit id per customization slot (below) |
| c20428c6, 6d1d5cfb | 167 | one-entry lists: {12} / {1}; the Railgun {10} / {1.1}. Not the scope zoom |
| **underbarrel_goid** (67526982) | 166 | |
| 31182caf | 166 | bits that empty over the last 4 rounds of a magazine |
| **enabled_mask** (788b9753) | 121 | a multiple of 4 on your body, 1 in a hellpod, 2 dropped. A weapon the map placed reads 0 while it lies |
| c3a3f66c | 37 | the pickup link: an object id while a called-down weapon lies on the ground, none in a hand. A weapon the map placed (in a crate or a crashed flier) keeps its link in your hand |
| a5023836 | 30 | the heat. Tolerance 15.62, so falls come in steps of 15.7 and a shot of less than the band can hide inside it. The last value before an overheat is a lower bound of the overheat point (the Talon: 84.8 for 100). The Talon's rises read about 12 a shot |
| **is_overheated** (f6275c53), **is_charging** (88b7cf6d) | 30 | |
| 04ec5b95, e525fa9c, a74ef0d5 | 25 | two loaded ammo counts and which one is selected (0 / 1). The Halt: flechette / stun. On a shotgun with two tubes of one ammo the selected field is the tube in use and moves by itself |
| 9a34c336 | 25 | spare rounds (the reserve), on the same 25 types |
| f8d23bd2 | 1 | laser guidance on / off (the Commando) |

### Attachments (98b4aaf0)

- One 64-bit id per customization slot the weapon has: the Breaker 6, the Sweeper 4, a bare Verdict 1.
- An attachment has one id on every weapon, and the ids survive a restart.
- On the Breaker, place 2 is the optic, 4 the muzzle, 5 the magazine. The first id is the piece itself or its paint.
- Known ids: the reflex sight fa994cd576b2f912, the full choke 75713afac474d9c4, the Breaker's short / extended
  magazine 9992e382b80955cc / 68b8d040421e8a49, its 1.5x tube red dot 490c9e167b3aaf8c.
- The ids are not the murmur64 of any known name or path.
- Not every weapon type has the field. Reading it from one that doesn't (the HMG emplacement's gun, fa6ddf17) ends
  the game.

### Weapon types by id

| Type | Weapon | Option at 4 (0 / 1) |
|---|---|---|
| c920c2d3 | the Warrant | guided / unguided |
| fd585726 | the missile pistol | guided / unguided |
| 7bfb2e06 | the Autocannon | APHET / flak |
| b2bfd847 | the Recoilless Rifle | HEAT / HE |
| 8a3c6fee | the Airburst Rocket Launcher | flak / cluster |
| 656d507b | the WASP | burst / artillery |
| 6b2c3bed | the C4 | at 256: deploy / detonate |
| 9c06f074 | the Halt | (two ammo counts: flechette / stun) |
| bd5f17dd | the two-tube pump shotgun (`pump_shotgun_dragon`) | (two tubes: 7 + 8 and one chambered) |
| cd0e4b4a | the Stoker | |
| fa6ddf17 | the HMG emplacement's gun (46 fields) | |

## Backpacks

- **Ammo backpacks** (30 types) have **remaining** (69889752).
- **enabled_mask** on a backpack: 0 worn, 1 in the pod, 2 dropped. A backpack the map placed also reads 0 until
  someone has used it.
- **Jump pack 3a9a3ab0** (16 fields): faaa8598 goes true about 1.8 s after the jump press; the pack is
  ready again 15 s after the press.
- **Hover pack efb4a22e** (the same 16 fields as the jump pack): one flag, f8d23bd2, true in flight and for about
  a second past touchdown. There is no fuel field. Fitted to timed flights: the tank is 8.1 s of flag-on time, a
  drop down a slope adds a little, and the refill takes 1.15 x the flag-on time, counted from touchdown.
- **Warp pack c89adf0c** (12 fields): **heat** (35ff0b52).
- **Shield backpack b0b9f710** (22 fields): **charge** (1ad6d70f), 150 full, sent only when it has moved by its
  tolerance of 39, so a break can leave it reading 15 and a refill 133.7. 6fee6b03 is true while broken, 24cf7e78
  true while regenerating, and **active** (b19ad128) goes false when it breaks.
- **Directional shield d3e4682e** (20 fields; max_health 400; a raised / lowered flag 7f7d11f7) and **ballistic
  shield 2b651283** (26 fields; max_health 1000; state 0, 2 stowed): no health field. Their damage isn't networked.
