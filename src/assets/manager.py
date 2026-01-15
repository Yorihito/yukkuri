"""
素材管理モジュール

素材ファイルの検索・整理を行う
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union
import hashlib

from ..utils.config import Config
from ..utils.logger import get_logger


@dataclass
class Asset:
    """素材情報"""
    path: Path
    asset_type: str
    name: str
    size: int
    checksum: Optional[str] = None

    @property
    def extension(self) -> str:
        return self.path.suffix.lower()


class AssetManager:
    """素材管理クラス"""

    # 素材タイプと拡張子のマッピング
    TYPE_EXTENSIONS = {
        "background": [".png", ".jpg", ".jpeg", ".webp", ".gif"],
        "bgm": [".mp3", ".wav", ".ogg", ".m4a", ".flac"],
        "sfx": [".mp3", ".wav", ".ogg"],
        "character": [".png", ".gif", ".webp"],
        "font": [".ttf", ".otf", ".woff", ".woff2"],
        "video": [".mp4", ".mov", ".avi", ".webm"],
    }

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Args:
            base_dir: 素材ベースディレクトリ
        """
        self.logger = get_logger()
        self.config = Config.get()
        
        if base_dir:
            self.base_dir = base_dir
        else:
            self.base_dir = Path("assets")
        
        self._cache: Dict[str, List[Asset]] = {}

    def get_assets_dir(self, asset_type: str) -> Path:
        """素材タイプのディレクトリを取得"""
        dir_mapping = {
            "background": self.config.paths.backgrounds,
            "bgm": self.config.paths.bgm,
            "sfx": self.config.paths.sfx,
            "character": self.config.paths.characters,
            "font": self.config.paths.fonts,
        }
        
        if asset_type in dir_mapping:
            return Path(dir_mapping[asset_type])
        else:
            return self.base_dir / asset_type

    def list_assets(
        self,
        asset_type: str,
        use_cache: bool = True,
    ) -> List[Asset]:
        """
        指定タイプの素材一覧を取得
        
        Args:
            asset_type: 素材タイプ
            use_cache: キャッシュを使用するか
        
        Returns:
            素材リスト
        """
        if use_cache and asset_type in self._cache:
            return self._cache[asset_type]
        
        assets_dir = self.get_assets_dir(asset_type)
        extensions = self.TYPE_EXTENSIONS.get(asset_type, [])
        
        assets = []
        
        if assets_dir.exists():
            for ext in extensions:
                for path in assets_dir.rglob(f"*{ext}"):
                    assets.append(Asset(
                        path=path,
                        asset_type=asset_type,
                        name=path.stem,
                        size=path.stat().st_size,
                    ))
        
        self._cache[asset_type] = assets
        return assets

    def find_asset(
        self,
        name: str,
        asset_type: Optional[str] = None,
    ) -> Optional[Asset]:
        """
        名前で素材を検索
        
        Args:
            name: 素材名（拡張子なし可）
            asset_type: 素材タイプ（指定なしで全検索）
        
        Returns:
            見つかった素材
        """
        name_lower = name.lower()
        name_stem = Path(name).stem.lower()
        
        if asset_type:
            types_to_search = [asset_type]
        else:
            types_to_search = list(self.TYPE_EXTENSIONS.keys())
        
        for t in types_to_search:
            for asset in self.list_assets(t):
                if (asset.name.lower() == name_lower or 
                    asset.name.lower() == name_stem or
                    asset.path.name.lower() == name_lower):
                    return asset
        
        return None

    def find_assets_by_pattern(
        self,
        pattern: str,
        asset_type: Optional[str] = None,
    ) -> List[Asset]:
        """
        パターンで素材を検索
        
        Args:
            pattern: 検索パターン（部分一致）
            asset_type: 素材タイプ
        
        Returns:
            マッチした素材リスト
        """
        pattern_lower = pattern.lower()
        results = []
        
        if asset_type:
            types_to_search = [asset_type]
        else:
            types_to_search = list(self.TYPE_EXTENSIONS.keys())
        
        for t in types_to_search:
            for asset in self.list_assets(t):
                if pattern_lower in asset.name.lower():
                    results.append(asset)
        
        return results

    def get_random_asset(
        self,
        asset_type: str,
    ) -> Optional[Asset]:
        """ランダムに素材を取得"""
        import random
        
        assets = self.list_assets(asset_type)
        if assets:
            return random.choice(assets)
        return None

    def get_background(self, name: str) -> Optional[Path]:
        """背景画像を取得"""
        asset = self.find_asset(name, "background")
        return asset.path if asset else None

    def get_bgm(self, name: str) -> Optional[Path]:
        """BGMを取得"""
        asset = self.find_asset(name, "bgm")
        return asset.path if asset else None

    def get_sfx(self, name: str) -> Optional[Path]:
        """効果音を取得"""
        asset = self.find_asset(name, "sfx")
        return asset.path if asset else None

    def get_font(self, name: str) -> Optional[Path]:
        """フォントを取得"""
        asset = self.find_asset(name, "font")
        return asset.path if asset else None

    def ensure_directories(self) -> None:
        """必要なディレクトリを作成"""
        for asset_type in self.TYPE_EXTENSIONS.keys():
            dir_path = self.get_assets_dir(asset_type)
            dir_path.mkdir(parents=True, exist_ok=True)

    def get_asset_stats(self) -> Dict[str, Dict[str, int]]:
        """素材の統計情報を取得"""
        stats = {}
        
        for asset_type in self.TYPE_EXTENSIONS.keys():
            assets = self.list_assets(asset_type, use_cache=False)
            stats[asset_type] = {
                "count": len(assets),
                "total_size": sum(a.size for a in assets),
            }
        
        return stats

    def compute_checksum(self, path: Path) -> str:
        """ファイルのチェックサムを計算"""
        hasher = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def find_duplicates(self, asset_type: str) -> Dict[str, List[Path]]:
        """重複ファイルを検出"""
        assets = self.list_assets(asset_type, use_cache=False)
        
        checksums: Dict[str, List[Path]] = {}
        for asset in assets:
            checksum = self.compute_checksum(asset.path)
            if checksum not in checksums:
                checksums[checksum] = []
            checksums[checksum].append(asset.path)
        
        # 重複のみ返す
        return {k: v for k, v in checksums.items() if len(v) > 1}

    def clear_cache(self) -> None:
        """キャッシュをクリア"""
        self._cache.clear()
