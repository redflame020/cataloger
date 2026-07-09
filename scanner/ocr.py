import cv2
import numpy as np
import pytesseract
import re


def _apply_gamma(gray, gamma):
    inv_gamma = 1.0 / gamma
    table = np.array([(i / 255.0) ** inv_gamma * 255 for i in range(256)]).astype("uint8")
    return cv2.LUT(gray, table)


def ocr_spine(crop_bgr):
    h, w = crop_bgr.shape[:2]
    if h < 20 or w < 20:
        return ""
    results = []
    for rotation in [cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE]:
        try:
            rotated = cv2.rotate(crop_bgr, rotation)
            gray = cv2.cvtColor(rotated, cv2.COLOR_BGR2GRAY)
            text = _ocr_gray_optimized(gray)
            if text:
                score = _score_text(text)
                results.append((text, score))
        except Exception:
            continue
    if not results:
        gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        text = _ocr_gray_optimized(gray)
        if text:
            score = _score_text(text)
            results.append((text, score))
    if not results:
        return ""
    results.sort(key=lambda r: r[1], reverse=True)
    return results[0][0]


def _ocr_gray_optimized(gray):
    h, w = gray.shape[:2]
    if h < 30 or w < 30:
        return ""
    scale = max(1.0, 300.0 / max(h, w))
    # Path 1: fast path — raw grayscale + resize
    try:
        img = gray
        if scale > 1.2:
            img = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
        text = _tesseract_read_fast(img)
        if text:
            return text
    except Exception:
        pass
    # Path 2: gamma + resize (for dark images)
    try:
        mean = np.mean(gray)
        if mean < 110:
            gamma = max(1.5, 130.0 / max(mean, 5))
            img = _apply_gamma(gray, gamma)
            if scale > 1.2:
                img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            text = _tesseract_read_fast(img)
            if text:
                return text
    except Exception:
        pass
    # Path 3: CLAHE + resize (low contrast fallback)
    try:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        img = clahe.apply(gray)
        if scale > 1.2:
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        text = _tesseract_read_fast(img)
        if text:
            return text
    except Exception:
        pass
    return ""


def _tesseract_read_fast(gray_img):
    try:
        text = pytesseract.image_to_string(gray_img, config="--psm 6 --oem 3").strip()
        words = _extract_valid_words(text)
        if words:
            return words
    except Exception:
        pass
    return ""


NOISE_WORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
    "her", "was", "one", "our", "out", "has", "have", "been", "some",
    "them", "than", "that", "this", "very", "were", "each", "from",
    "which", "their", "what", "when", "with", "make", "more", "most",
    "also", "over", "into", "such", "only", "other", "about", "after",
    "then", "there", "would", "could", "should", "well",
}


def _extract_valid_words(text):
    words = re.findall(r"[A-Za-z]{4,}", text)
    if not words:
        return ""
    filtered = [w for w in words if w.lower() not in NOISE_WORDS and len(w) >= 4]
    if len(filtered) < 2 and words:
        filtered = [w for w in words if len(w) >= 4]
    seen = set()
    result = []
    for w in filtered:
        key = w.lower()
        if key not in seen:
            seen.add(key)
            result.append(w)
    return " ".join(result) if len(result) >= 2 else ""


def _score_text(text):
    if not text:
        return 0
    words = text.split()
    return sum(1 for w in words if len(w) >= 4) * 2 + len(words)
