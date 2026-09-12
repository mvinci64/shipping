"""Login per shipping-web — stessi account del Portal (viscotta.users),
sessione separata (nuova riga in viscotta.sessions, non condivisa con il
cookie del Portal: domini diversi, spedizioni.viscotta.com non riceverebbe
comunque il cookie di app.viscotta.com). Accesso riservato al ruolo
"admin": "agent" nel Portal sono agenti commerciali esterni, non hanno
nulla a che fare con il reparto spedizioni."""
import bcrypt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app import db

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class UtenteResponse(BaseModel):
    email: str
    full_name: str
    roles: list[str]


class LoginResponse(BaseModel):
    token: str
    expires_at: str
    user: UtenteResponse


class LogoutRequest(BaseModel):
    token: str


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request) -> LoginResponse:
    utente = db.fetch_user_by_email(body.email)
    if utente is None or not utente["is_active"]:
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    if not bcrypt.checkpw(body.password.encode(), utente["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    if "admin" not in utente["roles"]:
        raise HTTPException(status_code=403, detail="Account non abilitato al reparto spedizioni")

    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or None
    user_agent = request.headers.get("user-agent")
    token, expires_at = db.create_session(utente["id"], ip, user_agent)

    return LoginResponse(
        token=token,
        expires_at=expires_at,
        user=UtenteResponse(email=utente["email"], full_name=utente["full_name"], roles=utente["roles"]),
    )


@router.get("/session", response_model=UtenteResponse)
def session(request: Request) -> UtenteResponse:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Token mancante")
    token = auth_header[7:]

    utente = db.fetch_session_user(token)
    if utente is None:
        raise HTTPException(status_code=401, detail="Sessione non valida o scaduta")

    return UtenteResponse(email=utente["email"], full_name=utente["full_name"], roles=utente["roles"])


@router.post("/logout")
def logout(body: LogoutRequest) -> dict:
    db.revoke_session(body.token)
    return {"status": "ok"}
