Dead Space 2008 Randomizer: Console DLC 1.0.1
Dead Space (2008), Steam version

WHAT IT DOES

The console DLC suits and weapons of the original Dead Space on PC, free in the
store and in every chapter:
- Scorpion, Obsidian, Elite, Unitology and Astronaut suits with their weapons,
  and the Military weapons
- the unreleased Scorpion and Unitology weapons of the August 2008 Xbox
  prototypes: all seven weapons in both styles
- Heavy Damage, Hot Rod, Pedestrian, Speed Kills and Big Gun weapon packs
- levels 1 to 6 of the suit styles (Military 1 to 5, Mining Rig 1) on the stats
  of the level suits
- optional RIG bar colours per suit style (RigColours in the INI, off by default)

It runs on its own, or together with the Dead Space 2008 Randomizer (1.0.2 or later).

INSTALL

1. Open the game folder: in Steam, right-click Dead Space > Manage > Browse local files.
   It is the folder that holds "Dead Space.exe".
2. Extract everything from this zip into that folder, keeping the folders:
     winmm.dll                                   (Ultimate ASI Loader, loads the plugin)
     plugins\DeadSpace2008Randomizer_ConsoleDLC.asi
     ds1_randomizer_assets\dlc\
     DeadSpace2008Randomizer_ConsoleDLC.ini      (settings without the randomizer)
3. If the folder already has a winmm.dll from the randomizer or another mod, keep
   that one; it is the same loader.
4. Start the game. The DLC items are in the store.

SETTINGS

Without the randomizer: DeadSpace2008Randomizer_ConsoleDLC.ini
  ConsoleDlc=1           DLC items in the store
  SuitSlots=64           suit table size (the game has 30)
  SoundBankSlots=96      loaded sound banks (the game has 35)

With the randomizer: the same keys in DeadSpace2008Randomizer.ini or its settings
window, plus SuitPaths=1 for runs played in one DLC style.

COMPATIBILITY

- Made for the Steam release (1.0.0.222). Patch sites that differ are skipped
  and named in the log.
- Randomizer 1.0.2 or later, or no randomizer at all.
- Works next to DeadSpaceFixes. DeadSpaceFixes and the Ishimura Stability Patch
  both ship xinput1_3.dll, so only one of those two can be installed.
- Do not run a 4GB patcher on Dead Space.exe: Steam refuses a changed exe
  ("Application load error 3:0000065432"). The add-on does not need it.

SAVES AND UNINSTALL

A save that wears a DLC suit does not load without the add-on (the game crashes
while loading). Saves that hold DLC weapons or items were not tested without
it; treat them the same. Saves without DLC items are not affected.

To remove it safely:
1. Back up Documents\Electronic Arts\Dead Space\ds_slot_NN.deadspacesaved.
2. With the add-on installed, load the game, put on a regular suit at a store
   and save in a NEW slot.
3. Delete plugins\DeadSpace2008Randomizer_ConsoleDLC.asi, the folder
   ds1_randomizer_assets\dlc and DeadSpace2008Randomizer_ConsoleDLC.ini (and
   winmm.dll if no other mod uses it).
4. Load the new slot. If it crashes, reinstall the add-on; older slots are
   untouched.

REPORTING A PROBLEM

Send DeadSpace2008Randomizer_ConsoleDLC.log from the game folder (or
DeadSpace2008Randomizer.log when the randomizer is installed) with a short
description. A working start logs "suit slots: table extended from 30 to 64
entries" and "console DLC: 72 of 72 line(s) installed"; with the randomizer
also "extension: Dead Space 2008 Randomizer Console DLC 1.0.1 attached".

VERSIONS

Console DLC 1.0.1 works alone or with randomizer 1.0.2 or later.

Not affiliated with EA or Visceral Games. The DLC content belongs to EA.
