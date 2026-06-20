#!/usr/bin/env python3
"""Tests for the Playwright browser tool — tests all operations end-to-end."""

import json
import os
import subprocess
import socket
import sys
import time
import tempfile
from pathlib import Path

# Add the project dir to sys.path so we can import the script
PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

# Patch CONFIG_FILE / SESSION_FILE so tests don't interfere with real data
import importlib
import browser_playwright as bp

# Use temp dirs for tests
TEST_DIR = Path(tempfile.mkdtemp(prefix="opencode_pw_test_"))
bp.SESSION_FILE = TEST_DIR / "sessions.json"
bp.CONFIG_FILE = TEST_DIR / "browser_playwright_config.json"
bp.DEFAULT_CONFIG["screenshot_dir"] = str(TEST_DIR / "screenshots")

# Ensure config file exists with test settings
bp.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
bp.CONFIG_FILE.write_text(json.dumps({
    "browser_type": "chromium",
    "headless": True,
    "screenshot_dir": str(TEST_DIR / "screenshots"),
}))

TEST_URL = "https://example.com"
PASSED = 0
FAILED = 0


def check(description, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  ✅ {description}")
    else:
        FAILED += 1
        print(f"  ❌ {description} — {detail}")


def start_daemon():
    """Start a daemon on a free port, return (proc, cmd_port)."""
    port = bp.get_next_port({})
    env = os.environ.copy()
    env["HEADLESS"] = "true"
    env["BROWSER_TYPE"] = "chromium"
    env["SCREENSHOT_DIR"] = str(TEST_DIR / "screenshots")
    proc = subprocess.Popen(
        [sys.executable, str(PROJECT_DIR / "browser_playwright.py"), "--daemon", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    out = proc.stdout.readline().decode().strip()
    result = json.loads(out)
    assert result.get("ok"), f"Daemon start failed: {result}"
    return proc, result["cmd_port"]


def stop_daemon(proc, cmd_port):
    """Send quit and wait for daemon."""
    try:
        bp.send_to_daemon(cmd_port, {"command": "quit"})
    except Exception:
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def send(cmd_port, payload):
    return bp.send_to_daemon(cmd_port, payload)


# =============================================================================
print("=" * 60)
print("Playwright Browser Tool Tests")
print(f"Test dir: {TEST_DIR}")
print("=" * 60)

# --- Test 1: Open session ---
print("\n📋 Test: Open browser session")
try:
    proc, cmd_port = start_daemon()

    cfg = bp.load_config()
    result = json.loads(bp.cmd_open(cfg, {"headless": True}))
    data = result.get("data", {})
    session_id = data.get("session_id", "")
    check("open returns session_id", bool(session_id), str(result))
    check("open returns ok", result.get("ok", False))
except Exception as e:
    check("open session", False, str(e))
    proc = None

if proc is None:
    print("\n❌ Cannot continue — daemon failed to start")
    sys.exit(1)

# --- Test 2: Navigate ---
print("\n📋 Test: Navigate")
try:
    r = send(cmd_port, {"command": "navigate", "url": TEST_URL})
    check("navigate ok", r.get("ok"), r)
    check("navigate title contains Example", "Example" in str(r.get("data", "")), r.get("data"))
except Exception as e:
    check("navigate", False, str(e))

# --- Test 3: Get title ---
print("\n📋 Test: Get title")
try:
    r = send(cmd_port, {"command": "get_title"})
    check("get_title ok", r.get("ok"), r)
    check("title is Example Domain", "Example Domain" in str(r.get("data", "")), r.get("data"))
except Exception as e:
    check("get_title", False, str(e))

# --- Test 4: Get URL ---
print("\n📋 Test: Get URL")
try:
    r = send(cmd_port, {"command": "get_url"})
    check("get_url ok", r.get("ok"), r)
    check("url is example.com", "example.com" in str(r.get("data", "")), r.get("data"))
except Exception as e:
    check("get_url", False, str(e))

# --- Test 5: Get content ---
print("\n📋 Test: Get content (text)")
try:
    r = send(cmd_port, {"command": "get_content", "format": "text", "limit_chars": 500})
    check("get_content ok", r.get("ok"), r)
    check("content not empty", len(str(r.get("data", ""))) > 10)
except Exception as e:
    check("get_content text", False, str(e))

print("\n📋 Test: Get content (html)")
try:
    r = send(cmd_port, {"command": "get_content", "format": "html", "limit_chars": 500})
    check("get_content html ok", r.get("ok"), r)
    check("html contains tags", "<" in str(r.get("data", "")))
except Exception as e:
    check("get_content html", False, str(e))

# --- Test 6: Execute JS ---
print("\n📋 Test: Execute JS")
try:
    r = send(cmd_port, {"command": "execute_js", "code": "return document.title"})
    check("execute_js ok", r.get("ok"), r)
    check("js returns title", "Example Domain" in str(r.get("data", "")), r.get("data"))
except Exception as e:
    check("execute_js", False, str(e))

# --- Test 7: Wait ---
print("\n📋 Test: Wait")
try:
    r = send(cmd_port, {"command": "wait", "timeout_ms": 500})
    check("wait ok", r.get("ok"), r)
except Exception as e:
    check("wait", False, str(e))

print("\n📋 Test: Wait for selector")
try:
    r = send(cmd_port, {"command": "wait", "selector": "h1", "timeout_ms": 5000})
    check("wait for h1 ok", r.get("ok"), r)
except Exception as e:
    check("wait for selector", False, str(e))

# --- Test 8: Scroll ---
print("\n📋 Test: Scroll down")
try:
    r = send(cmd_port, {"command": "scroll", "direction": "down", "amount": 100})
    check("scroll down ok", r.get("ok"), r)
except Exception as e:
    check("scroll down", False, str(e))

print("\n📋 Test: Scroll to element")
try:
    r = send(cmd_port, {"command": "scroll", "selector": "h1"})
    check("scroll to h1 ok", r.get("ok"), r)
except Exception as e:
    check("scroll to element", False, str(e))

# --- Test 9: Screenshot ---
print("\n📋 Test: Screenshot")
try:
    r = send(cmd_port, {"command": "screenshot", "session_id": session_id})
    check("screenshot ok", r.get("ok"), r)
    path_str = r.get("data", "")
    check("screenshot file exists", os.path.isfile(path_str), path_str)
except Exception as e:
    check("screenshot", False, str(e))

# --- Test 10: Click (on h1) — before any navigation tests ---
print("\n📋 Test: Click")
try:
    r = send(cmd_port, {"command": "click", "selector": "h1", "timeout_ms": 5000})
    check("click h1 ok", r.get("ok"), r)
except Exception as e:
    check("click", False, str(e))

# --- Test 11: Press key ---
print("\n📋 Test: Press key")
try:
    r = send(cmd_port, {"command": "press_key", "key": "TAB"})
    check("press_key TAB ok", r.get("ok"), r)
except Exception as e:
    check("press_key", False, str(e))

# --- Test 12: New tab ---
print("\n📋 Test: New tab")
try:
    r = send(cmd_port, {"command": "new_tab", "url": "about:blank"})
    check("new_tab ok", r.get("ok"), r)
except Exception as e:
    check("new_tab", False, str(e))

# --- Test 13: Switch tab ---
print("\n📋 Test: Switch tab")
try:
    r = send(cmd_port, {"command": "switch_tab", "index": 0})
    check("switch_tab ok", r.get("ok"), r)
except Exception as e:
    check("switch_tab", False, str(e))

# --- Test 14: Refresh ---
print("\n📋 Test: Refresh")
try:
    r = send(cmd_port, {"command": "refresh"})
    check("refresh ok", r.get("ok"), r)
except Exception as e:
    check("refresh", False, str(e))

# --- Test 15: Back ---
print("\n📋 Test: Back")
try:
    r = send(cmd_port, {"command": "back"})
    check("back ok", r.get("ok"), r)
except Exception as e:
    check("back", False, str(e))

# --- Test 16: Close via client command ---
print("\n📋 Test: Close session")
stop_daemon(proc, cmd_port)
result = json.loads(bp.cmd_close(cfg, {"session_id": session_id}))
check("close returns ok", result.get("ok"), str(result))
check("close returns message", "Browser closed" in str(result.get("data", "")), str(result))

# --- Test 17: List (should be empty) ---
print("\n📋 Test: List sessions")
sessions_result = bp.cmd_list(cfg, {})
check("list shows no sessions", "No active sessions" == sessions_result, sessions_result)

# --- Cleanup ---
import shutil
shutil.rmtree(TEST_DIR, ignore_errors=True)

# =============================================================================
print("\n" + "=" * 60)
total = PASSED + FAILED
print(f"Results: {PASSED}/{total} passed, {FAILED}/{total} failed")
print("=" * 60)

if FAILED > 0:
    sys.exit(1)
