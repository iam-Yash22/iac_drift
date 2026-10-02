from fastapi import FastAPI
from app.middleware import register_middleware

app = FastAPI()
register_middleware(app)
for mw in app.user_middleware:
    if mw.cls.__name__ == "CORSMiddleware":
        print(mw.kwargs.get("allow_origins"))
