    // =====================================================================
    // Suit slots ([DeadSpace2008Randomizer] SuitSlots, default 64; 30 keeps retail).
    //
    // The UniformManager (ctor 0x005A2000, 0x964 bytes) holds 30 suit entries
    // of 0x4C bytes from +0x6C, then the current index and four state fields
    // at +0x954..+0x963. A DLC suit fills the entry of its slot without a
    // bounds check (0x005A2E10), so slot 31 and up would overwrite them. The
    // tail moves behind a longer table: object and registry size, the three
    // loops over the table and every tail access, also those through the
    // +0x3C and +0x44 interfaces. Every site is checked before a byte is
    // written; one mismatch keeps the retail layout.
    // =====================================================================
    constexpr unsigned kUniformRetailSlots = 30;
    constexpr unsigned kUniformMaxSlots = 100;   // the loop counts are imm8
    constexpr unsigned kUniformRetailTail = 0x954;
    constexpr unsigned kUniformRetailSize = 0x964;
    constexpr unsigned kUniformTableStart = 0x6C;
    constexpr unsigned kUniformStride = 0x4C;
    constexpr uintptr_t kUniformFactorySize = 0x0040A85A;      // add eax, 0x964
    constexpr uintptr_t kUniformCtorArrayCount = 0x005A202E;   // push 0x1E (entry constructors)
    constexpr uintptr_t kUniformCtorInitCount = 0x005A20B2;    // mov ecx, 0x1E (slots and factor)
    constexpr uintptr_t kUniformLinkCount = 0x005A2A11;        // cmp edi, 0x1E (DLC entries at link)
    // The class registry is filled during game init (0x00414A40 -> 0x0040ED90), usually after this runs, so
    // the size the registration pushes is patched too; a row that already exists is patched in place.
    constexpr uintptr_t kUniformRegisterSize = 0x0040F5F9;     // push 0x964 (registry size)
    constexpr uintptr_t kClassRegistryRows = 0x00F65138;       // 16-byte rows: hash, factory, name, size
    constexpr uintptr_t kClassRegistryCount = 0x00F6513C;
    constexpr uint32_t kUniformManagerHash = 0x67B6CED9;
    constexpr uintptr_t kUniformManagerFactory = 0x0040A840;
    constexpr uintptr_t kUniformManagerLinked = 0x00F4415C;

    struct UniformTailSite
    {
        uintptr_t at;
        uint8_t length;
        uint8_t disp;    // position of the displacement in the instruction
        uint8_t base;    // interface offset the register points at
        uint8_t bytes[10];
    };

    // From the live retail code (2026-10-23); the field is disp + base.
    constexpr UniformTailSite kUniformTailSites[] = {
        {0x00520FB0, 6, 2, 0x00, {0x8B, 0x88, 0x54, 0x09, 0x00, 0x00}},   // mov ecx, dword ptr [eax + 0x954]
        {0x00520FD0, 6, 2, 0x00, {0x8B, 0x88, 0x54, 0x09, 0x00, 0x00}},   // mov ecx, dword ptr [eax + 0x954]
        {0x0052AD04, 6, 2, 0x00, {0x8B, 0x88, 0x54, 0x09, 0x00, 0x00}},   // mov ecx, dword ptr [eax + 0x954]
        {0x0052B35C, 6, 2, 0x00, {0x8B, 0x88, 0x54, 0x09, 0x00, 0x00}},   // mov ecx, dword ptr [eax + 0x954]
        {0x0057A670, 6, 2, 0x00, {0x8B, 0x91, 0x54, 0x09, 0x00, 0x00}},   // mov edx, dword ptr [ecx + 0x954]
        {0x0057A83C, 6, 2, 0x00, {0x8B, 0x82, 0x54, 0x09, 0x00, 0x00}},   // mov eax, dword ptr [edx + 0x954]
        {0x0058173F, 6, 2, 0x00, {0x8B, 0x81, 0x54, 0x09, 0x00, 0x00}},   // mov eax, dword ptr [ecx + 0x954]
        {0x00581ADA, 6, 2, 0x00, {0x8B, 0x88, 0x54, 0x09, 0x00, 0x00}},   // mov ecx, dword ptr [eax + 0x954]
        {0x00598310, 6, 2, 0x00, {0x8A, 0x80, 0x58, 0x09, 0x00, 0x00}},   // mov al, byte ptr [eax + 0x958]
        {0x00598320, 6, 2, 0x00, {0x8B, 0x80, 0x54, 0x09, 0x00, 0x00}},   // mov eax, dword ptr [eax + 0x954]
        {0x0059C4C1, 6, 2, 0x00, {0x8B, 0xB0, 0x54, 0x09, 0x00, 0x00}},   // mov esi, dword ptr [eax + 0x954]
        {0x0059D0CF, 7, 2, 0x00, {0x80, 0xB8, 0x58, 0x09, 0x00, 0x00, 0x00}},   // cmp byte ptr [eax + 0x958], 0
        {0x005A0869, 6, 2, 0x00, {0x8B, 0xB6, 0x54, 0x09, 0x00, 0x00}},   // mov esi, dword ptr [esi + 0x954]
        {0x005A206E, 6, 2, 0x00, {0x89, 0x8F, 0x54, 0x09, 0x00, 0x00}},   // mov dword ptr [edi + 0x954], ecx
        {0x005A2074, 6, 2, 0x00, {0x88, 0x9F, 0x58, 0x09, 0x00, 0x00}},   // mov byte ptr [edi + 0x958], bl
        {0x005A207A, 6, 2, 0x00, {0x88, 0x9F, 0x59, 0x09, 0x00, 0x00}},   // mov byte ptr [edi + 0x959], bl
        {0x005A2080, 6, 2, 0x00, {0x89, 0x9F, 0x5C, 0x09, 0x00, 0x00}},   // mov dword ptr [edi + 0x95c], ebx
        {0x005A2086, 10, 2, 0x00, {0xC7, 0x87, 0x60, 0x09, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF}},   // mov dword ptr [edi + 0x960], 0xffffffff
        {0x005A24A6, 6, 2, 0x00, {0x89, 0x81, 0x5C, 0x09, 0x00, 0x00}},   // mov dword ptr [ecx + 0x95c], eax
        {0x005A25FE, 6, 2, 0x00, {0x89, 0x96, 0x54, 0x09, 0x00, 0x00}},   // mov dword ptr [esi + 0x954], edx
        {0x005A260C, 6, 2, 0x00, {0x8B, 0x87, 0x54, 0x09, 0x00, 0x00}},   // mov eax, dword ptr [edi + 0x954]
        {0x005A26AA, 7, 2, 0x00, {0x80, 0xBF, 0x59, 0x09, 0x00, 0x00, 0x00}},   // cmp byte ptr [edi + 0x959], 0
        {0x005A26C4, 7, 2, 0x00, {0xC6, 0x87, 0x59, 0x09, 0x00, 0x00, 0x01}},   // mov byte ptr [edi + 0x959], 1
        {0x005A26D8, 6, 2, 0x00, {0x8B, 0xB8, 0x54, 0x09, 0x00, 0x00}},   // mov edi, dword ptr [eax + 0x954]
        {0x005A2750, 6, 2, 0x00, {0x8B, 0x90, 0x54, 0x09, 0x00, 0x00}},   // mov edx, dword ptr [eax + 0x954]
        {0x005A2A1E, 6, 2, 0x00, {0x8B, 0x88, 0x54, 0x09, 0x00, 0x00}},   // mov ecx, dword ptr [eax + 0x954]
        {0x005A2A63, 6, 2, 0x00, {0x8B, 0x8B, 0x54, 0x09, 0x00, 0x00}},   // mov ecx, dword ptr [ebx + 0x954]
        {0x005A2B12, 6, 2, 0x00, {0x8B, 0x93, 0x54, 0x09, 0x00, 0x00}},   // mov edx, dword ptr [ebx + 0x954]
        {0x005A2BA6, 6, 2, 0x00, {0x39, 0xB3, 0x54, 0x09, 0x00, 0x00}},   // cmp dword ptr [ebx + 0x954], esi
        {0x005A2CBF, 7, 2, 0x00, {0xC6, 0x83, 0x58, 0x09, 0x00, 0x00, 0x00}},   // mov byte ptr [ebx + 0x958], 0
        {0x005A2DD6, 7, 2, 0x00, {0xC6, 0x83, 0x58, 0x09, 0x00, 0x00, 0x01}},   // mov byte ptr [ebx + 0x958], 1
        {0x005A2DE1, 6, 2, 0x00, {0x89, 0x83, 0x54, 0x09, 0x00, 0x00}},   // mov dword ptr [ebx + 0x954], eax
        {0x005A2F21, 6, 2, 0x00, {0x8B, 0x8B, 0x54, 0x09, 0x00, 0x00}},   // mov ecx, dword ptr [ebx + 0x954]
        {0x005A2F33, 6, 2, 0x00, {0x8B, 0x93, 0x54, 0x09, 0x00, 0x00}},   // mov edx, dword ptr [ebx + 0x954]
        {0x005A2F6D, 6, 2, 0x00, {0x89, 0x96, 0x54, 0x09, 0x00, 0x00}},   // mov dword ptr [esi + 0x954], edx
        {0x005A2F83, 7, 2, 0x00, {0x83, 0xBE, 0x60, 0x09, 0x00, 0x00, 0xFF}},   // cmp dword ptr [esi + 0x960], -1
        {0x005A2F93, 7, 2, 0x00, {0x83, 0xBE, 0x5C, 0x09, 0x00, 0x00, 0x00}},   // cmp dword ptr [esi + 0x95c], 0
        {0x005A2F9C, 6, 2, 0x00, {0x8B, 0x86, 0x5C, 0x09, 0x00, 0x00}},   // mov eax, dword ptr [esi + 0x95c]
        {0x005A2FAA, 6, 2, 0x00, {0x89, 0x86, 0x60, 0x09, 0x00, 0x00}},   // mov dword ptr [esi + 0x960], eax
        {0x005A2FB0, 6, 2, 0x00, {0x8B, 0x86, 0x60, 0x09, 0x00, 0x00}},   // mov eax, dword ptr [esi + 0x960]
        {0x005A2FC4, 6, 2, 0x00, {0x8B, 0x8E, 0x54, 0x09, 0x00, 0x00}},   // mov ecx, dword ptr [esi + 0x954]
        {0x0052ACEE, 6, 2, 0x44, {0x8B, 0x88, 0x10, 0x09, 0x00, 0x00}},   // mov ecx, dword ptr [eax + 0x910]
        {0x005A280A, 6, 2, 0x3C, {0x8B, 0x96, 0x18, 0x09, 0x00, 0x00}},   // mov edx, dword ptr [esi + 0x918]
        {0x005A2841, 7, 2, 0x3C, {0x80, 0xBE, 0x1D, 0x09, 0x00, 0x00, 0x00}},   // cmp byte ptr [esi + 0x91d], 0
        {0x005A2857, 7, 2, 0x3C, {0xC6, 0x86, 0x1D, 0x09, 0x00, 0x00, 0x01}},   // mov byte ptr [esi + 0x91d], 1
        {0x005A2880, 6, 2, 0x3C, {0x8B, 0x86, 0x18, 0x09, 0x00, 0x00}},   // mov eax, dword ptr [esi + 0x918]
        {0x005A28B1, 6, 2, 0x3C, {0x8B, 0x86, 0x18, 0x09, 0x00, 0x00}},   // mov eax, dword ptr [esi + 0x918]
        {0x005A28F3, 7, 2, 0x3C, {0xC6, 0x86, 0x1C, 0x09, 0x00, 0x00, 0x00}},   // mov byte ptr [esi + 0x91c], 0
    };

    unsigned gUniformSlotCount = kUniformRetailSlots;   // entries the live table holds
    unsigned gUniformTail = kUniformRetailTail;

    // A retail tail offset (0x954..0x963) to where the field lives now.
    unsigned UniformTailOffset(unsigned retail)
    {
        return retail - kUniformRetailTail + gUniformTail;
    }

    bool UniformCodeMatches(uintptr_t at, const uint8_t* bytes, size_t length)
    {
        __try
        {
            return std::memcmp(reinterpret_cast<const void*>(at), bytes, length) == 0;
        }
        __except (EXCEPTION_EXECUTE_HANDLER)
        {
            return false;
        }
    }

    void UniformReadCode(uintptr_t at, uint8_t* out, size_t length)
    {
        __try
        {
            std::memcpy(out, reinterpret_cast<const void*>(at), length);
        }
        __except (EXCEPTION_EXECUTE_HANDLER)
        {
        }
    }

    bool UniformWriteCode(uintptr_t at, const void* data, size_t length)
    {
        DWORD old = 0;
        if (!VirtualProtect(reinterpret_cast<void*>(at), length, PAGE_EXECUTE_READWRITE, &old))
            return false;
        std::memcpy(reinterpret_cast<void*>(at), data, length);
        VirtualProtect(reinterpret_cast<void*>(at), length, old, &old);
        FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void*>(at), length);
        return true;
    }

    uint8_t* UniformRegistryRow()
    {
        __try
        {
            auto* rows = *reinterpret_cast<uint8_t**>(kClassRegistryRows);
            const uint32_t count = *reinterpret_cast<uint32_t*>(kClassRegistryCount);
            for (uint32_t i = 0; rows && i < count && i < 4096; ++i)
            {
                uint8_t* row = rows + 16 * i;
                if (*reinterpret_cast<uint32_t*>(row) == kUniformManagerHash)
                    return *reinterpret_cast<uint32_t*>(row + 4) == kUniformManagerFactory ? row : nullptr;
            }
        }
        __except (EXCEPTION_EXECUTE_HANDLER)
        {
        }
        return nullptr;
    }

    void InstallUniformSlots()
    {
        unsigned wanted = GetPrivateProfileIntA("DeadSpace2008Randomizer", "SuitSlots", 64, gIniPath);
        if (wanted <= kUniformRetailSlots)
        {
            Log("suit slots: %u requested, retail table of %u kept", wanted, kUniformRetailSlots);
            return;
        }
        if (wanted > kUniformMaxSlots)
        {
            Log("suit slots: %u requested, capped at %u", wanted, kUniformMaxSlots);
            wanted = kUniformMaxSlots;
        }
        if (*reinterpret_cast<volatile uint32_t*>(kUniformManagerLinked))
        {
            Log("suit slots: NOT extended, a UniformManager is linked already (%08X); retail table of %u kept",
                *reinterpret_cast<volatile uint32_t*>(kUniformManagerLinked), kUniformRetailSlots);
            return;
        }

        static constexpr uint8_t kFactory[] = {0x05, 0x64, 0x09, 0x00, 0x00};
        static constexpr uint8_t kArrayCount[] = {0x6A, 0x1E};
        static constexpr uint8_t kInitCount[] = {0xB9, 0x1E, 0x00, 0x00, 0x00};
        static constexpr uint8_t kLinkCount[] = {0x83, 0xFF, 0x1E};
        unsigned mismatches = 0;
        auto check = [&](uintptr_t at, const uint8_t* bytes, size_t length, const char* what) {
            if (UniformCodeMatches(at, bytes, length))
                return;
            ++mismatches;
            uint8_t actual[6]{};
            UniformReadCode(at, actual, sizeof(actual));
            Log("suit slots: %s at %08X does not match (found %02X %02X %02X %02X %02X %02X)", what,
                static_cast<unsigned>(at), actual[0], actual[1], actual[2], actual[3], actual[4], actual[5]);
        };
        check(kUniformFactorySize, kFactory, sizeof(kFactory), "factory size");
        check(kUniformCtorArrayCount, kArrayCount, sizeof(kArrayCount), "constructor array count");
        check(kUniformCtorInitCount, kInitCount, sizeof(kInitCount), "constructor init count");
        check(kUniformLinkCount, kLinkCount, sizeof(kLinkCount), "link loop count");
        static constexpr uint8_t kRegisterSize[] = {0x68, 0x64, 0x09, 0x00, 0x00};
        check(kUniformRegisterSize, kRegisterSize, sizeof(kRegisterSize), "registration size");
        for (const UniformTailSite& site : kUniformTailSites)
            check(site.at, site.bytes, site.length, "tail access");
        uint8_t* row = UniformRegistryRow();
        if (row && *reinterpret_cast<uint32_t*>(row + 12) != kUniformRetailSize)
        {
            ++mismatches;
            Log("suit slots: registry row for %08X holds an unexpected size %X", kUniformManagerHash,
                *reinterpret_cast<uint32_t*>(row + 12));
        }
        if (mismatches)
        {
            Log("suit slots: NOT extended, %u of %u site(s) differ; retail table of %u kept", mismatches,
                static_cast<unsigned>(std::size(kUniformTailSites)) + 6, kUniformRetailSlots);
            return;
        }

        const uint32_t tail = kUniformTableStart + wanted * kUniformStride;
        const uint32_t size = tail + (kUniformRetailSize - kUniformRetailTail);
        unsigned written = 0;
        uint8_t count8 = static_cast<uint8_t>(wanted);
        uint32_t count32 = wanted;
        written += UniformWriteCode(kUniformFactorySize + 1, &size, 4);
        written += UniformWriteCode(kUniformCtorArrayCount + 1, &count8, 1);
        written += UniformWriteCode(kUniformCtorInitCount + 1, &count32, 4);
        written += UniformWriteCode(kUniformLinkCount + 2, &count8, 1);
        written += UniformWriteCode(kUniformRegisterSize + 1, &size, 4);
        for (const UniformTailSite& site : kUniformTailSites)
        {
            uint32_t disp = 0;
            std::memcpy(&disp, site.bytes + site.disp, 4);
            const uint32_t moved = disp - kUniformRetailTail + tail;   // the interface base cancels out
            written += UniformWriteCode(site.at + site.disp, &moved, 4);
        }
        if (row)
            *reinterpret_cast<uint32_t*>(row + 12) = size;
        const unsigned expected = static_cast<unsigned>(std::size(kUniformTailSites)) + 5;
        if (written != expected)
        {
            // Partly patched code cannot be trusted; nothing should run on it.
            Log("suit slots: only %u of %u write(s) took; the game is left in an unknown state", written,
                expected);
            return;
        }
        gUniformSlotCount = wanted;
        gUniformTail = tail;
        Log("suit slots: table extended from %u to %u entries; object %X -> %X bytes, tail %X -> %X, "
            "%u site(s) patched, registry %s", kUniformRetailSlots, wanted, kUniformRetailSize, size, kUniformRetailTail,
            tail, expected, row ? "row patched" : "not filled yet, its registration pushes the new size");
    }
