"""
Performance: Session cache vs DB — сравнительная таблица.

Все сценарии прогоняются одним тестом, результаты выводятся в виде
таблицы: метрика | DB | Cache | speedup.
"""

import asyncio
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = [pytest.mark.performance, pytest.mark.asyncio]

MODULE = "SessionCache"
N = 1_000
CONCURRENT_BATCH = 100
CONCURRENT_WAVES = 10
WARMUP = 20


@dataclass
class Metrics:
    avg_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    total_ms: float
    rps: float


def _metrics(times_sec: list[float]) -> Metrics:
    times = sorted(times_sec)
    n = len(times)
    total = sum(times)
    return Metrics(
        avg_ms=statistics.mean(times) * 1000,
        p50_ms=times[n // 2] * 1000,
        p95_ms=times[int(n * 0.95)] * 1000,
        p99_ms=times[int(n * 0.99)] * 1000,
        total_ms=total * 1000,
        rps=n / total if total > 0 else 0,
    )


async def _create_test_session(
    db_pool, user_id: int = 1
) -> tuple[int, str, str]:
    token = f"sc_perf_token_{int(time.time() * 1e6)}"
    cookie_token = f"sc_perf_cookie_{int(time.time() * 1e6)}"
    expired = datetime.now(timezone.utc) + timedelta(days=1)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO sessions
                (user_id, token, cookie_token, ttl, active, expired_datetime,
                 create_datetime, create_user_id, update_datetime, update_user_id)
            VALUES ($1, $2, $3, 86400, true, $4, now(), $1, now(), $1)
            RETURNING id
            """,
            user_id,
            token,
            cookie_token,
            expired,
        )
    return row["id"], token, cookie_token


async def _run_sequential(
    check_fn, token, cookie_token, n: int
) -> list[float]:
    times: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            await check_fn(token, cookie_token=cookie_token)
        except Exception:
            pass
        times.append(time.perf_counter() - t0)
    return times


async def _run_concurrent(
    check_fn, token, cookie_token, batch: int, waves: int
) -> float:
    async def one_call():
        try:
            await check_fn(token, cookie_token=cookie_token)
        except Exception:
            pass

    t0 = time.perf_counter()
    for _ in range(waves):
        await asyncio.gather(*(one_call() for _ in range(batch)))
    return time.perf_counter() - t0


def _fmt_row(label: str, db_val: str, cache_val: str, speedup: str) -> str:
    return f"│ {label:<32} │ {db_val:>15} │ {cache_val:>15} │ {speedup:>10} │"


def _print_comparison_table(
    db_seq: Metrics,
    cache_seq: Metrics,
    db_concurrent_sec: float,
    cache_concurrent_sec: float,
    n: int,
    concurrent_total: int,
):
    total_width = 34 + 17 + 17 + 12 + 4
    top = "┌" + "─" * (total_width - 2) + "┐"
    sep = "├" + "─" * (total_width - 2) + "┤"
    bottom = "└" + "─" * (total_width - 2) + "┘"

    def sp(db: float, cache: float) -> str:
        if cache <= 0:
            return "—"
        return f"×{db / cache:.1f}"

    def sp_rps(db: float, cache: float) -> str:
        # для RPS больше=лучше, поэтому cache/db
        if db <= 0:
            return "—"
        return f"×{cache / db:.1f}"

    lines = [
        "",
        top,
        _fmt_row("Метрика", "DB", "Cache", "Speedup"),
        sep,
        _fmt_row(f"Sequential {n}", "", "", ""),
        _fmt_row(
            "  total time (ms)",
            f"{db_seq.total_ms:.1f}",
            f"{cache_seq.total_ms:.1f}",
            sp(db_seq.total_ms, cache_seq.total_ms),
        ),
        _fmt_row(
            "  avg per call (ms)",
            f"{db_seq.avg_ms:.3f}",
            f"{cache_seq.avg_ms:.3f}",
            sp(db_seq.avg_ms, cache_seq.avg_ms),
        ),
        _fmt_row(
            "  p50 (ms)",
            f"{db_seq.p50_ms:.3f}",
            f"{cache_seq.p50_ms:.3f}",
            sp(db_seq.p50_ms, cache_seq.p50_ms),
        ),
        _fmt_row(
            "  p95 (ms)",
            f"{db_seq.p95_ms:.3f}",
            f"{cache_seq.p95_ms:.3f}",
            sp(db_seq.p95_ms, cache_seq.p95_ms),
        ),
        _fmt_row(
            "  p99 (ms)",
            f"{db_seq.p99_ms:.3f}",
            f"{cache_seq.p99_ms:.3f}",
            sp(db_seq.p99_ms, cache_seq.p99_ms),
        ),
        _fmt_row(
            "  throughput (req/s)",
            f"{db_seq.rps:,.0f}",
            f"{cache_seq.rps:,.0f}",
            sp_rps(db_seq.rps, cache_seq.rps),
        ),
        sep,
        _fmt_row(
            f"Concurrent {CONCURRENT_BATCH}×{CONCURRENT_WAVES}", "", "", ""
        ),
        _fmt_row(
            "  total time (ms)",
            f"{db_concurrent_sec * 1000:.1f}",
            f"{cache_concurrent_sec * 1000:.1f}",
            sp(db_concurrent_sec, cache_concurrent_sec),
        ),
        _fmt_row(
            "  throughput (req/s)",
            f"{concurrent_total / db_concurrent_sec:,.0f}",
            f"{concurrent_total / cache_concurrent_sec:,.0f}",
            sp_rps(
                concurrent_total / db_concurrent_sec,
                concurrent_total / cache_concurrent_sec,
            ),
        ),
        bottom,
        "",
    ]
    print("\n".join(lines))


class TestSessionCacheComparison:
    async def test_cache_vs_db_full_comparison(
        self, db_pool, seed_users, perf_report
    ):
        """
        Полное сравнение DB vs Cache в одном тесте:
         - Sequential N=1000 вызовов (avg/p50/p95/p99/throughput)
         - Concurrent 100×10 волн

        Выводит:
         - сравнительную таблицу в консоль (DB | Cache | Speedup)
         - парные строки в perf_report (для каждой метрики сначала DB,
           следом Cache) — в HTML-отчёте видно обе колонки.
        """
        from backend.base.crm.security.models.sessions import Session
        from backend.base.crm.auth_token.app import AuthTokenApp

        _, token, cookie_token = await _create_test_session(db_pool)
        concurrent_total = CONCURRENT_BATCH * CONCURRENT_WAVES

        # ── DB путь ──
        AuthTokenApp.session_cache_enabled = False
        await _run_sequential(
            Session.session_check, token, cookie_token, WARMUP
        )
        db_seq_times = await _run_sequential(
            Session.session_check, token, cookie_token, N
        )
        db_concurrent_sec = await _run_concurrent(
            Session.session_check,
            token,
            cookie_token,
            CONCURRENT_BATCH,
            CONCURRENT_WAVES,
        )

        # ── Cache путь ──
        AuthTokenApp.session_cache_enabled = True
        await AuthTokenApp.session_cache.clear()
        await _run_sequential(
            Session.session_check_cached, token, cookie_token, WARMUP
        )
        cache_seq_times = await _run_sequential(
            Session.session_check_cached, token, cookie_token, N
        )
        cache_concurrent_sec = await _run_concurrent(
            Session.session_check_cached,
            token,
            cookie_token,
            CONCURRENT_BATCH,
            CONCURRENT_WAVES,
        )

        db_seq = _metrics(db_seq_times)
        cache_seq = _metrics(cache_seq_times)

        _print_comparison_table(
            db_seq,
            cache_seq,
            db_concurrent_sec,
            cache_concurrent_sec,
            N,
            concurrent_total,
        )

        # ── Выгрузка в perf_report парами для HTML ──
        # elapsed передаётся в секундах (см. conftest.add)

        # Sequential: 6 пар строк (total, avg, p50, p95, p99, throughput)
        # Для throughput elapsed не имеет смысла — кладём 1 сек,
        # а rows = throughput чтобы колонка rows/sec показала правильное значение.

        # Total time
        perf_report.add(MODULE, f"[SEQ] total — DB", N, db_seq.total_ms / 1000)
        perf_report.add(
            MODULE,
            f"[SEQ] total — Cache (×{db_seq.total_ms / max(cache_seq.total_ms, 1e-9):.1f})",
            N,
            cache_seq.total_ms / 1000,
        )

        # Avg per call
        perf_report.add(
            MODULE, "[SEQ] avg per call — DB", 1, db_seq.avg_ms / 1000
        )
        perf_report.add(
            MODULE,
            f"[SEQ] avg per call — Cache (×{db_seq.avg_ms / max(cache_seq.avg_ms, 1e-9):.1f})",
            1,
            cache_seq.avg_ms / 1000,
        )

        # p50 / p95 / p99
        for name, db_v, cache_v in [
            ("p50", db_seq.p50_ms, cache_seq.p50_ms),
            ("p95", db_seq.p95_ms, cache_seq.p95_ms),
            ("p99", db_seq.p99_ms, cache_seq.p99_ms),
        ]:
            perf_report.add(MODULE, f"[SEQ] {name} — DB", 1, db_v / 1000)
            perf_report.add(
                MODULE,
                f"[SEQ] {name} — Cache (×{db_v / max(cache_v, 1e-9):.1f})",
                1,
                cache_v / 1000,
            )

        # Concurrent total time
        perf_report.add(
            MODULE,
            f"[CONCURRENT {CONCURRENT_BATCH}×{CONCURRENT_WAVES}] total — DB",
            concurrent_total,
            db_concurrent_sec,
        )
        perf_report.add(
            MODULE,
            (
                f"[CONCURRENT {CONCURRENT_BATCH}×{CONCURRENT_WAVES}] total — Cache "
                f"(×{db_concurrent_sec / max(cache_concurrent_sec, 1e-9):.1f})"
            ),
            concurrent_total,
            cache_concurrent_sec,
        )

        seq_speedup = (
            db_seq.total_ms / cache_seq.total_ms
            if cache_seq.total_ms > 0
            else 0
        )
        assert (
            seq_speedup > 1
        ), f"Cache should be faster than DB sequentially, got x{seq_speedup:.2f}"
