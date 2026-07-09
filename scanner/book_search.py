import urllib.request
import urllib.parse
import json
import re
import hashlib

_cache = {}


def _cache_key(query, params):
    raw = json.dumps({"q": query, "p": params}, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def search_books(text: str = "", isbn: str = "") -> list[dict]:
    if isbn:
        results = _search_openlibrary_by_isbn(isbn)
        if results:
            return results

    title, author = _split_title_author(text)

    seen_isbns = set()
    all_results = []

    # Tier 1: title + author parameters (most specific)
    if title:
        if author:
            tier1 = _search_openlibrary(title, extra_params={"author": author})
            for r in tier1:
                _add(r, seen_isbns, all_results)
        tier1b = _search_openlibrary(title, extra_params={"title": title})
        for r in tier1b:
            _add(r, seen_isbns, all_results)

    # Tier 2: general combined search
    if len(all_results) < 3:
        combined = text
        tier2 = _search_openlibrary(combined)
        for r in tier2:
            _add(r, seen_isbns, all_results)

    # Tier 3: word subset (broadest)
    if not all_results:
        nouns = _extract_nouns(text)[:5]
        if nouns:
            tier3 = _search_openlibrary(" ".join(nouns))
            for r in tier3:
                all_results.append(r)

    return all_results[:10]


def _add(result, seen, results):
    key = result.get("isbn") or result["title"]
    if key not in seen:
        seen.add(key)
        results.append(result)


def _split_title_author(text: str) -> tuple:
    parts = re.split(r"\s+(by|by:)\s+", text, flags=re.I, maxsplit=1)
    if len(parts) > 1:
        return parts[0].strip(), parts[-1].strip()
    return text, ""


def _extract_nouns(text: str) -> list:
    return re.findall(r"[A-Z][a-z]{3,}", text)


def _search_openlibrary(query: str, extra_params: dict = None) -> list[dict]:
    ck = _cache_key(query, extra_params)
    if ck in _cache:
        return _cache[ck]
    try:
        params = {"q": query, "limit": 10}
        if extra_params:
            params.update(extra_params)
        url = f"https://openlibrary.org/search.json?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Cataloger/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            docs = data.get("docs", [])
            results = []
            seen = set()
            for d in docs:
                title = d.get("title", "")
                if not title:
                    continue
                key = title.lower().strip()
                if key in seen:
                    continue
                seen.add(key)
                author_list = d.get("author_name", [])
                author = author_list[0] if author_list else ""
                isbns = d.get("isbn", [])
                isbn = isbns[0] if isbns else ""
                publisher_list = d.get("publisher", [])
                publisher = publisher_list[0] if publisher_list else ""
                cover_i = d.get("cover_i")
                cover_url = f"https://covers.openlibrary.org/b/id/{cover_i}-L.jpg" if cover_i else ""
                results.append({
                    "title": title, "author": author, "isbn": isbn,
                    "publisher": publisher, "cover_url": cover_url, "source": "openlibrary",
                })
                if len(results) >= 10:
                    break
            _cache[ck] = results
            return results
    except Exception:
        return []


def _search_openlibrary_by_isbn(isbn: str) -> list[dict]:
    try:
        url = f"https://openlibrary.org/isbn/{isbn}.json"
        req = urllib.request.Request(url, headers={"User-Agent": "Cataloger/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            title = data.get("title", "")
            authors_raw = data.get("authors", [])
            author = authors_raw[0].get("name", "") if authors_raw else ""
            publishers = data.get("publishers", [])
            publisher = publishers[0] if publishers else ""
            covers = data.get("covers", [])
            cover_url = f"https://covers.openlibrary.org/b/id/{covers[0]}-L.jpg" if covers else ""
            return [{"title": title, "author": author, "isbn": isbn,
                     "publisher": publisher, "cover_url": cover_url, "source": "openlibrary"}]
    except Exception:
        return []
