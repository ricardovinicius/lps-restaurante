import asyncio
from contextlib import asynccontextmanager

from mesa_platform.application import create_app
from services.orders.routes import router
from services.orders.worker import run_worker


app = create_app("orders")
app.include_router(router)
database_lifespan = app.router.lifespan_context


@asynccontextmanager
async def lifespan(app):
    async with database_lifespan(app):
        stopped = asyncio.Event()
        worker = asyncio.create_task(run_worker(app, stopped))
        try:
            yield
        finally:
            stopped.set()
            await worker


app.router.lifespan_context = lifespan
