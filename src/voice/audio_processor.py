"""
音声処理モジュール

音声ファイルの加工・結合を行う
"""

from pathlib import Path
from typing import List, Optional, Union
import io
import wave
import struct

from pydub import AudioSegment

from ..utils.logger import get_logger


class AudioProcessor:
    """音声ファイル処理クラス"""

    def __init__(self):
        self.logger = get_logger()

    def load_audio(self, path: Union[str, Path]) -> AudioSegment:
        """音声ファイルを読み込む"""
        path = Path(path)
        self.logger.debug(f"音声読み込み: {path}")
        return AudioSegment.from_file(path)

    def save_audio(
        self,
        audio: AudioSegment,
        path: Union[str, Path],
        format: str = "wav",
    ) -> Path:
        """音声ファイルを保存する"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        audio.export(path, format=format)
        self.logger.debug(f"音声保存: {path}")
        return path

    def normalize_volume(
        self,
        audio: AudioSegment,
        target_dBFS: float = -20.0,
    ) -> AudioSegment:
        """
        音量を正規化する
        
        Args:
            audio: 音声データ
            target_dBFS: 目標音量（dBFS）
        
        Returns:
            正規化された音声データ
        """
        change_in_dBFS = target_dBFS - audio.dBFS
        return audio.apply_gain(change_in_dBFS)

    def add_silence(
        self,
        audio: AudioSegment,
        before_ms: int = 0,
        after_ms: int = 0,
    ) -> AudioSegment:
        """
        音声の前後に無音を追加する
        
        Args:
            audio: 音声データ
            before_ms: 前に追加する無音（ミリ秒）
            after_ms: 後に追加する無音（ミリ秒）
        
        Returns:
            無音が追加された音声データ
        """
        silence_before = AudioSegment.silent(duration=before_ms)
        silence_after = AudioSegment.silent(duration=after_ms)
        return silence_before + audio + silence_after

    def concatenate(
        self,
        audio_list: List[AudioSegment],
        crossfade_ms: int = 0,
    ) -> AudioSegment:
        """
        複数の音声を結合する
        
        Args:
            audio_list: 音声データのリスト
            crossfade_ms: クロスフェード（ミリ秒）
        
        Returns:
            結合された音声データ
        """
        if not audio_list:
            return AudioSegment.empty()
        
        result = audio_list[0]
        for audio in audio_list[1:]:
            if crossfade_ms > 0:
                result = result.append(audio, crossfade=crossfade_ms)
            else:
                result = result + audio
        
        return result

    def concatenate_files(
        self,
        file_paths: List[Union[str, Path]],
        output_path: Union[str, Path],
        crossfade_ms: int = 0,
        silence_between_ms: int = 0,
    ) -> Path:
        """
        複数の音声ファイルを結合する
        
        Args:
            file_paths: 音声ファイルパスのリスト
            output_path: 出力ファイルパス
            crossfade_ms: クロスフェード（ミリ秒）
            silence_between_ms: ファイル間の無音（ミリ秒）
        
        Returns:
            出力ファイルパス
        """
        audio_list = []
        for path in file_paths:
            audio = self.load_audio(path)
            if silence_between_ms > 0 and audio_list:
                audio_list.append(AudioSegment.silent(duration=silence_between_ms))
            audio_list.append(audio)
        
        result = self.concatenate(audio_list, crossfade_ms=0)  # 無音挿入時はクロスフェードしない
        return self.save_audio(result, output_path)

    def get_duration(self, audio: AudioSegment) -> float:
        """音声の長さを取得（秒）"""
        return len(audio) / 1000.0

    def get_duration_from_file(self, path: Union[str, Path]) -> float:
        """ファイルから音声の長さを取得（秒）"""
        audio = self.load_audio(path)
        return self.get_duration(audio)

    def adjust_speed(
        self,
        audio: AudioSegment,
        speed_factor: float,
    ) -> AudioSegment:
        """
        再生速度を調整する
        
        Args:
            audio: 音声データ
            speed_factor: 速度係数（1.0が標準、2.0で2倍速）
        
        Returns:
            速度調整された音声データ
        """
        if speed_factor == 1.0:
            return audio
        
        # フレームレートを変更することで速度調整
        new_frame_rate = int(audio.frame_rate * speed_factor)
        return audio._spawn(
            audio.raw_data,
            overrides={"frame_rate": new_frame_rate}
        ).set_frame_rate(audio.frame_rate)

    def mix_audio(
        self,
        audio1: AudioSegment,
        audio2: AudioSegment,
        position_ms: int = 0,
    ) -> AudioSegment:
        """
        2つの音声をミックスする
        
        Args:
            audio1: ベース音声
            audio2: 重ねる音声
            position_ms: audio2を開始する位置（ミリ秒）
        
        Returns:
            ミックスされた音声データ
        """
        return audio1.overlay(audio2, position=position_ms)

    def apply_fade(
        self,
        audio: AudioSegment,
        fade_in_ms: int = 0,
        fade_out_ms: int = 0,
    ) -> AudioSegment:
        """
        フェードイン・フェードアウトを適用する
        
        Args:
            audio: 音声データ
            fade_in_ms: フェードイン（ミリ秒）
            fade_out_ms: フェードアウト（ミリ秒）
        
        Returns:
            フェード適用された音声データ
        """
        if fade_in_ms > 0:
            audio = audio.fade_in(fade_in_ms)
        if fade_out_ms > 0:
            audio = audio.fade_out(fade_out_ms)
        return audio

    def split_on_silence(
        self,
        audio: AudioSegment,
        min_silence_len: int = 500,
        silence_thresh: int = -40,
        keep_silence: int = 100,
    ) -> List[AudioSegment]:
        """
        無音部分で音声を分割する
        
        Args:
            audio: 音声データ
            min_silence_len: 無音と判定する最小長さ（ミリ秒）
            silence_thresh: 無音と判定する閾値（dBFS）
            keep_silence: 各チャンクの前後に残す無音（ミリ秒）
        
        Returns:
            分割された音声データのリスト
        """
        from pydub.silence import split_on_silence as pydub_split
        
        return pydub_split(
            audio,
            min_silence_len=min_silence_len,
            silence_thresh=silence_thresh,
            keep_silence=keep_silence,
        )

    def wav_bytes_to_audio(self, wav_bytes: bytes) -> AudioSegment:
        """WAVバイトデータをAudioSegmentに変換"""
        return AudioSegment.from_wav(io.BytesIO(wav_bytes))
