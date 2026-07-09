import cv2
import uuid
from pathlib import Path

from .detect import find_books
from .ocr import ocr_spine
from .isbn import scan_barcodes, find_isbn_in_text


def scan_image(image_path, output_dir="data/crops"):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Cannot load image: {image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    books = find_books(gray)
    barcodes = scan_barcodes(img)
    results = []
    for i, book in enumerate(books):
        x1, y1, x2, y2 = book["bbox"]
        x1 = max(0, x1 - 2)
        x2 = min(img.shape[1], x2 + 2)
        crop = img[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        book_id = str(uuid.uuid4())
        crop_path = output_dir / f"{book_id}.jpg"
        cv2.imwrite(str(crop_path), crop)
        text = ocr_spine(crop)
        isbn = find_isbn_in_text(text) if text else None
        results.append({
            "id": book_id,
            "bbox": [int(x1), int(y1), int(x2), int(y2)],
            "text": text,
            "isbn": isbn,
            "crop_path": str(crop_path),
            "confirmed": False,
        })
    source_name = Path(image_path).name
    for r in results:
        r["source_image"] = source_name
    return {
        "image_path": str(image_path),
        "barcodes": barcodes,
        "detected_spines": results,
    }
