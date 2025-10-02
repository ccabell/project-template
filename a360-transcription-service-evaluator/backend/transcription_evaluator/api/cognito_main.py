"""Main FastAPI application with AWS Cognito authentication.

This is the updated main application that uses AWS Cognito for authentication
and Amazon Verified Permissions for authorization instead of custom implementations.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from ..config.settings import get_settings
from ..config.parameter_store import get_backend_config
from .cognito_assignment_routes import router as assignment_router
from .cognito_auth_routes import router as auth_router
from .cognito_generation_routes import router as generation_router
from .cognito_brands_terms_routes import router as brands_terms_router
from .cognito_jobs_routes import router as jobs_router

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Startup
    logger.info("Starting Transcription Evaluator API with AWS Cognito authentication")

    try:
        # Verify AWS configuration
        settings = get_settings()
        if not all(
            [
                os.getenv("COGNITO_USER_POOL_ID"),
                os.getenv("COGNITO_CLIENT_ID"),
                os.getenv("VERIFIED_PERMISSIONS_POLICY_STORE_ID"),
            ]
        ):
            logger.warning("AWS configuration environment variables may be missing")

        logger.info("AWS Cognito configuration verified")

    except Exception as e:
        logger.error(f"Startup configuration error: {str(e)}")

    yield

    # Shutdown
    logger.info("Shutting down Transcription Evaluator API")


# Create FastAPI application
app = FastAPI(
    title="Transcription Evaluator API",
    description="AWS Cognito-integrated API for transcription evaluation and script assignment",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware - Configure allowed origins securely using Parameter Store
backend_config = get_backend_config()
cors_origins = [
    "http://localhost:3000",
    "http://localhost:8000", 
    os.getenv("FRONTEND_URL", "http://localhost:3000"),
]

# Add CloudFront URL from Parameter Store or environment
cloudfront_url = backend_config.get("cloudfront_url") or os.getenv("CLOUDFRONT_URL")
if cloudfront_url:
    cors_origins.append(cloudfront_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    # Use regex as fallback for other CloudFront domains
    allow_origin_regex=r"^https://[a-z0-9]+\.cloudfront\.net$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type", 
        "X-Requested-With",
        "Accept",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
    ],
)

# Trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "localhost",
        "127.0.0.1",
        "*.amazonaws.com",
        "*.execute-api.us-east-1.amazonaws.com",
        os.getenv("ALLOWED_HOST", "*"),
    ],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)

    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# Health check endpoint (no authentication required)
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    service_name = backend_config.get("service_name", "transcription-evaluator-api")
    return {
        "status": "healthy",
        "service": service_name,
        "version": "2.0.0",
        "authentication": "aws-cognito",
        "authorization": "verified-permissions",
        "timestamp": "2024-01-01T00:00:00Z",  # In real implementation, use datetime.utcnow()
    }


# Root endpoint
@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint with API information."""
    return {
        "message": "Transcription Evaluator API with AWS Cognito Authentication",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "authentication": "Bearer token (Cognito JWT)",
    }


# API information endpoint
@app.get("/api/info")
async def api_info() -> Dict[str, Any]:
    """API information and configuration."""
    return {
        "name": "Transcription Evaluator API",
        "version": "2.0.0",
        "description": "AWS Cognito-integrated API for transcription evaluation and script assignment",
        "authentication": {
            "type": "AWS Cognito JWT",
            "header": "Authorization: Bearer <token>",
        },
        "authorization": {
            "service": "Amazon Verified Permissions",
            "policy_language": "Cedar",
        },
        "features": [
            "User authentication with AWS Cognito",
            "Role-based access control with Cognito Groups",
            "Fine-grained permissions with Verified Permissions",
            "Script assignment management",
            "Audio recording and transcription evaluation",
            "Audit logging and user activity tracking",
        ],
        "roles": [
            {"name": "admin", "description": "System administrators with full access"},
            {
                "name": "evaluator",
                "description": "Evaluators who assess transcription quality",
            },
            {"name": "reviewer", "description": "Reviewers who validate evaluations"},
            {
                "name": "voice_actor",
                "description": "Voice actors who create audio content",
            },
        ],
        "endpoints": {
            "authentication": "/auth",
            "assignments": "/assignments",
            "health": "/health",
            "documentation": "/docs",
        },
    }


# Include routers
app.include_router(auth_router)
app.include_router(assignment_router)
app.include_router(generation_router)
app.include_router(brands_terms_router)
app.include_router(jobs_router)


# Development server configuration
if __name__ == "__main__":
    # Load environment variables
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "false").lower() == "true"

    logger.info(f"Starting development server on {host}:{port}")

    uvicorn.run(
        "transcription_evaluator.api.cognito_main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info" if not debug else "debug",
        access_log=True,
    )
