"""Nearest-neighbor path optimization with optional contour reversal."""

import numpy as np

__all__ = ["optimize_path"]


def optimize_path(contours):
    if len(contours) <= 1:
        return list(contours), 0.0

    original_travel = _travel_distance(contours)

    remaining = list(range(len(contours)))
    ordered = []
    reversed_flags = {}

    # Start from contour closest to origin
    best_idx = min(remaining, key=lambda i: np.linalg.norm(contours[i][0]))
    ordered.append(best_idx)
    reversed_flags[best_idx] = False
    remaining.remove(best_idx)
    current_end = contours[best_idx][-1]

    while remaining:
        best_dist = float("inf")
        best_idx = remaining[0]
        best_reverse = False

        for i in remaining:
            d_start = np.linalg.norm(current_end - contours[i][0])
            d_end = np.linalg.norm(current_end - contours[i][-1])
            if d_start < best_dist:
                best_dist = d_start
                best_idx = i
                best_reverse = False
            if d_end < best_dist:
                best_dist = d_end
                best_idx = i
                best_reverse = True

        remaining.remove(best_idx)
        reversed_flags[best_idx] = best_reverse
        ordered.append(best_idx)
        c = contours[best_idx]
        current_end = c[0] if best_reverse else c[-1]

    result = [contours[i][::-1] if reversed_flags[i] else contours[i] for i in ordered]

    optimized_travel = _travel_distance(result)
    if original_travel > 0:
        reduction = (original_travel - optimized_travel) / original_travel
    else:
        reduction = 0.0

    return result, reduction


def _travel_distance(contours):
    dist = 0.0
    for i in range(1, len(contours)):
        dist += np.linalg.norm(contours[i][0] - contours[i - 1][-1])
    return dist
