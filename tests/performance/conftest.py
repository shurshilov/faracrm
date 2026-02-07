"""
Performance test configuration.

Provides:
- Timing helpers (perf_timer context manager)
- Bulk data seeding fixtures (users, sessions, messages, etc.)
- HTML/console report generation at session end

Run:
    pytest tests/performance/ -v -m performance --tb=short -s
    pytest tests/performance/ -v -m performance -k "users"   # one module
"""

import os
import time
import json
import asyncio
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import pytest
import pytest_asyncio

# ──────────────────────────────────────────────
# Marker
# ──────────────────────────────────────────────

pytestmark = [pytest.mark.performance]


# ──────────────────────────────────────────────
# Override: disable per-test TRUNCATE from root conftest.
# Performance tests manage their own data lifecycle.
# ──────────────────────────────────────────────


@pytest_asyncio.fixture(autouse=True)
async def clean_all_tables():
    """Override root conftest clean_all_tables — do nothing for perf tests."""
    yield


# ──────────────────────────────────────────────
# Result collector (session-global singleton)
# ──────────────────────────────────────────────


@dataclass
class PerfResult:
    module: str
    operation: str
    rows: int
    elapsed_ms: float
    rps: float  # rows per second (rows / elapsed)


class PerfReport:
    """Accumulates results across all tests, prints summary."""

    def __init__(self):
        self.results: list[PerfResult] = []

    def add(self, module: str, operation: str, rows: int, elapsed: float):
        rps = rows / elapsed if elapsed > 0 else float("inf")
        self.results.append(
            PerfResult(
                module=module,
                operation=operation,
                rows=rows,
                elapsed_ms=round(elapsed * 1000, 2),
                rps=round(rps, 1),
            )
        )

    # ── console ──

    def print_console(self):
        if not self.results:
            return

        print("\n")
        print("=" * 100)
        print(f"{'PERFORMANCE REPORT':^100}")
        print("=" * 100)

        header = f"{'Module':<18} {'Operation':<35} {'Rows':>10} {'Time ms':>12} {'rows/sec':>12}"
        print(header)
        print("-" * 100)

        current_module = None
        for r in self.results:
            if r.module != current_module:
                if current_module is not None:
                    print("-" * 100)
                current_module = r.module
            rps_str = f"{r.rps:,.1f}" if r.rps != float("inf") else "∞"
            print(
                f"{r.module:<18} {r.operation:<35} {r.rows:>10,} {r.elapsed_ms:>11,.2f} {rps_str:>12}"
            )

        print("=" * 100)

    # ── html ──

    def save_html(self, path: str):
        if not self.results:
            return

        rows_html = ""
        current_module = None
        for r in self.results:
            if r.module != current_module:
                current_module = r.module
                rows_html += (
                    f'<tr class="group"><td colspan="5">{r.module}</td></tr>\n'
                )
            rps_str = f"{r.rps:,.1f}" if r.rps != float("inf") else "∞"

            # color code: green < 500ms, yellow < 2000ms, red >= 2000ms
            if r.elapsed_ms < 500:
                cls = "fast"
            elif r.elapsed_ms < 2000:
                cls = "medium"
            else:
                cls = "slow"

            rows_html += (
                f'<tr class="{cls}">'
                f"<td>{r.module}</td>"
                f"<td>{r.operation}</td>"
                f"<td class='num'>{r.rows:,}</td>"
                f"<td class='num'>{r.elapsed_ms:,.2f}</td>"
                f"<td class='num'>{rps_str}</td>"
                f"</tr>\n"
            )

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Perf Report {ts}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       margin: 2em auto; max-width: 960px; color: #333; }}
h1 {{ text-align:center; }}
table {{ width:100%; border-collapse:collapse; margin-top:1em; }}
th {{ background:#2c3e50; color:white; padding:10px 12px; text-align:left; }}
td {{ padding:8px 12px; border-bottom:1px solid #eee; }}
.num {{ text-align:right; font-variant-numeric: tabular-nums; }}
tr.group {{ background:#ecf0f1; font-weight:bold; }}
tr.fast td.num:nth-child(4) {{ color:#27ae60; }}
tr.medium td.num:nth-child(4) {{ color:#f39c12; }}
tr.slow td.num:nth-child(4) {{ color:#e74c3c; font-weight:bold; }}
tr:hover {{ background:#f8f9fa; }}
.meta {{ color:#888; text-align:center; margin-top:1.5em; font-size:0.9em; }}
</style></head><body>
<h1>🚀 FARA CRM — Performance Report</h1>
<table>
<tr><th>Module</th><th>Operation</th><th>Rows</th><th>Time (ms)</th><th>rows/sec</th></tr>
{rows_html}
</table>
<p class="meta">Generated {ts}</p>
</body></html>"""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n✓ HTML report saved to {path}")

    # ── json ──

    def save_json(self, path: str):
        if not self.results:
            return
        data = [
            {
                "module": r.module,
                "operation": r.operation,
                "rows": r.rows,
                "elapsed_ms": r.elapsed_ms,
                "rps": r.rps,
            }
            for r in self.results
        ]
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    # ── comparison html (rich, with inline data) ──

    def save_comparison_html(self, path: str):
        """Generate beautiful comparison HTML with data embedded inline."""
        if not self.results:
            return

        data = [
            {
                "module": r.module,
                "operation": r.operation,
                "rows": r.rows,
                "elapsed_ms": r.elapsed_ms,
                "rps": r.rps,
            }
            for r in self.results
        ]
        data_json = json.dumps(data)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        html = _COMPARISON_HTML_TEMPLATE.replace("__DATA_PLACEHOLDER__", data_json)
        html = html.replace("__TIMESTAMP__", ts)

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n✓ Comparison HTML saved to {path}")


# ── HTML template for comparison report ──
_COMPARISON_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DotORM — Performance Comparison</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=DM+Sans:wght@400;500;600;700&display=swap');
  :root {
    --bg:#0c0e13;--surface:#13161d;--surface2:#1a1e28;--border:#252a36;
    --text:#e2e4ea;--text-dim:#7a7f8e;
    --gold:#f5c542;--gold-dim:rgba(245,197,66,.12);
    --green:#34d399;--green-dim:rgba(52,211,153,.10);
    --red:#f87171;--red-dim:rgba(248,113,113,.08);
    --purple:#a78bfa;--orange:#fb923c;--cyan:#22d3ee;
  }
  *{margin:0;padding:0;box-sizing:border-box}
  body{background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;min-height:100vh;padding:40px 24px 80px}
  .container{max-width:1320px;margin:0 auto}

  /* Header */
  .header{text-align:center;margin-bottom:40px}
  .header h1{font-family:'JetBrains Mono',monospace;font-size:2rem;font-weight:700;letter-spacing:-.5px;background:linear-gradient(135deg,var(--gold),var(--orange));-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px}
  .header p{color:var(--text-dim);font-size:.9rem}
  .header .meta{display:inline-flex;gap:20px;margin-top:14px;font-family:'JetBrains Mono',monospace;font-size:.75rem;color:var(--text-dim)}
  .header .ts{display:block;margin-top:8px;font-family:'JetBrains Mono',monospace;font-size:.68rem;color:var(--text-dim);opacity:.45}

  /* Summary cards */
  .summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:12px;margin-bottom:32px}
  .card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px;text-align:center}
  .card .emoji{font-size:1.5rem;margin-bottom:4px}
  .card .card-label{font-size:.7rem;color:var(--text-dim);text-transform:uppercase;letter-spacing:.5px;margin-bottom:3px}
  .card .card-val{font-family:'JetBrains Mono',monospace;font-size:1.25rem;font-weight:700}
  .card .card-sub{font-size:.7rem;color:var(--text-dim);margin-top:2px}

  /* Tabs */
  .tabs{display:flex;gap:2px;margin-bottom:0;background:var(--surface2);border-radius:10px 10px 0 0;padding:4px 4px 0;border:1px solid var(--border);border-bottom:none}
  .tab{padding:10px 24px;font-family:'JetBrains Mono',monospace;font-size:.78rem;font-weight:600;color:var(--text-dim);cursor:pointer;border-radius:8px 8px 0 0;transition:all .15s;border:none;background:none}
  .tab:hover{color:var(--text);background:rgba(255,255,255,.03)}
  .tab.active{color:var(--gold);background:var(--surface);border:1px solid var(--border);border-bottom:1px solid var(--surface);margin-bottom:-1px;z-index:1}
  .tab-content{display:none}
  .tab-content.active{display:block}

  /* Legend */
  .legend{display:flex;justify-content:center;flex-wrap:wrap;gap:20px;margin:20px 0}
  .legend-item{display:flex;align-items:center;gap:7px;font-size:.8rem;color:var(--text-dim)}
  .legend-dot{width:10px;height:10px;border-radius:2px}

  /* Table shared */
  .table-wrap{overflow-x:auto;border-radius:0 0 12px 12px;border:1px solid var(--border);border-top:none;background:var(--surface)}
  table{width:100%;border-collapse:collapse;font-size:.84rem}
  thead th{background:var(--surface2);font-family:'JetBrains Mono',monospace;font-weight:600;font-size:.71rem;text-transform:uppercase;letter-spacing:1px;color:var(--text-dim);padding:13px 14px;text-align:right;white-space:nowrap;border-bottom:2px solid var(--border)}
  thead th:first-child{text-align:left;min-width:210px}
  thead th.col-asyncpg{color:var(--cyan)} thead th.col-sa{color:var(--purple)}
  thead th.col-tortoise{color:var(--orange)} thead th.col-dotorm{color:var(--gold)}
  tr.group-header td{background:var(--bg);font-family:'JetBrains Mono',monospace;font-weight:700;font-size:.76rem;letter-spacing:.5px;color:var(--text-dim);padding:9px 14px;border-bottom:1px solid var(--border);text-transform:uppercase}
  tbody tr{border-bottom:1px solid rgba(255,255,255,.03);transition:background .15s}
  tbody tr:hover{background:rgba(255,255,255,.02)}
  td{padding:11px 14px;text-align:right;font-family:'JetBrains Mono',monospace;font-size:.8rem;white-space:nowrap;position:relative}
  td:first-child{text-align:left;font-family:'DM Sans',sans-serif;font-weight:500;color:var(--text);font-size:.84rem}
  td .rows-badge{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:.66rem;color:var(--text-dim);background:var(--surface2);padding:2px 5px;border-radius:3px;margin-left:7px}
  .val{display:inline-flex;align-items:center;gap:5px}
  .badge{display:inline-block;font-size:.63rem;font-family:'DM Sans',sans-serif;font-weight:600;padding:1px 5px;border-radius:3px;letter-spacing:.3px}
  .badge-gold{background:var(--gold-dim);color:var(--gold)}
  .badge-silver{background:var(--green-dim);color:var(--green)}
  .badge-last{background:var(--red-dim);color:var(--red)}
  td.cell-asyncpg{color:var(--cyan)} td.cell-sa{color:var(--purple)}
  td.cell-tortoise{color:var(--orange)} td.cell-dotorm{color:var(--gold)}
  td.winner-cell{font-weight:700}
  td.winner-cell::before{content:'';position:absolute;left:0;top:4px;bottom:4px;width:3px;border-radius:0 2px 2px 0}
  td.winner-cell.cell-asyncpg::before{background:var(--cyan)}
  td.winner-cell.cell-sa::before{background:var(--purple)}
  td.winner-cell.cell-tortoise::before{background:var(--orange)}
  td.winner-cell.cell-dotorm::before{background:var(--gold)}

  /* Detail table */
  .detail-table th{text-align:left}
  .detail-table td{text-align:left}
  .detail-table td.num{text-align:right;font-variant-numeric:tabular-nums}
  .detail-table tr.group td{background:var(--surface2);font-weight:700;color:var(--text);font-size:.78rem}
  .detail-table tr.fast td.num:nth-child(4){color:var(--green)}
  .detail-table tr.medium td.num:nth-child(4){color:var(--orange)}
  .detail-table tr.slow td.num:nth-child(4){color:var(--red);font-weight:700}

  .footer{text-align:center;margin-top:32px;color:var(--text-dim);font-size:.73rem;line-height:1.7}
  .footer span{font-family:'JetBrains Mono',monospace;color:var(--text)}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>⚡ DotORM Performance Report</h1>
    <p>Head-to-head: raw asyncpg · SQLAlchemy · Tortoise · dotorm</p>
    <div class="meta"><span>PostgreSQL 16</span><span>100k rows</span><span>asyncpg 0.30</span><span>Python 3.12</span></div>
    <span class="ts">Generated: __TIMESTAMP__</span>
  </div>
  <div id="summary" class="summary"></div>

  <div class="tabs">
    <div class="tab active" onclick="switchTab('comparison')">⚔️ Comparison</div>
    <div class="tab" onclick="switchTab('detail')">📋 Detail Log</div>
  </div>

  <div id="tab-comparison" class="tab-content active">
    <div class="legend">
      <div class="legend-item"><div class="legend-dot" style="background:var(--cyan)"></div>raw asyncpg</div>
      <div class="legend-item"><div class="legend-dot" style="background:var(--purple)"></div>SQLAlchemy</div>
      <div class="legend-item"><div class="legend-dot" style="background:var(--orange)"></div>Tortoise</div>
      <div class="legend-item"><div class="legend-dot" style="background:var(--gold)"></div>dotorm</div>
      <div class="legend-item"><span class="badge badge-gold">🥇 1st</span></div>
      <div class="legend-item"><span class="badge badge-silver">🥈 2nd</span></div>
      <div class="legend-item"><span class="badge badge-last">🐌 last</span></div>
    </div>
    <div class="table-wrap" id="comparison-table"></div>
  </div>

  <div id="tab-detail" class="tab-content">
    <div class="table-wrap" id="detail-table"></div>
  </div>

  <div class="footer">
    Lower is better (ms). Badges compare <span>ORM-only</span> (excl. raw asyncpg).<br>
    Re-run <span>pytest tests/performance/test_orm_comparison.py</span> to refresh data.
  </div>
</div>

<script>
const data = __DATA_PLACEHOLDER__;

function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
}

// ── Detect modules ──
const modules = [...new Set(data.map(d => d.module))];
const baseline = modules[0];
const ormModules = modules.slice(1);
const cssMap = ['cell-asyncpg','cell-sa','cell-tortoise','cell-dotorm'];
const colMap = ['col-asyncpg','col-sa','col-tortoise','col-dotorm'];
const themeColors = ['var(--cyan)','var(--purple)','var(--orange)','var(--gold)'];

const ops = {};
data.forEach(d => { if (!ops[d.operation]) ops[d.operation] = {}; ops[d.operation][d.module] = d; });

// ── Categorize ──
const cats = { CREATE:[], READ:[], UPDATE:[], DELETE:[] };
Object.keys(ops).forEach(op => {
  const lo = op.toLowerCase();
  if (lo.startsWith('create')) cats.CREATE.push(op);
  else if (lo.startsWith('get')||lo.startsWith('search')) cats.READ.push(op);
  else if (lo.startsWith('update')) cats.UPDATE.push(op);
  else if (lo.startsWith('delete')) cats.DELETE.push(op);
  else cats.READ.push(op);
});

function fmt(ms) { return ms < 1 ? ms.toFixed(2) : ms < 10 ? ms.toFixed(1) : Math.round(ms).toLocaleString(); }
function fmtRps(rps) { return rps === Infinity ? '∞' : rps > 1e6 ? (rps/1e6).toFixed(1)+'M' : rps > 1e3 ? (rps/1e3).toFixed(1)+'K' : rps.toFixed(0); }

// ═══ Comparison table ═══
const wins = {}; ormModules.forEach(m => wins[m] = 0);
let cHead = '<tr><th>Operation</th>' + modules.map((m,i) => `<th class="${colMap[i]||'col-dotorm'}">${m}</th>`).join('') + '</tr>';
let cBody = '';

Object.entries(cats).forEach(([cat, opNames]) => {
  if (!opNames.length) return;
  cBody += `<tr class="group-header"><td colspan="${modules.length+1}">${cat}</td></tr>`;
  opNames.forEach(opName => {
    const row = ops[opName]; if (!row) return;
    const ormVals = ormModules.map(m => ({mod:m, ms:row[m]?.elapsed_ms??Infinity})).sort((a,b) => a.ms - b.ms);
    const rank = {}; ormVals.forEach((v,i) => rank[v.mod] = i);
    if (ormVals[0].ms < Infinity) wins[ormVals[0].mod]++;
    const fe = row[modules[0]] || Object.values(row)[0];
    const rb = fe ? `<span class="rows-badge">${fe.rows.toLocaleString()}</span>` : '';
    let cells = `<td>${opName}${rb}</td>`;
    modules.forEach(mod => {
      const e = row[mod]; if (!e) { cells += `<td class="${cssMap[modules.indexOf(mod)]}">—</td>`; return; }
      const cls = cssMap[modules.indexOf(mod)] || 'cell-dotorm';
      const isORM = ormModules.includes(mod);
      let badge = '', wc = '';
      if (isORM) { const r = rank[mod]; if (r===0){badge='<span class="badge badge-gold">🥇</span>';wc=' winner-cell'} else if(r===1){badge='<span class="badge badge-silver">🥈</span>'} else if(r===ormVals.length-1){badge='<span class="badge badge-last">🐌</span>'} }
      cells += `<td class="${cls}${wc}"><span class="val">${fmt(e.elapsed_ms)} ms ${badge}</span></td>`;
    });
    cBody += `<tr>${cells}</tr>`;
  });
});

document.getElementById('comparison-table').innerHTML = `<table><thead>${cHead}</thead><tbody>${cBody}</tbody></table>`;

// ═══ Detail table ═══
let dBody = '';
let curMod = null;
data.forEach(r => {
  if (r.module !== curMod) { curMod = r.module; dBody += `<tr class="group"><td colspan="5">${r.module}</td></tr>`; }
  const cls = r.elapsed_ms < 500 ? 'fast' : r.elapsed_ms < 2000 ? 'medium' : 'slow';
  dBody += `<tr class="${cls}"><td>${r.module}</td><td>${r.operation}</td><td class="num">${r.rows.toLocaleString()}</td><td class="num">${r.elapsed_ms.toFixed(2)}</td><td class="num">${fmtRps(r.rps)}</td></tr>`;
});
document.getElementById('detail-table').innerHTML = `<table class="detail-table"><thead><tr><th>Module</th><th>Operation</th><th style="text-align:right">Rows</th><th style="text-align:right">Time (ms)</th><th style="text-align:right">rows/sec</th></tr></thead><tbody>${dBody}</tbody></table>`;

// ═══ Summary cards ═══
const totalOps = Object.keys(ops).length;
const overhead = {};
ormModules.forEach(mod => {
  let sO=0,sR=0,c=0;
  Object.values(ops).forEach(row => { if(row[mod]&&row[baseline]){sO+=row[mod].elapsed_ms;sR+=row[baseline].elapsed_ms;c++} });
  overhead[mod] = c > 0 ? ((sO/sR-1)*100).toFixed(0) : '?';
});
let best='',bw=0; Object.entries(wins).forEach(([m,w])=>{if(w>bw){bw=w;best=m}});

const emojis=['🏆','⚡','🐘','🐢'];
const labels=['Most ORM Wins',...ormModules.map(m=>`${m} overhead`)];
const vals=[best,...ormModules.map(m=>`+${overhead[m]}%`)];
const subs=[`${bw} / ${totalOps} operations`,...ormModules.map(()=>`vs ${baseline}`)];

let sh='';
vals.forEach((v,i) => {
  const c = themeColors[i]||themeColors[3];
  sh += `<div class="card"><div class="emoji">${emojis[i]||'📊'}</div><div class="card-label">${labels[i]}</div><div class="card-val" style="color:${c}">${v}</div><div class="card-sub">${subs[i]}</div></div>`;
});
document.getElementById('summary').innerHTML = sh;
</script>
</body>
</html>"""


# Session-scoped singleton
_report = PerfReport()


@pytest.fixture(scope="session")
def perf_report():
    return _report


@pytest.fixture(scope="session", autouse=True)
def _print_report_at_end(perf_report):
    """Print report after all tests finish."""
    yield
    perf_report.print_console()
    report_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "reports"
    )
    perf_report.save_html(os.path.join(report_dir, "perf_report.html"))
    perf_report.save_json(os.path.join(report_dir, "perf_report.json"))


# ──────────────────────────────────────────────
# Timer helper
# ──────────────────────────────────────────────


@asynccontextmanager
async def perf_timer(report: PerfReport, module: str, operation: str, rows: int):
    """
    Usage:
        async with perf_timer(perf_report, "Users", "create_bulk 10_000", 10_000):
            await User.create_bulk(payload)
    """
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    report.add(module, operation, rows, elapsed)


# ──────────────────────────────────────────────
# Chunked bulk create (asyncpg 32767 param limit)
# ──────────────────────────────────────────────

ASYNCPG_MAX_PARAMS = 32_767


async def chunked_create_bulk(model_cls, payload: list):
    """
    create_bulk in safe chunks to stay under asyncpg's 32767 parameter limit.
    Auto-detects field count from the model class.
    """
    if not payload:
        return
    # Count actual store fields that will become SQL params
    fields_per_row = len(model_cls.get_store_fields())
    chunk_size = max(1, ASYNCPG_MAX_PARAMS // max(fields_per_row, 1) - 1)
    for i in range(0, len(payload), chunk_size):
        await model_cls.create_bulk(payload[i : i + chunk_size])


# ──────────────────────────────────────────────
# Seed fixtures (direct SQL for max speed)
# ──────────────────────────────────────────────


@pytest_asyncio.fixture(scope="class")
async def seed_users(db_pool) -> int:
    """Insert 10 000 users via raw SQL. Returns count."""
    from backend.base.crm.languages.models.language import Language

    lang_id = await Language.create(
        Language(code="en", name="English", active=True)
    )

    count = 10_000
    async with db_pool.acquire() as conn:
        # Clean only users + dependents, not the whole DB
        await conn.execute("TRUNCATE TABLE users CASCADE")
        await conn.execute(
            """
            INSERT INTO users (name, login, password_hash, password_salt, is_admin, lang_id)
            SELECT
                'User ' || g,
                'user_' || g,
                'hash_' || g,
                'salt_' || g,
                false,
                $1
            FROM generate_series(1, $2) g
            """,
            lang_id,
            count,
        )
    return count


@pytest_asyncio.fixture(scope="class")
async def seed_sessions(db_pool, seed_users) -> int:
    """Insert 1 000 000 sessions via raw SQL. Returns count."""
    count = 1_000_000
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE sessions CASCADE")
        # Distribute sessions across users (10k users → ~100 sessions each)
        await conn.execute(
            """
            INSERT INTO sessions (user_id, token, ttl, active, expired_datetime,
                                  create_datetime, create_user_id, update_datetime, update_user_id)
            SELECT
                (g % $1) + 1,
                md5(random()::text || g::text),
                86400,
                true,
                now() + interval '1 day',
                now() - (random() * interval '30 days'),
                (g % $1) + 1,
                now(),
                (g % $1) + 1
            FROM generate_series(1, $2) g
            """,
            seed_users,
            count,
        )
    return count


@pytest_asyncio.fixture(scope="class")
async def seed_chat_and_messages(db_pool, seed_users) -> dict:
    """
    Create chats + 1 000 000 messages + members.
    Returns: {"chats": N, "messages": N, "members": N, "big_chat_id": int}
    """
    num_chats = 100
    num_messages = 1_000_000
    # One "big" chat with 5000 members for subscriber load test
    big_chat_members = 5_000

    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE chat_message, chat_member, chat CASCADE")

        # 1) Create chats
        await conn.execute(
            """
            INSERT INTO chat (name, chat_type, active, is_public, is_internal,
                              default_can_read, default_can_write, default_can_invite,
                              default_can_pin, default_can_delete_others,
                              create_date, write_date, create_user_id)
            SELECT
                'Chat #' || g,
                CASE WHEN g = 1 THEN 'channel' ELSE 'group' END,
                true, false, true,
                true, true, false, false, false,
                now(), now(),
                1
            FROM generate_series(1, $1) g
            """,
            num_chats,
        )
        big_chat_id = await conn.fetchval(
            "SELECT id FROM chat WHERE name = 'Chat #1'"
        )

        # 2) Members: spread users across chats + big_chat has 5000 members
        #    Each regular chat gets ~50 members
        await conn.execute(
            """
            INSERT INTO chat_member (chat_id, user_id, is_active,
                                     can_read, can_write, can_invite, can_pin,
                                     can_delete_others, is_admin, joined_at)
            SELECT
                chat_sub.chat_id,
                chat_sub.user_id,
                true,
                true, true, false, false, false, false, now()
            FROM (
                -- big chat: first 5000 users
                SELECT $1::int AS chat_id, g AS user_id
                FROM generate_series(1, $2) g
                UNION ALL
                -- other chats: 50 users each
                SELECT
                    c.id AS chat_id,
                    ((c.id * 50 + g - 1) % $3) + 1 AS user_id
                FROM chat c, generate_series(1, 50) g
                WHERE c.id != $1
            ) chat_sub
            ON CONFLICT DO NOTHING
            """,
            big_chat_id,
            big_chat_members,
            seed_users,
        )

        member_count = await conn.fetchval("SELECT count(*) FROM chat_member")

        # 3) Messages: distribute across chats, ~10k per chat average
        await conn.execute(
            """
            INSERT INTO chat_message (chat_id, body, message_type,
                                      author_user_id, create_date, write_date,
                                      is_read, is_deleted, starred, pinned, is_edited)
            SELECT
                ((g - 1) % $1) + (SELECT min(id) FROM chat),
                'Message body #' || g,
                'comment',
                (g % $2) + 1,
                now() - ((($1 - g) * interval '1 second')),
                now(),
                (random() > 0.3),
                false,
                (random() > 0.95),
                false,
                false
            FROM generate_series(1, $3) g
            """,
            num_chats,
            seed_users,
            num_messages,
        )

    return {
        "chats": num_chats,
        "messages": num_messages,
        "members": member_count,
        "big_chat_id": big_chat_id,
    }


@pytest_asyncio.fixture(scope="class")
async def seed_activities(db_pool, seed_users) -> int:
    """Insert 100 000 activities via raw SQL."""
    count = 100_000
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE activity, activity_type CASCADE")

        # Create some activity types
        await conn.execute(
            """
            INSERT INTO activity_type (name, active, default_days, icon)
            VALUES
                ('Call', true, 1, 'phone'),
                ('Email', true, 2, 'mail'),
                ('Meeting', true, 3, 'calendar'),
                ('Task', true, 5, 'check')
            """
        )

        await conn.execute(
            """
            INSERT INTO activity (res_model, res_id, activity_type_id,
                                  user_id, date_deadline, state, done,
                                  notification_sent, active, create_date, summary)
            SELECT
                CASE g % 3 WHEN 0 THEN 'lead' WHEN 1 THEN 'partner' ELSE 'task' END,
                (g % 1000) + 1,
                (g % 4) + (SELECT min(id) FROM activity_type),
                (g % $1) + 1,
                current_date + ((g % 60) - 30),
                CASE
                    WHEN g % 5 = 0 THEN 'done'
                    WHEN g % 7 = 0 THEN 'overdue'
                    WHEN g % 3 = 0 THEN 'today'
                    ELSE 'planned'
                END,
                (g % 5 = 0),
                false,
                true,
                now() - (random() * interval '90 days'),
                'Activity #' || g
            FROM generate_series(1, $2) g
            """,
            seed_users,
            count,
        )
    return count


@pytest_asyncio.fixture(scope="class")
async def seed_leads(db_pool, seed_users) -> int:
    """Insert 100 000 leads via raw SQL."""
    count = 100_000
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE lead, lead_stage CASCADE")

        await conn.execute(
            """
            INSERT INTO lead_stage (name, sequence)
            VALUES ('New', 1), ('Qualified', 2), ('Proposal', 3),
                   ('Won', 4), ('Lost', 5)
            """
        )

        await conn.execute(
            """
            INSERT INTO lead (name, active, stage_id, user_id, type,
                              email, phone)
            SELECT
                'Lead #' || g,
                true,
                (g % 5) + (SELECT min(id) FROM lead_stage),
                (g % $1) + 1,
                CASE WHEN g % 3 = 0 THEN 'opportunity' ELSE 'lead' END,
                'lead_' || g || '@test.com',
                '+1' || lpad((g % 10000000)::text, 10, '0')
            FROM generate_series(1, $2) g
            """,
            seed_users,
            count,
        )
    return count
