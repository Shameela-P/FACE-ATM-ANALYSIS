"""Main FastAPI application entrypoint."""

import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routers.health import router as health_router
from app.routers.admin import router as admin_router
from app.routers.customers import router as customers_router
from app.routers.atm import router as atm_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("face_atm.app")

# Initialize FastAPI application
app = FastAPI(
    title="Face Authentication & Customer Transaction API",
    description="Backend service for admin authentication, customer verification, and transactions.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler preventing secret/stack exposure to clients."""
    logger.error("Unhandled exception at %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please contact system administrator."},
    )


# Register route handlers
app.include_router(health_router)
app.include_router(admin_router)
app.include_router(customers_router)
app.include_router(atm_router)



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
