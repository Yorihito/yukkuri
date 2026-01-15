"""
タイムライン管理モジュール

動画のセリフ・音声・立ち絵の時間軸管理を行う
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import json

from pydantic import BaseModel


class ItemType(str, Enum):
    """タイムラインアイテムの種類"""
    DIALOGUE = "dialogue"      # セリフ（音声+字幕）
    BACKGROUND = "background"  # 背景
    CHARACTER = "character"    # キャラクター立ち絵
    BGM = "bgm"               # BGM
    SFX = "sfx"               # 効果音
    TRANSITION = "transition"  # トランジション


class TimelineItem(BaseModel):
    """タイムラインアイテム"""
    id: str
    type: ItemType
    start_time: float  # 開始時間（秒）
    duration: float    # 持続時間（秒）
    
    # コンテンツ
    text: Optional[str] = None           # セリフテキスト
    character: Optional[str] = None      # キャラクター名
    expression: Optional[str] = None     # 表情
    audio_path: Optional[Path] = None    # 音声ファイルパス
    image_path: Optional[Path] = None    # 画像ファイルパス
    
    # スタイル
    position: Optional[tuple[int, int]] = None  # 表示位置
    scale: float = 1.0                          # スケール
    opacity: float = 1.0                        # 不透明度
    
    # エフェクト
    fade_in: float = 0.0   # フェードイン（秒）
    fade_out: float = 0.0  # フェードアウト（秒）
    
    # メタデータ
    layer: int = 0         # レイヤー番号（大きいほど前面）
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def end_time(self) -> float:
        """終了時間"""
        return self.start_time + self.duration

    def overlaps(self, other: "TimelineItem") -> bool:
        """他のアイテムと時間が重なっているか"""
        return (
            self.start_time < other.end_time and
            other.start_time < self.end_time
        )

    class Config:
        arbitrary_types_allowed = True


class Timeline:
    """タイムライン管理クラス"""

    def __init__(self):
        self.items: List[TimelineItem] = []
        self._id_counter = 0

    def _generate_id(self, prefix: str = "item") -> str:
        """ユニークIDを生成"""
        self._id_counter += 1
        return f"{prefix}_{self._id_counter:04d}"

    def add_item(self, item: TimelineItem) -> TimelineItem:
        """アイテムを追加"""
        if not item.id:
            item.id = self._generate_id(item.type.value)
        self.items.append(item)
        return item

    def add_dialogue(
        self,
        text: str,
        character: str,
        start_time: float,
        duration: float,
        audio_path: Optional[Path] = None,
        expression: str = "normal",
        **kwargs,
    ) -> TimelineItem:
        """セリフを追加"""
        item = TimelineItem(
            id=self._generate_id("dialogue"),
            type=ItemType.DIALOGUE,
            start_time=start_time,
            duration=duration,
            text=text,
            character=character,
            expression=expression,
            audio_path=audio_path,
            layer=10,  # セリフは前面
            **kwargs,
        )
        return self.add_item(item)

    def add_background(
        self,
        image_path: Path,
        start_time: float,
        duration: float,
        **kwargs,
    ) -> TimelineItem:
        """背景を追加"""
        item = TimelineItem(
            id=self._generate_id("bg"),
            type=ItemType.BACKGROUND,
            start_time=start_time,
            duration=duration,
            image_path=image_path,
            layer=0,  # 背景は最背面
            **kwargs,
        )
        return self.add_item(item)

    def add_character(
        self,
        character: str,
        expression: str,
        start_time: float,
        duration: float,
        image_path: Optional[Path] = None,
        position: Optional[tuple[int, int]] = None,
        **kwargs,
    ) -> TimelineItem:
        """キャラクター立ち絵を追加"""
        item = TimelineItem(
            id=self._generate_id("char"),
            type=ItemType.CHARACTER,
            start_time=start_time,
            duration=duration,
            character=character,
            expression=expression,
            image_path=image_path,
            position=position,
            layer=5,  # キャラクターは中間
            **kwargs,
        )
        return self.add_item(item)

    def add_bgm(
        self,
        audio_path: Path,
        start_time: float,
        duration: float,
        fade_in: float = 1.0,
        fade_out: float = 1.0,
        **kwargs,
    ) -> TimelineItem:
        """BGMを追加"""
        item = TimelineItem(
            id=self._generate_id("bgm"),
            type=ItemType.BGM,
            start_time=start_time,
            duration=duration,
            audio_path=audio_path,
            fade_in=fade_in,
            fade_out=fade_out,
            layer=0,
            **kwargs,
        )
        return self.add_item(item)

    def add_sfx(
        self,
        audio_path: Path,
        start_time: float,
        **kwargs,
    ) -> TimelineItem:
        """効果音を追加"""
        # 効果音の長さは後で音声ファイルから取得
        item = TimelineItem(
            id=self._generate_id("sfx"),
            type=ItemType.SFX,
            start_time=start_time,
            duration=1.0,  # 仮の値
            audio_path=audio_path,
            layer=1,
            **kwargs,
        )
        return self.add_item(item)

    def get_items_at(self, time: float) -> List[TimelineItem]:
        """指定時間のアイテムを取得"""
        return [
            item for item in self.items
            if item.start_time <= time < item.end_time
        ]

    def get_items_by_type(self, item_type: ItemType) -> List[TimelineItem]:
        """種類でアイテムを取得"""
        return [item for item in self.items if item.type == item_type]

    def get_items_by_character(self, character: str) -> List[TimelineItem]:
        """キャラクターでアイテムを取得"""
        return [item for item in self.items if item.character == character]

    def get_total_duration(self) -> float:
        """タイムライン全体の長さ（秒）"""
        if not self.items:
            return 0.0
        return max(item.end_time for item in self.items)

    def get_items_in_range(
        self,
        start: float,
        end: float,
    ) -> List[TimelineItem]:
        """時間範囲内のアイテムを取得"""
        return [
            item for item in self.items
            if item.start_time < end and item.end_time > start
        ]

    def sort_by_layer(self) -> List[TimelineItem]:
        """レイヤー順にソート"""
        return sorted(self.items, key=lambda x: x.layer)

    def sort_by_time(self) -> List[TimelineItem]:
        """時間順にソート"""
        return sorted(self.items, key=lambda x: x.start_time)

    def remove_item(self, item_id: str) -> bool:
        """アイテムを削除"""
        for i, item in enumerate(self.items):
            if item.id == item_id:
                self.items.pop(i)
                return True
        return False

    def clear(self) -> None:
        """全アイテムを削除"""
        self.items.clear()
        self._id_counter = 0

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式にエクスポート"""
        return {
            "total_duration": self.get_total_duration(),
            "items": [
                {
                    **item.model_dump(),
                    "audio_path": str(item.audio_path) if item.audio_path else None,
                    "image_path": str(item.image_path) if item.image_path else None,
                }
                for item in self.sort_by_time()
            ],
        }

    def to_json(self, path: Optional[Path] = None, indent: int = 2) -> str:
        """JSON形式にエクスポート"""
        json_str = json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_str, encoding="utf-8")
        return json_str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Timeline":
        """辞書形式からインポート"""
        timeline = cls()
        for item_data in data.get("items", []):
            # パスの変換
            if item_data.get("audio_path"):
                item_data["audio_path"] = Path(item_data["audio_path"])
            if item_data.get("image_path"):
                item_data["image_path"] = Path(item_data["image_path"])
            # 位置のタプル変換
            if item_data.get("position"):
                item_data["position"] = tuple(item_data["position"])
            
            item = TimelineItem(**item_data)
            timeline.add_item(item)
        return timeline

    @classmethod
    def from_json(cls, path: Path) -> "Timeline":
        """JSONファイルからインポート"""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)
