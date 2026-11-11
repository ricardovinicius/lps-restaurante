import asyncio
import logging

from services.orders.dispatch import process_dispatch
from services.orders.orchestration import process_operation

logger = logging.getLogger("mesa.orders")
BATCH_SIZE = 10


async def drain(process, engine, stopped):
    for _ in range(BATCH_SIZE):
        if stopped.is_set() or not await asyncio.to_thread(process, engine):
            return


async def run_worker(app, stopped):
    """Resume due checkout and dispatch operations every three seconds."""
    while not stopped.is_set():
        try:
            await asyncio.wait_for(stopped.wait(), timeout=3)
        except TimeoutError:
            for process in (process_operation, process_dispatch):
                try:
                    await drain(process, app.state.engine, stopped)
                except Exception as error:
                    # Only the type: database errors may echo parameters such as addresses.
                    logger.error("Operation recovery temporarily unavailable: %s", type(error).__name__)
