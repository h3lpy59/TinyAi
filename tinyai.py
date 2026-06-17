#!/usr/bin/env python3
"""
TinyAI - Local AI with internet access.
Runs the model on YOUR PC via Ollama.
Searches the web automatically when needed.
"""

import requests
import json
import sys
import os
import time
import textwrap
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
OLLAMA_URL  = "http://localhost:11434"
SEARCH_URL  = "https://api.duckduckgo.com/"
WIDTH       = 72

# ── Colours (Windows + Unix) ──────────────────────────────────────────────────
def enable_ansi():
    if os.name == "nt":
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7)

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
DIM    = "\033[2m"
RED    = "\033[91m"

def c(text, colour):
    return f"{colour}{text}{RESET}"

# ── Ollama helpers ────────────────────────────────────────────────────────────
def get_models():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=4)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return None

def stream_chat(messages, model, system_prompt):
    payload = {
        "model":    model,
        "messages": messages,
        "stream":   True,
        "system":   system_prompt,
        "options":  {"temperature": 0.7, "num_predict": 512},
    }
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()
        full = ""
        for line in resp.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            chunk = data.get("message", {}).get("content", "")
            print(chunk, end="", flush=True)
            full += chunk
            if data.get("done"):
                break
        return full
    except requests.exceptions.ConnectionError:
        print(c("\n[Error] Ollama stopped responding.", RED))
        return ""
    except Exception as e:
        print(c(f"\n[Error] {e}", RED))
        return ""

# ── Web search ────────────────────────────────────────────────────────────────
def web_search(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo instant-answer API — no key needed."""
    params = {
        "q":           query,
        "format":      "json",
        "no_html":     "1",
        "skip_disambig": "1",
    }
    snippets = []
    try:
        r = requests.get(SEARCH_URL, params=params, timeout=8,
                         headers={"User-Agent": "TinyAI/1.0"})
        data = r.json()

        # Abstract (Wikipedia-style summary)
        if data.get("AbstractText"):
            snippets.append({
                "title":   data.get("Heading", "Result"),
                "snippet": data["AbstractText"],
                "url":     data.get("AbstractURL", ""),
            })

        # Related topics
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                snippets.append({
                    "title":   topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                    "snippet": topic["Text"],
                    "url":     topic.get("FirstURL", ""),
                })
            if len(snippets) >= max_results:
                break

    except Exception:
        pass

    # Fallback: DuckDuckGo HTML scrape for more results
    if len(snippets) < 2:
        try:
            html_r = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                timeout=8,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
            import re
            results = re.findall(
                r'<a class="result__snippet"[^>]*>(.*?)</a>', html_r.text, re.S
            )
            titles  = re.findall(
                r'<a class="result__a"[^>]*>(.*?)</a>', html_r.text, re.S
            )
            def strip_tags(t):
                return re.sub(r"<[^>]+>", "", t).strip()
            for i, snip in enumerate(results[:max_results]):
                title = strip_tags(titles[i]) if i < len(titles) else "Result"
                snippets.append({"title": title, "snippet": strip_tags(snip), "url": ""})
        except Exception:
            pass

    return snippets[:max_results]


def needs_search(text: str) -> bool:
    """Decide whether this message warrants a web search."""
    low = text.lower().strip()
    # Skip pure chit-chat
    chit = {"hi","hello","hey","thanks","thank you","bye","goodbye",
            "who are you","what are you","how are you"}
    if low in chit:
        return False
    # Trigger words that almost always need current info
    triggers = [
        "latest","recent","news","today","current","now","2024","2025","2026",
        "price","weather","score","result","who won","what happened",
        "update","release","when did","where is","how much","how many",
    ]
    if any(t in low for t in triggers):
        return True
    # Questions with question words generally benefit from search
    q_words = ["what","who","where","when","why","how","which","is ","are ","does ","did "]
    if any(low.startswith(w) for w in q_words):
        return True
    return False


def format_search_context(results: list[dict]) -> str:
    lines = ["[Web search results — use these to answer accurately]"]
    for i, r in enumerate(results, 1):
        title   = r.get("title", "")
        snippet = r.get("snippet", "")
        url     = r.get("url", "")
        lines.append(f"\n[{i}] {title}")
        lines.append(f"    {snippet}")
        if url:
            lines.append(f"    Source: {url}")
    lines.append("\n[End of search results]")
    return "\n".join(lines)


# ── UI helpers ────────────────────────────────────────────────────────────────
def clear():
    os.system("cls" if os.name == "nt" else "clear")

def hr():
    print(c("─" * WIDTH, DIM))

def wrap(text, indent=0):
    prefix = " " * indent
    for line in text.splitlines():
        if line.strip():
            for wrapped in textwrap.wrap(line, WIDTH - indent):
                print(prefix + wrapped)
        else:
            print()

def banner(model_name):
    clear()
    print(c("""
  ╔══════════════════════════════════════════════════════════╗
  ║   TinyAI  ·  Local model  ·  Live internet search       ║
  ╚══════════════════════════════════════════════════════════╝""", CYAN))
    print(c(f"  Model  : {model_name}", DIM))
    print(c(f"  Date   : {datetime.now().strftime('%Y-%m-%d %H:%M')}", DIM))
    print(c("  Type 'help' for commands, 'quit' to exit\n", DIM))
    hr()

SYSTEM_PROMPT = (
    "You are TinyAI, a helpful local AI assistant running on the user's PC. "
    "You have access to live web search results which are injected before the "
    "user's question when relevant. Use those results to give accurate, "
    "up-to-date answers. Cite sources when useful. Be concise and clear. "
    "Today's date is " + datetime.now().strftime("%B %d, %Y") + "."
)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    enable_ansi()

    # ── Check Ollama ──────────────────────────────────────────────────────────
    models = get_models()
    if models is None:
        clear()
        print(c("\n  Ollama is not running!\n", RED))
        print("  TinyAI needs Ollama to run the local AI model.")
        print("  1. Download Ollama from  https://ollama.com")
        print("  2. Open a new terminal and run:  ollama serve")
        print("  3. Pull a model:                 ollama pull llama3.2")
        print("  4. Start TinyAI again.\n")
        input("  Press Enter to exit...")
        sys.exit(1)

    if not models:
        clear()
        print(c("\n  No models installed!\n", YELLOW))
        print("  Open a terminal and run:")
        print(c("    ollama pull llama3.2\n", CYAN))
        input("  Press Enter to exit...")
        sys.exit(1)

    # Pick model (prefer llama3 variants, else first available)
    preferred = next(
        (m for m in models if "llama3" in m.lower()), models[0]
    )

    banner(preferred)

    history = []   # [{role, content}]

    while True:
        try:
            user_input = input(c("\n  You ▶  ", CYAN)).strip()
        except (EOFError, KeyboardInterrupt):
            print(c("\n\n  Goodbye!\n", DIM))
            break

        if not user_input:
            continue

        low = user_input.lower()

        # ── Commands ──────────────────────────────────────────────────────────
        if low in ("quit", "exit", "q", "bye"):
            print(c("\n  Goodbye!\n", DIM))
            break

        if low == "help":
            print(c("""
  Commands:
    quit / exit   — exit TinyAI
    clear         — clear the screen
    history       — show conversation history
    search <q>    — force a web search
    nosearch      — toggle auto-search off/on
    model         — show current model
""", DIM))
            continue

        if low == "clear":
            banner(preferred)
            history.clear()
            continue

        if low == "history":
            hr()
            for msg in history[-10:]:
                role = "You" if msg["role"] == "user" else "AI"
                colour = CYAN if role == "You" else GREEN
                print(c(f"\n  {role}:", colour))
                wrap(msg["content"][:300] + ("…" if len(msg["content"]) > 300 else ""), indent=4)
            hr()
            continue

        if low == "model":
            print(c(f"\n  Current model: {preferred}", DIM))
            continue

        # Force search command
        force_search = low.startswith("search ")
        query = user_input[7:].strip() if force_search else user_input

        # ── Web search ────────────────────────────────────────────────────────
        context_block = ""
        if force_search or needs_search(user_input):
            print(c(f"\n  🔎 Searching: {query[:60]}…", YELLOW), end="", flush=True)
            results = web_search(query)
            if results:
                print(c(f" {len(results)} results found", YELLOW))
                context_block = format_search_context(results)
            else:
                print(c(" no results", RED))

        # ── Build message ─────────────────────────────────────────────────────
        if context_block:
            content = f"{context_block}\n\nUser question: {user_input}"
        else:
            content = user_input

        history.append({"role": "user", "content": content})

        # Keep history bounded (last 12 messages)
        trimmed = history[-12:]

        # ── Stream response ───────────────────────────────────────────────────
        print(c("\n  AI ▶  ", GREEN), end="", flush=True)
        reply = stream_chat(trimmed, preferred, SYSTEM_PROMPT)
        print()

        if reply:
            history.append({"role": "assistant", "content": reply})

        hr()


if __name__ == "__main__":
    main()
