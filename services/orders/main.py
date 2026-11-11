import asyncio
from contextlib import asynccontextmanager

from mesa_platform.application import create_app
from services.orders.routes import router
from services.orders.table_routes import router as table_router
from services.orders.transition_routes import router as transition_router
from services.orders.worker import run_worker


app = create_app("orders")
app.include_router(router)
app.include_router(transition_router)
app.include_router(table_router)
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
