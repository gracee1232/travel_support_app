"""
FastAPI Application Entry Point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .api import router
from .config import settings


# Create FastAPI app
app = FastAPI(
    title="Travel Planner Chatbot",
    description="AI-powered travel itinerary planner with constraint-based planning",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)

# Get the frontend directory path
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# Mount static files if frontend exists
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    
    @app.get("/")
    async def serve_frontend():
        """Serve the frontend."""
        return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "engine": "grounded-engine"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
    