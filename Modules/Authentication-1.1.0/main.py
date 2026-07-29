import os

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

try:
    from .router import HealthResponse, ReadinessResponse, liveness, readiness, router
except ImportError:  # Keeps `python main.py` working from this directory.
    from router import HealthResponse, ReadinessResponse, liveness, readiness, router

# Stays standalone-runnable: `uvicorn modules.auth.main:app` from the repo
# root, OR `python main.py` from inside modules/auth/. Either works.

_dir = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="INSIGHT Authentication", docs_url="/api/auth/docs")
app.include_router(router)
app.mount("/static", StaticFiles(directory=os.path.join(_dir, "static")), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(_dir, "static", "index.html"))


@app.get("/healthz", response_model=HealthResponse, tags=["ops"])
def healthz():
    return liveness()


@app.get("/readyz", response_model=ReadinessResponse, tags=["ops"])
def readyz(response: Response):
    return readiness(response)


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    """
    SPA-like fallback so deep links on the login surface resolve to the same
    page. Login/disclaimer screens are single-file; deeper dashboard routes
    belong to other modules hosted at /dashboard/*.

    ponytail: no actual SPA routing — justFiles the HTML; relevant only for
    human navigators. Real API routes are mount-prefixed (/api/auth/*).
    """
    if full_path.startswith("api/"):
        # Let FastAPI's 404 handler take over for unknown API routes.
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not Found")
    return index()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("AUTH_PORT", "8000")))
