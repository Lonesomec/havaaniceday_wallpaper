# -*- coding: utf-8 -*-
"""设置持久化层 — dataclass + JSON 替代 QSettings"""

import json
import plistlib
from dataclasses import dataclass, field, asdict
from pathlib import Path


# 配置文件路径
SETTINGS_DIR = Path.home() / "Library" / "Application Support" / "WallpaperChanger"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

# 旧版 QSettings plist 路径（用于一次性迁移）
OLD_PLIST_PATH = Path.home() / "Library" / "Preferences" / "com.WallpaperChanger.Settings.plist"


@dataclass
class AppSettings:
    """应用设置数据类"""

    rotation_enabled: bool = True
    rotation_interval_index: int = 0
    change_lock_screen: bool = True
    auto_start: bool = False
    folder_path: str = ""
    url_groups: dict = field(
        default_factory=lambda: {"default_site": ["https://example.com/wallpapers"]}
    )

    def save(self) -> None:
        """保存设置到 JSON 文件"""
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls) -> "AppSettings":
        """加载设置，若 JSON 不存在则尝试从旧版 plist 迁移"""
        # 优先读取 JSON
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls(
                    rotation_enabled=data.get("rotation_enabled", True),
                    rotation_interval_index=int(data.get("rotation_interval_index", 0)),
                    change_lock_screen=data.get("change_lock_screen", True),
                    auto_start=data.get("auto_start", False),
                    folder_path=data.get("folder_path", ""),
                    url_groups=data.get("url_groups", {"default_site": ["https://example.com/wallpapers"]}),
                )
            except (json.JSONDecodeError, KeyError, TypeError):
                pass  # JSON 损坏，回退默认值

        # 尝试从旧版 QSettings plist 迁移
        migrated = cls._migrate_from_plist()
        if migrated:
            migrated.save()  # 迁移后立即保存为 JSON
            return migrated

        return cls()

    @classmethod
    def _migrate_from_plist(cls) -> "AppSettings | None":
        """从旧版 QSettings plist 文件迁移设置（只读不删）"""
        if not OLD_PLIST_PATH.exists():
            return None

        try:
            with open(OLD_PLIST_PATH, "rb") as f:
                plist_data = plistlib.load(f)

            # QSettings 存储的键名映射
            def _get_bool(key: str, default: bool) -> bool:
                val = plist_data.get(key)
                if val is None:
                    return default
                if isinstance(val, str):
                    return val.lower() == "true"
                return bool(val)

            return cls(
                rotation_enabled=_get_bool("rotation_enabled", True),
                rotation_interval_index=int(plist_data.get("rotation_interval", 0)),
                change_lock_screen=_get_bool("change_lock_screen", True),
                auto_start=_get_bool("auto_start", False),
                folder_path=plist_data.get("folder_path", ""),
                url_groups=plist_data.get("url_groups", {"default_site": ["https://example.com/wallpapers"]}),
            )
        except Exception:
            return None  # 迁移失败，静默回退默认值
