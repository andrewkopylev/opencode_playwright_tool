#!/usr/bin/env python3
"""Browser automation tool for OpenCode — Playwright-based daemon architecture."""

import sys
import json
import os
import time
import socket
import subprocess
import uuid
import tempfile
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError as e:
    print(json.dumps({"ok": False, "error": f"Playwright not installed: {e}. Run install.sh first."}))
    sys.exit(1)

SESSION_FILE = Path(tempfile.gettempdir()) / "opencode_browser_pw" / "sessions.json"
BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "browser_playwright_config.json"

DEFAULT_CONFIG = {
    "browser_type": "chromium",
    "headless": False,
    "screenshot_dir": str(Path(tempfile.gettempdir()) / "opencode_browser_pw" / "screenshots"),
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text()))
        except (json.JSONDecodeError, IOError):
            pass
    return cfg


def load_sessions():
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_sessions(sessions):
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(sessions, indent=2))


def get_next_port(sessions, start=9515):
    used_ports = {int(s["port"]) for s in sessions.values()}
    port = start
    while port in used_ports or not _port_free(port):
        port += 1
    return port


def _port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        s.close()
        return True
    except OSError:
        return False


def _find_element(page, selector, selector_type="css"):
    """Return a Playwright Locator for the given selector."""
    if selector_type == "xpath":
        return page.locator(f"xpath={selector}")
    else:
        return page.locator(selector)


def _ok(data):
    return json.dumps({"ok": True, "data": str(data) if not isinstance(data, dict) else data})


def _err(msg):
    return json.dumps({"ok": False, "error": str(msg)})


def handle_command(cfg, page, cmd):
    c = cmd.get("command", "")
    try:
        if c == "navigate":
            page.goto(cmd["url"], wait_until="domcontentloaded", timeout=30000)
            return _ok(page.title())
        elif c == "back":
            page.go_back(wait_until="domcontentloaded", timeout=10000)
            return _ok(page.title())
        elif c == "forward":
            page.go_forward(wait_until="domcontentloaded", timeout=10000)
            return _ok(page.title())
        elif c == "refresh":
            page.reload(wait_until="domcontentloaded", timeout=10000)
            return _ok("Refreshed")
        elif c == "click":
            sel = cmd.get("selector", "")
            sel_type = cmd.get("selector_type", "css")
            timeout = cmd.get("timeout_ms", 5000)
            loc = _find_element(page, sel, sel_type)
            loc.wait_for(state="visible", timeout=timeout)
            loc.click(timeout=timeout)
            return _ok(f"Clicked: {sel}")
        elif c == "type":
            sel = cmd["selector"]
            text = cmd["text"]
            sel_type = cmd.get("selector_type", "css")
            loc = _find_element(page, sel, sel_type)
            if cmd.get("clear_first", True):
                loc.fill("", timeout=5000)
            loc.fill(text, timeout=5000)
            return _ok(f"Typed into: {sel}")
        elif c == "select":
            sel = cmd["selector"]
            sel_type = cmd.get("selector_type", "css")
            loc = _find_element(page, sel, sel_type)
            label = cmd.get("label", "")
            value = cmd.get("value", "")
            if label:
                loc.select_option(label=label, timeout=5000)
            elif value:
                loc.select_option(value=value, timeout=5000)
            return _ok(f"Selected in: {sel}")
        elif c == "submit":
            sel = cmd.get("selector", "")
            if sel:
                sel_type = cmd.get("selector_type", "css")
                loc = _find_element(page, sel, sel_type)
                loc.press("Enter")
            else:
                page.keyboard.press("Enter")
            return _ok("Submitted")
        elif c == "scroll":
            sel = cmd.get("selector", "")
            if sel:
                sel_type = cmd.get("selector_type", "css")
                loc = _find_element(page, sel, sel_type)
                loc.scroll_into_view_if_needed(timeout=5000)
                return _ok(f"Scrolled to: {sel}")
            direction = cmd.get("direction", "down")
            amount = cmd.get("amount", 300)
            if direction == "down":
                page.evaluate(f"window.scrollBy(0, {amount})")
            elif direction == "up":
                page.evaluate(f"window.scrollBy(0, -{amount})")
            elif direction == "top":
                page.evaluate("window.scrollTo(0, 0)")
            elif direction == "bottom":
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            return _ok(f"Scrolled {direction}")
        elif c == "press_key":
            key = cmd["key"].upper()
            # Map common key names to Playwright format
            pw_key_map = {
                "TAB": "Tab",
                "ENTER": "Enter",
                "BACKSPACE": "Backspace",
                "DELETE": "Delete",
                "ESCAPE": "Escape",
                "ESC": "Escape",
                "HOME": "Home",
                "END": "End",
                "SPACE": " ",
                "ARROW_UP": "ArrowUp", "ARROW_DOWN": "ArrowDown",
                "ARROW_LEFT": "ArrowLeft", "ARROW_RIGHT": "ArrowRight",
                "PAGE_UP": "PageUp", "PAGE_DOWN": "PageDown",
            }
            key_name = pw_key_map.get(key, key)
            sel = cmd.get("selector", "")
            if sel:
                sel_type = cmd.get("selector_type", "css")
                loc = _find_element(page, sel, sel_type)
                loc.press(key_name, timeout=5000)
            else:
                page.keyboard.press(key_name)
            return _ok(f"Pressed: {key}")
        elif c == "get_content":
            sel = cmd.get("selector", "")
            fmt = cmd.get("format", "text")
            limit = cmd.get("limit_chars", 0)
            if sel:
                sel_type = cmd.get("selector_type", "css")
                loc = _find_element(page, sel, sel_type)
                content = loc.inner_html(timeout=5000) if fmt == "html" else loc.inner_text(timeout=5000)
            else:
                content = page.content() if fmt == "html" else page.locator("body").inner_text(timeout=5000)
            if limit and len(content) > limit:
                content = content[:limit] + f"\n... [truncated, total {len(content)} chars]"
            return _ok(content)
        elif c == "get_url":
            return _ok(page.url)
        elif c == "get_title":
            return _ok(page.title())
        elif c == "screenshot":
            sel = cmd.get("selector", "")
            sd = Path(cfg.get("screenshot_dir", DEFAULT_CONFIG["screenshot_dir"]))
            sd.mkdir(parents=True, exist_ok=True)
            filename = f"{cmd.get('session_id','')}_{int(time.time())}.png"
            fp = sd / filename
            if sel:
                sel_type = cmd.get("selector_type", "css")
                loc = _find_element(page, sel, sel_type)
                loc.screenshot(path=str(fp), timeout=5000)
            else:
                page.screenshot(path=str(fp))
            return _ok(str(fp))
        elif c == "execute_js":
            code = cmd["code"]
            # Strip 'return ' / 'return;' prefix — Playwright evaluate wraps in a function
            if code.strip().startswith("return "):
                code = code.strip()[7:]
            elif code.strip().startswith("return;"):
                code = code.strip()[7:]
            result = page.evaluate(code)
            return _ok(json.dumps(result, default=str))
        elif c == "wait":
            sel = cmd.get("selector", "")
            timeout = cmd.get("timeout_ms", 5000)
            if sel:
                sel_type = cmd.get("selector_type", "css")
                loc = _find_element(page, sel, sel_type)
                try:
                    loc.wait_for(state="visible", timeout=timeout)
                    return _ok(f"Element found: {sel}")
                except Exception as e:
                    return _err(f"Timeout waiting for: {sel}: {e}")
            else:
                page.wait_for_timeout(timeout)
                return _ok(f"Waited {cmd.get('timeout_ms', 5000)}ms")
        elif c == "new_tab":
            url = cmd.get("url", "about:blank")
            ctx = page.context
            new_page = ctx.new_page()
            if url and url != "about:blank":
                new_page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(0.3)
            pages = ctx.pages
            return _ok(f"New tab, {len(pages)} total, current: {new_page.title()}")
        elif c == "switch_tab":
            idx = cmd.get("index", 0)
            ctx = page.context
            pages = ctx.pages
            if 0 <= idx < len(pages):
                target = pages[idx]
                target.bring_to_front()
                return _ok(f"Tab {idx}: {target.title()}")
            return _err(f"Invalid tab {idx}, have {len(pages)}")
        elif c == "quit":
            return _ok("bye")
        else:
            return _err(f"Unknown command: {c}")
    except Exception as e:
        msg = str(e)
        if not msg:
            msg = repr(e)
        return _err(msg)


def run_daemon(cfg, port):
    cmd_port = get_next_port({}, port + 1)
    headless = cfg.get("headless", False)
    browser_type = cfg.get("browser_type", "chromium")

    try:
        pw = sync_playwright().start()
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Failed to start Playwright: {e}"}))
        sys.exit(1)

    browser = None
    page = None
    try:
        if browser_type == "firefox":
            browser = pw.firefox.launch(headless=headless)
        elif browser_type == "webkit":
            browser = pw.webkit.launch(headless=headless)
        else:
            browser = pw.chromium.launch(
                headless=headless,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                      "--window-size=1280,900"],
            )
        ctx = browser.new_context()
        page = ctx.new_page()
    except Exception as e:
        pw.stop()
        print(json.dumps({"ok": False, "error": f"Failed to launch browser: {e}"}))
        sys.exit(1)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", cmd_port))
    server.listen(1)
    server.settimeout(300)

    print(json.dumps({"ok": True, "cmd_port": cmd_port, "browser_pid": 0}))
    sys.stdout.flush()

    try:
        while True:
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            try:
                data = b""
                while True:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    data += chunk
                    if len(data) > 10 * 1024 * 1024:
                        break
                    try:
                        json.loads(data.decode())
                        break
                    except json.JSONDecodeError:
                        continue
                cmd = json.loads(data.decode())

                c = cmd.get("command", "")
                if c in ("new_tab", "switch_tab"):
                    result = handle_command(cfg, page, cmd)
                    resp = json.loads(result)
                    if resp.get("ok"):
                        ctx = browser.contexts[0] if browser.contexts else None
                        if ctx and ctx.pages:
                            # Find the front-most page after the operation
                            for p in ctx.pages:
                                try:
                                    page = p
                                    _ = p.url  # quick access check
                                except Exception:
                                    continue
                            page = ctx.pages[-1]
                    conn.sendall(result.encode())
                elif c == "quit":
                    conn.sendall(json.dumps({"ok": True, "data": "bye"}).encode())
                    conn.close()
                    break
                else:
                    result = handle_command(cfg, page, cmd)
                    conn.sendall(result.encode())
            except Exception as e:
                try:
                    conn.sendall(json.dumps({"ok": False, "error": str(e)}).encode())
                except Exception:
                    pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
    finally:
        try:
            page.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass
        try:
            pw.stop()
        except Exception:
            pass
        try:
            server.close()
        except Exception:
            pass


def send_to_daemon(cmd_port, payload):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(15)
    sock.connect(("127.0.0.1", cmd_port))
    sock.sendall(json.dumps(payload).encode())
    sock.shutdown(socket.SHUT_WR)
    data = b""
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break
        data += chunk
    sock.close()
    return json.loads(data.decode())


def cmd_open(cfg, args):
    sessions = load_sessions()
    port = get_next_port(sessions)

    headless = args.get("headless", cfg.get("headless", False))
    run_cfg = dict(cfg)
    run_cfg["headless"] = headless

    env = os.environ.copy()
    env["BROWSER_TYPE"] = run_cfg.get("browser_type", "chromium")
    env["HEADLESS"] = "true" if headless else "false"
    env["SCREENSHOT_DIR"] = run_cfg.get("screenshot_dir", DEFAULT_CONFIG["screenshot_dir"])

    proc = subprocess.Popen(
        [sys.executable, __file__, "--daemon", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    out = proc.stdout.readline().decode().strip()
    if not out:
        err = proc.stderr.read().decode().strip()
        try:
            proc.kill()
        except Exception:
            pass
        return json.dumps({"ok": False, "error": f"Daemon start failed (stderr): {err}"})
    try:
        result = json.loads(out)
    except json.JSONDecodeError:
        return json.dumps({"ok": False, "error": f"Daemon output not JSON: {out}"})
    if not result.get("ok"):
        return json.dumps({"ok": False, "error": result.get("error", "Daemon start failed")})

    sid = uuid.uuid4().hex[:8]
    sessions[sid] = {
        "port": port,
        "cmd_port": result["cmd_port"],
        "browser_pid": result.get("browser_pid", 0),
        "daemon_pid": proc.pid,
    }
    save_sessions(sessions)
    return json.dumps({"ok": True, "data": {"session_id": sid, "headless": headless}})


def cmd_close(cfg, args):
    sid = args["session_id"]
    sessions = load_sessions()
    session = sessions.pop(sid, None)
    save_sessions(sessions)
    if not session:
        return json.dumps({"ok": False, "error": "Session not found"})
    try:
        send_to_daemon(session["cmd_port"], {"command": "quit"})
    except Exception:
        pass
    return json.dumps({"ok": True, "data": "Browser closed"})


def cmd_proxy(cfg, args):
    sid = args["session_id"]
    sessions = load_sessions()
    session = sessions.get(sid)
    if not session:
        return _err("Session not found")
    result = send_to_daemon(session["cmd_port"], args)
    if result.get("ok"):
        return result.get("data", "ok")
    return f"Error: {result.get('error', 'unknown')}"


def cmd_list(cfg, args):
    sessions = load_sessions()
    if not sessions:
        return "No active sessions"
    lines = []
    for sid, s in sessions.items():
        try:
            r = send_to_daemon(s["cmd_port"], {"command": "get_url"})
            url = r.get("data", "?") if r.get("ok") else "?"
            r2 = send_to_daemon(s["cmd_port"], {"command": "get_title"})
            title = r2.get("data", "?") if r2.get("ok") else "?"
            lines.append(f"{sid}: {title} — {url}")
        except Exception:
            lines.append(f"{sid}: (disconnected)")
    return "\n".join(lines)


CLIENT_COMMANDS = {
    "open": cmd_open,
    "close": cmd_close,
    "list": cmd_list,
}

PROXY_COMMANDS = {
    "navigate", "back", "forward", "refresh", "click", "type", "select",
    "submit", "scroll", "press_key", "get_content", "get_url", "get_title",
    "screenshot", "execute_js", "wait", "new_tab", "switch_tab",
}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        port = int(sys.argv[2])
        cfg = load_config()
        cfg["headless"] = os.environ.get("HEADLESS", "false").lower() == "true"
        cfg["browser_type"] = os.environ.get("BROWSER_TYPE", cfg.get("browser_type", "chromium"))
        cfg["screenshot_dir"] = os.environ.get("SCREENSHOT_DIR", cfg.get("screenshot_dir", DEFAULT_CONFIG["screenshot_dir"]))
        run_daemon(cfg, port)
        return

    try:
        raw = sys.stdin.read().strip()
        if not raw:
            print("Error: no input")
            sys.exit(1)
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}")
        sys.exit(1)

    cmd = payload.get("command", "")
    cfg = load_config()
    try:
        if cmd in CLIENT_COMMANDS:
            result = CLIENT_COMMANDS[cmd](cfg, payload)
            print(result)
        elif cmd in PROXY_COMMANDS:
            result = cmd_proxy(cfg, payload)
            print(result)
        else:
            print(f"Error: unknown command '{cmd}'")
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
