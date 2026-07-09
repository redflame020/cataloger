import cv2
import numpy as np
import re
from pyzbar.pyzbar import decode as zbar_decode
from PIL import Image


def scan_barcodes(img_bgr):
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    results = []
    try:
        barcodes = zbar_decode(pil_img)
        for b in barcodes:
            data = b.data.decode("utf-8")
            if re.match(r"^(978|979)\d{10}$", data):
                results.append(data)
    except Exception:
        pass
    return list(set(results))


def find_isbn_in_text(text):
    cleaned = re.sub(r"[^0-9]", "", text)
    if len(cleaned) >= 13:
        candidate = cleaned[:13]
        if candidate.startswith("978") or candidate.startswith("979"):
            return candidate
    match = re.search(r"((978|979)[- ]?\d{1,5}[- ]?\d{1,7}[- ]?\d{1,7}[- ]?[\dXx])", text)
    if match:
        isbn_raw = re.sub(r"[^0-9Xx]", "", match.group(1))
        if len(isbn_raw) == 13 or len(isbn_raw) == 10:
            return isbn_raw
    return None
