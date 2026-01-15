"""
素材ダウンローダーモジュール

BGM、効果音、背景画像などをダウンロードする
"""

from pathlib import Path
from typing import Dict, List, Optional, Union
from urllib.parse import urlparse
import re

import httpx
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn

from ..utils.config import Config
from ..utils.logger import get_logger


class AssetDownloader:
    """素材ダウンロードクラス"""

    # サポートする素材タイプと拡張子
    ASSET_TYPES = {
        "background": [".png", ".jpg", ".jpeg", ".webp", ".gif"],
        "bgm": [".mp3", ".wav", ".ogg", ".m4a"],
        "sfx": [".mp3", ".wav", ".ogg"],
        "character": [".png", ".gif", ".webp"],
        "font": [".ttf", ".otf", ".woff", ".woff2"],
    }

    def __init__(self):
        self.logger = get_logger()
        self.config = Config.get()

    def get_asset_type(self, url: str) -> Optional[str]:
        """URLから素材タイプを推測"""
        parsed = urlparse(url)
        path = Path(parsed.path)
        ext = path.suffix.lower()
        
        for asset_type, extensions in self.ASSET_TYPES.items():
            if ext in extensions:
                return asset_type
        
        return None

    def download_file(
        self,
        url: str,
        output_path: Path,
        timeout: float = 60.0,
    ) -> Path:
        """
        ファイルをダウンロード
        
        Args:
            url: ダウンロードURL
            output_path: 保存先パス
            timeout: タイムアウト（秒）
        
        Returns:
            保存先パス
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"ダウンロード: {url}")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            
            output_path.write_bytes(response.content)
        
        self.logger.info(f"保存完了: {output_path}")
        return output_path

    def download_with_progress(
        self,
        url: str,
        output_path: Path,
        timeout: float = 60.0,
    ) -> Path:
        """
        プログレス表示付きでダウンロード
        
        Args:
            url: ダウンロードURL
            output_path: 保存先パス
            timeout: タイムアウト（秒）
        
        Returns:
            保存先パス
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            DownloadColumn(),
        ) as progress:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                with client.stream("GET", url, headers=headers) as response:
                    response.raise_for_status()
                    
                    total = int(response.headers.get("content-length", 0))
                    task = progress.add_task(
                        f"ダウンロード: {output_path.name}",
                        total=total or None,
                    )
                    
                    with open(output_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)
                            progress.update(task, advance=len(chunk))
        
        self.logger.info(f"保存完了: {output_path}")
        return output_path

    def download_from_list(
        self,
        list_file: Union[str, Path],
        base_output_dir: Optional[Path] = None,
    ) -> Dict[str, List[Path]]:
        """
        リストファイルから素材を一括ダウンロード
        
        リストファイル形式:
        ```
        background https://example.com/bg.png
        bgm https://example.com/music.mp3
        sfx https://example.com/sound.wav
        # コメント行
        ```
        
        Args:
            list_file: リストファイルパス
            base_output_dir: 出力ベースディレクトリ
        
        Returns:
            タイプ別ダウンロードファイルリスト
        """
        list_file = Path(list_file)
        if not list_file.exists():
            raise FileNotFoundError(f"リストファイルが見つかりません: {list_file}")
        
        if base_output_dir is None:
            base_output_dir = Path("assets")
        
        results: Dict[str, List[Path]] = {
            "background": [],
            "bgm": [],
            "sfx": [],
            "character": [],
            "font": [],
            "other": [],
        }
        
        lines = list_file.read_text(encoding="utf-8").strip().split("\n")
        
        for line in lines:
            line = line.strip()
            
            # 空行とコメントをスキップ
            if not line or line.startswith("#"):
                continue
            
            # タイプとURLを分離
            parts = line.split(None, 1)
            if len(parts) == 2:
                asset_type, url = parts
            elif len(parts) == 1:
                url = parts[0]
                asset_type = self.get_asset_type(url) or "other"
            else:
                continue
            
            # タイプの正規化
            asset_type = asset_type.lower()
            if asset_type not in results:
                asset_type = "other"
            
            # ファイル名を決定
            parsed = urlparse(url)
            filename = Path(parsed.path).name
            if not filename:
                filename = f"asset_{len(results[asset_type]) + 1}"
            
            # 保存先パスを決定
            if asset_type == "other":
                output_dir = base_output_dir
            else:
                output_dir = base_output_dir / (asset_type + "s")  # backgrounds, bgms, etc.
            
            output_path = output_dir / filename
            
            try:
                downloaded = self.download_file(url, output_path)
                results[asset_type].append(downloaded)
            except Exception as e:
                self.logger.error(f"ダウンロード失敗: {url}: {e}")
        
        return results

    def download_from_urls(
        self,
        urls: List[str],
        output_dir: Path,
        auto_categorize: bool = True,
    ) -> List[Path]:
        """
        URLリストから素材をダウンロード
        
        Args:
            urls: URLリスト
            output_dir: 出力ディレクトリ
            auto_categorize: 自動カテゴリ分類
        
        Returns:
            ダウンロードファイルリスト
        """
        results = []
        
        for url in urls:
            try:
                parsed = urlparse(url)
                filename = Path(parsed.path).name
                if not filename:
                    filename = f"asset_{len(results) + 1}"
                
                if auto_categorize:
                    asset_type = self.get_asset_type(url)
                    if asset_type:
                        output_path = output_dir / (asset_type + "s") / filename
                    else:
                        output_path = output_dir / filename
                else:
                    output_path = output_dir / filename
                
                downloaded = self.download_file(url, output_path)
                results.append(downloaded)
                
            except Exception as e:
                self.logger.error(f"ダウンロード失敗: {url}: {e}")
        
        return results


# 素材サイト別ダウンローダー
class FreeSiteDownloader:
    """
    無料素材サイト用ダウンローダー
    
    注意: 各サイトの利用規約を確認してください
    """

    def __init__(self):
        self.logger = get_logger()
        self.downloader = AssetDownloader()

    def list_irasutoya_search(self, query: str) -> List[str]:
        """
        いらすとやで検索（参考URLリストを返す）
        
        Args:
            query: 検索クエリ
        
        Returns:
            検索結果URL（参考用）
        """
        # 実際のダウンロードは手動で行う必要があります
        search_url = f"https://www.irasutoya.com/search?q={query}"
        self.logger.info(f"いらすとや検索URL: {search_url}")
        return [search_url]

    def get_recommended_free_sites(self) -> Dict[str, Dict[str, str]]:
        """推奨無料素材サイトのリストを取得"""
        return {
            "backgrounds": {
                "いらすとや": "https://www.irasutoya.com/",
                "ぱくたそ": "https://www.pakutaso.com/",
                "Pixabay": "https://pixabay.com/ja/",
                "Unsplash": "https://unsplash.com/",
            },
            "bgm": {
                "DOVA-SYNDROME": "https://dova-s.jp/",
                "甘茶の音楽工房": "https://amachamusic.chagasi.com/",
                "魔王魂": "https://maou.audio/",
                "MusMus": "https://musmus.main.jp/",
            },
            "sfx": {
                "効果音ラボ": "https://soundeffect-lab.info/",
                "OtoLogic": "https://otologic.jp/",
                "くらげ工匠": "https://www.kurage-kosho.info/",
            },
            "characters": {
                "きつねゆっくり": "ニコニコで検索",
                "ゆっくり素材配布所": "ニコニコ静画で検索",
            },
        }
