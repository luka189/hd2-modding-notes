# After a game patch

What a Helldivers 2 update can move under a mod, and how to find out.

## Which build is running

| Patch | Engine string (`Application.build_identifier()`) | Steam build |
|---|---|---|
| 7.2.1 | `stingray:46659 e176252a3ac4eb5436b25e7cef665a8c71afa243` | 26088801 |
| 7.2.2 (2026-10-29) | `stingray:46805 437a3d445f9df7662b60086ac8ae3c65b5c95da6` | 26251122 |

The Steam build id is the `buildid` line of `steamapps/appmanifest_553850.acf`, and is on SteamDB.

## What can move

- **The network config:** types and fields can be added, removed or reordered. A field removed from a type a mod
  reads is a crash at the read (see "What ends the game" in [ONBOARDING.md](ONBOARDING.md)).
- **Atlas sprite rectangles:** they change whenever an atlas is repacked (see [ICONS.md](ICONS.md)).
- **Unit kinds** are hashes of content paths: they stay unless a unit's path changes, and new scenery arrives with
  new hashes.

7.2.1 to 7.2.2 changed nothing in the Helldiver's, the player's, the weapons' or the backpacks' fields.

## The network config

`filediver -T network_config -o extracted` writes `generated.network_config.main`.

The game object types are stored one after the other. Each record, little-endian:

| Part | Meaning |
|---|---|
| `u32` | the type's id |
| `u32`, `u32` | unknown |
| `u32` 0, `u32` 0 | |
| `u32` n | the number of fields |
| n × `u32` | each field's type index |
| `u32` n | the number of fields again |
| n × `u32` | each field's id, in the type's field order |
| `u32` | unknown |

Build 26251122 has 1,884 types, contiguous from 0x52b42 to 0xb6da2 in the file. The fields of the Helldiver and the
player that
hold another object's id have type index 108.

Comparing two builds' lists type by type shows new types, types gone, and fields added or removed on the types a
mod reads.

## Checking at run time

`Network.object_info(type_name)` lists the fields a type declares on the running build. A mod that compares the
list with the fields it reads can leave out a type that lost one, without an update.

## Names for new ids

- An id is the upper 32 bits of MurmurHash64A (seed 0) of the name.
- The engine compares only hashes, so any string with the same hash works as the name in `game_object_is_type`,
  `game_object_field` and `Network.object_info`.
- Brute force finds a stand-in for any id: the strings of `[a-z0-9_]` that start with a letter, up to 7
  characters, are about 78 billion, some 18 for every 32-bit id; most ids need 6 or 7 characters.
- For strings of up to 7 bytes MurmurHash64A reduces to its tail step, so the search is a few multiplications a
  string. A handful of new ids takes minutes on a multi-core machine; hundreds take hours.
- A real name is found the other way round: hash a guess and look for the id in the config.
