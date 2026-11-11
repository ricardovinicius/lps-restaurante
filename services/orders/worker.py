import asyncio
import logging

from services.orders.orchestration import process_operation

logger = logging.getLogger("mesa.orders")


async def run_worker(app, stopped):
    while not stopped.is_set():
        try:
            await asyncio.wait_for(stopped.wait(), timeout=3)
        except TimeoutError:
            try:
                for _ in range(10):
                    if stopped.is_set() or not await asyncio.to_thread(process_operation, app.state.engine):
                        break
            except Exception:
                logger.error("Checkout recovery temporarily unavailable")
