# ゆっくり解説動画自動生成システム

Apple Silicon対応のフル機能「ゆっくり」解説動画自動生成ツールです。

## 🚀 特徴

- **VOICEVOX音声合成** - ゆっくりボイス（霊夢・魔理沙等）
- **自動動画生成** - MoviePy/FFmpegによる高品質レンダリング
- **キャラクター立ち絵** - 表情変化・口パクアニメーション
- **字幕自動生成** - 美しいテロップ
- **素材ダウンローダー** - BGM・SE・背景の自動取得
- **AI台本生成** - OpenAI/Gemini連携（オプション）

## 📋 必要条件

- Python 3.10+
- Apple Silicon Mac (M1/M2/M3)
- [VOICEVOX](https://voicevox.hiroshiba.jp/) (音声合成エンジン)
- FFmpeg

## 🛠️ セットアップ

```bash
# 1. リポジトリ移動
cd /path/to/yukkuri

# 2. 仮想環境作成
python3 -m venv venv
source venv/bin/activate

# 3. 依存関係インストール
pip install -r requirements.txt

# 4. VOICEVOX起動
open /Applications/VOICEVOX.app
```

## 📖 使い方

### スピーカー一覧表示

```bash
python main.py list-speakers
```

### 音声生成

```bash
python main.py generate-voice --text "ゆっくりしていってね！" --speaker 0 --output output/test.wav
```

### 動画生成

```bash
python main.py generate --script scripts/sample_script.yaml
```

### 素材ダウンロード

```bash
python main.py download-assets --list assets_list.txt
```

## 📝 台本フォーマット

`scripts/sample_script.yaml` を参照してください。

```yaml
title: "動画タイトル"
settings:
  resolution: [1920, 1080]
  fps: 30
  background: "default_room.png"
  bgm: "calm_bgm.mp3"

scenes:
  - id: intro
    lines:
      - character: reimu
        text: "ゆっくりしていってね！"
        expression: smile
```

## 📁 素材配置

```
assets/
├── characters/
│   ├── reimu/         # 霊夢立ち絵
│   │   ├── normal.png
│   │   ├── smile.png
│   │   └── ...
│   └── marisa/        # 魔理沙立ち絵
├── backgrounds/       # 背景画像
├── bgm/               # BGMファイル
├── sfx/               # 効果音
└── fonts/             # フォント
```

## 🎨 素材入手先

### キャラクター立ち絵
- きつねゆっくり（ニコニコ）
- ゆっくり素材配布所

### 背景・画像
- [いらすとや](https://www.irasutoya.com/)
- [ぱくたそ](https://www.pakutaso.com/)
- [Pixabay](https://pixabay.com/)

### BGM
- [DOVA-SYNDROME](https://dova-s.jp/)
- [甘茶の音楽工房](https://amachamusic.chagasi.com/)
- [魔王魂](https://maou.audio/)

### 効果音
- [効果音ラボ](https://soundeffect-lab.info/)
- [OtoLogic](https://otologic.jp/)

## 📜 ライセンス

MIT License
