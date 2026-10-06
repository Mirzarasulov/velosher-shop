"""
Эры-проект: Backend + Telegram Bot
Запуск: python bot.py
Требуется: pip install fastapi uvicorn aiogram apscheduler aiosqlite python-jose passlib python-multipart
"""

import os
import hmac
import hashlib
import json
import secrets
import sqlite3
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Header, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from jose import jwt, JWTError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties

# ============================================================
# КОНФИГ
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8673170042:AAE8cDClKSdADlXZ-TQAk8YhDZ3qdgzgEA4")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",") if x.strip()]
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(48))
JWT_ALG = "HS256"
JWT_TTL_HOURS = 24 * 7

WEB_URL = os.getenv("WEB_URL", "http://localhost:8000/web.html")
ADMIN_URL = os.getenv("ADMIN_URL", "http://localhost:8000/admin.html")
DB_PATH = os.getenv("DB_PATH", "era.db")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ============================================================
# БАЗА ДАННЫХ
# ============================================================
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        telegram_username TEXT,
        first_name TEXT,
        last_name TEXT,
        photo_url TEXT,
        referral_code TEXT UNIQUE,
        referrer_id INTEGER,
        status TEXT DEFAULT 'active',
        agreed_terms INTEGER DEFAULT 0,
        agreed_at TEXT,
        registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (referrer_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS eras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        price REAL NOT NULL,
        duration_days INTEGER NOT NULL,
        profit_amount REAL NOT NULL,
        total_amount REAL NOT NULL,
        description TEXT,
        is_active INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        era_id INTEGER NOT NULL,
        era_title TEXT,
        purchase_price REAL NOT NULL,
        duration_days INTEGER NOT NULL,
        profit_amount REAL NOT NULL,
        total_amount REAL NOT NULL,
        status TEXT DEFAULT 'awaiting_payment',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        activated_at TEXT,
        expires_at TEXT,
        completed_at TEXT,
        payout_requested_at TEXT,
        paid_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (era_id) REFERENCES eras(id)
    );

    CREATE TABLE IF NOT EXISTS payouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchase_id INTEGER UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        status TEXT DEFAULT 'pending',
        requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
        paid_at TEXT,
        FOREIGN KEY (purchase_id) REFERENCES purchases(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS content (
        key TEXT PRIMARY KEY,
        value TEXT
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        text TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        read INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS admin_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin TEXT,
        action TEXT,
        details TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Эры по умолчанию (7 штук)
    c.execute("SELECT COUNT(*) FROM eras")
    if c.fetchone()[0] == 0:
        defaults = [
            (1, "Эра №1", 1500, 20, 1000, 2500, "Базовый вход в проект. Оптимальный старт.", 1, 1),
            (2, "Эра №2", 3000, 25, 2200, 5200, "Ускоренный рост с повышенным начислением.", 1, 2),
            (3, "Эра №3", 5000, 30, 4000, 9000, "Сбалансированный вариант для уверенного дохода.", 1, 3),
            (4, "Эра №4", 10000, 35, 8500, 18500, "Для участников, готовых к серьёзному результату.", 1, 4),
            (5, "Эра №5", 25000, 40, 22000, 47000, "Премиальная эра с максимальной отдачей.", 1, 5),
            (6, "Эра №6", 50000, 45, 45000, 95000, "VIP-уровень. Индивидуальный подход.", 1, 6),
            (7, "Эра №7", 100000, 60, 100000, 200000, "Максимальная эра проекта. Для лидеров.", 1, 7),
        ]
        c.executemany("""INSERT INTO eras
            (id,title,price,duration_days,profit_amount,total_amount,description,is_active,sort_order)
            VALUES (?,?,?,?,?,?,?,?,?)""", defaults)

    # Контент по умолчанию
    defaults_content = {
        "marketing_image": "",
        "rules_text": "Правила проекта:\n\n1. Участник обязан соблюдать условия.\n2. Запрещено создавать множественные аккаунты.\n3. Администрация вправе отказать в участии без объяснения причин.\n4. Все спорные ситуации решаются в чате поддержки.",
        "terms_text": "Условия участия:\n\n1. Участник подтверждает, что ознакомлен с правилами.\n2. Участник понимает, что начисление ≠ фактическая выплата.\n3. Выплата производится администратором вручную после завершения эры.\n4. Проект не является финансовым инструментом и не гарантирует доход.\n5. Участие добровольное.",
        "notif_registration": "Добро пожаловать в проект!",
        "notif_purchase_created": "Ваша заявка на покупку создана. Ожидайте связи администратора.",
        "notif_purchase_activated": "Ваша заявка принята. Продукт активирован.",
        "notif_era_completed": "Ваша эра завершена. Вы можете подать заявку на вывод.",
        "notif_payout_requested": "Заявка на вывод создана. Ожидайте выплату.",
        "notif_payout_paid": "Ваша заявка на вывод выполнена. Выплата отправлена.",
    }
    for k, v in defaults_content.items():
        c.execute("INSERT OR IGNORE INTO content (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def get_content(key: str, default: str = "") -> str:
    conn = db()
    row = conn.execute("SELECT value FROM content WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default

def set_content(key: str, value: str):
    conn = db()
    conn.execute("INSERT INTO content (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                 (key, value))
    conn.commit()
    conn.close()

def log_admin(admin: str, action: str, details: str = ""):
    conn = db()
    conn.execute("INSERT INTO admin_actions (admin,action,details) VALUES (?,?,?)", (admin, action, details))
    conn.commit()
    conn.close()

def add_notification(user_id: int, type_: str, text: str):
    conn = db()
    conn.execute("INSERT INTO notifications (user_id,type,text) VALUES (?,?,?)", (user_id, type_, text))
    conn.commit()
    conn.close()

# ============================================================
# JWT
# ============================================================
def make_token(user_id: int, is_admin: bool = False) -> str:
    payload = {
        "sub": str(user_id),
        "adm": is_admin,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_TTL_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        raise HTTPException(401, "Invalid token")

async def current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "No token")
    data = decode_token(authorization.split(" ", 1)[1])
    conn = db()
    row = conn.execute("SELECT * FROM users WHERE id=?", (int(data["sub"]),)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(401, "User not found")
    return dict(row)

async def current_admin(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "No token")
    data = decode_token(authorization.split(" ", 1)[1])
    if not data.get("adm"):
        raise HTTPException(403, "Not admin")
    return {"admin": True}

# ============================================================
# TELEGRAM
# ============================================================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

async def notify_admins(text: str, kb: Optional[InlineKeyboardMarkup] = None):
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid, text, reply_markup=kb)
        except Exception as e:
            print(f"[notify_admins] {aid}: {e}")

async def notify_user(user_id: int, text: str):
    conn = db()
    row = conn.execute("SELECT telegram_id FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if not row or not row["telegram_id"]:
        return
    try:
        await bot.send_message(row["telegram_id"], text)
    except Exception as e:
        print(f"[notify_user] {user_id}: {e}")

@dp.message(Command("start"))
async def cmd_start(message: Message):
    args = message.text.split(maxsplit=1)
    ref = ""
    if len(args) > 1 and args[1].startswith("ref"):
        ref = args[1][3:]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Открыть приложение", web_app=WebAppInfo(url=WEB_URL))]
    ])
    await message.answer(
        "Добро пожаловать в проект «Эры»!\n\n"
        "Нажмите кнопку ниже, чтобы открыть личный кабинет.",
        reply_markup=kb
    )

# ============================================================
# FASTAPI
# ============================================================
app = FastAPI(title="Era Project API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ---------- Pydantic ----------
class TelegramAuth(BaseModel):
    id: int
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    username: Optional[str] = ""
    photo_url: Optional[str] = ""
    auth_date: Optional[int] = 0
    hash: Optional[str] = ""
    ref: Optional[str] = ""

class AdminLogin(BaseModel):
    login: str
    password: str

class EraIn(BaseModel):
    title: str
    price: float
    duration_days: int
    profit_amount: float
    description: str = ""
    is_active: int = 1
    sort_order: int = 0

class ContentIn(BaseModel):
    key: str
    value: str

# ---------- AUTH ----------
def verify_telegram_auth(data: dict) -> bool:
    """Проверка hash от Telegram Login Widget."""
    check_hash = data.get("hash", "")
    if not check_hash:
        return False
    data_check = {k: v for k, v in data.items() if k != "hash" and v is not None and v != ""}
    data_check = {k: str(v) for k, v in data_check.items()}
    data_check_str = "\n".join(f"{k}={data_check[k]}" for k in sorted(data_check))
    secret = hashlib.sha256(BOT_TOKEN.encode()).digest()
    calc = hmac.new(secret, data_check_str.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calc, check_hash)

def gen_ref_code() -> str:
    return "USER" + secrets.token_hex(4).upper()

@app.post("/api/auth/telegram")
async def auth_telegram(payload: TelegramAuth):
    data = payload.model_dump()
    # В dev-режиме разрешаем без hash (для локального теста)
    is_valid = verify_telegram_auth(data) or os.getenv("DEV_MODE", "1") == "1"
    if not is_valid:
        raise HTTPException(401, "Invalid Telegram auth")

    conn = db()
    row = conn.execute("SELECT * FROM users WHERE telegram_id=?", (payload.id,)).fetchone()

    if not row:
        # Регистрация
        ref_code = gen_ref_code()
        referrer_id = None
        if payload.ref:
            r = conn.execute("SELECT id FROM users WHERE referral_code=?", (payload.ref,)).fetchone()
            if r:
                referrer_id = r["id"]

        cur = conn.execute("""INSERT INTO users
            (telegram_id, telegram_username, first_name, last_name, photo_url, referral_code, referrer_id)
            VALUES (?,?,?,?,?,?,?)""",
            (payload.id, payload.username, payload.first_name, payload.last_name,
             payload.photo_url, ref_code, referrer_id))
        user_id = cur.lastrowid
        conn.commit()

        # Уведомления
        add_notification(user_id, "registration", get_content("notif_registration"))
        await notify_user(user_id, get_content("notif_registration"))
        await notify_admins(
            f"🆕 Новый пользователь\n"
            f"Имя: {payload.first_name}\n"
            f"@{payload.username or '—'}\n"
            f"ID: {payload.id}\n"
            f"Реферер: {'да' if referrer_id else 'нет'}"
        )
        if referrer_id:
            await notify_user(referrer_id, f"🎉 У вас новый реферал: {payload.first_name} (@{payload.username or '—'})")
    else:
        user_id = row["id"]

    conn.close()
    token = make_token(user_id, is_admin=False)
    return {"token": token, "is_admin": False}

@app.post("/api/admin/login")
async def admin_login(payload: AdminLogin):
    if payload.login != ADMIN_LOGIN or payload.password != ADMIN_PASSWORD:
        raise HTTPException(401, "Invalid credentials")
    token = make_token(0, is_admin=True)
    return {"token": token, "is_admin": True}

@app.get("/api/me")
async def me(user: dict = Depends(current_user)):
    conn = db()
    ref = None
    if user.get("referrer_id"):
        r = conn.execute("SELECT * FROM users WHERE id=?", (user["referrer_id"],)).fetchone()
        if r:
            ref = {"username": r["telegram_username"], "first_name": r["first_name"]}
    purchases = conn.execute("SELECT COUNT(*) c FROM purchases WHERE user_id=?", (user["id"],)).fetchone()["c"]
    invited = conn.execute("SELECT COUNT(*) c FROM users WHERE referrer_id=?", (user["id"],)).fetchone()["c"]
    conn.close()
    return {
        "id": user["id"],
        "telegram_id": user["telegram_id"],
        "telegram_username": user["telegram_username"],
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "photo_url": user["photo_url"],
        "referral_code": user["referral_code"],
        "referrer": ref,
        "status": user["status"],
        "agreed_terms": bool(user["agreed_terms"]),
        "agreed_at": user["agreed_at"],
        "registered_at": user["registered_at"],
        "purchases_count": purchases,
        "invited_count": invited
    }

@app.post("/api/agree")
async def agree(user: dict = Depends(current_user)):
    conn = db()
    conn.execute("UPDATE users SET agreed_terms=1, agreed_at=? WHERE id=?",
                 (now_iso(), user["id"]))
    conn.commit()
    conn.close()
    add_notification(user["id"], "terms", "Вы подтвердили условия участия.")
    return {"ok": True}

# ---------- CONTENT ----------
@app.get("/api/content/{key}")
async def get_content_api(key: str):
    return {"key": key, "value": get_content(key)}

# ---------- ERAS ----------
@app.get("/api/eras")
async def list_eras():
    conn = db()
    rows = conn.execute("SELECT * FROM eras WHERE is_active=1 ORDER BY sort_order, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ---------- PURCHASES ----------
@app.post("/api/purchases/create/{era_id}")
async def create_purchase(era_id: int, user: dict = Depends(current_user)):
    if not user["agreed_terms"]:
        raise HTTPException(403, "Сначала подтвердите условия участия")

    conn = db()
    era = conn.execute("SELECT * FROM eras WHERE id=? AND is_active=1", (era_id,)).fetchone()
    if not era:
        conn.close()
        raise HTTPException(404, "Эра не найдена или недоступна")

    # Защита от дубля: активная или ожидающая заявка на эту эру
    dup = conn.execute("""SELECT id FROM purchases
        WHERE user_id=? AND era_id=? AND status IN ('awaiting_payment','active','completed','awaiting_payout')""",
        (user["id"], era_id)).fetchone()
    if dup:
        conn.close()
        raise HTTPException(409, "У вас уже есть активная заявка на эту эру")

    cur = conn.execute("""INSERT INTO purchases
        (user_id, era_id, era_title, purchase_price, duration_days, profit_amount, total_amount, status)
        VALUES (?,?,?,?,?,?,?,'awaiting_payment')""",
        (user["id"], era["id"], era["title"], era["price"], era["duration_days"],
         era["profit_amount"], era["total_amount"]))
    pid = cur.lastrowid
    conn.commit()
    conn.close()

    add_notification(user["id"], "purchase", get_content("notif_purchase_created"))
    await notify_user(user["id"], get_content("notif_purchase_created"))
    await notify_admins(
        f"🛒 Новая заявка на покупку #{pid}\n"
        f"Пользователь: {user['first_name']} @{user['telegram_username'] or '—'}\n"
        f"Telegram ID: {user['telegram_id']}\n"
        f"Эра: {era['title']}\n"
        f"Стоимость: {era['price']} ₽\n"
        f"Срок: {era['duration_days']} дн.\n"
        f"Начисление: {era['profit_amount']} ₽\n"
        f"Итого: {era['total_amount']} ₽\n"
        f"Дата: {now_iso()}"
    )
    return {"ok": True, "purchase_id": pid}

@app.get("/api/purchases/my")
async def my_purchases(user: dict = Depends(current_user)):
    conn = db()
    rows = conn.execute("SELECT * FROM purchases WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall()
    conn.close()
    result = []
    now = datetime.now(timezone.utc)
    for r in rows:
        d = dict(r)
        d["days_left"] = calc_days_left(d)
        result.append(d)
    return result

def calc_days_left(p: dict) -> int:
    if p["status"] != "active" or not p.get("expires_at"):
        return 0
    try:
        exp = datetime.fromisoformat(p["expires_at"].replace("Z", "+00:00"))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        left = (exp - datetime.now(timezone.utc)).days
        return max(0, left)
    except Exception:
        return 0

# ---------- PAYOUTS ----------
@app.post("/api/payouts/request/{purchase_id}")
async def request_payout(purchase_id: int, user: dict = Depends(current_user)):
    conn = db()
    p = conn.execute("SELECT * FROM purchases WHERE id=? AND user_id=?", (purchase_id, user["id"])).fetchone()
    if not p:
        conn.close()
        raise HTTPException(404, "Покупка не найдена")
    if p["status"] not in ("completed",):
        conn.close()
        raise HTTPException(400, "Заявку можно подать только по завершённой эре")
    # Защита от дубля
    existing = conn.execute("SELECT id FROM payouts WHERE purchase_id=?", (purchase_id,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(409, "Заявка на вывод уже создана")

    conn.execute("""INSERT INTO payouts (purchase_id, user_id, amount, status)
        VALUES (?,?,?, 'pending')""", (purchase_id, user["id"], p["total_amount"]))
    conn.execute("UPDATE purchases SET status='awaiting_payout', payout_requested_at=? WHERE id=?",
                 (now_iso(), purchase_id))
    conn.commit()
    conn.close()

    add_notification(user["id"], "payout", get_content("notif_payout_requested"))
    await notify_user(user["id"], get_content("notif_payout_requested"))
    await notify_admins(
        f"💸 Новая заявка на вывод\n"
        f"Пользователь: {user['first_name']} @{user['telegram_username'] or '—'}\n"
        f"Telegram ID: {user['telegram_id']}\n"
        f"Покупка #{purchase_id}: {p['era_title']}\n"
        f"Сумма к выплате: {p['total_amount']} ₽"
    )
    return {"ok": True}

# ---------- NOTIFICATIONS ----------
@app.get("/api/notifications")
async def notifications(user: dict = Depends(current_user)):
    conn = db()
    rows = conn.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50",
                        (user["id"],)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ---------- REFERRALS ----------
@app.get("/api/referrals")
async def referrals(user: dict = Depends(current_user)):
    conn = db()
    rows = conn.execute("""SELECT id, telegram_username, first_name, registered_at, status,
        (SELECT COUNT(*) FROM purchases WHERE user_id=users.id) AS purchases_count
        FROM users WHERE referrer_id=? ORDER BY id DESC""", (user["id"],)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ============================================================
# АДМИН API
# ============================================================
@app.get("/api/admin/dashboard")
async def admin_dashboard(_: dict = Depends(current_admin)):
    conn = db()
    def scalar(q, *a):
        return conn.execute(q, a).fetchone()[0]
    data = {
        "users": scalar("SELECT COUNT(*) FROM users"),
        "active_eras": scalar("SELECT COUNT(*) FROM purchases WHERE status='active'"),
        "completed_eras": scalar("SELECT COUNT(*) FROM purchases WHERE status IN ('completed','awaiting_payout','paid')"),
        "purchase_requests": scalar("SELECT COUNT(*) FROM purchases WHERE status='awaiting_payment'"),
        "payout_requests": scalar("SELECT COUNT(*) FROM payouts WHERE status='pending'"),
        "total_purchases_sum": scalar("SELECT COALESCE(SUM(purchase_price),0) FROM purchases WHERE status NOT IN ('awaiting_payment')"),
        "total_profit_sum": scalar("SELECT COALESCE(SUM(profit_amount),0) FROM purchases WHERE status IN ('active','completed','awaiting_payout','paid')"),
        "total_paid_sum": scalar("SELECT COALESCE(SUM(amount),0) FROM payouts WHERE status='paid'"),
    }
    conn.close()
    return data

@app.get("/api/admin/users")
async def admin_users(_: dict = Depends(current_admin)):
    conn = db()
    rows = conn.execute("""SELECT u.*,
        (SELECT telegram_username FROM users WHERE id=u.referrer_id) AS referrer_username,
        (SELECT COUNT(*) FROM purchases WHERE user_id=u.id) AS purchases_count
        FROM users u ORDER BY u.id DESC""").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/admin/purchases")
async def admin_purchases(_: dict = Depends(current_admin)):
    conn = db()
    rows = conn.execute("""SELECT p.*, u.telegram_username, u.first_name, u.telegram_id
        FROM purchases p JOIN users u ON u.id=p.user_id ORDER BY p.id DESC""").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["days_left"] = calc_days_left(d)
        result.append(d)
    return result

@app.post("/api/admin/purchases/{pid}/confirm")
async def admin_confirm_purchase(pid: int, _: dict = Depends(current_admin)):
    conn = db()
    p = conn.execute("SELECT * FROM purchases WHERE id=?", (pid,)).fetchone()
    if not p:
        conn.close()
        raise HTTPException(404, "Не найдено")
    if p["status"] != "awaiting_payment":
        conn.close()
        raise HTTPException(400, "Неверный статус")

    activated = datetime.now(timezone.utc)
    expires = activated + timedelta(days=p["duration_days"])
    conn.execute("""UPDATE purchases SET status='active', activated_at=?, expires_at=?
        WHERE id=?""", (activated.isoformat(), expires.isoformat(), pid))
    conn.commit()
    conn.close()

    log_admin("admin", "confirm_purchase", f"purchase #{pid}")
    add_notification(p["user_id"], "activated", get_content("notif_purchase_activated"))
    await notify_user(p["user_id"], get_content("notif_purchase_activated"))
    return {"ok": True, "activated_at": activated.isoformat(), "expires_at": expires.isoformat()}

@app.post("/api/admin/purchases/{pid}/cancel")
async def admin_cancel_purchase(pid: int, _: dict = Depends(current_admin)):
    conn = db()
    conn.execute("UPDATE purchases SET status='cancelled' WHERE id=? AND status='awaiting_payment'", (pid,))
    conn.commit()
    conn.close()
    log_admin("admin", "cancel_purchase", f"purchase #{pid}")
    return {"ok": True}

@app.get("/api/admin/payouts")
async def admin_payouts(_: dict = Depends(current_admin)):
    conn = db()
    rows = conn.execute("""SELECT po.*, u.telegram_username, u.first_name, u.telegram_id,
        p.era_title, p.purchase_price, p.profit_amount, p.total_amount
        FROM payouts po
        JOIN users u ON u.id=po.user_id
        JOIN purchases p ON p.id=po.purchase_id
        ORDER BY po.id DESC""").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/admin/payouts/{pid}/mark_paid")
async def admin_mark_paid(pid: int, _: dict = Depends(current_admin)):
    conn = db()
    po = conn.execute("SELECT * FROM payouts WHERE id=?", (pid,)).fetchone()
    if not po:
        conn.close()
        raise HTTPException(404, "Не найдено")
    if po["status"] == "paid":
        conn.close()
        raise HTTPException(400, "Уже выплачено")

    paid_at = now_iso()
    conn.execute("UPDATE payouts SET status='paid', paid_at=? WHERE id=?", (paid_at, pid))
    conn.execute("UPDATE purchases SET status='paid', paid_at=? WHERE id=?", (paid_at, po["purchase_id"]))
    conn.commit()
    conn.close()

    log_admin("admin", "mark_paid", f"payout #{pid}")
    add_notification(po["user_id"], "paid", get_content("notif_payout_paid"))
    await notify_user(po["user_id"], get_content("notif_payout_paid"))
    return {"ok": True}

@app.post("/api/admin/payouts/{pid}/cancel")
async def admin_cancel_payout(pid: int, _: dict = Depends(current_admin)):
    conn = db()
    po = conn.execute("SELECT * FROM payouts WHERE id=?", (pid,)).fetchone()
    if not po:
        conn.close()
        raise HTTPException(404, "Не найдено")
    conn.execute("DELETE FROM payouts WHERE id=?", (pid,))
    conn.execute("UPDATE purchases SET status='completed', payout_requested_at=NULL WHERE id=?",
                 (po["purchase_id"],))
    conn.commit()
    conn.close()
    log_admin("admin", "cancel_payout", f"payout #{pid}")
    return {"ok": True}

@app.get("/api/admin/eras")
async def admin_eras(_: dict = Depends(current_admin)):
    conn = db()
    rows = conn.execute("SELECT * FROM eras ORDER BY sort_order, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.put("/api/admin/eras/{eid}")
async def admin_update_era(eid: int, payload: EraIn, _: dict = Depends(current_admin)):
    conn = db()
    conn.execute("""UPDATE eras SET title=?, price=?, duration_days=?, profit_amount=?,
        total_amount=?, description=?, is_active=?, sort_order=? WHERE id=?""",
        (payload.title, payload.price, payload.duration_days, payload.profit_amount,
         payload.price + payload.profit_amount, payload.description, payload.is_active,
         payload.sort_order, eid))
    conn.commit()
    conn.close()
    log_admin("admin", "update_era", f"era #{eid}")
    return {"ok": True}

@app.post("/api/admin/eras")
async def admin_create_era(payload: EraIn, _: dict = Depends(current_admin)):
    conn = db()
    cur = conn.execute("""INSERT INTO eras (title,price,duration_days,profit_amount,
        total_amount,description,is_active,sort_order) VALUES (?,?,?,?,?,?,?,?)""",
        (payload.title, payload.price, payload.duration_days, payload.profit_amount,
         payload.price + payload.profit_amount, payload.description, payload.is_active, payload.sort_order))
    eid = cur.lastrowid
    conn.commit()
    conn.close()
    log_admin("admin", "create_era", f"era #{eid}")
    return {"ok": True, "id": eid}

@app.post("/api/admin/content")
async def admin_set_content(payload: ContentIn, _: dict = Depends(current_admin)):
    set_content(payload.key, payload.value)
    log_admin("admin", "set_content", payload.key)
    return {"ok": True}

@app.post("/api/admin/upload/marketing")
async def admin_upload_marketing(file: UploadFile = File(...), _: dict = Depends(current_admin)):
    ext = os.path.splitext(file.filename or "img.png")[1] or ".png"
    name = f"marketing_{secrets.token_hex(4)}{ext}"
    path = os.path.join(UPLOAD_DIR, name)
    with open(path, "wb") as f:
        f.write(await file.read())
    url = f"/uploads/{name}"
    set_content("marketing_image", url)
    log_admin("admin", "upload_marketing", url)
    return {"ok": True, "url": url}

@app.get("/api/admin/actions")
async def admin_actions(_: dict = Depends(current_admin)):
    conn = db()
    rows = conn.execute("SELECT * FROM admin_actions ORDER BY id DESC LIMIT 200").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/admin/referral_tree/{user_id}")
async def admin_ref_tree(user_id: int, _: dict = Depends(current_admin)):
    conn = db()
    def children(uid):
        rows = conn.execute("SELECT id, telegram_username, first_name FROM users WHERE referrer_id=?", (uid,)).fetchall()
        return [{"id": r["id"], "username": r["telegram_username"], "name": r["first_name"],
                 "children": children(r["id"])} for r in rows]
    tree = children(user_id)
    conn.close()
    return {"user_id": user_id, "children": tree}

# ============================================================
# АВТОМАТИЗАЦИЯ: проверка сроков
# ============================================================
async def check_expired_eras():
    conn = db()
    now = now_iso()
    rows = conn.execute("""SELECT * FROM purchases
        WHERE status='active' AND expires_at IS NOT NULL AND expires_at <= ?""", (now,)).fetchall()
    for p in rows:
        conn.execute("UPDATE purchases SET status='completed', completed_at=? WHERE id=?",
                     (now, p["id"]))
        add_notification(p["user_id"], "completed", get_content("notif_era_completed"))
        await notify_user(p["user_id"], get_content("notif_era_completed"))
    conn.commit()
    conn.close()
    if rows:
        print(f"[scheduler] completed {len(rows)} purchases")

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def on_startup():
    init_db()
    scheduler.add_job(check_expired_eras, "interval", minutes=5, next_run_time=datetime.now(timezone.utc))
    scheduler.start()
    # Запуск бота в фоне
    asyncio.create_task(dp.start_polling(bot))

@app.on_event("shutdown")
async def on_shutdown():
    scheduler.shutdown(wait=False)
    await bot.session.close()

# ---------- Отдача страниц ----------
@app.get("/")
async def root():
    return HTMLResponse('<meta http-equiv="refresh" content="0; url=/web.html">')

@app.get("/web.html")
async def serve_web():
    return FileResponse("web.html")

@app.get("/admin.html")
async def serve_admin():
    return FileResponse("admin.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)