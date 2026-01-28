"""Utility functions for dotorm."""

import asyncio
from typing import Any, Coroutine, Sequence


async def execute_maybe_parallel(
    coroutines: Sequence[Coroutine[Any, Any, Any]],
) -> list[Any]:
    """
    Execute coroutines in parallel or sequentially depending on transaction context.
    
    If inside a transaction (single connection), executes sequentially to avoid
    asyncpg "another operation is in progress" error.
    
    If outside transaction (pool), executes in parallel for better performance.
    
    Args:
        coroutines: List of coroutines to execute
        
    Returns:
        List of results in the same order as input coroutines
    """
    from ..databases.postgres.transaction import get_current_session
    
    if not coroutines:
        return []
    
    # Check if we're inside a transaction
    if get_current_session() is not None:
        # Inside transaction - execute sequentially
        results = []
        for coro in coroutines:
            result = await coro
            results.append(result)
        return results
    else:
        # Outside transaction - execute in parallel
        return list(await asyncio.gather(*coroutines))
