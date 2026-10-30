# Dead Space 2008 Randomizer: Console DLC

An add-on for the [Dead Space 2008 Randomizer](https://github.com/RichardHafer/DS2008-Randomizer)
that brings the console DLC suits and weapons of the original Dead Space to the
PC version, free and in every chapter. The PC game still carries the console
DLC framework; this plugin fills it with the packs converted to PC data.

It is a separate plugin and needs the randomizer next to it. The randomizer
finds it on start, calls it from its own hooks and lists its options in the
settings window. Without this add-on the randomizer runs as usual.

## What you get

**Suits**: Scorpion, Obsidian, Elite, Unitology (Tank) and Astronaut, each with
its pack weapons, plus the Military weapons.

**Weapon packs**: Heavy Damage, Hot Rod, Pedestrian, Speed Kills and Big Gun.

**Level suits in DLC style**: levels 1 to 6 of the Scorpion, Obsidian,
Unitology, Elite and Astronaut looks, levels 1 to 5 of the Military look and a
level 1 Mining Rig. Each carries the stats of the level suit it is built on.

Everything appears in the store for 0 credits. The game's suit table holds 30
suits; the plugin raises it to 64 (`SuitSlots`) so the extra suits fit.

**Suit paths** (off by default, `SuitPaths=1`): a seed may play a whole run in
one DLC style. Level 1 is worn from New Game, levels 2 to 6 take the store
places, prices and unlocks of the retail suits, and the style's weapons
replace the retail weapons of their type. After the run is finished (New
Game+) every DLC item is back in the store for free.

## Install

Install the [randomizer](https://github.com/RichardHafer/DS2008-Randomizer/releases/latest)
first. Then extract the add-on's zip into the game folder, keeping the folders:

```text
Dead Space/
|-- plugins/
|   |-- DeadSpace2008Randomizer.asi            (the randomizer)
|   `-- DeadSpace2008Randomizer_ConsoleDLC.asi (this add-on)
`-- ds1_randomizer_assets/
    `-- dlc/                                   (the converted packs)
```

Start the game. `DeadSpace2008Randomizer.log` has an `extension: ... attached`
line when the add-on is in use, and the settings window's Console DLC page is
no longer greyed out.

Settings go into `DeadSpace2008Randomizer.ini`, section `[DeadSpace2008Randomizer]`:

| Key | Default | |
|---|---|---|
| `ConsoleDlc` | 1 | The DLC suits and weapons in the store. |
| `SuitSlots` | 64 | Size of the suit table (30 in the retail game). |
| `SuitPaths` | 0 | Seeded runs in one DLC style. |
| `SuitPath_<name>` | 1 | Which styles a suit path may pick. |
| `SuitPathWeaponPacks` | 1 | A suit path may add a weapon-only pack for the weapon types its style lacks. |

To uninstall, delete `plugins\DeadSpace2008Randomizer_ConsoleDLC.asi` and the
`ds1_randomizer_assets\dlc` folder. Keep it installed while you play a save
that holds DLC items.

## How it works

The retail executable still has the console DLC manager (at `0x00F64A68`) with
its store lists, uniform slots and weapon entries. On the console a DLC pack
registered its archives there; on PC the manager simply stays empty. The plugin
fills its entries once `global_assets` has loaded, and the game does the rest
itself: it loads the store archives, shows the items, equips the suits and
builds the weapons.

The archives are converted offline from the console packs:

- Scene data is converted from big-endian, with each property's width taken
  from the PC class tables.
- Models, rigs, banks and effects the PC already ships under the same name are
  taken from the PC data.
- DLC-only textures keep their pixels (both platforms use DXT) with a PC header.
- DLC meshes are converted from the console geometry.
- The level suits in DLC style are repainted from the level suits and the
  pack's paint.

The randomizer's extension interface is `src/ds2008_extension.h`. The add-on
never hooks a function the randomizer hooks; it asks the host for stream state,
verified hook sites, the store hooks and the seed.

## Building

Visual Studio 2022 with the x86 toolchain, then `build.bat`. safetyhook needs
`std::expected`, hence `/std:c++latest`.

The `src/*_generated.inc` tables come from the pack conversion and are
committed, so the plugin builds without the console data.

The converted archives are game data and are not part of the repository. To
build them yourself you need the console packs (`DLCs/extracted/<pack>`), the
PC game, Python 3 with numpy and Pillow, and Gibbed's Visceral tools
(`Gibbed.Visceral.StrUnpack.exe` and `StrPack.exe` in `tools/gibbed`, or set
`GIBBED_VISCERAL_DIR`):

```bat
set DEAD_SPACE_DIR=C:\Program Files (x86)\Steam\steamapps\common\Dead Space
python -I tools\ds1_dlc_build.py
python -I tools\make_release.py assets_dlc --version 1.0.0
```

`make_release.py` packs only the archives the plugin's table lists.

## Credits

- [safetyhook](https://github.com/cursey/safetyhook) and [Zydis](https://github.com/zyantific/zydis) for hooking
- Gibbed for the Visceral archive tools

## Licence

MIT, see `LICENSE`. Not affiliated with EA or Visceral Games. The DLC content
belongs to EA.
