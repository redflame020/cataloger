import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from scanner.pipeline import scan_image
from scanner.cover_ocr import ocr_cover
from scanner.book_search import search_books
from models.store import (
    load_catalog,
    save_catalog,
    add_book,
    update_book,
    get_book,
    get_books,
    checkout_book,
    checkin_book,
    verify_book,
    delete_unverified,
    reorder_shelf,
    reorder_book,
    swap_books_on_shelf,
    get_shelf_books,
    load_rooms,
    save_rooms,
)
from models.catalog import Book

app = FastAPI(title="Cataloger")

STATIC_DIR = Path("static")
DATA_DIR = Path("data")
CROPS_DIR = DATA_DIR / "crops"
CROPS_DIR.mkdir(parents=True, exist_ok=True)

import json
import threading
import urllib.request

def _warmup_llm():
    try:
        data = json.dumps({
            "model": "llama3.2:latest", "prompt": "warmup", "stream": False,
            "options": {"num_predict": 1},
        }).encode()
        urllib.request.urlopen(
            "http://localhost:11434/api/generate", data=data, timeout=30
        )
    except Exception:
        pass

threading.Thread(target=_warmup_llm, daemon=True).start()


@app.get("/api/books")
def api_list_books(
    room: str = "",
    shelf: str = "",
    search: str = "",
    verified: str = "",
):
    books = get_books(room=room, shelf=shelf, search=search, verified=verified)
    return [b.model_dump() for b in books]


@app.get("/api/books/{book_id}")
def api_get_book(book_id: str):
    book = get_book(book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    return book.model_dump()


@app.post("/api/books")
def api_create_book(data: dict):
    book = Book(
        title=data.get("title", "(untitled)"),
        author=data.get("author", ""),
        isbn=data.get("isbn", ""),
        publisher=data.get("publisher", ""),
        cover_url=data.get("cover_url", ""),
        snapped_cover=data.get("snapped_cover", ""),
        location_room=data.get("location_room", ""),
        location_shelf=data.get("location_shelf", ""),
        verified=data.get("verified", False),
        ocred_text=data.get("ocred_text", ""),
    )
    added = add_book(book)
    return added.model_dump()


@app.get("/api/check-duplicate")
def api_check_duplicate(title: str = "", author: str = ""):
    catalog = load_catalog()
    title_lower = title.lower().strip()
    author_lower = author.lower().strip() if author else ""
    matches = []
    for b in catalog.books:
        bt = b.title.lower().strip()
        if bt == title_lower or (len(bt) > 5 and (bt in title_lower or title_lower in bt)):
            ba = b.author.lower().strip() if b.author else ""
            if not author_lower or not ba or ba == author_lower or ba in author_lower or author_lower in ba:
                matches.append({"id": b.id, "title": b.title, "author": b.author})
                if len(matches) >= 5:
                    break
    return {"duplicate": len(matches) > 0, "matches": matches}


@app.post("/api/books/{book_id}")
def api_update_book(book_id: str, data: dict):
    book = update_book(book_id, data)
    if not book:
        raise HTTPException(404, "Book not found")
    return book.model_dump()


@app.post("/api/books/{book_id}/verify")
def api_verify_book(book_id: str):
    book = verify_book(book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    return book.model_dump()


@app.delete("/api/books/unverified")
def api_delete_unverified():
    count = delete_unverified()
    return {"deleted": count}


@app.delete("/api/books/{book_id}")
def api_delete_book(book_id: str):
    catalog = load_catalog()
    initial = len(catalog.books)
    catalog.books = [b for b in catalog.books if b.id != book_id]
    if len(catalog.books) == initial:
        raise HTTPException(404, "Book not found")
    save_catalog(catalog)
    return {"deleted": book_id}


@app.post("/api/books/{book_id}/checkout")
def api_checkout(book_id: str, data: dict):
    user = data.get("user", "")
    if not user:
        raise HTTPException(400, "User required")
    book, err = checkout_book(book_id, user)
    if not book:
        raise HTTPException(400, err or "Cannot check out")
    return book.model_dump()


@app.post("/api/books/{book_id}/checkin")
def api_checkin(book_id: str):
    book = checkin_book(book_id)
    if not book:
        raise HTTPException(400, "Cannot check in")
    return book.model_dump()


@app.post("/api/books/{book_id}/swap")
def api_swap_book(book_id: str, data: dict):
    direction = data.get("direction", "")
    book = swap_books_on_shelf(book_id, direction)
    if not book:
        raise HTTPException(400, "Cannot move further")
    return book.model_dump()


@app.get("/api/shelves/{room}/{shelf}/books")
def api_shelf_books(room: str, shelf: str):
    books = get_shelf_books(room, shelf)
    return [b.model_dump() for b in books]


@app.post("/api/shelves/{room}/{shelf}/reorder")
def api_reorder_shelf(room: str, shelf: str, data: dict):
    book_ids = data.get("order", [])
    books = reorder_shelf(room, shelf, book_ids)
    return [b.model_dump() for b in books]


@app.post("/api/scan")
async def api_scan(file: UploadFile = File(...)):
    temp_path = DATA_DIR / "uploads" / file.filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    result = scan_image(temp_path)
    return result


@app.post("/api/scan-cover-live")
async def api_scan_cover(file: UploadFile = File(...)):
    image_bytes = await file.read()
    result = ocr_cover(image_bytes)
    return result


@app.get("/api/search-books")
def api_search_books(q: str = "", isbn: str = ""):
    results = search_books(text=q, isbn=isbn)
    return results


@app.post("/api/import")
def api_import(data: dict):
    room = data.get("room", "")
    shelf = data.get("shelf", "")
    spines = data.get("spines", [])
    spines.sort(key=lambda s: s.get("bbox", [0, 0, 0, 0])[0])
    imported = []
    for order, s in enumerate(spines, 1):
        book = Book(
            title=s.get("title", s.get("text", "(untitled)")),
            author=s.get("author", ""),
            isbn=s.get("isbn", ""),
            location_room=room,
            location_shelf=shelf,
            shelf_order=order,
            ocred_text=s.get("text", ""),
            source_image=s.get("source_image", ""),
            spine_crop=s.get("crop_path", ""),
            verified=False,
        )
        add_book(book)
        imported.append(book.model_dump())
    return {"imported": imported}


@app.get("/api/rooms")
def api_list_rooms():
    return load_rooms()


@app.get("/api/loans")
def api_list_loans():
    catalog = load_catalog()
    loans = []
    for b in catalog.books:
        if hasattr(b, "loans") and b.loans:
            for loan in b.loans:
                loans.append({**loan, "book_title": b.title, "book_id": b.id})
    return loans


@app.get("/api/crops/{filename}")
def api_get_crop(filename: str):
    filepath = CROPS_DIR / filename
    if filepath.exists():
        return FileResponse(str(filepath))
    raise HTTPException(404, "Crop not found")


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
