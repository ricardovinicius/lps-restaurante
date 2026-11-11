from mesa_platform.application import create_app
from services.configuration import access, internal, routes


app = create_app("configuration")
app.include_router(access.router)
app.include_router(internal.router)
app.include_router(routes.router)
