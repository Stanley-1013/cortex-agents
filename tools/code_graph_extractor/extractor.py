"""
Code Graph Extractor - 核心提取邏輯

使用 Tree-sitter 解析 AST，提取：
- Node: file, class, function, interface, type, constant, variable
- Edge: imports, calls, extends, implements, defines, contains

設計原則：
1. 不依賴 LLM，結果確定性
2. 增量更新，只處理變更檔案
3. 多語言支援（可擴展）
"""

import os
import hashlib
import re
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path

# =============================================================================
# Data Models
# =============================================================================

@dataclass
class CodeNode:
    """程式碼節點"""
    id: str                          # e.g. 'func.src/api/auth.ts:validateToken'
    kind: str                        # e.g. 'function', 'class', 'file'
    name: str                        # e.g. 'validateToken'
    file_path: str                   # e.g. 'src/api/auth.ts'
    line_start: int = 0
    line_end: int = 0
    signature: Optional[str] = None  # 函式簽名或類別定義
    language: Optional[str] = None   # 'typescript', 'python'
    visibility: Optional[str] = None # 'public', 'private', 'protected'
    hash: Optional[str] = None       # 內容 hash

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'kind': self.kind,
            'name': self.name,
            'file_path': self.file_path,
            'line_start': self.line_start,
            'line_end': self.line_end,
            'signature': self.signature,
            'language': self.language,
            'visibility': self.visibility,
            'hash': self.hash,
        }


@dataclass
class CodeEdge:
    """程式碼邊（關係）"""
    from_id: str                     # 來源 node id
    to_id: str                       # 目標 node id
    kind: str                        # 'imports', 'calls', 'extends', etc.
    line_number: Optional[int] = None
    confidence: float = 1.0          # 確定性程度

    def to_dict(self) -> Dict:
        return {
            'from_id': self.from_id,
            'to_id': self.to_id,
            'kind': self.kind,
            'line_number': self.line_number,
            'confidence': self.confidence,
        }


@dataclass
class ExtractionResult:
    """提取結果"""
    nodes: List[CodeNode] = field(default_factory=list)
    edges: List[CodeEdge] = field(default_factory=list)
    file_path: str = ''
    file_hash: str = ''
    language: str = ''
    errors: List[str] = field(default_factory=list)


# =============================================================================
# Constants
# =============================================================================

SUPPORTED_EXTENSIONS = {
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.py': 'python',
    '.go': 'go',
    '.java': 'java',
}

# 忽略的目錄
IGNORED_DIRS = {
    'node_modules',
    '.git',
    '__pycache__',
    '.venv',
    'venv',
    'dist',
    'build',
    '.next',
    'coverage',
}

# =============================================================================
# Helper Functions
# =============================================================================

def get_supported_languages() -> List[str]:
    """取得支援的語言列表"""
    return list(set(SUPPORTED_EXTENSIONS.values()))

def compute_file_hash(file_path: str) -> str:
    """計算檔案內容 hash"""
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def make_node_id(kind: str, file_path: str, name: str = None) -> str:
    """
    生成 Node ID

    格式：{kind}.{file_path}[:{name}]
    例如：
    - file.src/api/auth.ts
    - func.src/api/auth.ts:validateToken
    - class.src/models/User.ts:User
    """
    base = f"{kind}.{file_path}"
    if name:
        return f"{base}:{name}"
    return base

def detect_language(file_path: str) -> Optional[str]:
    """偵測檔案語言"""
    ext = os.path.splitext(file_path)[1].lower()
    return SUPPORTED_EXTENSIONS.get(ext)

# =============================================================================
# Regex-Based Extractors (Fallback when Tree-sitter unavailable)
# =============================================================================

class RegexExtractor:
    """
    基於正則表達式的提取器

    當 Tree-sitter 不可用時作為 fallback。
    準確度較低但無需額外依賴。
    """

    # TypeScript/JavaScript patterns
    TS_PATTERNS = {
        'import': re.compile(
            r'^import\s+(?:(?:\{[^}]+\}|\*\s+as\s+\w+|\w+)\s+from\s+)?[\'"]([^\'"]+)[\'"]',
            re.MULTILINE
        ),
        'export_function': re.compile(
            r'^export\s+(?:async\s+)?function\s+(\w+)',
            re.MULTILINE
        ),
        'export_const_arrow': re.compile(
            r'^export\s+const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*(?::\s*[^=]+)?\s*=>',
            re.MULTILINE
        ),
        'function': re.compile(
            r'^(?:async\s+)?function\s+(\w+)',
            re.MULTILINE
        ),
        'const_arrow': re.compile(
            r'^const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*(?::\s*[^=]+)?\s*=>',
            re.MULTILINE
        ),
        'class': re.compile(
            r'^(?:export\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?',
            re.MULTILINE
        ),
        'interface': re.compile(
            r'^(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+([^{]+))?',
            re.MULTILINE
        ),
        'type': re.compile(
            r'^(?:export\s+)?type\s+(\w+)\s*=',
            re.MULTILINE
        ),
        'const': re.compile(
            r'^(?:export\s+)?const\s+(\w+)\s*(?::\s*[^=]+)?\s*=\s*[^=]',
            re.MULTILINE
        ),
    }

    # Python patterns
    PY_PATTERNS = {
        'import': re.compile(
            r'^(?:from\s+(\S+)\s+)?import\s+(.+)$',
            re.MULTILINE
        ),
        'function': re.compile(
            r'^(?:async\s+)?def\s+(\w+)\s*\(',
            re.MULTILINE
        ),
        'class': re.compile(
            r'^class\s+(\w+)(?:\s*\(([^)]*)\))?:',
            re.MULTILINE
        ),
        'const': re.compile(
            r'^([A-Z][A-Z0-9_]*)\s*=',
            re.MULTILINE
        ),
    }

    # Java patterns
    JAVA_PATTERNS = {
        'package': re.compile(
            r'^\s*package\s+([\w.]+)\s*;',
            re.MULTILINE
        ),
        'import': re.compile(
            r'^\s*import\s+(?:static\s+)?([\w.*]+)\s*;',
            re.MULTILINE
        ),
        'class': re.compile(
            r'^\s*(?:public\s+|private\s+|protected\s+)?(?:abstract\s+)?(?:final\s+)?(?:static\s+)?class\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+([\w.<>]+))?(?:\s+implements\s+([\w\s,.<>]+))?\s*\{',
            re.MULTILINE
        ),
        'interface': re.compile(
            r'^\s*(?:public\s+|private\s+|protected\s+)?interface\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+([\w\s,.<>]+))?\s*\{',
            re.MULTILINE
        ),
        'enum': re.compile(
            r'^\s*(?:public\s+|private\s+|protected\s+)?enum\s+(\w+)(?:\s+implements\s+([\w\s,.<>]+))?\s*\{',
            re.MULTILINE
        ),
        'annotation': re.compile(
            r'^\s*(?:public\s+|private\s+|protected\s+)?@interface\s+(\w+)\s*\{',
            re.MULTILINE
        ),
        'method': re.compile(
            r'^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:(?:public|private|protected)\s+)?(?:static\s+)?(?:final\s+)?(?:abstract\s+)?(?:synchronized\s+)?(?:native\s+)?(?:<[^>]+>\s+)?([A-Z][\w.<>\[\]]*|void|int|long|short|byte|char|boolean|float|double)\s+(\w+)\s*\(([^)]*)\)(?:\s+throws\s+([\w\s,.<>]+))?\s*(?:\{|;)',
            re.MULTILINE
        ),
        'field': re.compile(
            r'^\s*(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:final\s+)?(?:transient\s+)?(?:volatile\s+)?([\w.<>\[\],\s]+)\s+(\w+)(?:\s*=\s*[^;]+)?\s*;',
            re.MULTILINE
        ),
        'constant': re.compile(
            r'^\s*(?:public\s+|private\s+|protected\s+)?static\s+final\s+([\w.<>\[\]]+)\s+([A-Z][A-Z0-9_]*)\s*=',
            re.MULTILINE
        ),
    }

    @classmethod
    def extract_typescript(cls, content: str, file_path: str) -> ExtractionResult:
        """提取 TypeScript/JavaScript"""
        result = ExtractionResult(
            file_path=file_path,
            language='typescript',
            file_hash=hashlib.md5(content.encode()).hexdigest()
        )

        # File node
        file_node = CodeNode(
            id=make_node_id('file', file_path),
            kind='file',
            name=os.path.basename(file_path),
            file_path=file_path,
            language='typescript',
            hash=result.file_hash
        )
        result.nodes.append(file_node)

        lines = content.split('\n')

        # Extract imports
        for match in cls.TS_PATTERNS['import'].finditer(content):
            import_path = match.group(1)
            line_num = content[:match.start()].count('\n') + 1

            # 建立 edge 到被導入的模組
            target_id = f"module.{import_path}"
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=target_id,
                kind='imports',
                line_number=line_num
            ))

        # Extract functions (export function)
        for match in cls.TS_PATTERNS['export_function'].finditer(content):
            name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1

            # 找到函式結束行（簡化：找下一個同層級的定義）
            line_end = cls._find_block_end(lines, line_num - 1)

            func_node = CodeNode(
                id=make_node_id('function', file_path, name),
                kind='function',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                visibility='public',
                language='typescript'
            )
            result.nodes.append(func_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=func_node.id,
                kind='defines'
            ))

        # Extract arrow functions (export const xxx = () =>)
        for match in cls.TS_PATTERNS['export_const_arrow'].finditer(content):
            name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            line_end = cls._find_block_end(lines, line_num - 1)

            func_node = CodeNode(
                id=make_node_id('function', file_path, name),
                kind='function',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                visibility='public',
                language='typescript'
            )
            result.nodes.append(func_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=func_node.id,
                kind='defines'
            ))

        # Extract classes
        for match in cls.TS_PATTERNS['class'].finditer(content):
            name = match.group(1)
            extends = match.group(2)
            implements = match.group(3)
            line_num = content[:match.start()].count('\n') + 1
            line_end = cls._find_block_end(lines, line_num - 1)

            class_node = CodeNode(
                id=make_node_id('class', file_path, name),
                kind='class',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                visibility='public',
                language='typescript'
            )
            result.nodes.append(class_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=class_node.id,
                kind='defines'
            ))

            # 繼承關係
            if extends:
                result.edges.append(CodeEdge(
                    from_id=class_node.id,
                    to_id=f"class.{extends}",
                    kind='extends',
                    line_number=line_num,
                    confidence=0.8  # 不確定目標檔案
                ))

            # 實作關係
            if implements:
                for iface in implements.split(','):
                    iface = iface.strip()
                    if iface:
                        result.edges.append(CodeEdge(
                            from_id=class_node.id,
                            to_id=f"interface.{iface}",
                            kind='implements',
                            line_number=line_num,
                            confidence=0.8
                        ))

        # Extract interfaces
        for match in cls.TS_PATTERNS['interface'].finditer(content):
            name = match.group(1)
            extends = match.group(2)
            line_num = content[:match.start()].count('\n') + 1
            line_end = cls._find_block_end(lines, line_num - 1)

            iface_node = CodeNode(
                id=make_node_id('interface', file_path, name),
                kind='interface',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                language='typescript'
            )
            result.nodes.append(iface_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=iface_node.id,
                kind='defines'
            ))

        # Extract type aliases
        for match in cls.TS_PATTERNS['type'].finditer(content):
            name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1

            type_node = CodeNode(
                id=make_node_id('type', file_path, name),
                kind='type',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                language='typescript'
            )
            result.nodes.append(type_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=type_node.id,
                kind='defines'
            ))

        return result

    @classmethod
    def extract_python(cls, content: str, file_path: str) -> ExtractionResult:
        """提取 Python"""
        result = ExtractionResult(
            file_path=file_path,
            language='python',
            file_hash=hashlib.md5(content.encode()).hexdigest()
        )

        # File node
        file_node = CodeNode(
            id=make_node_id('file', file_path),
            kind='file',
            name=os.path.basename(file_path),
            file_path=file_path,
            language='python',
            hash=result.file_hash
        )
        result.nodes.append(file_node)

        lines = content.split('\n')

        # Extract imports
        for match in cls.PY_PATTERNS['import'].finditer(content):
            from_module = match.group(1)
            imports = match.group(2)
            line_num = content[:match.start()].count('\n') + 1

            if from_module:
                target_id = f"module.{from_module}"
            else:
                # import xxx, yyy
                target_id = f"module.{imports.split(',')[0].strip().split()[0]}"

            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=target_id,
                kind='imports',
                line_number=line_num
            ))

        # Extract functions
        for match in cls.PY_PATTERNS['function'].finditer(content):
            name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            line_end = cls._find_python_block_end(lines, line_num - 1)

            # 判斷 visibility
            visibility = 'private' if name.startswith('_') else 'public'

            func_node = CodeNode(
                id=make_node_id('function', file_path, name),
                kind='function',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                visibility=visibility,
                language='python'
            )
            result.nodes.append(func_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=func_node.id,
                kind='defines'
            ))

        # Extract classes
        for match in cls.PY_PATTERNS['class'].finditer(content):
            name = match.group(1)
            bases = match.group(2)
            line_num = content[:match.start()].count('\n') + 1
            line_end = cls._find_python_block_end(lines, line_num - 1)

            class_node = CodeNode(
                id=make_node_id('class', file_path, name),
                kind='class',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                language='python'
            )
            result.nodes.append(class_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=class_node.id,
                kind='defines'
            ))

            # 繼承關係
            if bases:
                for base in bases.split(','):
                    base = base.strip()
                    if base and base != 'object':
                        result.edges.append(CodeEdge(
                            from_id=class_node.id,
                            to_id=f"class.{base}",
                            kind='extends',
                            line_number=line_num,
                            confidence=0.8
                        ))

        # Extract constants (UPPER_CASE)
        for match in cls.PY_PATTERNS['const'].finditer(content):
            name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1

            const_node = CodeNode(
                id=make_node_id('constant', file_path, name),
                kind='constant',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                language='python'
            )
            result.nodes.append(const_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=const_node.id,
                kind='defines'
            ))

        return result

    @staticmethod
    def _find_block_end(lines: List[str], start_line: int) -> int:
        """找到 JS/TS block 結束行（簡化版：計算括號）"""
        brace_count = 0
        started = False

        for i, line in enumerate(lines[start_line:], start=start_line):
            for char in line:
                if char == '{':
                    brace_count += 1
                    started = True
                elif char == '}':
                    brace_count -= 1
                    if started and brace_count == 0:
                        return i + 1  # 1-indexed

        return len(lines)

    @staticmethod
    def _find_python_block_end(lines: List[str], start_line: int) -> int:
        """找到 Python block 結束行（基於縮排）"""
        if start_line >= len(lines):
            return start_line + 1

        # 取得起始縮排
        start_indent = len(lines[start_line]) - len(lines[start_line].lstrip())

        for i, line in enumerate(lines[start_line + 1:], start=start_line + 1):
            stripped = line.strip()
            if not stripped:  # 空行
                continue
            if stripped.startswith('#'):  # 註解
                continue

            current_indent = len(line) - len(line.lstrip())
            if current_indent <= start_indent:
                return i

        return len(lines)

    @staticmethod
    def _remove_java_comments(content: str) -> str:
        """
        移除 Java 註解以避免 regex 誤判

        處理：
        - 單行註解: // ...
        - 多行註解: /* ... */
        - Javadoc 註解: /** ... */
        """
        # 移除多行註解（包含 javadoc）
        content = re.sub(r'/\*[\s\S]*?\*/', '', content)
        # 移除單行註解
        content = re.sub(r'//[^\n]*', '', content)
        return content

    @staticmethod
    def _find_java_block_end(lines: List[str], start_line: int) -> int:
        """
        找到 Java block 結束行（括號配對，考慮字串/字元字面值）

        處理：
        - 巢狀括號
        - 字串字面值中的括號
        - 字元字面值中的括號
        """
        brace_count = 0
        started = False
        in_string = False
        in_char = False
        escape_next = False

        for i, line in enumerate(lines[start_line:], start=start_line):
            for char in line:
                if escape_next:
                    escape_next = False
                    continue

                if char == '\\':
                    escape_next = True
                    continue

                if char == '"' and not in_char:
                    in_string = not in_string
                    continue

                if char == "'" and not in_string:
                    in_char = not in_char
                    continue

                if in_string or in_char:
                    continue

                if char == '{':
                    brace_count += 1
                    started = True
                elif char == '}':
                    brace_count -= 1
                    if started and brace_count == 0:
                        return i + 1  # 1-indexed

        return len(lines)

    @classmethod
    def extract_java(cls, content: str, file_path: str) -> ExtractionResult:
        """提取 Java 程式碼結構"""
        result = ExtractionResult(
            file_path=file_path,
            language='java',
            file_hash=hashlib.md5(content.encode()).hexdigest()
        )

        # 前處理：移除註解
        cleaned_content = cls._remove_java_comments(content)
        lines = cleaned_content.split('\n')

        # File node
        file_node = CodeNode(
            id=make_node_id('file', file_path),
            kind='file',
            name=os.path.basename(file_path),
            file_path=file_path,
            language='java',
            hash=result.file_hash
        )
        result.nodes.append(file_node)

        # 追蹤 package 名稱用於 qualified ID
        package_name = ''

        # 提取 package
        for match in cls.JAVA_PATTERNS['package'].finditer(cleaned_content):
            package_name = match.group(1)
            break  # 每個檔案只有一個 package

        # 提取 imports
        for match in cls.JAVA_PATTERNS['import'].finditer(cleaned_content):
            import_path = match.group(1)
            line_num = cleaned_content[:match.start()].count('\n') + 1

            # 處理萬用字元 import
            if import_path.endswith('.*'):
                target_id = f"package.{import_path[:-2]}"
            else:
                target_id = f"class.{import_path}"

            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=target_id,
                kind='imports',
                line_number=line_num
            ))

        # 追蹤 class 堆疊處理 inner class
        class_stack = []  # [(class_name, class_id, line_end)]

        # 提取 classes
        for match in cls.JAVA_PATTERNS['class'].finditer(cleaned_content):
            name = match.group(1)
            extends = match.group(2)
            implements = match.group(3)
            line_num = cleaned_content[:match.start()].count('\n') + 1
            line_end = cls._find_java_block_end(lines, line_num - 1)

            # 判斷 visibility
            match_text = match.group(0)
            if 'public' in match_text:
                visibility = 'public'
            elif 'protected' in match_text:
                visibility = 'protected'
            elif 'private' in match_text:
                visibility = 'private'
            else:
                visibility = 'package'  # Java 預設

            # 生成 qualified ID
            qualified_name = f"{package_name}.{name}" if package_name else name
            class_id = make_node_id('class', file_path, qualified_name)

            class_node = CodeNode(
                id=class_id,
                kind='class',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                visibility=visibility,
                language='java'
            )
            result.nodes.append(class_node)

            # 父子關係
            if class_stack and line_num < class_stack[-1][2]:
                # Inner class - 包含於父 class
                parent_id = class_stack[-1][1]
                result.edges.append(CodeEdge(
                    from_id=parent_id,
                    to_id=class_id,
                    kind='contains',
                    line_number=line_num
                ))
            else:
                # 頂層 class - 由 file 定義
                result.edges.append(CodeEdge(
                    from_id=file_node.id,
                    to_id=class_id,
                    kind='defines'
                ))

            # 繼承
            if extends:
                extends_name = extends.strip().split('<')[0].strip()
                result.edges.append(CodeEdge(
                    from_id=class_id,
                    to_id=f"class.{extends_name}",
                    kind='extends',
                    line_number=line_num,
                    confidence=0.8
                ))

            # 實作
            if implements:
                for iface in implements.split(','):
                    iface_name = iface.strip().split('<')[0].strip()
                    if iface_name:
                        result.edges.append(CodeEdge(
                            from_id=class_id,
                            to_id=f"interface.{iface_name}",
                            kind='implements',
                            line_number=line_num,
                            confidence=0.8
                        ))

            # 清理過期的 class stack
            while class_stack and line_num >= class_stack[-1][2]:
                class_stack.pop()

            class_stack.append((name, class_id, line_end))

        # 提取 interfaces
        for match in cls.JAVA_PATTERNS['interface'].finditer(cleaned_content):
            name = match.group(1)
            extends = match.group(2)
            line_num = cleaned_content[:match.start()].count('\n') + 1
            line_end = cls._find_java_block_end(lines, line_num - 1)

            qualified_name = f"{package_name}.{name}" if package_name else name
            iface_id = make_node_id('interface', file_path, qualified_name)

            iface_node = CodeNode(
                id=iface_id,
                kind='interface',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                language='java'
            )
            result.nodes.append(iface_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=iface_id,
                kind='defines'
            ))

            # Interface 繼承
            if extends:
                for parent in extends.split(','):
                    parent_name = parent.strip().split('<')[0].strip()
                    if parent_name:
                        result.edges.append(CodeEdge(
                            from_id=iface_id,
                            to_id=f"interface.{parent_name}",
                            kind='extends',
                            line_number=line_num,
                            confidence=0.8
                        ))

        # 提取 enums
        for match in cls.JAVA_PATTERNS['enum'].finditer(cleaned_content):
            name = match.group(1)
            implements = match.group(2)
            line_num = cleaned_content[:match.start()].count('\n') + 1
            line_end = cls._find_java_block_end(lines, line_num - 1)

            qualified_name = f"{package_name}.{name}" if package_name else name
            enum_id = make_node_id('enum', file_path, qualified_name)

            enum_node = CodeNode(
                id=enum_id,
                kind='enum',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                language='java'
            )
            result.nodes.append(enum_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=enum_id,
                kind='defines'
            ))

            # Enum 實作
            if implements:
                for iface in implements.split(','):
                    iface_name = iface.strip().split('<')[0].strip()
                    if iface_name:
                        result.edges.append(CodeEdge(
                            from_id=enum_id,
                            to_id=f"interface.{iface_name}",
                            kind='implements',
                            line_number=line_num,
                            confidence=0.8
                        ))

        # 提取 annotations (@interface)
        for match in cls.JAVA_PATTERNS['annotation'].finditer(cleaned_content):
            name = match.group(1)
            line_num = cleaned_content[:match.start()].count('\n') + 1
            line_end = cls._find_java_block_end(lines, line_num - 1)

            qualified_name = f"{package_name}.{name}" if package_name else name
            annotation_id = make_node_id('annotation', file_path, qualified_name)

            annotation_node = CodeNode(
                id=annotation_id,
                kind='annotation',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                language='java'
            )
            result.nodes.append(annotation_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=annotation_id,
                kind='defines'
            ))

        # 收集所有 class/interface/enum 名稱和範圍用於過濾建構子和定位 containing class
        type_names = set()
        type_ranges = []  # [(name, id, line_start, line_end)]
        for node in result.nodes:
            if node.kind in ('class', 'interface', 'enum', 'annotation'):
                type_names.add(node.name)
                type_ranges.append((node.name, node.id, node.line_start, node.line_end))

        # 按 line_start 排序，用於找到最內層的 containing class
        type_ranges.sort(key=lambda x: x[2])

        # 提取 methods（排除建構子）
        for match in cls.JAVA_PATTERNS['method'].finditer(cleaned_content):
            return_type = match.group(1).strip()
            name = match.group(2)
            params = match.group(3)
            throws = match.group(4)
            line_num = cleaned_content[:match.start()].count('\n') + 1

            # 跳過建構子（方法名等於 class 名稱且沒有 return type）
            # 建構子的特徵：名稱等於其所在 class，且 return type 也等於該 class
            # 例如：public User(String name) 會被 regex 匹配為 return_type=User, name=User
            if name in type_names and return_type == name:
                continue

            # 跳過看起來不像方法的匹配（例如 throw new X()）
            if return_type in ('throw', 'return', 'new', 'if', 'for', 'while', 'switch'):
                continue

            line_end = cls._find_java_block_end(lines, line_num - 1)

            # 判斷 visibility
            match_text = match.group(0)
            if 'public' in match_text:
                visibility = 'public'
            elif 'protected' in match_text:
                visibility = 'protected'
            elif 'private' in match_text:
                visibility = 'private'
            else:
                visibility = 'package'

            method_id = make_node_id('function', file_path, name)
            signature = f"{return_type} {name}({params})"
            if throws:
                signature += f" throws {throws.strip()}"

            method_node = CodeNode(
                id=method_id,
                kind='function',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                signature=signature,
                visibility=visibility,
                language='java'
            )
            result.nodes.append(method_node)

            # 找到包含此 method 的最內層 class
            containing_class = None
            for type_name, type_id, type_start, type_end in reversed(type_ranges):
                if type_start < line_num < type_end:
                    containing_class = type_id
                    break

            if containing_class:
                result.edges.append(CodeEdge(
                    from_id=containing_class,
                    to_id=method_id,
                    kind='contains',
                    line_number=line_num
                ))
            else:
                result.edges.append(CodeEdge(
                    from_id=file_node.id,
                    to_id=method_id,
                    kind='defines'
                ))

        # 提取 constants (static final UPPER_CASE)
        for match in cls.JAVA_PATTERNS['constant'].finditer(cleaned_content):
            type_name = match.group(1)
            name = match.group(2)
            line_num = cleaned_content[:match.start()].count('\n') + 1

            const_id = make_node_id('constant', file_path, name)

            const_node = CodeNode(
                id=const_id,
                kind='constant',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                language='java'
            )
            result.nodes.append(const_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=const_id,
                kind='defines'
            ))

        return result


# =============================================================================
# Main API
# =============================================================================

def extract_from_file(file_path: str) -> ExtractionResult:
    """
    從單一檔案提取程式碼結構

    Args:
        file_path: 檔案路徑

    Returns:
        ExtractionResult 包含 nodes 和 edges
    """
    if not os.path.exists(file_path):
        return ExtractionResult(
            file_path=file_path,
            errors=[f"File not found: {file_path}"]
        )

    language = detect_language(file_path)
    if not language:
        return ExtractionResult(
            file_path=file_path,
            errors=[f"Unsupported file type: {file_path}"]
        )

    try:
        from servers.utils import read_text_file
        content = read_text_file(file_path)
    except (FileNotFoundError, UnicodeDecodeError) as e:
        return ExtractionResult(
            file_path=file_path,
            errors=[f"Failed to read file: {str(e)}"]
        )

    # 使用 Regex extractor（fallback）
    # TODO: 當 Tree-sitter 可用時，優先使用
    if language in ('typescript', 'javascript'):
        return RegexExtractor.extract_typescript(content, file_path)
    elif language == 'python':
        return RegexExtractor.extract_python(content, file_path)
    elif language == 'java':
        return RegexExtractor.extract_java(content, file_path)
    else:
        return ExtractionResult(
            file_path=file_path,
            language=language,
            errors=[f"Extractor not implemented for: {language}"]
        )


def extract_from_directory(
    directory: str,
    incremental: bool = True,
    project: str = None,
    file_hashes: Dict[str, str] = None
) -> Dict:
    """
    從目錄提取程式碼結構

    Args:
        directory: 目錄路徑
        incremental: 是否增量更新（跳過未變更檔案）
        project: 專案名稱
        file_hashes: 已知的檔案 hash（用於增量比對）

    Returns:
        {
            'nodes': List[Dict],
            'edges': List[Dict],
            'files_processed': int,
            'files_skipped': int,
            'errors': List[str],
            'file_hashes': Dict[str, str]  # 新的 hash 對照表
        }
    """
    if not os.path.isdir(directory):
        return {
            'nodes': [],
            'edges': [],
            'files_processed': 0,
            'files_skipped': 0,
            'errors': [f"Directory not found: {directory}"],
            'file_hashes': {}
        }

    file_hashes = file_hashes or {}
    all_nodes = []
    all_edges = []
    new_hashes = {}
    errors = []
    files_processed = 0
    files_skipped = 0

    # 遍歷目錄
    for root, dirs, files in os.walk(directory):
        # 跳過忽略的目錄
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue

            file_path = os.path.join(root, filename)
            rel_path = os.path.relpath(file_path, directory)

            # 增量檢查
            if incremental:
                current_hash = compute_file_hash(file_path)
                if rel_path in file_hashes and file_hashes[rel_path] == current_hash:
                    files_skipped += 1
                    new_hashes[rel_path] = current_hash
                    continue

            # 提取
            result = extract_from_file(file_path)

            if result.errors:
                errors.extend(result.errors)
            else:
                all_nodes.extend([n.to_dict() for n in result.nodes])
                all_edges.extend([e.to_dict() for e in result.edges])
                new_hashes[rel_path] = result.file_hash
                files_processed += 1

    return {
        'nodes': all_nodes,
        'edges': all_edges,
        'files_processed': files_processed,
        'files_skipped': files_skipped,
        'errors': errors,
        'file_hashes': new_hashes
    }
