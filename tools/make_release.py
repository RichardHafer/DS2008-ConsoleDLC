"""Build the release zip of the console DLC add-on.

The zip holds the plugin and the DLC archives the plugin's table names, nothing else. A custom suit whose archives
sit in the assets folder but which the table does not list (a suit built for yourself) stays out, with its text
tables.

usage: python -I tools/make_release.py ASSETS_DIR [--version 1.0.1]
  ASSETS_DIR is the folder tools/ds1_dlc_build.py wrote (assets_dlc).
"""
import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "DeadSpace2008Randomizer_ConsoleDLC.asi"
TABLE = ROOT / "src" / "console_dlc_generated.inc"
SOURCES = [ROOT / "src" / "dlc" / "ds2008_console_dlc.cpp", ROOT / "src" / "dlc" / "standalone.inc", TABLE,
           ROOT / "src" / "console_dlc.inc", ROOT / "src" / "uniform_slots.inc", ROOT / "src" / "suit_paths.inc"]
README = ROOT / "release" / "README.txt"
STANDALONE_INI = ROOT / "release" / "DeadSpace2008Randomizer_ConsoleDLC.ini"
# The Ultimate ASI Loader, for players without the randomizer (not in the repository)
LOADER = ROOT / "release" / "winmm.dll"
LOADER_LICENSE = ROOT / "release" / "UltimateASILoader_LICENSE.txt"
INSTALL = "ds1_randomizer_assets/dlc/"
LANGUAGES = ("en", "fr", "es", "ss", "ll")


def hash65599(text):
    value = 0
    for c in text.lower():
        value = (value * 65599 + ord(c)) & 0xFFFFFFFF
    return value


def table_streams():
    names = set()
    for line in TABLE.read_text(encoding="ascii").splitlines():
        m = re.match(r'\{(?:true|false), \d+, "([^"]+)", "([^"]+)", \d+\}', line)
        if m:
            names.update(m.groups())
    return names


def pick(assets):
    listed = table_streams()
    files, left_out = [], []
    unlisted_customs = set()
    for path in sorted(assets.iterdir()):
        if path.is_file() and path.suffix == ".str":
            # the suit change loads a model archive with or without the _cm suffix
            if path.stem in listed or (path.stem.endswith("_cm") and path.stem[:-3] in listed):
                files.append(path)
            else:
                left_out.append(path.name)
                if path.stem.startswith("uniCustom_"):
                    unlisted_customs.add(path.stem[len("uniCustom_"):])
    missing = sorted(n for n in listed if not (assets / (n + ".str")).is_file())
    if missing:
        raise SystemExit("the table names archives that are not in %s: %s" % (assets, ", ".join(missing)))
    hidden_texts = {"%08X.str" % hash65599("%s.%s" % (prefix, lang))
                    for prefix in unlisted_customs for lang in LANGUAGES}
    for path in sorted((assets / "text").iterdir()):
        if path.name in hidden_texts:
            left_out.append("text/" + path.name)
        else:
            files.append(path)
    legs = assets / "legs.txt"
    leg_lines = []
    if legs.is_file():
        for line in legs.read_text(encoding="ascii").splitlines():
            if line.startswith("#") or line.split()[0] in listed:
                leg_lines.append(line)
    return files, leg_lines, left_out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("assets", type=Path)
    p.add_argument("--version", default="1.0.1")
    a = p.parse_args()
    if not PLUGIN.is_file():
        raise SystemExit("build the plugin first (build.bat)")
    if not LOADER.is_file():
        raise SystemExit("put the Ultimate ASI Loader's winmm.dll into release/")
    newest = max(s.stat().st_mtime for s in SOURCES)
    if PLUGIN.stat().st_mtime < newest:
        raise SystemExit("%s is older than its sources; rebuild it" % PLUGIN.name)
    files, leg_lines, left_out = pick(a.assets)
    out = ROOT / "dist" / ("DeadSpace2008Randomizer_ConsoleDLC_v%s.zip" % a.version)
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(PLUGIN, "plugins/" + PLUGIN.name)
        z.write(README, "DeadSpace2008Randomizer_ConsoleDLC_README.txt")
        z.write(STANDALONE_INI, STANDALONE_INI.name)
        z.write(LOADER, LOADER.name)
        z.write(LOADER_LICENSE, LOADER_LICENSE.name)
        for path in files:
            z.write(path, INSTALL + path.relative_to(a.assets).as_posix())
        if len(leg_lines) > 1:
            z.writestr(INSTALL + "legs.txt", "\n".join(leg_lines) + "\n")
    print("%s: %d archives" % (out, len(files)))
    if left_out:
        print("left out (not in the table): %s" % ", ".join(left_out))


if __name__ == "__main__":
    sys.exit(main())
