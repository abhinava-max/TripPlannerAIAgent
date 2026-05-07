from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .routers.trip_router import router as trip_router
from .routers.health_router import router as health_router
from .routers.external_api_router import router as external_api_router
from .routers.policy_router import router as policy_router

app = FastAPI(
    title="Trip Planner AI Agent",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health_router)
app.include_router(trip_router)
app.include_router(external_api_router)
app.include_router(policy_router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app.mount(
    "/frontend",
    StaticFiles(directory=FRONTEND_DIR),
    name="frontend"
)


@app.get("/")
def root():
    return RedirectResponse(url="/frontend/index.html")
