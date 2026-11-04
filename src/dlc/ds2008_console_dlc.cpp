// Dead Space 2008 Randomizer Console DLC: the console DLC suits and weapons, converted from the PS3/Xbox packs, the
// custom suits built on them (tools/ds1_dlc_build.py, ds1_randomizer_assets\dlc) and the larger suit table they need.
//
// With the Dead Space 2008 Randomizer installed it is an extension: the randomizer finds it through
// DS2008_GetExtension (src/ds2008_extension.h) once the game code is decrypted and calls it from its own hooks.
// Without the randomizer it runs on its own (standalone.inc): its own StreamManager::Load hook, poll thread, log,
// INI and sound bank table. Suit paths need the randomizer's store hooks and seed and stay off then.
#include <windows.h>
#include <shlobj.h>
#include <cstdio>
#include <cstdarg>
#include <cstdint>
#include <cstring>
#include <intrin.h>
#include <iterator>
#include "../../include/safetyhook/safetyhook.hpp"
#include "../ds2008_extension.h"

namespace
{
    // The randomizer logs this name when it attaches the plugin.
    constexpr char kDlcName[] = "Dead Space 2008 Randomizer Console DLC 1.0.2";

    const ds2008::HostApi* gHost = nullptr;
    char gIniPath[MAX_PATH]{};
    char gGameRoot[MAX_PATH]{};

    // Who drives the plugin: the randomizer (host) or the plugin itself.
    enum : LONG { kModeUndecided, kModeHost, kModeStandalone };
    volatile LONG gMode = kModeUndecided;
    char gLogPath[MAX_PATH]{};
    SRWLOCK gLogLock = SRWLOCK_INIT;

    void StandaloneLog(const char* text)
    {
        if (!gLogPath[0])
            return;
        AcquireSRWLockExclusive(&gLogLock);
        if (FILE* file = _fsopen(gLogPath, "a", _SH_DENYNO))
        {
            SYSTEMTIME now{};
            GetLocalTime(&now);
            std::fprintf(file, "[%02u:%02u:%02u.%03u] %s\n", now.wHour, now.wMinute, now.wSecond,
                         now.wMilliseconds, text);
            std::fclose(file);
        }
        ReleaseSRWLockExclusive(&gLogLock);
    }

    void Log(const char* format, ...)
    {
        char text[2048];
        va_list args;
        va_start(args, format);
        _vsnprintf_s(text, sizeof(text), _TRUNCATE, format, args);
        va_end(args);
        if (gHost && gHost->log)
            gHost->log(text);
        else
            StandaloneLog(text);
    }

    bool PathMentions(const char* path, const char* needle)
    {
        if (!path || !needle)
            return false;
        const size_t length = std::strlen(needle);
        for (const char* at = path; *at; ++at)
            if (_strnicmp(at, needle, length) == 0)
                return true;
        return false;
    }

    // The StreamManager's id table: buckets at +0x54, count at +0x58, nodes {id, stream, next}; state at stream +0x1C.
    uintptr_t OwnStreamObject(void* managerObject, uint32_t id)
    {
        const uintptr_t manager = reinterpret_cast<uintptr_t>(managerObject);
        if (!manager || !id)
            return 0;
        __try
        {
            const uintptr_t buckets = *reinterpret_cast<const uintptr_t*>(manager + 0x54);
            const unsigned count = *reinterpret_cast<const unsigned*>(manager + 0x58);
            if (!buckets || !count)
                return 0;
            uintptr_t node = *reinterpret_cast<const uintptr_t*>(buckets + (id % count) * sizeof(uintptr_t));
            for (unsigned step = 0; node && step < 4096; ++step)
            {
                if (*reinterpret_cast<const uint32_t*>(node) == id)
                    return *reinterpret_cast<const uintptr_t*>(node + 4);
                const uintptr_t next = *reinterpret_cast<const uintptr_t*>(node + 8);
                if (next == node)
                    break;
                node = next;
            }
        }
        __except (EXCEPTION_EXECUTE_HANDLER)
        {
        }
        return 0;
    }

    int StreamStateFor(void* manager, uint32_t id)
    {
        if (gHost)
            return gHost->streamState ? gHost->streamState(manager, id) : -1;
        const uintptr_t stream = OwnStreamObject(manager, id);
        if (!stream)
            return -1;
        __try
        {
            return *reinterpret_cast<const int*>(stream + 0x1C);
        }
        __except (EXCEPTION_EXECUTE_HANDLER)
        {
            return -1;
        }
    }

    uintptr_t StreamObjectFor(void* manager, uint32_t id)
    {
        if (gHost)
            return gHost->streamObject ? gHost->streamObject(manager, id) : 0;
        return OwnStreamObject(manager, id);
    }

#include "../hook_signatures_generated.inc"

    bool ReadCode(uintptr_t address, unsigned char* out, size_t length)
    {
        __try
        {
            std::memcpy(out, reinterpret_cast<const void*>(address), length);
            return true;
        }
        __except (EXCEPTION_EXECUTE_HANDLER)
        {
            return false;
        }
    }

    // Without the host: the same retail byte check, from the same signature table.
    bool OwnHookSiteOk(void* target, const char* kind)
    {
        const uintptr_t address = reinterpret_cast<uintptr_t>(target);
        for (const HookSignature& site : kHookSignatures)
        {
            if (site.address != address)
                continue;
            unsigned char code[8]{};
            if (!ReadCode(address, code, site.length ? site.length : 1))
            {
                Log("hook %s (%s) at %08X REFUSED: not readable (not the Dead Space exe?)", site.name, kind,
                    static_cast<unsigned>(address));
                return false;
            }
            if (site.length ? std::memcmp(code, site.bytes, site.length) == 0 : code[0] != 0xE9)
                return true;
            Log("hook %s (%s) at %08X REFUSED: %s", site.name, kind, static_cast<unsigned>(address),
                code[0] == 0xE9 ? "a jump is already there (another mod)" : "the bytes differ from the Steam build");
            return false;
        }
        Log("hook (%s) at %08X is not in the signature table; refused", kind, static_cast<unsigned>(address));
        return false;
    }

    bool HookSiteOk(void* target, const char* kind)
    {
        if (gHost)
            return gHost->hookSiteOk && gHost->hookSiteOk(target, kind);
        return OwnHookSiteOk(target, kind);
    }

    safetyhook::InlineHook VerifiedInline(void* target, void* destination)
    {
        if (!HookSiteOk(target, "inline"))
            return {};
        return safetyhook::create_inline(target, destination);
    }

    safetyhook::MidHook VerifiedMid(void* target, safetyhook::MidHookFn destination)
    {
        if (!HookSiteOk(target, "mid"))
            return {};
        return safetyhook::create_mid(target, destination);
    }

    constexpr uintptr_t kStreamManagerLoad = 0x006C8B00;
    constexpr uint8_t kStreamLoadRetainedCustom = 4u;
    using StreamLoadFn = uint32_t(SAFETYHOOK_THISCALL*)(
        void*, const char*, float, uint8_t, const uint32_t*, const char*, int);

#include "../uniform_slots.inc"
#include "../console_dlc.inc"
#include "../suit_paths.inc"
#include "../sound_banks.inc"

    // --- the extension ----------------------------------------------------------------------------------------
    void ExtensionInstall()
    {
        InstallUniformSlots();
        InstallConsoleDlc();
        InstallSuitPaths();
    }

    void ExtensionPoll()
    {
        PollConsoleDlc();
        PollSuitPaths();
    }

    bool ExtensionWantsStoreHooks()
    {
        return gSuitPaths;
    }

    bool ExtensionWantsStreamHook()
    {
        return gConsoleDlc;
    }

    int ExtensionAdjustLoad(const char* path, int packed)
    {
        // The console DLC code asks for its archives with the last argument 1, which opens the path inside a
        // packed archive (0x006C7AF0); a loose file then never leaves state 0. Loose files take 0, as the text
        // tables do (0x0078A7DF).
        return gConsoleDlc && packed && path && PathMentions(path, kConsoleDlcFolder) ? 0 : packed;
    }

    void ExtensionLoadSeen(void* streams, const char* path, uint8_t flags, uint32_t result, uintptr_t caller,
                           bool globalAssets)
    {
        if (!gConsoleDlc || !path)
            return;
        if (PathMentions(path, kConsoleDlcFolder))
            ConsoleDlcLoadSeen(streams, path, flags, result, caller);
        if (globalAssets && !gConsoleDlcDone)
            ConsoleDlcRegister(streams);
    }

    uint32_t ExtensionUniformTail()
    {
        return gUniformTail;
    }

    uint32_t ExtensionUniformSlots()
    {
        return gUniformSlotCount;
    }

    struct DlcName
    {
        const char* model;
        const char* name;
    };
    constexpr DlcName kDlcNames[] = {
#include "dlc_names_generated.inc"
    };

    const ds2008::Extension kExtension = {
        ds2008::kExtensionApiVersion, kDlcName, &ExtensionInstall, &ExtensionWantsStreamHook,
        &ExtensionAdjustLoad, &ExtensionLoadSeen, &ExtensionPoll, &ExtensionUniformTail, &ExtensionUniformSlots,
        &ExtensionWantsStoreHooks, &PathStoreAddItem, &PathStoreGate, &PathNewGame, &PathStartingUniform,
        &PathFirstWeapon,
    };

#include "standalone.inc"
}

extern "C" __declspec(dllexport) const ds2008::Extension* __cdecl DS2008_GetExtension(const ds2008::HostApi* host)
{
    if (!host || host->version != ds2008::kExtensionApiVersion)
        return nullptr;
    if (InterlockedCompareExchange(&gMode, kModeHost, kModeUndecided) == kModeStandalone)
    {
        Log("a randomizer asked to attach, but this plugin already runs on its own; refused");
        return nullptr;
    }
    gHost = host;
    strncpy_s(gIniPath, host->iniPath ? host->iniPath : "", _TRUNCATE);
    strncpy_s(gGameRoot, host->gameRoot ? host->gameRoot : "", _TRUNCATE);
    return &kExtension;
}

extern "C" __declspec(dllexport) const char* __cdecl DS2008_DlcName(const char* modelArchive)
{
    if (!modelArchive)
        return nullptr;
    // ConsoleDlcMaterials loads <model>_cm instead, RigColours <model>_rig or <model>_cm_rig
    size_t length = strnlen(modelArchive, 128);
    if (length > 4 && _strnicmp(modelArchive + length - 4, "_rig", 4) == 0)
        length -= 4;
    if (length > 3 && _strnicmp(modelArchive + length - 3, "_cm", 3) == 0)
        length -= 3;
    for (const DlcName& entry : kDlcNames)
        if (std::strlen(entry.model) == length && _strnicmp(entry.model, modelArchive, length) == 0)
            return entry.name;
    return nullptr;
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        DisableThreadLibraryCalls(module);
        StandaloneAttach();
    }
    return TRUE;
}
