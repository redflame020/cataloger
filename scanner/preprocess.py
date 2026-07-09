import cv2
import numpy as np


def load_image(path, max_width=1500):
    img = cv2.imread(str(path))
    if img is None:
        raise ValueError(f"Cannot load image: {path}")
    h, w = img.shape[:2]
    if w > max_width:
        scale = max_width / w
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return img


def to_grayscale(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def enhance_contrast(gray):
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def deskew(gray):
    coords = np.column_stack(np.where(gray > 0))
    if len(coords) < 10:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5:
        return gray
    h, w = gray.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return rotated


def preprocess(path, max_width=1500):
    img = load_image(path, max_width)
    gray = to_grayscale(img)
    enhanced = enhance_contrast(gray)
    deskewed = deskew(enhanced)
    return img, deskewed
