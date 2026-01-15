"""
ロギングモジュール

統一されたログ出力を提供する
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


_logger: Optional[logging.Logger] = None
console = Console()


def setup_logger(
    name: str = "yukkuri",
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
) -> logging.Logger:
    """ロガーをセットアップする"""
    global _logger
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 既存のハンドラをクリア
    logger.handlers.clear()
    
    # Rich ハンドラ（コンソール出力）
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
    )
    rich_handler.setLevel(level)
    logger.addHandler(rich_handler)
    
    # ファイルハンドラ（オプション）
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(file_handler)
    
    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """ロガーを取得する"""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger
