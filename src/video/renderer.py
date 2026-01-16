"""
動画レンダリングモジュール

MoviePyを使用して動画を生成する
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import tempfile

from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
)
from moviepy.video.fx.all import fadein, fadeout
from PIL import Image
import numpy as np

from .timeline import Timeline, TimelineItem, ItemType
from .subtitle import SubtitleGenerator
from ..utils.config import Config
from ..utils.logger import get_logger


class VideoRenderer:
    """動画レンダリングクラス"""

    def __init__(
        self,
        resolution: Optional[Tuple[int, int]] = None,
        fps: int = 30,
    ):
        """
        Args:
            resolution: 解像度 (width, height)
            fps: フレームレート
        """
        self.logger = get_logger()
        config = Config.get()
        
        self.resolution = resolution or config.video.resolution
        self.fps = fps
        self.subtitle_generator = SubtitleGenerator()
        
        # 一時ファイル管理
        self._temp_files: List[Path] = []

    def _cleanup_temp_files(self) -> None:
        """一時ファイルを削除"""
        for path in self._temp_files:
            try:
                path.unlink(missing_ok=True)
            except Exception as e:
                self.logger.warning(f"一時ファイル削除失敗: {path}: {e}")
        self._temp_files.clear()

    def create_background_clip(
        self,
        source: Union[str, Path, Tuple[int, int, int]],
        duration: float,
    ) -> VideoFileClip | ColorClip | ImageClip:
        """
        背景クリップを作成
        
        Args:
            source: 画像パス、動画パス、または色(RGB)
            duration: 持続時間
        
        Returns:
            背景クリップ
        """
        if isinstance(source, tuple):
            # 単色背景
            return ColorClip(
                size=self.resolution,
                color=source,
                duration=duration,
            )
        
        path = Path(source)
        if path.suffix.lower() in [".mp4", ".mov", ".avi", ".webm"]:
            # 動画背景
            clip = VideoFileClip(str(path))
            if clip.duration < duration:
                # ループ
                clip = clip.loop(duration=duration)
            else:
                clip = clip.subclip(0, duration)
            return clip.resize(self.resolution)
        else:
            # 画像背景 - Pillowでリサイズしてから読み込み
            img = Image.open(path).convert("RGB")
            img = img.resize(self.resolution, Image.Resampling.LANCZOS)
            img_array = np.array(img)
            return ImageClip(img_array, duration=duration)

    def create_character_clip(
        self,
        image_path: Path,
        duration: float,
        position: Tuple[int, int],
        scale: float = 1.0,
        fade_in: float = 0.0,
        fade_out: float = 0.0,
        flip_horizontal: bool = False,
    ) -> ImageClip:
        """
        キャラクター立ち絵クリップを作成
        
        Args:
            image_path: 立ち絵画像パス
            duration: 持続時間
            position: 表示位置 (x, y)
            scale: スケール
            fade_in: フェードイン時間
            fade_out: フェードアウト時間
            flip_horizontal: 左右反転（Trueで右向きに）
        
        Returns:
            キャラクタークリップ
        """
        # Pillowで読み込み（RGBAサポート）
        img = Image.open(image_path).convert("RGBA")
        
        # 左右反転
        if flip_horizontal:
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        
        if scale != 1.0:
            new_size = (int(img.width * scale), int(img.height * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        img_array = np.array(img)
        clip = ImageClip(img_array, duration=duration, transparent=True)
        
        # 位置設定（中心基準から左上を計算）
        pos_x = position[0] - img.width // 2
        pos_y = position[1] - img.height // 2
        clip = clip.set_position((pos_x, pos_y))
        
        # フェード適用
        if fade_in > 0:
            clip = fadein(clip, fade_in)
        if fade_out > 0:
            clip = fadeout(clip, fade_out)
        
        return clip

    def create_subtitle_clip(
        self,
        text: str,
        duration: float,
        position: str = "bottom",
        margin_bottom: int = 80,
    ) -> ImageClip:
        """
        字幕クリップを作成
        
        Args:
            text: 字幕テキスト
            duration: 持続時間
            position: 位置（bottom, center, top）
            margin_bottom: 下マージン
        
        Returns:
            字幕クリップ
        """
        # 字幕画像を生成
        max_width = int(self.resolution[0] * 0.9)
        subtitle_img = self.subtitle_generator.create_subtitle_image(
            text,
            max_width=max_width,
        )
        
        # PIL ImageをNumPy配列に変換
        img_array = np.array(subtitle_img)
        
        clip = ImageClip(img_array, duration=duration, transparent=True)
        
        # 位置設定
        if position == "bottom":
            clip = clip.set_position(("center", self.resolution[1] - clip.size[1] - margin_bottom))
        elif position == "top":
            clip = clip.set_position(("center", margin_bottom))
        else:  # center
            clip = clip.set_position("center")
        
        return clip

    def create_scrolling_text_background(
        self,
        text: str,
        duration: float,
        text_color: tuple = (80, 80, 100),
        bg_color: tuple = (25, 25, 35),
        font_size: int = 28,
    ) -> CompositeVideoClip:
        """
        下から上にスクロールするテキスト背景を作成
        
        Args:
            text: スクロールするテキスト
            duration: 持続時間
            text_color: テキスト色 (RGB)
            bg_color: 背景色 (RGB)
            font_size: フォントサイズ
        
        Returns:
            スクロールテキスト背景クリップ
        """
        from moviepy.editor import VideoClip
        from PIL import ImageDraw, ImageFont
        
        # フォント読み込み
        try:
            font = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", font_size)
        except:
            font = ImageFont.load_default()
        
        # テキスト描画エリア（横80%）
        text_width = int(self.resolution[0] * 0.8)
        margin_x = int(self.resolution[0] * 0.1)
        line_height = int(font_size * 1.4)
        
        # テキストを行に分割
        lines = text.strip().split("\n")
        total_text_height = len(lines) * line_height
        
        # スクロール範囲: 画面下端から始まり、テキストが全部上に消えるまで
        scroll_range = self.resolution[1] + total_text_height
        
        def make_frame(t):
            # 背景画像作成
            img = Image.new("RGB", self.resolution, bg_color)
            draw = ImageDraw.Draw(img)
            
            # スクロール位置計算（下から上へ）
            progress = t / duration
            start_y = self.resolution[1] - int(progress * scroll_range)
            
            # テキスト描画
            for i, line in enumerate(lines):
                y = start_y + i * line_height
                # 画面内のテキストのみ描画
                if -line_height < y < self.resolution[1]:
                    draw.text((margin_x, y), line, font=font, fill=text_color)
            
            return np.array(img)
        
        return VideoClip(make_frame, duration=duration)

    def render_from_timeline(
        self,
        timeline: Timeline,
        output_path: Union[str, Path],
        codec: str = "libx264",
        audio_codec: str = "aac",
        bitrate: str = "8000k",
        preset: str = "medium",
        threads: int = 4,
        scrolling_text: Optional[str] = None,
    ) -> Path:
        """
        タイムラインから動画をレンダリング
        
        Args:
            timeline: タイムラインオブジェクト
            output_path: 出力ファイルパス
            codec: 動画コーデック
            audio_codec: 音声コーデック
            bitrate: ビットレート
            preset: エンコードプリセット
            threads: スレッド数
            scrolling_text: スクロールテキスト（指定時はテキストスクロール背景を使用）
        
        Returns:
            出力ファイルパス
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        total_duration = timeline.get_total_duration()
        self.logger.info(f"動画レンダリング開始: {total_duration:.2f}秒")
        
        video_clips = []
        audio_clips = []
        
        # 背景クリップを作成
        if scrolling_text:
            # スクロールテキスト背景を使用
            bg_clip = self.create_scrolling_text_background(
                scrolling_text,
                total_duration,
                text_color=(90, 90, 110),  # 少し明るめ
            )
            video_clips.append(bg_clip)
        else:
            bg_items = timeline.get_items_by_type(ItemType.BACKGROUND)
            if bg_items:
                for item in bg_items:
                    if item.image_path and item.image_path.exists():
                        clip = self.create_background_clip(
                            item.image_path,
                            item.duration,
                        ).set_start(item.start_time)
                        video_clips.append(clip)
            else:
                # デフォルト背景（黒）
                video_clips.append(
                    ColorClip(
                        size=self.resolution,
                        color=(30, 30, 30),
                        duration=total_duration,
                    )
                )
        
        # キャラクタークリップ
        char_items = timeline.get_items_by_type(ItemType.CHARACTER)
        for item in char_items:
            if item.image_path and item.image_path.exists():
                position = item.position or (self.resolution[0] // 2, self.resolution[1] // 2)
                clip = self.create_character_clip(
                    item.image_path,
                    item.duration,
                    position,
                    item.scale,
                    item.fade_in,
                    item.fade_out,
                    flip_horizontal=item.flip_horizontal,
                ).set_start(item.start_time)
                video_clips.append(clip)
        
        # セリフ（字幕）
        dialogue_items = timeline.get_items_by_type(ItemType.DIALOGUE)
        for item in dialogue_items:
            if item.text:
                clip = self.create_subtitle_clip(
                    item.text,
                    item.duration,
                ).set_start(item.start_time)
                video_clips.append(clip)
            
            # セリフ音声
            if item.audio_path and item.audio_path.exists():
                audio = AudioFileClip(str(item.audio_path)).set_start(item.start_time)
                audio_clips.append(audio)
        
        # BGM
        bgm_items = timeline.get_items_by_type(ItemType.BGM)
        for item in bgm_items:
            if item.audio_path and item.audio_path.exists():
                audio = AudioFileClip(str(item.audio_path))
                
                # 長さ調整（短い場合はループ、長い場合はカット）
                if audio.duration < item.duration:
                    # BGMが短い場合はループ
                    from moviepy.editor import concatenate_audioclips
                    loops_needed = int(item.duration / audio.duration) + 1
                    audio = concatenate_audioclips([audio] * loops_needed)
                    audio = audio.subclip(0, item.duration)
                elif audio.duration > item.duration:
                    audio = audio.subclip(0, item.duration)
                
                # フェード適用
                if item.fade_in > 0:
                    audio = audio.audio_fadein(item.fade_in)
                if item.fade_out > 0:
                    audio = audio.audio_fadeout(item.fade_out)
                
                audio = audio.set_start(item.start_time)
                # BGMは音量を下げる（0.15 = 控えめ）
                audio = audio.volumex(0.15)
                audio_clips.append(audio)
        
        # 効果音
        sfx_items = timeline.get_items_by_type(ItemType.SFX)
        for item in sfx_items:
            if item.audio_path and item.audio_path.exists():
                audio = AudioFileClip(str(item.audio_path)).set_start(item.start_time)
                audio_clips.append(audio)
        
        # 動画合成
        self.logger.info(f"動画クリップ数: {len(video_clips)}, 音声クリップ数: {len(audio_clips)}")
        
        final_video = CompositeVideoClip(video_clips, size=self.resolution)
        
        if audio_clips:
            final_audio = CompositeAudioClip(audio_clips)
            final_video = final_video.set_audio(final_audio)
        
        final_video = final_video.set_duration(total_duration)
        
        # 出力
        self.logger.info(f"エンコード中: {output_path}")
        final_video.write_videofile(
            str(output_path),
            fps=self.fps,
            codec=codec,
            audio_codec=audio_codec,
            bitrate=bitrate,
            preset=preset,
            threads=threads,
            logger=None,  # MoviePyのログを抑制
        )
        
        # クリーンアップ
        final_video.close()
        for clip in video_clips:
            clip.close()
        for clip in audio_clips:
            clip.close()
        
        self._cleanup_temp_files()
        
        self.logger.info(f"動画生成完了: {output_path}")
        return output_path

    def render_preview(
        self,
        timeline: Timeline,
        time: float,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Image.Image:
        """
        指定時間のプレビュー画像を生成
        
        Args:
            timeline: タイムライン
            time: 時間（秒）
            output_path: 出力パス（指定時は保存）
        
        Returns:
            プレビュー画像
        """
        # 指定時間のアイテムを取得
        items = timeline.get_items_at(time)
        
        # 空の画像を作成
        result = Image.new("RGBA", self.resolution, (30, 30, 30, 255))
        
        # レイヤー順にソート
        items.sort(key=lambda x: x.layer)
        
        for item in items:
            if item.type == ItemType.BACKGROUND and item.image_path:
                bg = Image.open(item.image_path).convert("RGBA")
                bg = bg.resize(self.resolution)
                result = Image.alpha_composite(result, bg)
            
            elif item.type == ItemType.CHARACTER and item.image_path:
                char = Image.open(item.image_path).convert("RGBA")
                if item.scale != 1.0:
                    new_size = (
                        int(char.width * item.scale),
                        int(char.height * item.scale),
                    )
                    char = char.resize(new_size)
                
                position = item.position or (self.resolution[0] // 2, self.resolution[1] // 2)
                # 中心位置から左上座標を計算
                paste_pos = (
                    position[0] - char.width // 2,
                    position[1] - char.height // 2,
                )
                result.paste(char, paste_pos, char)
            
            elif item.type == ItemType.DIALOGUE and item.text:
                subtitle = self.subtitle_generator.create_subtitle_image(
                    item.text,
                    max_width=int(self.resolution[0] * 0.9),
                )
                # 下部中央に配置
                paste_pos = (
                    (self.resolution[0] - subtitle.width) // 2,
                    self.resolution[1] - subtitle.height - 80,
                )
                result.paste(subtitle, paste_pos, subtitle)
        
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            result.save(output_path)
        
        return result
