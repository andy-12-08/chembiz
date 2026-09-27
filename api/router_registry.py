from fastapi import FastAPI

from api.routers import files, runs, sessions


def register_routers(app: FastAPI) -> None:
    """Attach all public ChemBiz API routers to an application.

    Args:
        app: FastAPI application that receives the session, file, and run routes.

    Returns:
        None.
    """
    app.include_router(sessions.router)
    app.include_router(files.router)
    app.include_router(runs.router)
