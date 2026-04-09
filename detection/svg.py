"""Parse SVG files into contours (list of (N,2) float64 arrays)."""

import re
import numpy as np
import xml.etree.ElementTree as ET
from math import radians, cos, sin, sqrt, pi
from core.bezier import flatten_quadratic, flatten_cubic, flatten_arc, arc_endpoint_to_center

__all__ = ["load_svg"]


def load_svg(path: str, tolerance=0.5) -> list[np.ndarray]:
    """Parse an SVG file and return contours as list of (N, 2) float64 arrays."""
    tree = ET.parse(path)
    root = tree.getroot()
    ns = _get_namespace(root)

    # Parse viewBox for coordinate mapping
    vb = root.get("viewBox")
    vb_x, vb_y, vb_w, vb_h = 0, 0, 0, 0
    if vb:
        parts = re.split(r"[,\s]+", vb.strip())
        if len(parts) == 4:
            vb_x, vb_y, vb_w, vb_h = (float(p) for p in parts)

    contours = []
    _process_element(root, ns, np.eye(3), contours, tolerance)

    # Apply viewBox offset if present
    if vb_x != 0 or vb_y != 0:
        for i, c in enumerate(contours):
            contours[i] = c - np.array([vb_x, vb_y])

    return contours


def _get_namespace(root):
    tag = root.tag
    if tag.startswith("{"):
        return tag[1:tag.index("}")]
    return ""


def _tag(ns, name):
    return f"{{{ns}}}{name}" if ns else name


def _process_element(el, ns, parent_transform, contours, tol):
    transform = parent_transform @ _parse_transform(el.get("transform", ""))

    tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag

    if tag == "path":
        d = el.get("d", "")
        if d:
            paths = _parse_path_d(d, tol)
            for path in paths:
                if len(path) >= 2:
                    contours.append(_apply_transform(path, transform))

    elif tag == "line":
        x1, y1 = float(el.get("x1", 0)), float(el.get("y1", 0))
        x2, y2 = float(el.get("x2", 0)), float(el.get("y2", 0))
        pts = np.array([[x1, y1], [x2, y2]], dtype=np.float64)
        contours.append(_apply_transform(pts, transform))

    elif tag == "polyline" or tag == "polygon":
        raw = el.get("points", "")
        coords = re.findall(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?", raw)
        if len(coords) >= 4:
            pts = np.array([(float(coords[i]), float(coords[i+1]))
                           for i in range(0, len(coords) - 1, 2)], dtype=np.float64)
            if tag == "polygon" and len(pts) >= 2:
                pts = np.vstack([pts, pts[:1]])
            contours.append(_apply_transform(pts, transform))

    elif tag == "rect":
        x, y = float(el.get("x", 0)), float(el.get("y", 0))
        w, h = float(el.get("width", 0)), float(el.get("height", 0))
        rx_attr = el.get("rx")
        ry_attr = el.get("ry")
        rx = float(rx_attr) if rx_attr else 0
        ry = float(ry_attr) if ry_attr else 0
        if rx and not ry_attr:
            ry = rx
        if ry and not rx_attr:
            rx = ry
        rx = min(rx, w / 2)
        ry = min(ry, h / 2)

        if rx > 0 and ry > 0:
            # Rounded rectangle
            segs = []
            # Top-right corner
            segs.append(np.array([[x + rx, y]]))
            segs.append(np.array([[x + w - rx, y]]))
            arc = flatten_arc(x + w - rx, y + ry, rx, ry, -pi/2, pi/2, tolerance=tol)
            segs.append(arc)
            # Right side + bottom-right
            segs.append(np.array([[x + w, y + h - ry]]))
            arc = flatten_arc(x + w - rx, y + h - ry, rx, ry, 0, pi/2, tolerance=tol)
            segs.append(arc)
            # Bottom side + bottom-left
            segs.append(np.array([[x + rx, y + h]]))
            arc = flatten_arc(x + rx, y + h - ry, rx, ry, pi/2, pi/2, tolerance=tol)
            segs.append(arc)
            # Left side + top-left
            segs.append(np.array([[x, y + ry]]))
            arc = flatten_arc(x + rx, y + ry, rx, ry, pi, pi/2, tolerance=tol)
            segs.append(arc)
            pts = np.vstack(segs)
            pts = np.vstack([pts, pts[:1]])
        else:
            pts = np.array([
                [x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]
            ], dtype=np.float64)
        contours.append(_apply_transform(pts, transform))

    elif tag == "circle":
        cx, cy = float(el.get("cx", 0)), float(el.get("cy", 0))
        r = float(el.get("r", 0))
        if r > 0:
            pts = flatten_arc(cx, cy, r, r, 0, 2 * pi, tolerance=tol)
            pts = np.vstack([pts, pts[:1]])
            contours.append(_apply_transform(pts, transform))

    elif tag == "ellipse":
        cx, cy = float(el.get("cx", 0)), float(el.get("cy", 0))
        rx, ry = float(el.get("rx", 0)), float(el.get("ry", 0))
        if rx > 0 and ry > 0:
            pts = flatten_arc(cx, cy, rx, ry, 0, 2 * pi, tolerance=tol)
            pts = np.vstack([pts, pts[:1]])
            contours.append(_apply_transform(pts, transform))

    # Recurse into children (handles <g> groups and nested elements)
    for child in el:
        _process_element(child, ns, transform, contours, tol)


def _apply_transform(pts, matrix):
    if np.allclose(matrix, np.eye(3)):
        return pts
    n = len(pts)
    homogeneous = np.ones((n, 3), dtype=np.float64)
    homogeneous[:, :2] = pts
    transformed = (matrix @ homogeneous.T).T
    return transformed[:, :2].copy()


def _parse_transform(attr):
    """Parse SVG transform attribute into a 3x3 matrix."""
    if not attr:
        return np.eye(3)

    result = np.eye(3)
    for match in re.finditer(r"(\w+)\s*\(([^)]+)\)", attr):
        name = match.group(1)
        vals = [float(v) for v in re.findall(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?", match.group(2))]
        m = np.eye(3)

        if name == "translate":
            m[0, 2] = vals[0]
            m[1, 2] = vals[1] if len(vals) > 1 else 0
        elif name == "scale":
            m[0, 0] = vals[0]
            m[1, 1] = vals[1] if len(vals) > 1 else vals[0]
        elif name == "rotate":
            a = radians(vals[0])
            if len(vals) == 3:
                cx, cy = vals[1], vals[2]
                t1 = np.eye(3); t1[0, 2] = cx; t1[1, 2] = cy
                t2 = np.eye(3); t2[0, 2] = -cx; t2[1, 2] = -cy
                r = np.eye(3)
                r[0, 0] = cos(a); r[0, 1] = -sin(a)
                r[1, 0] = sin(a); r[1, 1] = cos(a)
                m = t1 @ r @ t2
            else:
                m[0, 0] = cos(a); m[0, 1] = -sin(a)
                m[1, 0] = sin(a); m[1, 1] = cos(a)
        elif name == "matrix":
            if len(vals) == 6:
                m[0, 0], m[1, 0], m[0, 1], m[1, 1], m[0, 2], m[1, 2] = vals
        elif name == "skewX":
            from math import tan
            m[0, 1] = tan(radians(vals[0]))
        elif name == "skewY":
            from math import tan
            m[1, 0] = tan(radians(vals[0]))

        result = result @ m

    return result


# ── SVG path d-attribute parser ──

_CMD_RE = re.compile(r"([MmZzLlHhVvCcSsQqTtAa])")
_NUM_RE = re.compile(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?")


def _parse_path_d(d, tol):
    """Parse an SVG path d attribute into list of point arrays."""
    tokens = _CMD_RE.split(d)
    # tokens alternates between gaps and commands
    commands = []
    for t in tokens:
        t = t.strip()
        if not t:
            continue
        if _CMD_RE.fullmatch(t):
            commands.append((t, []))
        elif commands:
            nums = [float(n) for n in _NUM_RE.findall(t)]
            commands[-1][1].extend(nums)

    paths = []
    current_path = []
    cx, cy = 0.0, 0.0  # current point
    sx, sy = 0.0, 0.0  # subpath start
    last_ctrl = None    # for S/T shorthand
    last_cmd = None

    for cmd, nums in commands:
        rel = cmd.islower()
        C = cmd.upper()

        if C == "M":
            if current_path:
                paths.append(np.array(current_path, dtype=np.float64))
            # First pair is moveto, subsequent are implicit lineto
            i = 0
            while i + 1 < len(nums):
                x, y = nums[i], nums[i + 1]
                if rel and i > 0:
                    x += cx; y += cy
                elif rel and i == 0:
                    x += cx; y += cy
                cx, cy = x, y
                if i == 0:
                    sx, sy = cx, cy
                    current_path = [(cx, cy)]
                else:
                    current_path.append((cx, cy))
                i += 2

        elif C == "L":
            i = 0
            while i + 1 < len(nums):
                x, y = nums[i], nums[i + 1]
                if rel: x += cx; y += cy
                cx, cy = x, y
                current_path.append((cx, cy))
                i += 2

        elif C == "H":
            for val in nums:
                x = val + cx if rel else val
                cx = x
                current_path.append((cx, cy))

        elif C == "V":
            for val in nums:
                y = val + cy if rel else val
                cy = y
                current_path.append((cx, cy))

        elif C == "C":
            i = 0
            while i + 5 < len(nums):
                x1, y1 = nums[i], nums[i+1]
                x2, y2 = nums[i+2], nums[i+3]
                x, y = nums[i+4], nums[i+5]
                if rel:
                    x1 += cx; y1 += cy; x2 += cx; y2 += cy; x += cx; y += cy
                pts = flatten_cubic((cx, cy), (x1, y1), (x2, y2), (x, y), tol)
                current_path.extend(pts[1:].tolist())
                last_ctrl = (x2, y2)
                cx, cy = x, y
                i += 6

        elif C == "S":
            i = 0
            while i + 3 < len(nums):
                # Reflected control point
                if last_cmd in ("C", "c", "S", "s") and last_ctrl:
                    x1 = 2 * cx - last_ctrl[0]
                    y1 = 2 * cy - last_ctrl[1]
                else:
                    x1, y1 = cx, cy
                x2, y2 = nums[i], nums[i+1]
                x, y = nums[i+2], nums[i+3]
                if rel:
                    x2 += cx; y2 += cy; x += cx; y += cy
                pts = flatten_cubic((cx, cy), (x1, y1), (x2, y2), (x, y), tol)
                current_path.extend(pts[1:].tolist())
                last_ctrl = (x2, y2)
                cx, cy = x, y
                i += 4

        elif C == "Q":
            i = 0
            while i + 3 < len(nums):
                x1, y1 = nums[i], nums[i+1]
                x, y = nums[i+2], nums[i+3]
                if rel:
                    x1 += cx; y1 += cy; x += cx; y += cy
                pts = flatten_quadratic((cx, cy), (x1, y1), (x, y), tol)
                current_path.extend(pts[1:].tolist())
                last_ctrl = (x1, y1)
                cx, cy = x, y
                i += 4

        elif C == "T":
            i = 0
            while i + 1 < len(nums):
                if last_cmd in ("Q", "q", "T", "t") and last_ctrl:
                    x1 = 2 * cx - last_ctrl[0]
                    y1 = 2 * cy - last_ctrl[1]
                else:
                    x1, y1 = cx, cy
                x, y = nums[i], nums[i+1]
                if rel:
                    x += cx; y += cy
                pts = flatten_quadratic((cx, cy), (x1, y1), (x, y), tol)
                current_path.extend(pts[1:].tolist())
                last_ctrl = (x1, y1)
                cx, cy = x, y
                i += 2

        elif C == "A":
            i = 0
            while i + 6 < len(nums):
                rx_a, ry_a = nums[i], nums[i+1]
                phi = radians(nums[i+2])
                fa = int(nums[i+3])
                fs = int(nums[i+4])
                x, y = nums[i+5], nums[i+6]
                if rel:
                    x += cx; y += cy
                result = arc_endpoint_to_center(cx, cy, rx_a, ry_a, phi, fa, fs, x, y)
                if result:
                    acx, acy, start, sweep = result
                    pts = flatten_arc(acx, acy, abs(rx_a), abs(ry_a), start, sweep, phi, tol)
                    current_path.extend(pts[1:].tolist())
                else:
                    current_path.append((x, y))
                cx, cy = x, y
                i += 7

        elif C == "Z":
            if current_path:
                current_path.append((sx, sy))
                cx, cy = sx, sy

        last_cmd = cmd

    if current_path:
        paths.append(np.array(current_path, dtype=np.float64))

    return paths
