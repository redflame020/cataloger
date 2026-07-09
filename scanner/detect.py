import cv2
import numpy as np


def _normalize_brightness(gray):
    mean = np.mean(gray)
    if mean < 100:
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    return gray


def find_books(gray, min_book_width=25, max_book_width=200, min_gap=6, tall_kernel=100):
    h, w = gray.shape[:2]
    gray = _normalize_brightness(gray)
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobelx = np.abs(sobelx)
    sobelx_uint8 = cv2.convertScaleAbs(sobelx)
    _, binary_edges = cv2.threshold(sobelx_uint8, 30, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, tall_kernel))
    closed = cv2.morphologyEx(binary_edges, cv2.MORPH_CLOSE, kernel)
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.dilate(closed, kernel_dilate, iterations=1)
    col_profile = np.sum(closed > 0, axis=0).astype(np.float64)
    col_max = np.max(col_profile)
    if col_max < 1:
        return find_books_fallback(gray, min_book_width, max_book_width * 2)
    profile = col_profile / col_max * 100
    profile_smooth = np.convolve(profile, np.ones(7) / 7, mode="same")
    local_minima = []
    for i in range(3, len(profile_smooth) - 3):
        left = profile_smooth[i - 3]
        right = profile_smooth[i + 3]
        if profile_smooth[i] < left and profile_smooth[i] < right:
            depth = min(left, right) - profile_smooth[i]
            if depth > 3:
                local_minima.append((i, profile_smooth[i], depth))
    if not local_minima:
        return find_books_fallback(gray, min_book_width, max_book_width * 2)
    noise_floor = np.percentile(profile_smooth, 15)
    strong_minima = [m for m in local_minima if m[1] <= noise_floor * 1.5]
    if len(strong_minima) < 2:
        strong_minima = local_minima
    merged = [strong_minima[0][0]]
    for m in strong_minima[1:]:
        if m[0] - merged[-1] < min_gap:
            if m[2] > next((lm[2] for lm in strong_minima if lm[0] == merged[-1]), 0):
                merged[-1] = m[0]
        else:
            merged.append(m[0])
    boundaries = [0] + merged + [w - 1]
    books = []
    for i in range(len(boundaries) - 1):
        bw = boundaries[i + 1] - boundaries[i]
        if min_book_width < bw < max_book_width:
            x1 = max(0, boundaries[i] - 2)
            x2 = min(w, boundaries[i + 1] + 2)
            books.append({"bbox": (x1, 0, x2, h), "width": bw})
        elif bw >= max_book_width:
            split_regions = _split_wide_region(profile_smooth, boundaries[i], boundaries[i + 1], min_book_width, max_book_width)
            for sx1, sx2 in split_regions:
                books.append({"bbox": (sx1, 0, sx2, h), "width": sx2 - sx1})
    return books


def _split_wide_region(profile, start, end, min_w, max_w):
    if end - start < max_w:
        return [(start, end)]
    segment = profile[start:end]
    deepest = -1
    deepest_val = float("inf")
    for j in range(3, len(segment) - 3):
        if segment[j] < segment[j - 1] and segment[j] < segment[j + 1]:
            if segment[j] < deepest_val:
                deepest_val = segment[j]
                deepest = j
    if deepest < 0:
        return [(start, end)]
    split_point = start + deepest
    left = [(start, split_point)] if split_point - start > min_w else []
    right = [(split_point, end)] if end - split_point > min_w else []
    results = []
    for sub_start, sub_end in left + right:
        sub_w = sub_end - sub_start
        if sub_w > max_w:
            results.extend(_split_wide_region(profile, sub_start, sub_end, min_w, max_w))
        elif sub_w > min_w:
            results.append((sub_start, sub_end))
    return results


def find_books_fallback(gray, min_book_width=25, max_book_width=400):
    h, w = gray.shape[:2]
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobelx = np.abs(sobelx)
    col_energy = np.sum(sobelx, axis=0)
    col_max = np.max(col_energy)
    if col_max < 1:
        return []
    profile = col_energy / col_max * 100
    profile = np.convolve(profile, np.ones(7) / 7, mode="same")
    threshold = np.percentile(profile[profile > 0], 35)
    threshold = max(threshold, 5)
    is_book = profile >= threshold
    transitions = np.diff(is_book.astype(int))
    starts = np.where(transitions == 1)[0] + 1
    ends = np.where(transitions == -1)[0] + 1
    if is_book[0]:
        starts = np.insert(starts, 0, 0)
    if is_book[-1]:
        ends = np.append(ends, w - 1)
    min_len = min(len(starts), len(ends))
    starts = starts[:min_len]
    ends = ends[:min_len]
    merged_starts, merged_ends = [], []
    for s, e in zip(starts, ends):
        if e - s < 10:
            continue
        if merged_starts and s - merged_ends[-1] < 8:
            merged_ends[-1] = e
        else:
            merged_starts.append(s)
            merged_ends.append(e)
    books = []
    for s, e in zip(merged_starts, merged_ends):
        bw = e - s
        if min_book_width < bw < max_book_width:
            x1 = max(0, s - 2)
            x2 = min(w, e + 2)
            books.append({"bbox": (x1, 0, x2, h), "width": bw})
    return books
