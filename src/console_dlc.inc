    // =====================================================================
    // Console DLC ([DeadSpace2008Randomizer] ConsoleDlc; analysis/DeadSpace1_DLC_Research_2026-10-23.md).
    //
    // The PC exe still has the console DLC manager at 0x00F64A68 (ctor
    // 0x0051DEE0): up to 160 entries of 0x1DC bytes from +0x1C, count at
    // +0x1299C. An entry is one line of a pack's .store list: +0x00 1 for a
    // weapon, 0 for a suit; +0x04 the store number; +0x08 the store archive;
    // +0x88 the model archive; +0x108 the weapon index or uniform slot minus
    // one (the .store parser 0x0051F9F5 subtracts it, and so do the DLC
    // decoders); +0x10C the folder. Nothing on PC fills it, so we do, from the converted packs
    // (tools/ds1_dlc_build.py) in ds1_randomizer_assets\dlc.
    //
    // After that the game does the rest by itself:
    // - the store archive (DLCItemStoreList 0x0050F8A0) puts its item GUID at
    //   +0x1C8 of the entry with its store number; the kiosk (0x005A0EE0) adds
    //   every entry's item to the shop, with PickupItem[20] -1 so the store gate
    //   always admits it, and Item[36] unset, so it costs nothing;
    // - DLCWeaponStreamAttributes (0x00506AE0) writes the gun and ammo GUIDs of
    //   its weapon index into 0x00F46728 and the WeaponManager;
    // - equipping a DLC weapon or suit finds no retail stream, looks the entry
    //   up by index (0x0051EF00) or slot (0x0051EE00) and loads folder + model
    //   archive itself (0x0050799E, 0x005A2738, 0x005A2D7E);
    // - each store archive's LHR loads the text table of the language.
    //
    // The store archives are requested right after global_assets and marked
    // persistent (stream +0x48 bit 3, which UnloadAll 0x006C8460 skips; the
    // game's own setter 0x006CB590 is never called on PC). They and their
    // entities therefore stay through world changes and save loads, so the
    // DLC items a save holds always exist when it is restored.
    // Each world change the level loader's step 4 (0x00413FB0) has the
    // manager queue every entry whose stream (+0x1D8) is not resident and
    // reload it (0x0051E1E0), waiting for a completion event per archive
    // (0x0051E320). That event never arrived for a loose archive and the
    // loading screen stayed forever (log 2026-10-23 18:19), so our entries
    // carry the persistent handle and the replacement below only re-requests
    // an archive that was dropped anyway, without waiting.
    // =====================================================================
    struct ConsoleDlcLine
    {
        bool weapon;
        uint32_t number;
        const char* storeArchive;
        const char* modelArchive;
        uint32_t key;
    };
    constexpr ConsoleDlcLine kConsoleDlcLines[] = {
#include "console_dlc_generated.inc"
    };
    constexpr unsigned kConsoleDlcLineCount = sizeof(kConsoleDlcLines) / sizeof(kConsoleDlcLines[0]);

    constexpr uintptr_t kDlcManagerGlobal = 0x00F64A68;
    constexpr uintptr_t kDlcWeaponTable = 0x00F46728;   // 32-byte rows: gun GUID, ammo GUID
    constexpr uintptr_t kWeaponManagerGlobal = 0x00F44138;
    constexpr unsigned kDlcEntries = 0x1C;
    constexpr unsigned kDlcEntrySize = 0x1DC;
    constexpr unsigned kDlcEntryCapacity = 0xA0;
    constexpr unsigned kDlcEntryCount = 0x1299C;
    constexpr unsigned kDlcEntryNumber = 0x04;
    constexpr unsigned kDlcEntryStoreArchive = 0x08;
    constexpr unsigned kDlcEntryModelArchive = 0x88;
    constexpr unsigned kDlcEntryKey = 0x108;
    constexpr unsigned kDlcEntryFolder = 0x10C;
    constexpr unsigned kDlcEntrySlot = 0x190;
    constexpr unsigned kDlcEntryItem = 0x1C8;
    constexpr unsigned kDlcEntryStream = 0x1D8;
    constexpr uintptr_t kDlcReloadContent = 0x0051E1E0;   // stdcall(manager), returns true while it waits
    constexpr uintptr_t kStreamManagerInstance = 0x00F648E0;
    constexpr unsigned kStreamFlags = 0x48;
    constexpr uint16_t kStreamPersistent = 0x08;
    constexpr int kStreamResident = 3;
    constexpr unsigned kDlcNameSize = 0x80;
    constexpr char kConsoleDlcFolder[] = "ds1_randomizer_assets\\dlc\\";

    bool gConsoleDlc = true;
    // Suits: the archive with the console material values (<model>_cm) instead of the PC ones
    bool gConsoleDlcMaterials = false;
    char gConsoleDlcModel[kConsoleDlcLineCount][64]{};
    bool gConsoleDlcPresent[kConsoleDlcLineCount]{};
    bool gConsoleDlcDone = false;
    unsigned gConsoleDlcAttempts = 0;
    void* gConsoleDlcStreams = nullptr;
    uint32_t gConsoleDlcHandles[kConsoleDlcLineCount]{};
    int gConsoleDlcEntry[kConsoleDlcLineCount]{};
    safetyhook::InlineHook gDlcReloadHook;
    volatile LONG gConsoleDlcReloads = 0;

    bool ReadGame(uintptr_t at, void* out, size_t size)
    {
        SIZE_T done = 0;
        return ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<const void*>(at), out, size, &done) &&
               done == size;
    }

    void LoadConsoleDlcSettings()
    {
        gConsoleDlc = GetPrivateProfileIntA("DeadSpace2008Randomizer", "ConsoleDlc", 1, gIniPath) != 0;
        gConsoleDlcMaterials = GetPrivateProfileIntA("DeadSpace2008Randomizer", "ConsoleDlcMaterials", 0, gIniPath) != 0;
    }

    uint8_t* ConsoleDlcEntryFor(uint8_t* manager, uint32_t number, int* index)
    {
        const uint32_t count = *reinterpret_cast<uint32_t*>(manager + kDlcEntryCount);
        for (uint32_t e = 0; e < count && e < kDlcEntryCapacity; ++e)
        {
            uint8_t* entry = manager + kDlcEntries + e * kDlcEntrySize;
            if (*reinterpret_cast<uint32_t*>(entry + kDlcEntryNumber) == number)
            {
                *index = static_cast<int>(e);
                return entry;
            }
        }
        return nullptr;
    }

    // Game thread. Requests a store archive and marks its stream persistent.
    uint32_t ConsoleDlcRequest(void* streams, unsigned line, uint8_t* entry)
    {
        char path[MAX_PATH];
        std::snprintf(path, sizeof(path), "%s%s", kConsoleDlcFolder, kConsoleDlcLines[line].storeArchive);
        const auto load = reinterpret_cast<StreamLoadFn>(kStreamManagerLoad);
        const uint32_t handle = load(streams, path, 0.0f, kStreamLoadRetainedCustom, nullptr, nullptr, 0);
        const uintptr_t stream = handle ? StreamObjectFor(streams, handle) : 0;
        if (stream)
            *reinterpret_cast<uint16_t*>(stream + kStreamFlags) |= kStreamPersistent;
        if (entry)
            *reinterpret_cast<uint32_t*>(entry + kDlcEntryStream) = handle;
        gConsoleDlcHandles[line] = handle;
        gConsoleDlcStreams = streams;
        Log("console DLC: store archive %s requested: handle=%08X state=%d %s", path, handle,
            handle ? StreamStateFor(streams, handle) : -1,
            stream ? "persistent" : "NOT persistent (no stream object), a world change will drop it");
        return handle;
    }

    // Game thread, loader step 4 of every world change.
    uint8_t __stdcall DlcReloadContent_Hook(uint8_t* manager)
    {
        if (!gConsoleDlcDone || !manager)
            return gDlcReloadHook.stdcall<uint8_t>(manager);
        const LONG reload = InterlockedIncrement(&gConsoleDlcReloads);
        __try
        {
            void* streams = *reinterpret_cast<void**>(kStreamManagerInstance);
            unsigned resident = 0, dropped = 0, missing = 0;
            for (unsigned i = 0; i < kConsoleDlcLineCount; ++i)
            {
                if (!gConsoleDlcPresent[i])
                    continue;
                int index = -1;
                uint8_t* entry = ConsoleDlcEntryFor(manager, kConsoleDlcLines[i].number, &index);
                gConsoleDlcEntry[i] = index;
                if (!entry || !streams)
                {
                    ++missing;
                    continue;
                }
                const uint32_t handle = *reinterpret_cast<uint32_t*>(entry + kDlcEntryStream);
                const int state = handle ? StreamStateFor(streams, handle) : -1;
                if (state == kStreamResident)
                {
                    ++resident;
                    continue;
                }
                ++dropped;
                Log("console DLC: world change %ld dropped %s (handle %08X state %d); its items may be missing "
                    "from a save restored now", reload, kConsoleDlcLines[i].storeArchive, handle, state);
                ConsoleDlcRequest(streams, i, entry);
            }
            if (reload <= 20)
                Log("console DLC: world change %ld, %u store archive(s) still resident, %u requested again, "
                    "%u entr%s missing", reload, resident, dropped, missing, missing == 1 ? "y" : "ies");
        }
        __except (EXCEPTION_EXECUTE_HANDLER)
        {
            Log("console DLC: reload faulted (code %08X), the loader goes on", GetExceptionCode());
        }
        return 0;
    }

    // At attach: which packs are installed. The game thread then only works from this list.
    void InstallConsoleDlc()
    {
        LoadConsoleDlcSettings();
        if (!gConsoleDlc)
        {
            Log("console DLC: off");
            return;
        }
        unsigned present = 0;
        for (unsigned i = 0; i < kConsoleDlcLineCount; ++i)
        {
            const ConsoleDlcLine& line = kConsoleDlcLines[i];
            char store[MAX_PATH], model[MAX_PATH];
            std::snprintf(store, sizeof(store), "%s%s%s.str", gGameRoot, kConsoleDlcFolder, line.storeArchive);
            std::snprintf(model, sizeof(model), "%s%s%s.str", gGameRoot, kConsoleDlcFolder, line.modelArchive);
            const bool haveStore = GetFileAttributesA(store) != INVALID_FILE_ATTRIBUTES;
            const bool haveModel = GetFileAttributesA(model) != INVALID_FILE_ATTRIBUTES;
            strncpy_s(gConsoleDlcModel[i], line.modelArchive, _TRUNCATE);
            if (gConsoleDlcMaterials && !line.weapon)
            {
                char variant[MAX_PATH];
                std::snprintf(variant, sizeof(variant), "%s%s%s_cm.str", gGameRoot, kConsoleDlcFolder,
                              line.modelArchive);
                if (GetFileAttributesA(variant) != INVALID_FILE_ATTRIBUTES)
                    std::snprintf(gConsoleDlcModel[i], sizeof(gConsoleDlcModel[i]), "%s_cm", line.modelArchive);
            }
            // A suit fills table entry key - 1 unchecked; past the table it would overwrite the manager
            const bool fits = line.weapon || line.key <= gUniformSlotCount;
            gConsoleDlcPresent[i] = haveStore && haveModel && fits;
            gConsoleDlcEntry[i] = -1;
            present += gConsoleDlcPresent[i] ? 1u : 0u;
            Log("console DLC: %s %u %s / %s key %u: %s", line.weapon ? "weapon" : "suit", line.number,
                line.storeArchive, gConsoleDlcModel[i], line.key,
                !fits ? "SKIPPED, slot beyond the suit table (SuitSlots)" : gConsoleDlcPresent[i] ? "installed" :
                haveStore ? "model archive missing" : "store archive missing");
        }
        Log("console DLC: %u of %u line(s) installed in %s", present, kConsoleDlcLineCount, kConsoleDlcFolder);
        if (!present)
        {
            gConsoleDlc = false;
            return;
        }
        gDlcReloadHook = VerifiedInline(reinterpret_cast<void*>(kDlcReloadContent),
                                        reinterpret_cast<void*>(&DlcReloadContent_Hook));
        Log("console DLC: content reload hook %s at %08X", gDlcReloadHook ? "active" : "NOT installed",
            static_cast<unsigned>(kDlcReloadContent));
        if (!gDlcReloadHook)
            gConsoleDlc = false;   // without it the first world change would hang
    }

    // Game thread, inside our StreamManager::Load hook.
    void ConsoleDlcRegister(void* streams)
    {
        if (!gConsoleDlc || gConsoleDlcDone)
            return;
        auto* manager = *reinterpret_cast<uint8_t**>(kDlcManagerGlobal);
        if (!manager)
        {
            if (++gConsoleDlcAttempts <= 3 || gConsoleDlcAttempts % 50 == 0)
                Log("console DLC: manager at %08X not created yet (attempt %u)",
                    static_cast<unsigned>(kDlcManagerGlobal), gConsoleDlcAttempts);
            return;
        }
        gConsoleDlcDone = true;
        gConsoleDlcStreams = streams;
        auto& count = *reinterpret_cast<uint32_t*>(manager + kDlcEntryCount);
        Log("console DLC: manager %p holds %u entr%s before ours", manager, count, count == 1 ? "y" : "ies");
        __try
        {
            for (unsigned i = 0; i < kConsoleDlcLineCount; ++i)
            {
                if (!gConsoleDlcPresent[i])
                    continue;
                const ConsoleDlcLine& line = kConsoleDlcLines[i];
                uint8_t* entry = nullptr;
                for (uint32_t e = 0; e < count && e < kDlcEntryCapacity; ++e)
                {
                    uint8_t* candidate = manager + kDlcEntries + e * kDlcEntrySize;
                    if (*reinterpret_cast<uint32_t*>(candidate + kDlcEntryNumber) == line.number)
                    {
                        entry = candidate;
                        gConsoleDlcEntry[i] = static_cast<int>(e);
                        Log("console DLC: store number %u already has entry %u, filled in", line.number, e);
                        break;
                    }
                }
                if (!entry)
                {
                    if (count >= kDlcEntryCapacity)
                    {
                        Log("console DLC: manager full, %s not registered", line.storeArchive);
                        continue;
                    }
                    entry = manager + kDlcEntries + count * kDlcEntrySize;
                    gConsoleDlcEntry[i] = static_cast<int>(count);
                    ++count;
                }
                entry[0] = line.weapon ? 1 : 0;
                *reinterpret_cast<uint32_t*>(entry + kDlcEntryNumber) = line.number;
                *reinterpret_cast<uint32_t*>(entry + kDlcEntryKey) = line.key - 1;
                strncpy_s(reinterpret_cast<char*>(entry + kDlcEntryStoreArchive), kDlcNameSize, line.storeArchive,
                          _TRUNCATE);
                strncpy_s(reinterpret_cast<char*>(entry + kDlcEntryModelArchive), kDlcNameSize, gConsoleDlcModel[i],
                          _TRUNCATE);
                strncpy_s(reinterpret_cast<char*>(entry + kDlcEntryFolder), kDlcNameSize, kConsoleDlcFolder,
                          _TRUNCATE);
                Log("console DLC: entry %d = %s %u, key %u (.store %u), %s%s", gConsoleDlcEntry[i],
                    line.weapon ? "weapon" : "suit", line.number, line.key - 1, line.key, kConsoleDlcFolder,
                    gConsoleDlcModel[i]);
            }
            // The store archives only after every entry exists: DLCItemStoreList adds an entry of its
            // own for a store number it cannot find.
            for (unsigned i = 0; i < kConsoleDlcLineCount; ++i)
            {
                if (!gConsoleDlcPresent[i] || gConsoleDlcEntry[i] < 0)
                    continue;
                ConsoleDlcRequest(streams, i, manager + kDlcEntries + gConsoleDlcEntry[i] * kDlcEntrySize);
            }
        }
        __except (EXCEPTION_EXECUTE_HANDLER)
        {
            Log("console DLC: registration faulted (code %08X)", GetExceptionCode());
        }
    }

    // Every load of one of our archives, whoever asks for it: the store archives, the model archives the
    // game requests on equip and the text tables the LHRs request.
    // The text tables come from the LHR of a store archive, which loads once. They are kept like the
    // store archives: dropped by a death reload, every DLC entry in the store showed the Line Gun's
    // text (2026-10-23 18:4x).
    void ConsoleDlcLoadSeen(void* streams, const char* path, uint8_t flags, uint32_t result, uintptr_t caller)
    {
        bool kept = false;
        if (result && PathMentions(path, "dlc\\text\\"))
        {
            const uintptr_t stream = StreamObjectFor(streams, result);
            if (stream)
            {
                *reinterpret_cast<uint16_t*>(stream + kStreamFlags) |= kStreamPersistent;
                kept = true;
            }
        }
        // The text tables alone used up the old shared cap of 64 lines, so suit and weapon loads went unlogged.
        static volatile LONG textLines = 0, modelLines = 0;
        const bool text = PathMentions(path, "dlc\\text\\");
        if (InterlockedIncrement(text ? &textLines : &modelLines) <= (text ? 16 : 200))
            Log("console DLC: load %s flags=%02X from %08X -> handle=%08X state=%d%s%s", path,
                static_cast<unsigned>(flags), static_cast<unsigned>(caller), result,
                result ? StreamStateFor(streams, result) : -1, kept ? " persistent" : "",
                result ? "" : " (FAILED)");
    }

    // Poll thread: what the game made of the entries, logged when it changes.
    void PollConsoleDlc()
    {
        if (!gConsoleDlc || !gConsoleDlcDone)
            return;
        static ULONGLONG last = 0;
        const ULONGLONG now = GetTickCount64();
        if (now - last < 2000)
            return;
        last = now;
        static uint32_t lastDigest = 0;
        static unsigned reports = 0;
        uintptr_t manager = 0, weapons = 0;
        uint32_t count = 0;
        if (!ReadGame(kDlcManagerGlobal, &manager, 4) || !manager ||
            !ReadGame(manager + kDlcEntryCount, &count, 4))
            return;
        ReadGame(kWeaponManagerGlobal, &weapons, 4);
        char text[1536];
        int used = std::snprintf(text, sizeof(text), "console DLC state: %u entr%s, WeaponManager %08X;",
                                 count, count == 1 ? "y" : "ies", static_cast<unsigned>(weapons));
        uint32_t digest = count * 2654435761u ^ static_cast<uint32_t>(weapons);
        for (unsigned i = 0; i < kConsoleDlcLineCount && used > 0 && used < static_cast<int>(sizeof(text)); ++i)
        {
            if (gConsoleDlcEntry[i] < 0)
                continue;
            const ConsoleDlcLine& line = kConsoleDlcLines[i];
            const uintptr_t entry = manager + kDlcEntries + gConsoleDlcEntry[i] * kDlcEntrySize;
            uint32_t number = 0, slot = 0, item[4]{};
            ReadGame(entry + kDlcEntryNumber, &number, 4);
            ReadGame(entry + kDlcEntrySlot, &slot, 4);
            ReadGame(entry + kDlcEntryItem, item, sizeof(item));
            const int state = gConsoleDlcHandles[i] && gConsoleDlcStreams
                                  ? StreamStateFor(gConsoleDlcStreams, gConsoleDlcHandles[i]) : -1;
            digest = (digest * 31u) ^ number ^ slot ^ item[0] ^ item[1] ^ static_cast<uint32_t>(state);
            used += std::snprintf(text + used, sizeof(text) - used, " [%u %s state %d item %08X-%08X", number,
                                  line.modelArchive, state, item[0], item[1]);
            if (line.weapon)
            {
                uint32_t row[8]{}, wm[12]{};
                const uint32_t index = line.key - 1;
                if (index < 0x96)
                    ReadGame(kDlcWeaponTable + index * 0x20, row, sizeof(row));
                if (weapons && index < 30)
                    ReadGame(weapons + 0x68 + index * 0x30, wm, sizeof(wm));
                digest = (digest * 31u) ^ row[0] ^ row[1] ^ wm[3] ^ wm[4] ^ wm[5];
                used += std::snprintf(text + used, sizeof(text) - used,
                                      " gun %08X-%08X ammo %08X-%08X wm stream %08X-%08X gun %08X-%08X]", row[0],
                                      row[1], row[4], row[5], wm[0], wm[3], wm[4], wm[5]);
            }
            else
            {
                uint32_t model = 0;
                ReadGame(entry + 0x198, &model, 4);
                digest = (digest * 31u) ^ model;
                used += std::snprintf(text + used, sizeof(text) - used, " slot %u uniform data %08X]", slot, model);
            }
        }
        if (digest == lastDigest || reports >= 40)
            return;
        lastDigest = digest;
        ++reports;
        Log("%s", text);
    }
