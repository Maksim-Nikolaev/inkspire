"""Convert text + font into contours (list of (N,2) float64 arrays)."""

import numpy as np
from core.bezier import flatten_quadratic, flatten_cubic

__all__ = ["render_text"]


def render_text(text: str, font_path: str, font_size: float,
                max_width: float | None = None,
                line_spacing: float = 1.2) -> list[np.ndarray]:
    """Convert text to contours using the given font.

    Args:
        text: Input string. Newlines create manual line breaks.
        font_path: Path to a .ttf or .otf font file.
        font_size: Font size in pixels (em-height).
        max_width: If set, auto-wrap lines exceeding this width (in pixels).
        line_spacing: Line height multiplier (1.0 = tight, 1.2 = normal).

    Returns:
        List of (N, 2) float64 arrays, one per glyph contour.
    """
    from fontTools.ttLib import TTFont

    font = TTFont(font_path)
    upem = font["head"].unitsPerEm
    scale = font_size / upem

    # Get metrics
    if "OS/2" in font:
        ascent = font["OS/2"].sTypoAscender
        descent = abs(font["OS/2"].sTypoDescender)
    elif "hhea" in font:
        ascent = font["hhea"].ascent
        descent = abs(font["hhea"].descent)
    else:
        ascent = upem * 0.8
        descent = upem * 0.2

    line_height = (ascent + descent) * line_spacing * scale
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    kern_table = _load_kern(font)

    # Layout: split into lines, handle wrapping
    raw_lines = text.split("\n")
    lines = []
    for raw_line in raw_lines:
        if max_width and raw_line.strip():
            wrapped = _wrap_line(raw_line, cmap, hmtx, kern_table, scale, max_width)
            lines.extend(wrapped)
        else:
            lines.append(raw_line)

    # Extract glyphs
    contours = []
    y_offset = ascent * scale  # Start from baseline of first line

    is_cff = "CFF " in font

    for line in lines:
        x_cursor = 0.0
        prev_glyph = None

        for char in line:
            cp = ord(char)
            if cp not in cmap:
                # Try space advance
                if char == " ":
                    glyph_name = cmap.get(32)
                    if glyph_name:
                        advance, _ = hmtx[glyph_name]
                        x_cursor += advance * scale
                    else:
                        x_cursor += font_size * 0.25
                prev_glyph = None
                continue

            glyph_name = cmap[cp]
            advance, lsb = hmtx[glyph_name]

            # Kerning
            if prev_glyph and kern_table:
                kern_val = kern_table.get((prev_glyph, glyph_name), 0)
                x_cursor += kern_val * scale

            # Extract glyph contours
            glyph_contours = _extract_glyph(font, glyph_name, is_cff)
            for gc in glyph_contours:
                # Scale and position: flip Y (font coords are Y-up)
                positioned = gc.copy()
                positioned[:, 0] = positioned[:, 0] * scale + x_cursor
                positioned[:, 1] = -positioned[:, 1] * scale + y_offset
                if len(positioned) >= 2:
                    contours.append(positioned)

            x_cursor += advance * scale
            prev_glyph = glyph_name

        y_offset += line_height

    font.close()
    return contours


def _load_kern(font):
    """Load kerning pairs from kern or GPOS table."""
    pairs = {}
    if "kern" in font:
        try:
            kern = font["kern"]
            for table in kern.kernTables:
                if hasattr(table, "kernTable"):
                    for (left, right), val in table.kernTable.items():
                        pairs[(left, right)] = val
        except Exception:
            pass
    return pairs if pairs else None


def _wrap_line(line, cmap, hmtx, kern_table, scale, max_width):
    """Word-wrap a line to fit within max_width."""
    words = line.split(" ")
    lines = []
    current = ""
    current_width = 0.0
    space_width = _measure_text(" ", cmap, hmtx, kern_table, scale)

    for word in words:
        word_width = _measure_text(word, cmap, hmtx, kern_table, scale)
        if current and current_width + space_width + word_width > max_width:
            lines.append(current)
            current = word
            current_width = word_width
        else:
            if current:
                current += " " + word
                current_width += space_width + word_width
            else:
                current = word
                current_width = word_width

    if current:
        lines.append(current)
    return lines if lines else [""]


def _measure_text(text, cmap, hmtx, kern_table, scale):
    """Measure the width of a text string in pixels."""
    width = 0.0
    prev = None
    for char in text:
        cp = ord(char)
        if cp not in cmap:
            if char == " ":
                gn = cmap.get(32)
                if gn:
                    width += hmtx[gn][0] * scale
            prev = None
            continue
        gn = cmap[cp]
        if prev and kern_table:
            width += kern_table.get((prev, gn), 0) * scale
        width += hmtx[gn][0] * scale
        prev = gn
    return width


def _extract_glyph(font, glyph_name, is_cff, tolerance=0.5):
    """Extract contour arrays from a single glyph."""
    if is_cff:
        return _extract_cff_glyph(font, glyph_name, tolerance)
    else:
        return _extract_ttf_glyph(font, glyph_name, tolerance)


def _extract_ttf_glyph(font, glyph_name, tolerance):
    """Extract contours from a TrueType glyph (quadratic beziers)."""
    glyf_table = font["glyf"]
    if glyph_name not in glyf_table:
        return []
    glyph = glyf_table[glyph_name]
    if glyph is None or not hasattr(glyph, "numberOfContours"):
        return []

    # Decompose composite glyphs
    if glyph.isComposite():
        glyph = _decompose_composite(glyf_table, glyph_name)
        if glyph is None:
            return []

    if not hasattr(glyph, "coordinates") or not glyph.coordinates:
        return []

    coords = list(glyph.coordinates)
    flags = list(glyph.flags)
    end_pts = list(glyph.endPtsOfContours)

    contours = []
    start = 0
    for end in end_pts:
        c_coords = coords[start:end + 1]
        c_flags = flags[start:end + 1]
        pts = _ttf_contour_to_points(c_coords, c_flags, tolerance)
        if len(pts) >= 2:
            # Close the contour
            pts = np.vstack([pts, pts[:1]])
            contours.append(pts)
        start = end + 1

    return contours


def _decompose_composite(glyf_table, glyph_name):
    """Recursively decompose a composite glyph."""
    from fontTools.pens.recordingPen import RecordingPen
    from fontTools.pens.pointPen import SegmentToPointPen

    try:
        glyph = glyf_table[glyph_name]
        if not glyph.isComposite():
            return glyph

        # Use fonttools' built-in decomposition
        from fontTools.pens.t2Pen import T2Pen
        coords, end_pts, flags_list = [], [], []

        for component in glyph.components:
            comp_glyph = _decompose_composite(glyf_table, component.glyphName)
            if comp_glyph is None or not hasattr(comp_glyph, "coordinates"):
                continue

            # Apply component transform
            xx, xy, yx, yy = 1, 0, 0, 1
            dx, dy = 0, 0
            if hasattr(component, "transform"):
                (xx, xy), (yx, yy) = component.transform if component.transform else ((1, 0), (0, 1))
            if hasattr(component, "x"):
                dx = component.x
            if hasattr(component, "y"):
                dy = component.y

            offset = len(coords)
            for x, y in comp_glyph.coordinates:
                nx = xx * x + yx * y + dx
                ny = xy * x + yy * y + dy
                coords.append((int(nx), int(ny)))
            flags_list.extend(comp_glyph.flags)
            for ep in comp_glyph.endPtsOfContours:
                end_pts.append(ep + offset)

        if not coords:
            return None

        # Build a simple glyph-like object
        class SimpleGlyph:
            pass
        sg = SimpleGlyph()
        sg.numberOfContours = len(end_pts)
        sg.coordinates = coords
        sg.flags = flags_list
        sg.endPtsOfContours = end_pts
        return sg

    except Exception:
        return None


def _ttf_contour_to_points(coords, flags, tolerance):
    """Convert TrueType on/off curve points to flattened point array.

    TrueType uses quadratic beziers. On-curve points have flag bit 0 set.
    Two consecutive off-curve points imply an on-curve midpoint.
    """
    n = len(coords)
    if n == 0:
        return np.empty((0, 2), dtype=np.float64)

    # First, expand implied on-curve points
    expanded = []
    for i in range(n):
        on_curve = bool(flags[i] & 1)
        x, y = coords[i]
        if not on_curve and expanded and not expanded[-1][2]:
            # Two consecutive off-curve: insert midpoint
            px, py = expanded[-1][0], expanded[-1][1]
            mx, my = (px + x) / 2, (py + y) / 2
            expanded.append((mx, my, True))
        expanded.append((x, y, on_curve))

    # Handle wrap-around: if first point is off-curve
    if expanded and not expanded[0][2]:
        if expanded[-1][2]:
            # Use last on-curve as start
            expanded.insert(0, expanded.pop())
        else:
            # Both off-curve: insert midpoint
            mx = (expanded[0][0] + expanded[-1][0]) / 2
            my = (expanded[0][1] + expanded[-1][1]) / 2
            expanded.insert(0, (mx, my, True))

    points = []
    i = 0
    while i < len(expanded):
        x, y, on = expanded[i]
        if on:
            points.append((x, y))
            i += 1
        else:
            # Should not happen if expansion is correct, but handle gracefully
            points.append((x, y))
            i += 1

    # Now rebuild with bezier flattening
    result = []
    i = 0
    while i < len(expanded):
        ex, ey, eon = expanded[i]
        if eon:
            if i + 2 < len(expanded) and not expanded[i + 1][2]:
                # On - Off - On/Off sequence: quadratic bezier
                cx, cy, _ = expanded[i + 1]
                if i + 2 < len(expanded) and expanded[i + 2][2]:
                    nx, ny, _ = expanded[i + 2]
                    pts = flatten_quadratic((ex, ey), (cx, cy), (nx, ny), tolerance)
                    result.extend(pts[:-1].tolist())
                    i += 2
                else:
                    result.append((ex, ey))
                    i += 1
            else:
                result.append((ex, ey))
                i += 1
        else:
            result.append((ex, ey))
            i += 1

    if not result:
        return np.empty((0, 2), dtype=np.float64)
    return np.array(result, dtype=np.float64)


def _extract_cff_glyph(font, glyph_name, tolerance):
    """Extract contours from a CFF glyph (cubic beziers)."""
    try:
        from fontTools.pens.recordingPen import RecordingPen
        glyphset = font.getGlyphSet()
        pen = RecordingPen()
        glyphset[glyph_name].draw(pen)
    except Exception:
        return []

    contours = []
    current = []
    cx, cy = 0.0, 0.0

    for op, args in pen.value:
        if op == "moveTo":
            if current and len(current) >= 2:
                contours.append(np.array(current, dtype=np.float64))
            (cx, cy), = args
            current = [(cx, cy)]
        elif op == "lineTo":
            (cx, cy), = args
            current.append((cx, cy))
        elif op == "curveTo":
            # args is list of points: control1, control2, ..., endpoint
            # For cubic: 3 points (c1, c2, end)
            if len(args) == 3:
                pts = flatten_cubic((cx, cy), args[0], args[1], args[2], tolerance)
                current.extend(pts[1:].tolist())
                cx, cy = args[-1]
            else:
                # Multiple cubics chained
                i = 0
                while i + 2 < len(args):
                    pts = flatten_cubic((cx, cy), args[i], args[i+1], args[i+2], tolerance)
                    current.extend(pts[1:].tolist())
                    cx, cy = args[i+2]
                    i += 3
        elif op == "qCurveTo":
            # Quadratic: args has control points + endpoint
            if len(args) == 2:
                pts = flatten_quadratic((cx, cy), args[0], args[1], tolerance)
                current.extend(pts[1:].tolist())
                cx, cy = args[-1]
            else:
                # TrueType-style implicit on-curves in CFF2
                for i in range(len(args) - 1):
                    if i < len(args) - 2:
                        # Implied on-curve midpoint
                        mid_x = (args[i][0] + args[i+1][0]) / 2
                        mid_y = (args[i][1] + args[i+1][1]) / 2
                        pts = flatten_quadratic((cx, cy), args[i], (mid_x, mid_y), tolerance)
                        current.extend(pts[1:].tolist())
                        cx, cy = mid_x, mid_y
                    else:
                        pts = flatten_quadratic((cx, cy), args[i], args[i+1], tolerance)
                        current.extend(pts[1:].tolist())
                        cx, cy = args[-1]
        elif op == "closePath" or op == "endPath":
            if current and len(current) >= 2:
                if op == "closePath":
                    current.append(current[0])
                contours.append(np.array(current, dtype=np.float64))
            current = []

    if current and len(current) >= 2:
        contours.append(np.array(current, dtype=np.float64))

    return contours
