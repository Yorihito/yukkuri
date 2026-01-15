"""
VOICEVOX クライアントモジュール

VOICEVOX Engine APIと連携して音声合成を行う
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from ..utils.config import Config
from ..utils.logger import get_logger


class VoicevoxClient:
    """VOICEVOX Engine APIクライアント"""

    def __init__(self, base_url: Optional[str] = None):
        """
        Args:
            base_url: VOICEVOX Engine URL (デフォルト: http://localhost:50021)
        """
        config = Config.get()
        self.base_url = base_url or config.voicevox.url
        self.logger = get_logger()
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "VoicevoxClient":
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")
        return self._client

    async def is_available(self) -> bool:
        """VOICEVOX Engineが利用可能か確認"""
        try:
            response = await self.client.get("/version")
            return response.status_code == 200
        except Exception:
            return False

    async def get_speakers(self) -> List[Dict[str, Any]]:
        """利用可能なスピーカー一覧を取得"""
        response = await self.client.get("/speakers")
        response.raise_for_status()
        return response.json()

    async def get_speaker_info(self, speaker_id: int) -> Dict[str, Any]:
        """スピーカー情報を取得"""
        response = await self.client.get(f"/speaker_info", params={"speaker": speaker_id})
        response.raise_for_status()
        return response.json()

    async def create_audio_query(
        self,
        text: str,
        speaker: int,
        speed_scale: float = 1.0,
        pitch_scale: float = 0.0,
        intonation_scale: float = 1.0,
        volume_scale: float = 1.0,
    ) -> Dict[str, Any]:
        """
        音声合成用のクエリを作成
        
        Args:
            text: 読み上げテキスト
            speaker: スピーカーID
            speed_scale: 話速（1.0が標準）
            pitch_scale: 音高（0.0が標準）
            intonation_scale: 抑揚（1.0が標準）
            volume_scale: 音量（1.0が標準）
        
        Returns:
            AudioQuery オブジェクト
        """
        response = await self.client.post(
            "/audio_query",
            params={"text": text, "speaker": speaker},
        )
        response.raise_for_status()
        
        query = response.json()
        
        # パラメータ調整
        query["speedScale"] = speed_scale
        query["pitchScale"] = pitch_scale
        query["intonationScale"] = intonation_scale
        query["volumeScale"] = volume_scale
        
        return query

    async def synthesize(
        self,
        audio_query: Dict[str, Any],
        speaker: int,
    ) -> bytes:
        """
        音声を合成
        
        Args:
            audio_query: AudioQuery オブジェクト
            speaker: スピーカーID
        
        Returns:
            WAV音声データ
        """
        response = await self.client.post(
            "/synthesis",
            params={"speaker": speaker},
            json=audio_query,
        )
        response.raise_for_status()
        return response.content

    async def text_to_speech(
        self,
        text: str,
        speaker: int,
        output_path: Optional[Path] = None,
        speed_scale: float = 1.0,
        pitch_scale: float = 0.0,
        intonation_scale: float = 1.0,
        volume_scale: float = 1.0,
    ) -> bytes:
        """
        テキストから音声を生成
        
        Args:
            text: 読み上げテキスト
            speaker: スピーカーID
            output_path: 出力ファイルパス（指定時はファイル保存）
            speed_scale: 話速
            pitch_scale: 音高
            intonation_scale: 抑揚
            volume_scale: 音量
        
        Returns:
            WAV音声データ
        """
        self.logger.info(f"音声生成: '{text[:20]}...' (speaker={speaker})")
        
        # AudioQuery作成
        query = await self.create_audio_query(
            text=text,
            speaker=speaker,
            speed_scale=speed_scale,
            pitch_scale=pitch_scale,
            intonation_scale=intonation_scale,
            volume_scale=volume_scale,
        )
        
        # 音声合成
        audio_data = await self.synthesize(query, speaker)
        
        # ファイル保存
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(audio_data)
            self.logger.info(f"音声保存: {output_path}")
        
        return audio_data

    async def get_audio_duration(self, audio_query: Dict[str, Any]) -> float:
        """
        AudioQueryから音声の長さを計算
        
        Args:
            audio_query: AudioQuery オブジェクト
        
        Returns:
            音声の長さ（秒）
        """
        duration = 0.0
        for accent_phrase in audio_query.get("accent_phrases", []):
            for mora in accent_phrase.get("moras", []):
                if mora.get("consonant_length"):
                    duration += mora["consonant_length"]
                if mora.get("vowel_length"):
                    duration += mora["vowel_length"]
            # ポーズ
            if accent_phrase.get("pause_mora"):
                pause = accent_phrase["pause_mora"]
                if pause.get("vowel_length"):
                    duration += pause["vowel_length"]
        
        # speedScaleで調整
        speed_scale = audio_query.get("speedScale", 1.0)
        if speed_scale > 0:
            duration /= speed_scale
        
        return duration


# 同期版ラッパー
class VoicevoxClientSync:
    """VOICEVOX クライアント（同期版）"""

    def __init__(self, base_url: Optional[str] = None):
        config = Config.get()
        self.base_url = base_url or config.voicevox.url
        self.logger = get_logger()

    def _run(self, coro):
        """コルーチンを実行"""
        return asyncio.get_event_loop().run_until_complete(coro)

    def is_available(self) -> bool:
        """VOICEVOX Engineが利用可能か確認"""
        try:
            with httpx.Client(base_url=self.base_url, timeout=5.0) as client:
                response = client.get("/version")
                return response.status_code == 200
        except Exception:
            return False

    def get_speakers(self) -> List[Dict[str, Any]]:
        """利用可能なスピーカー一覧を取得"""
        with httpx.Client(base_url=self.base_url, timeout=30.0) as client:
            response = client.get("/speakers")
            response.raise_for_status()
            return response.json()

    def text_to_speech(
        self,
        text: str,
        speaker: int,
        output_path: Optional[Path] = None,
        speed_scale: float = 1.0,
        pitch_scale: float = 0.0,
        intonation_scale: float = 1.0,
        volume_scale: float = 1.0,
    ) -> bytes:
        """テキストから音声を生成（同期版）"""
        self.logger.info(f"音声生成: '{text[:20]}...' (speaker={speaker})")
        
        with httpx.Client(base_url=self.base_url, timeout=60.0) as client:
            # AudioQuery作成
            response = client.post(
                "/audio_query",
                params={"text": text, "speaker": speaker},
            )
            response.raise_for_status()
            query = response.json()
            
            # パラメータ調整
            query["speedScale"] = speed_scale
            query["pitchScale"] = pitch_scale
            query["intonationScale"] = intonation_scale
            query["volumeScale"] = volume_scale
            
            # 音声合成
            response = client.post(
                "/synthesis",
                params={"speaker": speaker},
                json=query,
            )
            response.raise_for_status()
            audio_data = response.content
        
        # ファイル保存
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(audio_data)
            self.logger.info(f"音声保存: {output_path}")
        
        return audio_data

    def get_audio_duration_from_text(self, text: str, speaker: int) -> float:
        """テキストから音声長を取得"""
        with httpx.Client(base_url=self.base_url, timeout=30.0) as client:
            response = client.post(
                "/audio_query",
                params={"text": text, "speaker": speaker},
            )
            response.raise_for_status()
            query = response.json()
            
            duration = 0.0
            for accent_phrase in query.get("accent_phrases", []):
                for mora in accent_phrase.get("moras", []):
                    if mora.get("consonant_length"):
                        duration += mora["consonant_length"]
                    if mora.get("vowel_length"):
                        duration += mora["vowel_length"]
                if accent_phrase.get("pause_mora"):
                    pause = accent_phrase["pause_mora"]
                    if pause.get("vowel_length"):
                        duration += pause["vowel_length"]
            
            return duration
