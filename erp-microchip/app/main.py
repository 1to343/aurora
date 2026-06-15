from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from .models import ROLE_TITLES_RU, Role, User
from .routers import audit, chat, infrastructure, logistics, power, production, wms
from .security import audit as write_audit
from .security import get_current_user, make_token, verify_password

BASE_DIR = Path(__file__).parent

app = FastAPI(title="ERP Микрочипы — MVP", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

app.include_router(wms.router)
app.include_router(production.router)
app.include_router(audit.router)
app.include_router(chat.router)
app.include_router(power.router)
app.include_router(logistics.router)
app.include_router(infrastructure.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


# ---- Resilience: health + service worker ----

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/sw.js")
def service_worker():
    resp = FileResponse(BASE_DIR / "static" / "sw.js", media_type="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


# ---- Web ----

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str | None = None):
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": error}
    )


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return RedirectResponse(url="/login?error=1", status_code=303)
    token = make_token(user)
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(
        "access_token", token, httponly=True, samesite="lax", max_age=60 * 60 * 8
    )
    write_audit(db, user, "login", ip=request.client.host if request.client else "")
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("access_token")
    return resp


def _ctx(request: Request, user: User, **extra):
    return {
        "request": request,
        "user": user,
        "role_title": ROLE_TITLES_RU.get(user.role, user.role.value),
        **extra,
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("dashboard.html", _ctx(request, user))


@app.get("/wms", response_class=HTMLResponse)
def wms_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("wms.html", _ctx(request, user))


@app.get("/production", response_class=HTMLResponse)
def prod_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("production.html", _ctx(request, user))


@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("chat.html", _ctx(request, user))


@app.get("/logistics", response_class=HTMLResponse)
def logistics_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("logistics.html", _ctx(request, user))


@app.get("/tree", response_class=HTMLResponse)
def tree_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("tree.html", _ctx(request, user))


@app.get("/audit", response_class=HTMLResponse)
def audit_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("audit.html", _ctx(request, user))


@app.get("/infrastructure", response_class=HTMLResponse)
def infrastructure_page(request: Request, user: User = Depends(get_current_user)):
    if user.role not in (Role.ADMIN, Role.DIRECTOR, Role.SHIFT_LEAD, Role.MECHANIC):
        raise HTTPException(403, "Недостаточно прав для модуля инфраструктуры")
    return templates.TemplateResponse("infrastructure.html", _ctx(request, user))


@app.get("/shift-summary", response_class=HTMLResponse)
def shift_summary_page(request: Request, user: User = Depends(get_current_user)):
    if user.role not in (Role.ADMIN, Role.DIRECTOR, Role.SHIFT_LEAD):
        raise HTTPException(403, "Доступно только для смены, директора и админа")
    return templates.TemplateResponse("shift_summary.html", _ctx(request, user))


# превратить 401 на HTML-страницах в редирект на логин
@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    if (
        exc.status_code == 401
        and not request.url.path.startswith("/api/")
        and request.url.path != "/login"
    ):
        return RedirectResponse(url="/login", status_code=303)
    from fastapi.responses import JSONResponse

    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
