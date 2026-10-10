import time
import threading
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ============================================================
# КОНФИГ
# ============================================================
BOT_TOKEN = "8880107122:AAFixW8sKxpKYm6dmQ5wMKALlBIjAj4zlMM"
ADMIN_IDS = [6040186314, 6972338698, 6544017826]
ADMIN_ID = ADMIN_IDS[0]

CHANNEL_ID = -1004305451466
FIREBASE = "https://velosher-f82b5-default-rtdb.asia-southeast1.firebasedatabase.app"
WEB_URL = "https://mirzarasulov.github.io/velosher-shop/tester/web.html?v=4"
ADMIN_URL = "https://mirzarasulov.github.io/velosher-shop/tester/admin.html?v=4"

PDF_FILENAME = "РОСТЭРА.pdf"
PDF_PATH = Path(PDF_FILENAME)
AGREE_TEXT = "📄 Подтвердите ознакомление с условиями:"
WELCOME_AFTER = (
    "👋 <b>Добро пожаловать в проект «РОСТЭРА»!</b>\n\n"
    "Откройте приложение:\n\n"
)
AGREE_CALLBACK = "user_agree_terms"

# ============================================================
# ТЕКСТЫ ИНФО-РАЗДЕЛОВ
# ============================================================
HOW_IT_WORKS = (
    "📖 <b>Как работает РОСТЭРА?</b>\n\n"
    "РОСТЭРА работает по модели <b>P2P</b> — от участника к участнику. "
    "Общего фонда проекта нет: переводы проходят между участниками "
    "по реквизитам, которые сообщает администрация.\n\n"
    "После завершения срока Эры участник может подать заявку на выплату. "
    "Она обрабатывается в порядке очереди, а возможность и сроки выплаты "
    "зависят от покупок других участников."
)

RULES_TEXT = (
    "📜 <b>Правила проекта</b>\n\n"
    "<b>1. Уважение к участникам</b>\n"
    "В официальной группе запрещены оскорбления, угрозы, унижение, "
    "провокации и переходы на личности. Просим общаться корректно и уважительно.\n\n"
    "<b>2. Проведение операций</b>\n"
    "Заявки и операции оформляются через официальную группу и представителя "
    "администрации. Перед переводом дождитесь реквизитов и инструкций по своей "
    "заявке. Соблюдайте установленный порядок: его нарушение может задержать "
    "операцию или сделать её невозможной.\n\n"
    "<b>3. Изменение условий проекта</b>\n"
    "Администрация может обновлять маркетинг, условия и правила проекта. "
    "Изменения публикуются в официальной группе — перед участием ознакомьтесь "
    "с актуальной информацией.\n\n"
    "<b>4. Решения администрации</b>\n"
    "При нарушении правил администрация может удалить сообщение, ограничить "
    "возможность писать в группе или исключить участника.\n\n"
    "<b>5. Финансовые решения</b>\n"
    "Указанные суммы и сроки не гарантируют получение выплаты или конкретный "
    "результат. Каждый участник самостоятельно оценивает свои финансовые "
    "возможности и принимает решение об участии.\n\n"
    "Желаем удачи)🤗"
)

DEFAULT_DAYS = 30
TZ = timezone(timedelta(hours=5))
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
REFERRAL_PERCENT = 5

offset = {"v": 0}
last_seen_purchase_id = 0
last_seen_payout_id = 0
last_seen_ref_request_id = 0
AGREE_MESSAGES = {}
PURCHASE_STATUS_CACHE = {}
PAYOUT_STATUS_CACHE = {}
REF_REQUEST_STATUS_CACHE = {}
BOT_USERNAME = "ROSTERAbot"

SESSION = requests.Session()
SESSION.headers.update({"Connection": "keep-alive"})

# ============================================================
# FIREBASE
# ============================================================
def fb_get(path):
    try:
        r = SESSION.get(f"{FIREBASE}/{path}.json", timeout=5)
        return r.json()
    except Exception as e:
        log("FB", f"GET {path} ошибка: {e}")
        return None

def fb_patch(path, data):
    try:
        r = SESSION.patch(f"{FIREBASE}/{path}.json", json=data, timeout=5)
        return r.ok
    except Exception as e:
        log("FB", f"PATCH {path} ошибка: {e}")
        return False

def fb_put(path, data):
    try:
        r = SESSION.put(f"{FIREBASE}/{path}.json", json=data, timeout=5)
        return r.ok
    except Exception as e:
        log("FB", f"PUT {path} ошибка: {e}")
        return False

def fb_post(path, data):
    try:
        r = SESSION.post(f"{FIREBASE}/{path}.json", json=data, timeout=5)
        return r.json() if r.ok else None
    except Exception as e:
        log("FB", f"POST {path} ошибка: {e}")
        return None

def log(tag, msg):
    print(f"[{datetime.now(TZ).strftime('%H:%M:%S')}] [{tag}] {msg}", flush=True)

# ============================================================
# TELEGRAM CORE
# ============================================================
def tg(method, **kwargs):
    try:
        r = SESSION.post(f"{API}/{method}", json=kwargs, timeout=10)
        data = r.json()
        if not data.get("ok"):
            log("TG", f"{method} FAIL: {data.get('description')}")
        return data
    except Exception as e:
        log("TG", f"{method} EXC: {e}")
        return None

def tg_send(chat_id, text, kb=None, parse_mode="HTML"):
    if not chat_id:
        return False
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode,
               "disable_web_page_preview": True}
    if kb is not None:
        payload["reply_markup"] = kb
    res = tg("sendMessage", **payload)
    return bool(res and res.get("ok"))

def tg_edit(chat_id, msg_id, text, kb=None):
    payload = {"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": "HTML"}
    if kb is not None:
        payload["reply_markup"] = kb
    return tg("editMessageText", **payload)

def tg_delete(chat_id, msg_id):
    if not chat_id or not msg_id:
        return
    return tg("deleteMessage", chat_id=chat_id, message_id=msg_id)

def tg_answer(cb_id, text="", alert=False):
    return tg("answerCallbackQuery", callback_query_id=cb_id, text=text, show_alert=alert)

def is_admin(uid):
    try:
        return int(uid) in ADMIN_IDS
    except:
        return False

def notify_admins(text, kb=None):
    for aid in ADMIN_IDS:
        tg_send(aid, text, kb=kb)

# ============================================================
# 🚫 БЛОКИРОВКА
# ============================================================
def is_blocked(uid):
    try:
        u = fb_get(f"users/{uid}")
        if not u:
            return None
        if u.get("blocked"):
            return u.get("block_reason") or "Нарушение правил"
        return None
    except Exception as e:
        log("BLOCK", f"ошибка проверки {uid}: {e}")
        return None

def send_blocked_msg(chat_id, reason):
    tg_send(chat_id,
            f"🚫 <b>Вы заблокированы администрацией</b>\n\n"
            f"📝 Причина: <i>{reason}</i>\n\n"
            f"Обратитесь в поддержку для выяснения деталей.",
            kb={"inline_keyboard": [[
                {"text": "💬 Написать в поддержку", "url": "https://t.me/DAMIR1500"}
            ]]})
    log("BLOCK", f"юзер {chat_id} заблокирован — отказано")

# ============================================================
# УТИЛИТЫ
# ============================================================
def fmt_money(v):
    try:
        return f"{int(float(v)):,}".replace(",", " ") + " ₽"
    except:
        return f"{v} ₽"

def now_iso():
    return datetime.now(TZ).isoformat()

def parse_dt(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ)
    except:
        return None

def fmt_date(dt):
    if isinstance(dt, str):
        dt = parse_dt(dt)
    if not dt:
        return "—"
    months = ["янв","фев","мар","апр","мая","июн",
              "июл","авг","сен","окт","ноя","дек"]
    return f"{dt.day} {months[dt.month-1]} {dt.year}"

def fmt_dt(s):
    dt = parse_dt(s)
    return dt.strftime("%d.%m.%Y %H:%M") if dt else "—"

def calc_dates(activated_at, days):
    d0 = activated_at.date() if isinstance(activated_at, datetime) else parse_dt(activated_at).date()
    first = d0 + timedelta(days=1)
    last = first + timedelta(days=days - 1)
    expires = last + timedelta(days=1)
    return {
        "start_date": datetime(first.year, first.month, first.day, tzinfo=TZ).isoformat(),
        "last_day": datetime(last.year, last.month, last.day, tzinfo=TZ).isoformat(),
        "expires_at": datetime(expires.year, expires.month, expires.day, tzinfo=TZ).isoformat(),
    }

def find_record(collection, target_id):
    all_ = fb_get(collection) or {}
    if not isinstance(all_, dict):
        return None, None
    if str(target_id) in all_:
        v = all_[str(target_id)]
        if isinstance(v, dict):
            return str(target_id), v
    for k, v in all_.items():
        if isinstance(v, dict) and str(v.get("id")) == str(target_id):
            return k, v
    return None, None

def get_referral_bonus(p):
    if p.get("referral_bonus") not in (None, ""):
        try:
            return int(float(p.get("referral_bonus")))
        except:
            pass
    try:
        return int(float(p.get("purchase_price", 0)) * REFERRAL_PERCENT / 100)
    except:
        return 0

def ref_has_active_era(ref_uid):
    ref_uid = str(ref_uid)
    purchases = fb_get("purchases") or {}
    now = datetime.now(TZ)
    if not isinstance(purchases, dict):
        return False
    for p in purchases.values():
        if not isinstance(p, dict):
            continue
        if str(p.get("user_telegram_id")) != ref_uid:
            continue
        if p.get("status") != "approved":
            continue
        exp = parse_dt(p.get("expires_at"))
        if exp and exp > now:
            return True
    return False

def activate_pending_bonuses(ref_uid):
    ref_uid = str(ref_uid)
    users = fb_get("users") or {}
    purchases = fb_get("purchases") or {}
    my_ids = set()
    if isinstance(users, dict):
        for u in users.values():
            if isinstance(u, dict) and str(u.get("referrer_uid", "")) == ref_uid:
                my_ids.add(str(u.get("telegram_id")))
    activated = 0
    total = 0
    now = now_iso()
    if isinstance(purchases, dict):
        for pk, p in purchases.items():
            if not isinstance(p, dict):
                continue
            if str(p.get("user_telegram_id")) not in my_ids:
                continue
            if p.get("status") in ("rejected", "cancelled"):
                continue
            if (p.get("referral_status") or "") != "pending_active":
                continue
            bonus = get_referral_bonus(p)
            if bonus <= 0:
                continue
            fb_patch(f"purchases/{pk}", {
                "referral_status": "approved",
                "referral_activated_at": now,
                "referral_activated_reason": "ref_active_after_purchase",
            })
            activated += 1
            total += bonus
    return activated, total

def force_activate_pending_bonuses(ref_uid):
    ref_uid = str(ref_uid)
    users = fb_get("users") or {}
    purchases = fb_get("purchases") or {}
    my_ids = set()
    if isinstance(users, dict):
        for u in users.values():
            if isinstance(u, dict) and str(u.get("referrer_uid", "")) == ref_uid:
                my_ids.add(str(u.get("telegram_id")))
    count = 0
    total = 0
    now = now_iso()
    if isinstance(purchases, dict):
        for pk, p in purchases.items():
            if not isinstance(p, dict): continue
            if str(p.get("user_telegram_id")) not in my_ids: continue
            if p.get("status") in ("rejected", "cancelled"): continue
            if (p.get("referral_status") or "") != "pending_active": continue
            bonus = get_referral_bonus(p)
            if bonus <= 0: continue
            fb_patch(f"purchases/{pk}", {
                "referral_status": "approved",
                "referral_activated_at": now,
                "referral_activated_by": "admin_manual",
            })
            count += 1
            total += bonus
    return count, total

def reject_pending_bonuses(ref_uid):
    ref_uid = str(ref_uid)
    users = fb_get("users") or {}
    purchases = fb_get("purchases") or {}
    my_ids = set()
    if isinstance(users, dict):
        for u in users.values():
            if isinstance(u, dict) and str(u.get("referrer_uid", "")) == ref_uid:
                my_ids.add(str(u.get("telegram_id")))
    count = 0
    total = 0
    now = now_iso()
    if isinstance(purchases, dict):
        for pk, p in purchases.items():
            if not isinstance(p, dict): continue
            if str(p.get("user_telegram_id")) not in my_ids: continue
            if (p.get("referral_status") or "") != "pending_active": continue
            bonus = get_referral_bonus(p)
            fb_patch(f"purchases/{pk}", {
                "referral_status": "rejected",
                "referral_rejected_at": now,
                "referral_rejected_by": "admin_manual",
            })
            count += 1
            total += bonus
    return count, total

def calc_user_ref_balance(uid):
    uid = str(uid)
    users = fb_get("users") or {}
    purchases = fb_get("purchases") or {}
    my_ids = set()
    if isinstance(users, dict):
        for u in users.values():
            if isinstance(u, dict) and str(u.get("referrer_uid", "")) == uid:
                my_ids.add(str(u.get("telegram_id")))
    accrued = 0
    paid = 0
    pending = 0
    frozen = 0
    pending_active = 0
    last_at = None
    last_amount = 0
    if isinstance(purchases, dict):
        for p in purchases.values():
            if not isinstance(p, dict):
                continue
            if str(p.get("user_telegram_id")) not in my_ids:
                continue
            if p.get("status") in ("rejected", "cancelled"):
                continue
            b = get_referral_bonus(p)
            st = p.get("referral_status") or "pending"
            if st == "rejected":
                continue
            frozen_amt = 0
            try:
                frozen_amt = int(float(p.get("referral_frozen_amount") or 0))
            except:
                frozen_amt = 0
            if st == "paid":
                accrued += b
                paid += b
                if p.get("referral_paid_at"):
                    if not last_at or p.get("referral_paid_at") > last_at:
                        last_at = p.get("referral_paid_at")
                        try:
                            last_amount = int(float(p.get("referral_paid_amount") or b))
                        except:
                            last_amount = b
            elif st == "frozen":
                accrued += b
                frozen += frozen_amt or b
            elif st == "approved":
                accrued += b
            elif st == "pending_active":
                pending_active += b
            else:
                pending += b
    return {
        "accrued": accrued, "paid": paid, "pending": pending,
        "frozen": frozen, "pending_active": pending_active,
        "owed": max(0, accrued - paid - frozen),
        "last_at": last_at, "last_amount": last_amount,
    }

# ============================================================
# 💳 РЕКВИЗИТЫ
# ============================================================
def get_requisites(uid):
    u = fb_get(f"users/{uid}") or {}
    r = u.get("requisites") or {}
    return {
        "fio": r.get("fio") or "",
        "card": r.get("card") or "",
        "bank": r.get("bank") or "",
    }

def fmt_requisites(req):
    fio = req.get("fio") or "—"
    card = req.get("card") or "—"
    bank = req.get("bank") or "—"
    return (
        f"💳 <b>РЕКВИЗИТЫ:</b>\n"
        f"👤 Ф.И.О.: <b>{fio}</b>\n"
        f"💳 Карта/Тел: <code>{card}</code>\n"
        f"🏦 Банк: <b>{bank}</b>"
    )

# ============================================================
# КЛАВИАТУРЫ
# ============================================================
def kb_agree():
    return {"inline_keyboard": [[{"text": "✅ Я СОГЛАСЕН/А", "callback_data": AGREE_CALLBACK}]]}

def kb_start():
    return {"inline_keyboard": [
        [{"text": "🚀 Открыть приложение", "web_app": {"url": WEB_URL}}],
        [{"text": "📖 Как работает РОСТЭРА?", "callback_data": "info_how"}],
        [{"text": "📜 Правила проекта", "callback_data": "info_rules"}],
        [{"text": "💸 Подать заявку на вывод", "callback_data": "withdraw_start"}],
        [{"text": "👥 Мои рефералы", "callback_data": "my_refs"}],
    ]}

def kb_info():
    return {"inline_keyboard": [
        [{"text": "🔙 Назад", "callback_data": "back_to_start"}],
    ]}

# ---- Кнопки для админ-уведомлений: только "Открыть админку" ----
def kb_admin_purchase(pid, uid):
    return {"inline_keyboard": [
        [{"text": "🌐 Открыть админку", "web_app": {"url": ADMIN_URL}}]
    ]}

def kb_admin_payout(poid, uid):
    return {"inline_keyboard": [
        [{"text": "🌐 Открыть админку", "web_app": {"url": ADMIN_URL}}]
    ]}

def kb_admin_ref_payout(rid, uid):
    return {"inline_keyboard": [
        [{"text": "🌐 Открыть админку", "web_app": {"url": ADMIN_URL}}]
    ]}

def kb_admin_pending_bonus(ref_uid):
    return {"inline_keyboard": [
        [{"text": "🌐 Открыть админку", "web_app": {"url": ADMIN_URL}}]
    ]}

def kb_withdraw():
    return {"inline_keyboard": [[{"text": "💸 Подать заявку на вывод", "callback_data": "withdraw_start"}]]}

def kb_refs():
    return {"inline_keyboard": [
        [{"text": "🚀 Открыть приложение", "web_app": {"url": WEB_URL}}],
        [{"text": "🔄 Обновить", "callback_data": "my_refs"}]
    ]}

def kb_unknown():
    return {"inline_keyboard": [
        [{"text": "🚀 Открыть приложение", "web_app": {"url": WEB_URL}}],
        [{"text": "💬 Написать админу", "url": "https://t.me/DAMIR1500"}]
    ]}

# ============================================================
# PDF + СОГЛАСИЕ
# ============================================================
def send_pdf_and_button(chat_id):
    def _run():
        pdf_id = None
        if PDF_PATH.exists():
            try:
                with open(PDF_PATH, "rb") as f:
                    files = {"document": (PDF_FILENAME, f)}
                    data = {"chat_id": chat_id}
                    r = requests.post(f"{API}/sendDocument", data=data, files=files, timeout=60)
                    if r.ok:
                        pdf_id = r.json().get("result", {}).get("message_id")
            except Exception as e:
                log("PDF", f"❌ {e}")
        time.sleep(0.2)
        tg_send(chat_id, AGREE_TEXT, kb=kb_agree())
        AGREE_MESSAGES[str(chat_id)] = {"pdf": pdf_id}
    threading.Thread(target=_run, daemon=True).start()

# ============================================================
# РЕГИСТРАЦИЯ
# ============================================================
def register_user(user, start_text):
    uid = str(user["id"])
    existing = fb_get(f"users/{uid}") or {}
    if existing.get("registered_at"):
        return existing

    parts = start_text.split(maxsplit=1)
    ref_code = ""
    if len(parts) > 1 and parts[1].startswith("ref_"):
        ref_code = parts[1][4:].strip()

    data = {
        "telegram_id": user["id"],
        "username": user.get("username") or "",
        "first_name": user.get("first_name") or "",
        "last_name": user.get("last_name") or "",
        "registered_at": now_iso(),
    }

    if ref_code and str(ref_code) != uid:
        ref_user = fb_get(f"users/{ref_code}")
        if ref_user and ref_user.get("telegram_id"):
            data["referrer_uid"] = str(ref_code)
            new_name = user.get("first_name") or "Пользователь"
            new_un = f"@{user.get('username')}" if user.get("username") else ""
            tg_send(int(ref_code),
                    f"🎉 <b>Новый реферал!</b>\n\n"
                    f"👤 {new_name} {new_un}\n"
                    f"🆔 <code>{uid}</code>\n\n"
                    f"💰 <i>Вы получите {REFERRAL_PERCENT}% с каждой его покупки.</i>")
            log("REF", f"новый реферал у {ref_code}: {uid}")

    fb_put(f"users/{uid}", data)
    return data

# ============================================================
# КОМАНДЫ
# ============================================================
def cmd_start(chat_id, user, text):
    uid = str(user["id"])
    block_reason = is_blocked(uid)
    if block_reason:
        send_blocked_msg(chat_id, block_reason)
        return

    u = register_user(user, text)
    if u.get("agreed_terms"):
        tg_send(chat_id, WELCOME_AFTER, kb=kb_start())
        return
    send_pdf_and_button(chat_id)

def cmd_admin(chat_id):
    tg_send(chat_id,
            "🛠 <b>Админ-панель</b>\n\n"
            "Все действия — заявки, выплаты, статистика, товары, рефералы — "
            "доступны в веб-панели.\n\n"
            "<b>Доступные команды:</b>\n"
            "/test — самодиагностика\n"
            "/test_era — создать тестовую эру на 1 день\n"
            "/reset_era — удалить все тестовые эры",
            kb={"inline_keyboard": [[
                {"text": "🌐 Открыть админ-панель", "web_app": {"url": ADMIN_URL}}
            ]]})

def cmd_test(chat_id, user_tg):
    if not is_admin(user_tg):
        return
    me = tg("getMe")
    admins_str = ", ".join(f"<code>{a}</code>" for a in ADMIN_IDS)
    tg_send(chat_id,
            f"🧪 <b>Самодиагностика</b>\n\n"
            f"🤖 Бот: @{me['result']['username']}\n"
            f"👤 Ваш ID: <code>{user_tg}</code>\n"
            f"👑 Админы: {admins_str}\n"
            f"💰 Реф. процент: <b>{REFERRAL_PERCENT}%</b>\n\n"
            f"<i>Если это сообщение пришло — бот может вам писать.</i>")

def cmd_test_era(chat_id, user_tg):
    if not is_admin(user_tg):
        tg_send(chat_id, "⛔️ Только для админа"); return
    cur = fb_get("counters/purchase") or 0
    pid = int(cur) + 1
    fb_put("counters/purchase", pid)
    u = fb_get(f"users/{user_tg}") or {}
    now = now_iso()
    test_purchase = {
        "id": pid, "user_telegram_id": user_tg,
        "user_username": u.get("username", ""),
        "user_first_name": u.get("first_name", "Тест"),
        "era_title": "🧪 ТЕСТ ЭРА (1 день)",
        "purchase_price": 1000, "total_amount": 1500,
        "days": 1, "status": "created", "created_at": now, "is_test": 1,
        "referrer_uid": u.get("referrer_uid"),
        "referral_percent": REFERRAL_PERCENT, "referral_bonus": 50,
        "referral_status": "pending" if u.get("referrer_uid") else None,
    }
    fb_post("purchases", test_purchase)
    tg_send(chat_id, f"🧪 <b>Тестовая эра создана</b>\n\n📩 Заявка #{pid}\n💳 ТЕСТ ЭРА\n💰 1 500 ₽")
    notify_new_purchase(test_purchase, pid)

def cmd_reset_era(chat_id, user_tg):
    if not is_admin(user_tg):
        tg_send(chat_id, "⛔️ Только для админа"); return
    P = fb_get("purchases") or {}
    removed = 0
    if isinstance(P, dict):
        for k, p in P.items():
            if isinstance(p, dict) and p.get("is_test"):
                fb_put(f"purchases/{k}", None)
                PURCHASE_STATUS_CACHE.pop(k, None)
                removed += 1
    tg_send(chat_id, f"🧹 Удалено тестовых эр: <b>{removed}</b>")

def build_myrefs_text(uid):
    uid = str(uid)
    users = fb_get("users") or {}
    purchases = fb_get("purchases") or {}
    my_refs = []
    if isinstance(users, dict):
        for u in users.values():
            if isinstance(u, dict) and str(u.get("referrer_uid", "")) == uid:
                my_refs.append(u)
    my_refs.sort(key=lambda r: r.get("registered_at", ""), reverse=True)
    bal = calc_user_ref_balance(uid)
    if not my_refs:
        return ("👥 <b>Мои рефералы</b>\n\nПока никого нет.\n\n"
                f"<i>Приглашайте друзей — вы получаете {REFERRAL_PERCENT}% с каждой их покупки.</i>")
    lines = [
        f"👥 <b>Мои рефералы ({len(my_refs)})</b>", "", "━━━━━━━━━━━━━━━",
        "💰 <b>БАЛАНС</b>",
        f"💎 К выводу: <b>{fmt_money(bal['owed'])}</b>",
        f"📈 Начислено: {fmt_money(bal['accrued'])}",
        f"💸 Выплачено: {fmt_money(bal['paid'])}",
    ]
    if bal["pending"]:
        lines.append(f"⏳ Ожидает: {fmt_money(bal['pending'])}")
    if bal["pending_active"]:
        lines.append(f"⏸ Отложено: {fmt_money(bal['pending_active'])}")
        lines.append("   <i>(нужно купить эру — активируются)</i>")
    if bal["last_at"]:
        lines.append(f"\n<i>Последняя выплата: {fmt_money(bal['last_amount'])} · {fmt_dt(bal['last_at'])} (Ташкент)</i>")
    lines.append("━━━━━━━━━━━━━━━")
    lines.append("")
    my_ids = {str(r.get("telegram_id")) for r in my_refs}
    purchases_by_ref = {}
    if isinstance(purchases, dict):
        for p in purchases.values():
            if not isinstance(p, dict):
                continue
            buyer = str(p.get("user_telegram_id"))
            if buyer not in my_ids:
                continue
            if p.get("status") in ("rejected", "cancelled"):
                continue
            purchases_by_ref.setdefault(buyer, []).append(p)
    for r in my_refs[:15]:
        rid = str(r.get("telegram_id"))
        name = r.get("first_name") or "Пользователь"
        un = f"@{r.get('username')}" if r.get("username") else "—"
        rp = purchases_by_ref.get(rid, [])
        bsum = sum(get_referral_bonus(p) for p in rp)
        if rp:
            lines.append(f"👤 <b>{name}</b> ({un})\n   🛒 {len(rp)} покупок · 🎁 {fmt_money(bsum)}")
        else:
            lines.append(f"👤 <b>{name}</b> ({un})\n   <i>Пока без покупок</i>")
    if len(my_refs) > 15:
        lines.append(f"\n<i>…и ещё {len(my_refs) - 15}</i>")
    return "\n\n".join(lines)

def cmd_myrefs(chat_id, user_tg):
    block_reason = is_blocked(str(user_tg))
    if block_reason:
        send_blocked_msg(chat_id, block_reason)
        return
    text = build_myrefs_text(user_tg)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_tg}"
    text += f"\n\n🔗 <b>Ваша ссылка:</b>\n<code>{ref_link}</code>"
    tg_send(chat_id, text, kb=kb_refs())

# ============================================================
# CALLBACK HANDLER
# ============================================================
def handle_callback(cb):
    data = cb.get("data", "")
    user_tg = cb["from"]["id"]
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    msg_id = msg.get("message_id")
    cb_id = cb.get("id")
    log("CB", f"data={data} user={user_tg}")

    if not is_admin(user_tg):
        block_reason = is_blocked(str(user_tg))
        if block_reason:
            tg_answer(cb_id, "🚫 Вы заблокированы", True)
            if chat_id:
                send_blocked_msg(chat_id, block_reason)
            return

    if data == AGREE_CALLBACK:
        tg_answer(cb_id, "✅")
        uid = str(user_tg)
        stored = AGREE_MESSAGES.get(str(chat_id)) or {}
        if msg_id: tg_delete(chat_id, msg_id)
        if stored.get("pdf"): tg_delete(chat_id, stored["pdf"])
        AGREE_MESSAGES.pop(str(chat_id), None)
        u = fb_get(f"users/{uid}") or {}
        if u.get("telegram_id"):
            fb_patch(f"users/{uid}", {"agreed_terms": 1, "agreed_at": now_iso()})
        tg_send(chat_id, WELCOME_AFTER, kb=kb_start())
        return

    # ---- ИНФО-РАЗДЕЛЫ ----
    if data == "info_how":
        tg_answer(cb_id, "📖")
        if msg_id:
            tg_edit(chat_id, msg_id, HOW_IT_WORKS, kb=kb_info())
        else:
            tg_send(chat_id, HOW_IT_WORKS, kb=kb_info())
        return

    if data == "info_rules":
        tg_answer(cb_id, "📜")
        if msg_id:
            tg_edit(chat_id, msg_id, RULES_TEXT, kb=kb_info())
        else:
            tg_send(chat_id, RULES_TEXT, kb=kb_info())
        return

    if data == "back_to_start":
        tg_answer(cb_id, "🔙")
        if msg_id:
            tg_edit(chat_id, msg_id, WELCOME_AFTER, kb=kb_start())
        else:
            tg_send(chat_id, WELCOME_AFTER, kb=kb_start())
        return

    if data == "withdraw_start":
        ui_withdraw(chat_id, user_tg, cb_id, msg_id); return
    if data.startswith("wd_sel:"):
        ui_wd_sel(chat_id, user_tg, data[7:], msg_id, cb_id); return
    if data.startswith("wd_confirm:"):
        ui_wd_confirm(chat_id, user_tg, data[11:], msg_id, cb_id); return

    if data == "my_refs":
        tg_answer(cb_id, "👥")
        text = build_myrefs_text(user_tg)
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_tg}"
        text += f"\n\n🔗 <b>Ваша ссылка:</b>\n<code>{ref_link}</code>"
        if msg_id: tg_edit(chat_id, msg_id, text, kb=kb_refs())
        else: tg_send(chat_id, text, kb=kb_refs())
        return

    # ---- Callback-обработчики для старых сообщений (кнопки в истории) ----
    if data.startswith("adm_approve:"):
        if not is_admin(user_tg):
            tg_answer(cb_id, "⛔️", True); return
        pid = data.split(":", 1)[1]
        tg_answer(cb_id, "✅ Подтверждено")
        tg_edit(chat_id, msg_id, f"✅ <b>Заявка #{pid} подтверждена</b>\n<i>Админ: <code>{user_tg}</code></i>")
        admin_set_purchase(pid, "approved"); return

    if data.startswith("adm_reject:"):
        if not is_admin(user_tg):
            tg_answer(cb_id, "⛔️", True); return
        pid = data.split(":", 1)[1]
        tg_answer(cb_id, "❌ Отклонено")
        tg_edit(chat_id, msg_id, f"❌ <b>Заявка #{pid} отклонена</b>\n<i>Админ: <code>{user_tg}</code></i>")
        admin_set_purchase(pid, "rejected"); return

    if data.startswith("adm_paid:"):
        if not is_admin(user_tg):
            tg_answer(cb_id, "⛔️", True); return
        poid = data.split(":", 1)[1]
        tg_answer(cb_id, "💸")
        tg_edit(chat_id, msg_id, f"💸 <b>Вывод #{poid} выплачен</b>\n<i>Админ: <code>{user_tg}</code></i>")
        admin_set_payout(poid, "paid"); return

    if data.startswith("adm_preject:"):
        if not is_admin(user_tg):
            tg_answer(cb_id, "⛔️", True); return
        poid = data.split(":", 1)[1]
        tg_answer(cb_id, "❌")
        tg_edit(chat_id, msg_id, f"❌ <b>Вывод #{poid} отклонён</b>\n<i>Админ: <code>{user_tg}</code></i>")
        admin_set_payout(poid, "rejected"); return

    if data.startswith("adm_refpaid:"):
        if not is_admin(user_tg):
            tg_answer(cb_id, "⛔️", True); return
        rid = data.split(":", 1)[1]
        tg_answer(cb_id, "💸")
        tg_edit(chat_id, msg_id, f"💸 <b>Реф. заявка #{rid} выплачена</b>\n<i>Админ: <code>{user_tg}</code></i>")
        admin_set_ref_payout(rid, "paid"); return

    if data.startswith("adm_refreject:"):
        if not is_admin(user_tg):
            tg_answer(cb_id, "⛔️", True); return
        rid = data.split(":", 1)[1]
        tg_answer(cb_id, "❌")
        tg_edit(chat_id, msg_id, f"❌ <b>Реф. заявка #{rid} отклонена</b>\n<i>Админ: <code>{user_tg}</code></i>")
        admin_set_ref_payout(rid, "rejected"); return

    if data.startswith("adm_actbonus:"):
        if not is_admin(user_tg):
            tg_answer(cb_id, "⛔️", True); return
        ref_uid = data.split(":", 1)[1]
        tg_answer(cb_id, "⏳ Активирую…")
        count, total = force_activate_pending_bonuses(ref_uid)
        tg_edit(chat_id, msg_id,
                f"✅ <b>Активировано {count} бонусов</b>\n"
                f"💰 На сумму: <b>{fmt_money(total)}</b>\n"
                f"👤 Реферер: <code>{ref_uid}</code>")
        bal = calc_user_ref_balance(ref_uid)
        tg_send(int(ref_uid),
                f"🎉 <b>Бонусы активированы!</b>\n\n"
                f"💰 Начислено: <b>+{fmt_money(total)}</b>\n"
                f"📦 От {count} покупк{'и' if count == 1 else 'ок'}\n\n"
                f"💎 К выводу: <b>{fmt_money(bal['owed'])}</b>",
                kb=kb_refs())
        return

    if data.startswith("adm_rejbonus:"):
        if not is_admin(user_tg):
            tg_answer(cb_id, "⛔️", True); return
        ref_uid = data.split(":", 1)[1]
        tg_answer(cb_id, "❌ Отклонено")
        count, total = reject_pending_bonuses(ref_uid)
        tg_edit(chat_id, msg_id,
                f"❌ <b>Отклонено {count} бонусов</b>\n"
                f"💰 На сумму: <b>{fmt_money(total)}</b>")
        tg_send(int(ref_uid),
                f"❌ <b>Отложенные бонусы отклонены</b>\n\n"
                f"💰 {fmt_money(total)} не будут начислены.\n\n"
                f"Если это ошибка — свяжитесь с админом.")
        return

    tg_answer(cb_id, "")

# ============================================================
# UI ВЫВОДА
# ============================================================
def ui_withdraw(chat_id, user_tg, cb_id=None, msg_id=None):
    all_p = fb_get("purchases") or {}
    all_po = fb_get("payouts") or {}
    blocked = set()
    if isinstance(all_po, dict):
        for po in all_po.values():
            if isinstance(po, dict) and po.get("status") in ("pending", "paid", "processing"):
                blocked.add(str(po.get("purchase_id")))
    available = []
    if isinstance(all_p, dict):
        for k, p in all_p.items():
            if not isinstance(p, dict):
                continue
            if str(p.get("user_telegram_id")) != str(user_tg):
                continue
            if p.get("status") != "completed":
                continue
            if str(p.get("id")) in blocked:
                continue
            available.append((k, p))
    if cb_id:
        tg_answer(cb_id)
    if not available:
        text = "📭 Нет эр для вывода"
        kb = {"inline_keyboard": [[{"text": "🚀 Приложение", "web_app": {"url": WEB_URL}}]]}
        if msg_id: tg_edit(chat_id, msg_id, text, kb=kb)
        else: tg_send(chat_id, text, kb=kb)
        return
    buttons = [[{"text": f"📄 #{p.get('id')} · {fmt_money(p.get('total_amount', 0))}",
                 "callback_data": f"wd_sel:{k}"}] for k, p in available]
    if msg_id: tg_edit(chat_id, msg_id, "📋 <b>Выберите покупку:</b>", kb={"inline_keyboard": buttons})
    else: tg_send(chat_id, "📋 <b>Выберите покупку:</b>", kb={"inline_keyboard": buttons})

def ui_wd_sel(chat_id, user_tg, key, msg_id, cb_id):
    tg_answer(cb_id)
    p = fb_get(f"purchases/{key}")
    if not p:
        tg_send(chat_id, "❌ Не найдено"); return
    req = get_requisites(user_tg)
    has_req = bool(req["fio"] and req["card"] and req["bank"])
    text = (f"📄 <b>#{p.get('id')}</b>\n"
            f"💳 {p.get('era_title', '—')}\n"
            f"💰 {fmt_money(p.get('total_amount', 0))}\n\n")
    if has_req:
        text += fmt_requisites(req)
    else:
        text += "⚠️ <b>Реквизиты не заполнены</b>\nЗаполните их в приложении → Профиль → Реквизиты."
    kb = {"inline_keyboard": [[{"text": "🔘 Подать заявку", "callback_data": f"wd_confirm:{key}"}]]}
    tg_edit(chat_id, msg_id, text, kb=kb)

def ui_wd_confirm(chat_id, user_tg, key, msg_id, cb_id):
    tg_answer(cb_id, "✅ Создаю…")
    p = fb_get(f"purchases/{key}")
    if not p:
        tg_send(chat_id, "❌ Не найдено"); return

    req = get_requisites(user_tg)
    if not (req["fio"] and req["card"] and req["bank"]):
        tg_edit(chat_id, msg_id,
                "⚠️ <b>Реквизиты не заполнены</b>\n\n"
                "Откройте приложение → Профиль → Реквизиты и заполните:\n"
                "👤 Ф.И.О.\n💳 Карта/телефон\n🏦 Банк",
                kb={"inline_keyboard": [[
                    {"text": "🚀 Открыть приложение", "web_app": {"url": WEB_URL}}
                ]]})
        return

    cur = fb_get("counters/payout") or 0
    poid = int(cur) + 1
    fb_put("counters/payout", poid)
    u = fb_get(f"users/{user_tg}") or {}
    now = now_iso()
    po = {
        "id": poid, "purchase_id": p.get("id"),
        "user_telegram_id": user_tg,
        "user_username": u.get("username", ""),
        "user_first_name": u.get("first_name", ""),
        "era_title": p.get("era_title", ""),
        "purchase_price": p.get("purchase_price", 0),
        "amount": p.get("total_amount", 0),
        "status": "pending", "requested_at": now, "paid_at": None,
        "requisites": req,
    }
    fb_post("payouts", po)
    tg_edit(chat_id, msg_id,
            f"✅ <b>Заявка #{poid} создана</b>\n💰 {fmt_money(po['amount'])}\n\n"
            f"{fmt_requisites(req)}\n\n"
            f"⏳ Ожидайте — администратор свяжется с вами.")
    PAYOUT_STATUS_CACHE[str(poid)] = "pending"
    notify_new_payout(po)

# ============================================================
# СООБЩЕНИЯ
# ============================================================
def handle_message(msg):
    text = (msg.get("text") or "").strip()
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    user = msg.get("from", {})
    user_tg = user.get("id")
    if chat.get("type") != "private":
        return
    log("MSG", f"{user_tg}: {text[:60] if text else '[no text]'}")

    if not is_admin(user_tg):
        block_reason = is_blocked(str(user_tg))
        if block_reason:
            send_blocked_msg(chat_id, block_reason)
            return

    if text.startswith("/start"):
        cmd_start(chat_id, user, text); return
    if text.startswith("/admin"):
        if not is_admin(user_tg):
            tg_send(chat_id, "⛔️ Доступ запрещён"); return
        cmd_admin(chat_id); return
    if text.startswith("/myrefs") or text.startswith("/refs"):
        cmd_myrefs(chat_id, user_tg); return
    if text.startswith("/test_era"):
        cmd_test_era(chat_id, user_tg); return
    if text.startswith("/reset_era"):
        cmd_reset_era(chat_id, user_tg); return
    if text.startswith("/test"):
        cmd_test(chat_id, user_tg); return

    tg_send(chat_id,
            "🤔 <b>Такой команды нет</b>\n\n"
            "Доступные действия:\n"
            "• 🚀 Открыть приложение\n"
            "• 💬 Связаться с админом",
            kb=kb_unknown())

# ============================================================
# ПОЛЛИНГ
# ============================================================
def poll():
    try:
        r = requests.post(f"{API}/getUpdates",
                          json={"offset": offset["v"], "timeout": 10},
                          timeout=25)
        data = r.json()
        if not data.get("ok"):
            return
        for upd in data.get("result", []):
            offset["v"] = upd["update_id"] + 1
            try:
                if "message" in upd:
                    handle_message(upd["message"])
                elif "callback_query" in upd:
                    handle_callback(upd["callback_query"])
            except Exception as e:
                log("UPD", f"ошибка: {e}")
    except requests.exceptions.ReadTimeout:
        pass
    except requests.exceptions.ConnectionError as e:
        log("POLL", f"сеть: {e}")
        time.sleep(2)
    except Exception as e:
        log("POLL", f"{e}")
        time.sleep(1)

# ============================================================
# АДМИН-ДЕЙСТВИЯ
# ============================================================
def admin_set_purchase(pid, status):
    log("ADM", f"purchase #{pid} → {status}")
    k, p = find_record("purchases", pid)
    if not p:
        notify_admins(f"⚠️ Заявка #{pid} не найдена в Firebase.")
        return
    old_status = p.get("status", "")
    patch = {"status": status, "status_changed_at": now_iso()}
    buyer_uid = str(p.get("user_telegram_id"))
    activated_count = 0
    activated_total = 0

    if status == "approved":
        try:
            days = int(p.get("days") or DEFAULT_DAYS)
        except:
            days = DEFAULT_DAYS
        patch.update(calc_dates(now_iso(), days))
        patch["approved_at"] = now_iso()
        patch["days"] = days

        if p.get("referrer_uid"):
            ref_uid = str(p["referrer_uid"])
            bonus = get_referral_bonus(p)
            if ref_has_active_era(ref_uid):
                patch["referral_status"] = "approved"
                patch["referral_activated_at"] = now_iso()
                if p.get("referral_bonus") in (None, ""):
                    patch["referral_bonus"] = bonus
            else:
                patch["referral_status"] = "pending_active"
                patch["referral_pending_reason"] = "У реферера нет активной эры"
                if p.get("referral_bonus") in (None, ""):
                    patch["referral_bonus"] = bonus

        activated_count, activated_total = activate_pending_bonuses(buyer_uid)

    if status in ("rejected", "cancelled"):
        if p.get("referrer_uid"):
            patch["referral_status"] = "rejected"

    fb_patch(f"purchases/{k}", patch)
    PURCHASE_STATUS_CACHE[k] = status

    if old_status != status:
        updated = {**p, **patch}
        notify_purchase_status(k, updated, old_status, status)

        if status == "approved" and patch.get("referral_status") == "pending_active":
            ref_uid = str(p["referrer_uid"])
            ref_user = fb_get(f"users/{ref_uid}") or {}
            bonus = get_referral_bonus(p)
            ref_bal = calc_user_ref_balance(ref_uid)
            notify_admins(
                f"⏸ <b>Бонус отложен — нужна проверка</b>\n\n"
                f"🎁 Реферер: <b>{ref_user.get('first_name', '—')}</b> "
                f"{'@' + ref_user.get('username') if ref_user.get('username') else ''}\n"
                f"🆔 <code>{ref_uid}</code>\n\n"
                f"👤 Купил: {p.get('user_first_name', '—')}\n"
                f"💳 {p.get('era_title', '—')}\n"
                f"💰 Бонус: <b>{fmt_money(bonus)}</b>\n\n"
                f"❌ Причина: у реферера нет активной эры\n\n"
                f"📊 Всего отложено у реферера: "
                f"<b>{fmt_money(ref_bal['pending_active'])}</b>\n\n"
                f"👇 Откройте админку для управления:",
                kb=kb_admin_pending_bonus(ref_uid)
            )

        if activated_count > 0:
            bal = calc_user_ref_balance(buyer_uid)
            tg_send(int(buyer_uid),
                    f"🎉 <b>Отложенные бонусы активированы!</b>\n\n"
                    f"💰 Зачислено: <b>+{fmt_money(activated_total)}</b>\n"
                    f"📦 От {activated_count} покупк{'и' if activated_count == 1 else 'ок'} рефералов\n\n"
                    f"💎 К выводу: <b>{fmt_money(bal['owed'])}</b>",
                    kb=kb_refs())

def admin_set_payout(poid, status):
    log("ADM", f"payout #{poid} → {status}")
    k, po = find_record("payouts", poid)
    if not po:
        notify_admins(f"⚠️ Вывод #{poid} не найден.")
        return
    old_status = po.get("status", "")
    patch = {"status": status, "status_changed_at": now_iso()}
    if status == "paid":
        patch["paid_at"] = now_iso()
    fb_patch(f"payouts/{k}", patch)
    PAYOUT_STATUS_CACHE[k] = status
    if old_status != status:
        notify_payout_status(k, {**po, **patch}, old_status, status)

def admin_set_ref_payout(rid, status):
    log("ADM", f"ref_payout #{rid} → {status}")
    k, r = find_record("ref_payout_requests", rid)
    if not r:
        notify_admins(f"⚠️ Реф. заявка #{rid} не найдена.")
        return
    uid = str(r.get("user_telegram_id"))
    amount = int(float(r.get("amount", 0)))
    now = now_iso()
    if status == "paid":
        users = fb_get("users") or {}
        purchases = fb_get("purchases") or {}
        my_ids = set()
        if isinstance(users, dict):
            for u in users.values():
                if isinstance(u, dict) and str(u.get("referrer_uid", "")) == uid:
                    my_ids.add(str(u.get("telegram_id")))
        if isinstance(purchases, dict):
            for pk, p in purchases.items():
                if not isinstance(p, dict):
                    continue
                if str(p.get("user_telegram_id")) not in my_ids:
                    continue
                if (p.get("referral_status") or "") != "frozen":
                    continue
                if str(p.get("referral_request_id") or "") != str(r.get("id")):
                    continue
                fz = 0
                try:
                    fz = int(float(p.get("referral_frozen_amount") or 0))
                except:
                    fz = 0
                if fz <= 0:
                    fz = get_referral_bonus(p)
                fb_patch(f"purchases/{pk}", {
                    "referral_status": "paid",
                    "referral_paid_at": now,
                    "referral_paid_amount": fz,
                    "referral_frozen_amount": 0,
                    "referral_frozen_at": None,
                    "referral_request_id": None,
                })
        fb_post("ref_payouts_log", {
            "user_telegram_id": uid, "amount": amount,
            "request_id": r.get("id"), "paid_at": now, "paid_by": ADMIN_ID,
        })
    elif status == "rejected":
        purchases = fb_get("purchases") or {}
        if isinstance(purchases, dict):
            for pk, p in purchases.items():
                if not isinstance(p, dict):
                    continue
                if (p.get("referral_status") or "") != "frozen":
                    continue
                if str(p.get("referral_request_id") or "") != str(r.get("id")):
                    continue
                fb_patch(f"purchases/{pk}", {
                    "referral_status": "approved",
                    "referral_frozen_amount": 0,
                    "referral_frozen_at": None,
                    "referral_request_id": None,
                })
    fb_patch(f"ref_payout_requests/{k}", {
        "status": status, "status_changed_at": now,
    })
    if status == "paid":
        bal = calc_user_ref_balance(uid)
        remain_text = (f"🎁 Осталось к выводу: <b>{fmt_money(bal['owed'])}</b>"
                       if bal["owed"] > 0 else "✅ <b>Все бонусы выплачены!</b>")
        tg_send(int(uid),
                f"💸 <b>Вам выплачен реферальный бонус!</b>\n\n"
                f"💰 Сумма: <b>{fmt_money(amount)}</b>\n"
                f"🕐 {fmt_dt(now)} (Ташкент)\n\n{remain_text}",
                kb=kb_refs())
    elif status == "rejected":
        bal = calc_user_ref_balance(uid)
        tg_send(int(uid),
                f"❌ <b>Заявка на вывод бонуса отклонена</b>\n\n"
                f"💰 {fmt_money(amount)}\n\n"
                f"💎 Вернулось к выводу: <b>{fmt_money(bal['owed'])}</b>\n\n"
                f"Если это ошибка — напишите администратору.",
                kb=kb_refs())
    notify_admins(
        f"🔄 <b>Реф. заявка #{r.get('id')}</b>: {status}\n"
        f"👤 {r.get('user_first_name', '—')}\n"
        f"💰 {fmt_money(amount)}")

# ============================================================
# УВЕДОМЛЕНИЯ
# ============================================================
def notify_new_purchase(p, pid):
    uid = p.get("user_telegram_id")
    log("NOTIFY", f"новая заявка #{pid} от uid={uid}")
    tg_send(uid,
            f"📩 <b>Заявка #{pid} создана</b>\n\n"
            f"💳 {p.get('era_title', '—')}\n"
            f"💵 {fmt_money(p.get('purchase_price', 0))}\n"
            f"🏆 {fmt_money(p.get('total_amount', 0))}\n\n"
            f"⏳ Ожидайте подтверждения.")
    notify_admins(
        f"📩 <b>НОВАЯ ЗАЯВКА #{pid}</b>\n\n"
        f"👤 {p.get('user_first_name', '—')} @{p.get('user_username') or '—'}\n"
        f"🆔 <code>{uid}</code>\n"
        f"💳 {p.get('era_title', '—')}\n"
        f"💵 {fmt_money(p.get('purchase_price', 0))} → <b>{fmt_money(p.get('total_amount', 0))}</b>\n\n"
        f"👇 Откройте админку для обработки:",
        kb=kb_admin_purchase(pid, uid))
    buyer = fb_get(f"users/{uid}") or {}
    ref_uid = buyer.get("referrer_uid") or p.get("referrer_uid")
    if ref_uid:
        bonus = get_referral_bonus(p)
        tg_send(int(ref_uid),
                f"💰 <b>Ваш реферал сделал покупку!</b>\n\n"
                f"👤 {p.get('user_first_name', '—')}\n"
                f"💳 {p.get('era_title', '—')}\n"
                f"💵 Номинал: {fmt_money(p.get('purchase_price', 0))}\n\n"
                f"🎁 <b>Ваш бонус ({REFERRAL_PERCENT}%): {fmt_money(bonus)}</b>\n"
                f"⏳ Ожидает подтверждения админом.",
                kb=kb_refs())

def notify_new_payout(po):
    uid = po.get("user_telegram_id")
    poid = po.get("id")
    amount = fmt_money(po.get("amount", 0))

    req = po.get("requisites") or {}
    if not req or not req.get("fio"):
        req = get_requisites(uid)

    # Уведомление пользователю — БЕЗ кнопок
    tg_send(uid,
            f"📤 <b>Заявка на вывод #{poid} создана</b>\n\n"
            f"💰 {amount}\n\n⏳ Ожидайте — админ скоро обработает.")

    # Уведомление админам — только кнопка "Открыть админку"
    notify_admins(
        f"📤 <b>НОВАЯ ЗАЯВКА НА ВЫВОД #{poid}</b>\n\n"
        f"👤 {po.get('user_first_name', '—')} @{po.get('user_username') or '—'}\n"
        f"🆔 <code>{uid}</code>\n"
        f"💰 <b>{amount}</b>\n\n"
        f"{fmt_requisites(req)}\n\n"
        f"👇 Откройте админку для обработки:",
        kb=kb_admin_payout(poid, uid))

def notify_new_ref_request(r):
    rid = r.get("id")
    uid = r.get("user_telegram_id")
    amount = fmt_money(r.get("amount", 0))

    req = r.get("requisites") or {}
    if not req or not req.get("fio"):
        req = get_requisites(uid)

    # Уведомление пользователю — БЕЗ кнопок
    tg_send(int(uid),
            f"✅ <b>Заявка на вывод бонуса #{rid}</b>\n\n"
            f"💰 Сумма: <b>{amount}</b>\n\n⏳ Ожидайте подтверждения админом.")

    # Уведомление админам — только кнопка "Открыть админку"
    notify_admins(
        f"💰 <b>НОВАЯ ЗАЯВКА НА ВЫВОД БОНУСА #{rid}</b>\n\n"
        f"👤 {r.get('user_first_name', '—')} @{r.get('user_username') or '—'}\n"
        f"🆔 <code>{uid}</code>\n"
        f"💰 Сумма: <b>{amount}</b>\n\n"
        f"{fmt_requisites(req)}\n\n👇 Откройте админку для обработки:",
        kb=kb_admin_ref_payout(rid, uid))

def notify_purchase_status(k, p, old_status, new_status):
    uid = p.get("user_telegram_id")
    pid = p.get("id")
    era = p.get("era_title", "—")
    price = fmt_money(p.get("purchase_price", 0))
    total = fmt_money(p.get("total_amount", 0))
    log("NOTIFY", f"purchase #{pid} {old_status}→{new_status}")

    if new_status == "approved":
        start = fmt_date(p.get("start_date"))
        last = fmt_date(p.get("last_day"))
        exp = fmt_date(p.get("expires_at"))
        days = p.get("days", DEFAULT_DAYS)
        tg_send(uid,
                f"✅ <b>Заявка #{pid} подтверждена!</b>\n\n"
                f"💳 Эра: <b>{era}</b>\n"
                f"💵 Номинал: {price}\n"
                f"🏆 К выплате: <b>{total}</b>\n\n"
                f"🟢 <b>Эра активна:</b>\n"
                f"▶️ С {start}\n⏹ По {last}\n⏰ Истекает: {exp}\n"
                f"📅 Длительность: <b>{days} дн.</b>")
        buyer = fb_get(f"users/{uid}") or {}
        ref_uid = buyer.get("referrer_uid") or p.get("referrer_uid")
        if ref_uid:
            bonus = get_referral_bonus(p)
            ref_status = p.get("referral_status") or "approved"
            if ref_status == "approved":
                bal = calc_user_ref_balance(ref_uid)
                tg_send(int(ref_uid),
                        f"✅ <b>Бонус активирован!</b>\n\n"
                        f"👤 {p.get('user_first_name', '—')}\n"
                        f"💳 {era}\n"
                        f"🎁 <b>+{fmt_money(bonus)}</b>\n\n"
                        f"💰 К выводу: <b>{fmt_money(bal['owed'])}</b>",
                        kb=kb_refs())
            elif ref_status == "pending_active":
                bal = calc_user_ref_balance(ref_uid)
                tg_send(int(ref_uid),
                        f"⏸ <b>Бонус отложен</b>\n\n"
                        f"👤 Ваш реферал {p.get('user_first_name', '—')} купил эру.\n"
                        f"🎁 Бонус: {fmt_money(bonus)}\n\n"
                        f"❌ <b>Причина:</b> у вас нет активной эры.\n\n"
                        f"🎯 <i>Купите любую эру — и отложенные бонусы "
                        f"(<b>{fmt_money(bal['pending_active'])}</b>) активируются автоматически.</i>",
                        kb=kb_refs())
    elif new_status in ("rejected", "cancelled"):
        emoji = "❌" if new_status == "rejected" else "🚫"
        tg_send(uid,
                f"{emoji} <b>Заявка #{pid} отклонена</b>\n\n"
                f"💳 {era}\n💵 {price}")
        buyer = fb_get(f"users/{uid}") or {}
        ref_uid = buyer.get("referrer_uid") or p.get("referrer_uid")
        if ref_uid:
            tg_send(int(ref_uid),
                    f"⚠️ <b>Заявка вашего реферала отклонена</b>\n\n"
                    f"👤 {p.get('user_first_name', '—')}\n"
                    f"💳 {era}\n\n<i>Бонус не начислен.</i>")
    elif new_status == "completed":
        start = fmt_date(p.get("start_date"))
        last = fmt_date(p.get("last_day"))
        if p.get("early_closed"):
            notify_purchase_early_closed(k, p, p.get("early_closed_by", ADMIN_ID))
            return
        tg_send(uid,
                f"🏁 <b>Период по заявке #{pid} завершён!</b>\n\n"
                f"💳 Эра: <b>{era}</b>\n"
                f"🟢 Была активна: с {start} по {last}\n"
                f"🏆 К выплате: <b>{total}</b>\n\n"
                f"Подайте заявку на вывод 👇",
                kb=kb_withdraw())

def notify_purchase_early_closed(k, p, closed_by):
    uid = p.get("user_telegram_id")
    pid = p.get("id")
    era = p.get("era_title", "—")
    total = fmt_money(p.get("total_amount", 0))
    price = fmt_money(p.get("purchase_price", 0))
    profit = fmt_money(p.get("profit_amount", 0))
    tg_send(uid,
            f"🔌 <b>Эра отключена</b>\n\n"
            f"📩 Заявка #{pid}\n"
            f"💳 Эра: <b>{era}</b>\n\n"
            f"💰 <b>Досрочное начисление:</b>\n"
            f"💵 Вложено: {price}\n"
            f"📈 Начислено: +{profit}\n"
            f"🏆 <b>К выводу: {total}</b>\n\n"
            f"✅ Сумма доступна к выводу.\n"
            f"<i>Обратитесь к администратору или подайте заявку в приложении.</i>",
            kb=kb_withdraw())
    notify_admins(
        f"🔌 <b>Эра отключена досрочно</b>\n\n"
        f"👤 {p.get('user_first_name', '—')} @{p.get('user_username') or '—'}\n"
        f"🆔 <code>{uid}</code>\n"
        f"💳 {era}\n"
        f"💰 Начислено: <b>{total}</b>\n"
        f"👑 Админ: <code>{closed_by}</code>")

def notify_payout_status(k, po, old_status, new_status):
    uid = po.get("user_telegram_id")
    poid = po.get("id")
    amount = fmt_money(po.get("amount", 0))
    if new_status == "paid":
        tg_send(uid,
                f"💸 <b>Выплата #{poid} произведена!</b>\n\n"
                f"💰 Сумма: <b>{amount}</b>\n"
                f"🕐 {fmt_dt(po.get('paid_at'))} (Ташкент)")
    elif new_status in ("rejected", "cancelled"):
        tg_send(uid,
                f"❌ <b>Заявка на вывод #{poid} отклонена</b>\n\n💰 {amount}")
    notify_admins(
        f"🔄 <b>Вывод #{poid}</b>: {old_status} → <b>{new_status}</b>\n"
        f"👤 {po.get('user_first_name', '—')}\n"
        f"💰 {amount}")

# ============================================================
# ФОНОВЫЙ МОНИТОРИНГ
# ============================================================
def check_new():
    global last_seen_purchase_id, last_seen_payout_id, last_seen_ref_request_id
    P = fb_get("purchases") or {}
    if isinstance(P, dict):
        for k, p in P.items():
            if not isinstance(p, dict):
                continue
            try:
                pid = int(p.get("id", 0))
            except:
                continue
            cur_status = p.get("status", "")
            old_status = PURCHASE_STATUS_CACHE.get(k)
            if pid > last_seen_purchase_id:
                last_seen_purchase_id = pid
                if cur_status == "created":
                    notify_new_purchase(p, pid)
            elif old_status and old_status != cur_status:
                if cur_status == "completed" and p.get("early_closed"):
                    notify_purchase_early_closed(k, p, p.get("early_closed_by", ADMIN_ID))
                    PURCHASE_STATUS_CACHE[k] = cur_status
                    continue
                notify_purchase_status(k, p, old_status, cur_status)
            PURCHASE_STATUS_CACHE[k] = cur_status
    PO = fb_get("payouts") or {}
    if isinstance(PO, dict):
        for k, po in PO.items():
            if not isinstance(po, dict):
                continue
            try:
                poid = int(po.get("id", 0))
            except:
                continue
            cur_status = po.get("status", "")
            old_status = PAYOUT_STATUS_CACHE.get(k)
            if poid > last_seen_payout_id:
                last_seen_payout_id = poid
                if cur_status == "pending":
                    notify_new_payout(po)
            elif old_status and old_status != cur_status:
                notify_payout_status(k, po, old_status, cur_status)
            PAYOUT_STATUS_CACHE[k] = cur_status
    RQ = fb_get("ref_payout_requests") or {}
    if isinstance(RQ, dict):
        for k, r in RQ.items():
            if not isinstance(r, dict):
                continue
            try:
                rid = int(r.get("id", 0))
            except:
                continue
            cur_status = r.get("status", "")
            old_status = REF_REQUEST_STATUS_CACHE.get(k)
            if rid > last_seen_ref_request_id:
                last_seen_ref_request_id = rid
                if cur_status == "pending":
                    notify_new_ref_request(r)
            REF_REQUEST_STATUS_CACHE[k] = cur_status

# ============================================================
# НАПОМИНАНИЯ
# ============================================================
def check_expired():
    P = fb_get("purchases") or {}
    if not isinstance(P, dict):
        return
    now = datetime.now(TZ)
    for k, p in P.items():
        if not isinstance(p, dict):
            continue
        if p.get("status") != "approved":
            continue
        exp = parse_dt(p.get("expires_at"))
        if not exp:
            continue
        hours = (exp - now).total_seconds() / 3600
        uid = p.get("user_telegram_id")
        pid = p.get("id")
        era = p.get("era_title", "—")
        total = fmt_money(p.get("total_amount", 0))
        last_d = fmt_date(p.get("last_day"))
        exp_d = fmt_dt(p.get("expires_at"))

        if 48 < hours <= 72 and not p.get("notified_3d"):
            tg_send(uid,
                    f"⏰ <b>Осталось 3 дня до окончания эры «{era}»</b>\n\n"
                    f"📩 Заявка #{pid}\n"
                    f"⏰ Истекает: {exp_d}\n"
                    f"🏆 К выплате: <b>{total}</b>")
            fb_patch(f"purchases/{k}", {"notified_3d": 1})
        elif 3 < hours <= 24 and not p.get("notified_1d"):
            tg_send(uid,
                    f"⏰ <b>Остался 1 день до окончания эры «{era}»</b>\n\n"
                    f"📩 Заявка #{pid}\n"
                    f"🏁 Последний день: {last_d}\n"
                    f"⏰ Истекает: {exp_d}\n"
                    f"🏆 К выплате: <b>{total}</b>")
            fb_patch(f"purchases/{k}", {"notified_1d": 1})
        elif 0 < hours <= 3 and not p.get("notified_3h"):
            tg_send(uid,
                    f"⏰ <b>Осталось 3 часа до окончания эры «{era}»</b>\n\n"
                    f"📩 Заявка #{pid}\n"
                    f"⏰ Истекает: {exp_d}\n"
                    f"🏆 К выплате: <b>{total}</b>")
            fb_patch(f"purchases/{k}", {"notified_3h": 1})
        if now >= exp and not p.get("completed_notified"):
            fb_patch(f"purchases/{k}", {
                "status": "completed",
                "completed_at": now.isoformat(),
                "status_changed_at": now.isoformat(),
                "completed_notified": 1,
            })
            old_status = p.get("status", "approved")
            notify_purchase_status(k, {**p, "status": "completed"}, old_status, "completed")
            PURCHASE_STATUS_CACHE[k] = "completed"

# ============================================================
# MAIN
# ============================================================
def main():
    global last_seen_purchase_id, last_seen_payout_id, last_seen_ref_request_id, BOT_USERNAME
    print("=" * 60)
    print("🤖 Бот @ROSTERAbot")
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"💰 Реф. процент: {REFERRAL_PERCENT}%")
    print("=" * 60)

    me = tg("getMe")
    if not me or not me.get("ok"):
        print("❌ Токен невалидный."); return
    info = me.get("result", {})
    BOT_USERNAME = info.get("username", "ROSTERAbot")
    print(f"✅ @{BOT_USERNAME}")

    tg("deleteWebhook", drop_pending_updates=True)
    print("✅ Webhook удалён")

    P = fb_get("purchases") or {}
    max_pid = 0
    if isinstance(P, dict):
        for k, v in P.items():
            if isinstance(v, dict):
                try:
                    max_pid = max(max_pid, int(v.get("id", 0)))
                except:
                    pass
                PURCHASE_STATUS_CACHE[k] = v.get("status", "")
    last_seen_purchase_id = max_pid

    PO = fb_get("payouts") or {}
    max_poid = 0
    if isinstance(PO, dict):
        for k, v in PO.items():
            if isinstance(v, dict):
                try:
                    max_poid = max(max_poid, int(v.get("id", 0)))
                except:
                    pass
                PAYOUT_STATUS_CACHE[k] = v.get("status", "")
    last_seen_payout_id = max_poid

    RQ = fb_get("ref_payout_requests") or {}
    max_rid = 0
    if isinstance(RQ, dict):
        for k, v in RQ.items():
            if isinstance(v, dict):
                try:
                    max_rid = max(max_rid, int(v.get("id", 0)))
                except:
                    pass
                REF_REQUEST_STATUS_CACHE[k] = v.get("status", "")
    last_seen_ref_request_id = max_rid

    print(f"✅ Кэш: purchases={len(PURCHASE_STATUS_CACHE)}, "
          f"payouts={len(PAYOUT_STATUS_CACHE)}, "
          f"ref_requests={len(REF_REQUEST_STATUS_CACHE)}")
    print("▶️ Готов.\n")

    last_new = 0
    last_exp = 0
    while True:
        try:
            poll()
            now = time.time()
            if now - last_new > 2:
                check_new()
                last_new = now
            if now - last_exp > 30:
                check_expired()
                last_exp = now
        except Exception as e:
            log("MAIN", f"{e}")
        time.sleep(0.1)

if __name__ == "__main__":
    main()
