"""
台本生成モジュール

OpenAI/Gemini APIを使用して台本を自動生成（オプション）
"""

import os
from typing import Any, Dict, Optional

from ..utils.config import Config
from ..utils.logger import get_logger
from .parser import Script, SceneData, LineData, ScriptSettings


class ScriptGenerator:
    """AI台本生成クラス"""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Args:
            provider: プロバイダー ("openai" or "gemini")
            api_key: API キー
            model: モデル名
        """
        self.logger = get_logger()
        config = Config.get()
        
        self.provider = provider or config.ai.provider
        self.api_key = api_key or config.ai.api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or config.ai.model
        
        self._client = None

    def is_available(self) -> bool:
        """AI機能が利用可能か"""
        config = Config.get()
        return config.ai.enabled and bool(self.api_key)

    def _get_system_prompt(self) -> str:
        """システムプロンプトを取得"""
        return """あなたは「ゆっくり解説動画」の台本作成者です。
霊夢と魔理沙の掛け合いで視聴者にわかりやすく解説する台本を作成してください。

台本のルール:
1. 霊夢（れいむ）: ボケ役・質問役。視聴者目線で疑問を投げかける
2. 魔理沙（まりさ）: ツッコミ役・解説役。詳しく説明する
3. テンポよく、短いセリフで掛け合いを進める
4. 専門用語は魔理沙が解説し、霊夢が「なるほど！」と納得する流れ
5. 時々ユーモアを交える

出力形式（YAML）:
```yaml
title: "タイトル"
scenes:
  - id: intro
    lines:
      - character: reimu
        text: "ゆっくりしていってね！"
        expression: smile
      - character: marisa
        text: "今日は○○について解説するぜ！"
        expression: normal
```

利用可能な表情: normal, smile, sad, angry, surprised, smug, wink, excited, thinking
"""

    def generate(
        self,
        topic: str,
        style: str = "解説",
        length: str = "medium",
        additional_instructions: str = "",
    ) -> Script:
        """
        台本を生成
        
        Args:
            topic: トピック/テーマ
            style: スタイル（解説、雑学、ニュース等）
            length: 長さ（short, medium, long）
            additional_instructions: 追加指示
        
        Returns:
            生成された台本
        """
        if not self.is_available():
            raise RuntimeError("AI機能が有効ではありません。config.yamlのai.enabledをtrueにし、API キーを設定してください。")
        
        length_guide = {
            "short": "5〜10セリフ程度",
            "medium": "15〜25セリフ程度",
            "long": "30〜50セリフ程度",
        }.get(length, "15〜25セリフ程度")
        
        user_prompt = f"""以下のテーマで「ゆっくり解説動画」の台本を作成してください。

テーマ: {topic}
スタイル: {style}
長さ: {length_guide}

{additional_instructions}

台本をYAML形式で出力してください。
"""
        
        if self.provider == "openai":
            return self._generate_with_openai(user_prompt)
        elif self.provider == "gemini":
            return self._generate_with_gemini(user_prompt)
        else:
            raise ValueError(f"未対応のプロバイダー: {self.provider}")

    def _generate_with_openai(self, prompt: str) -> Script:
        """OpenAI APIで生成"""
        try:
            import openai
        except ImportError:
            raise ImportError("openaiパッケージをインストールしてください: pip install openai")
        
        client = openai.OpenAI(api_key=self.api_key)
        
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
        )
        
        content = response.choices[0].message.content
        
        # YAMLを抽出
        yaml_content = self._extract_yaml(content)
        
        from .parser import ScriptParser
        parser = ScriptParser()
        return parser.parse_text(yaml_content)

    def _generate_with_gemini(self, prompt: str) -> Script:
        """Gemini APIで生成"""
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("google-generativeaiパッケージをインストールしてください: pip install google-generativeai")
        
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model or "gemini-pro")
        
        full_prompt = f"{self._get_system_prompt()}\n\n{prompt}"
        response = model.generate_content(full_prompt)
        
        content = response.text
        
        # YAMLを抽出
        yaml_content = self._extract_yaml(content)
        
        from .parser import ScriptParser
        parser = ScriptParser()
        return parser.parse_text(yaml_content)

    def _extract_yaml(self, text: str) -> str:
        """テキストからYAMLを抽出"""
        import re
        
        # コードブロック内のYAMLを抽出
        match = re.search(r"```(?:yaml)?\n(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1)
        
        # コードブロックがない場合はそのまま返す
        return text

    def generate_from_outline(
        self,
        outline: str,
        characters: list[str] = ["reimu", "marisa"],
    ) -> Script:
        """
        アウトラインから台本を生成
        
        Args:
            outline: アウトライン/箇条書き
            characters: 使用キャラクター
        
        Returns:
            生成された台本
        """
        char_names = "、".join(characters)
        prompt = f"""以下のアウトラインを元に、{char_names}の掛け合いで台本を作成してください。

アウトライン:
{outline}

各ポイントを詳しく解説し、視聴者がわかりやすいように台本にしてください。
YAML形式で出力してください。
"""
        
        if self.provider == "openai":
            return self._generate_with_openai(prompt)
        elif self.provider == "gemini":
            return self._generate_with_gemini(prompt)
        else:
            raise ValueError(f"未対応のプロバイダー: {self.provider}")


def create_sample_script() -> Script:
    """サンプル台本を作成（ChatGPT/AI言及バージョン）"""
    return Script(
        title="ChatGPTでゆっくり動画を作る方法",
        settings=ScriptSettings(
            resolution=(1920, 1080),
            fps=30,
        ),
        scenes=[
            SceneData(
                id="intro",
                lines=[
                    LineData(character="reimu", text="ゆっくりしていってね！", expression="smile"),
                    LineData(character="marisa", text="今日はちょっと特別な話をするぜ！", expression="excited"),
                    LineData(character="reimu", text="特別？何かあるの？", expression="normal"),
                ],
            ),
            SceneData(
                id="reveal",
                lines=[
                    LineData(character="marisa", text="実はこの動画、ほとんどAIが作ってるんだぜ！", expression="smug"),
                    LineData(character="reimu", text="え！？AIって、ChatGPTとか？", expression="surprised"),
                    LineData(character="marisa", text="そう！台本から音声、動画編集まで自動化できるんだ", expression="normal"),
                    LineData(character="reimu", text="すごい時代になったわね…", expression="thinking"),
                ],
            ),
            SceneData(
                id="explanation",
                lines=[
                    LineData(character="marisa", text="VOICEVOXで音声を生成して、MoviePyで動画を合成する", expression="normal"),
                    LineData(character="reimu", text="私たちの声もAIなの？", expression="normal"),
                    LineData(character="marisa", text="VOICEVOXっていう無料の音声合成ソフトを使ってるぜ", expression="normal"),
                    LineData(character="reimu", text="無料なの！？太っ腹ね！", expression="smile"),
                ],
            ),
            SceneData(
                id="meta",
                lines=[
                    LineData(character="marisa", text="この台本自体もChatGPTに書いてもらったんだぜ", expression="wink"),
                    LineData(character="reimu", text="メタいわね…私たちの存在意義は…", expression="sad"),
                    LineData(character="marisa", text="まあまあ、人間とAIの協力ってことで！", expression="smile"),
                    LineData(character="reimu", text="そ、そうね！これからもよろしくね！", expression="smile"),
                ],
            ),
            SceneData(
                id="ending",
                lines=[
                    LineData(character="reimu", text="チャンネル登録と高評価よろしくね！", expression="smile"),
                    LineData(character="marisa", text="次の動画もAIと一緒に作るぜ！またな！", expression="wink"),
                ],
            ),
        ],
    )
