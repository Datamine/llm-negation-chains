from __future__ import annotations

import math
from pathlib import Path
from xml.sax.saxutils import escape


SVG_NS = "http://www.w3.org/2000/svg"


def svg_output_path(path: Path) -> Path:
    return path.with_suffix(".svg") if path.suffix.lower() != ".svg" else path


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _write_svg(path: Path, width: int, height: int, body: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    svg = [
        f'<svg xmlns="{SVG_NS}" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        *body,
        "</svg>",
    ]
    path.write_text("\n".join(svg), encoding="utf-8")


def _draw_legend(
    *,
    body: list[str],
    labels: list[str],
    colors: dict[str, str],
    x: float,
    y: float,
    row_width: float,
) -> float:
    cursor_x = x
    cursor_y = y
    for label in labels:
        text_width = max(60, len(label) * 7)
        if cursor_x + text_width + 38 > row_width:
            cursor_x = x
            cursor_y += 22
        color = colors[label]
        body.append(
            f'<line x1="{cursor_x}" y1="{cursor_y}" x2="{cursor_x + 20}" y2="{cursor_y}" '
            f'stroke="{color}" stroke-width="3" stroke-linecap="round" />',
        )
        body.append(
            f'<circle cx="{cursor_x + 10}" cy="{cursor_y}" r="3" fill="{color}" />',
        )
        body.append(
            f'<text x="{cursor_x + 28}" y="{cursor_y + 4}" font-size="12" '
            f'font-family="sans-serif" fill="#1d2630">{escape(label)}</text>',
        )
        cursor_x += text_width + 42
    return cursor_y + 20


def _value_to_y(
    value: float,
    *,
    top: float,
    height: float,
    y_min: float,
    y_max: float,
    log_y: bool,
) -> float:
    if log_y:
        value = max(value, y_min)
        y_min_log = math.log10(y_min)
        y_max_log = math.log10(y_max)
        fraction = (math.log10(value) - y_min_log) / (y_max_log - y_min_log)
    else:
        fraction = (value - y_min) / (y_max - y_min)
    return top + height - (fraction * height)


def _draw_line_panel(
    *,
    body: list[str],
    panel_x: float,
    panel_y: float,
    panel_width: float,
    panel_height: float,
    title: str,
    ylabel: str,
    x_labels: list[str],
    series: list[tuple[str, list[float | None], str]],
    log_y: bool,
    fixed_y_range: tuple[float, float] | None = None,
) -> None:
    margin_left = 48
    margin_right = 16
    margin_top = 32
    margin_bottom = 56
    plot_x = panel_x + margin_left
    plot_y = panel_y + margin_top
    plot_width = panel_width - margin_left - margin_right
    plot_height = panel_height - margin_top - margin_bottom

    values = [
        value
        for _, points, _ in series
        for value in points
        if value is not None and (not log_y or value > 0)
    ]
    if fixed_y_range is not None:
        y_min, y_max = fixed_y_range
    elif log_y:
        y_min = max(1.0, min(values) if values else 1.0)
        y_max = max(values) if values else 10.0
        if y_min == y_max:
            y_max = y_min * 10.0
    else:
        y_min, y_max = (0.0, 100.0)

    body.append(
        f'<rect x="{panel_x}" y="{panel_y}" width="{panel_width}" height="{panel_height}" '
        f'rx="10" fill="#ffffff" stroke="#d6dee8" />',
    )
    body.append(
        f'<text x="{panel_x + panel_width / 2}" y="{panel_y + 20}" text-anchor="middle" '
        f'font-size="14" font-weight="600" font-family="sans-serif" fill="#1d2630">{escape(title)}</text>',
    )

    if log_y:
        tick_values = []
        min_exp = int(math.floor(math.log10(y_min)))
        max_exp = int(math.ceil(math.log10(y_max)))
        for exponent in range(min_exp, max_exp + 1):
            tick_values.append(float(10**exponent))
    else:
        tick_values = [0.0, 25.0, 50.0, 75.0, 100.0]

    for tick in tick_values:
        tick_y = _value_to_y(
            tick,
            top=plot_y,
            height=plot_height,
            y_min=y_min,
            y_max=y_max,
            log_y=log_y,
        )
        body.append(
            f'<line x1="{plot_x}" y1="{tick_y}" x2="{plot_x + plot_width}" y2="{tick_y}" '
            f'stroke="#ebeff5" stroke-width="1" />',
        )
        body.append(
            f'<text x="{plot_x - 8}" y="{tick_y + 4}" text-anchor="end" font-size="11" '
            f'font-family="sans-serif" fill="#5a6773">{escape(_format_number(tick))}</text>',
        )

    body.append(
        f'<line x1="{plot_x}" y1="{plot_y}" x2="{plot_x}" y2="{plot_y + plot_height}" stroke="#8fa0b4" />',
    )
    body.append(
        f'<line x1="{plot_x}" y1="{plot_y + plot_height}" x2="{plot_x + plot_width}" y2="{plot_y + plot_height}" stroke="#8fa0b4" />',
    )

    step = plot_width / max(1, len(x_labels) - 1)
    for index, label in enumerate(x_labels):
        x = plot_x + (index * step if len(x_labels) > 1 else plot_width / 2)
        body.append(
            f'<line x1="{x}" y1="{plot_y + plot_height}" x2="{x}" y2="{plot_y + plot_height + 4}" stroke="#8fa0b4" />',
        )
        body.append(
            f'<text x="{x}" y="{plot_y + plot_height + 18}" text-anchor="middle" font-size="10" '
            f'font-family="sans-serif" fill="#5a6773">{escape(label)}</text>',
        )

    for _, points, color in series:
        path_segments: list[str] = []
        for index, value in enumerate(points):
            if value is None or (log_y and value <= 0):
                continue
            x = plot_x + (index * step if len(x_labels) > 1 else plot_width / 2)
            y = _value_to_y(
                float(value),
                top=plot_y,
                height=plot_height,
                y_min=y_min,
                y_max=y_max,
                log_y=log_y,
            )
            command = "M" if not path_segments else "L"
            path_segments.append(f"{command} {x:.2f} {y:.2f}")
            body.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.8" fill="{color}" />')
        if path_segments:
            body.append(
                f'<path d="{" ".join(path_segments)}" fill="none" stroke="{color}" stroke-width="2.4" '
                'stroke-linecap="round" stroke-linejoin="round" />',
            )

    body.append(
        f'<text x="{panel_x + 14}" y="{panel_y + panel_height / 2}" transform="rotate(-90 {panel_x + 14} {panel_y + panel_height / 2})" '
        f'text-anchor="middle" font-size="11" font-family="sans-serif" fill="#5a6773">{escape(ylabel)}</text>',
    )


def render_line_chart(
    *,
    output_path: Path,
    title: str,
    ylabel: str,
    x_labels: list[str],
    series: list[tuple[str, list[float | None], str]],
    log_y: bool = False,
) -> Path:
    output_path = svg_output_path(output_path)
    width = 1000
    height = 620
    body: list[str] = [
        '<rect width="100%" height="100%" fill="#f6f8fb" />',
        f'<text x="{width / 2}" y="34" text-anchor="middle" font-size="22" font-weight="700" '
        f'font-family="sans-serif" fill="#17212b">{escape(title)}</text>',
    ]
    labels = [label for label, _, _ in series]
    colors = {label: color for label, _, color in series}
    legend_bottom = _draw_legend(body=body, labels=labels, colors=colors, x=40, y=62, row_width=width - 40)
    _draw_line_panel(
        body=body,
        panel_x=30,
        panel_y=legend_bottom + 6,
        panel_width=width - 60,
        panel_height=height - legend_bottom - 26,
        title="",
        ylabel=ylabel,
        x_labels=x_labels,
        series=series,
        log_y=log_y,
    )
    _write_svg(output_path, width, height, body)
    return output_path


def render_panel_line_charts(
    *,
    output_path: Path,
    title: str,
    panels: list[dict[str, object]],
    legend: list[tuple[str, str]],
) -> Path:
    output_path = svg_output_path(output_path)
    width = 1400
    height = 1200
    body: list[str] = [
        '<rect width="100%" height="100%" fill="#f6f8fb" />',
        f'<text x="{width / 2}" y="34" text-anchor="middle" font-size="24" font-weight="700" '
        f'font-family="sans-serif" fill="#17212b">{escape(title)}</text>',
    ]
    legend_bottom = _draw_legend(
        body=body,
        labels=[label for label, _ in legend],
        colors={label: color for label, color in legend},
        x=40,
        y=62,
        row_width=width - 40,
    )

    cols = 2
    rows = math.ceil(len(panels) / cols)
    gap_x = 24
    gap_y = 24
    panel_width = (width - 60 - gap_x) / cols
    panel_height = (height - legend_bottom - 40 - gap_y * (rows - 1)) / max(1, rows)

    for index, panel in enumerate(panels):
        row = index // cols
        col = index % cols
        panel_x = 20 + col * (panel_width + gap_x)
        panel_y = legend_bottom + 8 + row * (panel_height + gap_y)
        _draw_line_panel(
            body=body,
            panel_x=panel_x,
            panel_y=panel_y,
            panel_width=panel_width,
            panel_height=panel_height,
            title=str(panel["title"]),
            ylabel=str(panel["ylabel"]),
            x_labels=list(panel["x_labels"]),
            series=list(panel["series"]),
            log_y=bool(panel.get("log_y", False)),
            fixed_y_range=panel.get("fixed_y_range"),
        )

    _write_svg(output_path, width, height, body)
    return output_path


def render_heatmap(
    *,
    output_path: Path,
    title: str,
    row_labels: list[str],
    column_labels: list[str],
    matrix: list[list[float | None]],
) -> Path:
    output_path = svg_output_path(output_path)
    cell_width = 170
    cell_height = 56
    left_margin = 210
    top_margin = 110
    width = left_margin + cell_width * len(column_labels) + 40
    height = top_margin + cell_height * len(row_labels) + 70

    body: list[str] = [
        '<rect width="100%" height="100%" fill="#f6f8fb" />',
        f'<text x="{width / 2}" y="36" text-anchor="middle" font-size="24" font-weight="700" '
        f'font-family="sans-serif" fill="#17212b">{escape(title)}</text>',
    ]

    for index, label in enumerate(column_labels):
        x = left_margin + index * cell_width + cell_width / 2
        body.append(
            f'<text x="{x}" y="{top_margin - 18}" text-anchor="middle" font-size="12" font-family="sans-serif" '
            f'fill="#1d2630">{escape(label)}</text>',
        )

    for row_index, row_label in enumerate(row_labels):
        y = top_margin + row_index * cell_height + cell_height / 2
        body.append(
            f'<text x="{left_margin - 12}" y="{y + 4}" text-anchor="end" font-size="13" font-family="sans-serif" '
            f'fill="#1d2630">{escape(row_label)}</text>',
        )
        for col_index, value in enumerate(matrix[row_index]):
            x = left_margin + col_index * cell_width
            if value is None:
                fill = "#eef2f7"
                label = "n/a"
            else:
                intensity = max(0.0, min(1.0, float(value) / 100.0))
                blue = int(235 - intensity * 95)
                green = int(245 - intensity * 25)
                red = int(250 - intensity * 150)
                fill = f"rgb({red},{green},{blue})"
                label = f"{value:.1f}"
            body.append(
                f'<rect x="{x}" y="{top_margin + row_index * cell_height}" width="{cell_width - 8}" height="{cell_height - 8}" '
                f'rx="10" fill="{fill}" stroke="#d6dee8" />',
            )
            body.append(
                f'<text x="{x + (cell_width - 8) / 2}" y="{top_margin + row_index * cell_height + (cell_height - 8) / 2 + 5}" '
                f'text-anchor="middle" font-size="13" font-weight="600" font-family="sans-serif" fill="#10212b">{escape(label)}</text>',
            )

    _write_svg(output_path, width, height, body)
    return output_path
