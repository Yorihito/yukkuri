#!/usr/bin/env python3
"""
ゆっくり解説動画自動生成システム

メインエントリーポイント
"""

from pathlib import Path
from typing import Optional
import sys

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.utils.config import Config
from src.utils.logger import setup_logger, get_logger
from src.voice.voicevox_client import VoicevoxClientSync
from src.voice.audio_processor import AudioProcessor
from src.video.timeline import Timeline, ItemType
from src.video.renderer import VideoRenderer
from src.script.parser import ScriptParser
from src.script.generator import create_sample_script
from src.assets.manager import AssetManager
from src.assets.character import CharacterManager
from src.assets.downloader import AssetDownloader, FreeSiteDownloader


app = typer.Typer(
    name="yukkuri",
    help="ゆっくり解説動画自動生成システム",
    add_completion=False,
)
console = Console()


def init_app() -> Config:
    """アプリケーション初期化"""
    setup_logger()
    config = Config.load(Path("config.yaml"))
    config.ensure_directories()
    return config


@app.command()
def list_speakers():
    """VOICEVOXのスピーカー一覧を表示"""
    init_app()
    logger = get_logger()
    
    client = VoicevoxClientSync()
    
    if not client.is_available():
        console.print("[red]エラー: VOICEVOXが起動していません[/red]")
        console.print("VOICEVOXを起動してから再実行してください。")
        console.print("ダウンロード: https://voicevox.hiroshiba.jp/")
        raise typer.Exit(1)
    
    speakers = client.get_speakers()
    
    table = Table(title="VOICEVOXスピーカー一覧")
    table.add_column("ID", style="cyan")
    table.add_column("名前", style="green")
    table.add_column("スタイル", style="yellow")
    
    for speaker in speakers:
        name = speaker.get("name", "Unknown")
        for style in speaker.get("styles", []):
            style_id = style.get("id", "?")
            style_name = style.get("name", "default")
            table.add_row(str(style_id), name, style_name)
    
    console.print(table)


@app.command()
def generate_voice(
    text: str = typer.Option(..., "--text", "-t", help="読み上げテキスト"),
    speaker: int = typer.Option(0, "--speaker", "-s", help="スピーカーID"),
    output: Path = typer.Option(Path("output/audio/test.wav"), "--output", "-o", help="出力ファイル"),
    speed: float = typer.Option(1.0, "--speed", help="話速"),
    pitch: float = typer.Option(0.0, "--pitch", help="音高"),
):
    """テキストから音声を生成"""
    init_app()
    
    client = VoicevoxClientSync()
    
    if not client.is_available():
        console.print("[red]エラー: VOICEVOXが起動していません[/red]")
        raise typer.Exit(1)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
    ) as progress:
        progress.add_task("音声生成中...", total=None)
        
        client.text_to_speech(
            text=text,
            speaker=speaker,
            output_path=output,
            speed_scale=speed,
            pitch_scale=pitch,
        )
    
    console.print(f"[green]音声生成完了: {output}[/green]")


@app.command()
def generate(
    script: Path = typer.Option(..., "--script", "-s", help="台本ファイル (YAML)"),
    output: Path = typer.Option(Path("output/video/output.mp4"), "--output", "-o", help="出力動画ファイル"),
    preview_only: bool = typer.Option(False, "--preview", help="プレビュー画像のみ生成"),
):
    """台本から動画を生成"""
    config = init_app()
    logger = get_logger()
    
    # 台本読み込み
    if not script.exists():
        console.print(f"[red]エラー: 台本ファイルが見つかりません: {script}[/red]")
        raise typer.Exit(1)
    
    parser = ScriptParser()
    script_data = parser.parse_file(script)
    
    console.print(f"[cyan]台本: {script_data.title}[/cyan]")
    console.print(f"シーン数: {len(script_data.scenes)}, セリフ数: {script_data.get_total_lines()}")
    
    # VOICEVOX確認
    voicevox = VoicevoxClientSync()
    if not voicevox.is_available():
        console.print("[red]エラー: VOICEVOXが起動していません[/red]")
        raise typer.Exit(1)
    
    # キャラクターマネージャー
    char_manager = CharacterManager()
    
    # タイムライン作成
    timeline = Timeline()
    current_time = 0.0
    
    audio_dir = Path(config.paths.output_audio)
    audio_files = []
    
    # スクロール用の台本テキスト収集
    script_lines_for_scroll = []
    
    # まず全体の時間を計算するために音声を生成
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
    ) as progress:
        # 音声生成
        task = progress.add_task("音声生成中...", total=script_data.get_total_lines())
        
        line_index = 0
        for scene in script_data.scenes:
            for line in scene.lines:
                # スクロール用テキスト収集
                display_name = config.get_character_config(line.character)
                name = display_name.name if display_name else line.character
                script_lines_for_scroll.append(f"{name}: {line.text}")
                
                # 音声生成
                speaker_id = config.get_speaker_id(line.character)
                audio_path = audio_dir / f"line_{line_index:04d}.wav"
                
                voicevox.text_to_speech(
                    text=line.text,
                    speaker=speaker_id,
                    output_path=audio_path,
                    speed_scale=line.speed,
                    pitch_scale=line.pitch,
                )
                audio_files.append(audio_path)
                
                # 音声長取得
                audio_processor = AudioProcessor()
                duration = audio_processor.get_duration_from_file(audio_path)
                
                # 両キャラクターを常時表示（話している方を強調）
                speaking_char = line.character.lower()
                
                # 霊夢の立ち絵（左側、右向き）
                reimu_config = config.get_character_config("reimu")
                reimu_image = char_manager.get_expression_path(
                    "reimu", 
                    line.expression if speaking_char == "reimu" else "normal"
                )
                if reimu_image and reimu_image.exists():
                    reimu_pos = reimu_config.position if reimu_config else (350, 650)
                    # 話している時は大きく、聞いている時は小さく
                    reimu_scale = 0.9 if speaking_char == "reimu" else 0.75
                    timeline.add_character(
                        character="reimu",
                        expression=line.expression if speaking_char == "reimu" else "normal",
                        start_time=current_time,
                        duration=duration,
                        image_path=reimu_image,
                        position=reimu_pos,
                        scale=reimu_scale,
                        flip_horizontal=True,  # 右向き
                    )
                
                # 魔理沙の立ち絵（右側、左向き）
                marisa_config = config.get_character_config("marisa")
                marisa_image = char_manager.get_expression_path(
                    "marisa",
                    line.expression if speaking_char == "marisa" else "normal"
                )
                if marisa_image and marisa_image.exists():
                    marisa_pos = marisa_config.position if marisa_config else (1570, 650)
                    # 話している時は大きく、聞いている時は小さく
                    marisa_scale = 0.9 if speaking_char == "marisa" else 0.75
                    timeline.add_character(
                        character="marisa",
                        expression=line.expression if speaking_char == "marisa" else "normal",
                        start_time=current_time,
                        duration=duration,
                        image_path=marisa_image,
                        position=marisa_pos,
                        scale=marisa_scale,
                        flip_horizontal=False,  # 左向き（元のまま）
                    )
                
                # セリフをタイムラインに追加（話者名付き）
                subtitle_text = f"【{name}】{line.text}"
                timeline.add_dialogue(
                    text=subtitle_text,
                    character=line.character,
                    start_time=current_time,
                    duration=duration,
                    audio_path=audio_path,
                    expression=line.expression,
                )
                
                current_time += duration + line.pause_after
                line_index += 1
                progress.update(task, advance=1)
    
    # BGMを追加
    asset_manager = AssetManager()
    bgm_files = list(Path(config.paths.bgm).glob("*.mp3")) + list(Path(config.paths.bgm).glob("*.wav"))
    if bgm_files:
        bgm_path = bgm_files[0]
        timeline.add_bgm(bgm_path, 0.0, current_time, fade_in=2.0, fade_out=3.0)
        console.print(f"[green]BGM追加: {bgm_path.name}[/green]")
    
    console.print(f"[green]音声生成完了: {len(audio_files)}ファイル[/green]")
    console.print(f"総時間: {current_time:.2f}秒")
    
    if preview_only:
        # プレビュー画像生成
        renderer = VideoRenderer()
        preview_path = output.with_suffix(".png")
        renderer.render_preview(timeline, 1.0, preview_path)
        console.print(f"[green]プレビュー生成完了: {preview_path}[/green]")
    else:
        # 動画生成
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
        ) as progress:
            progress.add_task("動画レンダリング中...", total=None)
            
            renderer = VideoRenderer()
            
            # スクロールテキスト背景を直接render_from_timelineに渡す
            scroll_text = "\n".join(script_lines_for_scroll)
            renderer.render_from_timeline(
                timeline, 
                output,
                scrolling_text=scroll_text,
            )
        
        console.print(f"[green]動画生成完了: {output}[/green]")


@app.command()
def generate_sample():
    """サンプル台本を生成"""
    init_app()
    
    sample = create_sample_script()
    
    output_path = Path("scripts/sample_script.yaml")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    import yaml
    
    # Scriptオブジェクトを辞書に変換
    data = {
        "title": sample.title,
        "settings": {
            "resolution": list(sample.settings.resolution),
            "fps": sample.settings.fps,
        },
        "scenes": [
            {
                "id": scene.id,
                "lines": [
                    {
                        "character": line.character,
                        "text": line.text,
                        "expression": line.expression,
                    }
                    for line in scene.lines
                ],
            }
            for scene in sample.scenes
        ],
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    console.print(f"[green]サンプル台本生成完了: {output_path}[/green]")
    console.print("\n台本内容:")
    console.print(f"タイトル: {sample.title}")
    console.print(f"シーン数: {len(sample.scenes)}")
    console.print(f"セリフ数: {sample.get_total_lines()}")


@app.command()
def download_assets(
    list_file: Path = typer.Option(..., "--list", "-l", help="素材リストファイル"),
    output_dir: Path = typer.Option(Path("assets"), "--output", "-o", help="出力ディレクトリ"),
):
    """素材をダウンロード"""
    init_app()
    
    if not list_file.exists():
        console.print(f"[red]エラー: リストファイルが見つかりません: {list_file}[/red]")
        raise typer.Exit(1)
    
    downloader = AssetDownloader()
    results = downloader.download_from_list(list_file, output_dir)
    
    console.print("[green]ダウンロード完了[/green]")
    for asset_type, files in results.items():
        if files:
            console.print(f"  {asset_type}: {len(files)}ファイル")


@app.command()
def list_assets():
    """素材一覧を表示"""
    init_app()
    
    manager = AssetManager()
    stats = manager.get_asset_stats()
    
    table = Table(title="素材一覧")
    table.add_column("種類", style="cyan")
    table.add_column("ファイル数", style="green")
    table.add_column("合計サイズ", style="yellow")
    
    for asset_type, info in stats.items():
        size_mb = info["total_size"] / (1024 * 1024)
        table.add_row(
            asset_type,
            str(info["count"]),
            f"{size_mb:.2f} MB",
        )
    
    console.print(table)


@app.command()
def list_characters():
    """キャラクター一覧を表示"""
    init_app()
    
    manager = CharacterManager()
    characters = manager.list_characters()
    
    if not characters:
        console.print("[yellow]キャラクターが見つかりません[/yellow]")
        console.print("assets/characters/ にキャラクター素材を配置してください。")
        return
    
    table = Table(title="キャラクター一覧")
    table.add_column("名前", style="cyan")
    table.add_column("表示名", style="green")
    table.add_column("表情数", style="yellow")
    table.add_column("利用可能な表情", style="white")
    
    for char_name in characters:
        char = manager.get_character(char_name)
        if char:
            expressions = ", ".join(char.list_expressions()[:5])
            if len(char.list_expressions()) > 5:
                expressions += f", ... (+{len(char.list_expressions()) - 5})"
            
            table.add_row(
                char.name,
                char.display_name,
                str(len(char.expressions)),
                expressions,
            )
    
    console.print(table)


@app.command()
def show_free_sites():
    """無料素材サイト一覧を表示"""
    downloader = FreeSiteDownloader()
    sites = downloader.get_recommended_free_sites()
    
    for category, site_list in sites.items():
        console.print(f"\n[bold cyan]{category}[/bold cyan]")
        for name, url in site_list.items():
            console.print(f"  • {name}: {url}")


@app.command()
def init():
    """プロジェクトを初期化（ディレクトリ作成）"""
    config = init_app()
    
    console.print("[green]ディレクトリを作成しました:[/green]")
    
    dirs = [
        "assets/characters/reimu",
        "assets/characters/marisa",
        "assets/backgrounds",
        "assets/bgm",
        "assets/sfx",
        "assets/fonts",
        "scripts",
        "output/audio",
        "output/video",
    ]
    
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        console.print(f"  • {d}")
    
    console.print("\n[yellow]次のステップ:[/yellow]")
    console.print("1. VOICEVOXをインストール・起動")
    console.print("2. assets/characters/ にキャラクター立ち絵を配置")
    console.print("3. python main.py generate-sample で台本サンプル生成")
    console.print("4. python main.py generate -s scripts/sample_script.yaml で動画生成")


@app.command()
def version():
    """バージョン情報を表示"""
    from src import __version__
    console.print(f"ゆっくり解説動画自動生成システム v{__version__}")


if __name__ == "__main__":
    app()
