from fastapi import FastAPI

from app import db
from app.routers import cartonizzazioni, spedizioni

app = FastAPI(title="VISCOTTA Shipping API")
app.include_router(cartonizzazioni.router)
app.include_router(spedizioni.router)


@app.get("/health")
def health():
    return {"status": "ok", "db": "ok" if db.ping() else "unreachable"}
