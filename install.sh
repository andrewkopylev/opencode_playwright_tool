#!/usr/bin/env bash
set -euo pipefail

# =========================================================================
# install.sh — Playwright Browser Tool installer for OpenCode
# Installs browser_playwright.py / browser_playwright.ts into
# ~/.config/opencode/tools/ with a dedicated venv.
# =========================================================================

OPENCODE_DIR="${HOME}/.config/opencode"
TOOLS_DIR="${OPENCODE_DIR}/tools"
VENV_DIR="${TOOLS_DIR}/venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()  { echo -e "${RED}[ERR]${NC}   $*"; }
info() { echo -e "${CYAN}[Q]${NC}    $*"; }

# -------------------------------------------------------------------
# Detect existing python3
# -------------------------------------------------------------------
find_system_python() {
    for py in python3 python; do
        if command -v "$py" &>/dev/null; then
            echo "$py"
            return
        fi
    done
    err "No python3 found on the system. Install python3 first."
    exit 1
}

# -------------------------------------------------------------------
# Ensure python3-venv is available (required for creating venv)
# -------------------------------------------------------------------
ensure_venv_module() {
    local py="$1"

    if "$py" -c "import ensurepip" 2>/dev/null; then
        return 0
    fi

    local py_version
    py_version="$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "")"

    warn "python3-venv (ensurepip) not installed."

    if command -v apt-get &>/dev/null; then
        log "Installing python${py_version}-venv via apt-get (may require sudo password)..."
        sudo -S apt-get update -qq
        sudo -S apt-get install -y -qq "python${py_version}-venv" python3-venv
    elif command -v dnf &>/dev/null; then
        log "Installing python${py_version}-venv via dnf..."
        sudo -S dnf install -y "python${py_version}-venv"
    elif command -v yum &>/dev/null; then
        log "Installing python${py_version}-venv via yum..."
        sudo -S yum install -y "python${py_version}-venv"
    elif command -v pacman &>/dev/null; then
        log "Installing python via pacman..."
        sudo -S pacman -S --noconfirm python
    else
        err "Cannot install python3-venv automatically — unknown package manager."
        err "Please install python3-venv manually and re-run this script."
        exit 1
    fi

    if ! "$py" -c "import ensurepip" 2>/dev/null; then
        err "python3-venv installation failed."
        exit 1
    fi
    log "python3-venv installed."
}

# -------------------------------------------------------------------
# Choose browser (interactive only)
# -------------------------------------------------------------------
choose_browser() {
    echo "" >&2
    echo -e "${YELLOW}═══════════════════════════════════════════${NC}" >&2
    echo -e "${YELLOW}  Choose browser for Playwright automation:${NC}" >&2
    echo -e "  ${GREEN}1${NC}) Chromium (Chrome) — recommended" >&2
    echo -e "  ${GREEN}2${NC}) Firefox" >&2
    echo -e "${YELLOW}═══════════════════════════════════════════${NC}" >&2
    echo "" >&2
    while true; do
        read -r -p "  Chromium or Firefox? [1/2, default=1]: " choice
        choice="${choice:-1}"
        case "$choice" in
            1) echo "chromium" ; return ;;
            2) echo "firefox" ; return ;;
            *) echo -e "  ${RED}Please enter 1 or 2${NC}" >&2 ;;
        esac
    done
}

# -------------------------------------------------------------------
# Check if playright is usable in a given python
# -------------------------------------------------------------------
check_playwright_python() {
    local py="$1"
    "$py" -c "from playwright.sync_api import sync_playwright" 2>/dev/null
}

# -------------------------------------------------------------------
# Check if browser is installed
# -------------------------------------------------------------------
check_playwright_browser() {
    local py="$1"
    local browser_type="$2"
    "$py" -m playwright install --dry-run "$browser_type" &>/dev/null && return 0 || return 1
}

# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------
main() {
    echo ""
    echo "============================================"
    echo "  OpenCode Playwright Browser Tool Installer"
    echo "============================================"
    echo ""

    log "Detecting system python..."
    SYSTEM_PYTHON="$(find_system_python)"
    log "System python: $SYSTEM_PYTHON"

    BROWSER_TYPE="$(choose_browser)"
    log "Selected browser: $BROWSER_TYPE"

    mkdir -p "$TOOLS_DIR"

    # --- Decide whether we need a venv ---
    NEED_VENV=false

    if check_playwright_python "$SYSTEM_PYTHON"; then
        log "playwright library found in system python."
        VENV_PYTHON="$SYSTEM_PYTHON"
    else
        NEED_VENV=true
        warn "playwright not installed in system python."
    fi

    if [ "$NEED_VENV" = false ]; then
        if check_playwright_browser "$SYSTEM_PYTHON" "$BROWSER_TYPE"; then
            log "Browser '$BROWSER_TYPE' found."
        else
            NEED_VENV=true
            warn "Browser '$BROWSER_TYPE' not installed in system python."
        fi
    fi

    # --- Create venv if needed ---
    if [ "$NEED_VENV" = true ]; then
        log "Creating venv at: $VENV_DIR"

        # Try normal venv first
        if "$SYSTEM_PYTHON" -c "import ensurepip" 2>/dev/null; then
            "$SYSTEM_PYTHON" -m venv "$VENV_DIR"
        elif "$SYSTEM_PYTHON" -m venv --without-pip "$VENV_DIR" 2>/dev/null; then
            # If ensurepip missing, try without-pip + bootstrap via get-pip.py
            log "ensurepip not available — bootstrapping pip via get-pip.py..."
            local GET_PIP
            GET_PIP="$(mktemp /tmp/get-pip.XXXXXX.py)"
            if curl -fsSL --retry 3 https://bootstrap.pypa.io/get-pip.py -o "$GET_PIP"; then
                "$VENV_DIR/bin/python3" "$GET_PIP" --no-setuptools --no-wheel -q
                rm -f "$GET_PIP"
            else
                rm -f "$GET_PIP"
                warn "Cannot download get-pip.py. Trying system package..."
                ensure_venv_module "$SYSTEM_PYTHON"
                rm -rf "$VENV_DIR"
                "$SYSTEM_PYTHON" -m venv "$VENV_DIR"
            fi
        else
            warn "venv creation failed outright. Trying system package..."
            ensure_venv_module "$SYSTEM_PYTHON"
            rm -rf "$VENV_DIR"
            "$SYSTEM_PYTHON" -m venv "$VENV_DIR"
        fi

        if [ -f "$VENV_DIR/bin/python3" ]; then
            VENV_PYTHON="$VENV_DIR/bin/python3"
        elif [ -f "$VENV_DIR/bin/python" ]; then
            VENV_PYTHON="$VENV_DIR/bin/python"
        else
            err "Venv created but python not found inside it."
            exit 1
        fi

        log "Upgrading pip..."
        "$VENV_PYTHON" -m pip install --upgrade pip -q

        log "Installing playwright..."
        "$VENV_PYTHON" -m pip install playwright -q

        log "Installing browser '$BROWSER_TYPE'..."
        "$VENV_PYTHON" -m playwright install "$BROWSER_TYPE"
    fi

    # --- Verify installation ---
    log "Verifying installation..."
    if ! check_playwright_python "$VENV_PYTHON"; then
        err "Playwright verification failed."
        exit 1
    fi
    log "Playwright library: OK"

    if ! check_playwright_browser "$VENV_PYTHON" "$BROWSER_TYPE"; then
        err "Browser '$BROWSER_TYPE' verification failed."
        exit 1
    fi
    log "Browser '$BROWSER_TYPE': OK"

    # --- Copy tool files ---
    log "Copying tool files to $TOOLS_DIR ..."
    cp -v "$SCRIPT_DIR/browser_playwright.py" "$TOOLS_DIR/browser_playwright.py"
    cp -v "$SCRIPT_DIR/browser_playwright.ts" "$TOOLS_DIR/browser_playwright.ts"

    # --- Write config ---
    log "Writing config..."
    cat > "$TOOLS_DIR/browser_playwright_config.json" <<EOF
{
  "browser_type": "$BROWSER_TYPE",
  "headless": false,
  "screenshot_dir": ""
}
EOF
    log "Config written to $TOOLS_DIR/browser_playwright_config.json"
    log "Venv python: $VENV_PYTHON"

    echo ""
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  ✅  INSTALLATION COMPLETE!${NC}"
    echo ""
    echo -e "  ${GREEN}Available tools:${NC}"
    echo "    browser_playwright_open         — Launch browser, returns session_id"
    echo "    browser_playwright_close        — Close session & cleanup"
    echo "    browser_playwright_navigate     — Go to URL"
    echo "    browser_playwright_back         — Go back in history"
    echo "    browser_playwright_forward      — Go forward in history"
    echo "    browser_playwright_refresh      — Reload page"
    echo "    browser_playwright_click        — Click element (CSS/XPath)"
    echo "    browser_playwright_type         — Type text into input"
    echo "    browser_playwright_select       — Select dropdown option"
    echo "    browser_playwright_submit       — Submit form"
    echo "    browser_playwright_scroll       — Scroll page / to element"
    echo "    browser_playwright_press_key    — Press keyboard key"
    echo "    browser_playwright_get_content  — Get page text or HTML"
    echo "    browser_playwright_get_url      — Get current URL"
    echo "    browser_playwright_get_title    — Get page title"
    echo "    browser_playwright_screenshot   — Take screenshot (PNG)"
    echo "    browser_playwright_execute_js   — Run JavaScript in page"
    echo "    browser_playwright_wait         — Wait ms or for element"
    echo "    browser_playwright_new_tab      — Open new tab"
    echo "    browser_playwright_switch_tab   — Switch tab by index"
    echo "    browser_playwright_list         — List active sessions"
    echo ""
    echo -e "  ${GREEN}Config:${NC} $TOOLS_DIR/browser_playwright_config.json"
    echo -e "${GREEN}============================================${NC}"
}

main "$@"
