---
description: Launch the PetMedBot Streamlit app and drive it in a headless browser to verify UI/behavior changes (chat flow, emergency alert, image upload). Use this instead of rediscovering the launch/driver steps.
---

# Running and verifying PetMedBot

This is a Streamlit app (`main.py`). "Running" it means starting the
dev server and driving it in a real browser — not just importing
functions.

## Launch

The project venv already has everything installed (streamlit,
google-generativeai, pillow, python-dotenv, playwright).

```bash
cd d:/Users/askar/PycharmProjects/petmedbot
nohup venv/Scripts/streamlit.exe run main.py --server.headless true --server.port 8510 > /tmp/streamlit.log 2>&1 &
echo $! > /tmp/streamlit.pid
timeout 30 bash -c 'until curl -sf http://localhost:8510 >/dev/null; do sleep 1; done' && echo "SERVER UP"
```

Pick a port that isn't already in use (8501 is commonly occupied by
the user's own manual test session — check with
`netstat -ano | grep ":<port>"` first, or just use a distinct port
like 8510+ for automated verification).

Stop it with `taskkill //F //PID <pid>` (look up the PID via
`netstat -ano | grep ":<port>" | grep LISTENING` since the backgrounded
`streamlit.exe` process isn't the same PID bash reports with `$!`).

Requires `GEMINI_API_KEY=...` set in `.env` at the project root
(gitignored) — `main.py` loads it via `python-dotenv`.

## Drive it

No `chromium-cli` available in this environment. Chrome and Edge are
both installed on the machine, so Playwright can reuse the system
Chrome via `channel="chrome"` without downloading a separate browser
binary (`pip install playwright` into the venv is enough — skip
`playwright install`).

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto("http://localhost:8510", wait_until="networkidle", timeout=30000)
    page.wait_for_selector("text=PetMedBot", timeout=15000)
    page.screenshot(path="out.png", full_page=True)

    # Send a chat message
    page.locator('[data-testid="stChatInputTextArea"]').click()
    page.locator('[data-testid="stChatInputTextArea"]').fill("My dog is limping")
    page.keyboard.press("Enter")
    page.wait_for_selector('[data-testid="stChatMessage"]', timeout=15000)

    # Start a fresh chat (useful to see the hero header / empty state —
    # persisted chat history in db_chat_history.json means the default
    # loaded chat is often long and auto-scrolled past the header)
    page.get_by_role("button", name="New Chat").click()

    browser.close()
```

Key selectors (from Streamlit's minified JS, grep
`venv/Lib/site-packages/streamlit/static/static/js/*.js` for
`stChatMessage`/`stFileUploader`/`stChatInput` if these ever change
after a streamlit upgrade):
- `[data-testid="stChatInputTextArea"]` — chat input box
- `[data-testid="stChatMessage"]` — each message container
- `[data-testid="stChatMessageAvatarUser"]` / `stChatMessageAvatarCustom` — used in CSS to style user vs. assistant bubbles differently (see the `<style>` block in `main.py`)
- `[data-testid="stFileUploaderDropzone"]` — image upload dropzone

## Gotcha

`db_chat_history.json` (gitignored, holds real prior conversations)
persists across runs — a fresh `streamlit run` still loads whatever
chat history already exists on disk, so the "first" screenshot after
launch may show old test conversations, not an empty state. Click
"New Chat" to see the true empty/first-load UI.
