# OpenCode Playwright Browser Tool

A browser automation tool for the [OpenCode](https://opencode.ai) AI agent, providing browser control via [Playwright](https://playwright.dev/) (Python).

Lets the AI assistant interactively open a browser, navigate URLs, click elements, type text, take screenshots, execute JavaScript, and more — using the same Playwright engine trusted in industrial testing.

## Features

- Full automation of Chromium or Firefox
- Headless mode (no GUI) or visible browser window
- CSS and XPath selectors
- Screenshots (full page or individual elements)
- Tab management (open, switch)
- Execute arbitrary JavaScript on the page
- Extract content in text or HTML format

## Use Cases

| Use Case | Example |
|---|---|
| **Web scraping** | Extract data from JavaScript-rendered sites |
| **UI testing** | Automated form, button, and navigation checks |
| **Form filling** | Automatically fill in web page data |
| **Screenshot capture** | Visual layout checks, bug reports |
| **JS debugging** | Run JavaScript in page context |
| **Site exploration** | Navigate and analyze web application structure |

## Installation

```bash
git clone https://github.com/your-org/opencode_playwright_tool.git
cd opencode_playwright_tool
bash install.sh
```

The installer:
1. Detects the system Python
2. **Interactively** prompts you to choose a browser: Chromium or Firefox
3. Creates a virtual environment at `~/.config/opencode/tools/venv/`
4. Installs `playwright` and the selected browser
5. Copies the tool files to `~/.config/opencode/tools/`

All files are placed in `~/.config/opencode/tools/` and become available to OpenCode on the next launch.

## Uninstall

```bash
bash uninstall.sh
```

Removes all installed tool files and the virtual environment from `~/.config/opencode/tools/`.

## Available Tools (Commands)

All tools use the `browser_playwright_` prefix:

| Tool | Purpose |
|---|---|
| `browser_playwright_open` | Launch browser, returns `session_id` |
| `browser_playwright_close` | Close session and clean up resources |
| `browser_playwright_navigate` | Navigate to a URL |
| `browser_playwright_back` | Go back in history |
| `browser_playwright_forward` | Go forward in history |
| `browser_playwright_refresh` | Reload the page |
| `browser_playwright_click` | Click an element (CSS / XPath) |
| `browser_playwright_type` | Type text into an input field |
| `browser_playwright_select` | Select an option in a `<select>` element |
| `browser_playwright_submit` | Submit a form |
| `browser_playwright_scroll` | Scroll the page or to an element |
| `browser_playwright_press_key` | Press a keyboard key (Enter, Tab, Escape, ...) |
| `browser_playwright_get_content` | Get page/element text or HTML |
| `browser_playwright_get_url` | Get the current URL |
| `browser_playwright_get_title` | Get the page title |
| `browser_playwright_screenshot` | Take a screenshot (PNG) |
| `browser_playwright_execute_js` | Execute JavaScript on the page |
| `browser_playwright_wait` | Wait (ms) or wait for an element to appear |
| `browser_playwright_new_tab` | Open a new tab |
| `browser_playwright_switch_tab` | Switch tab by index |
| `browser_playwright_list` | List active sessions |

## Configuration

File `~/.config/opencode/tools/browser_playwright_config.json`:

```json
{
  "browser_type": "chromium",
  "headless": false,
  "screenshot_dir": ""
}
```

| Parameter | Description |
|---|---|
| `browser_type` | `"chromium"` or `"firefox"` |
| `headless` | No GUI (default `false`) |
| `screenshot_dir` | Screenshot save path (empty = temp) |

## Example Usage in OpenCode

```
> Open a browser and go to example.com

[AI calls browser_playwright_open → gets session_id]
[AI calls browser_playwright_navigate with url="https://example.com"]
→ Title: "Example Domain"

> Click the h1 heading

[AI calls browser_playwright_click with selector="h1"]
→ Clicked: h1

> Take a screenshot

[AI calls browser_playwright_screenshot]
→ /tmp/.../screenshot.png
```

## Architecture

- **TypeScript layer** (`browser_playwright.ts`) — OpenCode tool definitions, invokes the Python script via stdin
- **Python layer** (`browser_playwright.py`) — Daemon architecture: the parent process manages sessions; the child process launches a Playwright browser and listens on a TCP socket for commands

## Dependencies

- Python 3.8+
- Playwright for Python
- Chromium or Firefox (installed automatically by the installer)
