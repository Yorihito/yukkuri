#!/usr/bin/env python3
"""背景画像生成スクリプト - 台本テキストを暗めに表示"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# 台本テキスト（最初に渡された内容を適度に抜粋）
script_text = """皆様、お久しぶりです。
前回ChatGPTについて解説してから、およそ3年が経ちました。
あれからAIの話、やたら聞くようになったよな。
で、ChatGPTの中身って、実際どう進化したんだ？
今回は、そこを重点的に解説していきますね。
まず前提として、ChatGPTは「大規模言語モデル」と呼ばれるAIです。
前も聞いたけど、結局それって何なんだ？
簡単に言うと、大量の文章を学習して、
「次に来そうな言葉」を予測する仕組みです。
予測だけで、あんな会話ができるのか？
実は、それがこの技術の面白いところなんです。
文脈全体を数値として扱い、確率的に最適な文章を生成しています。
なるほどな。じゃあ、この3年で何が一番変わったんだ？
大きく分けて三つあります。
モデルの規模、理解の深さ、そして扱える情報の種類です。
おお、いきなり本格的だな。
まずモデルの規模ですが、
学習に使われるパラメータ数が増え、
より複雑な関係を表現できるようになりました。
パラメータって、脳みその細かさみたいなもんか？
とても良い例えですね。
それが増えたことで、文脈の保持力が大きく向上しました。
だから長い会話でも話を忘れにくくなったんだな。
その通りです。
次に、理解の深さについてです。
単語単位ではなく、文章全体の意味構造を捉えやすくなりました。
つまり、行間を読む力が上がったってことか？
はい。あいまいな指示や、省略された表現にも強くなっています。
そして三つ目が、マルチモーダル化です。
文章だけでなく、画像や音声も一緒に扱えるようになりました。"""

def create_text_background():
    # 1920x1080の暗い背景
    width, height = 1920, 1080
    bg_color = (25, 25, 35)  # 暗い青紫
    text_color = (60, 60, 75)  # さらに暗めのテキスト
    
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # フォント設定
    try:
        font = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", 28)
    except:
        font = ImageFont.load_default()
    
    # テキストエリア（横80%）
    margin_x = int(width * 0.1)  # 左右10%ずつマージン
    text_width = int(width * 0.8)
    
    # テキストを描画
    y = 50
    line_height = 38
    
    for line in script_text.strip().split("\n"):
        if y > height - 50:
            break
        draw.text((margin_x, y), line, font=font, fill=text_color)
        y += line_height
    
    # 保存
    output_path = Path("assets/backgrounds/script_text_bg.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    print(f"背景画像を保存しました: {output_path}")
    
    return output_path

if __name__ == "__main__":
    create_text_background()
