import json
import socket
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:1b"


def _ollama_available():
    try:
        sock = socket.create_connection(("localhost", 11434), timeout=0.5)
        sock.close()
        return True
    except Exception:
        return False


def parse_with_llm(title_candidates: list, author_candidates: list,
                    edition_candidates: list) -> dict:
    if not _ollama_available():
        return {
            "title": title_candidates[0] if title_candidates else "",
            "author": author_candidates[0] if author_candidates else "",
            "edition": edition_candidates[0] if edition_candidates else "",
        }

    if len(title_candidates) <= 1 and len(author_candidates) <= 1:
        return {
            "title": title_candidates[0] if title_candidates else "",
            "author": author_candidates[0] if author_candidates else "",
            "edition": edition_candidates[0] if edition_candidates else "",
        }

    prompt = (
        "Given these candidate fields scanned from a book cover by OCR, "
        "choose the best title, author, and edition.\n"
        "Fix common OCR typos (like y→J in names, split words that belong together).\n"
        "Do not make up information. If unsure, use empty string.\n\n"
        f"Title candidates: {json.dumps(title_candidates)}\n"
        f"Author candidates: {json.dumps(author_candidates)}\n"
        f"Edition candidates: {json.dumps(edition_candidates)}\n\n"
        "Return JSON with keys: title, author, edition."
    )

    try:
        body = json.dumps({
            "model": MODEL, "prompt": prompt, "stream": False,
            "format": "json", "options": {"temperature": 0, "num_predict": 128},
        }).encode()
        req = urllib.request.Request(
            OLLAMA_URL, data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        response_text = result.get("response", "").strip()
        parsed = json.loads(response_text)
        return {
            "title": (parsed.get("title") or "").strip(),
            "author": (parsed.get("author") or "").strip(),
            "edition": (parsed.get("edition") or "").strip(),
        }
    except Exception:
        return {"title": title_candidates[0] if title_candidates else "",
                "author": author_candidates[0] if author_candidates else "",
                "edition": edition_candidates[0] if edition_candidates else ""}


def warmup():
    if not _ollama_available():
        return
    try:
        body = json.dumps({
            "model": MODEL, "prompt": "warmup", "stream": False,
            "format": "json", "options": {"num_predict": 1},
        }).encode()
        req = urllib.request.Request(
            OLLAMA_URL, data=body,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=30)
    except Exception:
        pass
