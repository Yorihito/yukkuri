"""
キャラクター管理モジュール

立ち絵の読み込み・表情管理・口パクアニメーション
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import json

from PIL import Image

from ..utils.config import Config
from ..utils.logger import get_logger


@dataclass
class CharacterExpression:
    """キャラクター表情"""
    name: str
    image_path: Path
    mouth_open_path: Optional[Path] = None  # 口開き画像（口パク用）
    
    def get_image(self) -> Image.Image:
        """表情画像を取得"""
        return Image.open(self.image_path).convert("RGBA")
    
    def get_mouth_open_image(self) -> Optional[Image.Image]:
        """口開き画像を取得"""
        if self.mouth_open_path and self.mouth_open_path.exists():
            return Image.open(self.mouth_open_path).convert("RGBA")
        return None


@dataclass
class Character:
    """キャラクター"""
    name: str                                    # キャラクター名
    display_name: str                            # 表示名（霊夢、魔理沙等）
    base_path: Path                              # 素材ベースパス
    expressions: Dict[str, CharacterExpression] = field(default_factory=dict)
    default_expression: str = "normal"
    position: Tuple[int, int] = (0, 0)
    scale: float = 1.0
    
    def get_expression(self, expression: str) -> Optional[CharacterExpression]:
        """表情を取得"""
        return self.expressions.get(expression) or self.expressions.get(self.default_expression)
    
    def get_expression_image(self, expression: str) -> Optional[Image.Image]:
        """表情画像を取得"""
        expr = self.get_expression(expression)
        if expr:
            return expr.get_image()
        return None
    
    def list_expressions(self) -> List[str]:
        """利用可能な表情一覧"""
        return list(self.expressions.keys())


class CharacterManager:
    """キャラクター管理クラス"""

    # 表情名のエイリアス
    EXPRESSION_ALIASES = {
        "normal": ["default", "neutral", "普通"],
        "smile": ["happy", "笑顔", "にっこり"],
        "sad": ["悲しい", "泣き"],
        "angry": ["怒り", "怒る"],
        "surprised": ["驚き", "びっくり"],
        "smug": ["ドヤ顔", "得意"],
        "wink": ["ウインク"],
        "excited": ["興奮", "テンション高い"],
        "thinking": ["考え中", "悩み"],
    }

    def __init__(self, characters_dir: Optional[Path] = None):
        """
        Args:
            characters_dir: キャラクター素材ディレクトリ
        """
        self.logger = get_logger()
        self.config = Config.get()
        
        if characters_dir:
            self.characters_dir = characters_dir
        else:
            self.characters_dir = Path(self.config.paths.characters)
        
        self.characters: Dict[str, Character] = {}
        
        # キャラクターを自動読み込み
        self._load_characters()

    def _load_characters(self) -> None:
        """キャラクター素材を自動読み込み"""
        if not self.characters_dir.exists():
            self.logger.warning(f"キャラクターディレクトリが存在しません: {self.characters_dir}")
            return
        
        for char_dir in self.characters_dir.iterdir():
            if char_dir.is_dir():
                try:
                    character = self._load_character_from_dir(char_dir)
                    self.characters[character.name] = character
                    self.logger.debug(f"キャラクター読み込み: {character.name} ({len(character.expressions)}表情)")
                except Exception as e:
                    self.logger.warning(f"キャラクター読み込み失敗: {char_dir}: {e}")

    def _load_character_from_dir(self, char_dir: Path) -> Character:
        """ディレクトリからキャラクターを読み込み"""
        name = char_dir.name
        
        # キャラクター設定ファイルを確認
        config_file = char_dir / "character.json"
        if config_file.exists():
            char_config = json.loads(config_file.read_text(encoding="utf-8"))
            display_name = char_config.get("display_name", name)
            default_expression = char_config.get("default_expression", "normal")
            position = tuple(char_config.get("position", [0, 0]))
            scale = char_config.get("scale", 1.0)
        else:
            display_name = self._guess_display_name(name)
            default_expression = "normal"
            position = self._get_default_position(name)
            scale = 1.0
        
        # 表情画像を読み込み
        expressions = {}
        for image_file in char_dir.glob("*.png"):
            expr_name = image_file.stem.lower()
            
            # エイリアスを正規化
            normalized_name = self._normalize_expression_name(expr_name)
            
            # 口開き画像を探す
            mouth_open = char_dir / f"{image_file.stem}_open.png"
            
            expressions[normalized_name] = CharacterExpression(
                name=normalized_name,
                image_path=image_file,
                mouth_open_path=mouth_open if mouth_open.exists() else None,
            )
        
        return Character(
            name=name,
            display_name=display_name,
            base_path=char_dir,
            expressions=expressions,
            default_expression=default_expression,
            position=position,
            scale=scale,
        )

    def _guess_display_name(self, name: str) -> str:
        """ディレクトリ名から表示名を推測"""
        name_mapping = {
            "reimu": "霊夢",
            "marisa": "魔理沙",
            "zundamon": "ずんだもん",
            "shikoku_metan": "四国めたん",
        }
        return name_mapping.get(name.lower(), name)

    def _get_default_position(self, name: str) -> Tuple[int, int]:
        """キャラクターのデフォルト位置を取得"""
        config = Config.get()
        char_config = config.get_character_config(name)
        if char_config:
            return char_config.position
        
        # デフォルト位置
        width = config.video.resolution[0]
        height = config.video.resolution[1]
        
        positions = {
            "reimu": (300, height - 300),
            "marisa": (width - 300, height - 300),
        }
        return positions.get(name.lower(), (width // 2, height - 300))

    def _normalize_expression_name(self, name: str) -> str:
        """表情名を正規化"""
        name_lower = name.lower()
        
        for canonical, aliases in self.EXPRESSION_ALIASES.items():
            if name_lower == canonical or name_lower in [a.lower() for a in aliases]:
                return canonical
        
        return name_lower

    def get_character(self, name: str) -> Optional[Character]:
        """キャラクターを取得"""
        return self.characters.get(name.lower()) or self.characters.get(name)

    def get_expression_image(
        self,
        character_name: str,
        expression: str = "normal",
    ) -> Optional[Image.Image]:
        """キャラクターの表情画像を取得"""
        character = self.get_character(character_name)
        if character:
            return character.get_expression_image(expression)
        return None

    def get_expression_path(
        self,
        character_name: str,
        expression: str = "normal",
    ) -> Optional[Path]:
        """キャラクターの表情画像パスを取得"""
        character = self.get_character(character_name)
        if character:
            expr = character.get_expression(expression)
            if expr:
                return expr.image_path
        return None

    def list_characters(self) -> List[str]:
        """利用可能なキャラクター一覧"""
        return list(self.characters.keys())

    def list_expressions(self, character_name: str) -> List[str]:
        """キャラクターの表情一覧"""
        character = self.get_character(character_name)
        if character:
            return character.list_expressions()
        return []

    def create_lip_sync_frames(
        self,
        character_name: str,
        expression: str,
        audio_duration: float,
        fps: int = 10,
    ) -> List[Image.Image]:
        """
        口パクアニメーションフレームを生成
        
        Args:
            character_name: キャラクター名
            expression: 表情
            audio_duration: 音声長（秒）
            fps: フレームレート
        
        Returns:
            フレーム画像リスト
        """
        character = self.get_character(character_name)
        if not character:
            return []
        
        expr = character.get_expression(expression)
        if not expr:
            return []
        
        base_image = expr.get_image()
        mouth_open = expr.get_mouth_open_image()
        
        if not mouth_open:
            # 口開き画像がない場合は基本画像のみ
            frame_count = int(audio_duration * fps)
            return [base_image] * frame_count
        
        # 口パクパターン生成
        frames = []
        frame_count = int(audio_duration * fps)
        
        for i in range(frame_count):
            # 簡易的な口パク（交互に開閉）
            # より高度な実装では音声の振幅に基づく
            if i % 3 in [0, 1]:  # 2フレーム開き、1フレーム閉じ
                frames.append(mouth_open)
            else:
                frames.append(base_image)
        
        return frames

    def add_character(self, character: Character) -> None:
        """キャラクターを追加"""
        self.characters[character.name] = character
        self.logger.info(f"キャラクター追加: {character.name}")

    def reload(self) -> None:
        """キャラクターを再読み込み"""
        self.characters.clear()
        self._load_characters()
