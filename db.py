"""Base de datos local (SQLite): búsquedas, locales, plantillas, cola de envíos y configuración."""
import json
import os
import sqlite3
import threading
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "datos.db")
_lock = threading.Lock()

DEFAULT_SETTINGS = {
    "limite_diario": 25,       # mensajes por día
    "demora_min": 90,          # segundos entre mensajes
    "demora_max": 240,
    "hora_inicio": 10,         # solo envía entre estas horas
    "hora_fin": 19,
    "pausa_cada": 8,           # cada N mensajes hace una pausa larga
    "pausa_larga_min": 10,     # minutos
    "envio_activo": 0,
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TEXT, rubro TEXT, ciudades TEXT, total INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS places (
    id TEXT PRIMARY KEY,               -- url de maps normalizada
    name TEXT, phone TEXT, wa_phone TEXT, tel_tipo TEXT,
    address TEXT, categoria TEXT, rubro TEXT, ciudad TEXT,
    rating REAL, reviews INTEGER DEFAULT 0,
    web TEXT, web_tipo TEXT, instagram TEXT, horarios TEXT, nocturno INTEGER DEFAULT 0,
    maps_url TEXT,
    estado TEXT DEFAULT 'nuevo',       -- nuevo | en_cola | enviado | sin_whatsapp | error | respondio | no_interesa
    sent_at TEXT, notas TEXT DEFAULT '',
    first_seen TEXT, updated TEXT
);
CREATE INDEX IF NOT EXISTS idx_places_wa ON places(wa_phone);
CREATE TABLE IF NOT EXISTS search_places (
    search_id INTEGER, place_id TEXT, PRIMARY KEY (search_id, place_id)
);
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT, rubros TEXT DEFAULT '', body TEXT, is_default INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    place_id TEXT, wa_phone TEXT, message TEXT, template_id INTEGER,
    estado TEXT DEFAULT 'pendiente',   -- pendiente | enviado | sin_whatsapp | error | cancelado
    created TEXT, sent_at TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT, rubro TEXT, ciudades TEXT, limite INTEGER
);
"""


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def query(sql, params=(), one=False):
    with _lock, connect() as con:
        rows = [dict(r) for r in con.execute(sql, params).fetchall()]
    return (rows[0] if rows else None) if one else rows


def execute(sql, params=()):
    with _lock, connect() as con:
        cur = con.execute(sql, params)
        return cur.lastrowid


def executemany(sql, seq):
    with _lock, connect() as con:
        con.executemany(sql, seq)


def init():
    with _lock, connect() as con:
        con.executescript(SCHEMA)
        con.execute("PRAGMA journal_mode=WAL")
    if not query("SELECT 1 FROM templates LIMIT 1"):
        execute("INSERT INTO templates (name, rubros, body, is_default) VALUES (?,?,?,1)", (
            "General",
            "",
            "Hola, equipo de {nombre} 👋 Soy Lucía, ayudo a negocios de {ciudad} a conseguir más clientes con una "
            "página web propia. ¿Les interesaría ver un ejemplo sin compromiso?"
            " ||| "
            "¡Buenas! Les escribo a {nombre}. Me dedico a crear páginas web para comercios de {ciudad}, "
            "con menú, ubicación y contacto directo por WhatsApp. ¿Puedo mostrarles algunos ejemplos?",
        ))
    _migrate_json()


# ---------- configuración ----------
def get_settings():
    s = dict(DEFAULT_SETTINGS)
    for r in query("SELECT k, v FROM settings"):
        try:
            s[r["k"]] = json.loads(r["v"])
        except ValueError:
            s[r["k"]] = r["v"]
    return s


def set_settings(values):
    for k, v in values.items():
        if k in DEFAULT_SETTINGS:
            execute("INSERT OR REPLACE INTO settings (k, v) VALUES (?, ?)", (k, json.dumps(v)))


def get_secret(k):
    r = query("SELECT v FROM settings WHERE k=?", ("_" + k,), one=True)
    return r["v"] if r else None


def set_secret(k, v):
    execute("INSERT OR REPLACE INTO settings (k, v) VALUES (?, ?)", ("_" + k, v))
    return v


# ---------- locales ----------
PLACE_FIELDS = ["name", "phone", "wa_phone", "tel_tipo", "address", "categoria", "rubro", "ciudad", "rating",
                "reviews", "web", "web_tipo", "instagram", "horarios", "nocturno", "maps_url"]


def upsert_place(p):
    """Inserta o actualiza los datos del local sin pisar su estado de contacto."""
    row = {k: p.get(k) for k in PLACE_FIELDS}
    if isinstance(row["horarios"], list):
        row["horarios"] = json.dumps(row["horarios"], ensure_ascii=False)
    row["nocturno"] = 1 if row["nocturno"] else 0
    cols = ", ".join(PLACE_FIELDS)
    marks = ", ".join("?" for _ in PLACE_FIELDS)
    updates = ", ".join(f"{k}=excluded.{k}" for k in PLACE_FIELDS)
    execute(
        f"INSERT INTO places (id, {cols}, first_seen, updated) VALUES (?, {marks}, ?, ?) "
        f"ON CONFLICT(id) DO UPDATE SET {updates}, updated=excluded.updated",
        [p["id"]] + [row[k] for k in PLACE_FIELDS] + [now(), now()],
    )
    # si ese número ya fue contactado desde otro local (cadenas, duplicados), heredar el estado
    if p.get("wa_phone"):
        prev = query("SELECT estado FROM places WHERE wa_phone=? AND id<>? AND estado IN ('enviado','sin_whatsapp','respondio','no_interesa') "
                     "LIMIT 1", (p["wa_phone"], p["id"]), one=True)
        if prev:
            execute("UPDATE places SET estado=? WHERE id=? AND estado='nuevo'", (prev["estado"], p["id"]))


def place_to_api(r):
    r = dict(r)
    try:
        r["horarios"] = json.loads(r.get("horarios") or "[]")
    except ValueError:
        r["horarios"] = []
    r["wa_link"] = f"https://wa.me/{r['wa_phone']}" if r.get("wa_phone") else ""
    return r


def contacted_phones():
    return {r["wa_phone"] for r in query(
        "SELECT wa_phone FROM places WHERE wa_phone IS NOT NULL "
        "AND estado IN ('en_cola','enviado','sin_whatsapp','respondio','no_interesa')")}


# ---------- migración de los archivos JSON viejos ----------
def _migrate_json():
    old = os.path.join(BASE_DIR, "saved_searches.json")
    flag = os.path.join(BASE_DIR, "saved_searches.migrado.json")
    if not os.path.exists(old) or os.path.exists(flag):
        return
    from whatsapp import clean_argentina_phone, phone_type
    try:
        searches = json.load(open(old, encoding="utf-8"))
    except ValueError:
        searches = []
    for s in searches:
        ciudades = " ; ".join(s.get("ciudades", []))
        created = s.get("date", now())
        sid = execute("INSERT INTO searches (created, rubro, ciudades, total) VALUES (?,?,?,?)",
                      (created, s.get("rubro", ""), ciudades, len(s.get("data", []))))
        for d in s.get("data", []):
            url = d.get("url", "")
            pid = url.split("?")[0].split("/data=")[0] or d.get("name")
            phone = d.get("phone", "")
            upsert_place({
                "id": pid, "name": d.get("name"), "phone": phone,
                "wa_phone": clean_argentina_phone(phone) if phone and phone != "No tiene" else None,
                "tel_tipo": phone_type(phone), "address": d.get("address"), "rubro": s.get("rubro"),
                "ciudad": ciudades, "web_tipo": "Web propia" if d.get("has_web") else "Sin web",
                "maps_url": url, "reviews": 0,
            })
            execute("INSERT OR IGNORE INTO search_places VALUES (?,?)", (sid, pid))
    os.replace(old, flag)
