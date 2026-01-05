#!/bin/bash
# Cortex Git Hooks Installer
#
# 安裝 Git hooks 到當前 repo，自動同步 Code Graph。
#
# 使用方式：
#   cd /path/to/your/project
#   ~/.claude/skills/cortex-agents/scripts/install-hooks.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NEUROMORPHIC_DIR="$(dirname "$SCRIPT_DIR")"

# 顏色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🧠 Cortex Git Hooks Installer"
echo "===================================="
echo

# 檢查是否在 Git repo 中
if [ ! -d ".git" ]; then
    echo -e "${RED}Error: Not in a Git repository.${NC}"
    echo "Please run this script from the root of your Git project."
    exit 1
fi

HOOKS_DIR=".git/hooks"
PROJECT_NAME=$(basename "$(pwd)")

echo "Project: $PROJECT_NAME"
echo "Hooks directory: $HOOKS_DIR"
echo

# 建立 post-merge hook
POST_MERGE="$HOOKS_DIR/post-merge"

if [ -f "$POST_MERGE" ]; then
    echo -e "${YELLOW}Warning: post-merge hook already exists.${NC}"
    read -p "Overwrite? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping post-merge hook."
    else
        create_post_merge=true
    fi
else
    create_post_merge=true
fi

if [ "$create_post_merge" = true ]; then
    cat > "$POST_MERGE" << 'EOF'
#!/bin/bash
# Cortex post-merge hook
# Auto-sync Code Graph after git pull/merge

echo "🔄 Syncing Code Graph..."

# 取得專案資訊
PROJECT_PATH="$(pwd)"
PROJECT_NAME="$(basename "$PROJECT_PATH")"

# 執行同步
python3 -c "
import sys
sys.path.insert(0, '$HOME/.claude/cortex-agents')
from servers.facade import sync
result = sync('$PROJECT_PATH', '$PROJECT_NAME')
print(f'  Files processed: {result[\"files_processed\"]}')
print(f'  Files skipped: {result[\"files_skipped\"]}')
print(f'  Nodes added: {result[\"nodes_added\"]}')
if result.get('errors'):
    print(f'  Errors: {result[\"errors\"]}')
" 2>/dev/null || echo "  (Cortex sync skipped - not configured)"

echo "✅ Code Graph sync complete"
EOF
    chmod +x "$POST_MERGE"
    echo -e "${GREEN}✅ Created post-merge hook${NC}"
fi

# 建立 post-checkout hook（切換分支時也同步）
POST_CHECKOUT="$HOOKS_DIR/post-checkout"

if [ -f "$POST_CHECKOUT" ]; then
    echo -e "${YELLOW}Warning: post-checkout hook already exists.${NC}"
    read -p "Overwrite? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping post-checkout hook."
    else
        create_post_checkout=true
    fi
else
    create_post_checkout=true
fi

if [ "$create_post_checkout" = true ]; then
    cat > "$POST_CHECKOUT" << 'EOF'
#!/bin/bash
# Cortex post-checkout hook
# Auto-sync Code Graph after git checkout

# 只在切換分支時觸發（不是檔案 checkout）
# $3 = 1 表示分支切換，0 表示檔案 checkout
if [ "$3" = "1" ]; then
    echo "🔄 Syncing Code Graph after branch switch..."

    PROJECT_PATH="$(pwd)"
    PROJECT_NAME="$(basename "$PROJECT_PATH")"

    python3 -c "
import sys
sys.path.insert(0, '$HOME/.claude/cortex-agents')
from servers.facade import sync
result = sync('$PROJECT_PATH', '$PROJECT_NAME')
print(f'  Files processed: {result[\"files_processed\"]}')
" 2>/dev/null || true

    echo "✅ Done"
fi
EOF
    chmod +x "$POST_CHECKOUT"
    echo -e "${GREEN}✅ Created post-checkout hook${NC}"
fi

echo
echo "===================================="
echo -e "${GREEN}Installation complete!${NC}"
echo
echo "Hooks will automatically sync Code Graph after:"
echo "  - git pull"
echo "  - git merge"
echo "  - git checkout (branch switch)"
echo
echo "To manually sync:"
echo "  python3 -c \"from servers.facade import sync; sync('$(pwd)', '$PROJECT_NAME')\""
