    // =====================================================================
    // Suit paths ([DeadSpace2008Randomizer] SuitPaths, SuitPath_<name>, SuitPathWeaponPacks).
    //
    // A seed may play one DLC style instead of the level suits: level 1 is
    // worn from New Game, levels 2 to 6 take the kiosk places of the retail
    // suits (prices and unlocks of the suit they replace), and the style's
    // own pack weapons take the places of the retail weapons of their type.
    // A second roll may add a weapon-only pack for the types left. During
    // such a run the DLC content registry stays out of the store; once a
    // playthrough is done (round [0x00E8ADDC] > 0, New Game+) or a save from
    // another run is loaded, every DLC item is in the store for free again.
    //
    // The choice must equal SuitPaths.For in the configurator's Catalog.cs.
    //
    // Store: the host hooks PlayerStore::AddItem and the gate for us
    // (storeAddItem, storeGate). A retail GUID is swapped for the DLC entry's
    // item GUID (manager entry +0x1C8, filled by its store archive); the item
    // gets the retail item's price (Item[36] at +0x61C, read at 0x005A16D7)
    // and, at the gate, the retail item's requirement.
    //
    // Saves (analysis/DeadSpace1_SuitPath_Research_2026-10-24.md): SaveSlot
    // 0x005F7AB0 and its callback 0x005F8590 (status 0 = written, slot at
    // [this+0x6A06C]) mark which run a slot holds; LoadSlot 0x005F7BD0 and the
    // apply 0x005F7E20 decide the mode of a loaded save. The marks live in
    // DeadSpace2008Randomizer_SuitPaths.ini with the save file's write time,
    // so a slot overwritten without this plugin no longer counts as the run.
    // =====================================================================
    struct SuitPathRow
    {
        const char* style;
        uint32_t levels[6];   // store numbers of levels 1..6, 0 = the level's own suit
        uint32_t weapons[8];
        unsigned weaponCount;
    };
    constexpr SuitPathRow kSuitPathRows[] = {
#include "suit_paths_generated.inc"
    };
    constexpr unsigned kSuitPathRowCount = sizeof(kSuitPathRows) / sizeof(kSuitPathRows[0]);

    struct WeaponPackRow
    {
        const char* pack;
        uint32_t weapons[8];
        unsigned weaponCount;
    };
    constexpr WeaponPackRow kWeaponPackRows[] = {
#include "weapon_packs_generated.inc"
    };
    constexpr unsigned kWeaponPackRowCount = sizeof(kWeaponPackRows) / sizeof(kWeaponPackRows[0]);

    constexpr const char* kSuitPathNames[] = {"Normal", "Scorpion", "Obsidian", "Elite", "Unitology", "Astronaut",
                                              "Military"};
    constexpr unsigned kSuitPathNameCount = sizeof(kSuitPathNames) / sizeof(kSuitPathNames[0]);
    static_assert(kSuitPathNameCount == kSuitPathRowCount + 1, "one generated row per named path");

    // The kiosk suits of levels 2..6 (global_assets kiosk list 58C8CB2B slots 7..11) and their prices.
    struct RetailItem
    {
        uint32_t guid[4];
        const char* name;
        int32_t price;   // the authored Item[36]; checked against the live object before a price is copied
    };
    constexpr RetailItem kRetailSuits[5] = {
        {{0x38C85887u, 0x3B1B7B7Du, 0x534F5254u, 0x36314E49u}, "suit level 2", 10000},
        {{0x36C853BEu, 0x3BC7742Du, 0x44455257u, 0x34303245u}, "suit level 3", 20000},
        {{0x38C854C2u, 0x787B299Du, 0x54544950u, 0x32303253u}, "suit level 4", 35000},
        {{0x30C87D7Eu, 0x9E6B76CDu, 0x4E484F4Au, 0x324E4F53u}, "suit level 5", 60000},
        {{0x38C87D7Bu, 0xA377C370u, 0x534F5254u, 0x36314E49u}, "suit level 6", 99000},
    };
    // The seven store weapons, by the type a DLC model archive names (pdlc_<pack>_<type>).
    struct RetailWeapon
    {
        const char* type;
        RetailItem item;
    };
    constexpr RetailWeapon kRetailWeapons[7] = {
        {"plasma_cutter", {{0x36C8BC4Fu, 0x07EADE56u, 0x44455257u, 0x34303245u}, "Plasma Cutter", 0}},
        {"line_gun", {{0x36C8BC49u, 0x5F163CD0u, 0x44455257u, 0x34303245u}, "Line Gun", 9000}},
        {"pulse_rifle", {{0x36C8BC4Fu, 0x67BB5F38u, 0x44455257u, 0x34303245u}, "Pulse Rifle", 7000}},
        {"flamethrower", {{0x36C8BC40u, 0x0C67B69Au, 0x44455257u, 0x34303245u}, "Flamethrower", 11000}},
        {"force_gun", {{0x36C8BC48u, 0xED477CBAu, 0x44455257u, 0x34303245u}, "Force Gun", 11000}},
        {"ripper", {{0x36C8BC4Fu, 0x6F9078E2u, 0x44455257u, 0x34303245u}, "Ripper", 8000}},
        {"contact_beam", {{0x36C8BC3Fu, 0xF55615C8u, 0x44455257u, 0x34303245u}, "Contact Beam", 9000}},
    };
    constexpr unsigned kRetailCount = 12;   // 5 suits, then 7 weapons

    const RetailItem& RetailAt(unsigned i)
    {
        return i < 5 ? kRetailSuits[i] : kRetailWeapons[i - 5].item;
    }

    constexpr uintptr_t kSaveSlot = 0x005F7AB0;         // thiscall(manager, slot, ...), ret 1Ch
    constexpr uintptr_t kSaveFinished = 0x005F8590;     // thiscall(manager + 0x1C, status, detail, name), ret 0Ch
    constexpr uintptr_t kLoadSlot = 0x005F7BD0;         // thiscall(manager, slot), ret 4
    constexpr uintptr_t kApplyLoadedSave = 0x005F7E20;  // thiscall(manager), before the world restore
    constexpr unsigned kSaveFinishedSlot = 0x6A06C;     // from the callback's this
    constexpr uintptr_t kRoundCounter = 0x00E8ADDC;     // 0 after New Game, +1 per completed playthrough
    constexpr unsigned kSaveSlots = 20;
    constexpr uintptr_t kCallerStoreList = 0x00596949;
    constexpr uintptr_t kCallerSchematic = 0x005A0A43;
    constexpr uintptr_t kCallerRegistry = 0x005A0F30;
    constexpr unsigned kItemPrice = 0x61C;
    // The kiosk's price getter (thiscall on the item, reads +0x61C at 0x005A16D7). At the first kiosk of a
    // session the DLC items have no object yet at AddItem or the gate, so they showed their own price 0
    // until a suit change rebuilt the list (2026-10-24). The price is set here, where the kiosk reads it.
    constexpr uintptr_t kItemPriceGetter = 0x005A16D0;
    constexpr unsigned kItemGuid = 0x20;

    enum class PathMode
    {
        Off,    // SuitPaths=0: the DLC as before, all free
        Run,    // the seed's path: swaps, the registry kept out
        Free,   // a finished playthrough or another run's save: every DLC item free
    };

    bool gSuitPaths = false;
    bool gSuitPathWeaponPacks = true;
    uint32_t gSuitPathSeed = 0;
    unsigned gSuitPath = 0;     // index into kSuitPathNames
    unsigned gWeaponPack = 0;   // 0 none, else kWeaponPackRows[n - 1]
    uint32_t gSuitPathPrint = 0;
    volatile LONG gPathMode = static_cast<LONG>(PathMode::Off);
    int gStartLine = -1;              // console DLC line of the level 1 suit, -1 for the retail suit
    int gRetailLine[kRetailCount];    // console DLC line that takes the retail item's place, -1 none
    // Items swapped in this session: the live object and the price it had before we wrote one.
    struct PricedObject
    {
        uintptr_t object;
        int32_t original;
        uint32_t vtable;
        uint32_t guid[4];
    };
    PricedObject gPriced[kRetailCount]{};
    char gSuitPathFile[MAX_PATH]{};
    char gSaveFolder[MAX_PATH]{};
    // Per save slot: the run print and the file time it was written with (poll thread fills the times).
    uint32_t gSlotPrint[kSaveSlots]{};
    uint64_t gSlotTime[kSaveSlots]{};
    volatile uint64_t gSlotFileTime[kSaveSlots]{};
    volatile LONG gSlotPending[kSaveSlots]{};   // 1: a save just finished, record it
    uint32_t gSlotPendingPrint[kSaveSlots]{};
    unsigned gSavingSlot = kSaveSlots, gLoadingSlot = kSaveSlots;
    safetyhook::MidHook gSaveSlotHook, gSaveFinishedHook, gLoadSlotHook, gApplyLoadedSaveHook;
    volatile LONG gPathSwaps = 0, gPathHidden = 0, gPathGates = 0, gPathPrices = 0, gPathNotReady = 0, gPathStale = 0;
    // The DLC item GUID each retail place was swapped to, for the price getter.
    uint32_t gSwappedItem[kRetailCount][4]{};
    // Objects ApplyPathPrice left alone. Only refusals are remembered: a reopened kiosk often builds its item at the
    // address of the last one, and remembering every object skipped that new one at price 0 (2026-10-24).
    uintptr_t gPriceRefused[kRetailCount]{};
    safetyhook::MidHook gPriceGetterHook;
    volatile LONG gGetterCalls = 0, gGetterPriced = 0, gGetterSeen = 0;

    uint32_t PathMix(uint32_t value, uint32_t salt)
    {
        value ^= salt;
        value ^= value >> 16;
        value *= 0x7FEB352Du;
        value ^= value >> 15;
        value *= 0x846CA68Bu;
        value ^= value >> 16;
        return value;
    }

    PathMode CurrentPathMode()
    {
        return static_cast<PathMode>(InterlockedCompareExchange(&gPathMode, 0, 0));
    }

    const char* PathModeName(PathMode mode)
    {
        return mode == PathMode::Run ? "run" : mode == PathMode::Free ? "free" : "off";
    }

    int LineForNumber(uint32_t number)
    {
        for (unsigned i = 0; i < kConsoleDlcLineCount; ++i)
            if (kConsoleDlcLines[i].number == number)
                return gConsoleDlcPresent[i] ? static_cast<int>(i) : -2;
        return -1;
    }

    // pdlc_sco_force_gun -> force_gun
    const char* WeaponTypeOf(const char* model)
    {
        const char* rest = std::strncmp(model, "pdlc_", 5) == 0 ? model + 5 : model;
        const char* underscore = std::strchr(rest, '_');
        return underscore ? underscore + 1 : rest;
    }

    // The DLC entry's store item GUID, filled once its store archive decoded (DLCItemStoreList).
    bool LineItemGuid(int line, uint32_t* guid)
    {
        if (line < 0 || gConsoleDlcEntry[line] < 0)
            return false;
        uintptr_t manager = 0;
        if (!ReadGame(kDlcManagerGlobal, &manager, 4) || !manager)
            return false;
        uint32_t value[4]{};
        if (!ReadGame(manager + kDlcEntries + gConsoleDlcEntry[line] * kDlcEntrySize + kDlcEntryItem, value,
                      sizeof(value)) ||
            !(value[0] | value[1] | value[2] | value[3]))
            return false;
        std::memcpy(guid, value, sizeof(value));
        return true;
    }

    void SetPathMode(PathMode mode, const char* why)
    {
        const PathMode before = CurrentPathMode();
        InterlockedExchange(&gPathMode, static_cast<LONG>(mode));
        if (before != mode)
            Log("suit paths: mode %s -> %s (%s)", PathModeName(before), PathModeName(mode), why);
    }

    // Which DLC line takes which retail place for this seed.
    void BuildSuitPathPlan()
    {
        for (int& line : gRetailLine)
            line = -1;
        gStartLine = -1;
        if (gSuitPath > 0)
        {
            const SuitPathRow& row = kSuitPathRows[gSuitPath - 1];
            for (unsigned level = 0; level < 6; ++level)
            {
                if (!row.levels[level])
                    continue;
                const int line = LineForNumber(row.levels[level]);
                if (line < 0)
                {
                    Log("suit paths: %s level %u (store number %u) is %s; the retail suit stays", row.style,
                        level + 1, row.levels[level], line == -2 ? "not installed" : "unknown");
                    continue;
                }
                if (level == 0)
                    gStartLine = line;
                else
                    gRetailLine[level - 1] = line;
            }
            for (unsigned w = 0; w < row.weaponCount; ++w)
            {
                const int line = LineForNumber(row.weapons[w]);
                if (line < 0)
                    continue;
                const char* type = WeaponTypeOf(kConsoleDlcLines[line].modelArchive);
                for (unsigned r = 0; r < 7; ++r)
                    if (std::strcmp(kRetailWeapons[r].type, type) == 0 && gRetailLine[5 + r] < 0)
                        gRetailLine[5 + r] = line;
            }
        }
        if (gWeaponPack > 0)
        {
            const WeaponPackRow& pack = kWeaponPackRows[gWeaponPack - 1];
            for (unsigned w = 0; w < pack.weaponCount; ++w)
            {
                const int line = LineForNumber(pack.weapons[w]);
                if (line < 0)
                    continue;
                const char* type = WeaponTypeOf(kConsoleDlcLines[line].modelArchive);
                for (unsigned r = 0; r < 7; ++r)
                    if (std::strcmp(kRetailWeapons[r].type, type) == 0 && gRetailLine[5 + r] < 0)
                        gRetailLine[5 + r] = line;   // the suit path's own weapons come first
            }
        }
        // The seed's first weapon is owned from chapter 1, so the kiosk hides its row. Swapped, the row
        // became a DLC weapon the player does not own: a third weapon in the first kiosk (seed 0x20D1228E).
        uint32_t first[4]{};
        if (gHost && gHost->firstWeaponItem && gHost->firstWeaponItem(first))
            for (unsigned r = 0; r < 7; ++r)
                if (std::memcmp(kRetailWeapons[r].item.guid, first, sizeof(first)) == 0 && gRetailLine[5 + r] >= 0)
                {
                    Log("suit paths plan: the %s is the run's first weapon; %s stays out", kRetailWeapons[r].item.name,
                        kConsoleDlcLines[gRetailLine[5 + r]].modelArchive);
                    gRetailLine[5 + r] = -1;
                }
        Log("suit paths plan: level 1 %s", gStartLine >= 0 ? kConsoleDlcLines[gStartLine].modelArchive : "retail");
        for (unsigned i = 0; i < kRetailCount; ++i)
            if (gRetailLine[i] >= 0)
                Log("suit paths plan: %s -> %s (store number %u)", RetailAt(i).name,
                    kConsoleDlcLines[gRetailLine[i]].modelArchive, kConsoleDlcLines[gRetailLine[i]].number);
    }

    void LoadSuitPathSettings()
    {
        gSuitPaths = GetPrivateProfileIntA("DeadSpace2008Randomizer", "SuitPaths", 0, gIniPath) != 0;
        gSuitPathWeaponPacks =
            GetPrivateProfileIntA("DeadSpace2008Randomizer", "SuitPathWeaponPacks", 1, gIniPath) != 0;
        gSuitPathSeed = gHost && gHost->seed ? gHost->seed() : 0x00D5A11u;
        unsigned allowed[kSuitPathNameCount]{};
        unsigned count = 0;
        for (unsigned i = 0; i < kSuitPathNameCount; ++i)
        {
            char key[64];
            std::snprintf(key, sizeof(key), "SuitPath_%s", kSuitPathNames[i]);
            if (GetPrivateProfileIntA("DeadSpace2008Randomizer", key, 1, gIniPath) != 0)
                allowed[count++] = i;
        }
        gSuitPath = count ? allowed[PathMix(gSuitPathSeed, 0x50415448u) % count] : 0;   // "PATH"
        gWeaponPack = gSuitPathWeaponPacks ? PathMix(gSuitPathSeed, 0x5750434Bu) % (kWeaponPackRowCount + 1) : 0;
        gSuitPathPrint = PathMix(gSuitPathSeed ^ (gSuitPath << 8) ^ (gWeaponPack << 16), 0x53505631u) | 1u;   // "SPV1"
        std::snprintf(gSuitPathFile, sizeof(gSuitPathFile), "%sDeadSpace2008Randomizer_SuitPaths.ini", gGameRoot);
    }

    // Prices of the items swapped in: the retail item's, or back to their own when the run is over.
    void ApplyPathPrice(unsigned retail, uintptr_t object, bool restore)
    {
        PricedObject& priced = gPriced[retail];
        if (!object)
            return;
        __try
        {
            int32_t* price = reinterpret_cast<int32_t*>(object + kItemPrice);
            if (restore)
            {
                // The record outlives the object: an item freed with its level left its address to other data, and
                // writing the old price there zeroed a kiosk animation's event pointer (crash 0x007A52CB,
                // 2026-10-24). Only the same item, by vtable and GUID, gets its price back.
                const bool same = priced.object == object &&
                                  *reinterpret_cast<const uint32_t*>(object) == priced.vtable &&
                                  std::memcmp(reinterpret_cast<const void*>(object + kItemGuid), priced.guid, 16) == 0;
                if (same && *price != priced.original)
                    *price = priced.original;
                if (!same && InterlockedIncrement(&gPathStale) <= 8)
                    Log("suit paths: the priced %s at %08X is gone; its old price is not written back",
                        RetailAt(retail).name, static_cast<unsigned>(object));
                priced = {};
                return;
            }
            // The kiosk's price getter 0x005A16D0 reads +0x61C of any item (its callers 0x0059D9D0..0x005A07A0
            // price suits and weapons alike). The retail items are mostly templates without an object; when one
            // exists, its price must be the authored one, or nothing is written.
            const uintptr_t retailObject = gHost && gHost->objectFor ? gHost->objectFor(RetailAt(retail).guid) : 0;
            const int32_t want = RetailAt(retail).price;
            const int32_t live = retailObject ? *reinterpret_cast<const int32_t*>(retailObject + kItemPrice) : want;
            if (live != want)
            {
                if (InterlockedIncrement(&gPathPrices) <= 16)
                    Log("suit paths: %s shows %d at +0x61C, not its price %d; %s keeps its own price",
                        RetailAt(retail).name, live, want, kConsoleDlcLines[gRetailLine[retail]].modelArchive);
                return;
            }
            if (priced.object != object)
            {
                priced.object = object;
                priced.original = *price;
                priced.vtable = *reinterpret_cast<const uint32_t*>(object);
                std::memcpy(priced.guid, reinterpret_cast<const void*>(object + kItemGuid), 16);
            }
            if (*price != want)
                *price = want;
        }
        __except (EXCEPTION_EXECUTE_HANDLER)
        {
        }
    }

    void RestorePathPrices()
    {
        for (unsigned i = 0; i < kRetailCount; ++i)
            if (gPriced[i].object)
                ApplyPathPrice(i, gPriced[i].object, true);
    }

    // Game thread, through the host's AddItem hook.
    int PathStoreAddItem(uint32_t* guid, uintptr_t caller)
    {
        if (!gSuitPaths || !guid)
            return ds2008::kStoreKeep;
        PathMode mode = CurrentPathMode();
        if (mode == PathMode::Run)
        {
            uint32_t round = 0;
            if (ReadGame(kRoundCounter, &round, 4) && round > 0)
            {
                SetPathMode(PathMode::Free, "a playthrough is done, New Game+");
                mode = PathMode::Free;
            }
        }
        if (mode != PathMode::Run)
        {
            RestorePathPrices();
            return ds2008::kStoreKeep;
        }
        if (caller == kCallerRegistry)
        {
            if (InterlockedIncrement(&gPathHidden) <= 8)
                Log("suit paths: DLC item %08X-%08X stays out of the store during the run", guid[0], guid[1]);
            return ds2008::kStoreHide;
        }
        for (unsigned i = 0; i < kRetailCount; ++i)
        {
            if (gRetailLine[i] < 0 || std::memcmp(guid, RetailAt(i).guid, 16) != 0)
                continue;
            uint32_t item[4]{};
            if (!LineItemGuid(gRetailLine[i], item))
            {
                if (InterlockedIncrement(&gPathNotReady) <= 16)
                    Log("suit paths: %s stays retail, %s has no store item yet", RetailAt(i).name,
                        kConsoleDlcLines[gRetailLine[i]].storeArchive);
                return ds2008::kStoreKeep;
            }
            std::memcpy(guid, item, sizeof(item));
            std::memcpy(gSwappedItem[i], item, sizeof(item));
            ApplyPathPrice(i, gHost && gHost->objectFor ? gHost->objectFor(item) : 0, false);
            const LONG swaps = InterlockedIncrement(&gPathSwaps);
            if (swaps <= 64)
                Log("suit paths: %s -> %s (%08X-%08X) from %s", RetailAt(i).name,
                    kConsoleDlcLines[gRetailLine[i]].modelArchive, item[0], item[1],
                    caller == kCallerStoreList ? "a store list" : caller == kCallerSchematic ? "a schematic" : "AddItem");
            return ds2008::kStoreReplaced;
        }
        return ds2008::kStoreKeep;
    }

    // Game thread, at the gate: a swapped-in item waits for what the retail item waited for.
    void PathStoreGate(const uint32_t* guid, int32_t* chapter, int32_t* played, bool forced)
    {
        if (!gSuitPaths || forced || CurrentPathMode() != PathMode::Run || !gHost || !gHost->storeRequirement)
            return;
        for (unsigned i = 0; i < kRetailCount; ++i)
        {
            uint32_t item[4]{};
            if (gRetailLine[i] < 0 || !LineItemGuid(gRetailLine[i], item) || std::memcmp(guid, item, 16) != 0)
                continue;
            int32_t wantChapter = 0, wantPlayed = 0;
            if (!gHost->storeRequirement(RetailAt(i).guid, &wantChapter, &wantPlayed))
                return;
            if (InterlockedIncrement(&gPathGates) <= 32)
                Log("suit paths: %s in the place of %s waits for chapter %d, %d game(s) done (it had %d/%d)",
                    kConsoleDlcLines[gRetailLine[i]].modelArchive, RetailAt(i).name, wantChapter, wantPlayed,
                    *chapter, *played);
            *chapter = wantChapter;
            *played = wantPlayed;
            // The entry's key is resolved here; the object may exist now when it did not at AddItem.
            ApplyPathPrice(i, gHost->objectFor ? gHost->objectFor(item) : 0, false);
            return;
        }
    }

    // Game thread, the kiosk asks an item for its price: a swapped-in DLC item gets the retail price here.
    void PriceGetter_Hook(safetyhook::Context& ctx)
    {
        if (!gSuitPaths || !ctx.ecx || CurrentPathMode() != PathMode::Run)
            return;
        InterlockedIncrement(&gGetterCalls);
        __try
        {
            const uint32_t* guid = reinterpret_cast<const uint32_t*>(ctx.ecx + kItemGuid);
            for (unsigned i = 0; i < kRetailCount; ++i)
            {
                if (gRetailLine[i] < 0 || !gSwappedItem[i][0] || std::memcmp(guid, gSwappedItem[i], 16) != 0)
                    continue;
                const int32_t price = *reinterpret_cast<const int32_t*>(ctx.ecx + kItemPrice);
                if (InterlockedIncrement(&gGetterSeen) <= 12)
                    Log("suit paths: the kiosk prices %s (%08X-%08X, object %08X) at %d, the %s costs %d",
                        kConsoleDlcLines[gRetailLine[i]].modelArchive, guid[0], guid[1],
                        static_cast<unsigned>(ctx.ecx), price, RetailAt(i).name, RetailAt(i).price);
                if (price == RetailAt(i).price || gPriceRefused[i] == ctx.ecx)
                    return;
                ApplyPathPrice(i, ctx.ecx, false);
                if (*reinterpret_cast<const int32_t*>(ctx.ecx + kItemPrice) == RetailAt(i).price)
                    InterlockedIncrement(&gGetterPriced);
                else
                    gPriceRefused[i] = ctx.ecx;
                return;
            }
        }
        __except (EXCEPTION_EXECUTE_HANDLER)
        {
        }
    }

    void PathNewGame()
    {
        if (!gSuitPaths)
            return;
        BuildSuitPathPlan();
        SetPathMode(PathMode::Run, "New Game");
        Log("suit paths: New Game with seed %u plays the %s path%s%s", gSuitPathSeed, kSuitPathNames[gSuitPath],
            gWeaponPack ? " and the " : "", gWeaponPack ? kWeaponPackRows[gWeaponPack - 1].pack : "");
    }

    int PathStartingUniform()
    {
        if (!gSuitPaths || CurrentPathMode() != PathMode::Run || gStartLine < 0)
            return -1;
        const int index = static_cast<int>(kConsoleDlcLines[gStartLine].key) - 1;
        Log("suit paths: the run starts in %s (uniform entry %d)", kConsoleDlcLines[gStartLine].modelArchive, index);
        return index;
    }

    // Game thread: the chapter 1 Plasma Cutter (pickup or loadout) becomes the path's own cutter.
    bool PathFirstWeapon(uint32_t* proxy)
    {
        constexpr unsigned kCutter = 5;   // kRetailWeapons[0], the Plasma Cutter
        if (!gSuitPaths || !proxy || CurrentPathMode() != PathMode::Run || gRetailLine[kCutter] < 0)
            return false;
        uint32_t item[4]{};
        if (!LineItemGuid(gRetailLine[kCutter], item))
            return false;
        std::memcpy(proxy, item, sizeof(item));
        static LONG lines = 0;
        if (InterlockedIncrement(&lines) <= 8)
            Log("suit paths: the chapter 1 Plasma Cutter is the %s (%08X-%08X)",
                kConsoleDlcLines[gRetailLine[kCutter]].modelArchive, item[0], item[1]);
        return true;
    }

    // --- saves ----------------------------------------------------------------------------------------------
    void SaveSlot_Hook(safetyhook::Context& ctx)
    {
        gSavingSlot = *reinterpret_cast<const unsigned*>(ctx.esp + 4);
    }

    void SaveFinished_Hook(safetyhook::Context& ctx)
    {
        __try
        {
            const unsigned status = *reinterpret_cast<const unsigned*>(ctx.esp + 4);
            const unsigned slot = *reinterpret_cast<const unsigned*>(ctx.ecx + kSaveFinishedSlot);
            if (status != 0 || slot >= kSaveSlots)
                return;
            gSlotPendingPrint[slot] = CurrentPathMode() == PathMode::Run ? gSuitPathPrint : 0;
            InterlockedExchange(&gSlotPending[slot], 1);
            Log("suit paths: slot %u saved during a %s (asked for slot %u)", slot + 1,
                CurrentPathMode() == PathMode::Run ? "suit path run" : "free run", gSavingSlot + 1);
        }
        __except (EXCEPTION_EXECUTE_HANDLER)
        {
        }
    }

    void LoadSlot_Hook(safetyhook::Context& ctx)
    {
        gLoadingSlot = *reinterpret_cast<const unsigned*>(ctx.esp + 4);
    }

    void ApplyLoadedSave_Hook(safetyhook::Context&)
    {
        if (!gSuitPaths)
            return;
        const unsigned slot = gLoadingSlot;
        const bool ours = slot < kSaveSlots && gSlotPrint[slot] == gSuitPathPrint &&
                          gSlotTime[slot] && gSlotTime[slot] == gSlotFileTime[slot];
        BuildSuitPathPlan();
        SetPathMode(ours ? PathMode::Run : PathMode::Free,
                    ours ? "a save of this run" : slot < kSaveSlots && gSlotPrint[slot] && gSlotPrint[slot] != gSuitPathPrint
                        ? "a save of another seed or path" : "a save without a suit path mark, or changed since");
        Log("suit paths: slot %u loaded (mark %08X, ours %08X, file time %s)", slot + 1,
            slot < kSaveSlots ? gSlotPrint[slot] : 0, gSuitPathPrint,
            slot < kSaveSlots && gSlotTime[slot] == gSlotFileTime[slot] ? "unchanged" : "changed or unknown");
    }

    bool SaveFileTime(unsigned slot, uint64_t* time)
    {
        char path[MAX_PATH];
        std::snprintf(path, sizeof(path), "%sds_slot_%02u.deadspacesaved", gSaveFolder, slot + 1);
        WIN32_FILE_ATTRIBUTE_DATA info{};
        if (!GetFileAttributesExA(path, GetFileExInfoStandard, &info))
            return false;
        *time = (static_cast<uint64_t>(info.ftLastWriteTime.dwHighDateTime) << 32) |
                info.ftLastWriteTime.dwLowDateTime;
        return true;
    }

    // Poll thread: file times of the save slots, and the marks of fresh saves.
    void PollSuitPaths()
    {
        if (!gSuitPaths || !gSaveFolder[0])
            return;
        static ULONGLONG last = 0;
        const ULONGLONG now = GetTickCount64();
        if (now - last < 1000)
            return;
        last = now;
        for (unsigned slot = 0; slot < kSaveSlots; ++slot)
        {
            uint64_t time = 0;
            SaveFileTime(slot, &time);
            gSlotFileTime[slot] = time;
            if (!InterlockedCompareExchange(&gSlotPending[slot], 0, 0) || !time)
                continue;
            InterlockedExchange(&gSlotPending[slot], 0);
            gSlotPrint[slot] = gSlotPendingPrint[slot];
            gSlotTime[slot] = time;
            char key[16], value[48];
            std::snprintf(key, sizeof(key), "Slot%02u", slot + 1);
            std::snprintf(value, sizeof(value), "%08X %016llX", gSlotPrint[slot],
                          static_cast<unsigned long long>(time));
            WritePrivateProfileStringA("Saves", key, value, gSuitPathFile);
            Log("suit paths: slot %u marked %08X", slot + 1, gSlotPrint[slot]);
        }
        static LONG lastTotals[6] = {-1, -1, -1, -1, -1, -1};
        const LONG totals[6] = {gPathSwaps, gPathHidden, gPathGates, gPathNotReady, static_cast<LONG>(CurrentPathMode()),
                                gGetterPriced};
        if (std::memcmp(totals, lastTotals, sizeof(totals)) != 0)
        {
            std::memcpy(lastTotals, totals, sizeof(totals));
            Log("suit paths totals: mode %s, %ld swapped in, %ld DLC items kept out, %ld requirements set, %ld not ready, "
                "%ld priced at the kiosk (%ld price reads)", PathModeName(CurrentPathMode()), totals[0], totals[1],
                totals[2], totals[3], totals[5], InterlockedCompareExchange(&gGetterCalls, 0, 0));
        }
    }

    void InstallSuitPaths()
    {
        LoadSuitPathSettings();
        Log("suit paths: %s; seed %u -> %s path, weapon pack %s (roll %s), mark %08X", gSuitPaths ? "on" : "off",
            gSuitPathSeed, kSuitPathNames[gSuitPath], gWeaponPack ? kWeaponPackRows[gWeaponPack - 1].pack : "none",
            gSuitPathWeaponPacks ? "on" : "off", gSuitPathPrint);
        if (!gSuitPaths)
            return;
        if (!gConsoleDlc)
        {
            Log("suit paths: NOT active, the console DLC is off or not installed");
            gSuitPaths = false;
            return;
        }
        char documents[MAX_PATH]{};
        if (SUCCEEDED(SHGetFolderPathA(nullptr, CSIDL_PERSONAL, nullptr, SHGFP_TYPE_CURRENT, documents)))
            std::snprintf(gSaveFolder, sizeof(gSaveFolder), "%s\\Electronic Arts\\Dead Space\\", documents);
        for (unsigned slot = 0; slot < kSaveSlots; ++slot)
        {
            char key[16], value[64]{};
            std::snprintf(key, sizeof(key), "Slot%02u", slot + 1);
            GetPrivateProfileStringA("Saves", key, "", value, sizeof(value), gSuitPathFile);
            unsigned print = 0;
            unsigned long long time = 0;
            if (sscanf_s(value, "%x %llx", &print, &time) == 2)
            {
                gSlotPrint[slot] = print;
                gSlotTime[slot] = time;
            }
        }
        gSaveSlotHook = VerifiedMid(reinterpret_cast<void*>(kSaveSlot), &SaveSlot_Hook);
        gSaveFinishedHook = VerifiedMid(reinterpret_cast<void*>(kSaveFinished), &SaveFinished_Hook);
        gLoadSlotHook = VerifiedMid(reinterpret_cast<void*>(kLoadSlot), &LoadSlot_Hook);
        gApplyLoadedSaveHook = VerifiedMid(reinterpret_cast<void*>(kApplyLoadedSave), &ApplyLoadedSave_Hook);
        gPriceGetterHook = VerifiedMid(reinterpret_cast<void*>(kItemPriceGetter), &PriceGetter_Hook);
        Log("suit paths: kiosk price hook %s at %08X", gPriceGetterHook ? "active" : "NOT installed",
            static_cast<unsigned>(kItemPriceGetter));
        Log("suit paths: save hooks %s/%s/%s/%s, saves in %s, marks in %s", gSaveSlotHook ? "ok" : "MISSING",
            gSaveFinishedHook ? "ok" : "MISSING", gLoadSlotHook ? "ok" : "MISSING",
            gApplyLoadedSaveHook ? "ok" : "MISSING", gSaveFolder[0] ? gSaveFolder : "(unknown)", gSuitPathFile);
        if (!gSaveSlotHook || !gSaveFinishedHook || !gLoadSlotHook || !gApplyLoadedSaveHook)
            Log("suit paths: without every save hook a loaded save cannot be told apart; loaded saves count as free");
    }
