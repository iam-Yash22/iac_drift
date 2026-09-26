"""Application entry point for IaC DriftWatch.

Instantiates and exposes the FastAPI ASGI application for uvicorn/gunicorn.
"""

from app.factory import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)