from mesa_platform.application import create_app
from services.catalog.internal import router as internal_router
from services.catalog.routes import router
from services.catalog.summary import router as summary_router


app = create_app("catalog")
app.include_router(internal_router)
app.include_router(router)
app.include_router(summary_router)
