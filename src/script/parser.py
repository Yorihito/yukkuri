"""
台本パーサーモジュール

YAML形式の台本ファイルを読み込む
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel


class LineData(BaseModel):
    """セリフデータ"""
    character: str
    text: str
    expression: str = "normal"
    effects: List[str] = []
    speed: float = 1.0
    pitch: float = 0.0
    volume: float = 1.0
    pause_after: float = 0.3  # セリフ後の間（秒）


class SceneData(BaseModel):
    """シーンデータ"""
    id: str
    background: Optional[str] = None
    bgm: Optional[str] = None
    bgm_volume: float = 0.3
    lines: List[LineData] = []
    transition: Optional[str] = None  # fade, slide, etc.
    transition_duration: float = 0.5


class ScriptSettings(BaseModel):
    """台本設定"""
    resolution: tuple[int, int] = (1920, 1080)
    fps: int = 30
    background: Optional[str] = None
    bgm: Optional[str] = None
    bgm_volume: float = 0.3


class Script(BaseModel):
    """台本"""
    title: str
    settings: ScriptSettings = ScriptSettings()
    scenes: List[SceneData] = []
    metadata: Dict[str, Any] = {}

    def get_all_lines(self) -> List[LineData]:
        """全セリフを取得"""
        lines = []
        for scene in self.scenes:
            lines.extend(scene.lines)
        return lines

    def get_characters(self) -> List[str]:
        """登場キャラクター一覧"""
        characters = set()
        for scene in self.scenes:
            for line in scene.lines:
                characters.add(line.character)
        return list(characters)

    def get_total_lines(self) -> int:
        """総セリフ数"""
        return sum(len(scene.lines) for scene in self.scenes)


class ScriptParser:
    """台本パーサー"""

    def __init__(self):
        pass

    def parse_file(self, path: Union[str, Path]) -> Script:
        """
        YAMLファイルから台本を読み込む
        
        Args:
            path: 台本ファイルパス
        
        Returns:
            台本オブジェクト
        """
        path = Path(path)
        
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        return self.parse_dict(data)

    def parse_dict(self, data: Dict[str, Any]) -> Script:
        """
        辞書から台本を読み込む
        
        Args:
            data: 台本データ（辞書）
        
        Returns:
            台本オブジェクト
        """
        # 設定
        settings_data = data.get("settings", {})
        if isinstance(settings_data.get("resolution"), list):
            settings_data["resolution"] = tuple(settings_data["resolution"])
        settings = ScriptSettings(**settings_data)
        
        # シーン
        scenes = []
        for scene_data in data.get("scenes", []):
            lines = []
            for line_data in scene_data.get("lines", []):
                if isinstance(line_data.get("effects"), str):
                    line_data["effects"] = [line_data["effects"]]
                lines.append(LineData(**line_data))
            
            scene = SceneData(
                id=scene_data.get("id", f"scene_{len(scenes) + 1}"),
                background=scene_data.get("background"),
                bgm=scene_data.get("bgm"),
                bgm_volume=scene_data.get("bgm_volume", 0.3),
                lines=lines,
                transition=scene_data.get("transition"),
                transition_duration=scene_data.get("transition_duration", 0.5),
            )
            scenes.append(scene)
        
        return Script(
            title=data.get("title", "Untitled"),
            settings=settings,
            scenes=scenes,
            metadata=data.get("metadata", {}),
        )

    def parse_text(self, text: str) -> Script:
        """
        YAMLテキストから台本を読み込む
        
        Args:
            text: YAMLテキスト
        
        Returns:
            台本オブジェクト
        """
        data = yaml.safe_load(text)
        return self.parse_dict(data)

    def parse_simple_format(self, text: str) -> Script:
        """
        シンプル形式から台本を読み込む
        
        形式:
        ```
        @title タイトル
        @bg 背景名
        @bgm BGM名
        
        霊夢: セリフ1
        魔理沙: セリフ2 [表情:smile]
        ```
        
        Args:
            text: シンプル形式テキスト
        
        Returns:
            台本オブジェクト
        """
        lines_raw = text.strip().split("\n")
        
        title = "Untitled"
        background = None
        bgm = None
        script_lines: List[LineData] = []
        
        # キャラクター名のエイリアス
        char_aliases = {
            "霊夢": "reimu",
            "魔理沙": "marisa",
            "ずんだもん": "zundamon",
        }
        
        for line in lines_raw:
            line = line.strip()
            if not line:
                continue
            
            # メタデータ
            if line.startswith("@title "):
                title = line[7:].strip()
            elif line.startswith("@bg "):
                background = line[4:].strip()
            elif line.startswith("@bgm "):
                bgm = line[5:].strip()
            elif ":" in line and not line.startswith("#"):
                # セリフ行をパース
                parts = line.split(":", 1)
                if len(parts) == 2:
                    char_name = parts[0].strip()
                    text_part = parts[1].strip()
                    
                    # エイリアス変換
                    character = char_aliases.get(char_name, char_name.lower())
                    
                    # 表情指定を抽出 [表情:smile]
                    expression = "normal"
                    if "[" in text_part and "]" in text_part:
                        import re
                        match = re.search(r"\[表情:(\w+)\]|\[expr:(\w+)\]", text_part)
                        if match:
                            expression = match.group(1) or match.group(2)
                            text_part = re.sub(r"\[表情:\w+\]|\[expr:\w+\]", "", text_part).strip()
                    
                    script_lines.append(LineData(
                        character=character,
                        text=text_part,
                        expression=expression,
                    ))
        
        # シーンを作成
        scene = SceneData(
            id="main",
            background=background,
            bgm=bgm,
            lines=script_lines,
        )
        
        return Script(
            title=title,
            settings=ScriptSettings(),
            scenes=[scene],
        )
