"""قاعدة بيانات LOYALTY (SQLite). هي مصدر الحقيقة للأختام، وGoogle Wallet للعرض بس."""
import hashlib
import hmac
import os
import re
import sqlite3
import time
from contextlib import contextmanager

DB_PATH = "loyalty.db"
MIN_SECONDS_BETWEEN_STAMPS = 120   # حد أدنى بين ختمين لنفس العميل (منع التلاعب)
CONSENT_VERSION = "v1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS cafes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  logo_url TEXT NOT NULL,
  color TEXT NOT NULL DEFAULT '#3b2a20',
  stamps_required INTEGER NOT NULL DEFAULT 8,
  reward_text TEXT NOT NULL DEFAULT 'مشروب مجاني',
  cashier_pin_hash TEXT,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS customers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cafe_id INTEGER NOT NULL REFERENCES cafes(id),
  phone TEXT NOT NULL,
  name TEXT NOT NULL,
  stamps INTEGER NOT NULL DEFAULT 0,
  consent_at INTEGER NOT NULL,
  consent_version TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  UNIQUE (cafe_id, phone)
);
CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cafe_id INTEGER NOT NULL,
  customer_id INTEGER NOT NULL,
  kind TEXT NOT NULL,          -- stamp | redeem
  delta INTEGER NOT NULL,
  idem_key TEXT UNIQUE,        -- يمنع تكرار نفس العملية لو اتبعتت مرتين
  created_at INTEGER NOT NULL
);
"""


class LoyaltyError(Exception):
    """خطأ مفهوم نعرضه للمستخدم (رسالة بالعربي)."""


@contextmanager
def connect():
    con = sqlite3.connect(DB_PATH, isolation_level=None)  # نتحكم في الـ transactions بنفسنا
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def init_db():
    with connect() as con:
        con.executescript(SCHEMA)
        cols = [r["name"] for r in con.execute("PRAGMA table_info(cafes)")]
        if "cashier_pin_hash" not in cols:   # ترقية قاعدة قديمة
            con.execute("ALTER TABLE cafes ADD COLUMN cashier_pin_hash TEXT")


def normalize_phone(raw: str) -> str:
    """يوحّد الرقم المصري: 01xxxxxxxxx (11 رقم)."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0020"):
        digits = "0" + digits[4:]
    elif digits.startswith("20") and len(digits) == 12:
        digits = "0" + digits[2:]
    if not re.fullmatch(r"01[0125]\d{8}", digits):
        raise LoyaltyError("رقم الموبايل غير صحيح")
    return digits


def add_cafe(slug, name, logo_url, color="#3b2a20", stamps_required=8,
             reward_text="مشروب مجاني"):
    if not re.fullmatch(r"[a-z0-9_]{2,30}", slug):
        raise LoyaltyError("slug لازم يكون حروف إنجليزي صغيرة وأرقام و _ فقط")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise LoyaltyError("اللون لازم يكون بصيغة #rrggbb")
    with connect() as con:
        try:
            cur = con.execute(
                "INSERT INTO cafes (slug,name,logo_url,color,stamps_required,reward_text,created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (slug, name, logo_url, color, stamps_required, reward_text, int(time.time())),
            )
        except sqlite3.IntegrityError:
            raise LoyaltyError("فيه كافيه بنفس الـ slug")
        return cur.lastrowid


def get_cafe(slug):
    with connect() as con:
        return con.execute("SELECT * FROM cafes WHERE slug=?", (slug,)).fetchone()


def register_customer(cafe_id, phone, name, agreed: bool):
    """تسجيل العميل بنفسه. لو الرقم موجود نرجّع None (ومنكشفش بيانات صاحبه)."""
    if not agreed:
        raise LoyaltyError("لازم توافق على الشروط الأول")
    phone = normalize_phone(phone)
    name = (name or "").strip()
    if not (2 <= len(name) <= 60):
        raise LoyaltyError("الاسم لازم يكون بين حرفين و60 حرف")
    now = int(time.time())
    with connect() as con:
        try:
            cur = con.execute(
                "INSERT INTO customers (cafe_id,phone,name,consent_at,consent_version,created_at)"
                " VALUES (?,?,?,?,?,?)",
                (cafe_id, phone, name, now, CONSENT_VERSION, now),
            )
        except sqlite3.IntegrityError:
            return None
        return con.execute("SELECT * FROM customers WHERE id=?", (cur.lastrowid,)).fetchone()


def find_customer(cafe_id, phone):
    phone = normalize_phone(phone)
    with connect() as con:
        return con.execute(
            "SELECT * FROM customers WHERE cafe_id=? AND phone=?", (cafe_id, phone)
        ).fetchone()


def add_stamp(cafe_id, phone, idem_key=None):
    """يزوّد ختم. يرجّع (العميل بعد التحديث، تم_فعلاً). مفتاح التكرار يمنع الضغط المزدوج."""
    customer = find_customer(cafe_id, phone)
    if not customer:
        raise LoyaltyError("العميل ده مش مسجّل في الكافيه")
    now = int(time.time())
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            if idem_key:
                dup = con.execute(
                    "SELECT 1 FROM transactions WHERE idem_key=?", (idem_key,)
                ).fetchone()
                if dup:
                    con.execute("ROLLBACK")
                    return customer, False
            last = con.execute(
                "SELECT created_at FROM transactions WHERE customer_id=? AND kind='stamp'"
                " ORDER BY id DESC LIMIT 1", (customer["id"],)
            ).fetchone()
            if last and now - last["created_at"] < MIN_SECONDS_BETWEEN_STAMPS:
                raise LoyaltyError("اتسجّل ختم للعميل ده من شوية، استنى دقيقتين")
            con.execute("UPDATE customers SET stamps=stamps+1 WHERE id=?", (customer["id"],))
            con.execute(
                "INSERT INTO transactions (cafe_id,customer_id,kind,delta,idem_key,created_at)"
                " VALUES (?,?,?,?,?,?)",
                (cafe_id, customer["id"], "stamp", 1, idem_key, now),
            )
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        updated = con.execute("SELECT * FROM customers WHERE id=?", (customer["id"],)).fetchone()
        return updated, True


def redeem(cafe_id, phone, idem_key=None):
    """يصرف مكافأة: يخصم عدد الأختام المطلوب."""
    customer = find_customer(cafe_id, phone)
    if not customer:
        raise LoyaltyError("العميل ده مش مسجّل في الكافيه")
    now = int(time.time())
    with connect() as con:
        cafe = con.execute("SELECT * FROM cafes WHERE id=?", (cafe_id,)).fetchone()
        need = cafe["stamps_required"]
        con.execute("BEGIN IMMEDIATE")
        try:
            if idem_key:
                dup = con.execute(
                    "SELECT 1 FROM transactions WHERE idem_key=?", (idem_key,)
                ).fetchone()
                if dup:
                    con.execute("ROLLBACK")
                    return customer, False
            current = con.execute(
                "SELECT stamps FROM customers WHERE id=?", (customer["id"],)
            ).fetchone()["stamps"]
            if current < need:
                raise LoyaltyError(f"العميل معاه {current} من {need} ختم، لسه مش كفاية")
            con.execute("UPDATE customers SET stamps=stamps-? WHERE id=?", (need, customer["id"]))
            con.execute(
                "INSERT INTO transactions (cafe_id,customer_id,kind,delta,idem_key,created_at)"
                " VALUES (?,?,?,?,?,?)",
                (cafe_id, customer["id"], "redeem", -need, idem_key, now),
            )
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        updated = con.execute("SELECT * FROM customers WHERE id=?", (customer["id"],)).fetchone()
        return updated, True


def delete_customer(customer_id):
    """يمسح عميل لسه معندوش عمليات (بنستخدمها لو إنشاء الكارت فشل أثناء التسجيل)."""
    with connect() as con:
        con.execute(
            "DELETE FROM customers WHERE id=? AND NOT EXISTS"
            " (SELECT 1 FROM transactions WHERE customer_id=?)", (customer_id, customer_id))


def _hash_pin(pin, salt=None):
    salt = salt or os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 200_000)
    return salt.hex() + "$" + h.hex()


def set_cashier_pin(slug, pin):
    if not re.fullmatch(r"\d{4,8}", pin or ""):
        raise LoyaltyError("كود الكاشير لازم يكون من 4 إلى 8 أرقام")
    with connect() as con:
        cur = con.execute("UPDATE cafes SET cashier_pin_hash=? WHERE slug=?",
                          (_hash_pin(pin), slug))
        if cur.rowcount == 0:
            raise LoyaltyError("الكافيه مش موجود")


def check_cashier_pin(slug, pin):
    cafe = get_cafe(slug)
    if not cafe or not cafe["cashier_pin_hash"]:
        return False
    salt_hex, hash_hex = cafe["cashier_pin_hash"].split("$")
    candidate = _hash_pin(pin or "", bytes.fromhex(salt_hex)).split("$")[1]
    return hmac.compare_digest(candidate, hash_hex)
