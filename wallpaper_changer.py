import os
import sys
import time
import random
import requests
import shutil
import json
from pathlib import Path
from datetime import datetime
from threading import Thread
from urllib.parse import urlparse
import objc
from AppKit import NSApplication, NSApplicationActivationPolicyRegular, NSApplicationActivationPolicyAccessory
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QGroupBox, QRadioButton, QCheckBox,
                               QPushButton, QLabel, QLineEdit, QFileDialog,
                               QMessageBox, QButtonGroup, QSpinBox, QComboBox,
                               QSystemTrayIcon, QMenu, QDialog, QPlainTextEdit)
from PySide6.QtCore import Qt, QTimer, QSettings, QRect, QSize
from PySide6.QtGui import QScreen, QPixmap, QIcon, QAction

# 导入爬虫模块
from wallpaper_crawler import WallpaperCrawler


class WallpaperChanger(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("macOS壁纸更换器")
        self.setMinimumSize(500, 400)

        # 中心窗口部件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # 主布局
        self.main_layout = QVBoxLayout(self.central_widget)

        # 设置存储
        self.settings = QSettings("WallpaperChanger", "Settings")

        # 壁纸目录
        self.wallpaper_dir = Path.home() / "Pictures" / "Wallpapers"
        if not self.wallpaper_dir.exists():
            self.wallpaper_dir.mkdir(parents=True)

        # 初始化系统托盘
        self.init_tray()

        # 初始化UI
        self.init_ui()

        # 初始化壁纸列表
        self.wallpapers = []
        self.current_wallpaper_index = 0

        # 定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.change_wallpaper)

        # 爬虫实例
        self.crawler = WallpaperCrawler(self.wallpaper_dir)

        # 加载设置
        self.load_settings()

        # 启动壁纸扫描线程
        self.scan_wallpapers()

    def init_tray(self):
        if hasattr(sys, '_MEIPASS'):
            # 如果是打包后的环境
            base_path = sys._MEIPASS
        else:
            # 开发环境，直接使用当前路径
            base_path = os.path.abspath(".")
        icon_path = os.path.join(base_path, 'assets/iconapp.png')
        # 设置窗口图标
        self.setWindowIcon(QIcon(icon_path))
        # 在macOS上，还需要设置应用程序图标
        if hasattr(QApplication, 'setWindowIcon'):
            QApplication.setWindowIcon(QIcon(icon_path))
        # 创建系统托盘图标
        self.tray_icon = QSystemTrayIcon(self)
        # self.tray_icon.setIcon(QIcon.fromTheme("preferences-desktop-wallpaper"))
        self.tray_icon.setIcon(QIcon(icon_path))
        # 创建托盘菜单
        tray_menu = QMenu()

        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)

        change_action = QAction("立即更换壁纸", self)
        change_action.triggered.connect(self.change_wallpaper)
        tray_menu.addAction(change_action)

        tray_menu.addSeparator()

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def init_ui(self):
        # 轮换设置组
        rotation_group = QGroupBox("壁纸轮换设置")
        rotation_layout = QVBoxLayout()

        # 轮换时间选择
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("轮换时间:"))

        self.rotation_combo = QComboBox()
        self.rotation_combo.addItems(["30分钟", "1小时", "2小时", "3小时", "6小时", "12小时", "1天"])
        time_layout.addWidget(self.rotation_combo)

        self.rotation_enabled = QCheckBox("启用自动轮换")
        self.rotation_enabled.setChecked(True)  # 默认勾选
        time_layout.addWidget(self.rotation_enabled)
        time_layout.addStretch()

        rotation_layout.addLayout(time_layout)

        # 同时更换锁屏壁纸
        self.change_lock_screen = QCheckBox("同时更换锁屏壁纸")
        self.change_lock_screen.setChecked(True)  # 默认勾选
        rotation_layout.addWidget(self.change_lock_screen)

        # 开机自启
        self.auto_start = QCheckBox("开机自动启动")
        rotation_layout.addWidget(self.auto_start)

        rotation_group.setLayout(rotation_layout)
        self.main_layout.addWidget(rotation_group)

        # 壁纸来源组
        source_group = QGroupBox("壁纸来源")
        source_layout = QVBoxLayout()

        # 离线来源
        offline_layout = QHBoxLayout()
        offline_layout.addWidget(QLabel("本地文件夹:"))

        self.folder_path = QLineEdit()
        offline_layout.addWidget(self.folder_path)

        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.browse_folder)
        offline_layout.addWidget(self.browse_btn)

        source_layout.addLayout(offline_layout)

        # 在线来源
        online_layout = QVBoxLayout()

        # 爬虫URL组
        url_group_layout = QHBoxLayout()
        url_group_layout.addWidget(QLabel("壁纸网站URL组:"))

        self.url_group_combo = QComboBox()
        self.url_group_combo.addItems(["默认壁纸网站", "自定义URL组"])
        url_group_layout.addWidget(self.url_group_combo)

        self.edit_urls_btn = QPushButton("编辑URL组")
        self.edit_urls_btn.clicked.connect(self.edit_url_groups)
        url_group_layout.addWidget(self.edit_urls_btn)

        online_layout.addLayout(url_group_layout)

        # 爬虫设置
        crawl_layout = QHBoxLayout()
        self.crawl_btn = QPushButton("开始爬取壁纸")
        self.crawl_btn.clicked.connect(self.start_crawling)
        crawl_layout.addWidget(self.crawl_btn)

        self.crawl_progress = QLabel("就绪")
        crawl_layout.addWidget(self.crawl_progress)

        online_layout.addLayout(crawl_layout)
        source_layout.addLayout(online_layout)

        source_group.setLayout(source_layout)
        self.main_layout.addWidget(source_group)

        # 按钮组
        button_layout = QHBoxLayout()

        self.apply_btn = QPushButton("立即更换")
        self.apply_btn.clicked.connect(self.change_wallpaper)
        button_layout.addWidget(self.apply_btn)

        self.start_btn = QPushButton("开始自动更换")
        self.start_btn.clicked.connect(self.toggle_auto_change)
        button_layout.addWidget(self.start_btn)

        self.save_btn = QPushButton("保存设置")
        self.save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_btn)

        self.main_layout.addLayout(button_layout)

        # 状态栏
        self.status_bar = QLabel("就绪")
        self.main_layout.addWidget(self.status_bar)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择壁纸文件夹")
        if folder:
            self.folder_path.setText(folder)
            self.scan_wallpapers()

    def edit_url_groups(self):
        # 创建URL组编辑对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("编辑URL组")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)

        # URL组列表
        url_groups = self.settings.value("url_groups", {})
        if not url_groups:
            url_groups = {
                "default_site": ["https://example.com/wallpapers"]
            }

        self.url_groups_edit = QPlainTextEdit()
        self.url_groups_edit.setPlainText(json.dumps(url_groups, indent=2))
        layout.addWidget(QLabel("URL组(JSON格式):"))
        layout.addWidget(self.url_groups_edit)

        # 按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(lambda: self.save_url_groups(dialog))
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        dialog.exec()

    def save_url_groups(self, dialog):
        try:
            url_groups = json.loads(self.url_groups_edit.toPlainText())
            self.settings.setValue("url_groups", url_groups)

            # 更新URL组下拉框
            self.url_group_combo.clear()
            self.url_group_combo.addItems(url_groups.keys())

            dialog.accept()
            self.status_bar.setText("URL组已保存")
        except json.JSONDecodeError:
            QMessageBox.warning(self, "错误", "JSON格式不正确")

    def start_crawling(self):
        # 获取选中的URL组
        selected_group = self.url_group_combo.currentText()
        url_groups = self.settings.value("url_groups", {})

        if selected_group in url_groups:
            urls = url_groups[selected_group]

            # 在新线程中运行爬虫
            self.crawl_thread = Thread(target=self.run_crawler, args=(urls,))
            self.crawl_thread.daemon = True
            self.crawl_thread.start()

            self.status_bar.setText(f"开始爬取 {selected_group} 的壁纸...")
        else:
            self.status_bar.setText("请先添加URL组")

    def run_crawler(self, urls):
        try:
            self.crawl_progress.setText("爬取中...")

            # 调用爬虫
            success_count = self.crawler.crawl(urls)

            # 更新UI需要在主线程中执行
            self.crawl_progress.setText(f"爬取完成，成功下载 {success_count} 张壁纸")
            self.status_bar.setText(f"爬取完成，成功下载 {success_count} 张壁纸")

            # 重新扫描壁纸
            self.scan_wallpapers()
        except Exception as e:
            self.crawl_progress.setText(f"爬取失败: {str(e)}")
            self.status_bar.setText(f"爬取失败: {str(e)}")

    def scan_wallpapers(self):
        # 清空当前壁纸列表
        self.wallpapers = []

        # 添加本地壁纸
        folder = self.folder_path.text()
        if folder and os.path.exists(folder):
            for ext in ["*.jpg", "*.jpeg", "*.png", "*.bmp", "*.gif", "*.avif"]:
                self.wallpapers.extend(Path(folder).glob(f"**/{ext}"))

        # 添加爬虫下载的壁纸
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.bmp", "*.gif", "*.avif"]:
            self.wallpapers.extend(self.wallpaper_dir.glob(f"**/{ext}"))

        self.status_bar.setText(f"找到 {len(self.wallpapers)} 张壁纸")

    def change_wallpaper(self):
        if not self.wallpapers:
            self.status_bar.setText("没有可用的壁纸")
            return

        # 选择下一张壁纸
        self.current_wallpaper_index = (self.current_wallpaper_index + 1) % len(self.wallpapers)
        wallpaper = self.wallpapers[self.current_wallpaper_index]

        try:
            # 处理壁纸文件/URL
            if isinstance(wallpaper, Path):  # 本地文件
                wallpaper_path = str(wallpaper)
            else:  # 在线URL
                # 下载图片
                wallpaper_path = self.download_wallpaper(wallpaper)

            # 设置桌面壁纸
            self.set_desktop_wallpaper(wallpaper_path)

            # 设置锁屏壁纸（如果启用）
            if self.change_lock_screen.isChecked():
                self.set_lock_screen_wallpaper(wallpaper_path)

            self.status_bar.setText(f"已更换壁纸: {os.path.basename(wallpaper_path)}")

        except Exception as e:
            self.status_bar.setText(f"更换壁纸失败: {str(e)}")

    def download_wallpaper(self, url):
        try:
            # 从URL下载图片
            response = requests.get(url, stream=True)
            response.raise_for_status()

            # 生成文件名
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            if not filename:
                filename = f"wallpaper_{int(time.time())}.jpg"

            # 保存路径
            save_path = self.wallpaper_dir / filename

            # 下载文件
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return str(save_path)

        except Exception as e:
            raise Exception(f"下载壁纸失败: {str(e)}")

    def set_desktop_wallpaper(self, wallpaper_path):
        try:
            # 使用AppleScript设置桌面壁纸
            script = f'''
            tell application "System Events"
                set picture of every desktop to "{wallpaper_path}"
            end tell
            '''
            os.system(f"osascript -e '{script}'")
        except Exception as e:
            raise Exception(f"设置桌面壁纸失败: {str(e)}")

    def set_lock_screen_wallpaper(self, wallpaper_path):
        try:
            # macOS设置锁屏壁纸比较复杂，这里使用一个近似的方法
            # 注意：这可能需要用户授权，并且可能不是所有macOS版本都有效
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

    def toggle_auto_change(self):
        if self.timer.isActive():
            self.timer.stop()
            self.start_btn.setText("开始自动更换")
            self.status_bar.setText("已停止自动更换")
        else:
            # 获取轮换时间（分钟）
            time_text = self.rotation_combo.currentText()
            time_map = {
                "30分钟": 30,
                "1小时": 60,
                "2小时": 120,
                "3小时": 180,
                "6小时": 360,
                "12小时": 720,
                "1天": 1440
            }
            interval = time_map.get(time_text, 30) * 60 * 1000  # 转换为毫秒

            self.timer.start(interval)
            self.start_btn.setText("停止自动更换")
            self.status_bar.setText("已开始自动更换")

    def save_settings(self):
        # 保存设置
        self.settings.setValue("rotation_enabled", self.rotation_enabled.isChecked())
        self.settings.setValue("rotation_interval", self.rotation_combo.currentIndex())
        self.settings.setValue("change_lock_screen", self.change_lock_screen.isChecked())
        self.settings.setValue("auto_start", self.auto_start.isChecked())
        self.settings.setValue("folder_path", self.folder_path.text())

        # 设置开机自启
        self.set_auto_start(self.auto_start.isChecked())

        self.status_bar.setText("设置已保存")

    def set_auto_start(self, enable):
        # macOS设置开机自启
        app_path = os.path.abspath(sys.argv[0])
        app_name = "WallpaperChanger"

        if enable:
            # 创建启动项
            script = f'''
            tell application "System Events" to make login item at end with properties {{path:"{app_path}", hidden:false, name:"{app_name}"}}
            '''
            os.system(f"osascript -e '{script}'")
        else:
            # 移除启动项
            script = f'''
            tell application "System Events" to delete login item "{app_name}"
            '''
            os.system(f"osascript -e '{script}'")

    def load_settings(self):
        # 加载设置
        if self.settings.value("rotation_enabled") == "true":
            self.rotation_enabled.setChecked(True)

        rotation_index = int(self.settings.value("rotation_interval", 0))
        self.rotation_combo.setCurrentIndex(rotation_index)

        if self.settings.value("change_lock_screen") == "true":
            self.change_lock_screen.setChecked(True)

        if self.settings.value("auto_start") == "true":
            self.auto_start.setChecked(True)

        folder_path = self.settings.value("folder_path", "")
        self.folder_path.setText(folder_path)

        # 加载URL组
        url_groups = self.settings.value("url_groups", {})
        if url_groups:
            self.url_group_combo.clear()
            self.url_group_combo.addItems(url_groups.keys())

        # 如果设置了自动轮换，启动定时器
        if self.rotation_enabled.isChecked():
            self.toggle_auto_change()

    def center_window(self):
        # 将窗口居中显示
        frame_geometry = self.frameGeometry()
        screen = QApplication.primaryScreen()
        center_point = screen.availableGeometry().center()
        frame_geometry.moveCenter(center_point)
        self.move(frame_geometry.topLeft())

    def showEvent(self, event):
        # 窗口显示时居中
        self.center_window()
        super().showEvent(event)

    def closeEvent(self, event):
        # 点击关闭按钮时隐藏到系统托盘，不退出程序
        event.ignore()
        self.hide()
        # 在macOS上隐藏Dock图标
        self.hide_dock_icon()
        self.tray_icon.showMessage(
            "壁纸更换器",
            "程序已最小化到系统托盘，右键点击图标可退出程序",
            QSystemTrayIcon.Information,
            2000
        )

    def tray_icon_activated(self, reason):
        # 点击托盘图标时显示窗口
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_window()

    def show_window(self):
        # 显示窗口并置于前台
        # 在macOS上显示Dock图标
        self.show_dock_icon()
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_dock_icon(self):
        """在macOS上隐藏Dock图标"""
        try:
            # 使用AppleScript隐藏Dock图标
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        except Exception as e:
            print(f"隐藏Dock图标失败: {e}")

    def show_dock_icon(self):
        """在macOS上显示Dock图标"""
        try:
            # 使用AppleScript显示Dock图标
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        except Exception as e:
            print(f"显示Dock图标失败: {e}")

    def quit_application(self):
        # 退出应用程序
        self.show_dock_icon()
        self.tray_icon.hide()
        QApplication.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 设置应用程序名称（与AppleScript中的名称匹配）
    app.setApplicationName("WallpaperChanger")
    app.setApplicationDisplayName("壁纸更换器")

    # 确保应用程序在最后一个窗口关闭时不会退出
    app.setQuitOnLastWindowClosed(False)

    window = WallpaperChanger()
    # window.tray_icon.setIcon(QIcon("Contents/icon.png"))
    window.show()
    sys.exit(app.exec())