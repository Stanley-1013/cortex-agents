"""
Code Graph Extractor

使用 Tree-sitter 進行多語言 AST 解析，提取程式碼結構圖。
不依賴 LLM，產出確定性結果。

支援語言：
- TypeScript/JavaScript
- Python
- Go (可擴展)

使用方式：
    from tools.code_graph_extractor import extract_from_file, extract_from_directory

    # 單一檔案
    nodes, edges = extract_from_file('src/api/auth.ts')

    # 整個目錄（增量）
    result = extract_from_directory('src/', incremental=True)
"""

from .extractor import (
    extract_from_file,
    extract_from_directory,
    get_supported_languages,
    SUPPORTED_EXTENSIONS,
)

__all__ = [
    'extract_from_file',
    'extract_from_directory',
    'get_supported_languages',
    'SUPPORTED_EXTENSIONS',
]
