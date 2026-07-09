#!/usr/bin/env python3
"""Scan all images and import to catalog."""
from scanner.pipeline import scan_image
from models.store import add_book, save_rooms, load_rooms
from models.catalog import Book
from pathlib import Path

ROOM_KEY = "room-202"
SHELF_KEY = "shelf-1"

images = ["img/IMG_2161.JPG", "img/IMG_2162.JPG", "img/IMG_2163.JPG"]

for img_path in images:
    print(f"Scanning {img_path}...")
    result = scan_image(img_path)
    print(f"  Found {len(result['detected_spines'])} candidates")
    for spine in result["detected_spines"]:
        title = spine["text"] or "(unreadable)"
        book = Book(
            title=title,
            isbn=spine["isbn"] or "",
            location_room=ROOM_KEY,
            location_shelf=SHELF_KEY,
            ocred_text=spine["text"] or "",
            source_image=spine["source_image"] if "source_image" in spine else str(Path(img_path).name),
            spine_crop=spine["crop_path"],
            status="available",
        )
        add_book(book)
        print(f"    Added: {title[:60]}")

rooms = load_rooms()
if ROOM_KEY in rooms and SHELF_KEY in rooms[ROOM_KEY]["shelves"]:
    for img in images:
        p = Path(img).name
        if p not in rooms[ROOM_KEY]["shelves"][SHELF_KEY]["scan_images"]:
            rooms[ROOM_KEY]["shelves"][SHELF_KEY]["scan_images"].append(p)
    save_rooms(rooms)

print("\nDone! Run 'python3 cli.py serve' to start the web UI.")
