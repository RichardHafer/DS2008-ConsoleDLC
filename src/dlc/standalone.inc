    // Running without the Dead Space 2008 Randomizer.
    //
    // The randomizer is looked for where the ASI loader picks plugins up (the game folder, plugins\, scripts\).
    // When it is there it attaches through DS2008_GetExtension and drives everything. When it is not, this plugin
    // does the randomizer's part itself: the StreamManager::Load hook, the poll thread, the log, the INI
    // (DeadSpace2008Randomizer_ConsoleDLC.ini, same keys and section) and the larger sound bank table the DLC
    // weapons need.
    const char* const kHostFiles[] = {"DeadSpace2008Randomizer.asi", "plugins\\DeadSpace2008Randomizer.asi",
                                      "scripts\\DeadSpace2008Randomizer.asi"};
    safetyhook::InlineHook gOwnStreamLoad;

    bool HostInstalled()
    {
        if (GetModuleHandleA("DeadSpace2008Randomizer.asi"))
            return true;
        for (const char* name : kHostFiles)
        {
            char path[MAX_PATH];
            std::snprintf(path, sizeof(path), "%s%s", gGameRoot, name);
            if (GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES)
                return true;
        }
        return false;
    }

    // Still encrypted, the code section has almost no ordinary function prologues.
    bool CodeLooksDecrypted()
    {
        __try
        {
            const auto* base = reinterpret_cast<const BYTE*>(GetModuleHandleA(nullptr));
            const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
            const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS*>(base + dos->e_lfanew);
            const auto* section = IMAGE_FIRST_SECTION(nt);
            const BYTE* text = base + section->VirtualAddress;
            const size_t size = section->Misc.VirtualSize;
            size_t prologues = 0;
            for (size_t i = 0; i + 3 < size && prologues < 64; ++i)
                if (text[i] == 0x55 && text[i + 1] == 0x8B && text[i + 2] == 0xEC)
                    ++prologues;
            return prologues >= 64;
        }
        __except (EXCEPTION_EXECUTE_HANDLER)
        {
            return false;
        }
    }

    // Dead Space's own StreamManager::Load bytes; anything else (another game, another build) gets nothing patched.
    bool GameCodeMatches()
    {
        for (const HookSignature& site : kHookSignatures)
        {
            if (site.address != kStreamManagerLoad)
                continue;
            unsigned char code[8]{};
            return site.length && ReadCode(site.address, code, site.length) &&
                   std::memcmp(code, site.bytes, site.length) == 0;
        }
        return false;
    }

    // The randomizer's hook does the same for an extension: adjust the packed flag, report every load after it.
    uint32_t __fastcall OwnStreamLoad_Hook(void* self, void*, const char* path, float priority, uint8_t flags,
                                           const uint32_t* dependencies, const char* context, int packed)
    {
        static thread_local bool inside = false;
        static bool globalAssetsSeen = false;
        packed = ExtensionAdjustLoad(path, packed);
        if (inside)
            return gOwnStreamLoad.thiscall<uint32_t>(self, path, priority, flags, dependencies, context, packed);
        inside = true;
        const uint32_t result =
            gOwnStreamLoad.thiscall<uint32_t>(self, path, priority, flags, dependencies, context, packed);
        if (path)
        {
            if (result && PathMentions(path, "global_assets\\global_assets"))
                globalAssetsSeen = true;
            ExtensionLoadSeen(self, path, flags, result, reinterpret_cast<uintptr_t>(_ReturnAddress()),
                              globalAssetsSeen);
        }
        inside = false;
        return result;
    }

    DWORD WINAPI StandaloneStart(LPVOID)
    {
        unsigned attempts = 0;
        while (!CodeLooksDecrypted() && ++attempts < 400)
            Sleep(50);
        Log("code %s after %u check(s)", attempts < 400 ? "readable" : "STILL NOT readable", attempts + 1);
        if (!GameCodeMatches())
        {
            Log("StreamManager::Load at %08X is not the Steam build's; nothing installed",
                static_cast<unsigned>(kStreamManagerLoad));
            return 0;
        }
        InstallUniformSlots();
        InstallConsoleDlc();
        Log("suit paths: off, they need the randomizer's store hooks and seed");
        if (ExtensionWantsStreamHook())
        {
            gOwnStreamLoad = VerifiedInline(reinterpret_cast<void*>(kStreamManagerLoad),
                                            reinterpret_cast<void*>(&OwnStreamLoad_Hook));
            Log("StreamManager::Load hook %s at %08X", gOwnStreamLoad ? "installed" : "NOT installed, no DLC items",
                static_cast<unsigned>(kStreamManagerLoad));
        }
        for (;;)
        {
            Sleep(100);
            ExtensionPoll();
        }
    }

    // DllMain: decide who drives the plugin.
    void StandaloneAttach()
    {
        const DWORD length = GetModuleFileNameA(nullptr, gGameRoot, MAX_PATH);
        char* cut = length && length < MAX_PATH ? std::strrchr(gGameRoot, '\\') : nullptr;
        if (!cut)
            return;
        cut[1] = '\0';
        if (HostInstalled())
            return;   // the randomizer attaches once the code is decrypted
        if (InterlockedCompareExchange(&gMode, kModeStandalone, kModeUndecided) != kModeUndecided)
            return;
        std::snprintf(gIniPath, sizeof(gIniPath), "%sDeadSpace2008Randomizer_ConsoleDLC.ini", gGameRoot);
        char previous[MAX_PATH];
        std::snprintf(gLogPath, sizeof(gLogPath), "%sDeadSpace2008Randomizer_ConsoleDLC.log", gGameRoot);
        std::snprintf(previous, sizeof(previous), "%sDeadSpace2008Randomizer_ConsoleDLC.prev.log", gGameRoot);
        MoveFileExA(gLogPath, previous, MOVEFILE_REPLACE_EXISTING);
        Log("Dead Space 2008 Randomizer Console DLC, standalone: no DeadSpace2008Randomizer.asi found");
        Log("settings: %s (%s)", gIniPath,
            GetFileAttributesA(gIniPath) != INVALID_FILE_ATTRIBUTES ? "found" : "not found, defaults");
        // As the randomizer does: the bank table goes in before the audio init builds its manager.
        if (CodeLooksDecrypted() && GameCodeMatches())
            InstallSoundBankSlots();
        else
            Log("sound bank slots: game code not readable or not the Steam build at load, retail table of %u kept",
                kBankRetailSlots);
        if (HANDLE thread = CreateThread(nullptr, 0, &StandaloneStart, nullptr, 0, nullptr))
            CloseHandle(thread);
        else
            Log("could not start the plugin thread (%lu); nothing installed", GetLastError());
    }
