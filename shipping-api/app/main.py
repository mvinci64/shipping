from fastapi import FastAPI
from pydantic import BaseModel

from app import db
from app.routers import auth, cartonizzazioni, spedizioni

app = FastAPI(title="VISCOTTA Shipping API")
app.include_router(cartonizzazioni.router)
app.include_router(spedizioni.router)
app.include_router(auth.router)


class Health(BaseModel):
    status: str
    db: str


@app.get("/health", response_model=Health)
def health() -> Health:
    return Health(status="ok", db="ok" if db.ping() else "unreachable")
