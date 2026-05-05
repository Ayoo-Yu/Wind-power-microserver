"""Download monitoring dashboard.

Serves a real-time web dashboard at http://localhost:8501 showing
download progress across all products with calendar heatmap view.

Usage:
    python -m src.monitor
    python -m src.monitor --port 8080
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
FEATURES_DIR = Path(__file__).parent.parent / "data" / "features"
CONFIG_DIR = Path(__file__).parent.parent / "config"
LOG_DIR = Path(__file__).parent.parent / "logs"

PRODUCTS = {
    "hres": {"pattern": "hres_{date}_{cycle}z", "cycles": ["00", "06", "12", "18"]},
    "hres_pl": {"pattern": "hres_pl_{date}_{cycle}z", "cycles": ["00", "06", "12", "18"]},
    "era5": {"pattern": "era5_sfc_all_{date}", "cycles": None},
    "era5_pl": {"pattern": "era5_pl_{date}", "cycles": None},
    "ens": {"pattern": "ens_{date}_00z", "cycles": ["00"]},
    "ens_pl": {"pattern": "ens_pl_{date}_00z", "cycles": ["00"]},
}

# Expected file sizes (MB) for status coloring
# Below minimum = likely incomplete/old format
SIZE_THRESHOLDS = {
    "hres": {"min_mb": 50, "good_mb": 200},
    "hres_pl": {"min_mb": 10, "good_mb": 40},
    "era5": {"min_mb": 1, "good_mb": 2},
    "era5_pl": {"min_mb": 5, "good_mb": 15},
    "ens": {"min_mb": 50, "good_mb": 200},
    "ens_pl": {"min_mb": 20, "good_mb": 80},
}


def scan_raw_files() -> dict:
    """Scan raw data directories and collect file info."""
    result = {}
    for product in PRODUCTS:
        product_dir = RAW_DIR / product
        if not product_dir.exists():
            result[product] = []
            continue

        files = []
        for f in sorted(product_dir.glob("*.nc")):
            if f.name.startswith("test_") or f.name.startswith("_"):
                continue
            stat = f.stat()
            files.append({
                "name": f.name,
                "size_mb": round(stat.st_size / 1e6, 1),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            })
        result[product] = files
    return result


def scan_processed_files() -> dict:
    """Scan processed parquet directories."""
    result = {}
    for product in PRODUCTS:
        product_dir = PROCESSED_DIR / product
        if not product_dir.exists():
            result[product] = []
            continue
        files = []
        for f in sorted(product_dir.glob("*.parquet")):
            if f.name.startswith("test_") or f.name.startswith("_"):
                continue
            stat = f.stat()
            files.append({
                "name": f.name,
                "size_mb": round(stat.st_size / 1e6, 1),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            })
        result[product] = files
    return result


def scan_features() -> dict:
    """Scan features output."""
    result = {}
    if not FEATURES_DIR.exists():
        return result
    for f in FEATURES_DIR.glob("*/*.parquet"):
        stat = f.stat()
        result[f.name] = {
            "size_mb": round(stat.st_size / 1e6, 1),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        }
    return result


def parse_file_dates(files: list[dict], product: str) -> dict:
    """Parse dates and cycles from filenames. Groups chunks by date+cycle.

    Returns {date: {cycle: {"size_mb": total, "chunks": int, "modified": str}}}.
    """
    dates = {}
    for f in files:
        name = f["name"]
        if product in ("hres", "hres_pl", "ens", "ens_pl"):
            m = re.search(r"(\d{8})_(\d{2})z", name)
            if m:
                date, cycle = m.group(1), m.group(2)
                key = (date, cycle)
                if key not in dates:
                    dates[key] = {"size_mb": 0, "chunks": 0, "modified": f["modified"]}
                dates[key]["size_mb"] += f["size_mb"]
                dates[key]["chunks"] += 1
        else:
            m = re.search(r"(\d{8})", name)
            if m:
                dates[(m.group(1), "daily")] = {
                    "size_mb": f["size_mb"], "chunks": 1, "modified": f["modified"]
                }

    result = {}
    for (date, cycle), info in dates.items():
        result.setdefault(date, {})[cycle] = info
    return result


def get_status(file_info: dict | None, product: str) -> str:
    """Determine file status based on size thresholds."""
    if not file_info:
        return "missing"
    size = file_info["size_mb"]
    thresholds = SIZE_THRESHOLDS.get(product, {"min_mb": 0, "good_mb": 0})
    if size >= thresholds["good_mb"]:
        return "complete"
    elif size >= thresholds["min_mb"]:
        return "partial"
    else:
        return "incomplete"


def build_status_json() -> dict:
    """Build complete status JSON for the dashboard."""
    raw = scan_raw_files()
    processed = scan_processed_files()
    features = scan_features()

    summary = {}
    for product in PRODUCTS:
        raw_files = raw.get(product, [])
        proc_files = processed.get(product, [])
        raw_dates = parse_file_dates(raw_files, product)
        proc_dates = parse_file_dates(proc_files, product)

        all_dates = sorted(set(list(raw_dates.keys()) + list(proc_dates.keys())))
        product_info = PRODUCTS[product]
        cycles = product_info["cycles"] or ["daily"]

        grid = []
        for date_str in all_dates:
            date_display = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            row = {"date": date_display, "date_raw": date_str, "cycles": {}}
            for cycle in cycles:
                rf = raw_dates.get(date_str, {}).get(cycle)
                pf = proc_dates.get(date_str, {}).get(cycle)
                # Adapt old single-file format vs new chunk-grouped format
                raw_info = rf
                if rf and "chunks" in rf:
                    raw_info = {**rf, "size_mb": round(rf["size_mb"], 1)}
                row["cycles"][cycle] = {
                    "raw": raw_info,
                    "processed": pf,
                    "status": get_status(rf, product),
                    "chunks": rf.get("chunks", 0) if rf else 0,
                }
            grid.append(row)

        total_raw_mb = sum(f["size_mb"] for f in raw_files)
        total_proc_mb = sum(f["size_mb"] for f in proc_files)
        n_complete = sum(
            1 for d in all_dates
            for c in cycles
            if get_status(raw_dates.get(d, {}).get(c), product) == "complete"
        )
        n_total = len(all_dates) * len(cycles) if all_dates else 0

        summary[product] = {
            "grid": grid,
            "raw_count": len(raw_files),
            "proc_count": len(proc_files),
            "raw_mb": round(total_raw_mb, 1),
            "proc_mb": round(total_proc_mb, 1),
            "complete": n_complete,
            "total": n_total,
            "pct": round(n_complete / n_total * 100, 1) if n_total > 0 else 0,
        }

    return {
        "updated": datetime.now().isoformat(timespec="seconds"),
        "products": summary,
        "features": features,
    }


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MARS Download Monitor</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, 'Segoe UI', sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }
  h1 { color: #58a6ff; margin-bottom: 4px; font-size: 1.4em; }
  .subtitle { color: #8b949e; margin-bottom: 20px; font-size: 0.85em; }
  .product-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; margin-bottom: 16px; overflow: hidden; }
  .product-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-bottom: 1px solid #30363d; }
  .product-name { font-weight: 600; font-size: 1.1em; color: #f0f6fc; }
  .product-stats { display: flex; gap: 20px; font-size: 0.85em; color: #8b949e; }
  .product-stats span { white-space: nowrap; }
  .progress-bar { height: 3px; background: #21262d; }
  .progress-fill { height: 100%; background: #3fb950; transition: width 0.5s; }
  .grid-container { padding: 12px 16px; overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; min-width: 500px; }
  th { color: #8b949e; font-weight: 500; text-align: center; padding: 4px 8px; font-size: 0.8em; border-bottom: 1px solid #21262d; }
  td { text-align: center; padding: 3px 6px; font-size: 0.82em; }
  td.date { text-align: right; color: #8b949e; font-family: monospace; font-size: 0.8em; white-space: nowrap; padding-right: 12px; }
  .cell { display: inline-block; min-width: 56px; padding: 3px 4px; border-radius: 4px; cursor: default; position: relative; }
  .cell.complete { background: #1a4321; color: #3fb950; }
  .cell.partial { background: #3d2e00; color: #d29922; }
  .cell.incomplete { background: #3d1e1e; color: #f85149; }
  .cell.missing { background: #161b22; color: #30363d; }
  .cell:hover { outline: 1px solid #58a6ff; }
  .cell:hover .tooltip { display: block; }
  .tooltip { display: none; position: absolute; bottom: 110%; left: 50%; transform: translateX(-50%);
    background: #1c2128; border: 1px solid #30363d; border-radius: 6px; padding: 8px 10px;
    font-size: 0.78em; white-space: nowrap; z-index: 100; color: #c9d1d9; text-align: left;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4); }
  .features-section { margin-top: 20px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
  .features-section h2 { font-size: 1em; color: #f0f6fc; margin-bottom: 8px; }
  .feature-item { display: flex; justify-content: space-between; padding: 4px 0; font-size: 0.85em; }
  .legend { display: flex; gap: 16px; margin: 12px 0; font-size: 0.82em; }
  .legend-item { display: flex; align-items: center; gap: 4px; }
  .legend-dot { width: 12px; height: 12px; border-radius: 3px; }
  .legend-dot.complete { background: #3fb950; }
  .legend-dot.partial { background: #d29922; }
  .legend-dot.incomplete { background: #f85149; }
  .legend-dot.missing { background: #30363d; }
  .refresh-info { text-align: right; color: #484f58; font-size: 0.78em; margin-top: 12px; }
</style>
</head>
<body>
<h1>MARS Download Monitor</h1>
<div class="subtitle" id="updated">Loading...</div>
<div class="legend">
  <div class="legend-item"><div class="legend-dot complete"></div> Complete</div>
  <div class="legend-item"><div class="legend-dot partial"></div> Partial</div>
  <div class="legend-item"><div class="legend-dot incomplete"></div> Incomplete</div>
  <div class="legend-item"><div class="legend-dot missing"></div> Missing</div>
</div>
<div id="dashboard"></div>
<div class="refresh-info">Auto-refresh every 10s &middot; <span id="refresh-time"></span></div>

<script>
function render(data) {
  document.getElementById('updated').textContent = 'Last updated: ' + data.updated;
  document.getElementById('refresh-time').textContent = new Date().toLocaleTimeString();

  let html = '';
  for (const [product, info] of Object.entries(data.products)) {
    const cycles = info.grid.length > 0 ? Object.keys(info.grid[0].cycles) : [];
    html += '<div class="product-card">';
    html += '<div class="product-header">';
    html += '<span class="product-name">' + product.toUpperCase() + '</span>';
    html += '<div class="product-stats">';
    html += '<span>' + info.raw_count + ' raw (' + info.raw_mb + ' MB)</span>';
    html += '<span>' + info.proc_count + ' processed (' + info.proc_mb + ' MB)</span>';
    html += '<span>' + info.complete + '/' + info.total + ' (' + info.pct + '%)</span>';
    html += '</div></div>';
    html += '<div class="progress-bar"><div class="progress-fill" style="width:' + info.pct + '%"></div></div>';

    if (info.grid.length > 0) {
      html += '<div class="grid-container"><table>';
      html += '<tr><th>Date</th>';
      for (const c of cycles) { html += '<th>' + c + 'Z</th>'; }
      html += '</tr>';
      for (const row of info.grid) {
        html += '<tr><td class="date">' + row.date + '</td>';
        for (const c of cycles) {
          const cell = row.cycles[c];
          const status = cell.status;
          const rawSize = cell.raw ? cell.raw.size_mb + ' MB' : '-';
          const procSize = cell.processed ? cell.processed.size_mb + ' MB' : '-';
          const rawTime = cell.raw ? cell.raw.modified.slice(11, 19) : '';
          const chunks = cell.chunks || 0;
          html += '<td><div class="cell ' + status + '">';
          if (cell.raw) { html += cell.raw.size_mb.toFixed(0) + 'M'; if (chunks > 1) html += '<sub>' + chunks + '</sub>'; }
          else { html += '-'; }
          html += '<div class="tooltip">';
          html += '<b>' + row.date + ' ' + c + 'Z</b><br>';
          html += 'Status: ' + status + '<br>';
          html += 'Raw: ' + rawSize + (chunks > 1 ? ' (' + chunks + ' chunks)' : '') + (rawTime ? ' @ ' + rawTime : '') + '<br>';
          html += 'Processed: ' + procSize;
          html += '</div></div></td>';
        }
        html += '</tr>';
      }
      html += '</table></div>';
    }
    html += '</div>';
  }

  // Features section
  if (Object.keys(data.features).length > 0) {
    html += '<div class="features-section"><h2>Feature Output</h2>';
    for (const [name, info] of Object.entries(data.features)) {
      html += '<div class="feature-item"><span>' + name + '</span><span>'
        + info.size_mb + ' MB &middot; ' + info.modified + '</span></div>';
    }
    html += '</div>';
  }

  document.getElementById('dashboard').innerHTML = html;
}

async function refresh() {
  try {
    const resp = await fetch('/api/status');
    const data = await resp.json();
    render(data);
  } catch(e) {
    console.error('Fetch failed:', e);
  }
}

refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>
"""


class MonitorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))
        elif self.path == "/api/status":
            status = build_status_json()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(status).encode("utf-8"))
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="MARS Download Monitor")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), MonitorHandler)
    url = f"http://localhost:{args.port}"
    logger.info("Monitor dashboard: %s", url)
    logger.info("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()


if __name__ == "__main__":
    main()
