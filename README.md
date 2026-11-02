<p align="center">
  <img src="assets/DS2008ConsoleDLC_Banner.png" alt="Dead Space 2008 Randomizer: Console DLC" width="70%">
</p>

# Dead Space 2008 Randomizer: Console DLC

Brings the console DLC suits and weapons of the original Dead Space (2008) to
the PC version, on its own or as an add-on for the
[Dead Space 2008 Randomizer](https://github.com/RichardHafer/DS2008-Randomizer).
Everything sits in the store for free, in every chapter, with the stats the
packs had on console.

The PC game still carries the console DLC framework, it just never gets any
content. This plugin fills it with the packs converted to PC data, and the
game does the rest itself: store, equipping, weapon models, effects and sounds.

On its own you get the plain game plus the DLC. With the randomizer
installed, the randomizer picks it up on start, drives it from its own hooks
and shows its options in the settings window, and the suit paths below become
available.

## What it does

**Console packs**

| | |
|---|---|
| Scorpion | Suit, Force Gun, Line Gun, Plasma Cutter, and from the August 2008 Xbox prototype Contact Beam, Flamethrower, Pulse Rifle, Ripper |
| Obsidian | Suit, Line Gun, Plasma Cutter, Pulse Rifle |
| Elite | Suit, Line Gun, Plasma Cutter, Pulse Rifle (the Xbox pack) |
| Unitology (Tank) | Suit, Flamethrower, Force Gun, Line Gun, and from the August 2008 Xbox prototype Contact Beam, Plasma Cutter, Pulse Rifle, Ripper |
| Astronaut | Suit, Plasma Cutter, Pulse Rifle, Ripper |
| Military | Contact Beam, Flamethrower, Force Gun, Line Gun, Plasma Cutter, Pulse Rifle, Ripper |
| Weapon packs | Heavy Damage, Hot Rod, Pedestrian, Speed Kills, Big Gun |

The prototype weapons were never sold. Their skins are complete; their stats get the raise the retail pack
gave its own weapons (Military damage for the Tank set, faster handling for the Scorpion set).

**Level suits in DLC style**

| | |
|---|---|
| Scorpion, Obsidian, Unitology, Elite, Astronaut | Levels 1 to 6 in each look |
| Military | Levels 1 to 5 |
| Mining Rig | Level 1 |

Each one carries the inventory and armour of the level suit it is built on, so
a Scorpion level 2 plays like the regular level 2 suit. The Scorpion levels
carry the scorpion of the retail helmet on a clean spot of their own helmets.

**RIG colours, on in the shipped settings**

| | |
|---|---|
| `RigColours` | The RIG health and stasis bars of the DLC and DLC style suits in a colour per style (Scorpion gold, Obsidian blue, Unitology blue violet, Elite visor green, Astronaut white, Military dark blue). The first start after a change writes recoloured copies of those suits. The game's own level suits keep their teal. |

**Engine limits**

| | |
|---|---|
| Suit table | The game holds 30 suits. The plugin raises the table to 64 (`SuitSlots`) so all of the above fit. |

**With the randomizer only, on in the shipped settings**

| | |
|---|---|
| `SuitPaths` | A seed may play a whole run in one DLC style. Level 1 is worn from New Game, levels 2 to 6 take the store places, prices and unlocks of the retail suits, and the style's weapons replace the retail weapons of their type. `SuitPathWeaponPacks` may add a weapon-only pack for the types left. Once the run is finished (New Game+) every DLC item is back in the store for free. |

**On its own** the add-on also raises the game's sound bank table from 35 to
96 (`SoundBankSlots`), since the DLC weapons bring their own banks. With the
randomizer installed, the randomizer does that.

Every patch site is checked against the Steam bytes before it is placed, and
the log says which ones went in.

## Install

### Windows

**[Download the latest release](https://github.com/RichardHafer/DS2008-ConsoleDLC/releases/latest)**

Close the game and extract the archive into the game folder (Steam:
right-click Dead Space > Manage > Browse local files, the folder with
`Dead Space.exe`). The installed files should look like this:

```text
Dead Space/
|-- winmm.dll                                   (Ultimate ASI Loader)
|-- DeadSpace2008Randomizer_ConsoleDLC.ini      (settings when playing without the randomizer)
|-- plugins/
|   `-- DeadSpace2008Randomizer_ConsoleDLC.asi
`-- ds1_randomizer_assets/
    `-- dlc/
        `-- *.str                               (the converted packs)
```

If the folder already has a `winmm.dll` from the randomizer or another mod,
keep that one; it is the same loader.

**Without the randomizer** the add-on writes
`DeadSpace2008Randomizer_ConsoleDLC.log` into the game folder and reads
`DeadSpace2008Randomizer_ConsoleDLC.ini`:

| Key | Default | |
|---|---|---|
| `ConsoleDlc` | 1 | The DLC suits and weapons in the store. |
| `SuitSlots` | 64 | Size of the suit table (30 in the original game). |
| `SoundBankSlots` | 96 | Loaded sound banks (35 in the original game). |
| `RigColours` | 1 | Experimental: the RIG bars of the DLC and DLC style suits in a colour per style. The first start after a change writes recoloured copies (`<suit>_rig.str`). |
| `RigColour_<style>` | see INI | `R,G,B` (0 to 255) or `off` for Scorpion, Obsidian, Unitology, Elite, Astronaut and Military. Red and yellow at low health stay. |

**With the [randomizer](https://github.com/RichardHafer/DS2008-Randomizer/releases/latest)**
(1.0.2 or later) installed as well, the add-on's own INI and log are not used.
`DeadSpace2008Randomizer.log` has an `extension: ... attached` line, the
Console DLC page of the settings window is no longer greyed out, and the keys
go into `DeadSpace2008Randomizer.ini`:

| Key | Default | |
|---|---|---|
| `ConsoleDlc` | 1 | The DLC suits and weapons in the store. |
| `SuitSlots` | 64 | Size of the suit table. |
| `SuitPaths` | 1 | Seeded runs in one DLC style. |
| `SuitPath_<name>` | 1 | Which styles a suit path may pick. |
| `SuitPathWeaponPacks` | 1 | A suit path may add a weapon-only pack. |
| `RigColours` | 1 | Experimental: the RIG bars of the DLC and DLC style suits in a colour per style. The first start after a change writes recoloured copies (`<suit>_rig.str`). |
| `RigColour_<style>` | see INI | `R,G,B` (0 to 255) or `off` for Scorpion, Obsidian, Unitology, Elite, Astronaut and Military. Red and yellow at low health stay. |

To uninstall, see [Uninstall and saves](#uninstall-and-saves) first.

### Compatibility

- Made for the Steam release of Dead Space (1.0.0.222). On another build every
  patch site whose bytes differ is left alone and the log names it.
- Randomizer: 1.0.2 or later (see [Versions](#versions)), or none at all.
- Works next to DeadSpaceFixes. DeadSpaceFixes and the Ishimura Stability Patch
  both ship an `xinput1_3.dll`, so only one of those two can be installed; the
  add-on does not use that file. The Ishimura Stability Patch was not tested
  with the add-on.
- Do not run a 4GB (large address) patcher on `Dead Space.exe`: the Steam build
  refuses a changed executable with "Application load error 3:0000065432". The
  add-on does not need it. Mods that raise the limit without touching the exe,
  such as DeadSpace2008-4GB-Mod (a `dsound.dll` proxy), were not tested with it.

### Troubleshooting

Which log to look at:

- Without the randomizer: `DeadSpace2008Randomizer_ConsoleDLC.log` in the game
  folder (`.prev.log` is the run before).
- With the randomizer: `DeadSpace2008Randomizer.log`. The add-on's own log then
  only shows up when the randomizer never attached it.

A working start has these lines:

| Line | Meaning |
|---|---|
| `extension: Dead Space 2008 Randomizer Console DLC 1.0.1 attached` | The randomizer found the add-on (randomizer log). |
| `Dead Space 2008 Randomizer Console DLC 1.0.1, standalone: ...` | Running without the randomizer (own log). |
| `suit slots: table extended from 30 to 64 entries` | The larger suit table is in. |
| `console DLC: 72 of 72 line(s) installed in ...` | Every pack archive was found. |
| `console DLC: entry ...` | One line per suit or weapon registered with the game. |
| `sound bank slots: table extended from 35 to 96 banks` | Without the randomizer; with it, the randomizer logs its own line. |

When something is wrong:

| Line | What to do |
|---|---|
| `... did not attach this plugin within 15 s: no DLC items this session` | Update the randomizer to 1.0.2 or later, or restart the game. |
| `console DLC: N of 72 line(s) installed` with N below 72 | Files are missing in `ds1_randomizer_assets\dlc`; extract the zip again. |
| `suit slots: NOT extended ...` | DLC suits past the 30th slot are missing. Send the log. |
| `hook ... REFUSED` | Not the Steam build, or another mod changed that spot. Send the log. |

Send the log with a short description of what happened.

### Uninstall and saves

A save remembers the suit Isaac wears and the items he carries. The DLC suits
and weapons only exist while the add-on runs:

- A save that **wears a DLC suit** does not load without the add-on. The game
  crashes while loading (at `0x005261A6`, the player's suit data is missing).
  This was seen in testing when randomizer 1.0.0 missed the add-on at start.
- A save that wears a regular suit but **holds DLC weapons or items** was not
  tested without the add-on. Treat it the same way.
- `ConsoleDlc=0` leaves the DLC lines unregistered, so expect the same for
  those saves.
- A suit path run (`SuitPaths=1`) wears a DLC suit from New Game, so all of its
  saves need the add-on.
- Saves without any DLC item are not affected.

To remove the add-on safely:

1. Back up your saves: `Documents\Electronic Arts\Dead Space\ds_slot_NN.deadspacesaved`.
2. With the add-on still installed, load the playthrough, put on a regular suit
   at a store and save in a **new** slot.
3. Delete `plugins\DeadSpace2008Randomizer_ConsoleDLC.asi`, the folder
   `ds1_randomizer_assets\dlc` and `DeadSpace2008Randomizer_ConsoleDLC.ini`
   (and `winmm.dll` if no other mod uses it). With the randomizer, its
   `ConsoleDlc`, `SuitSlots` and `SuitPath*` keys may stay in its INI.
4. Load the new slot. If it loads and plays, you are done. If it crashes,
   reinstall the add-on: the older slots are untouched.

The simplest way is to keep the add-on until the playthrough is finished.

### Versions

| Console DLC | Randomizer | |
|---|---|---|
| 1.0.1 | 1.0.2 or later, or none | Extension interface 3. Randomizer 1.0.0 could miss the add-on at start; 1.0.1 lacks the 1.0.2 fixes. |

---

## How it works

Not required reading. This is here so the next person does not have to redo
the research.

### The DLC manager

The PC executable still has the console DLC manager (at `0x00F64A68`) with its
store lists, uniform slots and weapon entries. On console a pack registered
its archives there; on PC the manager simply stays empty. The plugin fills its
entries once `global_assets` has loaded, marks the store archives persistent
so a level change does not drop them, and lets the game load everything else
on demand, the same way it would for a console pack.

### Converting the packs

The archives are converted offline from the console packs:

- Scene data is converted from big-endian, with each property's width taken
  from the PC class tables (a byte property swapped as a word made every DLC
  shot bounce off).
- Models, rigs, banks and effects the PC already ships under the same name are
  taken from the PC data.
- DLC-only textures keep their pixels (both platforms use DXT) with a PC header.
- DLC meshes are converted from the console geometry.
- The level suits in DLC style are repainted from the level suits with the
  pack's paint, plates and decals.

### With and without the randomizer

On load the add-on looks for `DeadSpace2008Randomizer.asi` where the ASI loader
picks plugins up. If it is there, the add-on waits: the randomizer attaches
through the extension interface in `src/ds2008_extension.h`, calls it from its
own stream, store and poll hooks and hands it stream state, verified hook
sites and the seed. The add-on never hooks a function the randomizer hooks.

If it is not there, the add-on does that part itself (`src/dlc/standalone.inc`):
its own `StreamManager::Load` hook, poll thread, log and INI, the same retail
byte check before every hook, and the larger sound bank table. It checks that
the executable is the Steam build first and patches nothing otherwise. The
suit paths need the randomizer's store hooks and seed, so they stay off.

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
python -I tools\make_release.py assets_dlc --version 1.0.1
```

`make_release.py` packs only the archives the plugin's table lists. It also
needs the Ultimate ASI Loader's `winmm.dll` in `release/`, which is not part
of the repository.

## Credits

Created by [Richard Hafer](https://github.com/RichardHafer).

- [safetyhook](https://github.com/cursey/safetyhook) and [Zydis](https://github.com/zyantific/zydis) for hooking
- [Ultimate ASI Loader](https://github.com/ThirteenAG/Ultimate-ASI-Loader) by ThirteenAG for loading the plugin
- Gibbed for the Visceral archive tools
- Everyone who played test runs and sent logs

## Licence

MIT, see `LICENSE`. Not affiliated with EA or Visceral Games. The DLC content
belongs to EA.
