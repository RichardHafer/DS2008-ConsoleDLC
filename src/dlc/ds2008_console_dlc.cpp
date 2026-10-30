// Dead Space 2008 Randomizer Console DLC: an extension plugin for the Dead Space 2008 Randomizer (DeadSpace2008Randomizer.asi).
//
// The console DLC suits and weapons, converted from the PS3/Xbox packs and the custom suits built on them
// (tools/ds1_dlc_build.py, ds1_randomizer_assets\dlc), plus the larger suit table they need. It does nothing on its
// own: the host finds it through DS2008_GetExtension (src/ds2008_extension.h) once the game code is decrypted and
// calls it from its own hooks.
#include <windows.h>
#include <shlobj.h>
#include <cstdio>
#include <cstdarg>
#include <cstdint>
#include <cstring>
#include <iterator>
#include "../../include/safetyhook/safetyhook.hpp"
#include "../ds2008_extension.h"

namespace
{
    const ds2008::HostApi* gHost = nullptr;
    char gIniPath[MAX_PATH]{};
    char gGameRoot[MAX_PATH]{};

    void Log(const char* format, ...)
    {
        if (!gHost || !gHost->log)
            return;
        char text[2048];
        va_list args;
        va_start(args, format);
        _vsnprintf_s(text, sizeof(text), _TRUNCATE, format, args);
        va_end(args);
        gHost->log(text);
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

    int StreamStateFor(void* manager, uint32_t id)
    {
        return gHost && gHost->streamState ? gHost->streamState(manager, id) : -1;
    }

    uintptr_t StreamObjectFor(void* manager, uint32_t id)
    {
        return gHost && gHost->streamObject ? gHost->streamObject(manager, id) : 0;
    }

    safetyhook::InlineHook VerifiedInline(void* target, void* destination)
    {
        if (!gHost || !gHost->hookSiteOk || !gHost->hookSiteOk(target, "inline"))
            return {};
        return safetyhook::create_inline(target, destination);
    }

    safetyhook::MidHook VerifiedMid(void* target, safetyhook::MidHookFn destination)
    {
        if (!gHost || !gHost->hookSiteOk || !gHost->hookSiteOk(target, "mid"))
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
        ds2008::kExtensionApiVersion, "Dead Space 2008 Randomizer Console DLC", &ExtensionInstall, &ExtensionWantsStreamHook,
        &ExtensionAdjustLoad, &ExtensionLoadSeen, &ExtensionPoll, &ExtensionUniformTail, &ExtensionUniformSlots,
        &ExtensionWantsStoreHooks, &PathStoreAddItem, &PathStoreGate, &PathNewGame, &PathStartingUniform,
        &PathFirstWeapon,
    };
}

extern "C" __declspec(dllexport) const ds2008::Extension* __cdecl DS2008_GetExtension(const ds2008::HostApi* host)
{
    if (!host || host->version != ds2008::kExtensionApiVersion)
        return nullptr;
    gHost = host;
    strncpy_s(gIniPath, host->iniPath ? host->iniPath : "", _TRUNCATE);
    strncpy_s(gGameRoot, host->gameRoot ? host->gameRoot : "", _TRUNCATE);
    return &kExtension;
}

extern "C" __declspec(dllexport) const char* __cdecl DS2008_DlcName(const char* modelArchive)
{
    if (!modelArchive)
        return nullptr;
    // ConsoleDlcMaterials loads <model>_cm instead
    size_t length = strnlen(modelArchive, 128);
    if (length > 3 && _stricmp(modelArchive + length - 3, "_cm") == 0)
        length -= 3;
    for (const DlcName& entry : kDlcNames)
        if (std::strlen(entry.model) == length && _strnicmp(entry.model, modelArchive, length) == 0)
            return entry.name;
    return nullptr;
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH)
        DisableThreadLibraryCalls(module);
    return TRUE;
}
