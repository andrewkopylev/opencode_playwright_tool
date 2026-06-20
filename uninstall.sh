#!/usr/bin/env bash
# =========================================================================
# uninstall.sh — Remove Playwright Browser Tool from ~/.config/opencode/tools/
# =========================================================================

OPENCODE_DIR="${HOME}/.config/opencode"
TOOLS_DIR="${OPENCODE_DIR}/tools"
VENV_DIR="${TOOLS_DIR}/venv"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()  { echo -e "${RED}[ERR]${NC}   $*"; }

FILES_TO_REMOVE=(
    "$TOOLS_DIR/browser_playwright.py"
    "$TOOLS_DIR/browser_playwright.ts"
    "$TOOLS_DIR/browser_playwright_config.json"
    "$VENV_DIR"
)

echo ""
echo "============================================"
echo "  OpenCode Playwright Browser Tool Uninstall"
echo "============================================"
echo ""

REMOVED=0
SKIPPED=0

for target in "${FILES_TO_REMOVE[@]}"; do
    if [ -e "$target" ] || [ -L "$target" ]; then
        rm -rf "$target"
        log "Removed: $target"
        ((REMOVED++))
    else
        warn "Not found (skip): $target"
        ((SKIPPED++))
    fi
done

echo ""
if [ "$REMOVED" -gt 0 ]; then
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  ✅  Done. Removed $REMOVED item(s), skipped $SKIPPED.${NC}"
    echo -e "${GREEN}============================================${NC}"
else
    echo -e "${YELLOW}  Nothing to remove.${NC}"
fi
