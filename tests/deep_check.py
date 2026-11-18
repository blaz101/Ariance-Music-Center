# Copyright (C) 2026 Roger Barthares
# SPDX-License-Identifier: GPL-3.0-only
"""Deep verification for ariance.py.

Run:  QT_QPA_PLATFORM=offscreen python3 tests/deep_check.py

Every run builds a throw-away home and points ARIANCE_DATA/ARIANCE_CACHE into it, so a
real library, config or device list on this machine can never be touched. The suite
covers the places a regression has actually hurt before: settings surviving a save and
a restart, the config backup, remembered devices and shared presets, the two grids, the
Audiobooks tab, playlists,
smart playlists, multi-folder and selected-item sync, and session restore. Exit code 0
means every check passed.
"""
import atexit
import ast
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import wave

import mutagen

HOME = tempfile.mkdtemp(prefix="ariance-deep-")
os.environ["HOME"] = HOME
DATA = os.path.join(HOME, "Ariance")
CACHE = os.path.join(HOME, ".cache", "Ariance")
os.environ["ARIANCE_DATA"] = DATA
os.environ["ARIANCE_CACHE"] = CACHE
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
atexit.register(shutil.rmtree, HOME, True)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
sys.path.insert(0, ROOT)
sys.path.insert(0, ASSETS)

from mutagen.id3 import ID3, TALB, TCON, TDRC, TIT2, TPE1, TRCK, USLT  # noqa: E402
from mutagen.wave import WAVE  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QTextCursor  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (QApplication, QFileDialog, QInputDialog,  # noqa: E402
                               QLabel, QMessageBox, QPushButton, QToolButton)

import ariance  # noqa: E402

RESULTS = []
SECTION = [""]


def section(name):
    SECTION[0] = name
    print(f"\n== {name}")


def check(name, condition, detail=""):
    ok = bool(condition)
    RESULTS.append((SECTION[0], name, ok, detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + ("" if ok else f"   <- {detail}"))
    return ok


def ffmpeg(*args):
    return subprocess.run(["ffmpeg", "-y", "-v", "error", *args], capture_output=True,
                          text=True)


def write_wav(path, title, artist, album, track, seconds=1.0, year="1992"):
    with wave.open(path, "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(44100)
        n = int(44100 * seconds)
        f.writeframes(b"".join(struct.pack("<hh", int(900 * ((i // 40) % 3)), 0)
                               for i in range(n)))
    audio = WAVE(path)
    if audio.tags is None:
        audio.add_tags()
    audio.tags.add(TIT2(encoding=3, text=title))
    audio.tags.add(TPE1(encoding=3, text=artist))
    audio.tags.add(TALB(encoding=3, text=album))
    audio.tags.add(TRCK(encoding=3, text=str(track)))
    audio.tags.add(TDRC(encoding=3, text=year))
    audio.tags.add(TCON(encoding=3, text="Electronic"))
    audio.save()


def all_items(tree):
    out = []
    stack = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
    while stack:
        item = stack.pop()
        out.append(item)
        stack.extend(item.child(i) for i in range(item.childCount()))
    return out


# ---------------------------------------------------------------- fixtures
MUSIC = os.path.join(HOME, "Music")
ALBUM_A = os.path.join(MUSIC, "Aphex Twin", "Selected Ambient Works")
ALBUM_B = os.path.join(MUSIC, "Boards of Canada", "Music Has the Right")
os.makedirs(ALBUM_A)
os.makedirs(ALBUM_B)
WAV1 = os.path.join(ALBUM_A, "01 - Alpha.wav")
WAV2 = os.path.join(ALBUM_A, "02 - Beta.wav")
FLAC1 = os.path.join(ALBUM_B, "01 - Gamma.flac")
MP3A = os.path.join(ALBUM_B, "01 - Delta.mp3")
write_wav(WAV1, "Alpha", "Aphex Twin", "Selected Ambient Works", 1)
write_wav(WAV2, "Beta", "Aphex Twin", "Selected Ambient Works", 2)
ffmpeg("-i", WAV1, "-c:a", "flac", "-metadata", "title=Gamma", "-metadata",
       "artist=Boards of Canada", "-metadata", "album=Music Has the Right", "-metadata",
       "tracknumber=1", "-metadata", "date=1998", FLAC1)
ffmpeg("-i", WAV2, "-c:a", "libmp3lame", "-b:a", "128k", "-metadata", "title=Delta",
       "-metadata", "artist=MP3 Artist", "-metadata", "album=Compilation", "-metadata",
       "tracknumber=1", MP3A)

AB = os.path.join(HOME, "Audiobooks")
AB_BOOK = os.path.join(AB, "Dune")
os.makedirs(AB_BOOK)
chapters = "".join(f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={i * 3000}\nEND={(i + 1) * 3000}\n"
                   f"title=Chapter {i + 1}\n" for i in range(4))
meta = os.path.join(HOME, "chapters.txt")
with open(meta, "w", encoding="utf-8") as f:
    f.write(";FFMETADATA1\n" + chapters)
ffmpeg("-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "12", "-c:a", "aac",
       os.path.join(HOME, "silence.m4a"))
AB_CH1 = os.path.join(AB_BOOK, "Chapter 01.m4b")
AB_CH2 = os.path.join(AB_BOOK, "Chapter 02.m4b")
for path, title in ((AB_CH1, "Chapter 01"), (AB_CH2, "Chapter 02")):
    ffmpeg("-i", os.path.join(HOME, "silence.m4a"), "-i", meta, "-map_metadata", "1",
           "-c", "copy", "-metadata", f"title={title}", "-metadata",
           "artist=Frank Herbert", "-metadata", "album=Dune", path)
AB_LOOSE = os.path.join(AB, "The Hobbit.m4b")
ffmpeg("-i", os.path.join(HOME, "silence.m4a"), "-c", "copy", "-metadata",
       "title=The Hobbit", "-metadata", "artist=J. R. R. Tolkien", AB_LOOSE)

app = QApplication([])
ariance.install_app_style(app)
ariance.detect_devices = lambda: []
ariance.cd_drive_states = lambda: {}


def fresh_config(**values):
    cfg = json.loads(json.dumps(ariance.DEFAULT_CONFIG))
    cfg.update(values)
    return cfg


# ---------------------------------------------------------------- isolation
section("isolation and version")
check("the suite writes only inside its throw-away home",
      ariance.CONFIG_FILE.startswith(HOME + os.sep) and ariance.DB_FILE.startswith(HOME + os.sep),
      (ariance.CONFIG_FILE, ariance.DB_FILE))
check("the real settings file was not opened",
      not ariance.CONFIG_FILE.startswith("/home/rba/Ariance"), ariance.CONFIG_FILE)
check("file dialogs use the system's native chooser",
      not (ariance.FILE_DIALOG_OPTIONS & QFileDialog.Option.DontUseNativeDialog)
      and ariance.DIRECTORY_DIALOG_OPTIONS == QFileDialog.Option.ShowDirsOnly,
      (ariance.FILE_DIALOG_OPTIONS, ariance.DIRECTORY_DIALOG_OPTIONS))
dialog_source = open(os.path.join(ROOT, "ariance.py"), encoding="utf-8").read()
dialog_calls = [
    node for node in ast.walk(ast.parse(dialog_source))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    and isinstance(node.func.value, ast.Name) and node.func.value.id == "QFileDialog"
    and node.func.attr.startswith("get")]
check("every file dialog call passes the native chooser options",
      len(dialog_calls) == 23 and all(
          any(keyword.arg == "options" and isinstance(keyword.value, ast.Name)
              and keyword.value.id in {"FILE_DIALOG_OPTIONS", "DIRECTORY_DIALOG_OPTIONS"}
              for keyword in call.keywords)
          for call in dialog_calls),
      [(call.func.attr, [keyword.arg for keyword in call.keywords]) for call in dialog_calls])
launcher = open(os.path.join(ROOT, "run.sh"), encoding="utf-8").read()
check("the launcher passes the desktop GTK theme to the native chooser",
      "GTK_THEME" in launcher
      and "org.gnome.desktop.interface gtk-theme" in launcher
      and "color-scheme" in launcher, launcher[:1200])
launcher_assignments = [line.strip() for line in launcher.splitlines()
                        if line.strip().startswith(("XDG_CONFIG_HOME=", "XDG_DATA_HOME="))]
check("the launcher leaves the desktop config and data homes alone",
      not launcher_assignments, launcher_assignments)
check("version is 1.30", ariance.VERSION == "1.30", ariance.VERSION)
readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
check("README title matches the version",
      readme.startswith("# Ariance Music Center 1.30\n"), readme[:40])
check("README has a 1.30 section", "## What's new in 1.30" in readme)
build = open(os.path.join(ROOT, "packaging", "build-deb.sh"), encoding="utf-8").read()
check("the package script builds 1.30", "\nV=1.30\n" in build, build[:200])
check("the package is named after the app", "PKG=ariance-music-center" in build, build[:200])

# ------------------------------------------------------- the move from 1.29
section("the 1.29 folders move to the new name")
legacy = tempfile.mkdtemp(dir=HOME, prefix="legacy-")
old_root = os.path.join(legacy, "Nebula")
os.makedirs(os.path.join(old_root, "settings"))
with open(os.path.join(old_root, "settings", "config.json"), "w", encoding="utf-8") as fh:
    fh.write("{}")
new_root = os.path.join(legacy, "Ariance")
check("the old library is moved, not copied",
      ariance.migrate_legacy_root("ARIANCE_TEST_ROOT", new_root, old_root) == new_root
      and os.path.isfile(os.path.join(new_root, "settings", "config.json"))
      and not os.path.exists(old_root),
      os.listdir(legacy))
os.makedirs(old_root)
open(os.path.join(old_root, "stale.txt"), "w", encoding="utf-8").close()
check("a folder already at the new name wins",
      ariance.migrate_legacy_root("ARIANCE_TEST_ROOT", new_root, old_root) == new_root
      and os.path.isdir(old_root), os.listdir(legacy))
blocked = os.path.join(legacy, "blocked")
open(blocked, "w", encoding="utf-8").close()      # a file where the parent must be
old_root2 = os.path.join(legacy, "Nebula2")
os.makedirs(old_root2)
check("a failed move keeps using the old folder",
      ariance.migrate_legacy_root("ARIANCE_TEST_ROOT",
                                  os.path.join(blocked, "Ariance"), old_root2) == old_root2,
      ariance.migrate_legacy_root("ARIANCE_TEST_ROOT",
                                  os.path.join(blocked, "Ariance"), old_root2))
os.environ["ARIANCE_TEST_ROOT"] = new_root
check("an explicit ARIANCE_DATA-style root is used as given",
      ariance.migrate_legacy_root("ARIANCE_TEST_ROOT",
                                  os.path.join(legacy, "other"), old_root2) == new_root)
del os.environ["ARIANCE_TEST_ROOT"]
launcher_text = open(os.path.join(ROOT, "run.sh"), encoding="utf-8").read()
check("the launcher moves the old folder before it creates the new one",
      launcher_text.index("mv \"$HOME/Nebula\"") < launcher_text.index("mkdir -p \"$CACHE_ROOT/tmp\""),
      launcher_text[:600])

# ---------------------------------------------------------------- config
section("config: defaults, types, backup and recovery")
cfg = ariance.load_config()
check("every default key is present",
      all(k in cfg for k in ariance.DEFAULT_CONFIG), sorted(set(ariance.DEFAULT_CONFIG) - set(cfg)))
check("defaults keep the current UI revision", cfg["ui_revision"] == 43, cfg["ui_revision"])

cfg["library_folders"] = [MUSIC]
cfg["audiobook_folders"] = [AB]
cfg["volume"] = 11
cfg["tab"] = 2
cfg["window"] = [1111, 777]
cfg["device_registry"] = [{"id": "mass:/stick", "name": "Stick", "kind": "mass",
                           "root": "/stick", "uri": ""}]
cfg["device_names"] = {"mass:/stick": "My Stick"}
cfg["collections"] = [{"name": "Music", "folders": [MUSIC], "db": ariance.DB_FILE}]
cfg["active_collection"] = 0
ariance.save_config(cfg)
loaded = ariance.load_config()
check("library folders survive a save and load", loaded["library_folders"] == [MUSIC],
      loaded["library_folders"])
check("collections keep their folder list",
      loaded["collections"][0]["folders"] == [MUSIC], loaded["collections"])
check("remembered devices survive a save and load",
      loaded["device_registry"][0]["id"] == "mass:/stick", loaded["device_registry"])
check("device nicknames survive", loaded["device_names"] == {"mass:/stick": "My Stick"})
check("the audiobook folder list survives", loaded["audiobook_folders"] == [AB])
check("window, tab and volume survive",
      (loaded["window"], loaded["tab"], loaded["volume"]) == ([1111, 777], 2, 11),
      (loaded["window"], loaded["tab"], loaded["volume"]))

# a second save keeps the file it replaced
loaded["volume"] = 22
ariance.save_config(loaded)
backup = json.load(open(ariance.CONFIG_FILE + ".bak", encoding="utf-8"))
check("a save keeps the previous config as config.json.bak", backup["volume"] == 11,
      backup.get("volume"))
check("the backup holds the folders too", backup["library_folders"] == [MUSIC],
      backup.get("library_folders"))

# a truncated write is recovered from the backup instead of starting over
with open(ariance.CONFIG_FILE, "w", encoding="utf-8") as f:
    f.write('{"library_folders": [')
recovered = ariance.load_config()
check("a truncated config is read from the backup",
      recovered["library_folders"] == [MUSIC] and recovered["volume"] == 11,
      (recovered.get("library_folders"), recovered.get("volume")))
check("the recovery brings the devices back too",
      recovered["device_registry"][0]["id"] == "mass:/stick", recovered.get("device_registry"))

# an unreadable config with no backup keeps working with defaults
os.remove(ariance.CONFIG_FILE)
os.remove(ariance.CONFIG_FILE + ".bak")
check("no config at all still starts with defaults",
      ariance.load_config()["library_folders"] == [])
check("saving with no previous file does not fail",
      (ariance.save_config(fresh_config()), os.path.exists(ariance.CONFIG_FILE))[1])

# wrong types are repaired rather than crashing a tab
with open(ariance.CONFIG_FILE, "w", encoding="utf-8") as f:
    json.dump({"library_folders": "Music", "volume": "loud", "window": 12,
               "collections": "nope", "custom_key": {"kept": True}}, f)
repaired = ariance.load_config()
check("a string in place of the folder list is repaired",
      repaired["library_folders"] == [], repaired["library_folders"])
check("a bad number becomes the default", repaired["volume"] == 70, repaired["volume"])
check("an unknown key is left alone", repaired["custom_key"] == {"kept": True})
check("the repaired config has a usable collection",
      repaired["collections"][0]["name"] == "Music", repaired["collections"])

# the 1.07 tab-index migration must not run again, but must still work on old configs
with open(ariance.CONFIG_FILE, "w", encoding="utf-8") as f:
    json.dump({"ui_revision": 0, "tab": 2}, f)
migrated = ariance.load_config()
check("a pre-1.07 tab index moves past the new Audiobooks tab",
      migrated["tab"] == 3 and migrated["ui_revision"] == 43,
      (migrated["tab"], migrated["ui_revision"]))

# defaults filled into an old config must be copies, not shared module state
with open(ariance.CONFIG_FILE, "w", encoding="utf-8") as f:
    json.dump({"library_folders": [MUSIC]}, f)
missing_defaults = ariance.load_config()
missing_defaults["grid_layouts"]["leak"] = {"order": [0, 1], "widths": [10, 20]}
check("a default added to an old config is a private copy",
      "leak" not in ariance.DEFAULT_CONFIG["grid_layouts"],
      ariance.DEFAULT_CONFIG["grid_layouts"])

section("collections")
cols = ariance.migrate_collections(fresh_config())
check("one default collection is created", len(cols) == 1 and cols[0]["name"] == "Music", cols)
cfg = fresh_config()
cfg["collections"] = [{"name": "Music", "folders": [], "db": "a.db"},
                      {"name": "Music", "folders": [], "db": "b.db"},
                      {"name": "", "folders": [], "db": "c.db"},
                      "junk"]
cols = ariance.migrate_collections(cfg)
check("duplicate collection names are made unique",
      [c["name"] for c in cols] == ["Music", "Music 2"], [c["name"] for c in cols])
check("a nameless collection is dropped", len(cols) == 2, cols)
cfg["active_collection"] = 99
check("an out-of-range collection index is clamped",
      ariance.migrate_collections(cfg) and cfg["active_collection"] == 1,
      cfg["active_collection"])
cfg["library_folders"] = [MUSIC]
ariance.store_active_collection(cfg)
check("the active collection's folder list follows the live one",
      cfg["collections"][1]["folders"] == [MUSIC], cfg["collections"])
check("a new collection database lives under library/collections",
      ariance.new_collection_db("Deep Test").startswith(
          os.path.join(ariance.LIBRARY_DIR, "collections") + os.sep))

# ---------------------------------------------------------------- library
section("tags, scanning and the library database")
tags = ariance.read_tags(WAV1)
check("WAV tags are read", tags["title"] == "Alpha" and tags["artist"] == "Aphex Twin",
      tags)
specs = ariance.read_specs(WAV1)
check("WAV specs are read",
      (specs["bits_per_sample"], specs["sample_rate"], specs["channels"]) == (16, 44100, 2),
      specs)
check("FLAC tags are read", ariance.read_tags(FLAC1)["artist"] == "Boards of Canada",
      ariance.read_tags(FLAC1))
check("MP3 tags are read", ariance.read_tags(MP3A)["title"] == "Delta")

section("lyrics: sidecars, embedded tags and source order")
parsed = ariance.parse_lyrics("[ar:Test]\n[offset:100]\n"
                             "[00:01.50][00:03.00]Hello\n[00:02.00]World\n")
check("LRC timestamps, repeats and the offset tag parse",
      parsed["synced"] and parsed["lines"] == [(1600, "Hello"), (2100, "World"),
                                                (3100, "Hello")], parsed)
plain = ariance.parse_lyrics("Plain one\n\nPlain two")
check("plain lyrics keep their paragraphs",
      not plain["synced"] and plain["text"] == "Plain one\n\nPlain two", plain)
sidecar_audio = os.path.join(HOME, "lyrics-sidecar.mp3")
with open(os.path.join(HOME, "lyrics-sidecar.lrc"), "w", encoding="utf-8") as handle:
    handle.write("[00:00.00]Sidecar line one\n[00:02.00]Sidecar line two\n")
check("a case-insensitive LRC sidecar is found",
      ariance.parse_lyrics(ariance.read_lrc_lyrics(sidecar_audio))["text"]
      == "Sidecar line one\nSidecar line two", ariance.read_lrc_lyrics(sidecar_audio))
lyrics_mp3 = os.path.join(HOME, "lyrics-tag.mp3")
shutil.copyfile(MP3A, lyrics_mp3)
audio = mutagen.File(lyrics_mp3)
audio.tags.add(USLT(encoding=3, lang="eng", desc="",
                    text="Embedded line one\nEmbedded line two"))
audio.save()
check("USLT lyrics are read from an MP3",
      ariance.read_embedded_lyrics(lyrics_mp3) == "Embedded line one\nEmbedded line two",
      ariance.read_embedded_lyrics(lyrics_mp3))
lyrics_wav = os.path.join(HOME, "lyrics-tag.wav")
shutil.copyfile(WAV1, lyrics_wav)
audio = mutagen.File(lyrics_wav)
if audio.tags is None:
    audio.add_tags()
audio.tags.add(USLT(encoding=3, lang="eng", desc="", text="WAV line"))
audio.save()
check("USLT lyrics are read from a WAV",
      ariance.read_embedded_lyrics(lyrics_wav) == "WAV line",
      ariance.read_embedded_lyrics(lyrics_wav))
blank_lyrics_audio = os.path.join(HOME, "lyrics-blank.mp3")
shutil.copyfile(MP3A, blank_lyrics_audio)
blank_sidecar = ariance.write_lrc_lyrics(
    blank_lyrics_audio, lines=[(1000, ""), (2000, "Line")])
blank_saved = ariance.read_lrc_lyrics(blank_sidecar)
check("timed empty lines save as clear cues without the editor label",
      blank_saved == "[00:01.00]\n[00:02.00]Line",
      blank_saved)
blank_result = ariance._lyrics_result(blank_saved, "lrc")
check("timed empty lines survive loading a sidecar",
      blank_result is not None
      and blank_result["lines"] == [(1000, ""), (2000, "Line")],
      blank_result)
lyrics_flac = os.path.join(HOME, "lyrics-tag.flac")
shutil.copyfile(FLAC1, lyrics_flac)
audio = mutagen.File(lyrics_flac)
audio["LYRICS"] = "Vorbis line one\nVorbis line two"
audio.save()
check("LYRICS is read from a Vorbis comment",
      ariance.read_embedded_lyrics(lyrics_flac) == "Vorbis line one\nVorbis line two",
      ariance.read_embedded_lyrics(lyrics_flac))
lyrics_m4a = os.path.join(HOME, "lyrics-tag.m4a")
shutil.copyfile(AB_CH1, lyrics_m4a)
audio = mutagen.File(lyrics_m4a)
audio["\xa9lyr"] = "M4A line"
audio.save()
check("©lyr lyrics are read from an M4A",
      ariance.read_embedded_lyrics(lyrics_m4a) == "M4A line",
      ariance.read_embedded_lyrics(lyrics_m4a))
check("the default lyric order puts local sources first",
      ariance.lyric_order(fresh_config()) == ["lrc", "tags", "lrclib", "lyrics_ovh"],
      ariance.lyric_order(fresh_config()))
local_only = fresh_config(lyric_order=[["lrc", True], ["tags", True],
                                       ["lrclib", False], ["lyrics_ovh", False]])
check("lyrics resolve from a sidecar first",
      ariance.resolve_lyrics(sidecar_audio, local_only)["source"] == "lrc",
      ariance.resolve_lyrics(sidecar_audio, local_only))
check("lyrics fall through to the embedded tag",
      ariance.resolve_lyrics(lyrics_mp3, local_only)["source"] == "tags",
      ariance.resolve_lyrics(lyrics_mp3, local_only))
calls = []
def fake_lyrics_get(url, timeout=8):
    calls.append(url)
    return json.dumps({"instrumental": False,
                       "syncedLyrics": "[00:01.00]Online line\n[00:03.00]Online two",
                       "plainLyrics": "Online line\nOnline two"}).encode("utf-8")
real_lyrics_get = ariance._lyrics_http_get
ariance._lyrics_http_get = fake_lyrics_get
try:
    remote = ariance.lookup_lrclib(lyrics_mp3)
finally:
    ariance._lyrics_http_get = real_lyrics_get
check("LRCLIB exact lookup returns synchronized lyrics",
      remote and remote["source"] == "lrclib"
      and remote["lines"] == [(1000, "Online line"), (3000, "Online two")]
      and "/api/get?" in calls[0] and "duration=1" in calls[0],
      (remote, calls))


def fake_search_lyrics_get(url, timeout=8):
    if "/api/get?" in url:
        raise ariance.urllib.error.HTTPError(url, 404, "Not Found", {}, None)
    return json.dumps([
        {"id": 1, "trackName": "Delta", "artistName": "MP3 Artist",
         "albumName": "First", "duration": 1, "instrumental": False,
         "syncedLyrics": "[00:01.00]First version", "plainLyrics": "First version"},
        {"id": 2, "trackName": "Delta", "artistName": "MP3 Artist",
         "albumName": "Second", "duration": 2, "instrumental": False,
         "syncedLyrics": "[00:02.00]Second version", "plainLyrics": "Second version"},
        {"id": 3, "trackName": "Delta", "artistName": "MP3 Artist",
         "albumName": "Third", "duration": 10, "instrumental": False,
         "syncedLyrics": "[00:01.00]Long version", "plainLyrics": "Plain long version"},
    ]).encode("utf-8")
remote_only = fresh_config(lyric_order=[["lrc", False], ["tags", False],
                                        ["lrclib", True], ["lyrics_ovh", False]])
ariance._lyrics_http_get = fake_search_lyrics_get
try:
    match_result = ariance.resolve_lyrics(lyrics_mp3, remote_only)
finally:
    ariance._lyrics_http_get = real_lyrics_get
check("multiple LRCLIB matches are offered as choices",
      match_result and len(match_result.get("choices") or []) == 3
      and [choice["label"] for choice in match_result["choices"]]
      == ["Delta - MP3 Artist · First (0:01)", "Delta - MP3 Artist · Second (0:02)",
          "Delta - MP3 Artist · Third (0:10) · unsynced (length differs)"],
      match_result)
check("a length-mismatched match uses its plain lyrics",
      match_result["choices"][2]["result"].get("duration_mismatch")
      and match_result["choices"][2]["result"]["text"] == "Plain long version"
      and not match_result["choices"][2]["result"]["lines"],
      match_result["choices"][2]["result"])
ariance.forget_lyrics_match(lyrics_mp3)
check("lyric shifts default to zero and save per track",
      ariance.get_lyrics_offset(lyrics_mp3) == 0.0
      and ariance.save_lyrics_offset(lyrics_mp3, 1.25)
      and abs(ariance.get_lyrics_offset(lyrics_mp3) - 1.25) < 1e-9,
      ariance.get_lyrics_offset(lyrics_mp3))
ariance._LYRICS_MATCH_CACHE = None
check("a lyric shift reloads from disk",
      abs(ariance.get_lyrics_offset(lyrics_mp3) - 1.25) < 1e-9,
      ariance.get_lyrics_offset(lyrics_mp3))
check("saving a match keeps the track's lyric shift",
      ariance.save_lyrics_match(lyrics_mp3, 8, "Shifted match")
      and abs(ariance.get_lyrics_offset(lyrics_mp3) - 1.25) < 1e-9,
      ariance.get_lyrics_match(lyrics_mp3))
check("a zero shift removes only the shift",
      ariance.save_lyrics_offset(lyrics_mp3, 0)
      and ariance.get_lyrics_offset(lyrics_mp3) == 0.0
      and (ariance.get_lyrics_match(lyrics_mp3) or {}).get("id") == 8,
      ariance.get_lyrics_match(lyrics_mp3))
ariance.forget_lyrics_match(lyrics_mp3)
check("a chosen LRCLIB match is saved for its track",
      ariance.save_lyrics_match(lyrics_mp3, 2, "Second")
      and (ariance.get_lyrics_match(lyrics_mp3) or {}).get("id") == 2,
      ariance.get_lyrics_match(lyrics_mp3))
ariance._LYRICS_MATCH_CACHE = None
check("a saved match reloads from disk",
      (ariance.get_lyrics_match(lyrics_mp3) or {}).get("id") == 2,
      ariance.get_lyrics_match(lyrics_mp3))
saved_calls = []
def fake_saved_lyrics_get(url, timeout=8):
    saved_calls.append(url)
    return json.dumps({"id": 2, "trackName": "Delta", "artistName": "MP3 Artist",
                       "albumName": "Second", "duration": 2, "instrumental": False,
                       "syncedLyrics": "[00:02.00]Saved version",
                       "plainLyrics": "Saved version"}).encode("utf-8")
ariance._lyrics_http_get = fake_saved_lyrics_get
try:
    saved_result = ariance.lookup_lrclib(lyrics_mp3)
finally:
    ariance._lyrics_http_get = real_lyrics_get
check("a saved match is fetched by its LRCLIB id",
      saved_result and saved_result.get("saved_match")
      and saved_result.get("lrclib_id") == 2
      and saved_result.get("lines") == [(2000, "Saved version")]
      and saved_calls == ["https://lrclib.net/api/get/2"],
      (saved_result, saved_calls))
ariance.forget_lyrics_match(lyrics_mp3)

section("tag writes: every field and format")
tag_values = {
    "title": "Matrix Title", "artist": "Matrix Artist", "album": "Matrix Album",
    "albumartist": "Matrix Album Artist", "tracknumber": "3/12",
    "discnumber": "1/2", "date": "2024", "genre": "Rock",
    "composer": "Matrix Composer", "comment": "Matrix Comment",
}
tag_sources = {
    "FLAC": (FLAC1, ".flac"),
    "M4A": (AB_CH1, ".m4a"),
    "MP3": (MP3A, ".mp3"),
    "WAV": (WAV1, ".wav"),
}
for label, (source, ext) in tag_sources.items():
    target = os.path.join(HOME, "matrix-" + label.lower() + ext)
    shutil.copyfile(source, target)
    skipped = ariance.write_tags(target, dict(tag_values))
    core = ariance.read_tags(target)
    extra = ariance.read_extra_tags(target)
    missing = [key for key, value in tag_values.items()
               if (extra.get(key, "") if key == "comment" else core.get(key, "")) != value]
    check(f"{label}: every tag writes and reads back", not skipped and not missing,
          (skipped, missing, core, extra))
    skipped = ariance.write_tags(target, {key: "" for key in tag_values})
    core = ariance.read_tags(target)
    extra = ariance.read_extra_tags(target)
    still = [key for key in tag_values
             if (extra.get(key, "") if key == "comment" else core.get(key, ""))]
    check(f"{label}: every tag clears again", not skipped and not still,
          (skipped, still, core, extra))

db_file = os.path.join(HOME, "library.db")
library = ariance.Library(db_file)
library.scan([MUSIC])
check("the scan indexes every track", library.count() == 4, library.count())
rows = library.tracks(order_by="title")
check("tracks come back ordered", [r["title"] for r in rows][:2] == ["Alpha", "Beta"],
      [r["title"] for r in rows])
check("the library knows a path", FLAC1 in library.by_path())
library.scan([MUSIC])
check("a rescan keeps the same track count", library.count() == 4, library.count())
ariance.save_lyrics_match(WAV1, 7, "Alpha match")
ariance.save_lyrics_offset(WAV1, 1.5)
gone = library.forget_prefix(ALBUM_A)
library.rescan = None
check("forgetting a folder drops only its tracks and its saved lyrics state",
      gone == 2 and library.count() == 2 and ariance.get_lyrics_match(WAV1) is None
      and ariance.get_lyrics_offset(WAV1) == 0.0,
      (gone, library.count(), ariance.get_lyrics_match(WAV1),
       ariance.get_lyrics_offset(WAV1)))
ariance.save_lyrics_match(lyrics_mp3, 9, "Removed match")
ariance.save_lyrics_offset(lyrics_mp3, 2.0)
library.remove_paths([lyrics_mp3])
check("removing a track from the library forgets its saved lyrics state",
      ariance.get_lyrics_match(lyrics_mp3) is None
      and ariance.get_lyrics_offset(lyrics_mp3) == 0.0,
      (ariance.get_lyrics_match(lyrics_mp3), ariance.get_lyrics_offset(lyrics_mp3)))
library.scan([MUSIC])
check("a rescan brings a forgotten folder back", library.count() == 4, library.count())

section("playlists and smart playlists")
playlists = ariance.PlaylistStore(lambda: [MUSIC])
playlists.write("Mix", [WAV1, FLAC1])
raw = open(playlists.path("Mix"), encoding="utf-8").read().splitlines()
check("a playlist starts with #EXTM3U", raw[0] == "#EXTM3U", raw[:2])
check("a playlist stores portable paths",
      raw[1] == os.path.join("Aphex Twin", "Selected Ambient Works", "01 - Alpha.wav"),
      raw[1:])
check("a playlist reads back to absolute paths", playlists.read("Mix") == [WAV1, FLAC1],
      playlists.read("Mix"))
external = os.path.join(HOME, "external.m3u8")
with open(external, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n" + MP3A + "\n")
imported = playlists.import_file(external)
check("an external .m3u8 is imported", imported and playlists.read(imported) == [MP3A],
      imported)
check("a playlist can be renamed", playlists.rename(imported, "Imported")
      and playlists.read("Imported") == [MP3A])
playlists.remove("Imported")
check("a playlist can be deleted", "Imported" not in playlists.names())

store = ariance.SmartStore(library)
never = next(p for p in ariance.SMART_PRESETS if p["name"] == "Never Played")
check("a smart playlist runs against the real library",
      len(store.preset_tracks(library, never)) == 4,
      len(store.preset_tracks(library, never)))
where, params = ariance.build_smart_where(
    [{"field": "artist", "op": "contains", "value": "Aphex"}])
check("the rule builder returns parameterised SQL", "?" in where and params == ["%Aphex%"],
      (where, params))
check("the rule builder query runs",
      [r["title"] for r in library.tracks(where=where, args=params)] == ["Alpha", "Beta"],
      library.tracks(where=where, args=params))
where, params = ariance.parse_filter("artist:Aphex")
check("the filter language parses a field",
      where and [r["title"] for r in library.tracks(where=where, args=params)][:2]
      == ["Alpha", "Beta"], (where, params))

# ---------------------------------------------------------------- main window
section("main window, menus and the two regressions")
boot = fresh_config()
boot["library_folders"] = [MUSIC]
boot["audiobook_folders"] = [AB]
boot["collections"] = [{"name": "Music", "folders": [MUSIC], "db": ariance.DB_FILE}]
boot["device_registry"] = [{"id": "mass:/stick", "name": "Stick", "kind": "mass",
                            "root": "/stick", "uri": ""}]
boot["device_names"] = {"mass:/stick": "My Stick"}
ariance.save_config(boot)

w = ariance.MainWindow()
w.show()
app.processEvents()
check("the main window is titled Ariance Music Center",
      w.windowTitle() == ariance.APP_NAME == "Ariance Music Center",
      (w.windowTitle(), ariance.APP_NAME))
titles = [w.tabs.tabText(i) for i in range(w.tabs.count())]
check("the tabs are Music, Audiobooks, Tags, Devices, Syncing",
      titles == ["Music", "Audiobooks", "Tags", "Devices", "Syncing"], titles)
# A window that insists on being taller than the display gets its bottom cut off:
# the Syncing form alone used to force 1017 px, more than a 1000 px screen.
check("the window's minimum fits a 1366x768 laptop",
      w.minimumSizeHint().height() <= 700, w.minimumSizeHint().height())
check("the Syncing page scrolls instead of forcing the window taller",
      w.tabs.widget(4).minimumSizeHint().height() < 200,
      w.tabs.widget(4).minimumSizeHint().height())
_screen = ariance.QApplication.primaryScreen().availableGeometry()
w.config["window"] = [9999, 9999]
w._restore_window_size()
check("a saved window larger than the screen is clamped to it",
      w.width() <= _screen.width() and w.height() <= _screen.height(),
      (w.width(), w.height(), _screen.width(), _screen.height()))
w.config["window"] = [1360, 860]
w._restore_window_size()
w.resize(1200, 700)
check("the window can be made 700 px tall", w.height() == 700, w.height())
w.resize(1360, 860)
w.library_tab.refresh()
w.audiobooks_tab.refresh()
app.processEvents()


def menu_titles():
    return [a.text().replace("&", "") for a in w.menuBar().actions()]


check("the Music tab shows the player menus",
      menu_titles() == ["Music", "Playlist", "Tools", "Playback", "Help"], menu_titles())
w.tabs.setCurrentWidget(w.audiobooks_tab)
app.processEvents()
check("the Audiobooks tab hides the music player bar", w.player.isHidden())
check("the Audiobooks tab shows its own player bar",
      not w.audiobooks_tab.ab_player.isHidden())
w.tabs.setCurrentWidget(w.library_tab)
check("leaving Audiobooks brings the music player bar back", not w.player.isHidden())
stop_calls = []
real_stop = w.player.pause_playback
w.player.pause_playback = lambda: stop_calls.append(True)
w.tabs.setCurrentWidget(w.audiobooks_tab)
check("switching to Audiobooks pauses music", bool(stop_calls))
w.player.pause_playback = real_stop
check("the Audiobooks tab has its own menu set",
      menu_titles() == ["Audiobooks", "Playlist", "Tools", "Playback", "Help"],
      menu_titles())
playback_menu = next(a.menu() for a in w.menuBar().actions()
                     if a.text().replace("&", "") == "Playback")
playback_actions = [a.text() for a in playback_menu.actions() if a.text()]
check("Playback holds stop-after, gapless, crossfade and the sleep timer",
      playback_actions == ["Stop after this track", "Gapless playback", "Crossfade…",
                           "Sleep timer…", "Cancel sleep timer"],
      playback_actions)
check("the Tools menu no longer holds the sleep timer",
      "Sleep timer…" not in [a.text() for a in
                             next(a.menu() for a in w.menuBar().actions()
                                  if a.text().replace("&", "") == "Tools").actions()],
      [a.text() for a in next(a.menu() for a in w.menuBar().actions()
                              if a.text().replace("&", "") == "Tools").actions()])
w._playback_after.setChecked(True)
w._playback_gapless.setChecked(True)
check("the Playback actions drive the player",
      w.player.stop_after and w.player.gapless,
      (w.player.stop_after, w.player.gapless))
w._playback_after.setChecked(False)
w._playback_gapless.setChecked(False)
crossfade = ariance.CrossfadeDialog(w.player, w)
crossfade.spin.setValue(2.5)
check("the crossfade window updates the player and config",
      abs(w.player.crossfade_seconds - 2.5) < 0.01
      and abs(w.config["crossfade_seconds"] - 2.5) < 0.01,
      (w.player.crossfade_seconds, w.config.get("crossfade_seconds")))
w._sync_playback_menu()
check("the Playback menu shows the crossfade length",
      w._playback_crossfade.text() == "Crossfade… (2.5 s)",
      w._playback_crossfade.text())
crossfade.close()
w.player.set_crossfade(0)
w.player.set_queue([sidecar_audio], start=0)
lyrics_dialog = ariance.LyricsDialog(w.player, fresh_config(
    lyric_order=[["lrc", True], ["tags", False], ["lrclib", False], ["lyrics_ovh", False]]), w)
lyrics_dialog.show()
for _attempt in range(50):
    app.processEvents()
    if lyrics_dialog.source_label.text() != "Looking for lyrics…":
        break
    QTest.qWait(100)

def lyric_text(index):
    item = lyrics_dialog.list.item(index)
    if item is None:
        return ""
    widget = lyrics_dialog.list.itemWidget(item)
    label = widget.findChild(QLabel, "LyricText") if widget is not None else None
    return label.text() if label is not None else item.text()

def lyric_item_for(millis):
    for index in range(lyrics_dialog.list.count()):
        item = lyrics_dialog.list.item(index)
        if item is not None and item.data(Qt.ItemDataRole.UserRole) == millis:
            return item
    return None

check("the lyrics window uses the compact wider layout",
      lyrics_dialog.windowTitle() == "Lyrics - Ariance Music Center"
      and lyrics_dialog.width() >= 775
      and lyrics_dialog.height() <= 460,
      (lyrics_dialog.windowTitle(), lyrics_dialog.width(), lyrics_dialog.height()))
check("the unchanged LRC has a disabled Save and Revert",
      lyrics_dialog.save_lrc_btn.text() == "Save"
      and not lyrics_dialog.save_lrc_btn.isEnabled()
      and lyrics_dialog.revert_btn.text() == "Revert"
      and not lyrics_dialog.revert_btn.isEnabled(),
      (lyrics_dialog.save_lrc_btn.text(), lyrics_dialog.save_lrc_btn.isEnabled(),
       lyrics_dialog.revert_btn.text(), lyrics_dialog.revert_btn.isEnabled()))
check("the synced view keeps the helper note out of the way",
      not lyrics_dialog.note.isVisible(), lyrics_dialog.note.isVisible())
check("the lyrics window shows a three-line synced view centered on the current line",
      lyrics_dialog.source_label.text() == "LRC file · synced"
      and lyrics_dialog.list.count() == 3
      and lyric_text(0) == ""
      and lyric_text(1) == "Sidecar line one"
      and lyric_text(2) == "Sidecar line two",
      (lyrics_dialog.source_label.text(), lyrics_dialog.list.count(),
       [lyric_text(i) for i in range(lyrics_dialog.list.count())]))
lyrics_dialog._show_result({"source": "lrc", "lines": [(0, ""), (15000, "Next line")]})
check("the lyrics window shows a blank line as a live countdown",
      lyrics_dialog.list.count() == 3
      and lyric_text(0) == ""
      and lyric_text(1) == "Next lyric in 15.0s"
      and lyric_text(2) == "Next line",
      [lyric_text(i) for i in range(lyrics_dialog.list.count())])
check("the lyrics window has a hundredth-second shift control",
      lyrics_dialog.offset_spin.minimum() == -4.0
      and lyrics_dialog.offset_spin.maximum() == 4.0
      and lyrics_dialog.offset_spin.decimals() == 2
      and abs(lyrics_dialog.offset_spin.singleStep() - 0.01) < 1e-9,
      (lyrics_dialog.offset_spin.minimum(), lyrics_dialog.offset_spin.maximum(),
       lyrics_dialog.offset_spin.decimals(), lyrics_dialog.offset_spin.singleStep()))
ariance.forget_lyrics_match(lyrics_mp3)
lyrics_dialog._lyrics_path = lyrics_mp3
lyrics_dialog.offset_spin.setValue(1.5)
check("the lyrics window saves a per-track shift",
      abs(ariance.get_lyrics_offset(lyrics_mp3) - 1.5) < 1e-9,
      ariance.get_lyrics_offset(lyrics_mp3))
lyrics_dialog._render(match_result or {})
shifted_item = lyric_item_for(2500)
check("a positive shift moves synced timestamps later",
      shifted_item is not None
      and "shift +1.50 s" in lyrics_dialog.source_label.text(),
      (shifted_item.data(Qt.ItemDataRole.UserRole) if shifted_item else None,
       lyrics_dialog.source_label.text()))
check("the lyrics window lists multiple LRCLIB matches",
      lyrics_dialog.match_row.isVisible()
      and lyrics_dialog.match_combo.count() == 3
      and "First version" in [lyric_text(i)
                               for i in range(lyrics_dialog.list.count())],
      (lyrics_dialog.match_combo.count(),
       [lyric_text(i) for i in range(lyrics_dialog.list.count())]))
check("the first match is saved for the track",
      (ariance.get_lyrics_match(lyrics_mp3) or {}).get("id") == 1,
      ariance.get_lyrics_match(lyrics_mp3))
lyrics_dialog.match_combo.setCurrentIndex(1)
check("choosing another match switches the lyrics",
      "Second version" in [lyric_text(i)
                            for i in range(lyrics_dialog.list.count())]
      and lyric_item_for(3500) is not None,
      ([lyric_text(i) for i in range(lyrics_dialog.list.count())],
       lyric_item_for(3500) is not None))
lyrics_dialog.match_combo.setCurrentIndex(2)
check("a length-mismatched match shows its plain lyrics",
      lyric_text(0) == "Plain long version"
      and "unsynced (length differs)" in lyrics_dialog.source_label.text()
      and "not synchronized" in lyrics_dialog.note.text(),
      (lyrics_dialog.source_label.text(), lyrics_dialog.note.text(),
       [lyric_text(i) for i in range(lyrics_dialog.list.count())]))
check("choosing a match replaces the saved one",
      (ariance.get_lyrics_match(lyrics_mp3) or {}).get("id") == 3,
      ariance.get_lyrics_match(lyrics_mp3))
lyrics_dialog.match_combo.setCurrentIndex(0)
lrc_target = os.path.splitext(lyrics_mp3)[0] + ".lrc"
check("Save as LRC is offered for a local track",
      lyrics_dialog.save_lrc_btn.text() == "Save as LRC"
      and lyrics_dialog.save_lrc_btn.isEnabled(),
      (lyrics_dialog.save_lrc_btn.text(),
       lyrics_dialog.save_lrc_btn.isEnabled(), lyrics_dialog._lyrics_path))
lyrics_dialog.save_lrc_btn.click()
with open(lrc_target, encoding="utf-8") as handle:
    saved_lrc = handle.read()
check("Save as LRC writes adjusted timestamps beside the audio",
      saved_lrc.startswith("[00:02.50]First version")
      and lyrics_dialog.source_label.text() == "LRC file · synced"
      and lyric_item_for(2500) is not None,
      (saved_lrc, lyrics_dialog.source_label.text(),
       lyric_item_for(2500) is not None))
check("saving as LRC clears the now-baked-in shift",
      lyrics_dialog.offset_spin.value() == 0.0
      and ariance.get_lyrics_offset(lyrics_mp3) == 0.0,
      (lyrics_dialog.offset_spin.value(), ariance.get_lyrics_offset(lyrics_mp3)))
check("matching LRC disables Save as LRC",
      lyrics_dialog.save_lrc_btn.text() == "Save"
      and not lyrics_dialog.save_lrc_btn.isEnabled()
      and not lyrics_dialog.revert_btn.isEnabled()
      and lyrics_dialog.source_label.text() == "LRC file · synced",
      (lyrics_dialog.save_lrc_btn.text(), lyrics_dialog.save_lrc_btn.isEnabled(),
       lyrics_dialog.revert_btn.isEnabled(), lyrics_dialog.source_label.text()))
with open(lrc_target, "w", encoding="utf-8") as handle:
    handle.write("[ar:Test Artist]\n[00:02.50]First version\n")
line_item = lyric_item_for(2500)
line_widget = lyrics_dialog.list.itemWidget(line_item) if line_item else None
line_buttons = line_widget.findChildren(QToolButton) if line_widget else []
line_adjustment = (line_widget.findChild(QLabel, "LyricAdjustment")
                   if line_widget else None)
check("each synchronized lyric line shows its adjustment and controls",
      len(line_buttons) == 2
      and sorted(button.text() for button in line_buttons) == ["+", "-"]
      and line_adjustment is not None
      and line_adjustment.text() == "[+0.00]",
      ([button.text() for button in line_buttons],
       line_adjustment.text() if line_adjustment is not None else None))
plus = next((button for button in line_buttons if button.text() == "+"), None)
if plus is not None:
    plus.click()
QTest.qWait(10)
line_item = lyric_item_for(2510)
line_widget = lyrics_dialog.list.itemWidget(line_item) if line_item else None
line_adjustment = (line_widget.findChild(QLabel, "LyricAdjustment")
                   if line_widget else None)
check("a line adjustment moves only that line's timestamp",
      lyric_item_for(2510) is not None
      and line_adjustment is not None
      and line_adjustment.text() == "[+0.01]"
      and lyrics_dialog.save_lrc_btn.text() == "Save"
      and lyrics_dialog.save_lrc_btn.isEnabled()
      and lyrics_dialog.revert_btn.isEnabled()
      and "line edits" in lyrics_dialog.source_label.text(),
      (lyric_item_for(2510) is not None,
       line_adjustment.text() if line_adjustment is not None else None,
       lyrics_dialog.save_lrc_btn.text(), lyrics_dialog.save_lrc_btn.isEnabled(),
       lyrics_dialog.revert_btn.isEnabled(), lyrics_dialog.source_label.text()))
lyrics_dialog.save_lrc_btn.click()
with open(lrc_target, encoding="utf-8") as handle:
    updated_lrc = handle.read()
check("saving an existing LRC updates timestamps and keeps metadata",
      updated_lrc == "[ar:Test Artist]\n[00:02.51]First version\n"
      and lyrics_dialog.save_lrc_btn.text() == "Save"
      and lyrics_dialog.source_label.text() == "LRC file · synced"
      and not lyrics_dialog.save_lrc_btn.isEnabled()
      and not lyrics_dialog.revert_btn.isEnabled(),
      (updated_lrc, lyrics_dialog.save_lrc_btn.text(),
       lyrics_dialog.source_label.text(),
       lyrics_dialog.save_lrc_btn.isEnabled(), lyrics_dialog.revert_btn.isEnabled()))
line_item = lyric_item_for(2510)
line_widget = lyrics_dialog.list.itemWidget(line_item) if line_item else None
line_buttons = line_widget.findChildren(QToolButton) if line_widget else []
plus = next((button for button in line_buttons if button.text() == "+"), None)
if plus is not None:
    plus.click()
QTest.qWait(10)
check("changes after saving offer Revert",
      lyric_item_for(2520) is not None
      and lyrics_dialog.save_lrc_btn.isEnabled()
      and lyrics_dialog.revert_btn.isEnabled(),
      (lyric_item_for(2520) is not None,
       lyrics_dialog.save_lrc_btn.isEnabled(), lyrics_dialog.revert_btn.isEnabled()))
lyrics_dialog.revert_btn.click()
QTest.qWait(10)
check("Revert restores the LRC file and disables both buttons",
      lyric_item_for(2510) is not None
      and not lyrics_dialog.save_lrc_btn.isEnabled()
      and not lyrics_dialog.revert_btn.isEnabled()
      and lyrics_dialog.save_lrc_btn.text() == "Save",
      (lyric_item_for(2510) is not None,
       lyrics_dialog.save_lrc_btn.isEnabled(), lyrics_dialog.revert_btn.isEnabled(),
       lyrics_dialog.save_lrc_btn.text()))
ariance.forget_lyrics_match(lyrics_mp3)
lyrics_dialog.close()
w.player.set_queue([])

section("lyrics editor")
editor = ariance.LyricsEditorDialog(w.library, w.config, w.player, w)
check("the lyrics editor has the reference tabs and a song chooser",
      hasattr(editor, "song_btn")
      and [editor.editor_tabs.tabText(i) for i in range(editor.editor_tabs.count())]
      == ["Lyrics", "Syncer", "Preview", "Metadata", "Save"],
      (hasattr(editor, "song_btn"),
       [editor.editor_tabs.tabText(i) for i in range(editor.editor_tabs.count())]))
chooser = ariance.LyricsSongChooserDialog(library, w.config, WAV1, w)
check("the song chooser has a full-width library search",
      chooser.search.placeholderText() == "Search the library"
      and chooser.search.isVisibleTo(chooser),
      (chooser.search.placeholderText(), chooser.search.isVisibleTo(chooser)))
chooser.search.setText("Gamma")
app.processEvents()
search_paths = []
stack = [chooser.tree.topLevelItem(i)
         for i in range(chooser.tree.topLevelItemCount())]
while stack:
    item = stack.pop()
    if item.data(0, ariance.LyricsSongChooserDialog.KIND_ROLE) == "file":
        search_paths.append(item.data(0, ariance.LyricsSongChooserDialog.PATH_ROLE))
    stack.extend(item.child(i) for i in range(item.childCount()))
check("searching the song chooser finds library tracks",
      FLAC1 in search_paths,
      search_paths)
chooser.search.clear()
app.processEvents()
chooser_roots = [chooser.tree.topLevelItem(i)
                 for i in range(chooser.tree.topLevelItemCount())]
music_root = next((item for item in chooser_roots
                   if item.data(0, ariance.LyricsSongChooserDialog.PATH_ROLE) == MUSIC), None)
check("the song chooser shows only music library folders",
      music_root is not None and chooser.selected_path() == WAV1
      and all(item.data(0, ariance.LyricsSongChooserDialog.PATH_ROLE) != AB
              for item in chooser_roots),
      ([(item.text(0), item.data(0, ariance.LyricsSongChooserDialog.PATH_ROLE))
        for item in chooser_roots], chooser.selected_path()))
if music_root is not None:
    stack = [music_root]
    while stack:
        item = stack.pop()
        if item.data(0, ariance.LyricsSongChooserDialog.KIND_ROLE) == "dir":
            item.setExpanded(True)
            app.processEvents()
        stack.extend(item.child(i) for i in range(item.childCount()))
chooser_paths = []
stack = [chooser.tree.topLevelItem(i) for i in range(chooser.tree.topLevelItemCount())]
while stack:
    item = stack.pop()
    if item.data(0, ariance.LyricsSongChooserDialog.KIND_ROLE) == "file":
        chooser_paths.append(item.data(0, ariance.LyricsSongChooserDialog.PATH_ROLE))
    stack.extend(item.child(i) for i in range(item.childCount()))
check("the song chooser lazy-loads tracks inside folders",
      WAV1 in chooser_paths and len(chooser_paths) >= 4,
      chooser_paths)
chooser.close()
editor._load_track(lyrics_mp3)
check("the lyrics editor opens an existing LRC",
      editor.table.rowCount() == 1
      and editor.table.item(0, 1).text() == "[00:02.51]"
      and editor.table.item(0, 2).text() == "First version",
      (editor.table.rowCount(),
       editor.table.item(0, 1).text() if editor.table.rowCount() else "",
       editor.table.item(0, 2).text() if editor.table.rowCount() else ""))
check("the lyrics editor loads LRC metadata and defaults Tool to Ariance Music Center",
      editor.meta_fields["ar"][0].isChecked()
      and editor.meta_fields["ar"][1].text() == "Test Artist"
      and editor.meta_fields["tool"][0].isChecked()
      and editor.meta_fields["tool"][1].text() == ariance.APP_NAME,
      (editor.meta_fields["ar"][0].isChecked(),
       editor.meta_fields["ar"][1].text(),
       editor.meta_fields["tool"][0].isChecked(),
       editor.meta_fields["tool"][1].text()))
editor._apply_lyrics_text("[tool:SubtitleTools.com]\n[00:01.00]Line A")
check("a pasted Tool header cannot replace Ariance Music Center",
      editor.meta_fields["tool"][1].text() == ariance.APP_NAME
      and editor.table.rowCount() == 1,
      (editor.meta_fields["tool"][1].text(), editor.table.rowCount()))
editor._apply_lyrics_text("[00:01.00]Line A\n[00:03.50]Line B")
check("pasted timestamps become the line times",
      editor.table.rowCount() == 2
      and editor.table.item(0, 1).text() == "[00:01.00]"
      and editor.table.item(1, 1).text() == "[00:03.50]"
      and editor.table.item(0, 2).text() == "Line A",
      [(editor.table.item(i, 1).text(), editor.table.item(i, 2).text())
       for i in range(editor.table.rowCount())])
check("the Lyrics tab is one plain-text document without row boxes",
      isinstance(editor.lyrics_text, ariance.QPlainTextEdit)
      and not editor.lyrics_text.isReadOnly()
      and editor.table.isHidden()
      and editor.lyrics_text.toPlainText() == "[00:01.00] Line A\n[00:03.50] Line B",
      (type(editor.lyrics_text).__name__, editor.lyrics_text.isReadOnly(),
       editor.table.isHidden(), editor.lyrics_text.toPlainText()))
check("Tab 1 has no separate Paste lyrics button", not hasattr(editor, "paste_btn"),
      hasattr(editor, "paste_btn"))
editor.lyrics_text.moveCursor(QTextCursor.MoveOperation.Start)
editor.lyrics_text.moveCursor(QTextCursor.MoveOperation.Down)
app.processEvents()
check("the plain-text caret selects the matching Syncer line",
      editor.table.currentRow() == 1,
      (editor.lyrics_text.textCursor().blockNumber(), editor.table.currentRow()))
editor.lyrics_text.setPlainText("[00:01.00]Line A\n[00:04.00]Typed line")
app.processEvents()
check("editing the plain text updates the timed lyric rows",
      editor.table.rowCount() == 2
      and editor.table.item(1, 1).text() == "[00:04.00]"
      and editor.table.item(1, 2).text() == "Typed line",
      [(editor.table.item(i, 1).text(), editor.table.item(i, 2).text())
       for i in range(editor.table.rowCount())])
editor._apply_lyrics_text("[00:01.00]Line A\n[00:03.50]Line B")
editor.table.setCurrentCell(0, 2)
editor._set_time_to_current()
app.processEvents()
check("R sets the current timestamp and advances to the next line",
      editor.table.currentRow() == 1 and editor.sync_list.currentRow() == 1,
      (editor.table.currentRow(), editor.sync_list.currentRow(),
       editor.table.item(0, 1).text()))
editor._apply_lyrics_text("[00:01.00]Line A\n[00:03.50]Line B")
editor.table.setCurrentCell(1, 2)
editor._insert_line()
app.processEvents()
check("T adds an untimed blank line in the gap before the current line",
      editor.table.rowCount() == 3
      and editor.table.currentRow() == 1
      and editor.table.item(1, 1).text() == ""
      and editor.table.item(1, 2).text() == ""
      and editor.sync_list.item(1).text().strip() == "--:--.--"
      and editor.lyrics_text.toPlainText()
      == "[00:01.00] Line A\n\n[00:03.50] Line B",
      ([(editor.table.item(i, 1).text(), editor.table.item(i, 2).text())
        for i in range(editor.table.rowCount())],
       editor.lyrics_text.toPlainText(), editor.sync_list.item(1).text()))
editor._apply_lyrics_text("[00:01.00]Line A\n[00:03.50]Line B")
editor.table.setCurrentCell(1, 2)
editor._insert_line(empty=True)
app.processEvents()
check("Y inserts a clear line before the current line",
      editor.table.rowCount() == 3
      and editor.table.currentRow() == 2
      and editor.table.item(1, 1).text().startswith("[")
      and editor.table.item(1, 2).text() == ""
      and editor.sync_list.count() == 3
      and "- clear previous lyric -" in editor.sync_list.item(1).text(),
      ([(editor.table.item(i, 1).text(), editor.table.item(i, 2).text())
        for i in range(editor.table.rowCount())],
       editor.sync_list.item(1).text() if editor.sync_list.count() > 1 else ""))
editor._apply_lyrics_text("[00:01.00]Line A\n[00:03.50]Line B")
check("the Syncer tab mirrors the lyric rows and follows selection",
      editor.sync_list.count() == 2
      and "00:01.00" in editor.sync_list.item(0).text()
      and "Line A" in editor.sync_list.item(0).text(),
      [editor.sync_list.item(i).text() for i in range(editor.sync_list.count())])
editor.sync_list.setCurrentRow(1)
app.processEvents()
check("selecting a Syncer row selects the matching lyric row",
      editor.table.currentRow() == 1, editor.table.currentRow())
editor._select_relative(-1)
check("Syncer keyboard selection moves to the previous line",
      editor.table.currentRow() == 0, editor.table.currentRow())
check("the Preview tab shows a three-line first-lyric countdown",
      "First lyric in 1.0s" in editor.preview_current.text()
      and editor.preview_prev.text() == ""
      and "[00:01.00] Line A" in editor.preview_next.text(),
      (editor.preview_prev.text(), editor.preview_current.text(),
       editor.preview_next.text()))
sample_lyrics = [(29860, "One more time"), (31810, ""),
                 (45420, "One more time"), (47720, "")]
sample_slots = ariance.lyric_display_slots(sample_lyrics, 33000)
check("a blank current lyric becomes a live countdown to the next lyric",
      ariance.lyric_slot_text(sample_slots[0], sample_lyrics, 33000,
                             timestamp=True) == "[00:29.86] One more time"
      and "[00:31.81] Next lyric in 12.4s"
      == ariance.lyric_slot_text(sample_slots[1], sample_lyrics, 33000,
                                timestamp=True)
      and ariance.lyric_slot_text(sample_slots[2], sample_lyrics, 33000,
                                 timestamp=True) == "[00:45.42] One more time",
      [ariance.lyric_slot_text(slot, sample_lyrics, 33000, timestamp=True)
       for slot in sample_slots])
editor._save_lrc()
with open(lrc_target, encoding="utf-8") as handle:
    editor_lrc = handle.read()
check("the lyrics editor saves timestamps and metadata",
      "[tool:Ariance Music Center]" in editor_lrc
      and "[ar:Test Artist]" in editor_lrc
      and "[00:01.00] Line A" in editor_lrc
      and "[00:03.50] Line B" in editor_lrc,
      editor_lrc)
editor._apply_lyrics_text("[00:01.00]Line A\n[00:02.00]\n[00:03.50]Line B")
check("a timestamp with no lyric is kept as an empty timing",
      editor.table.rowCount() == 3
      and editor.table.item(1, 1).text() == "[00:02.00]"
      and editor.table.item(1, 2).text() == ""
      and "- clear previous lyric -" in editor.sync_list.item(1).text(),
      ([(editor.table.item(i, 1).text(), editor.table.item(i, 2).text())
        for i in range(editor.table.rowCount())],
       editor.sync_list.item(1).text() if editor.sync_list.count() > 1 else ""))
editor._save_lrc()
with open(lrc_target, encoding="utf-8") as handle:
    empty_timing_lrc = handle.read()
check("empty timings are saved without a trailing lyric",
      "[00:02.00]\n" in empty_timing_lrc,
      empty_timing_lrc)
check("the Syncer clear reminder is not written to the LRC",
      "clear previous lyric" not in empty_timing_lrc,
      empty_timing_lrc)
editor.table.setCurrentCell(1, 2)
QTest.keyClick(editor.sync_list, Qt.Key.Key_Backspace)
app.processEvents()
check("Backspace clears the timing but keeps the line",
      editor.table.rowCount() == 3
      and editor.table.item(1, 1).text() == ""
      and editor.table.item(1, 2).text() == ""
      and "- clear previous lyric -" not in editor.sync_list.item(1).text(),
      ([(editor.table.item(i, 1).text(), editor.table.item(i, 2).text())
        for i in range(editor.table.rowCount())],
       editor.sync_list.item(1).text()))
QTest.keyClick(editor.sync_list, Qt.Key.Key_Delete)
app.processEvents()
check("Delete removes the selected line",
      editor.table.rowCount() == 2
      and editor.sync_list.count() == 2
      and editor.table.item(0, 2).text() == "Line A"
      and editor.table.item(1, 2).text() == "Line B"
      and editor.lyrics_text.toPlainText()
      == "[00:01.00] Line A\n[00:03.50] Line B",
      ([editor.table.item(i, 2).text() for i in range(editor.table.rowCount())],
       editor.sync_list.count(), editor.lyrics_text.toPlainText()))
editor._apply_lyrics_text("[00:01.00]Line A\n[00:02.00]Line B")
editor.shift_all.setChecked(True)
editor._nudge_time(10)
check("shift all moves the timestamps together",
      editor.table.item(0, 1).text() == "[00:01.01]"
      and editor.table.item(1, 1).text() == "[00:02.01]",
      [editor.table.item(i, 1).text() for i in range(editor.table.rowCount())])
editor.shift_all.setChecked(False)
editor._apply_lyrics_text("[00:01.00]Line A\n[00:02.00]Line B")
editor.table.setCurrentCell(0, 2)
QTest.keyClick(editor.table, Qt.Key.Key_Down)
app.processEvents()
check("the Syncer keyboard shortcut moves to the next line",
      editor.table.currentRow() == 1, editor.table.currentRow())
editor._apply_lyrics_text("[00:01.00]Line A\n[00:01.20]Line B")
check("the Save tab warns about lyrics within 0.5 seconds",
      "within 0.5 seconds" in editor.download_warning.text()
      and not editor.download_warning.isHidden(),
      (editor.download_warning.text(), editor.download_warning.isHidden()))
editor._load_track(WAV1)
check("the lyrics editor starts empty when there is no LRC",
      editor.table.rowCount() == 0 and "No .lrc" in editor.status.text(),
      (editor.table.rowCount(), editor.status.text()))
editor.close()
tools_menu = next(a.menu() for a in w.menuBar().actions()
                  if a.text().replace("&", "") == "Tools")
check("Tools includes the lyrics editor",
      "Lyrics editor…" in [action.text() for action in tools_menu.actions()],
      [action.text() for action in tools_menu.actions()])
ab_menu = next(a.menu() for a in w.menuBar().actions() if a.text() == "&Audiobooks")
ab_actions = [a.text() for a in ab_menu.actions() if a.text()]
check("its menu has Select, Remove and Refresh",
      ab_actions == ["Select folder…", "Remove folder…", "Refresh"], ab_actions)
w.tabs.setCurrentWidget(w.tagger_tab)
app.processEvents()
check("the Tags tab still swaps to mp3tag's menus",
      menu_titles()[:3] == ["File", "Edit", "View"], menu_titles())
w.tabs.setCurrentWidget(w.library_tab)
app.processEvents()

check("the config still has the library folder after start-up",
      w.config["library_folders"] == [MUSIC], w.config["library_folders"])
check("the window lists the remembered device without it being plugged in",
      any(r["name"] == "My Stick" and not r["connected"]
          for r in w.devices_tab._device_rows()),
      w.devices_tab._device_rows())

# the 1.09 regression: the folder question must only appear when there are no folders
asked = []
real_question = QMessageBox.question
QMessageBox.question = staticmethod(
    lambda *a, **k: asked.append(a[2] if len(a) > 2 else "") or QMessageBox.No)
ariance.save_config(w.config)
w2 = ariance.MainWindow()
QTest.qWait(650)
check("an existing library folder is not asked about again", not asked, asked)
w2.close()
QMessageBox.question = real_question

# and the opposite: a genuinely empty config does ask once
empty = fresh_config()
empty["collections"] = [{"name": "Music", "folders": [], "db": ariance.DB_FILE}]
ariance.save_config(empty)
asked.clear()
QMessageBox.question = staticmethod(
    lambda *a, **k: asked.append(a[2] if len(a) > 2 else "") or QMessageBox.No)
w3 = ariance.MainWindow()
QTest.qWait(650)
check("an empty library asks for a folder", len(asked) == 1, asked)
w3.close()
QMessageBox.question = real_question
ariance.save_config(w.config)

prefs = ariance.PreferencesDialog(w.library_tab, w)
check("Preferences has an Audiobooks page",
      [prefs.sidebar.item(i).text() for i in range(prefs.sidebar.count())]
      == ["Theme", "Library", "Audiobooks", "Devices", "Playback", "Syncing",
          "Backup", "Audio CD", "Identification", "Lyrics"],
      [prefs.sidebar.item(i).text() for i in range(prefs.sidebar.count())])
check("Preferences has a Lyrics source list in priority order",
      [prefs.lyric_list.item(i).data(Qt.ItemDataRole.UserRole)
       for i in range(prefs.lyric_list.count())]
      == ["lrc", "tags", "lrclib", "lyrics_ovh"],
      [prefs.lyric_list.item(i).text() for i in range(prefs.lyric_list.count())])
prefs.lyric_list.setCurrentRow(1)
prefs._lyric_move(-1)
check("the Lyrics page can move a source up",
      [prefs.lyric_list.item(i).data(Qt.ItemDataRole.UserRole)
       for i in range(prefs.lyric_list.count())]
      == ["tags", "lrc", "lrclib", "lyrics_ovh"],
      [prefs.lyric_list.item(i).text() for i in range(prefs.lyric_list.count())])
prefs.lyric_list.item(0).setCheckState(Qt.CheckState.Unchecked)
check("the Lyrics page can switch a source off",
      prefs._lyric_order_value()[0] == ["tags", False], prefs._lyric_order_value())
prefs.lyric_list.item(0).setCheckState(Qt.CheckState.Checked)
check("Preferences no longer has .aax import settings",
      not any(key in prefs.widgets for key in
              ("audiobook_import_mode", "audiobook_import_artist_album",
               "audiobook_import_keep_cover")))
check("target folders move out of Preferences into each sync profile",
      not any(key in prefs.widgets for key in
              ("device_music_folder", "device_audiobook_folder", "device_podcast_folder"))
      and w.sync_tab.target_button.text() == "Choose Target Folders"
      and not hasattr(w.sync_tab, "target")
      and not hasattr(w.sync_tab, "music_folder"))
check("Preferences has settings export and import",
      prefs.backup_export.text() == "Export settings…"
      and prefs.backup_import.text() == "Import settings…"
      and len(prefs.backup_checks) == 4
      and all(box.isChecked() for box in prefs.backup_checks.values()))
prefs.close()

# ---------------------------------------------------------------- grids
section("grids: movable columns, remembered order and widths")
ab_tab = w.audiobooks_tab
check("the Audiobooks grid is full width, with no folder panel",
      not hasattr(ab_tab, "folder_list") and not hasattr(ab_tab, "remove_btn"))
check("the Audiobooks header has no folder picker",
      not hasattr(ab_tab, "target_combo"))
check("the Import button uses the ordinary button style",
      ab_tab.import_btn.objectName() != "Primary", ab_tab.import_btn.objectName())
check("the Audiobooks grid has Cover, Title, Author, Chapters, Length",
      [ab_tab.tree.headerItem().text(i) for i in range(ab_tab.tree.columnCount())]
      == ["", "Title", "Author", "Chapters", "Length"])
check("the Audiobooks grid has a search box",
      ab_tab.search.placeholderText().startswith("Search")
      and ab_tab.search.isClearButtonEnabled(), ab_tab.search.placeholderText())
check("its columns can be dragged",
      ab_tab.tree.header().sectionsMovable())
w.config["grid_layouts"] = {}
ab_tab.tree.header().moveSection(0, 2)
ab_tab.tree._grid_store()
order = w.config["grid_layouts"]["audiobooks"]["order"]
check("a reordered column order is written to the config", order == [1, 2, 0, 3, 4], order)
ab_tab.tree.setColumnWidth(1, 321)
ab_tab.tree._grid_store()
widths = w.config["grid_layouts"]["audiobooks"]["widths"]
check("column widths are written too", widths[1] == 321, widths)
saved_layout = json.loads(json.dumps(w.config["grid_layouts"]["audiobooks"]))
ab2 = ariance.AudiobooksTab(w.player, dict(w.config, audiobook_folders=[AB]))
check("a fresh Audiobooks tab restores the order",
      [ab2.tree.header().logicalIndex(v) for v in range(5)] == saved_layout["order"],
      [ab2.tree.header().logicalIndex(v) for v in range(5)])
check("a fresh Audiobooks tab restores the width", ab2.tree.columnWidth(1) == 321,
      ab2.tree.columnWidth(1))
legacy = fresh_config(audiobook_folders=[AB], grid_layouts={
    "audiobooks": {"order": [1, 2, 0, 3], "widths": [300, 200, 80, 70]}})
legacy_tab = ariance.AudiobooksTab(w.player, legacy)
check("a 1.16 audiobook layout gains the cover column in front",
      [legacy_tab.tree.header().logicalIndex(v) for v in range(5)] == [0, 2, 3, 1, 4],
      [legacy_tab.tree.header().logicalIndex(v) for v in range(5)])
legacy_tab.close()

w.config["lib_details"] = True
w.library_tab._apply_columns()
check("the Music grid's columns can be dragged too",
      w.library_tab.tree.header().sectionsMovable())
header = w.library_tab.tree.header()
header.moveSection(0, 1)
w.library_tab.tree._grid_store()
lib_order = w.config["grid_layouts"]["library"]["order"]
check("the Music grid remembers its own order", lib_order == [1, 0] + list(range(2, len(lib_order))),
      lib_order)
check("the remembered order is applied when the grid is rebuilt",
      w.library_tab.tree.header().logicalIndex(0) == 1,
      [header.logicalIndex(v) for v in range(header.count())])
w.config["lib_details"] = False

# ---------------------------------------------------------------- audiobooks
section("audiobooks: titles, chapters and import")
ab_cfg = fresh_config(audiobook_folders=[AB])
ab = ariance.AudiobooksTab(w.player, ab_cfg)
names = [ab.tree.topLevelItem(i).text(1) for i in range(ab.tree.topLevelItemCount())]
check("the Audiobooks header has no .aax import button", not hasattr(ab, "aax_btn"))
check("the .aax settings are gone",
      not any(key in fresh_config() for key in
              ("audiobook_import_mode", "audiobook_import_artist_album",
               "audiobook_import_keep_cover", "audible_activation_bytes",
               "rcrack_path", "rainbow_tables_dir")))
check("a subfolder is one title and a loose file is a title of its own",
      sorted(names) == ["Dune", "The Hobbit"], names)

# Opening the tab must not re-read every chapter's tags when nothing changed.
real_details = ariance.audiobook_details
detail_calls = []

def spy_details(paths, cache=None):
    detail_calls.append(list(paths))
    return real_details(paths, cache)

ariance.audiobook_details = spy_details
try:
    ab.refresh()
finally:
    ariance.audiobook_details = real_details
check("reopening an unchanged Audiobooks tab skips its tag and chapter scan",
      detail_calls == [], detail_calls)

ab._sort_by(3)
check("clicking Chapters sorts the titles by chapter count",
      [ab.tree.topLevelItem(i).text(1) for i in range(ab.tree.topLevelItemCount())]
      == ["The Hobbit", "Dune"],
      [ab.tree.topLevelItem(i).text(1) for i in range(ab.tree.topLevelItemCount())])
ab._sort_by(3)
check("clicking the same heading again reverses the sort",
      [ab.tree.topLevelItem(i).text(1) for i in range(ab.tree.topLevelItemCount())]
      == ["Dune", "The Hobbit"],
      [ab.tree.topLevelItem(i).text(1) for i in range(ab.tree.topLevelItemCount())])
check("the heading shows which way it is sorted",
      ab.tree.header().sortIndicatorSection() == 3
      and ab.tree.header().sortIndicatorOrder() == Qt.DescendingOrder,
      (ab.tree.header().sortIndicatorSection(), ab.tree.header().sortIndicatorOrder()))
ab._sort_by(1)
check("sorting by Title puts the titles back in order",
      [ab.tree.topLevelItem(i).text(1) for i in range(ab.tree.topLevelItemCount())]
      == ["Dune", "The Hobbit"],
      [ab.tree.topLevelItem(i).text(1) for i in range(ab.tree.topLevelItemCount())])
dune = next(ab.tree.topLevelItem(i) for i in range(ab.tree.topLevelItemCount())
            if ab.tree.topLevelItem(i).text(1) == "Dune")
check("the title shows its chapter count", dune.text(3) == "8", dune.text(3))
check("the author is shown in its own column",
      dune.text(2) == "Frank Herbert", dune.text(2))
ab._sort_by(2)
check("clicking Author sorts by author",
      [ab.tree.topLevelItem(i).text(1) for i in range(ab.tree.topLevelItemCount())]
      == ["Dune", "The Hobbit"],
      [ab.tree.topLevelItem(i).text(1) for i in range(ab.tree.topLevelItemCount())])
ab._sort_by(1)
dune = next(ab.tree.topLevelItem(i) for i in range(ab.tree.topLevelItemCount())
            if ab.tree.topLevelItem(i).text(1) == "Dune")
check("a real .m4b chapter list is counted",
      ariance.m4b_chapter_count(AB_CH1) == 4, ariance.m4b_chapter_count(AB_CH1))
check("both M4B files expand to their embedded chapters",
      dune.childCount() == 8, dune.childCount())
check("embedded chapter names are shown",
      [dune.child(i).text(1) for i in range(dune.childCount())]
      == [f"Chapter {i}" for i in range(1, 5)] * 2,
      [dune.child(i).text(1) for i in range(dune.childCount())])
check("the first chapter has a length", dune.child(0).text(4) not in ("", "0:00"),
      dune.child(0).text(4))
solo_rows = ariance.audiobook_chapters([AB_CH1], [12])
check("a single M4B uses one file with embedded chapter offsets",
      len(solo_rows) == 4 and all(row["path"] == AB_CH1 for row in solo_rows)
      and [row["start"] for row in solo_rows] == [0, 3, 6, 9],
      solo_rows)
separate_rows = ariance.audiobook_chapters([WAV1, WAV2], [1, 1])
check("separate chapter files use one row each, just like embedded chapters",
      [(row["name"], row["path"], row["start"]) for row in separate_rows]
      == [("Alpha", WAV1, 0.0), ("Beta", WAV2, 0.0)], separate_rows)
check("a chapter-file folder gets one book key",
      ariance.audiobook_book_key([WAV1, WAV2]) == os.path.normpath(os.path.dirname(WAV1)),
      ariance.audiobook_book_key([WAV1, WAV2]))
cover_file = os.path.join(AB_BOOK, "cover.png")
shutil.copyfile(os.path.join(ROOT, "ariance.png"), cover_file)
ab.refresh(force=True)
dune = next(ab.tree.topLevelItem(i) for i in range(ab.tree.topLevelItemCount())
            if ab.tree.topLevelItem(i).text(1) == "Dune")
check("the cover column shows a book's cover", not dune.icon(0).isNull())
ab.search.setText("hob")
check("the search box finds a title",
      [ab.tree.topLevelItem(i).text(1) for i in range(ab.tree.topLevelItemCount())]
      == ["The Hobbit"],
      [ab.tree.topLevelItem(i).text(1) for i in range(ab.tree.topLevelItemCount())])
ab.search.setText("frank")
check("the search box finds an author",
      [ab.tree.topLevelItem(i).text(1) for i in range(ab.tree.topLevelItemCount())]
      == ["Dune"],
      [ab.tree.topLevelItem(i).text(1) for i in range(ab.tree.topLevelItemCount())])
ab.search.clear()
check("the search box restores every title",
      ab.tree.topLevelItemCount() == 2, ab.tree.topLevelItemCount())
dune = next(ab.tree.topLevelItem(i) for i in range(ab.tree.topLevelItemCount())
            if ab.tree.topLevelItem(i).text(1) == "Dune")
check("the audiobook grid has a right-click menu",
      ab.tree.contextMenuPolicy() == Qt.CustomContextMenu)
book_paths = ab._book_paths[dune.data(0, Qt.UserRole)]
book_key = ariance.audiobook_book_key(book_paths)
check("the chapter drawer starts closed", ab.chapter_panel.isHidden())
ab.tree.setCurrentItem(dune)
ab._show_chapters(True)
check("the chapter drawer lists every embedded chapter",
      not ab.chapter_panel.isHidden() and ab.chapter_list.topLevelItemCount() == 8,
      ab.chapter_list.topLevelItemCount())
check("the chapter drawer shows chapter names",
      ab.chapter_list.topLevelItem(0).text(0) == "Chapter 1"
      and ab.chapter_list.topLevelItem(7).text(0) == "Chapter 4",
      [ab.chapter_list.topLevelItem(i).text(0) for i in range(ab.chapter_list.topLevelItemCount())])
check("the chapter buttons draw a |< and a >| glyph, not text",
      ab.ab_player.prev_btn.text() == "" and ab.ab_player.next_btn.text() == ""
      and not ab.ab_player.prev_btn.icon().isNull()
      and not ab.ab_player.next_btn.icon().isNull())
check("the audiobook bar can redraw its glyphs after a theme change",
      not ab.ab_player.chapters_btn.icon().isNull()
      and not ab.ab_player.prev_btn.icon().pixmap(22, 22).isNull()
      and not ab.ab_player.next_btn.icon().pixmap(22, 22).isNull())
drawer_real_load = ab.ab_player.load_book
drawer_real_load({"key": "drawer-test", "title": "Drawer", "author": "Author"},
                 ab._book_chapters[book_key], 0, 0.0, autoplay=False)
drawer_played = []
ab.ab_player.load_book = lambda *args, **kwargs: drawer_played.append((args, kwargs))
ab._chapter_clicked(ab.chapter_list.topLevelItem(3))
check("a single click on a chapter in the drawer plays that chapter",
      drawer_played and drawer_played[-1][0][2] == 3
      and drawer_played[-1][1].get("autoplay") is True, drawer_played[-1])
ab.ab_player.load_book = drawer_real_load
ab._show_chapters(False)
check("the chapter drawer can be closed again", ab.chapter_panel.isHidden())
played = []
real_load = ab.ab_player.load_book
ab.ab_player.load_book = lambda *args, **kwargs: played.append((args, kwargs))
queue_before = list(ab.player.queue)
ab.ab_player.bookmarks.remember(book_key, 5, 2.0)
ab._play_item(dune)
check("double-clicking a book resumes its saved chapter and timestamp",
      played and played[-1][0][2] == 5 and played[-1][0][3] == 2.0
      and played[-1][1].get("autoplay") is True, played[-1])
ab._play_item(dune.child(0))
check("double-clicking a different chapter starts that chapter at zero",
      played[-1][0][2] == 0 and played[-1][0][3] == 0.0, played[-1])
ab.ab_player.load_book = real_load
check("audiobook playback never touches the music queue",
      ab.player.queue == queue_before, (queue_before, ab.player.queue))
check("audiobook bookmarks have a file of their own, next to the config",
      ariance.AUDIOBOOK_STATE_FILE ==
      os.path.join(ariance.SETTINGS_DIR, "audiobooks.json") and
      os.path.exists(ariance.AUDIOBOOK_STATE_FILE), ariance.AUDIOBOOK_STATE_FILE)
check("config.json no longer holds any audiobook position",
      "audiobook_positions" not in ariance.load_config()
      and "audiobook_last" not in ariance.load_config(),
      sorted(ariance.load_config()))
ab.ab_player.load_book({"key": "book", "title": "Book", "author": "Author"},
                       ab._book_chapters[book_key], 2, 2.0, autoplay=False)
ab.ab_player.save_state()
check("the audiobook player writes its chapter and timestamp to the bookmark file",
      ab.ab_player.bookmarks.state("book") == (2, 2.0),
      ab.ab_player.bookmarks.books.get("book"))
book_file = json.load(open(ariance.AUDIOBOOK_STATE_FILE, encoding="utf-8"))
check("the bookmark file is readable on its own: title, author and chapter name",
      book_file.get("last") == "book"
      and book_file["books"]["book"]["title"] == "Book"
      and book_file["books"]["book"]["author"] == "Author"
      and book_file["books"]["book"]["chapter_name"], book_file["books"].get("book"))
ab.ab_player.load_book({"key": "first", "title": "First", "author": "Author"},
                       ab._book_chapters[book_key], 1, 2.0, autoplay=False)
ab.ab_player._chapter_pos = 7.25
ab.ab_player.load_book({"key": "second", "title": "Second", "author": "Author"},
                       ab._book_chapters[book_key], 0, 0.0, autoplay=False)
check("opening another book saves the outgoing book's exact position",
      ab.ab_player.bookmarks.state("first") == (1, 7.25),
      ab.ab_player.bookmarks.state("first"))
check("the book that was playing before keeps its own place in the file",
      ab.ab_player.bookmarks.state("book") == (2, 2.0)
      and ab.ab_player.bookmarks.state("second") == (0, 0.0),
      ab.ab_player.bookmarks.books)
check("a second book does not become another position for the first",
      ab.ab_player.saved_state("book") == (2, 2.0)
      and ab.ab_player.saved_state("first") == (1, 7.25),
      (ab.ab_player.saved_state("book"), ab.ab_player.saved_state("first")))
ab.ab_player.bookmarks.remember("other", 0, 1.0)
ab.ab_player.load_book({"key": "book", "title": "Book", "author": "Author"},
                       ab._book_chapters[book_key], 2, 2.0, autoplay=False)
check("opening a book updates the startup bookmark even at the same position",
      ab.ab_player.bookmarks.last == "book", ab.ab_player.bookmarks.last)
check("reopening a book leaves the other bookmarks untouched",
      ab.ab_player.bookmarks.state("other") == (0, 1.0),
      ab.ab_player.bookmarks.state("other"))
ab.ab_player.load_book({"key": "book", "title": "Book", "author": "Author"},
                       ab._book_chapters[book_key], 0, 0.0, autoplay=False)
ab.ab_player._position_changed(4500)
check("a multi-M4B book advances through its first file's embedded chapters",
      ab.ab_player.chapter == 1, ab.ab_player.chapter)
ab.ab_player.load_book({"key": "book", "title": "Book", "author": "Author"},
                       ab._book_chapters[book_key], 4, 0.0, autoplay=False)
ab.ab_player._position_changed(4500)
check("the second M4B in the same book advances by its own chapters",
      ab.ab_player.chapter == 5, ab.ab_player.chapter)
check("double-clicking a book does not unfold its chapters",
      not ab.tree.expandsOnDoubleClick())

# one small file for the whole audiobook library
bookmark_path = os.path.join(HOME, "bookmark-test", "audiobooks.json")
store = ariance.AudiobookBookmarks(path=bookmark_path)
check("a bookmark store starts empty", store.books == {} and store.last == "",
      (store.books, store.last))
store.remember("a", 1, 12.5, title="A", author="Author", chapter_name="Two")
store.remember("b", 0, 3.0, title="B")
store.remember("a", 1, 20.0, title="A", author="Author", chapter_name="Two")
reloaded = ariance.AudiobookBookmarks(path=bookmark_path)
check("one file keeps every book's own chapter and timestamp",
      reloaded.state("a") == (1, 20.0) and reloaded.state("b") == (0, 3.0),
      reloaded.books)
check("the bookmark file knows which book was played last", reloaded.last == "a",
      reloaded.last)
check("an unknown book starts at its first chapter",
      reloaded.state("nope") == (0, 0.0), reloaded.state("nope"))
old_bookmarks = {"audiobook_positions": {"b": {"chapter": 4, "position": 1.0},
                                         "c": {"chapter": 2, "position": 9.5}},
                 "audiobook_last": "c"}
ariance.migrate_audiobook_bookmarks(old_bookmarks, path=bookmark_path)
moved = ariance.AudiobookBookmarks(path=bookmark_path)
check("the config's old bookmarks move into the file, leaving the config",
      "audiobook_positions" not in old_bookmarks
      and "audiobook_last" not in old_bookmarks
      and moved.state("c") == (2, 9.5), (old_bookmarks, moved.books))
check("a migrated bookmark never overwrites the newer place in the file",
      moved.state("b") == (0, 3.0) and moved.last == "c", moved.books)


class _StubMedia:
    """Just enough of a QMediaPlayer to watch when the resume seek is issued."""

    def __init__(self, state, seekable=True):
        self.state = state
        self.seekable = seekable
        self.seeks = []

    def isSeekable(self):
        return self.seekable

    def playbackState(self):
        return self.state

    def setPosition(self, ms):
        self.seeks.append(ms)

    def play(self):
        pass


media_before = ab.ab_player.media
ab.ab_player.load_book({"key": "resume", "title": "Resume", "author": "Author"},
                       ab._book_chapters[book_key], 2, 120.0, autoplay=False)
stopped = _StubMedia(ariance.QMediaPlayer.StoppedState)
ab.ab_player.media = stopped
ab.ab_player._media_status = ariance.QMediaPlayer.BufferedMedia
ab.ab_player._pending_seek = 120.0
ab.ab_player._pending_play = False
ab.ab_player._apply_pending_seek()
check("a resume seek is not issued while the player is still stopped",
      stopped.seeks == [] and ab.ab_player._pending_seek == 120.0,
      (stopped.seeks, ab.ab_player._pending_seek))
ab.ab_player._chapter_pos = 120.0
ab.ab_player._position_changed(300)
check("a position reported before the seek lands is not taken as the bookmark",
      ab.ab_player._chapter_pos == 120.0, ab.ab_player._chapter_pos)
stopped.state = ariance.QMediaPlayer.PlayingState
ab.ab_player._apply_pending_seek()
check("the resume seek is offered once playback is running",
      stopped.seeks == [120000] and ab.ab_player._pending_seek == 120.0,
      (stopped.seeks, ab.ab_player._pending_seek))

# Switching books: the backend keeps answering for the file it has just closed,
# so a seek sent right after another book starts playing is dropped and the
# chapter plays from the top. The position report tells whether it took.
ab.ab_player.load_book({"key": "seek-test", "title": "Seek", "author": "Author"},
                       [{"name": "One", "path": WAV1, "start": 0.0,
                         "duration": 3600.0}], 0, 0.0, autoplay=False)
fresh = _StubMedia(ariance.QMediaPlayer.PlayingState)
ab.ab_player.media = fresh
ab.ab_player._media_status = ariance.QMediaPlayer.BufferedMedia
ab.ab_player._pending_seek = 300.0
ab.ab_player._pending_play = False
ab.ab_player._seek_tries = 0
ab.ab_player._seek_settle = 0
ab.ab_player._chapter_pos = 300.0
ab.ab_player._position_changed(0)
check("a seek the player drops is asked for again at the next position",
      fresh.seeks == [300000] and ab.ab_player._pending_seek == 300.0
      and ab.ab_player._chapter_pos == 300.0,
      (fresh.seeks, ab.ab_player._pending_seek, ab.ab_player._chapter_pos))
ab.ab_player._position_changed(300400)
check("a landed seek is not trusted until playback has moved past it",
      ab.ab_player._pending_seek == 300.0, ab.ab_player._pending_seek)
ab.ab_player._position_changed(302400)
check("the book has arrived once playback moves past the bookmark",
      ab.ab_player._pending_seek is None
      and ab.ab_player._chapter_pos == 302.4, ab.ab_player._chapter_pos)
fresh.seeks = []
ab.ab_player._pending_seek = 300.0
ab.ab_player._seek_tries = 0
ab.ab_player._seek_settle = 0
for _ in range(14):
    ab.ab_player._position_changed(0)
check("a file that refuses every seek is not scrubbed over and over",
      len(fresh.seeks) == 8 and ab.ab_player._pending_seek is None,
      (len(fresh.seeks), ab.ab_player._pending_seek))
ab.ab_player.media = media_before
ab.ab_player._pending_seek = None
ab.ab_player._seek_tries = 0
ab.ab_player._seek_settle = 0
ab.ab_player.load_book(
    {"key": "display", "title": "Out of the Silent Planet: Ransom", "author": "C.S. Lewis"},
    [{"name": "Out of the Silent Planet: Chapter 4", "path": WAV1,
      "start": 0.0, "duration": 3600.0}], 0, 0.0, autoplay=False)
check("the chapter line drops a repeated book-title prefix",
      ab.ab_player.chapter_label.text() == "Chapter 4",
      ab.ab_player.chapter_label.text())
check("the default import folder is ~/Music/Ariance - Audiobooks",
      ariance.audiobook_default_folder() ==
      os.path.join(HOME, "Music", "Ariance - Audiobooks"),
      ariance.audiobook_default_folder())
default_tab = ariance.AudiobooksTab(w.player, fresh_config())
check("with no folder configured the destination is the default folder",
      default_tab._target_folder() == ariance.audiobook_default_folder(),
      default_tab._target_folder())
check("with a folder configured its first folder is the destination",
      ab._target_folder() == AB, ab._target_folder())
check("the import progress bar is hidden when no import is running",
      ab.import_progress.isHidden(), ab.import_progress.isVisible())
check("an existing name gets a (2) suffix", ariance.unique_path(WAV1).endswith(" (2).wav"),
      ariance.unique_path(WAV1))
import_root = os.path.join(HOME, "import-src")
incoming = os.path.join(HOME, "import-dst")
os.makedirs(import_root)
os.makedirs(incoming)
to_import = os.path.join(import_root, "Incoming Book.m4b")
shutil.copyfile(AB_CH1, to_import)
ab_cfg["audiobook_import_target"] = incoming
ab_cfg["audiobook_folders"] = []
ab = ariance.AudiobooksTab(w.player, ab_cfg)
real_import_audio, real_import_folder = (
    ab.import_audio, ab.import_folder)
seen_imports = []
ab.import_audio = lambda background=True: seen_imports.append(("audio", background))
ab.import_folder = lambda background=True: seen_imports.append(("folder", background))
ab.import_btn.click()
ab.folder_btn.click()
ab.import_audio, ab.import_folder = (
    real_import_audio, real_import_folder)
check("every import button starts its work in the background",
      seen_imports == [("audio", True), ("folder", True)],
      seen_imports)
real_open = QFileDialog.getOpenFileNames
QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([to_import], ""))
ab.import_audio(background=False)
check("Import moves the file into the chosen folder",
      os.path.exists(os.path.join(incoming, "Incoming Book.m4b"))
      and not os.path.exists(to_import))
check("the import folder is added to the audiobook folders",
      incoming in ab_cfg["audiobook_folders"], ab_cfg["audiobook_folders"])
imported_path = os.path.join(incoming, "Incoming Book.m4b")
check("the imported file is in the grid",
      any(imported_path in paths for paths in ab._book_paths.values()),
      (imported_path, list(ab._book_paths.values())))
second = os.path.join(import_root, "Incoming Book.m4b")
shutil.copyfile(AB_CH2, second)
QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([second], ""))
ab.import_audio(background=False)
check("a second file of the same name does not overwrite the first",
      os.path.exists(os.path.join(incoming, "Incoming Book (2).m4b")),
      sorted(os.listdir(incoming)))
QFileDialog.getOpenFileNames = real_open

folder_book = os.path.join(HOME, "folder-source", "Folder Book")
os.makedirs(folder_book)
shutil.copyfile(AB_CH1, os.path.join(folder_book, "Part 1.m4b"))
real_dir = QFileDialog.getExistingDirectory
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: folder_book)
ab.import_folder(background=False)
QFileDialog.getExistingDirectory = real_dir
check("Import folder moves a whole book folder",
      os.path.isdir(os.path.join(incoming, "Folder Book"))
      and not os.path.exists(folder_book), sorted(os.listdir(incoming)))
check("the imported folder appears as a title",
      any(ab.tree.topLevelItem(i).text(1) == "Folder Book"
          for i in range(ab.tree.topLevelItemCount())),
      [ab.tree.topLevelItem(i).text(1) for i in range(ab.tree.topLevelItemCount())])
book_shelf = os.path.join(HOME, "folder-source", "Book Shelf")
for book in ("First Book", "Second Book"):
    os.makedirs(os.path.join(book_shelf, book))
    shutil.copyfile(AB_CH2, os.path.join(book_shelf, book, "Chapter.m4b"))
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: book_shelf)
ab.import_folder(background=False)
QFileDialog.getExistingDirectory = real_dir
check("Import folder imports each book inside a shelf folder",
      os.path.isdir(os.path.join(incoming, "First Book"))
      and os.path.isdir(os.path.join(incoming, "Second Book")),
      sorted(os.listdir(incoming)))

remove_cfg = fresh_config(audiobook_folders=[AB, incoming])
remove_tab = ariance.AudiobooksTab(w.player, remove_cfg)
real_get_item = QInputDialog.getItem
QInputDialog.getItem = staticmethod(lambda *a, **k: (AB, True))
remove_tab.remove_folder()
check("Remove folder takes the folder away without touching the files",
      remove_cfg["audiobook_folders"] == [incoming] and os.path.isdir(AB),
      remove_cfg["audiobook_folders"])
QInputDialog.getItem = real_get_item

# ---------------------------------------------------------------- devices
section("devices and presets")
dev_cfg = fresh_config()
dev1 = ariance.Device(id="mass:/stick", name="Stick", kind="mass", root="/media/stick")
dev2 = ariance.Device(id="mtp:host=PHONE", name="Phone", kind="mtp", root="/run/phone",
                     uri="mtp://PHONE/")
check("a new device is recorded", ariance.remember_device(dev_cfg, dev1) is True)
check("recording it again changes nothing", ariance.remember_device(dev_cfg, dev1) is False)
check("the record has id, name, kind and root",
      dev_cfg["device_registry"][0] ==
      {"id": "mass:/stick", "name": "Stick", "kind": "mass", "root": "/media/stick",
       "uri": ""}, dev_cfg["device_registry"])
ariance.remember_device(dev_cfg, dev2)
ariance.save_config(dev_cfg)
reloaded = ariance.load_config()
check("remembered devices survive a restart",
      [r["id"] for r in reloaded["device_registry"]] == ["mass:/stick", "mtp:host=PHONE"],
      reloaded["device_registry"])

dev_root = os.path.join(HOME, "stick")
os.makedirs(os.path.join(dev_root, "Music"), exist_ok=True)
live_stick = ariance.Device(id="mass:/stick", name="Stick", kind="mass", root=dev_root)
dev_tab = ariance.DevicesTab(w.player, reloaded, ariance.Library(db_file))
dev_tab.set_devices([live_stick])
app.processEvents()
rows = dev_tab._device_rows()
check("a plugged-in device is connected and an absent one is still listed",
      [(r["id"], r["connected"]) for r in rows] ==
      [("mass:/stick", True), ("mtp:host=PHONE", False)],
      [(r["id"], r["connected"]) for r in rows])
reloaded["device_names"] = {"mtp:host=PHONE": "Walkman"}
dev_tab._render_devices()
check("a nickname is used for a device that is not here",
      [r["name"] for r in dev_tab._device_rows()] == ["Stick", "Walkman"],
      [r["name"] for r in dev_tab._device_rows()])
dev_tab.set_devices([])
check("unplugging keeps both rows, now marked absent",
      all(not r["connected"] for r in dev_tab._device_rows())
      and len(dev_tab._device_rows()) == 2, dev_tab._device_rows())

index = next(i for i, r in enumerate(dev_tab._device_rows()) if r["id"] == "mtp:host=PHONE")
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
dev_tab._remove_device(index)
QMessageBox.question = real_question
check("removing a device hides it and remembers the removal",
      "mtp:host=PHONE" in reloaded["removed_devices"]
      and [r["id"] for r in dev_tab._device_rows()] == ["mass:/stick"],
      (reloaded["removed_devices"], [r["id"] for r in dev_tab._device_rows()]))
reloaded["removed_devices"].pop("mtp:host=PHONE", None)
ariance.save_config(reloaded)
dev_tab.refresh_list()
check("restoring it brings the row back with its name",
      [r["id"] for r in dev_tab._device_rows()] == ["mass:/stick", "mtp:host=PHONE"],
      [r["id"] for r in dev_tab._device_rows()])

presets = [ariance.DevicePreset(name="Stick sync", device_id="mass:/stick", source=MUSIC,
                               target="Music", mode="mirror", method="hash"),
           ariance.DevicePreset(name="Walkman sync", device_id="mtp:host=PHONE",
                               source=ALBUM_A, target="Music/Walkman", mode="add",
                               method="bytes", filesystem="exfat")]
ariance.save_presets(presets)
loaded_presets = ariance.load_presets()
check("presets keep their saved ids for compatibility",
      [(p.name, p.device_id) for p in loaded_presets] ==
      [("Stick sync", "mass:/stick"), ("Walkman sync", "mtp:host=PHONE")],
      [(p.name, p.device_id) for p in loaded_presets])
check("presets are shared, not filtered by device",
      len(ariance.load_presets()) == 2, ariance.load_presets())
check("a preset keeps its method and filesystem",
      loaded_presets[1].method == "bytes" and loaded_presets[1].filesystem == "exfat",
      (loaded_presets[1].method, loaded_presets[1].filesystem))
profile = ariance.Profile(name="temp", device_id="mtp:host=PHONE")
loaded_presets[1].apply_to(profile)
check("choosing a preset loads it into the profile",
      (profile.source, profile.target, profile.mode, profile.method, profile.filesystem,
       profile.sources) == (ALBUM_A, "Music/Walkman", "add", "bytes", "exfat", [ALBUM_A]),
      (profile.source, profile.target, profile.mode, profile.method, profile.filesystem,
       profile.sources))
check("presets are not lost when the device registry is",
      ("device_registry" not in fresh_config() and len(ariance.load_presets()) == 2))

# the Syncing tab shows every preset, whichever device the profile targets
w.sync_tab.presets = ariance.load_presets()
w.sync_tab.profiles = [ariance.Profile(name="Shared", device_id="mass:/stick", source=MUSIC)]
w.sync_tab._reload_list()
check("the Syncing tab lists presets saved for another device",
      w.sync_tab.preset.count() == 3, w.sync_tab.preset.count())
check("a profile can save a shared preset even when it has no device",
      w.sync_tab.preset_save.isEnabled())
w.sync_tab._fill_presets(loaded_presets[1].id)
check("a shared preset can be chosen from the list",
      w.sync_tab.preset.currentData() == loaded_presets[1].id,
      w.sync_tab.preset.currentData())
w.sync_tab.preset.setCurrentIndex(0)
w.sync_tab.preset.setCurrentIndex(w.sync_tab.preset.findData(loaded_presets[1].id))
check("the chosen preset is saved on the profile",
      w.sync_tab.current().preset_id == loaded_presets[1].id,
      getattr(w.sync_tab.current(), "preset_id", ""))
ariance.save_profiles(w.sync_tab.profiles)
restored_preset_profiles = ariance.load_profiles()
check("the chosen preset id survives a profile reload",
      restored_preset_profiles[0].preset_id == loaded_presets[1].id,
      restored_preset_profiles[0].preset_id)
w.sync_tab.profiles = restored_preset_profiles
w.sync_tab._reload_list()
check("the preset is selected again after a restart",
      w.sync_tab.preset.currentData() == loaded_presets[1].id,
      w.sync_tab.preset.currentData())

# force-transcode controls the Bitrate row
bit_profile = ariance.Profile(name="Bits", source=MUSIC)
w.sync_tab.profiles = [bit_profile]
w.sync_tab._reload_list()
check("Bitrate is hidden when Force transcode is off",
      w.sync_tab.transcode_bitrate.isHidden() and w.sync_tab.bitrate_label.isHidden())
codec_index = next(i for i in range(w.sync_tab.transcode.count())
                   if w.sync_tab.transcode.itemData(i))
w.sync_tab.transcode.setCurrentIndex(codec_index)
check("Bitrate appears when a transcode codec is chosen",
      not w.sync_tab.transcode_bitrate.isHidden()
      and w.sync_tab.transcode_bitrate.isEnabled())
w.sync_tab.transcode.setCurrentIndex(0)
check("Bitrate disappears again when transcode is turned off",
      w.sync_tab.transcode_bitrate.isHidden() and w.sync_tab.bitrate_label.isHidden())

# a profile can hold several source folders
w.sync_tab.sources_list.clear()
w.sync_tab.sources_list.addItem(MUSIC)
w.sync_tab.sources_list.addItem(ALBUM_B)
w.sync_tab._store()
check("a profile keeps every folder added to it",
      w.sync_tab.current().sources == [MUSIC, ALBUM_B]
      and w.sync_tab.current().source == MUSIC, w.sync_tab.current().sources)
w.sync_tab.selection_mode.setCurrentIndex(
    max(w.sync_tab.selection_mode.findData("selected"), 0))
check("choosing Selected items hides the folder list and its label",
      w.sync_tab.source_box.isHidden() and w.sync_tab.source_label.isHidden()
      and not w.sync_tab.select_btn.isHidden())
w.sync_tab.selection_mode.setCurrentIndex(
    max(w.sync_tab.selection_mode.findData("folders"), 0))
check("folder mode shows the source folder row again",
      not w.sync_tab.source_box.isHidden() and not w.sync_tab.source_label.isHidden())

section("sync engine")
src = os.path.join(HOME, "sync-src")
dst = os.path.join(HOME, "sync-dst")
os.makedirs(os.path.join(src, "Aphex Twin", "Selected Ambient Works"))
shutil.copyfile(WAV1, os.path.join(src, "Aphex Twin", "Selected Ambient Works",
                                   "01 - Alpha.wav"))
shutil.copyfile(WAV2, os.path.join(src, "Aphex Twin", "Selected Ambient Works",
                                   "02 - Beta.wav"))
os.makedirs(dst)
sync_profile = ariance.Profile(name="Stick", device_id=f"folder:{dst}", source=src,
                              target="Music")
backend = ariance.LocalFolderBackend(dst)
plan = ariance.compare(sync_profile, backend)
check("the first compare plans both files as new",
      sorted(a.kind for a in plan) == ["new", "new"], [(a.kind, a.rel) for a in plan])
check("execute copies them without errors", ariance.execute(sync_profile, backend, plan) == 0)
mirrored = os.path.join(dst, "Music", "Artists", "Aphex Twin", "Selected Ambient Works",
                        "01 - Alpha.wav")
check("the copied file is equal", os.path.exists(mirrored)
      and ariance.files_equal(os.path.join(src, "Aphex Twin", "Selected Ambient Works",
                                          "01 - Alpha.wav"), lambda: open(mirrored, "rb")))
check("a second compare finds everything equal",
      [a.kind for a in ariance.compare(sync_profile, backend)] == ["equal", "equal"],
      [a.kind for a in ariance.compare(sync_profile, backend)])
with open(mirrored, "r+b") as f:
    f.seek(-1, os.SEEK_END)
    last = f.read(1)
    f.seek(-1, os.SEEK_END)
    f.write(bytes([last[0] ^ 1]))
changed = [a for a in ariance.compare(sync_profile, backend) if a.kind == "changed"]
check("a one-bit change at the same size is caught", len(changed) == 1, changed)
ariance.execute(sync_profile, backend, ariance.compare(sync_profile, backend))
check("the changed file is repaired", ariance.files_equal(
    os.path.join(src, "Aphex Twin", "Selected Ambient Works", "01 - Alpha.wav"),
    lambda: open(mirrored, "rb")))
extra = os.path.join(dst, "Music", "Extra", "extra.mp3")
os.makedirs(os.path.dirname(extra), exist_ok=True)
shutil.copyfile(MP3A, extra)
plan = ariance.compare(sync_profile, backend)
check("mirror notices a file the library does not have",
      any(a.kind in ("extra", "delete") for a in plan), [(a.kind, a.rel) for a in plan])
ariance.execute(sync_profile, backend, plan)
check("mirror removes the extra file", not os.path.exists(extra))

hash_dst = os.path.join(HOME, "hash-dst")
os.makedirs(hash_dst)
hash_profile = ariance.Profile(name="Hash", device_id=f"folder:{hash_dst}", source=src,
                              target="Music", method="hash")
hash_backend = ariance.LocalFolderBackend(hash_dst)
ariance.execute(hash_profile, hash_backend, ariance.compare(hash_profile, hash_backend))
restore = os.path.join(hash_dst, "Music", "Artists", "Aphex Twin", "Selected Ambient Works",
                       "02 - Beta.wav")
os.remove(restore)
ariance.execute(hash_profile, hash_backend, ariance.compare(hash_profile, hash_backend))
check("hash sync restores a file deleted from the device", os.path.exists(restore))
ariance.save_profiles([hash_profile])
check("sync profiles survive a restart",
      ariance.load_profiles()[0].name == "Hash"
      and ariance.load_profiles()[0].method == "hash")
check("device file names drop FAT32-reserved characters",
      ariance.device_rel("A/VAMPIRE - DECO*27.m4a") == "A/VAMPIRE - DECO27.m4a",
      ariance.device_rel("A/VAMPIRE - DECO*27.m4a"))

src2_root = os.path.join(HOME, "sync-src2")
src2 = os.path.join(src2_root, "Second")
os.makedirs(src2)
shutil.copyfile(FLAC1, os.path.join(src2, "01 - Second.flac"))
multi_dst = os.path.join(HOME, "multi-dst")
os.makedirs(multi_dst)
multi_profile = ariance.Profile(name="Multi", device_id=f"folder:{multi_dst}", source=src,
                               sources=[src, src2_root], target="Music")
multi_backend = ariance.LocalFolderBackend(multi_dst)
multi_plan = ariance.compare(multi_profile, multi_backend)
check("both sync folders are planned together",
      sorted((a.kind, a.rel) for a in multi_plan) ==
      [("new", "Artists/Aphex Twin/Selected Ambient Works/01 - Alpha.wav"),
       ("new", "Artists/Aphex Twin/Selected Ambient Works/02 - Beta.wav"),
       ("new", "Artists/Second/01 - Second.flac")],
      [(a.kind, a.rel) for a in multi_plan])
ariance.execute(multi_profile, multi_backend, multi_plan)
check("both source folders reach the device",
      os.path.exists(os.path.join(multi_dst, "Music", "Artists", "Second",
                                  "01 - Second.flac"))
      and os.path.exists(os.path.join(multi_dst, "Music", "Artists", "Aphex Twin",
                                      "Selected Ambient Works", "01 - Alpha.wav")))

sel_dst = os.path.join(HOME, "selected-dst")
os.makedirs(sel_dst)
selected_rel = "Artists/Aphex Twin/Selected Ambient Works/01 - Alpha.wav"
sel_profile = ariance.Profile(
    name="Selected", device_id=f"folder:{sel_dst}", source=src, sources=[src],
    target="Music", mode="mirror", selection_mode="selected",
    selection=[{"path": WAV1, "rel": selected_rel}])
sel_backend = ariance.LocalFolderBackend(sel_dst)
sel_plan = ariance.compare(sel_profile, sel_backend)
check("selected mode plans only the chosen item",
      [(a.kind, a.rel) for a in sel_plan] == [("new", selected_rel)],
      [(a.kind, a.rel) for a in sel_plan])
ariance.execute(sel_profile, sel_backend, sel_plan)
check("only the chosen item is copied",
      os.path.exists(os.path.join(sel_dst, "Music", selected_rel))
      and not os.path.exists(os.path.join(sel_dst, "Music", "Artists", "Aphex Twin",
                                          "Selected Ambient Works", "02 - Beta.wav")))
sel_extra = os.path.join(sel_dst, "Music", "Other", "keep.mp3")
os.makedirs(os.path.dirname(sel_extra), exist_ok=True)
shutil.copyfile(MP3A, sel_extra)
sel_plan = ariance.compare(sel_profile, sel_backend)
check("selected mode leaves files it never synced alone",
      not any(a.kind == "delete" for a in sel_plan) and os.path.exists(sel_extra),
      [(a.kind, a.rel) for a in sel_plan])
ariance.execute(sel_profile, sel_backend, sel_plan)
check("the file it never synced is still there after a sync", os.path.exists(sel_extra))

# A copy this profile synced before and has now unticked is removed by Mirror only.
beta_rel = "Artists/Aphex Twin/Selected Ambient Works/02 - Beta.wav"
both_profile = ariance.Profile(
    name="Selected both", device_id=f"folder:{sel_dst}", source=src, sources=[src],
    target="Music", mode="mirror", selection_mode="selected",
    selection=[{"path": WAV1, "rel": selected_rel}, {"path": WAV2, "rel": beta_rel}])
both_plan = ariance.compare(both_profile, sel_backend)
check("a second ticked item is planned as new",
      sorted((a.kind, a.rel) for a in both_plan) ==
      [("equal", selected_rel), ("new", beta_rel)],
      [(a.kind, a.rel) for a in both_plan])
ariance.execute(both_profile, sel_backend, both_plan)
both_profile.selection = [{"path": WAV1, "rel": selected_rel}]
both_profile.mode = "update"
update_plan = ariance.compare(both_profile, sel_backend)
check("update plans no deletion for an item that is no longer selected",
      not any(a.kind == "delete" for a in update_plan),
      [(a.kind, a.rel) for a in update_plan])
ariance.execute(both_profile, sel_backend, update_plan)
check("update leaves the unselected copy on the device",
      os.path.exists(os.path.join(sel_dst, "Music", beta_rel)))
both_profile.mode = "mirror"
untick_plan = ariance.compare(both_profile, sel_backend)
check("mirror plans to delete the item that is no longer selected",
      sorted((a.kind, a.rel) for a in untick_plan) ==
      [("delete", beta_rel), ("equal", selected_rel)],
      [(a.kind, a.rel) for a in untick_plan])
ariance.execute(both_profile, sel_backend, untick_plan)
check("the unselected copy is removed and the other one stays",
      not os.path.exists(os.path.join(sel_dst, "Music", beta_rel))
      and os.path.exists(os.path.join(sel_dst, "Music", selected_rel)))
check("deleting an unselected item leaves a file the profile never wrote",
      os.path.exists(sel_extra))

# The same rule for Fast hash.
sel_hash_dst = os.path.join(HOME, "selected-hash-dst")
os.makedirs(sel_hash_dst)
sel_hash_profile = ariance.Profile(
    name="Selected hash", device_id=f"folder:{sel_hash_dst}", source=src, sources=[src],
    target="Music", method="hash", mode="mirror", selection_mode="selected",
    selection=[{"path": WAV1, "rel": selected_rel}, {"path": WAV2, "rel": beta_rel}])
sel_hash_backend = ariance.LocalFolderBackend(sel_hash_dst)
ariance.execute(sel_hash_profile, sel_hash_backend,
               ariance.compare(sel_hash_profile, sel_hash_backend))
hash_extra = os.path.join(sel_hash_dst, "Music", "Other", "keep.mp3")
os.makedirs(os.path.dirname(hash_extra), exist_ok=True)
shutil.copyfile(MP3A, hash_extra)
sel_hash_profile.selection = [{"path": WAV1, "rel": selected_rel}]
hash_untick = ariance.compare(sel_hash_profile, sel_hash_backend)
check("hash mirror plans to delete the item that is no longer selected",
      sorted((a.kind, a.rel) for a in hash_untick) ==
      [("delete", beta_rel), ("equal", selected_rel)],
      [(a.kind, a.rel) for a in hash_untick])
ariance.execute(sel_hash_profile, sel_hash_backend, hash_untick)
check("hash mirror removes the unselected copy and keeps the other",
      not os.path.exists(os.path.join(sel_hash_dst, "Music", beta_rel))
      and os.path.exists(os.path.join(sel_hash_dst, "Music", selected_rel)))
check("hash mirror leaves a file it never synced alone", os.path.exists(hash_extra))

selection_dlg = ariance.SyncSelectionDialog(
    fresh_config(library_folders=[MUSIC], audiobook_folders=[AB]),
    library, [], None)
selection_labels = [selection_dlg.tree.topLevelItem(i).text(0).split(" (")[0]
                    for i in range(selection_dlg.tree.topLevelItemCount())]
music_rows = sum(1 for row in library.tracks()
                 if "podcast" not in str(row.get("genre") or "").lower())
book_files = sum(len(paths) for _name, paths in ariance.audiobook_books([AB]))
check("the selection window has Music and Audiobooks groups, without Podcasts",
      selection_labels == ["Music", "Audiobooks"], selection_labels)
check("everything is selected by default",
      len(selection_dlg.entries()) == music_rows + book_files,
      (len(selection_dlg.entries()), music_rows, book_files))
check("the selection tree starts collapsed",
      all(not selection_dlg.tree.topLevelItem(i).isExpanded()
          for i in range(selection_dlg.tree.topLevelItemCount())))
music_group = selection_dlg.tree.topLevelItem(0)
aphex_artist = next((music_group.child(i) for i in range(music_group.childCount())
                     if music_group.child(i).text(0) == "Aphex Twin"), None)
aphex_album = next((aphex_artist.child(i) for i in range(aphex_artist.childCount())
                    if aphex_artist.child(i).text(0) == "Selected Ambient Works"), None) \
    if aphex_artist is not None else None
check("Music opens as artist > album > tracks",
      aphex_artist is not None and aphex_album is not None
      and aphex_album.parent() is aphex_artist and aphex_album.childCount() >= 2
      and all(aphex_album.child(i).data(0, Qt.UserRole)
              for i in range(aphex_album.childCount())),
      (aphex_artist.text(0) if aphex_artist else None,
       aphex_album.childCount() if aphex_album else None))
check("Music does not list every track as a direct child",
      music_group.childCount() > 0
      and all(music_group.child(i).childCount() > 0
              for i in range(music_group.childCount())),
      [music_group.child(i).text(0) for i in range(music_group.childCount())])
audio_group = selection_dlg.tree.topLevelItem(1)
check("audiobook titles start collapsed",
      all(not audio_group.child(i).isExpanded() for i in range(audio_group.childCount())))
check("the selection buttons are Select All and Unselect All",
      {"Select All", "Unselect All"} <= {b.text() for b in
                                          selection_dlg.findChildren(QPushButton)})
check("an audiobook keeps its book folder on the device",
      any(e["rel"].startswith("Dune/") for e in selection_dlg.entries()),
      [e["rel"] for e in selection_dlg.entries()][:6])
all_entries = selection_dlg.entries()
without_dune = [entry for entry in all_entries if not entry["rel"].startswith("Dune/")]
partial = ariance.SyncSelectionDialog(
    fresh_config(library_folders=[MUSIC], audiobook_folders=[AB]), library,
    without_dune, None)
partial_books = partial.tree.topLevelItem(1)
dune_book = next(partial_books.child(i) for i in range(partial_books.childCount())
                 if partial_books.child(i).text(0) == "Dune")
check("a book with all chapters unselected reopens unchecked",
      dune_book.checkState(0) == Qt.Unchecked
      and all(dune_book.child(i).checkState(0) == Qt.Unchecked
              for i in range(dune_book.childCount())))
none_dlg = ariance.SyncSelectionDialog(
    fresh_config(library_folders=[MUSIC], audiobook_folders=[AB]), library,
    [], None, select_all=False)
check("an explicitly empty selection stays empty", none_dlg.entries() == [])

class PodcastLibrary:
    def tracks(self):
        return [
            {"path": os.path.join(MUSIC, "Podcasts", "Show", "episode.mp3"),
             "title": "Episode", "artist": "", "album": "", "genre": ""},
            {"path": WAV1, "title": "Tagged podcast", "artist": "", "album": "",
             "genre": "Podcast"},
        ]

podcast_dlg = ariance.SyncSelectionDialog(
    fresh_config(library_folders=[MUSIC], audiobook_folders=[]),
    PodcastLibrary(), [], None)
podcast_labels = [podcast_dlg.tree.topLevelItem(i).text(0).split(" (")[0]
                  for i in range(podcast_dlg.tree.topLevelItemCount())]
check("podcast tracks are kept out of the sync selection by tag or folder",
      podcast_dlg.entries() == [] and podcast_labels == ["Music", "Audiobooks"],
      (podcast_dlg.entries(), podcast_labels))
podcast_dlg.close()
selection_dlg._select_none()
check("Unselect All clears every item", selection_dlg.entries() == [])
check("Unselect All clears the music artist branches",
      music_group.checkState(0) == Qt.Unchecked)
selection_dlg._select_all()
check("Select All selects every item again",
      len(selection_dlg.entries()) == music_rows + book_files)
check("Select All restores the music tree", music_group.checkState(0) == Qt.Checked)
partial.close()
none_dlg.close()
selection_dlg.close()

# Every profile carries its own target tree. Music and books land below the chosen
# device folder; podcasts are paused and are not offered or copied.
os.makedirs(os.path.join(src, "Podcasts", "Show"), exist_ok=True)
shutil.copyfile(MP3A, os.path.join(src, "Podcasts", "Show", "episode.mp3"))
routed_dst = os.path.join(HOME, "routed-dst")
os.makedirs(routed_dst)
routed_profile = ariance.Profile(name="Routed", device_id=f"folder:{routed_dst}",
                               source=src, sources=[src, AB], target="Music",
                               audiobook_roots=[AB])
routed_plan = ariance.compare(routed_profile, ariance.LocalFolderBackend(routed_dst))
check("the profile sends music and audiobooks, but not podcasts",
      sorted((a.kind, a.rel) for a in routed_plan) == [
          ("new", "Artists/Aphex Twin/Selected Ambient Works/01 - Alpha.wav"),
          ("new", "Artists/Aphex Twin/Selected Ambient Works/02 - Beta.wav"),
          ("new", "Audiobooks/Dune/Chapter 01.m4b"),
          ("new", "Audiobooks/Dune/Chapter 02.m4b"),
          ("new", "Audiobooks/The Hobbit.m4b")],
      [(a.kind, a.rel) for a in routed_plan])
ariance.execute(routed_profile, ariance.LocalFolderBackend(routed_dst), routed_plan)
check("the rendered paths use the selected folder and its music/audiobook subfolders",
      os.path.exists(os.path.join(routed_dst, "Music", "Artists", "Aphex Twin",
                                  "Selected Ambient Works", "01 - Alpha.wav"))
      and os.path.exists(os.path.join(routed_dst, "Music", "Audiobooks", "Dune",
                                      "Chapter 01.m4b"))
      and not os.path.exists(os.path.join(routed_dst, "Music", "Podcasts", "Show",
                                          "episode.mp3")))
target_dialog = ariance.SyncTargetsDialog(routed_profile, routed_dst)
target_dialog.base.setText("Walkman/Music")
target_dialog.music.setText("Artists")
target_dialog.audiobooks.setText("Audiobooks")
check("Choose Target Folders edits only the Music and Audiobooks paths",
      target_dialog.values() == ("Walkman/Music", "Artists", "Audiobooks")
      and "Walkman/Music/Audiobooks" in target_dialog.preview.text()
      and "Podcasts" not in target_dialog.preview.text()
      and not hasattr(target_dialog, "podcasts"),
      (target_dialog.values(), target_dialog.preview.text()))
target_dialog.close()
legacy_podcast_profile = ariance.Profile(
    name="Legacy podcast", selection_mode="selected",
    selection=[{"path": WAV1, "rel": "Podcasts/Show/episode.wav", "kind": "podcast"}])
check("a legacy podcast selection is ignored by the sync engine",
      ariance.profile_sync_files(legacy_podcast_profile) == {},
      ariance.profile_sync_files(legacy_podcast_profile))
inactive_dst = os.path.join(HOME, "inactive-dst")
os.makedirs(os.path.join(inactive_dst, "Music", "Audiobooks"))
os.makedirs(os.path.join(inactive_dst, "Music", "Podcasts", "Keep"))
shutil.copyfile(AB_CH1, os.path.join(inactive_dst, "Music", "Audiobooks", "keep.m4b"))
shutil.copyfile(MP3A, os.path.join(inactive_dst, "Music", "Podcasts", "Keep", "keep.mp3"))
inactive_profile = ariance.Profile(name="Music only", device_id=f"folder:{inactive_dst}",
                                 source=src, sources=[src], target="Music", mode="mirror")
inactive_plan = ariance.compare(inactive_profile, ariance.LocalFolderBackend(inactive_dst))
check("a music profile does not delete the Audiobooks or Podcasts trees it is not sending",
      not any(a.kind == "delete" and (a.rel.startswith("Audiobooks/")
                                       or a.rel.startswith("Podcasts/"))
              for a in inactive_plan)
      and os.path.exists(os.path.join(inactive_dst, "Music", "Podcasts", "Keep",
                                      "keep.mp3")),
      [(a.kind, a.rel) for a in inactive_plan])

saved_profiles = ariance.load_profiles()
empty_profile = ariance.Profile(name="Empty selection", selection_mode="selected",
                               selection=[], selection_all=False)
ariance.save_profiles([empty_profile])
loaded_empty = ariance.load_profiles()[0]
check("an empty selected-item choice survives a profile reload",
      loaded_empty.selection_mode == "selected" and not loaded_empty.selection
      and loaded_empty.selection_all is False)
ariance.save_profiles(saved_profiles)

# ---------------------------------------------------------------- session
section("session restore and the reported data loss")
w.config["library_folders"] = [MUSIC]
w.config["device_registry"] = [
    {"id": "mass:/stick", "name": "Stick", "kind": "mass", "root": "/stick", "uri": ""},
    {"id": "mtp:host=PHONE", "name": "Phone", "kind": "mtp", "root": "/run/phone",
     "uri": "mtp://PHONE/"}]
w.config["device_names"] = {"mtp:host=PHONE": "Walkman"}
w.config["volume"] = 63
w.tabs.setCurrentIndex(1)
app.processEvents()
w.player.set_queue([WAV1, FLAC1])
w.library_tab._save_queue_state()
ariance.save_config(w.config)
w.close()

restored = ariance.load_config()
check("the library folder is still there after closing",
      restored["library_folders"] == [MUSIC], restored["library_folders"])
check("both remembered devices are still there after closing",
      [r["id"] for r in restored["device_registry"]] == ["mass:/stick", "mtp:host=PHONE"],
      restored["device_registry"])
check("the queue survives the restart", restored["queue"] == [WAV1, FLAC1],
      restored["queue"])
check("volume and tab survive the restart",
      restored["volume"] == 63 and restored["tab"] == 1,
      (restored["volume"], restored["tab"]))

asked.clear()
QMessageBox.question = staticmethod(
    lambda *a, **k: asked.append(a[2] if len(a) > 2 else "") or QMessageBox.No)
w4 = ariance.MainWindow()
QTest.qWait(650)
check("the next launch restores the queue", len(w4.player.queue) == 2, w4.player.queue)
check("the next launch restores the remembered devices",
      [r["id"] for r in w4.devices_tab._device_rows()] == ["mass:/stick", "mtp:host=PHONE"],
      w4.devices_tab._device_rows())
check("the next launch does not ask for the library folder", not asked, asked)
QMessageBox.question = real_question
w4.close()

# a stray defaults write must never replace a configured install
good = json.loads(json.dumps(restored))
ariance.save_config(good)
ariance.save_config(good)                    # make the backup the good config
stray = fresh_config()
check("a defaults write is refused over an existing configured install",
      ariance.save_config(stray) is False
      and ariance.load_config()["library_folders"] == [MUSIC]
      and ariance.load_config()["volume"] == 63,
      (ariance.load_config().get("library_folders"), ariance.load_config().get("volume")))
backup_data = json.load(open(ariance.CONFIG_FILE + ".bak", encoding="utf-8"))
check("the refused defaults write leaves the good backup untouched",
      backup_data["library_folders"] == [MUSIC]
      and len(backup_data["device_registry"]) == 2, backup_data.get("library_folders"))
# Bypass the guard deliberately: that is what an interrupted or external write
# would look like, and the previous good file must still be recoverable.
ariance.save_json(ariance.CONFIG_FILE, fresh_config())
with open(ariance.CONFIG_FILE, "w", encoding="utf-8") as f:
    f.write("{")
check("a damaged config after an external defaults write comes back from the backup",
      ariance.load_config()["library_folders"] == [MUSIC],
      ariance.load_config()["library_folders"])

# ---------------------------------------------------------------- settings backup
section("settings backup")
w.config["discogs_token"] = "secret-token"
w.config["discogs_secret"] = "secret-secret"
backup_groups = {"preferences", "sync_profiles", "device_presets", "smart_playlists"}
backup = ariance.build_settings_bundle(w.config, backup_groups)
check("a settings backup has all four parts",
      set(backup) >= {"nebula_settings", "preferences", "sync_profiles",
                      "device_presets", "smart_playlists"}, set(backup))
check("a settings backup leaves credentials out",
      not ({"discogs_token", "discogs_secret"}
           & set(backup["preferences"])), backup["preferences"].keys())
backup_path = os.path.join(HOME, "settings-backup.json")
ariance.write_settings_bundle(backup_path, w.config, backup_groups)
loaded_backup = ariance.read_settings_bundle(backup_path)
check("an exported settings file reads back",
      loaded_backup.get("preferences", {}).get("volume") == w.config["volume"])
try:
    ariance.read_settings_bundle(ariance.CONFIG_FILE)
    bad_backup = False
except ValueError:
    bad_backup = True
check("an ordinary JSON file is not mistaken for a settings backup", bad_backup)
import_cfg = fresh_config(discogs_token="keep-me", volume=1)
import_bundle = {"nebula_settings": 1, "preferences": {"volume": 13,
                  "discogs_token": "do-not-copy"}}
imported = ariance.apply_settings_bundle(import_bundle, import_cfg, {"preferences"})
check("importing merges preferences and keeps credentials",
      import_cfg["volume"] == 13 and import_cfg["discogs_token"] == "keep-me"
      and imported.get("preferences") is True,
      (import_cfg["volume"], import_cfg["discogs_token"]))
try:
    ariance.apply_settings_bundle({"nebula_settings": 1}, import_cfg, {"preferences"})
    missing_ok = False
except ValueError:
    missing_ok = True
check("a settings file missing a selected part is refused", missing_ok)

# ---------------------------------------------------------------- summary
section("summary")
failed = [r for r in RESULTS if not r[2]]
print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
for sec, name, _ok, detail in failed:
    print(f"  FAILED [{sec}] {name}: {detail}")
print(f"\nscratch home: {HOME} (removed when the run ends)")
sys.exit(1 if failed else 0)
