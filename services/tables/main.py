from mesa_platform.application import create_app
from services.tables import contexts, internal, routes


app = create_app("tables")
app.include_router(internal.router)
app.include_router(contexts.router)
app.include_router(routes.router)
