"""
Cortex Utilities

共用工具函數，包含跨平台相容性處理。
"""

import sys
import os


def setup_console_encoding():
    """
    設定 Windows console 編碼為 UTF-8

    在腳本開頭呼叫此函數以避免 emoji 和中文輸出錯誤。
    """
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def read_text_file(file_path: str, encodings: list = None) -> str:
    """
    讀取文字檔案，自動處理編碼問題

    Args:
        file_path: 檔案路徑
        encodings: 嘗試的編碼列表，預設 ['utf-8', 'utf-8-sig', 'latin-1']

    Returns:
        檔案內容字串

    Raises:
        FileNotFoundError: 檔案不存在
        UnicodeDecodeError: 所有編碼都失敗
    """
    if encodings is None:
        encodings = ['utf-8', 'utf-8-sig', 'latin-1']

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    last_error = None
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError as e:
            last_error = e
            continue

    raise UnicodeDecodeError(
        'multiple',
        b'',
        0, 0,
        f"Failed to decode {file_path} with encodings: {encodings}"
    )


def write_text_file(file_path: str, content: str, encoding: str = 'utf-8'):
    """
    寫入文字檔案，預設 UTF-8 編碼

    Args:
        file_path: 檔案路徑
        content: 要寫入的內容
        encoding: 編碼，預設 'utf-8'
    """
    # 確保目錄存在
    dir_path = os.path.dirname(file_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    with open(file_path, 'w', encoding=encoding) as f:
        f.write(content)


def get_base_dir() -> str:
    """
    取得 cortex-agents 安裝目錄

    Returns:
        cortex-agents 根目錄的絕對路徑
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_db_path() -> str:
    """
    取得資料庫路徑

    Returns:
        brain.db 的絕對路徑
    """
    return os.path.join(get_base_dir(), 'brain', 'brain.db')
