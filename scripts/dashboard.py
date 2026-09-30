from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "config" / "dashboard.yaml"
COLORS = ("#2563eb", "#0891b2", "#7c3aed", "#ea580c")


def percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _event_time(event: dict[str, Any]) -> datetime | None:
    value = event.get("ts")
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_events(path: Path, start: datetime, end: datetime) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        lines = path.open("r", encoding="utf-8")
    except FileNotFoundError:
        return events
    with lines:
        for line in lines:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            timestamp = _event_time(item)
            if timestamp is not None and start <= timestamp <= end:
                item["_timestamp"] = timestamp
                events.append(item)
    return events


def _number(event: dict[str, Any], field: str) -> float | None:
    value = event.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _minute_buckets(start: datetime, end: datetime) -> list[datetime]:
    last = end.replace(second=0, microsecond=0)
    first = last - timedelta(minutes=59)
    return [first + timedelta(minutes=offset) for offset in range(60)]


def _events_by_minute(events: list[dict[str, Any]]) -> dict[datetime, list[dict[str, Any]]]:
    result: dict[datetime, list[dict[str, Any]]] = {}
    for event in events:
        timestamp = event.get("_timestamp")
        if isinstance(timestamp, datetime):
            bucket = timestamp.replace(second=0, microsecond=0)
            result.setdefault(bucket, []).append(event)
    return result


def _metric_panel(
    panel: dict[str, Any], events: list[dict[str, Any]], buckets: list[datetime]
) -> dict[str, Any]:
    panel_id = panel["id"]
    threshold = panel["threshold"]
    secondary = panel.get("secondary_thresholds", [])
    by_minute = _events_by_minute(events)

    def field_values(rows: list[dict[str, Any]], field: str) -> list[float]:
        return [value for row in rows if (value := _number(row, field)) is not None]

    if panel_id == "latency":
        rows = [event for event in events if event.get("event") == "response_sent"]
        series = [
            {"name": "P50", "values": []},
            {"name": "P95", "values": []},
            {"name": "P99", "values": []},
            {"name": "TTFT P95", "values": []},
        ]
        for bucket in buckets:
            minute_rows = [row for row in by_minute.get(bucket, []) if row.get("event") == "response_sent"]
            latency = field_values(minute_rows, "latency_ms")
            ttft = field_values(minute_rows, "ttft_ms")
            for item, value in zip(
                series,
                (percentile(latency, 50), percentile(latency, 95), percentile(latency, 99), percentile(ttft, 95)),
            ):
                item["values"].append(value)
        latency = field_values(rows, "latency_ms")
        ttft = field_values(rows, "ttft_ms")
        summary = (
            f"P50 {_fmt(percentile(latency, 50), 'ms')} · P95 {_fmt(percentile(latency, 95), 'ms')} · "
            f"P99 {_fmt(percentile(latency, 99), 'ms')} · TTFT P95 {_fmt(percentile(ttft, 95), 'ms')}"
        )
    elif panel_id == "traffic":
        counts = [
            sum(row.get("event") == "request_received" for row in by_minute.get(bucket, []))
            for bucket in buckets
        ]
        total = sum(counts)
        series = [{"name": "Requests/min", "values": counts}]
        summary = f"{total} requests · peak {max(counts, default=0)} requests/min"
    elif panel_id == "errors":
        series = [{"name": "Error rate", "values": []}, {"name": "Retrieval success", "values": []}]
        for bucket in buckets:
            minute_rows = by_minute.get(bucket, [])
            received = sum(row.get("event") == "request_received" for row in minute_rows)
            failed = sum(row.get("event") == "request_failed" for row in minute_rows)
            tool_values = [row["tool_success"] for row in minute_rows if isinstance(row.get("tool_success"), bool)]
            series[0]["values"].append((failed / received * 100) if received else 0.0)
            series[1]["values"].append(
                (sum(tool_values) / len(tool_values) * 100) if tool_values else None
            )
        received = sum(event.get("event") == "request_received" for event in events)
        failed = sum(event.get("event") == "request_failed" for event in events)
        tool_values = [event["tool_success"] for event in events if isinstance(event.get("tool_success"), bool)]
        error_rate = failed / received * 100 if received else 0.0
        success_rate = sum(tool_values) / len(tool_values) * 100 if tool_values else None
        summary = f"Error rate {_fmt(error_rate, '%')} · retrieval success {_fmt(success_rate, '%')}"
    elif panel_id == "cost":
        rows = [event for event in events if event.get("event") == "response_sent"]
        totals = [
            sum(field_values([row for row in by_minute.get(bucket, []) if row.get("event") == "response_sent"], "cost_usd"))
            for bucket in buckets
        ]
        cumulative: list[float] = []
        running = 0.0
        for value in totals:
            running += value
            cumulative.append(running)
        total_cost = sum(field_values(rows, "cost_usd"))
        series = [{"name": "Cumulative cost", "values": cumulative}]
        summary = f"Total {_fmt(total_cost, 'USD')} · {len(rows)} completed requests"
    elif panel_id == "tokens":
        rows = [event for event in events if event.get("event") == "response_sent"]
        input_series: list[float] = []
        output_series: list[float] = []
        for bucket in buckets:
            minute_rows = [row for row in by_minute.get(bucket, []) if row.get("event") == "response_sent"]
            input_series.append(sum(field_values(minute_rows, "tokens_in")))
            output_series.append(sum(field_values(minute_rows, "tokens_out")))
        input_total = sum(field_values(rows, "tokens_in"))
        output_total = sum(field_values(rows, "tokens_out"))
        series = [{"name": "Input", "values": input_series}, {"name": "Output", "values": output_series}]
        summary = f"Input {input_total:,.0f} · output {output_total:,.0f} tokens"
    elif panel_id == "quality":
        rows = [event for event in events if event.get("event") == "response_sent"]
        series = [{"name": "Mean quality", "values": []}]
        for bucket in buckets:
            minute_rows = [row for row in by_minute.get(bucket, []) if row.get("event") == "response_sent"]
            values = field_values(minute_rows, "quality_score")
            series[0]["values"].append(mean(values) if values else None)
        scores = field_values(rows, "quality_score")
        summary = f"Mean score {_fmt(mean(scores) if scores else None, 'score / 1')} · {len(scores)} scored responses"
    else:
        series = []
        summary = "Unsupported panel"

    return {"series": series, "summary": summary, "threshold": threshold, "secondary": secondary}


def _fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "no data"
    if unit == "USD":
        return f"${value:.6f}"
    if unit == "%":
        return f"{value:.2f}%"
    if unit == "ms":
        return f"{value:.1f} ms"
    if unit == "score / 1":
        return f"{value:.3f} / 1"
    return f"{value:,.0f} {unit}"


def _threshold_label(item: dict[str, Any], unit: str) -> str:
    operator = "≤" if item["operator"] == "lte" else "≥"
    value = item["value"]
    if unit == "ms":
        value_text = f"{value:,.0f} ms"
    elif unit == "usd":
        value_text = f"${value:,.2f}"
    elif unit == "percent":
        value_text = f"{value:g}%"
    elif unit == "score_0_to_1":
        value_text = f"{value:g} / 1"
    elif unit == "requests_per_minute":
        value_text = f"{value:g} request/min"
    else:
        value_text = f"{value:,.0f} {unit}"
    return f"{operator} {value_text}"


def _segments(points: list[tuple[float, float] | None]) -> list[list[tuple[float, float]]]:
    result: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    for point in points:
        if point is None:
            if current:
                result.append(current)
                current = []
        else:
            current.append(point)
    if current:
        result.append(current)
    return result


def _svg_chart(
    series: list[dict[str, Any]], threshold: dict[str, Any], secondary: list[dict[str, Any]], unit: str, buckets: list[datetime]
) -> str:
    width, height = 760, 230
    left, right, top, bottom = 58, 18, 18, 38
    plot_width, plot_height = width - left - right, height - top - bottom
    values = [value for item in series for value in item["values"] if isinstance(value, (int, float))]
    values.extend([threshold["value"], *(item["value"] for item in secondary)])
    floor = min(0.0, min(values, default=0.0))
    ceiling = max(values, default=1.0)
    if unit == "score_0_to_1":
        floor, ceiling = 0.0, 1.0
    if ceiling <= floor:
        ceiling = floor + 1.0
    padding = (ceiling - floor) * 0.12
    y_min, y_max = floor, ceiling + padding

    def x_at(index: int) -> float:
        return left + (plot_width * index / max(1, len(buckets) - 1))

    def y_at(value: float) -> float:
        return top + plot_height * (y_max - value) / (y_max - y_min)

    parts = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Time series chart">']
    for step in range(4):
        fraction = step / 3
        y = top + fraction * plot_height
        label = y_max - fraction * (y_max - y_min)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" class="axis">{label:.2f}</text>')
    for index, label_index in ((0, 0), (29, 29), (59, 59)):
        x = x_at(index)
        label = buckets[label_index].strftime("%H:%M")
        parts.append(f'<text x="{x:.1f}" y="{height-10}" text-anchor="middle" class="axis">{label}</text>')

    for item, color, dash in [(threshold, "#dc2626", "6 4"), *[(item, "#ea580c", "3 4") for item in secondary]]:
        y = y_at(float(item["value"]))
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="{color}" stroke-width="2" stroke-dasharray="{dash}"/>')

    for index, item in enumerate(series):
        color = COLORS[index % len(COLORS)]
        points = [None if value is None else (x_at(point_index), y_at(float(value))) for point_index, value in enumerate(item["values"])]
        for segment in _segments(points):
            coordinates = " ".join(f"{x:.1f},{y:.1f}" for x, y in segment)
            parts.append(f'<polyline points="{coordinates}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')
    parts.append("</svg>")
    return "".join(parts)


def render_dashboard(config_path: Path, now: datetime | None = None) -> str:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))["dashboard"]
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    buckets = _minute_buckets(current, current)
    start = buckets[0]
    source = (REPO_ROOT / config["panels"][0]["source"]).resolve()
    events = _load_events(source, start, current)
    cards: list[str] = []
    for panel in config["panels"]:
        stats = _metric_panel(panel, events, buckets)
        unit = panel["unit"]
        display_unit = {
            "requests_per_minute": "requests/min",
            "score_0_to_1": "score (0-1)",
            "usd": "USD",
            "percent": "%",
        }.get(unit, unit)
        labels = [_threshold_label(stats["threshold"], unit)]
        labels.extend(_threshold_label(item, unit) for item in stats["secondary"])
        legend = "".join(
            f'<span><i style="background:{COLORS[index % len(COLORS)]}"></i>{escape(item["name"])}</span>'
            for index, item in enumerate(stats["series"])
        )
        threshold_legend = "".join(
            f'<span><i class="threshold-mark"></i>{escape(label)}</span>' for label in labels
        )
        chart = _svg_chart(stats["series"], stats["threshold"], stats["secondary"], unit, buckets)
        cards.append(
            f'<section class="panel"><div class="panel-head"><div><h2>{escape(panel["title"])}</h2>'
            f'<p>{escape(stats["summary"])}</p></div><span class="unit">{escape(display_unit)}</span></div>'
            f'{chart}<div class="legend">{legend}{threshold_legend}</div></section>'
        )

    updated = current.strftime("%Y-%m-%d %H:%M UTC")
    refresh = int(config["refresh_seconds"])
    title = escape(config["title"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{refresh}"><title>{title}</title>
<style>
:root{{color-scheme:light;--ink:#172033;--muted:#667085;--line:#e5eaf1;--paper:#f5f7fb}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:14px/1.45 Inter,Segoe UI,Arial,sans-serif}}
header{{padding:24px max(24px,calc((100vw - 1580px)/2));background:#fff;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:20px}}
h1{{font-size:22px;margin:0 0 4px}}header p{{margin:0;color:var(--muted)}}.stamp{{text-align:right;color:var(--muted);white-space:nowrap}}
main{{max-width:1630px;margin:auto;padding:20px 24px 36px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}}
.panel{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px 16px 12px;min-width:0;box-shadow:0 1px 2px #1018280a}}
.panel-head{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}}h2{{font-size:16px;margin:0 0 5px}}.panel-head p{{color:var(--muted);margin:0;min-height:21px}}.unit{{border-radius:6px;background:#f2f4f7;padding:4px 7px;color:#475467;font-size:11px;white-space:nowrap}}
.chart{{width:100%;height:auto;display:block;margin-top:10px}}.grid{{stroke:#e9edf3;stroke-width:1}}.axis{{fill:#7b8493;font-size:10px}}
.legend{{display:flex;gap:14px;flex-wrap:wrap;color:#596579;font-size:11px;padding:0 0 2px 56px}}.legend span{{display:inline-flex;align-items:center;gap:5px}}.legend i{{display:inline-block;width:10px;height:3px;border-radius:2px}}.legend .threshold-mark{{height:0;border-top:2px dashed #dc2626;background:transparent}}
footer{{text-align:center;padding:4px 24px 22px;color:#778195;font-size:12px}}
@media(max-width:900px){{main{{grid-template-columns:1fr;padding:14px}}header{{padding:18px 14px;align-items:flex-start;flex-direction:column}}.stamp{{text-align:left}}}}
</style></head><body><header><div><h1>{title}</h1><p>Log dashboard · last 60 minutes · UTC · refresh every {refresh}s</p></div>
<div class="stamp">Updated {updated}<br>Source: data/logs.jsonl</div></header><main>{''.join(cards)}</main>
<footer>Retrieval success includes every event with a boolean tool_success field. Dashboard thresholds follow config/dashboard.yaml.</footer></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the six-panel Day 13 log dashboard")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path not in ("/", "/index.html"):
                self.send_error(404)
                return
            payload = render_dashboard(args.config).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Dashboard: http://{args.host}:{args.port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
