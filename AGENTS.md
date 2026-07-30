# havaaniceday-wallpaper

macOS desktop wallpaper auto-rotation app with a Flet UI.

## Architecture

- `wallpaper_changer.py` — entrypoint. Flet `ft.app` with system tray, async timer-based rotation, AppleScript wallpaper setting, NSApplication dock-icon control. Runs only on macOS.
- `settings.py` — `AppSettings` dataclass. JSON persistence at `~/Library/Application Support/WallpaperChanger/settings.json`. Includes automatic migration from old QSettings plist.
- `system_tray.py` — `TrayManager`. macOS native system tray via `NSStatusItem` (pyobjc), not pystray. Chosen to avoid event-loop conflicts with Flet.
- `wallpaper_crawler.py` — `WallpaperCrawler` class. BeautifulSoup HTML scraping, downloads images from `<img>` tags. Used from `wallpaper_changer.py` via `asyncio.to_thread`.
- `main.py` — alternative entrypoint, just imports and runs `wallpaper_changer.main`.
- `test.py` — ad-hoc Qwen image-generation API test (not project tests, not a test suite).

## Commands

```
uv run python wallpaper_changer.py   # run the app
uv run python main.py                # same thing, alternative entrypoint
```

Dependency management via `uv` with `uv.lock`. Python 3.14 required. PyPI registry: `https://pypi.tuna.tsinghua.edu.cn/simple`.

## Packaging

- `wallpaper_changer.spec` — PyInstaller spec file for `.app` bundle targeting `wallpaper_changer.py`.
- Icon: `iconapp.icns` (app bundle) + `assets/iconapp.png` (PyInstaller data + tray icon).
- `pyobjc-core` / `pyobjc-framework-cocoa` required for dock icon control + system tray.

## macOS-specific

- Wallpaper: `osascript -e 'tell application "System Events" to set picture of every desktop to "..."'`.
- Lock screen wallpaper is approximated via screen saver image path (may not work on all macOS versions).
- Auto-start: `System Events` login items (AppleScript).
- Dock icon hidden via `NSApplication setActivationPolicy:` when window closes (transitions to tray-only).

## Notes

- No test framework, no linter, no typechecker, no CI configured.
- Install deps via `uv sync` (from `pyproject.toml`). `requirements.txt` is a partial subset (no pyobjc/pyside6 listed).
- `test.py` contains a hardcoded API key — do not commit changes to it.
- `.opencode/` is gitignored; contains design/brand/ui skills for Claude artifact generation (not relevant to app code).
