"""واجهة الويب: صفحة تسجيل العميل + صفحة الكاشير."""
import os
import secrets
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import db
import wallet

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
SECRET = os.environ.get("SESSION_SECRET") or secrets.token_hex(32)
app.add_middleware(SessionMiddleware, secret_key=SECRET, same_site="lax",
                   max_age=60 * 60 * 12, https_only=False)
templates = Jinja2Templates(directory="templates")
db.init_db()

_class_ready = set()          # الكافيهات اللي كلاسها اتأكدنا منه في الجلسة دي
_login_fails = defaultdict(deque)


def _cafe_or_404(slug):
    cafe = db.get_cafe(slug)
    if not cafe:
        raise HTTPException(404)
    return cafe


def _too_many_fails(key, limit=5, window=600):
    q = _login_fails[key]
    while q and time.time() - q[0] > window:
        q.popleft()
    return len(q) >= limit


def _render(request, template, cafe, **ctx):
    return templates.TemplateResponse(request, template, {"cafe": cafe, "accent": cafe["color"], **ctx})


# ---------- العميل ----------
@app.get("/c/{slug}")
def register_page(request: Request, slug: str):
    return _render(request, "register.html", _cafe_or_404(slug))


@app.post("/c/{slug}/register")
def register(request: Request, slug: str, name: str = Form(""), phone: str = Form(""),
             agree: str = Form("")):
    cafe = _cafe_or_404(slug)

    def again(error):
        return _render(request, "register.html", cafe, error=error, name=name, phone=phone)

    try:
        customer = db.register_customer(cafe["id"], phone, name, agree == "yes")
    except db.LoyaltyError as e:
        return again(str(e))
    if customer is None:
        return again("رقمك مسجّل بالفعل في البرنامج. اطلب من الكاشير يساعدك.")
    try:
        if cafe["id"] not in _class_ready:
            wallet.ensure_class(cafe)
            _class_ready.add(cafe["id"])
        link = wallet.create_card(cafe, customer)
    except wallet.WalletError:
        db.delete_customer(customer["id"])      # عشان يقدر يحاول تاني
        return again("حصلت مشكلة مؤقتة في إنشاء الكارت. حاول بعد شوية.")
    return _render(request, "card.html", cafe, customer=customer, link=link)


# ---------- الكاشير ----------
@app.get("/cashier/{slug}")
def cashier_page(request: Request, slug: str):
    cafe = _cafe_or_404(slug)
    if request.session.get("cafe") == slug:
        return _render(request, "cashier.html", cafe)
    return _render(request, "cashier_login.html", cafe)


@app.post("/cashier/{slug}/login")
def cashier_login(request: Request, slug: str, pin: str = Form("")):
    cafe = _cafe_or_404(slug)
    key = f"{request.client.host if request.client else '?'}:{slug}"
    if _too_many_fails(key):
        return _render(request, "cashier_login.html", cafe, error="محاولات كتير، استنى شوية وجرّب تاني.")
    if db.check_cashier_pin(slug, pin):
        request.session["cafe"] = slug
        return RedirectResponse(f"/cashier/{slug}", status_code=303)
    _login_fails[key].append(time.time())
    return _render(request, "cashier_login.html", cafe, error="الكود غلط.")


@app.post("/cashier/{slug}/logout")
def cashier_logout(request: Request, slug: str):
    request.session.clear()
    return RedirectResponse(f"/cashier/{slug}", status_code=303)


def _apply(cafe, data, kind):
    phone = str(data.get("phone", ""))
    key = str(data.get("key", ""))[:64] or None
    fn = db.add_stamp if kind == "stamp" else db.redeem
    try:
        customer, done = fn(cafe["id"], phone, key)
    except db.LoyaltyError as e:
        return {"ok": False, "message": str(e)}
    if not done:
        return {"ok": True, "message": "العملية دي اتسجّلت قبل كده."}
    warning = None
    try:
        wallet.push_stamps(cafe, customer)
    except wallet.WalletError:
        warning = "اتسجّل في النظام، لكن تحديث كارت العميل اتأخر."
    need = cafe["stamps_required"]
    text = f"{customer['name']}: {customer['stamps']} / {need}"
    if kind == "redeem":
        text = "تم صرف المكافأة. " + text
    elif customer["stamps"] >= need:
        text += " — جاهز للمكافأة!"
    return {"ok": True, "message": text, "warning": warning}


@app.post("/cashier/{slug}/{kind}")
async def cashier_action(request: Request, slug: str, kind: str):
    if kind not in ("stamp", "redeem"):
        raise HTTPException(404)
    cafe = _cafe_or_404(slug)
    if request.session.get("cafe") != slug:
        return JSONResponse({"ok": False, "message": "سجّل دخول الأول"}, status_code=401)
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "message": "طلب غير صالح"}, status_code=400)
    return _apply(cafe, data, kind)
