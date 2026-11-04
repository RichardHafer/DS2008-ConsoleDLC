@echo off
setlocal

rem DeadSpace2008Randomizer_ConsoleDLC.asi, the console DLC add-on for the Dead Space 2008 Randomizer.
set VCVARS="C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars32.bat"
if not exist %VCVARS% set VCVARS="C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars32.bat"
if not exist %VCVARS% (
    echo Could not find vcvars32.bat - edit the path in this script.
    exit /b 1
)

call %VCVARS% >nul 2>&1
if not exist obj_dlc mkdir obj_dlc

cl /nologo /c /O2 /EHsc /std:c++latest /MT /DNDEBUG /W4 /Iinclude ^
   src\dlc\ds2008_console_dlc.cpp include\safetyhook\safetyhook.cpp /Foobj_dlc\
if not "%ERRORLEVEL%"=="0" goto fail

cl /nologo /c /O2 /MT /Iinclude include\safetyhook\Zydis.c /Foobj_dlc\
if not "%ERRORLEVEL%"=="0" goto fail

link /nologo /DLL /OUT:DeadSpace2008Randomizer_ConsoleDLC.asi obj_dlc\*.obj kernel32.lib user32.lib shell32.lib
if not "%ERRORLEVEL%"=="0" goto fail

echo Built DeadSpace2008Randomizer_ConsoleDLC.asi
exit /b 0

:fail
echo Build failed.
exit /b 1
