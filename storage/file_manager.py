r"""
JSON 存檔 / 讀檔 / Profile 管理
所有 Profile 儲存於 %APPDATA%\GameScriptPro\profiles\
"""
import json
import os
import shutil
from pathlib import Path
from typing import List, Optional
import uuid

from models.profile import Profile


def get_data_dir() -> Path:
    """取得應用程式資料目錄"""
    appdata = os.environ.get("APPDATA", str(Path.home()))
    data_dir = Path(appdata) / "GameScriptPro"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_profiles_dir() -> Path:
    profiles_dir = get_data_dir() / "profiles"
    profiles_dir.mkdir(exist_ok=True)
    return profiles_dir


def get_scripts_dir() -> Path:
    scripts_dir = get_data_dir() / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    return scripts_dir


def get_settings_path() -> Path:
    return get_data_dir() / "settings.json"


from models.macro import Macro


class FileManager:
    """Profile 與設定的持久化管理器"""

    # ── Profile CRUD ──────────────────────────────────────────
    @staticmethod
    def save_profile(profile: Profile) -> Path:
        """儲存一個 Profile 到獨立 JSON 檔案"""
        profiles_dir = get_profiles_dir()
        safe_name = "".join(c for c in profile.id if c.isalnum() or c in "-_")
        filepath = profiles_dir / f"{safe_name}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
        return filepath

    @staticmethod
    def load_profile(profile_id: str) -> Optional[Profile]:
        """根據 ID 載入 Profile"""
        profiles_dir = get_profiles_dir()
        filepath = profiles_dir / f"{profile_id}.json"
        if not filepath.exists():
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Profile.from_dict(data)

    @staticmethod
    def load_all_profiles() -> List[Profile]:
        """載入所有 Profile"""
        profiles_dir = get_profiles_dir()
        profiles = []
        for filepath in sorted(profiles_dir.glob("*.json")):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                profiles.append(Profile.from_dict(data))
            except Exception as e:
                print(f"[FileManager] 無法讀取 {filepath}: {e}")
        return profiles

    @staticmethod
    def list_profiles() -> List[Profile]:
        """列出所有 Profile 別名"""
        return FileManager.load_all_profiles()

    @staticmethod
    def delete_profile(profile_id: str) -> bool:
        """刪除 Profile"""
        profiles_dir = get_profiles_dir()
        filepath = profiles_dir / f"{profile_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    @staticmethod
    def export_profile(profile: Profile, export_path: str) -> bool:
        """匯出 Profile 到指定路徑"""
        try:
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[FileManager] 匯出失敗: {e}")
            return False

    @staticmethod
    def import_profile(import_path: str) -> Optional[Profile]:
        """從指定路徑匯入 Profile（會賦予新 ID 以避免衝突）"""
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            profile = Profile.from_dict(data)
            profile.id = str(uuid.uuid4())  # 給予新 ID
            FileManager.save_profile(profile)
            return profile
        except Exception as e:
            print(f"[FileManager] 匯入失敗: {e}")
            return None

    # ── 巨集腳本獨立儲存與管理 (免遊戲設定檔) ──────────────────
    @staticmethod
    def save_macro(macro: Macro) -> Path:
        """儲存單一巨集腳本到獨立檔案"""
        scripts_dir = get_scripts_dir()
        safe_id = "".join(c for c in macro.id if c.isalnum() or c in "-_")
        filepath = scripts_dir / f"{safe_id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(macro.to_dict(), f, ensure_ascii=False, indent=2)
        return filepath

    @staticmethod
    def delete_macro(macro_id: str) -> bool:
        """刪除指定巨集腳本檔案"""
        scripts_dir = get_scripts_dir()
        filepath = scripts_dir / f"{macro_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    @staticmethod
    def load_all_macros() -> List[Macro]:
        """載入所有獨立巨集腳本，若無則自動自既有 Profile 遷移"""
        scripts_dir = get_scripts_dir()
        macros: List[Macro] = []

        for fp in sorted(scripts_dir.glob("*.json")):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                macros.append(Macro.from_dict(data))
            except Exception as e:
                print(f"[FileManager] 讀取巨集失敗 {fp}: {e}")

        # 若目前尚未有獨立腳本，自動從舊版 Profiles 提取遷移
        if not macros:
            profiles = FileManager.load_all_profiles()
            for p in profiles:
                for m in p.macros:
                    FileManager.save_macro(m)
                    macros.append(m)

        # 若完全為空，建立一個預設腳本
        if not macros:
            default_m = Macro(name="預設腳本")
            FileManager.save_macro(default_m)
            macros.append(default_m)

        return macros

    # ── 自動視窗紀錄與通用設定 ──────────────────────────────
    @staticmethod
    def load_settings() -> dict:
        """載入通用設定檔"""
        sp = get_settings_path()
        if sp.exists():
            try:
                with open(sp, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[FileManager] 讀取設定檔失敗: {e}")
        return {}

    @staticmethod
    def save_settings(st: dict):
        """儲存通用設定檔"""
        sp = get_settings_path()
        try:
            with open(sp, "w", encoding="utf-8") as f:
                json.dump(st, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[FileManager] 儲存設定檔失敗: {e}")

    @staticmethod
    def save_window_record(title: str, hwnd: int):
        """記錄最新偵測到的目標視窗"""
        st = FileManager.load_settings()
        st["last_window_title"] = title
        st["last_window_hwnd"] = hwnd
        FileManager.save_settings(st)

    @staticmethod
    def get_window_record() -> dict:
        """取得記錄的目標視窗資訊"""
        st = FileManager.load_settings()
        return {
            "title": st.get("last_window_title", ""),
            "hwnd": st.get("last_window_hwnd", 0),
        }

