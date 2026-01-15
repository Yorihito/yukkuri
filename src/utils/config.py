"""
設定管理モジュール

YAML設定ファイルの読み込みと管理を行う
"""

from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from pydantic import BaseModel, Field


class VoicevoxConfig(BaseModel):
    """VOICEVOX設定"""
    url: str = "http://localhost:50021"
    default_speaker: int = 0
    speakers: Dict[str, int] = Field(default_factory=lambda: {"reimu": 0, "marisa": 1})


class VideoConfig(BaseModel):
    """動画設定"""
    resolution: tuple[int, int] = (1920, 1080)
    fps: int = 30
    codec: str = "libx264"
    audio_codec: str = "aac"
    bitrate: str = "8000k"
    preset: str = "medium"


class SubtitleConfig(BaseModel):
    """字幕設定"""
    font: str = "assets/fonts/NotoSansJP-Bold.ttf"
    font_size: int = 48
    color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_width: int = 3
    position: str = "bottom"
    margin_bottom: int = 80


class CharacterConfig(BaseModel):
    """キャラクター設定"""
    name: str
    position: tuple[int, int] = (0, 0)
    scale: float = 1.0
    default_expression: str = "normal"


class PathsConfig(BaseModel):
    """パス設定"""
    characters: str = "assets/characters"
    backgrounds: str = "assets/backgrounds"
    bgm: str = "assets/bgm"
    sfx: str = "assets/sfx"
    fonts: str = "assets/fonts"
    output_audio: str = "output/audio"
    output_video: str = "output/video"


class TimingConfig(BaseModel):
    """タイミング設定"""
    fade_in_duration: float = 0.5
    fade_out_duration: float = 0.5
    line_pause: float = 0.3
    scene_transition: float = 1.0


class AIConfig(BaseModel):
    """AI設定"""
    enabled: bool = False
    provider: str = "openai"
    model: str = "gpt-4"
    api_key: Optional[str] = None


class Config(BaseModel):
    """メイン設定クラス"""
    voicevox: VoicevoxConfig = Field(default_factory=VoicevoxConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    subtitle: SubtitleConfig = Field(default_factory=SubtitleConfig)
    characters: Dict[str, CharacterConfig] = Field(default_factory=dict)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    timing: TimingConfig = Field(default_factory=TimingConfig)
    ai: AIConfig = Field(default_factory=AIConfig)

    _instance: Optional["Config"] = None
    _config_path: Optional[Path] = None

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """設定ファイルを読み込む"""
        if config_path is None:
            config_path = Path("config.yaml")
        
        if not config_path.exists():
            # デフォルト設定を返す
            return cls()
        
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        # characters の変換
        if "characters" in data:
            characters = {}
            for name, char_data in data["characters"].items():
                if isinstance(char_data.get("position"), list):
                    char_data["position"] = tuple(char_data["position"])
                characters[name] = CharacterConfig(**char_data)
            data["characters"] = characters
        
        # resolution の変換
        if "video" in data and isinstance(data["video"].get("resolution"), list):
            data["video"]["resolution"] = tuple(data["video"]["resolution"])
        
        config = cls(**data)
        cls._instance = config
        cls._config_path = config_path
        return config

    @classmethod
    def get(cls) -> "Config":
        """シングルトンインスタンスを取得"""
        if cls._instance is None:
            cls._instance = cls.load()
        return cls._instance

    def get_character_config(self, character: str) -> Optional[CharacterConfig]:
        """キャラクター設定を取得"""
        return self.characters.get(character)

    def get_speaker_id(self, character: str) -> int:
        """キャラクターのスピーカーIDを取得"""
        return self.voicevox.speakers.get(character, self.voicevox.default_speaker)

    def ensure_directories(self) -> None:
        """必要なディレクトリを作成"""
        base_path = self._config_path.parent if self._config_path else Path(".")
        
        for path_name in ["characters", "backgrounds", "bgm", "sfx", "fonts", "output_audio", "output_video"]:
            path = base_path / getattr(self.paths, path_name)
            path.mkdir(parents=True, exist_ok=True)
