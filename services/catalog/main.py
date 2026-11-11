from mesa_platform.application import create_app
from services.catalog.internal import router as internal_router
from services.catalog.routes import router


app = create_app("catalog")
app.include_router(internal_router)
app.include_router(router)
