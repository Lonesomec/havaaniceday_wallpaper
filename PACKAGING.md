# 打包指南

## 前置条件

- macOS（仅支持 macOS，因使用 `osascript` 和 `pyobjc`）
- Python 3.14
- [uv](https://docs.astral.sh/uv/) 或 pip

## 开发环境

```bash
uv sync
```

或

```bash
pip install -r requirements.txt
pip install pyobjc-core pyobjc-framework-cocoa
```

> `requirements.txt` 不包含 pyobjc，需额外安装。

## 用 PyInstaller 打包为 .app

### 准备工作

```bash
uv pip install pyinstaller
```

### 构建

项目已包含 `wallpaper_changer.spec`，直接使用：

```bash
pyinstaller wallpaper_changer.spec
```

产物在 `dist/wallpaper_changer.app`。

### 构建产物内容

- `wallpaper_changer.app` — 原生 macOS 应用包（窗口模式，无控制台）
- 图标：`iconapp.icns`（应用）+ `assets/iconapp.png`（托盘 + PyInstaller data）
- 托盘图标路径自动兼容打包环境（`system_tray.py` 中已处理 `sys._MEIPASS`）

### spec 关键配置

| 选项 | 值 | 说明 |
|------|-----|------|
| 入口 | `wallpaper_changer.py` | 主入口 |
| `console` | `False` | 不显示控制台窗口 |
| `icon` | `iconapp.icns` | .app 图标 |
| `datas` | `assets/iconapp.png → assets` | 托盘图标数据文件 |

## 运行已打包的应用

```bash
open dist/wallpaper_changer.app
```

或双击 Finder 中的 `wallpaper_changer.app`。

## 代码签名与公证（分发前）

如需分发给其他 macOS 用户，建议签名：

```bash
# 签名
codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name" dist/wallpaper_changer.app

# 验证
codesign --verify --deep --strict --verbose=2 dist/wallpaper_changer.app
spctl --assess --verbose=4 dist/wallpaper_changer.app
```

公证（macOS notarization）：

```bash
# 压缩
ditto -c -k --keepParent dist/wallpaper_changer.app wallpaper_changer.zip

# 上传公证
xcrun notarytool submit wallpaper_changer.zip --apple-id your@email.com --team-id YOUR_TEAM --password @keychain:AC_PASSWORD --wait

#  stapler
xcrun stapler staple dist/wallpaper_changer.app
```

## 常见问题

### 应用打开后闪退

检查控制台日志：

```bash
log show --predicate 'process == "wallpaper_changer"' --last 1m
```

或在 Terminal 中直接运行可执行文件查看错误：

```bash
dist/wallpaper_changer.app/Contents/MacOS/wallpaper_changer
```

### 托盘图标不显示

确认 `assets/iconapp.png` 文件存在且已打包到 `.app` 中：

```bash
ls dist/wallpaper_changer.app/Contents/Resources/assets/
```

### Dock 图标行为异常

应用关闭窗口时自动隐藏 Dock 图标（`NSApplicationActivationPolicyAccessory`），重新打开窗口时恢复。如果 Dock 图标行为异常，检查 `pyobjc-framework-cocoa` 是否安装正确。

### 壁纸不自动轮换

定时器基于 `asyncio`，确保 Flet 的事件循环正常运行。打包后如果定时器不触发，尝试减小轮换间隔排查。

## 已知限制

- 锁屏壁纸功能依赖屏幕保护程序路径，可能不支持所有 macOS 版本
- 开机自启通过 AppleScript 设置 `System Events` login items 实现，非 LaunchAgent plist
- 仅支持 macOS，不支持 Windows/Linux
