"""Auto-suggest detection and processing parameters from image statistics."""

import cv2
import numpy as np

__all__ = ["compute_suggested"]


def compute_suggested(img) -> dict:
    h, w = img.shape

    otsu_val, binary_otsu = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    otsu_val = max(1, min(254, int(otsu_val)))

    ink_ratio = cv2.countNonZero(binary_otsu) / (h * w)

    diag = np.sqrt(h * h + w * w)
    proposed_min = max(5, min(100, int(diag * 0.01)))

    if ink_ratio > 0.15:
        proposed_eps = 2.0
    elif ink_ratio > 0.05:
        proposed_eps = 1.0
    else:
        proposed_eps = 0.5

    mean, stddev = cv2.meanStdDev(img)
    std = stddev[0][0]
    lap_var = cv2.Laplacian(img, cv2.CV_64F).var()

    if lap_var > 500 and std > 40:
        proposed_mode = "Canny Edge"
        proposed_blur = max(1, min(5, int(np.sqrt(lap_var) / 50)))
        proposed_morph = 1
        proposed_canny_lo = max(10, int(otsu_val * 0.3))
        proposed_canny_hi = max(proposed_canny_lo + 20, int(otsu_val * 0.9))
    elif std > 60 and 0.2 < ink_ratio < 0.8:
        proposed_mode = "Adaptive Threshold"
        proposed_blur = 1
        proposed_morph = 1
        proposed_canny_lo = 50
        proposed_canny_hi = 150
    else:
        proposed_mode = "Threshold"
        proposed_blur = 0
        proposed_morph = 0
        proposed_canny_lo = 50
        proposed_canny_hi = 150

    return {
        "threshold": otsu_val,
        "min_contour_len": proposed_min,
        "simplify": proposed_eps,
        "detect_mode": proposed_mode,
        "blur_radius": proposed_blur,
        "morph_iter": proposed_morph,
        "canny_lo": proposed_canny_lo,
        "canny_hi": proposed_canny_hi,
        "adaptive_block": 11,
        "adaptive_c": 2,
        "ink_ratio": ink_ratio,
        "lap_var": lap_var,
        "std": std,
    }
