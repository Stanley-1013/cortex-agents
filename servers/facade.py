"""
Neuromorphic Facade

統一入口，黑箱化系統複雜度。
使用者/Agent 只需要這個模組。

設計原則：
1. 極簡 API，一個函數做一件事
2. 錯誤訊息可行動（告訴使用者怎麼修）
3. 整合多個低階模組
"""

import os
import subprocess
from typing import Dict, List, Optional
from datetime import datetime

# =============================================================================
# SCHEMA（供 Agent 參考）
# =============================================================================

SCHEMA = """
=== Neuromorphic Facade ===
統一入口，使用者/Agent 只需要這些 API。

## 基本操作

sync(project_path=None, project_name=None, incremental=True) -> SyncResult
    同步專案 Code Graph（主要 API）
    - 自動偵測變更檔案
    - 增量更新 Code Graph（或完整重建）
    - 回傳同步結果

    Example:
        result = sync('/path/to/project', 'my-project')
        # {'files_processed': 10, 'nodes_added': 50, ...}

status(project_name=None) -> StatusReport
    取得專案狀態總覽
    - Code Graph 統計
    - SSOT 狀態
    - 最後同步時間

init(project_path, project_name=None) -> InitResult
    初始化專案（首次使用時呼叫）

## PFC 三層查詢（Story 15）

get_full_context(branch, project_name=None) -> Dict
    取得 Branch 完整三層 context（結構化版本）
    - L0: SSOT 層（意圖）- doctrine, flow_spec, related_nodes
    - L1: Code Graph 層（現實）- related_files, dependencies
    - L2: Memory 層（經驗）- 相關記憶
    - Drift: 偏差檢測

    Args:
        branch: {'flow_id': 'flow.auth', 'domain_ids': ['domain.user']}

    Example:
        ctx = get_full_context({'flow_id': 'flow.auth'})
        # {'branch': {...}, 'ssot': {...}, 'code': {...}, 'memory': [...], 'drift': {...}}

format_context_for_agent(context) -> str
    將 get_full_context 結果格式化為 Agent 可讀的 Markdown

## Critic 增強驗證（Story 16）

validate_with_graph(modified_files, branch, project_name=None) -> Dict
    使用 Graph 做增強驗證
    - 修改影響分析
    - SSOT 符合性檢查
    - 測試覆蓋檢查

    Args:
        modified_files: ['src/api/auth.py', ...]
        branch: {'flow_id': 'flow.auth'}

    Returns: {
        'impact_analysis': {...},
        'ssot_compliance': {...},
        'test_coverage': {...},
        'recommendations': [...]
    }

format_validation_report(validation) -> str
    將 validate_with_graph 結果格式化為 Markdown 報告

## Drift 偵測

check_drift(project_name, flow_id=None) -> DriftReport
    檢查 SSOT vs Code 偏差

    Example:
        report = check_drift('my-project', 'flow.auth')
        # {'has_drift': True, 'drifts': [...]}

## SSOT Graph 同步

sync_ssot_graph(project_name=None) -> SyncResult
    同步 SSOT Index 到 project_nodes/project_edges
    - 從 PROJECT_INDEX.md 解析所有節點
    - 建立節點和關係到 Graph
    - 動態支援任何類型（不寫死）

    Example:
        result = sync_ssot_graph('my-project')
        # {'nodes_added': 15, 'edges_added': 20, 'types_found': ['flows', ...]}
"""

# =============================================================================
# Errors
# =============================================================================

class FacadeError(Exception):
    """Facade 層錯誤基類"""
    pass

class ProjectNotFoundError(FacadeError):
    """專案不存在"""
    def __init__(self, path: str):
        self.path = path
        super().__init__(
            f"Project path not found: {path}\n\n"
            f"Please check:\n"
            f"  1. The path exists\n"
            f"  2. You have read permissions\n"
        )

class NotInitializedError(FacadeError):
    """系統未初始化"""
    def __init__(self):
        super().__init__(
            f"Neuromorphic system not initialized.\n\n"
            f"Please run:\n"
            f"  from servers.facade import init\n"
            f"  init('/path/to/your/project', 'project-name')\n"
        )

class CodeGraphEmptyError(FacadeError):
    """Code Graph 為空"""
    def __init__(self, project: str):
        self.project = project
        super().__init__(
            f"Code Graph is empty for project '{project}'.\n\n"
            f"Please run:\n"
            f"  from servers.facade import sync\n"
            f"  sync('/path/to/project', '{project}')\n"
        )

# =============================================================================
# Main API
# =============================================================================

def init(project_path: str, project_name: str = None) -> Dict:
    """
    初始化專案

    Args:
        project_path: 專案目錄路徑
        project_name: 專案名稱（預設使用目錄名）

    Returns:
        {
            'project_name': str,
            'project_path': str,
            'schema_initialized': bool,
            'types_initialized': (int, int),
            'code_graph_synced': bool,
            'sync_result': {...}
        }
    """
    from servers.registry import init_registry
    from servers.code_graph import sync_from_directory

    # 驗證路徑
    if not os.path.isdir(project_path):
        raise ProjectNotFoundError(project_path)

    project_name = project_name or os.path.basename(os.path.abspath(project_path))

    # 初始化 Schema 和預設類型
    node_count, edge_count = init_registry()

    # 同步 Code Graph
    sync_result = sync_from_directory(project_name, project_path, incremental=False)

    return {
        'project_name': project_name,
        'project_path': project_path,
        'schema_initialized': True,
        'types_initialized': (node_count, edge_count),
        'code_graph_synced': len(sync_result.get('errors', [])) == 0,
        'sync_result': sync_result
    }


def sync(project_path: str = None, project_name: str = None, incremental: bool = True) -> Dict:
    """
    同步專案 Code Graph

    Args:
        project_path: 專案目錄路徑
        project_name: 專案名稱
        incremental: 是否增量更新（預設 True）

    Returns:
        {
            'files_processed': int,
            'files_skipped': int,
            'nodes_added': int,
            'nodes_updated': int,
            'edges_added': int,
            'duration_ms': int,
            'errors': List[str]
        }
    """
    from servers.code_graph import sync_from_directory
    import time

    # 預設使用當前目錄
    project_path = project_path or os.getcwd()
    project_name = project_name or os.path.basename(os.path.abspath(project_path))

    if not os.path.isdir(project_path):
        raise ProjectNotFoundError(project_path)

    start_time = time.time()
    result = sync_from_directory(project_name, project_path, incremental=incremental)
    duration_ms = int((time.time() - start_time) * 1000)

    result['duration_ms'] = duration_ms
    return result


def status(project_name: str = None) -> Dict:
    """
    取得專案狀態總覽

    Returns:
        {
            'project_name': str,
            'code_graph': {
                'node_count': int,
                'edge_count': int,
                'file_count': int,
                'kinds': {...},
                'last_sync': datetime
            },
            'ssot': {
                'has_doctrine': bool,
                'has_index': bool,
                'flow_count': int,
                'domain_count': int
            },
            'registry': {
                'node_kinds': int,
                'edge_kinds': int
            },
            'health': 'ok' | 'warning' | 'error',
            'messages': List[str]
        }
    """
    from servers.code_graph import get_code_graph_stats
    from servers.registry import diagnose as registry_diagnose
    from servers.ssot import load_doctrine, parse_index

    project_name = project_name or os.path.basename(os.getcwd())
    messages = []
    health = 'ok'

    # Code Graph 狀態
    code_graph = get_code_graph_stats(project_name)
    if code_graph['node_count'] == 0:
        health = 'warning'
        messages.append(f"Code Graph is empty. Run sync('{project_name}') to populate.")

    # Registry 狀態
    registry_status = registry_diagnose()
    registry = {
        'node_kinds': registry_status.get('node_kinds_count', 0),
        'edge_kinds': registry_status.get('edge_kinds_count', 0)
    }
    if registry_status['status'] != 'ok':
        health = 'warning' if health == 'ok' else health
        messages.extend(registry_status.get('messages', []))

    # SSOT 狀態
    ssot = {
        'has_doctrine': False,
        'has_index': False,
        'flow_count': 0,
        'domain_count': 0
    }
    try:
        doctrine = load_doctrine()
        ssot['has_doctrine'] = bool(doctrine)
    except:
        pass

    try:
        index = parse_index()
        ssot['has_index'] = bool(index)
        ssot['flow_count'] = len([n for n in index if n.get('kind') == 'flow'])
        ssot['domain_count'] = len([n for n in index if n.get('kind') == 'domain'])
    except:
        pass

    if not ssot['has_doctrine']:
        messages.append("SSOT Doctrine not found. Create brain/ssot/PROJECT_DOCTRINE.md")

    return {
        'project_name': project_name,
        'code_graph': code_graph,
        'ssot': ssot,
        'registry': registry,
        'health': health,
        'messages': messages
    }


def get_context(branch: Dict, project_name: str = None) -> str:
    """
    取得 Branch 完整 context

    整合 SSOT + Memory + Graph 資訊，供 Agent 使用。

    Args:
        branch: {'flow_id': 'flow.auth', 'domain_ids': ['domain.user']}
        project_name: 專案名稱

    Returns:
        格式化的 context 字串
    """
    from servers.ssot import load_doctrine, load_flow_spec
    from servers.memory import search_memory
    from servers.graph import get_neighbors
    from servers.code_graph import get_code_nodes

    project_name = project_name or os.path.basename(os.getcwd())
    lines = []

    # 1. Doctrine（核心原則）
    try:
        doctrine = load_doctrine()
        if doctrine:
            lines.append("## Doctrine (核心原則)")
            lines.append(doctrine[:1000] + "..." if len(doctrine) > 1000 else doctrine)
            lines.append("")
    except:
        pass

    # 2. Flow Spec
    flow_id = branch.get('flow_id')
    if flow_id:
        try:
            flow_spec = load_flow_spec(flow_id)
            if flow_spec:
                lines.append(f"## Flow Spec: {flow_id}")
                lines.append(flow_spec[:1500] + "..." if len(flow_spec) > 1500 else flow_spec)
                lines.append("")
        except:
            pass

        # 3. Graph Neighbors（SSOT 層）
        try:
            neighbors = get_neighbors(flow_id, project_name, depth=1)
            if neighbors:
                lines.append(f"## 相關節點 (SSOT Graph)")
                for n in neighbors[:10]:
                    lines.append(f"- {n['id']} ({n['kind']})")
                lines.append("")
        except:
            pass

        # 4. Code Graph（Code 層）
        try:
            # 找與此 flow 相關的程式碼
            code_nodes = get_code_nodes(project_name, limit=20)
            if code_nodes:
                lines.append(f"## Code Structure (Top Files)")
                seen_files = set()
                for n in code_nodes:
                    if n['kind'] == 'file' and n['file_path'] not in seen_files:
                        seen_files.add(n['file_path'])
                        lines.append(f"- {n['file_path']}")
                        if len(seen_files) >= 10:
                            break
                lines.append("")
        except:
            pass

    # 5. Related Memory
    try:
        query = flow_id.replace('flow.', '') if flow_id else 'general'
        memories = search_memory(query, project=project_name, limit=3)
        if memories:
            lines.append("## 相關記憶")
            for m in memories:
                lines.append(f"- **{m.get('title', 'Untitled')}**: {m.get('content', '')[:100]}...")
            lines.append("")
    except:
        pass

    return "\n".join(lines) if lines else f"No context available for branch: {branch}"


def check_drift(project_name: str, flow_id: str = None) -> Dict:
    """
    檢查 SSOT vs Code 偏差

    Returns:
        {
            'has_drift': bool,
            'drifts': [
                {
                    'type': 'missing_implementation' | 'missing_spec' | 'mismatch',
                    'ssot_item': str,
                    'code_item': str,
                    'description': str
                }
            ],
            'summary': str
        }
    """
    from servers.ssot import parse_index
    from servers.graph import get_neighbors
    from servers.code_graph import get_code_nodes

    drifts = []

    # 1. 取得 SSOT 定義
    try:
        ssot_data = parse_index()
        # parse_index 返回 {'flows': [...], 'domains': [...], ...}
        # 展平為節點列表
        ssot_nodes = []
        for kind, nodes in ssot_data.items():
            for node in nodes:
                if isinstance(node, dict):
                    node['kind'] = kind.rstrip('s')  # flows -> flow
                    ssot_nodes.append(node)
    except:
        return {
            'has_drift': False,
            'drifts': [],
            'summary': 'Cannot check drift: SSOT Index not found'
        }

    # 2. 取得 Code Graph
    code_nodes = get_code_nodes(project_name, limit=1000)
    code_files = set(n['file_path'] for n in code_nodes if n.get('file_path'))

    # 3. 檢查 Flow → 應該有對應的 file
    for ssot_node in ssot_nodes:
        if ssot_node.get('kind') != 'flow':
            continue

        if flow_id and ssot_node.get('id') != flow_id:
            continue

        flow_name = ssot_node.get('id', '').replace('flow.', '')
        ref = ssot_node.get('ref', '')

        # 正規化名稱（處理 - 和 _ 的差異）
        flow_name_normalized = flow_name.lower().replace('-', '_')

        # 檢查是否有對應的實作檔案
        has_impl = False

        # 優先用 ref 匹配
        if ref:
            has_impl = any(ref in f or f.endswith(ref) for f in code_files)

        # 用正規化名稱匹配
        if not has_impl:
            has_impl = any(flow_name_normalized in f.lower().replace('-', '_') for f in code_files)

        if not has_impl:
            drifts.append({
                'type': 'missing_implementation',
                'ssot_item': ssot_node.get('id'),
                'code_item': None,
                'description': f"Flow '{ssot_node.get('id')}' defined in SSOT but no matching code files found"
            })

    # 4. 檢查 Code → 應該有對應的 SSOT
    ssot_ids = set(n.get('id', '') for n in ssot_nodes)
    for code_node in code_nodes:
        if code_node['kind'] != 'file':
            continue

        file_path = code_node.get('file_path', '')
        # 簡化：檢查主要目錄下的檔案是否有對應的 Flow
        if '/api/' in file_path or '/routes/' in file_path:
            # 提取可能的 flow 名稱
            name = os.path.splitext(os.path.basename(file_path))[0]
            expected_flow = f"flow.{name}"

            if expected_flow not in ssot_ids:
                drifts.append({
                    'type': 'missing_spec',
                    'ssot_item': None,
                    'code_item': file_path,
                    'description': f"Code file '{file_path}' exists but no SSOT spec for '{expected_flow}'"
                })

    summary = f"Found {len(drifts)} drift(s)" if drifts else "No drift detected"

    return {
        'has_drift': len(drifts) > 0,
        'drifts': drifts,
        'summary': summary
    }


# =============================================================================
# Story 15: PFC Three-Layer Query
# =============================================================================

def get_full_context(branch: Dict, project_name: str = None) -> Dict:
    """
    取得 Branch 完整三層 context（結構化版本）

    供 PFC 規劃任務時使用，整合：
    - L0: SSOT 層（意圖）
    - L1: Code Graph 層（現實）
    - L2: Memory 層（經驗）
    - Drift: 偏差檢測

    Args:
        branch: {'flow_id': 'flow.auth', 'domain_ids': ['domain.user']}
        project_name: 專案名稱

    Returns:
        {
            'branch': {...},
            'ssot': {
                'doctrine': str,
                'flow_spec': str,
                'related_nodes': [...]
            },
            'code': {
                'related_files': [...],
                'dependencies': [...]
            },
            'memory': [...],
            'drift': {
                'has_drift': bool,
                'drifts': [...]
            }
        }
    """
    from servers.ssot import load_doctrine, load_flow_spec
    from servers.memory import search_memory
    from servers.graph import get_neighbors, get_node
    from servers.code_graph import get_code_nodes, get_code_edges

    project_name = project_name or os.path.basename(os.getcwd())
    flow_id = branch.get('flow_id')
    domain_ids = branch.get('domain_ids', [])

    result = {
        'branch': branch,
        'project_name': project_name,
        'ssot': {
            'doctrine': None,
            'flow_spec': None,
            'related_nodes': []
        },
        'code': {
            'related_files': [],
            'dependencies': []
        },
        'memory': [],
        'drift': {
            'has_drift': False,
            'drifts': []
        }
    }

    # 1. SSOT 層
    try:
        result['ssot']['doctrine'] = load_doctrine()
    except:
        pass

    if flow_id:
        try:
            result['ssot']['flow_spec'] = load_flow_spec(flow_id)
        except:
            pass

        try:
            neighbors = get_neighbors(flow_id, project_name, depth=2)
            result['ssot']['related_nodes'] = neighbors
        except:
            pass

    # 2. Code Graph 層
    try:
        # 取得相關檔案
        code_nodes = get_code_nodes(project_name, limit=50)

        # 如果有 flow_id，過濾相關的檔案
        if flow_id:
            flow_name = flow_id.replace('flow.', '').replace('-', '_')
            related = [n for n in code_nodes
                      if flow_name.lower() in n.get('file_path', '').lower()
                      or flow_name.lower() in n.get('name', '').lower()]
            result['code']['related_files'] = related[:20]
        else:
            result['code']['related_files'] = [n for n in code_nodes if n['kind'] == 'file'][:10]

        # 取得依賴關係
        code_edges = get_code_edges(project_name, limit=50)
        result['code']['dependencies'] = code_edges

    except:
        pass

    # 3. Memory 層
    try:
        query = flow_id.replace('flow.', '') if flow_id else 'general'
        result['memory'] = search_memory(query, project=project_name, limit=5)
    except:
        pass

    # 4. Drift 檢測
    try:
        drift_result = check_drift(project_name, flow_id)
        result['drift'] = drift_result
    except:
        pass

    return result


def format_context_for_agent(context: Dict) -> str:
    """
    將結構化 context 格式化為 Agent 可讀的 Markdown

    Args:
        context: get_full_context() 的返回值

    Returns:
        格式化的 Markdown 字串
    """
    lines = []
    branch = context.get('branch', {})

    lines.append(f"# Context for Branch: {branch.get('flow_id', 'general')}")
    lines.append("")

    # SSOT 層
    ssot = context.get('ssot', {})
    if ssot.get('doctrine'):
        lines.append("## 📜 Doctrine (核心原則)")
        doctrine = ssot['doctrine']
        lines.append(doctrine[:800] + "..." if len(doctrine) > 800 else doctrine)
        lines.append("")

    if ssot.get('flow_spec'):
        lines.append(f"## 📋 Flow Spec: {branch.get('flow_id')}")
        spec = ssot['flow_spec']
        lines.append(spec[:1200] + "..." if len(spec) > 1200 else spec)
        lines.append("")

    if ssot.get('related_nodes'):
        lines.append("## 🔗 Related SSOT Nodes")
        for n in ssot['related_nodes'][:10]:
            direction = "→" if n.get('direction') == 'outgoing' else "←"
            lines.append(f"- {direction} [{n.get('edge_kind', '?')}] {n['id']} ({n.get('kind', '?')})")
        lines.append("")

    # Code 層
    code = context.get('code', {})
    if code.get('related_files'):
        lines.append("## 💻 Related Code Files")
        for f in code['related_files'][:10]:
            lines.append(f"- [{f['kind']}] {f.get('file_path', f['name'])}")
        lines.append("")

    # Memory 層
    memories = context.get('memory', [])
    if memories:
        lines.append("## 🧠 Related Memory")
        for m in memories:
            title = m.get('title', 'Untitled')
            content = m.get('content', '')[:100]
            lines.append(f"- **{title}**: {content}...")
        lines.append("")

    # Drift 警告
    drift = context.get('drift', {})
    if drift.get('has_drift'):
        lines.append("## ⚠️ Drift Warning")
        lines.append(f"**{drift.get('summary', 'Drift detected')}**")
        for d in drift.get('drifts', [])[:5]:
            lines.append(f"- [{d.get('type', '?')}] {d.get('description', '')}")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# Story 16: Critic Graph-Enhanced Validation
# =============================================================================

def validate_with_graph(
    modified_files: List[str],
    branch: Dict,
    project_name: str = None
) -> Dict:
    """
    使用 Graph 做增強驗證

    供 Critic 驗證時使用，檢查：
    1. 修改的影響範圍
    2. SSOT 符合性
    3. 測試覆蓋

    Args:
        modified_files: 被修改的檔案列表
        branch: {'flow_id': 'flow.auth', ...}
        project_name: 專案名稱

    Returns:
        {
            'impact_analysis': {
                'affected_nodes': [...],
                'cross_module_impact': bool,
                'api_affected': bool
            },
            'ssot_compliance': {
                'status': 'ok' | 'warning' | 'violation',
                'checks': [...]
            },
            'test_coverage': {
                'covered': [...],
                'missing': [...]
            },
            'recommendations': [...]
        }
    """
    from servers.graph import get_impact, get_neighbors, list_nodes
    from servers.code_graph import get_code_nodes, get_code_edges

    project_name = project_name or os.path.basename(os.getcwd())
    flow_id = branch.get('flow_id')

    result = {
        'impact_analysis': {
            'affected_nodes': [],
            'cross_module_impact': False,
            'api_affected': False
        },
        'ssot_compliance': {
            'status': 'ok',
            'checks': []
        },
        'test_coverage': {
            'covered': [],
            'missing': []
        },
        'recommendations': []
    }

    # 1. 影響分析
    try:
        all_nodes = list_nodes(project_name)
        node_ids_affected = set()

        # 找出修改的檔案對應的 SSOT nodes
        for f in modified_files:
            for node in all_nodes:
                ref = node.get('ref', '')
                if ref and f in ref:
                    node_ids_affected.add(node['id'])

                    # 找出誰依賴這個 node
                    impact = get_impact(node['id'], project_name)
                    for i in impact:
                        node_ids_affected.add(i['id'])
                        result['impact_analysis']['affected_nodes'].append({
                            'id': i['id'],
                            'reason': f"depends on {node['id']} via {i.get('edge_kind', '?')}"
                        })

        # 檢查是否有 API 受影響
        result['impact_analysis']['api_affected'] = any(
            n['id'].startswith('api.') for n in result['impact_analysis']['affected_nodes']
        )

        # 檢查是否跨模組
        affected_domains = set()
        for node in all_nodes:
            if node['id'] in node_ids_affected and node['kind'] == 'domain':
                affected_domains.add(node['id'])
        result['impact_analysis']['cross_module_impact'] = len(affected_domains) > 1

    except Exception as e:
        result['recommendations'].append(f"Impact analysis failed: {str(e)}")

    # 2. SSOT 符合性
    try:
        if flow_id:
            # 檢查 flow 是否有 SSOT 定義
            flow_node = None
            for node in all_nodes:
                if node['id'] == flow_id:
                    flow_node = node
                    break

            if flow_node:
                result['ssot_compliance']['checks'].append({
                    'check': f"Flow '{flow_id}' defined in SSOT",
                    'status': 'pass'
                })
            else:
                result['ssot_compliance']['checks'].append({
                    'check': f"Flow '{flow_id}' defined in SSOT",
                    'status': 'fail',
                    'message': 'Flow not found in SSOT Index'
                })
                result['ssot_compliance']['status'] = 'warning'

            # 檢查 flow 的鄰居是否完整
            neighbors = get_neighbors(flow_id, project_name, depth=1)
            has_api = any(n['id'].startswith('api.') for n in neighbors)
            has_domain = any(n['id'].startswith('domain.') for n in neighbors)

            if not has_api:
                result['ssot_compliance']['checks'].append({
                    'check': f"Flow '{flow_id}' has implementing APIs",
                    'status': 'warning',
                    'message': 'No API implementations found'
                })

    except Exception as e:
        result['recommendations'].append(f"SSOT compliance check failed: {str(e)}")

    # 3. 測試覆蓋
    try:
        test_nodes = [n for n in all_nodes if n['kind'] == 'test']

        if flow_id:
            # 找出覆蓋這個 flow 的測試
            for test in test_nodes:
                neighbors = get_neighbors(test['id'], project_name, depth=1, direction='outgoing')
                for n in neighbors:
                    if n['id'] == flow_id and n.get('edge_kind') == 'covers':
                        result['test_coverage']['covered'].append({
                            'test': test['id'],
                            'covers': flow_id
                        })

            if not result['test_coverage']['covered']:
                result['test_coverage']['missing'].append({
                    'target': flow_id,
                    'type': 'flow',
                    'message': f"No tests found covering '{flow_id}'"
                })
                result['recommendations'].append(f"Add test coverage for flow '{flow_id}'")

    except Exception as e:
        result['recommendations'].append(f"Test coverage check failed: {str(e)}")

    # 4. 生成建議
    if result['impact_analysis']['api_affected']:
        result['recommendations'].append("⚠️ API affected - consider backward compatibility")

    if result['impact_analysis']['cross_module_impact']:
        result['recommendations'].append("⚠️ Cross-module impact - coordinate with other teams")

    if result['ssot_compliance']['status'] != 'ok':
        result['recommendations'].append("📝 Update SSOT Index to match implementation")

    return result


def format_validation_report(validation: Dict) -> str:
    """
    將驗證結果格式化為 Markdown 報告

    Args:
        validation: validate_with_graph() 的返回值

    Returns:
        格式化的 Markdown 字串
    """
    lines = []
    lines.append("# 🔍 Critic Validation Report")
    lines.append("")

    # 影響分析
    impact = validation.get('impact_analysis', {})
    lines.append("## Impact Analysis")
    lines.append(f"- API Affected: {'⚠️ Yes' if impact.get('api_affected') else '✅ No'}")
    lines.append(f"- Cross-Module: {'⚠️ Yes' if impact.get('cross_module_impact') else '✅ No'}")

    affected = impact.get('affected_nodes', [])
    if affected:
        lines.append(f"- Affected Nodes: {len(affected)}")
        for n in affected[:5]:
            lines.append(f"  - {n['id']}: {n.get('reason', '')}")
    lines.append("")

    # SSOT 符合性
    ssot = validation.get('ssot_compliance', {})
    status_emoji = {'ok': '✅', 'warning': '⚠️', 'violation': '❌'}.get(ssot.get('status', 'ok'), '?')
    lines.append(f"## SSOT Compliance: {status_emoji} {ssot.get('status', 'unknown').upper()}")
    for check in ssot.get('checks', []):
        check_emoji = {'pass': '✅', 'fail': '❌', 'warning': '⚠️'}.get(check.get('status', '?'), '?')
        lines.append(f"- {check_emoji} {check.get('check', '')}")
        if check.get('message'):
            lines.append(f"  {check['message']}")
    lines.append("")

    # 測試覆蓋
    tests = validation.get('test_coverage', {})
    lines.append("## Test Coverage")
    covered = tests.get('covered', [])
    missing = tests.get('missing', [])
    lines.append(f"- Covered: {len(covered)}")
    for c in covered:
        lines.append(f"  - ✅ {c['test']} covers {c['covers']}")
    lines.append(f"- Missing: {len(missing)}")
    for m in missing:
        lines.append(f"  - ❌ {m['message']}")
    lines.append("")

    # 建議
    recommendations = validation.get('recommendations', [])
    if recommendations:
        lines.append("## Recommendations")
        for r in recommendations:
            lines.append(f"- {r}")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# SSOT Graph 同步
# =============================================================================

def sync_ssot_graph(project_name: str = None) -> Dict:
    """
    同步 SSOT Index 到 project_nodes/project_edges

    從 PROJECT_INDEX.md 解析所有節點和關係，同步到 Graph。
    動態支援任何類型（不寫死在程式碼中）。

    Args:
        project_name: 專案名稱（預設使用當前目錄名）

    Returns:
        {
            'project_name': str,
            'nodes_added': int,
            'edges_added': int,
            'types_found': List[str],
            'total_nodes': int,
            'total_edges': int
        }
    """
    from servers.ssot import parse_index
    from servers.graph import sync_from_index, get_graph_stats

    project_name = project_name or os.path.basename(os.getcwd())

    # 解析 SSOT Index
    index_data = parse_index()

    if not index_data:
        return {
            'project_name': project_name,
            'nodes_added': 0,
            'edges_added': 0,
            'types_found': [],
            'total_nodes': 0,
            'total_edges': 0,
            'message': 'No SSOT Index found or empty'
        }

    # 同步到 Graph
    result = sync_from_index(project_name, index_data)

    # 取得最終統計
    stats = get_graph_stats(project_name)

    return {
        'project_name': project_name,
        'nodes_added': result['nodes_added'],
        'edges_added': result['edges_added'],
        'types_found': list(index_data.keys()),
        'total_nodes': stats['node_count'],
        'total_edges': stats['edge_count']
    }


# =============================================================================
# 便利函數
# =============================================================================

def quick_status() -> str:
    """快速狀態報告（供 CLI 使用）"""
    try:
        s = status()
        lines = [
            f"Project: {s['project_name']}",
            f"Health: {s['health']}",
            f"",
            f"Code Graph:",
            f"  Nodes: {s['code_graph']['node_count']}",
            f"  Edges: {s['code_graph']['edge_count']}",
            f"  Files: {s['code_graph']['file_count']}",
            f"",
            f"SSOT:",
            f"  Doctrine: {'✅' if s['ssot']['has_doctrine'] else '❌'}",
            f"  Index: {'✅' if s['ssot']['has_index'] else '❌'}",
            f"  Flows: {s['ssot']['flow_count']}",
            f"  Domains: {s['ssot']['domain_count']}",
        ]
        if s['messages']:
            lines.append("")
            lines.append("Messages:")
            for msg in s['messages']:
                lines.append(f"  ⚠️ {msg}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"
