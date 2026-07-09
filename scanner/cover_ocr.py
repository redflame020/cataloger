import cv2
import numpy as np
import pytesseract
import re
import uuid
from io import BytesIO
from pathlib import Path
from pyzbar.pyzbar import decode as zbar_decode
from PIL import Image

from .llm_parser import parse_with_llm
from .scorer import score_line

ANNOTATIONS_DIR = Path("data/crops")
ANNOTATIONS_DIR.mkdir(parents=True, exist_ok=True)

OCR_CONF_MIN = 30
LINE_CONF_MIN = 25
ANNOT_CONF_MIN = 55


def ocr_cover(image_bytes: bytes) -> dict:
    img = _decode_bytes(image_bytes)
    if img is None:
        return {"text": "", "words": [], "isbn": None, "title": "", "author": "",
                "edition": "", "clean_query": "", "llm_parsed": False, "annotated": ""}

    img = _perspective_correct(img)
    gray = _prepare_gray(img)
    data = _single_ocr(gray)
    isbn = _scan_isbn(img)
    cover_filename = _save_cover_snap(img)
    annot_filename = _save_annotation_fast(img, data)

    clusters = _cluster_lines(data, gray.shape)

    title_candidates = []
    author_candidates = []
    edition_candidates = []

    main_font = max((c["font_size"] for c in clusters), default=0)
    for c in clusters:
        rel_size = c["font_size"] / max(main_font, 1)
        if rel_size > 0.75:
            title_candidates.append(c["text"])
        elif rel_size > 0.45:
            author_candidates.append(c["text"])
        elif c["text"] and len(c["text"]) > 5:
            title_candidates.append(c["text"])
        if re.search(r"(first|second|third|1st|2nd|3rd)\s*(ed|edition)", c["text"], re.I):
            edition_candidates.append(c["text"])

    title = max(title_candidates, key=len) if title_candidates else ""
    author = max(author_candidates, key=len) if author_candidates else ""
    edition = max(edition_candidates, key=len) if edition_candidates else ""
    llm_used = False

    if title_candidates or author_candidates:
        try:
            llm_result = parse_with_llm(title_candidates, author_candidates, edition_candidates)
            if llm_result.get("title"):
                title = llm_result["title"]
                author = llm_result.get("author") or author
                edition = llm_result.get("edition") or edition
                llm_used = True
        except Exception:
            pass

    search = title.replace("/", " ")
    if author and author not in search:
        search += " " + author.replace("/", " ")

    return {
        "text": "\n".join(c["text"] for c in clusters),
        "words": list(dict.fromkeys(w.lower() for c in clusters for w in c["text"].split() if len(w) >= 3)),
        "isbn": isbn,
        "title": title,
        "author": author,
        "edition": edition,
        "clean_query": search.strip(),
        "llm_parsed": llm_used,
        "annotated": annot_filename,
        "cover_snap": cover_filename,
    }


def _decode_bytes(image_bytes: bytes):
    try:
        arr = np.frombuffer(image_bytes, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _perspective_correct(img):
    h, w = img.shape[:2]
    if h < 100 or w < 100:
        return img
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blur, 30, 100)
    dilated = cv2.dilate(edged, None, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return img
    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    if area < w * h * 0.15:
        return img
    peri = cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, 0.02 * peri, True)
    if len(approx) != 4:
        return img
    pts = approx.reshape(4, 2).astype(np.float32)
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    (tl, tr, br, bl) = rect
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = max(int(width_a), int(width_b))
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = max(int(height_a), int(height_b))
    dst = np.array([
        [0, 0], [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(img, M, (max_width, max_height))


def _prepare_gray(img_bgr):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    mean = np.mean(gray)
    if mean < 80:
        gamma = min(2.5, 120.0 / max(mean, 5))
        inv = 1.0 / gamma
        table = np.array([(i / 255.0) ** inv * 255 for i in range(256)]).astype("uint8")
        gray = cv2.LUT(gray, table)
    h, w = gray.shape[:2]
    big = max(h, w)
    if big < 600:
        scale = 600.0 / big
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    return gray


def _single_ocr(gray):
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    try:
        data = pytesseract.image_to_data(enhanced, config="--psm 6 --oem 3",
                                          output_type=pytesseract.Output.DICT)
        confs = [c for c in data["conf"] if c > 0]
        if np.mean(confs) > 0 if confs else False:
            return data
    except Exception:
        pass
    try:
        return pytesseract.image_to_data(enhanced, config="--psm 3 --oem 3",
                                          output_type=pytesseract.Output.DICT)
    except Exception:
        return {"text": [], "conf": [], "left": [], "top": [], "width": [], "height": []}


def _cluster_lines(data, img_shape):
    img_h = img_shape[0]
    lines = []
    current = {"words": [], "heights": [], "confs": [], "lefts": [], "tops": []}
    prev_top = -1
    for i in range(len(data["text"])):
        w = (data["text"][i] or "").strip()
        if not w or data["conf"][i] < OCR_CONF_MIN:
            continue
        top, height = data["top"][i], data["height"][i]
        if prev_top > 0 and abs(top - prev_top) > height * 1.2:
            if current["words"]:
                lines.append(current)
            current = {"words": [], "heights": [], "confs": [], "lefts": [], "tops": []}
        current["words"].append(w)
        current["heights"].append(height)
        current["confs"].append(data["conf"][i])
        current["lefts"].append(data["left"][i])
        current["tops"].append(data["top"][i])
        prev_top = top
    if current["words"]:
        lines.append(current)

    clusters = []
    for l in lines:
        avg_conf = np.mean(l["confs"]) if l["confs"] else 0
        if avg_conf < LINE_CONF_MIN:
            continue
        text = _fix_ocr_line(" ".join(l["words"]))
        font_size = max(l["heights"])
        y_pos = min(l["tops"])
        result = score_line(text, font_size / max(img_h, 1), y_pos, img_h)
        if result["combined"] < 0.4 or result["label"] == "garbage":
            continue
        clusters.append({
            "text": text,
            "font_size": font_size,
            "y": y_pos,
            "confidence": round(avg_conf),
            "bbox": (min(l["lefts"]), y_pos, max(l["lefts"]) + 10, y_pos + font_size),
            "_score": result["combined"],
        })

    clusters.sort(key=lambda c: c["font_size"], reverse=True)
    return clusters


def _save_annotation(img_bgr, data):
    try:
        viz = img_bgr.copy()
        for i in range(len(data["text"])):
            w = (data["text"][i] or "").strip()
            if not w or data["conf"][i] < ANNOT_CONF_MIN:
                continue
            x, y, bw, bh = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            if bw < 5 or bh < 5:
                continue
            cv2.rectangle(viz, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
            cv2.putText(viz, w, (x, max(10, y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        fname = f"annot_{uuid.uuid4().hex[:12]}.jpg"
        cv2.imwrite(str(ANNOTATIONS_DIR / fname), viz)
        return fname
    except Exception:
        return ""


def _fix_ocr_line(text: str) -> str:
    return " ".join(text.strip(".,:;!?\"'()[]{}|/\\@#$%^&*+-=<>~").split())


def _save_annotation_fast(img_bgr, data):
    try:
        viz = img_bgr.copy()
        for i in range(len(data["text"])):
            w = (data["text"][i] or "").strip()
            if not w or data["conf"][i] < ANNOT_CONF_MIN:
                continue
            x, y, bw, bh = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            if bw < 5 or bh < 5:
                continue
            cv2.rectangle(viz, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
        fname = f"annot_{uuid.uuid4().hex[:12]}.jpg"
        cv2.imwrite(str(ANNOTATIONS_DIR / fname), viz, [cv2.IMWRITE_JPEG_QUALITY, 60])
        return fname
    except Exception:
        return ""


def _save_cover_snap(img_bgr):
    try:
        h, w = img_bgr.shape[:2]
        big = max(h, w)
        if big > 400:
            scale = 400.0 / big
            small = cv2.resize(img_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        else:
            small = img_bgr
        fname = f"cover_{uuid.uuid4().hex[:12]}.jpg"
        cv2.imwrite(str(ANNOTATIONS_DIR / fname), small, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return fname
    except Exception:
        return ""


def _scan_isbn(img_bgr):
    try:
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        barcodes = zbar_decode(pil_img)
        for b in barcodes:
            data = b.data.decode("utf-8")
            if re.match(r"^(978|979)\d{10}$", data):
                return data
    except Exception:
        pass
    return None
