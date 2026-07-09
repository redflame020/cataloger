import json
from pathlib import Path
from .catalog import Catalog, Book, Room, Shelf


DATA_DIR = Path("data")
CATALOG_PATH = DATA_DIR / "catalog.json"
ROOMS_PATH = DATA_DIR / "rooms.json"


def _ensure_dir():
    DATA_DIR.mkdir(exist_ok=True)


def load_catalog():
    _ensure_dir()
    if CATALOG_PATH.exists():
        with open(CATALOG_PATH) as f:
            data = json.load(f)
            return Catalog(**data)
    return Catalog()


def save_catalog(catalog):
    _ensure_dir()
    with open(CATALOG_PATH, "w") as f:
        json.dump(catalog.model_dump(), f, indent=2)


def add_book(book: Book):
    catalog = load_catalog()
    catalog.books.append(book)
    save_catalog(catalog)
    return book


def update_book(book_id: str, updates: dict):
    catalog = load_catalog()
    for i, b in enumerate(catalog.books):
        if b.id == book_id:
            for k, v in updates.items():
                setattr(catalog.books[i], k, v)
            save_catalog(catalog)
            return catalog.books[i]
    return None


def get_book(book_id: str):
    catalog = load_catalog()
    for b in catalog.books:
        if b.id == book_id:
            return b
    return None


def get_books(room: str = "", shelf: str = "", search: str = "", verified: str = ""):
    catalog = load_catalog()
    results = catalog.books
    if room:
        results = [b for b in results if b.location_room == room]
    if shelf:
        results = [b for b in results if b.location_shelf == shelf]
    if search:
        search_lower = search.lower()
        results = [
            b
            for b in results
            if search_lower in b.title.lower()
            or search_lower in b.author.lower()
        ]
    if verified == "true":
        results = [b for b in results if b.verified]
    elif verified == "false":
        results = [b for b in results if not b.verified]
    return results


def load_rooms():
    _ensure_dir()
    if ROOMS_PATH.exists():
        with open(ROOMS_PATH) as f:
            return json.load(f)
    return dict(_default_rooms())


def _default_rooms():
    return {
        "room-202": {
            "name": "Room 202",
            "shelves": {
                "shelf-1": {"name": "Shelf 1", "scan_images": []},
                "shelf-2": {"name": "Shelf 2", "scan_images": []},
            },
        },
        "room-203": {
            "name": "Room 203",
            "shelves": {
                "shelf-1": {"name": "Shelf 1", "scan_images": []},
                "shelf-2": {"name": "Shelf 2", "scan_images": []},
            },
        },
        "tv-room": {
            "name": "TV Room",
            "shelves": {"shelf": {"name": "Shelf", "scan_images": []}},
        },
        "family-room": {
            "name": "Family Room",
            "shelves": {"shelf": {"name": "Shelf", "scan_images": []}},
        },
    }


def save_rooms(rooms_dict):
    _ensure_dir()
    with open(ROOMS_PATH, "w") as f:
        json.dump(rooms_dict, f, indent=2)


def verify_book(book_id: str):
    catalog = load_catalog()
    for i, b in enumerate(catalog.books):
        if b.id == book_id:
            catalog.books[i].verified = True
            save_catalog(catalog)
            return catalog.books[i]
    return None


def delete_unverified():
    catalog = load_catalog()
    before = len(catalog.books)
    catalog.books = [b for b in catalog.books if b.verified]
    save_catalog(catalog)
    return before - len(catalog.books)


def checkout_book(book_id: str, user: str):
    from datetime import datetime
    catalog = load_catalog()
    for i, b in enumerate(catalog.books):
        if b.id == book_id and b.status == "available":
            if not b.verified:
                return None, "Book must be verified before checkout"
            catalog.books[i].status = "checked_out"
            if not hasattr(catalog.books[i], "loans"):
                catalog.books[i].loans = []
            catalog.books[i].loans.append({
                "user": user,
                "checkout": datetime.now().isoformat(),
                "checkin": None,
            })
            save_catalog(catalog)
            return catalog.books[i], None
    return None, "Book not available"


def checkin_book(book_id: str):
    from datetime import datetime
    catalog = load_catalog()
    for i, b in enumerate(catalog.books):
        if b.id == book_id and b.status == "checked_out":
            catalog.books[i].status = "available"
            if hasattr(catalog.books[i], "loans") and catalog.books[i].loans:
                catalog.books[i].loans[-1]["checkin"] = datetime.now().isoformat()
            save_catalog(catalog)
            return catalog.books[i]
    return None


def get_shelf_books(room: str, shelf: str):
    catalog = load_catalog()
    books = [b for b in catalog.books if b.location_room == room and b.location_shelf == shelf]
    books.sort(key=lambda b: (b.shelf_order if b.shelf_order > 0 else 9999, b.title.lower()))
    return books


def reorder_shelf(room: str, shelf: str, book_ids: list[str]):
    catalog = load_catalog()
    id_to_idx = {b.id: i for i, b in enumerate(catalog.books)}
    for order, bid in enumerate(book_ids, 1):
        if bid in id_to_idx:
            catalog.books[id_to_idx[bid]].shelf_order = order
    save_catalog(catalog)
    return get_shelf_books(room, shelf)


def reorder_book(book_id: str, new_order: int):
    catalog = load_catalog()
    for i, b in enumerate(catalog.books):
        if b.id == book_id:
            catalog.books[i].shelf_order = new_order
            save_catalog(catalog)
            return catalog.books[i]
    return None


def swap_books_on_shelf(book_id: str, direction: str):
    catalog = load_catalog()
    book = None
    for b in catalog.books:
        if b.id == book_id:
            book = b
            break
    if not book or book.shelf_order < 1:
        return None
    room, shelf_key = book.location_room, book.location_shelf
    shelf_books = [b for b in catalog.books if b.location_room == room and b.location_shelf == shelf_key and b.shelf_order > 0]
    shelf_books.sort(key=lambda b: b.shelf_order)
    idx = next((i for i, b in enumerate(shelf_books) if b.id == book_id), -1)
    if idx < 0:
        return None
    swap_idx = idx - 1 if direction == "left" else idx + 1
    if swap_idx < 0 or swap_idx >= len(shelf_books):
        return None
    other = shelf_books[swap_idx]
    catalog = load_catalog()
    for b in catalog.books:
        if b.id == book_id:
            b.shelf_order = other.shelf_order
        elif b.id == other.id:
            b.shelf_order = book.shelf_order
    save_catalog(catalog)
    return get_book(book_id)
