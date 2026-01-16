"""
字幕生成モジュール

Pillowを使用して字幕画像を生成する
"""

from pathlib import Path
from typing import Optional, Tuple, Union
import io

from PIL import Image, ImageDraw, ImageFont

from ..utils.config import Config
from ..utils.logger import get_logger


class SubtitleGenerator:
    """字幕生成クラス"""

    def __init__(
        self,
        font_path: Optional[str] = None,
        font_size: Optional[int] = None,
        color: Optional[str] = None,
        stroke_color: Optional[str] = None,
        stroke_width: Optional[int] = None,
    ):
        """
        Args:
            font_path: フォントファイルパス
            font_size: フォントサイズ
            color: 文字色（16進数）
            stroke_color: 縁取り色（16進数）
            stroke_width: 縁取り幅
        """
        self.logger = get_logger()
        config = Config.get()
        
        # configから設定を読み込む（引数で上書き可能）
        self.font_path = font_path or config.subtitle.font
        self.font_size = font_size or config.subtitle.font_size
        self.color = color or config.subtitle.color
        self.stroke_color = stroke_color or config.subtitle.stroke_color
        self.stroke_width = stroke_width if stroke_width is not None else config.subtitle.stroke_width
        
        # フォントの読み込み
        self._font: Optional[ImageFont.FreeTypeFont] = None

    @property
    def font(self) -> ImageFont.FreeTypeFont:
        """フォントを取得（遅延読み込み）"""
        if self._font is None:
            try:
                self._font = ImageFont.truetype(self.font_path, self.font_size)
            except Exception as e:
                self.logger.warning(f"フォント読み込み失敗: {e}, デフォルトフォント使用")
                # システムフォントを試す
                try:
                    self._font = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", self.font_size)
                except:
                    self._font = ImageFont.load_default()
        return self._font

    def _hex_to_rgba(self, hex_color: str, alpha: int = 255) -> Tuple[int, int, int, int]:
        """16進数カラーをRGBAに変換"""
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (r, g, b, alpha)
        elif len(hex_color) == 8:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            a = int(hex_color[6:8], 16)
            return (r, g, b, a)
        else:
            return (255, 255, 255, alpha)

    def get_text_size(self, text: str) -> Tuple[int, int]:
        """テキストのサイズを取得"""
        # ダミー画像を作成してテキストサイズを計測
        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)
        bbox = draw.textbbox((0, 0), text, font=self.font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        return (width + self.stroke_width * 2, height + self.stroke_width * 2)

    def create_subtitle_image(
        self,
        text: str,
        max_width: Optional[int] = None,
        background_color: Optional[str] = None,
        background_opacity: int = 0,
        padding: int = 10,
    ) -> Image.Image:
        """
        字幕画像を生成
        
        Args:
            text: 字幕テキスト
            max_width: 最大幅（折り返し用）
            background_color: 背景色（16進数）
            background_opacity: 背景不透明度（0-255）
            padding: パディング
        
        Returns:
            字幕画像（RGBA）
        """
        # テキストを折り返し
        if max_width:
            text = self._wrap_text(text, max_width - padding * 2)
        
        # サイズ計算
        text_width, text_height = self.get_text_size(text)
        
        # 複数行の場合はサイズを再計算
        lines = text.split("\n")
        if len(lines) > 1:
            max_line_width = 0
            for line in lines:
                line_width, _ = self.get_text_size(line)
                max_line_width = max(max_line_width, line_width)
            text_width = max_line_width
            text_height = (text_height + 5) * len(lines)
        
        img_width = text_width + padding * 2
        img_height = text_height + padding * 2
        
        # 画像作成
        if background_color and background_opacity > 0:
            bg_rgba = self._hex_to_rgba(background_color, background_opacity)
            img = Image.new("RGBA", (img_width, img_height), bg_rgba)
        else:
            img = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 0))
        
        draw = ImageDraw.Draw(img)
        
        # テキスト描画位置
        x = padding
        y = padding
        
        text_color = self._hex_to_rgba(self.color)
        stroke_color = self._hex_to_rgba(self.stroke_color)
        
        # テキスト描画（縁取り付き）
        draw.text(
            (x, y),
            text,
            font=self.font,
            fill=text_color,
            stroke_width=self.stroke_width,
            stroke_fill=stroke_color,
        )
        
        return img

    def _wrap_text(self, text: str, max_width: int) -> str:
        """テキストを折り返す"""
        if not max_width:
            return text
        
        words = list(text)  # 日本語は文字単位
        lines = []
        current_line = ""
        
        for char in words:
            test_line = current_line + char
            test_width, _ = self.get_text_size(test_line)
            
            if test_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        
        if current_line:
            lines.append(current_line)
        
        return "\n".join(lines)

    def save_subtitle(
        self,
        text: str,
        output_path: Union[str, Path],
        max_width: Optional[int] = None,
        **kwargs,
    ) -> Path:
        """字幕画像を保存"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        img = self.create_subtitle_image(text, max_width=max_width, **kwargs)
        img.save(output_path, "PNG")
        
        self.logger.debug(f"字幕保存: {output_path}")
        return output_path

    def create_name_tag(
        self,
        name: str,
        color: str = "#FFFF00",
        background_color: str = "#000000",
        background_opacity: int = 180,
        font_size: Optional[int] = None,
    ) -> Image.Image:
        """
        キャラクター名タグを生成
        
        Args:
            name: キャラクター名
            color: 文字色
            background_color: 背景色
            background_opacity: 背景不透明度
            font_size: フォントサイズ（指定なしで通常の80%）
        
        Returns:
            名前タグ画像
        """
        # 一時的にフォントサイズを変更
        original_font = self._font
        original_size = self.font_size
        
        if font_size:
            self.font_size = font_size
        else:
            self.font_size = int(self.font_size * 0.8)
        self._font = None  # 再読み込みを強制
        
        original_color = self.color
        self.color = color
        
        # 名前タグ生成
        img = self.create_subtitle_image(
            name,
            background_color=background_color,
            background_opacity=background_opacity,
            padding=8,
        )
        
        # 設定を復元
        self.font_size = original_size
        self._font = original_font
        self.color = original_color
        
        return img
