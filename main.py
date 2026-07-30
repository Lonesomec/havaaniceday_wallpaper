# -*- coding: utf-8 -*-
"""macOS 壁纸更换器 — 应用入口

运行方式:
    uv run python wallpaper_changer.py
    或
    uv run python main.py
"""

from wallpaper_changer import main
import flet as ft

if __name__ == "__main__":
    ft.run(main)
