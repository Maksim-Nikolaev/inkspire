"""Flatten bezier curves and elliptical arcs to point arrays."""

import numpy as np
from math import cos, sin, radians, sqrt, atan2, pi, ceil

__all__ = ["flatten_quadratic", "flatten_cubic", "flatten_arc", "arc_endpoint_to_center"]


def flatten_quadratic(p0, p1, p2, tolerance=0.5):
    """Flatten a quadratic bezier curve to a (N, 2) float64 array.

    p0, p1, p2: control points as (x, y) tuples or arrays.
    tolerance: max distance from true curve before subdividing.
    """
    p0, p1, p2 = np.array(p0, dtype=np.float64), np.array(p1, dtype=np.float64), np.array(p2, dtype=np.float64)
    points = [p0]
    _subdivide_quad(p0, p1, p2, tolerance, points)
    points.append(p2)
    return np.array(points, dtype=np.float64)


def _subdivide_quad(p0, p1, p2, tol, points):
    # Flatness test: distance from control point to midpoint of p0-p2
    mid = (p0 + p2) * 0.5
    if np.linalg.norm(p1 - mid) <= tol:
        return
    # De Casteljau split at t=0.5
    q0 = (p0 + p1) * 0.5
    q1 = (p1 + p2) * 0.5
    r = (q0 + q1) * 0.5
    _subdivide_quad(p0, q0, r, tol, points)
    points.append(r)
    _subdivide_quad(r, q1, p2, tol, points)


def flatten_cubic(p0, p1, p2, p3, tolerance=0.5):
    """Flatten a cubic bezier curve to a (N, 2) float64 array.

    p0, p1, p2, p3: control points as (x, y) tuples or arrays.
    tolerance: max distance from true curve before subdividing.
    """
    p0 = np.array(p0, dtype=np.float64)
    p1 = np.array(p1, dtype=np.float64)
    p2 = np.array(p2, dtype=np.float64)
    p3 = np.array(p3, dtype=np.float64)
    points = [p0]
    _subdivide_cubic(p0, p1, p2, p3, tolerance, points)
    points.append(p3)
    return np.array(points, dtype=np.float64)


def _subdivide_cubic(p0, p1, p2, p3, tol, points):
    # Flatness: max distance of control points from the line p0→p3
    d1 = _point_line_dist(p1, p0, p3)
    d2 = _point_line_dist(p2, p0, p3)
    if max(d1, d2) <= tol:
        return
    # De Casteljau split at t=0.5
    q0 = (p0 + p1) * 0.5
    q1 = (p1 + p2) * 0.5
    q2 = (p2 + p3) * 0.5
    r0 = (q0 + q1) * 0.5
    r1 = (q1 + q2) * 0.5
    s = (r0 + r1) * 0.5
    _subdivide_cubic(p0, q0, r0, s, tol, points)
    points.append(s)
    _subdivide_cubic(s, r1, q2, p3, tol, points)


def _point_line_dist(p, a, b):
    """Distance from point p to line segment a→b."""
    ab = b - a
    ab_len = np.linalg.norm(ab)
    if ab_len < 1e-12:
        return np.linalg.norm(p - a)
    return abs(np.cross(ab, a - p)) / ab_len


def flatten_arc(cx, cy, rx, ry, start_angle, sweep_angle, rotation=0.0, tolerance=0.5):
    """Flatten an elliptical arc to a (N, 2) float64 array.

    cx, cy: center of the ellipse.
    rx, ry: radii.
    start_angle, sweep_angle: in radians.
    rotation: ellipse rotation in radians.
    tolerance: controls point density.
    """
    if abs(sweep_angle) < 1e-12 or rx < 1e-12 or ry < 1e-12:
        return np.array([[cx + rx * cos(start_angle), cy + ry * sin(start_angle)]], dtype=np.float64)

    # Number of segments based on arc length approximation
    r_max = max(rx, ry)
    n_steps = max(4, int(ceil(abs(sweep_angle) * r_max / tolerance)))
    angles = np.linspace(start_angle, start_angle + sweep_angle, n_steps + 1)

    cos_rot = cos(rotation)
    sin_rot = sin(rotation)

    points = np.empty((len(angles), 2), dtype=np.float64)
    for i, a in enumerate(angles):
        ex = rx * cos(a)
        ey = ry * sin(a)
        points[i, 0] = cx + ex * cos_rot - ey * sin_rot
        points[i, 1] = cy + ex * sin_rot + ey * cos_rot

    return points


def arc_endpoint_to_center(x1, y1, rx, ry, phi, fa, fs, x2, y2):
    """Convert SVG endpoint arc parameters to center parameterization.

    Returns (cx, cy, start_angle, sweep_angle) or None if degenerate.
    """
    cos_phi = cos(phi)
    sin_phi = sin(phi)

    dx = (x1 - x2) / 2
    dy = (y1 - y2) / 2
    x1p = cos_phi * dx + sin_phi * dy
    y1p = -sin_phi * dx + cos_phi * dy

    rx = abs(rx)
    ry = abs(ry)

    # Scale radii if too small
    lam = (x1p ** 2) / (rx ** 2) + (y1p ** 2) / (ry ** 2)
    if lam > 1:
        s = sqrt(lam)
        rx *= s
        ry *= s

    num = max(0, rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2)
    den = rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2
    if den < 1e-12:
        return None
    sq = sqrt(num / den)
    if fa == fs:
        sq = -sq

    cxp = sq * rx * y1p / ry
    cyp = -sq * ry * x1p / rx

    cx = cos_phi * cxp - sin_phi * cyp + (x1 + x2) / 2
    cy = sin_phi * cxp + cos_phi * cyp + (y1 + y2) / 2

    def angle(ux, uy, vx, vy):
        dot = ux * vx + uy * vy
        cross = ux * vy - uy * vx
        return atan2(cross, dot)

    start = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    sweep = angle(
        (x1p - cxp) / rx, (y1p - cyp) / ry,
        (-x1p - cxp) / rx, (-y1p - cyp) / ry
    )

    if not fs and sweep > 0:
        sweep -= 2 * pi
    elif fs and sweep < 0:
        sweep += 2 * pi

    return cx, cy, start, sweep
