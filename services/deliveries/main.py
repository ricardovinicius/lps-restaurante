from mesa_platform.application import create_app
from services.deliveries.internal import router as internal_router


app = create_app("deliveries")
app.include_router(internal_router)
