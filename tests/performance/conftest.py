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
