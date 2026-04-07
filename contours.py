"""Contour extraction and skeletonization from binary/grayscale images."""

import cv2
import numpy as np

from detection import detect_edges

__all__ = ["extract_contours", "skeletonize"]


def skeletonize(binary: np.ndarray) -> np.ndarray:
    skel = np.zeros_like(binary)
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    temp = binary.copy()
    while True:
        eroded = cv2.erode(temp, element)
        opened = cv2.dilate(eroded, element)
        subset = cv2.subtract(temp, opened)
        skel = cv2.bitwise_or(skel, subset)
        temp = eroded.copy()
        if cv2.countNonZero(temp) == 0:
            break
    return skel


def extract_contours(gray_image, mode, threshold, canny_lo, canny_hi,
                     adaptive_block, adaptive_c, blur_radius, morph_iterations,
                     min_length, epsilon, use_skeleton) -> list:
    edges = detect_edges(
        gray_image,
        mode=mode,
        threshold=threshold,
        canny_lo=canny_lo,
        canny_hi=canny_hi,
        adaptive_block=adaptive_block,
        adaptive_c=adaptive_c,
        blur_radius=blur_radius,
        morph_iterations=morph_iterations,
    )

    if use_skeleton:
        edges = skeletonize(edges)

    contours_raw, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    result = []
    for c in contours_raw:
        if len(c) < min_length:
            continue
        if epsilon > 0:
            approx = cv2.approxPolyDP(c, epsilon, closed=False)
        else:
            approx = c
        result.append(approx.reshape(-1, 2))

    return result
