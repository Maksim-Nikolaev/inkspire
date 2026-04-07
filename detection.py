"""Image detection: auto-crop bounds, multi-mode edge detection, and the auto mode selector."""

import cv2

__all__ = ["detect_art_bounds", "detect_edges", "auto_detect"]


def detect_art_bounds(gray_img, border_thresh=240, padding=5):
    _, mask = cv2.threshold(gray_img, border_thresh, 255, cv2.THRESH_BINARY_INV)
    coords = cv2.findNonZero(mask)
    if coords is None:
        return None
    x, y, w, h = cv2.boundingRect(coords)
    ih, iw = gray_img.shape
    x = max(0, x - padding)
    y = max(0, y - padding)
    w = min(iw - x, w + padding * 2)
    h = min(ih - y, h + padding * 2)
    return (x, y, w, h)


def detect_edges(gray_img, mode, threshold, canny_lo, canny_hi,
                 adaptive_block, adaptive_c, blur_radius, morph_iterations):
    """
    Convert a grayscale image to a binary edge mask.
    Returns a uint8 image where 255 = edge/line.
    """
    img = gray_img.copy()

    # ── Pre-processing: blur to remove halftone dots / noise ──
    if blur_radius > 0:
        # Ensure odd kernel size
        k = blur_radius * 2 + 1
        img = cv2.GaussianBlur(img, (k, k), 0)

    # ── Detection ──
    if mode == "Canny Edge":
        edges = cv2.Canny(img, canny_lo, canny_hi)
    elif mode == "Adaptive Threshold":
        # Block size must be odd and > 1
        block = max(3, adaptive_block)
        if block % 2 == 0:
            block += 1
        edges = cv2.adaptiveThreshold(
            img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, block, adaptive_c
        )
    elif mode == "Auto":
        edges = auto_detect(img, threshold, canny_lo, canny_hi,
                            adaptive_block, adaptive_c)
    else:
        # Simple threshold (default)
        _, edges = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY_INV)

    # ── Post-processing: morphological cleanup ──
    if morph_iterations > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        # Close small gaps
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=morph_iterations)
        # Remove tiny specks
        edges = cv2.morphologyEx(edges, cv2.MORPH_OPEN, kernel, iterations=max(1, morph_iterations // 2))

    return edges


def auto_detect(img, threshold, canny_lo, canny_hi, adaptive_block, adaptive_c):
    """
    Analyze image and pick the best method automatically.
    - High contrast, bimodal histogram -> Threshold
    - Halftone / noisy gradients -> Canny
    - Uneven lighting -> Adaptive
    """
    # Check histogram bimodality via Otsu
    otsu_val, binary_otsu = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink_ratio = cv2.countNonZero(binary_otsu) / (img.shape[0] * img.shape[1])

    # Compute local variance to detect halftones/noise
    mean, stddev = cv2.meanStdDev(img)
    std = stddev[0][0]

    # Compute Laplacian variance (focus / texture measure)
    lap_var = cv2.Laplacian(img, cv2.CV_64F).var()

    # Heuristic decision:
    # Clean B/W line art: low std, clear bimodal split, low lap_var
    # Halftone/textured: high lap_var, moderate std
    # Uneven lighting: high std, moderate ink ratio

    if lap_var > 500 and std > 40:
        # Likely halftone or noisy textured image -> Canny
        return cv2.Canny(img, canny_lo, canny_hi)
    elif std > 60 and 0.2 < ink_ratio < 0.8:
        # Uneven lighting -> Adaptive
        block = max(3, adaptive_block)
        if block % 2 == 0:
            block += 1
        return cv2.adaptiveThreshold(
            img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, block, adaptive_c
        )
    else:
        # Clean enough for simple threshold
        _, edges = cv2.threshold(img, int(otsu_val), 255, cv2.THRESH_BINARY_INV)
        return edges
