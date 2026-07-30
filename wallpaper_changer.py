# -*- coding: utf-8 -*-
"""macOS 壁纸更换器 — Flet UI 实现"""

import os
import sys
import time
import json
import asyncio
import requests
from pathlib import Path
from urllib.parse import urlparse

import flet as ft
import objc
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyRegular,
    NSApplicationActivationPolicyAccessory,
)

from settings import AppSettings
from system_tray import TrayManager
from wallpaper_crawler import WallpaperCrawler


# ─── 常量 ───
INTERVAL_OPTIONS = ["30分钟", "1小时", "2小时", "3小时", "6小时", "12小时", "1天"]
INTERVAL_MINUTES = [30, 60, 120, 180, 360, 720, 1440]

# 设计令牌
CARD_RADIUS = 16
CARD_PADDING = 24
CARD_SPACING = 16
SHADOW_BLUR = 12
SHADOW_COLOR = "0x14000000"  # 8% 黑色


class WallpaperChanger:
    """壁纸更换器主类 — Flet UI + 业务逻辑"""

    def __init__(self, page: ft.Page):
        self.page = page
        self._really_quit = False
        self._timer_task: asyncio.Task | None = None

        # 壁纸目录
        self.wallpaper_dir = Path.home() / "Pictures" / "Wallpapers"
        if not self.wallpaper_dir.exists():
            self.wallpaper_dir.mkdir(parents=True)

        # 壁纸列表
        self.wallpapers: list[Path] = []
        self.current_wallpaper_index = 0

        # 加载设置
        self.settings = AppSettings.load()

        # 爬虫实例
        self.crawler = WallpaperCrawler(self.wallpaper_dir)

        # 系统托盘
        self.tray = TrayManager(
            on_show=self.show_window,
            on_change=self.change_wallpaper,
            on_quit=self.quit_application,
        )

        # 初始化 UI
        self.init_ui()

        # 启动托盘
        self.tray.start()

        # 扫描壁纸
        self.scan_wallpapers()

        # 如果启用了自动轮换，启动定时器
        if self.settings.rotation_enabled:
            self._start_timer()

    # ─── UI 构建 ───

    def init_ui(self):
        """初始化 Flet UI"""
        page = self.page
        page.title = "macOS壁纸更换器"
        page.window.width = 560
        page.window.height = 680
        # window.center() 是异步的，在 main 中调用

        # 主题设置 — Material 3
        page.theme = ft.Theme(
            color_scheme_seed=ft.Colors.DEEP_PURPLE,
            use_material3=True,
        )
        page.dark_theme = ft.Theme(
            color_scheme_seed=ft.Colors.DEEP_PURPLE,
            use_material3=True,
        )
        page.theme_mode = ft.ThemeMode.SYSTEM

        # 窗口关闭行为 — 隐藏到托盘
        page.window.prevent_close = True
        page.window.on_close = self._on_window_close

        # FilePicker 服务
        self.file_picker = ft.FilePicker()
        page.services.append(self.file_picker)

        # ─── 控件初始化 ───

        # 轮换间隔下拉框
        self.rotation_dropdown = ft.Dropdown(
            label="轮换时间",
            value=INTERVAL_OPTIONS[self.settings.rotation_interval_index],
            options=[ft.DropdownOption(key=opt, text=opt) for opt in INTERVAL_OPTIONS],
            filled=True,
            border_radius=ft.BorderRadius.all(12),
            width=160,
            on_select=self._on_interval_change,
        )

        # 启用自动轮换开关
        self.rotation_switch = ft.Switch(
            label="启用自动轮换",
            value=self.settings.rotation_enabled,
            on_change=self._on_rotation_toggle,
        )

        # 锁屏壁纸开关
        self.lock_screen_switch = ft.Switch(
            label="同时更换锁屏壁纸",
            value=self.settings.change_lock_screen,
        )

        # 开机自启开关
        self.auto_start_switch = ft.Switch(
            label="开机自动启动",
            value=self.settings.auto_start,
        )

        # 本地文件夹路径
        self.folder_field = ft.TextField(
            label="本地文件夹",
            value=self.settings.folder_path,
            read_only=True,
            filled=True,
            border_radius=ft.BorderRadius.all(12),
            expand=True,
        )

        # URL 组下拉框
        url_group_keys = list(self.settings.url_groups.keys())
        self.url_group_dropdown = ft.Dropdown(
            label="壁纸网站URL组",
            value=url_group_keys[0] if url_group_keys else None,
            options=[ft.DropdownOption(key=k, text=k) for k in url_group_keys],
            filled=True,
            border_radius=ft.BorderRadius.all(12),
            expand=True,
        )

        # 爬取进度
        self.crawl_progress = ft.Text(
            value="就绪",
            size=13,
            color=ft.Colors.GREY_600,
        )
        self.crawl_ring = ft.ProgressRing(width=20, height=20, visible=False)

        # 状态栏
        self.status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=16, color=ft.Colors.GREEN)
        self.status_text = ft.Text(
            value="就绪",
            size=13,
            color=ft.Colors.GREY_600,
        )

        # ─── 构建布局 ───
        page.add(
            ft.Column(
                [
                    # 标题区域
                    self._build_header(),
                    # 可滚动内容区
                    ft.Column(
                        [
                            self._build_rotation_card(),
                            self._build_source_card(),
                            self._build_action_card(),
                        ],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                        spacing=CARD_SPACING,
                    ),
                    # 底部状态栏
                    self._build_status_bar(),
                ],
                expand=True,
                spacing=0,
            )
        )

    def _build_header(self) -> ft.Control:
        """构建标题栏"""
        return ft.Container(
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(
                                "壁纸更换器",
                                size=24,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                "macOS 桌面壁纸自动轮换",
                                size=13,
                                color=ft.Colors.GREY_600,
                            ),
                        ],
                        spacing=2,
                    ),
                    ft.Icon(ft.Icons.WALLPAPER, size=32, color=ft.Colors.DEEP_PURPLE),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(left=24, top=20, right=24, bottom=12),
        )

    def _build_rotation_card(self) -> ft.Control:
        """构建轮换设置卡片"""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.TIMER, size=20, color=ft.Colors.DEEP_PURPLE),
                            ft.Text(
                                "壁纸轮换设置",
                                size=16,
                                weight=ft.FontWeight.W_600,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Divider(height=1),
                    ft.Row(
                        [
                            self.rotation_dropdown,
                            self.rotation_switch,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self.lock_screen_switch,
                    self.auto_start_switch,
                ],
                spacing=12,
            ),
            padding=CARD_PADDING,
            border_radius=ft.BorderRadius.all(CARD_RADIUS),
            bgcolor=ft.Colors.SURFACE,
            shadow=ft.BoxShadow(
                blur_radius=SHADOW_BLUR,
                color=SHADOW_COLOR,
                offset=ft.Offset(0, 4),
            ),
            margin=ft.Margin(left=20, top=0, right=20, bottom=0),
        )

    def _build_source_card(self) -> ft.Control:
        """构建壁纸来源卡片"""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.IMAGE, size=20, color=ft.Colors.DEEP_PURPLE),
                            ft.Text(
                                "壁纸来源",
                                size=16,
                                weight=ft.FontWeight.W_600,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Divider(height=1),
                    # 本地文件夹
                    ft.Text("本地文件夹", size=13, color=ft.Colors.GREY_600),
                    ft.Row(
                        [
                            self.folder_field,
                            ft.IconButton(
                                icon=ft.Icons.FOLDER_OPEN,
                                icon_color=ft.Colors.DEEP_PURPLE,
                                tooltip="选择文件夹",
                                on_click=self._on_browse_folder,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Container(height=8),
                    # 在线来源
                    ft.Text("在线壁纸", size=13, color=ft.Colors.GREY_600),
                    ft.Row(
                        [
                            self.url_group_dropdown,
                            ft.IconButton(
                                icon=ft.Icons.EDIT,
                                icon_color=ft.Colors.DEEP_PURPLE,
                                tooltip="编辑URL组",
                                on_click=self._on_edit_urls,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Row(
                        [
                            ft.FilledButton(
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.DOWNLOAD, size=18),
                                        ft.Text("开始爬取壁纸"),
                                    ],
                                    spacing=6,
                                ),
                                on_click=self._on_start_crawl,
                            ),
                            self.crawl_ring,
                            self.crawl_progress,
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=10,
            ),
            padding=CARD_PADDING,
            border_radius=ft.BorderRadius.all(CARD_RADIUS),
            bgcolor=ft.Colors.SURFACE,
            shadow=ft.BoxShadow(
                blur_radius=SHADOW_BLUR,
                color=SHADOW_COLOR,
                offset=ft.Offset(0, 4),
            ),
            margin=ft.Margin(left=20, top=0, right=20, bottom=0),
        )

    def _build_action_card(self) -> ft.Control:
        """构建操作按钮卡片"""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.PLAY_ARROW, size=20, color=ft.Colors.DEEP_PURPLE),
                            ft.Text(
                                "操作",
                                size=16,
                                weight=ft.FontWeight.W_600,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Divider(height=1),
                    ft.Row(
                        [
                            ft.FilledButton(
                                content=ft.Row(
                                    [ft.Icon(ft.Icons.SWAP_HORIZ, size=18), ft.Text("立即更换")],
                                    spacing=6,
                                ),
                                on_click=lambda e: self.change_wallpaper(),
                                expand=True,
                            ),
                            ft.FilledTonalButton(
                                content=ft.Row(
                                    [ft.Icon(ft.Icons.AUTO_MODE, size=18), ft.Text("开始自动更换")],
                                    spacing=6,
                                ),
                                on_click=self._on_toggle_auto,
                                expand=True,
                            ),
                        ],
                        spacing=12,
                    ),
                    ft.OutlinedButton(
                        content=ft.Row(
                            [ft.Icon(ft.Icons.SAVE, size=18), ft.Text("保存设置")],
                            spacing=6,
                        ),
                        on_click=self._on_save_settings,
                        width=float("inf"),
                    ),
                ],
                spacing=12,
            ),
            padding=CARD_PADDING,
            border_radius=ft.BorderRadius.all(CARD_RADIUS),
            bgcolor=ft.Colors.SURFACE,
            shadow=ft.BoxShadow(
                blur_radius=SHADOW_BLUR,
                color=SHADOW_COLOR,
                offset=ft.Offset(0, 4),
            ),
            margin=ft.Margin(left=20, top=0, right=20, bottom=0),
        )

    def _build_status_bar(self) -> ft.Control:
        """构建底部状态栏"""
        return ft.Container(
            content=ft.Row(
                [
                    self.status_icon,
                    self.status_text,
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(left=24, top=12, right=24, bottom=12),
            border=ft.Border(top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        )

    # ─── 状态更新 ───

    def set_status(self, message: str, success: bool = True):
        """更新状态栏"""
        self.status_text.value = message
        self.status_icon.icon = ft.Icons.CHECK_CIRCLE if success else ft.Icons.ERROR
        self.status_icon.color = ft.Colors.GREEN if success else ft.Colors.RED
        self.page.update()

    def _show_snackbar(self, message: str, error: bool = False):
        """显示 SnackBar 提示"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.RED_400 if error else ft.Colors.DEEP_PURPLE,
        )
        self.page.overlay.append(snackbar)
        snackbar.open = True
        self.page.update()

    # ─── 事件处理 ───

    def _on_interval_change(self, e):
        """轮换间隔变更"""
        if self.rotation_dropdown.value in INTERVAL_OPTIONS:
            self.settings.rotation_interval_index = INTERVAL_OPTIONS.index(
                self.rotation_dropdown.value
            )

    def _on_rotation_toggle(self, e):
        """自动轮换开关切换"""
        self.settings.rotation_enabled = self.rotation_switch.value
        if self.rotation_switch.value:
            self._start_timer()
            self.set_status("已启用自动轮换")
        else:
            self._stop_timer()
            self.set_status("已停止自动轮换")

    async def _on_browse_folder(self, e):
        """浏览文件夹"""
        path = await self.file_picker.get_directory_path(
            dialog_title="选择壁纸文件夹"
        )
        if path:
            self.folder_field.value = path
            self.settings.folder_path = path
            self.scan_wallpapers()
            self.page.update()

    def _on_edit_urls(self, e):
        """编辑 URL 组对话框"""
        url_text = ft.TextField(
            value=json.dumps(self.settings.url_groups, indent=2, ensure_ascii=False),
            multiline=True,
            min_lines=8,
            max_lines=12,
            filled=True,
            border_radius=ft.BorderRadius.all(12),
        )

        def save_urls(ev):
            try:
                new_groups = json.loads(url_text.value)
                self.settings.url_groups = new_groups
                # 更新下拉框
                keys = list(new_groups.keys())
                self.url_group_dropdown.options = [
                    ft.DropdownOption(key=k, text=k) for k in keys
                ]
                if keys:
                    self.url_group_dropdown.value = keys[0]
                self.page.pop_dialog()
                self.set_status("URL组已保存")
                self._show_snackbar("URL组已保存")
            except json.JSONDecodeError:
                self._show_snackbar("JSON格式不正确", error=True)

        dialog = ft.AlertDialog(
            title=ft.Text("编辑URL组"),
            content=ft.Container(
                content=url_text,
                width=400,
            ),
            actions=[
                ft.FilledButton(content=ft.Text("保存"), on_click=save_urls),
                ft.OutlinedButton(
                    content=ft.Text("取消"),
                    on_click=lambda ev: self.page.pop_dialog(),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dialog)

    async def _on_start_crawl(self, e):
        """开始爬取壁纸"""
        selected_group = self.url_group_dropdown.value
        if not selected_group or selected_group not in self.settings.url_groups:
            self._show_snackbar("请先添加URL组", error=True)
            return

        urls = self.settings.url_groups[selected_group]
        self.crawl_ring.visible = True
        self.crawl_progress.value = "爬取中..."
        self.page.update()

        try:
            # 在线程池中执行爬虫（避免阻塞 UI）
            success_count = await asyncio.to_thread(self.crawler.crawl, urls)
            self.crawl_progress.value = f"爬取完成，成功下载 {success_count} 张壁纸"
            self.set_status(f"爬取完成，成功下载 {success_count} 张壁纸")
            self.scan_wallpapers()
        except Exception as ex:
            self.crawl_progress.value = f"爬取失败: {str(ex)}"
            self.set_status(f"爬取失败: {str(ex)}", success=False)
        finally:
            self.crawl_ring.visible = False
            self.page.update()

    def _on_toggle_auto(self, e):
        """切换自动更换"""
        if self._timer_task and not self._timer_task.done():
            self._stop_timer()
            self.rotation_switch.value = False
            self.settings.rotation_enabled = False
            self.set_status("已停止自动更换")
            self._show_snackbar("已停止自动更换")
        else:
            self._start_timer()
            self.rotation_switch.value = True
            self.settings.rotation_enabled = True
            self.set_status("已开始自动更换")
            self._show_snackbar("已开始自动更换")
        self.page.update()

    def _on_save_settings(self, e):
        """保存设置"""
        self.save_settings()
        self._show_snackbar("设置已保存")

    # ─── 定时器管理 ───

    def _start_timer(self):
        """启动轮换定时器"""
        self._stop_timer()  # 先停止旧的
        interval_seconds = INTERVAL_MINUTES[self.settings.rotation_interval_index] * 60
        self._timer_task = asyncio.create_task(self._rotation_loop(interval_seconds))

    def _stop_timer(self):
        """停止轮换定时器"""
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
            self._timer_task = None

    async def _rotation_loop(self, interval_seconds: int):
        """轮换循环"""
        while True:
            await asyncio.sleep(interval_seconds)
            self.change_wallpaper()

    # ─── 业务逻辑（保留原有实现） ───

    def scan_wallpapers(self):
        """扫描壁纸文件"""
        self.wallpapers = []

        # 添加本地壁纸
        folder = self.folder_field.value if self.folder_field else self.settings.folder_path
        if folder and os.path.exists(folder):
            for ext in ["*.jpg", "*.jpeg", "*.png", "*.bmp", "*.gif", "*.avif"]:
                self.wallpapers.extend(Path(folder).glob(f"**/{ext}"))

        # 添加爬虫下载的壁纸
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.bmp", "*.gif", "*.avif"]:
            self.wallpapers.extend(self.wallpaper_dir.glob(f"**/{ext}"))

        self.set_status(f"找到 {len(self.wallpapers)} 张壁纸")

    def change_wallpaper(self):
        """更换壁纸"""
        if not self.wallpapers:
            self.set_status("没有可用的壁纸", success=False)
            return

        # 选择下一张壁纸
        self.current_wallpaper_index = (self.current_wallpaper_index + 1) % len(
            self.wallpapers
        )
        wallpaper = self.wallpapers[self.current_wallpaper_index]

        try:
            # 处理壁纸文件/URL
            if isinstance(wallpaper, Path):  # 本地文件
                wallpaper_path = str(wallpaper)
            else:  # 在线URL
                wallpaper_path = self.download_wallpaper(wallpaper)

            # 设置桌面壁纸
            self.set_desktop_wallpaper(wallpaper_path)

            # 设置锁屏壁纸（如果启用）
            if self.lock_screen_switch.value:
                self.set_lock_screen_wallpaper(wallpaper_path)

            self.set_status(f"已更换壁纸: {os.path.basename(wallpaper_path)}")

        except Exception as e:
            self.set_status(f"更换壁纸失败: {str(e)}", success=False)

    def download_wallpaper(self, url):
        """下载壁纸"""
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()

            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            if not filename:
                filename = f"wallpaper_{int(time.time())}.jpg"

            save_path = self.wallpaper_dir / filename

            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return str(save_path)

        except Exception as e:
            raise Exception(f"下载壁纸失败: {str(e)}")

    def set_desktop_wallpaper(self, wallpaper_path):
        """设置桌面壁纸 — AppleScript"""
        try:
            script = f'''
            tell application "System Events"
                set picture of every desktop to "{wallpaper_path}"
            end tell
            '''
            os.system(f"osascript -e '{script}'")
        except Exception as e:
            raise Exception(f"设置桌面壁纸失败: {str(e)}")

    def set_lock_screen_wallpaper(self, wallpaper_path):
        """设置锁屏壁纸 — AppleScript"""
        try:
            script = f'''
            tell application "System Events"
                tell current screen saver
                    set properties to {{image path:"{wallpaper_path}"}}
                end tell
            end tell
            '''
            os.system(f"osascript -e '{script}'")
        except Exception as e:
            raise Exception(f"设置锁屏壁纸失败: {str(e)}")

    def save_settings(self):
        """保存设置"""
        self.settings.rotation_enabled = self.rotation_switch.value
        self.settings.change_lock_screen = self.lock_screen_switch.value
        self.settings.auto_start = self.auto_start_switch.value
        self.settings.folder_path = self.folder_field.value or ""

        if self.rotation_dropdown.value in INTERVAL_OPTIONS:
            self.settings.rotation_interval_index = INTERVAL_OPTIONS.index(
                self.rotation_dropdown.value
            )

        self.settings.save()

        # 设置开机自启
        self.set_auto_start(self.auto_start_switch.value)

        self.set_status("设置已保存")

    def set_auto_start(self, enable):
        """设置开机自启 — AppleScript"""
        app_path = os.path.abspath(sys.argv[0])
        app_name = "WallpaperChanger"

        if enable:
            script = f'''
            tell application "System Events" to make login item at end with properties {{path:"{app_path}", hidden:false, name:"{app_name}"}}
            '''
            os.system(f"osascript -e '{script}'")
        else:
            script = f'''
            tell application "System Events" to delete login item "{app_name}"
            '''
            os.system(f"osascript -e '{script}'")

    # ─── Dock 图标控制 ───

    def hide_dock_icon(self):
        """在macOS上隐藏Dock图标"""
        try:
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        except Exception as e:
            print(f"隐藏Dock图标失败: {e}")

    def show_dock_icon(self):
        """在macOS上显示Dock图标"""
        try:
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        except Exception as e:
            print(f"显示Dock图标失败: {e}")

    # ─── 窗口管理 ───

    def _on_window_close(self, e):
        """窗口关闭事件 — 隐藏到托盘"""
        if self._really_quit:
            self.page.window.destroy()
            return
        self.page.window.visible = False
        self.hide_dock_icon()
        self.tray.notify("壁纸更换器", "程序已最小化到系统托盘，右键点击图标可退出程序")

    def show_window(self):
        """显示窗口"""
        self.show_dock_icon()
        self.page.window.visible = True
        self.page.window.to_front()
        self.page.update()

    def quit_application(self):
        """退出应用"""
        self._really_quit = True
        self._stop_timer()
        self.tray.stop()
        self.show_dock_icon()
        self.page.window.destroy()


# ─── 入口 ───

async def main(page: ft.Page):
    """应用主入口"""
    app = WallpaperChanger(page)
    await page.window.center()


if __name__ == "__main__":
    ft.run(main)
