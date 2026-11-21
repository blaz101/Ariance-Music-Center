# Asset provenance

This file records the origin of the artwork shipped with Ariance Music Center. It is
not a substitute for a legal review, but it is the project's written record of where
each asset came from.

## Ariance logo and app icon

- **Full logo source:** `branding/ariance-logo.png`
- **App icon source (1.27):** `branding/ariance-icon.png`, the cleaner circular mark
  supplied by the copyright holder (original file `Nebula Icon.png`,
  221 × 221 RGBA, transparent corners); renamed with the app in 1.30.
- **App icon:** `ariance.png`, generated from `branding/ariance-icon.png` at
  512 × 512.
- **1.26 icon:** `ariance.png` was a crop of the purple circle in the full logo.
- **Copyright:** Copyright (C) 2026 Roger Barthares.
- **License:** distributed under GPL-3.0-only with the application.
- **Evidence:** original source image supplied by the copyright holder.

## Sync log icon

- **File:** `sync-log.png`
- **Icon:** Lucide `file-clock`.
- **Source:** <https://lucide.dev/icons/file-clock>
- **License:** ISC, with Feather-derived portions under MIT. See
  `LICENSES/Lucide.txt`.

## Repeat and shuffle icons

- **Location:** vector paths drawn in `ariance.py` (`player_icon` / `mode_icon`).
- **Icons:** `repeat`, `repeat-one`, `repeat-off`, `shuffle`, `shuffle-off`.
- **Source:** derived from Lucide's icon set.
- **License:** ISC, with Feather-derived portions under MIT. See
  `LICENSES/Lucide.txt`.

## EQ icon

- **File:** `assets/icons/eq.svg`
- **Icon:** a six-bar equalizer outline, drawn for Ariance Music Center by the
  copyright holder. It is not taken from an icon set.
- **License:** distributed under GPL-3.0-only with the application.
- **Note:** `PySide6.QtSvg` is not bundled and the app does not depend on it, so
  the button paints these six bars as paths (like `player_icon`) rather than
  loading the file at runtime.

## Playback-speed icon

- **File:** `assets/icons/gauge.svg`
- **Icon:** Lucide `gauge`, supplied by the copyright holder.
- **Source:** <https://lucide.dev/icons/gauge>
- **License:** ISC, with Feather-derived portions under MIT. See
  `LICENSES/Lucide.txt`.
- **Note:** painted as vector paths (`gauge_icon_pixmap`), like the EQ and chapter
  glyphs, because `PySide6.QtSvg` is not bundled.

## Other UI icons

- The remaining interface glyphs are drawn in `ariance.py`, use Qt standard icons,
  or are emoji rendered by the user's system font. They are not separate bundled
  image files.

## Third-party fonts and libraries

See `THIRD_PARTY_LICENSES.md` for the bundled fonts, Qt/PySide6, FFmpeg, mutagen and
the native libraries. Those components keep their own copyrights and licenses.
