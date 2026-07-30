# -*- coding: utf-8 -*-
"""系统托盘模块 — pyobjc NSStatusItem 实现（macOS 原生）

使用 pyobjc 直接调用 macOS API，避免 pystray 与 Flet 的事件循环冲突。
"""

import os
import sys
import threading
from typing import Callable

import objc
from AppKit import (
    NSApplication,
    NSStatusBar,
    NSStatusItem,
    NSMenu,
    NSMenuItem,
    NSImage,
    NSVariableStatusItemLength,
)
from Foundation import NSObject


def _get_icon_path() -> str:
    """获取图标路径（兼容打包环境）"""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, "assets", "iconapp.png")


class TrayDelegate(NSObject):
    """托盘菜单事件委托"""

    def initWithCallbacks_(self, callbacks):
        self = objc.super(TrayDelegate, self).init()
        if self is None:
            return None
        self._on_show = callbacks.get("on_show")
        self._on_change = callbacks.get("on_change")
        self._on_quit = callbacks.get("on_quit")
        return self

    def showWindow_(self, sender):
        if self._on_show:
            self._on_show()

    def changeWallpaper_(self, sender):
        if self._on_change:
            self._on_change()

    def quitApp_(self, sender):
        if self._on_quit:
            self._on_quit()


class TrayManager:
    """macOS 系统托盘管理器（NSStatusItem）"""

    def __init__(
        self,
        on_show: Callable[[], None],
        on_change: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        self._on_show = on_show
        self._on_change = on_change
        self._on_quit = on_quit
        self._status_item = None
        self._delegate = None
        self._started = False

    def start(self) -> None:
        """启动系统托盘"""
        if self._started:
            return

        try:
            # 创建状态栏项
            status_bar = NSStatusBar.systemStatusBar()
            self._status_item = status_bar.statusItemWithLength_(NSVariableStatusItemLength)

            # 设置图标
            icon_path = _get_icon_path()
            if os.path.exists(icon_path):
                image = NSImage.alloc().initWithContentsOfFile_(icon_path)
                if image:
                    image.setSize_((18, 18))
                    image.setTemplate_(True)  # 适配深色/浅色模式
                    self._status_item.button().setImage_(image)

            # 设置提示文字
            self._status_item.button().setToolTip_("macOS壁纸更换器")

            # 创建委托
            self._delegate = TrayDelegate.alloc().initWithCallbacks_({
                "on_show": self._on_show,
                "on_change": self._on_change,
                "on_quit": self._on_quit,
            })

            # 创建菜单
            menu = NSMenu.alloc().init()

            # 显示窗口
            show_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "显示窗口", "showWindow:", ""
            )
            show_item.setTarget_(self._delegate)
            menu.addItem_(show_item)

            # 立即更换壁纸
            change_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "立即更换壁纸", "changeWallpaper:", ""
            )
            change_item.setTarget_(self._delegate)
            menu.addItem_(change_item)

            menu.addItem_(NSMenuItem.separatorItem())

            # 退出
            quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "退出", "quitApp:", "q"
            )
            quit_item.setTarget_(self._delegate)
            menu.addItem_(quit_item)

            self._status_item.setMenu_(menu)
            self._started = True

        except Exception as e:
            print(f"启动系统托盘失败: {e}")

    def stop(self) -> None:
        """停止系统托盘"""
        if self._status_item:
            try:
                NSStatusBar.systemStatusBar().removeStatusItem_(self._status_item)
            except Exception:
                pass
            self._status_item = None
        self._started = False

    def notify(self, title: str, message: str) -> None:
        """显示系统通知"""
        try:
            from AppKit import NSUserNotification, NSUserNotificationCenter

            notification = NSUserNotification.alloc().init()
            notification.setTitle_(title)
            notification.setInformativeText_(message)
            NSUserNotificationCenter.defaultUserNotificationCenter().deliverNotification_(
                notification
            )
        except Exception as e:
            print(f"通知发送失败: {e}")
