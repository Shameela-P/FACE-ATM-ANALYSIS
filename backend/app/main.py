"""Main FastAPI application entrypoint."""

import logging
import re
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

VERCEL_ORIGIN_REGEX = r"https://face-atm-analysis.*\.vercel\.app"
_compiled_origin_regex = re.compile(VERCEL_ORIGIN_REGEX)


def is_permitted_origin(origin: str) -> bool:
    """Check if an origin is permitted by static origins or Face ATM Vercel pattern."""
    if not origin:
        return False
    if origin in settings.cors_origins_list:
        return True
    return bool(_compiled_origin_regex.fullmatch(origin))


# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=VERCEL_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler preventing secret/stack exposure to clients while preserving CORS headers."""
    logger.error("Unhandled exception at %s: %s", request.url.path, exc)
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please contact system administrator."},
    )
    origin = request.headers.get("origin")
    if origin and is_permitted_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT"
        response.headers["Access-Control-Allow-Headers"] = "*"
    return response


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
