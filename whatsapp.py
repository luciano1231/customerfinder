"""Envío de mensajes por WhatsApp Web, de a poco, desde una cola guardada en la base de datos."""
import logging
import os
import random
import re
import threading
import time
import urllib.parse
from collections import deque
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_DIR = os.path.join(BASE_DIR, "wa_session")

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "whatsapp_debug.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def clean_argentina_phone(phone):
    """
    Formato que pide WhatsApp para Argentina: 54 + 9 + código de área (sin 0) + número (sin 15).
    Ej: '0379 15-475-8345' -> '5493794758345'
    """
    digits = "".join(filter(str.isdigit, phone or ""))
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("549"):
        digits = digits[3:]
    elif digits.startswith("54"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 12 and digits[3:5] == "15":      # 379 15 4758345
        digits = digits[:3] + digits[5:]
    elif len(digits) == 12 and digits[4:6] == "15":    # 3783 15 458345
        digits = digits[:4] + digits[6:]
    elif len(digits) == 12 and digits[2:4] == "15":    # 11 15 45678901 (área de 2)
        digits = digits[:2] + digits[4:]
    if len(digits) != 10:
        return None
    return "549" + digits


def phone_type(phone):
    """Google Maps muestra los celulares con '15' (0379 15-...). Los fijos casi nunca tienen WhatsApp."""
    if not phone or phone == "No tiene":
        return "Sin teléfono"
    digits = "".join(filter(str.isdigit, phone))
    if re.search(r"\b15[\s-]", phone) or digits.startswith("549") or (phone.strip().startswith("+54 9")):
        return "Celular"
    return "Fijo"


def nombre_corto(name):
    """'El Mirador del Paraná - Parrilla Restaurant' -> 'El Mirador del Paraná'"""
    n = re.split(r"\s[-|–]\s|\s\(", name or "")[0].strip()
    return n or (name or "").strip()


def build_message(body, place):
    variants = [v.strip() for v in (body or "").split("|||") if v.strip()]
    msg = random.choice(variants) if variants else ""
    ciudad = (place.get("ciudad") or "").split(",")[0].strip()
    return (msg.replace("{nombre}", nombre_corto(place.get("name")))
               .replace("{ciudad}", ciudad)
               .replace("{rubro}", (place.get("categoria") or place.get("rubro") or "").lower()))


class Sender:
    """Un único hilo que maneja el navegador de WhatsApp: login y envíos de la cola."""

    def __init__(self, db):
        self.db = db
        self.log = deque(maxlen=200)
        self.estado = "Detenido"
        self.sesion = "desconocida"   # desconocida | ok | qr
        self.proximo_envio = None
        self._wake = threading.Event()
        self._login_requested = False
        self._ctx = None
        self._page = None
        self._pw = None
        self._next_allowed = 0      # la demora entre mensajes se respeta aunque se despierte el hilo
        threading.Thread(target=self._run, daemon=True).start()

    # ---------- API para el servidor ----------
    def status(self):
        s = self.db.get_settings()
        return {
            "estado": self.estado,
            "sesion": self.sesion,
            "activo": bool(s["envio_activo"]),
            "enviados_hoy": self.sent_today(),
            "limite_diario": s["limite_diario"],
            "pendientes": self.db.query("SELECT COUNT(*) n FROM queue WHERE estado='pendiente'", one=True)["n"],
            "proximo_envio": self.proximo_envio,
            "log": list(self.log)[-40:][::-1],
        }

    def wake(self):
        self._wake.set()

    def request_login(self):
        self._login_requested = True
        self.wake()

    def sent_today(self):
        hoy = datetime.now().strftime("%Y-%m-%d")
        return self.db.query("SELECT COUNT(*) n FROM queue WHERE estado='enviado' AND sent_at LIKE ?",
                             (hoy + "%",), one=True)["n"]

    # ---------- internos ----------
    def _say(self, msg):
        line = f"{datetime.now().strftime('%d/%m %H:%M:%S')}  {msg}"
        self.log.append(line)
        logging.info(msg)

    def _sleep(self, seconds):
        """Espera interrumpible (se corta si cambian la configuración o pausan)."""
        self._wake.clear()
        self._wake.wait(seconds)

    def _open_browser(self):
        if self._page is not None:
            try:
                self._page.title()
                return self._page
            except Exception:
                self._close_browser()
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR, headless=False, viewport={"width": 1100, "height": 750})
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        return self._page

    def _close_browser(self):
        for obj in (self._ctx, self._pw):
            try:
                obj and (obj.close() if obj is self._ctx else obj.stop())
            except Exception:
                pass
        self._ctx = self._page = self._pw = None

    def _ensure_session(self, wait_qr_seconds):
        page = self._open_browser()
        if "web.whatsapp.com" not in page.url:
            page.goto("https://web.whatsapp.com/")
        try:
            page.wait_for_selector('#pane-side, canvas', timeout=60000)
        except Exception:
            pass
        if page.query_selector("#pane-side"):
            self.sesion = "ok"
            return True
        self.sesion = "qr"
        self.estado = "Escaneá el código QR en la ventana de WhatsApp"
        self._say("WhatsApp necesita que escanees el QR (Dispositivos vinculados).")
        try:
            page.wait_for_selector("#pane-side", timeout=wait_qr_seconds * 1000)
            self.sesion = "ok"
            self._say("Sesión de WhatsApp iniciada.")
            page.wait_for_timeout(3000)
            return True
        except Exception:
            return False

    def _send_one(self, item):
        page = self._page
        url = (f"https://web.whatsapp.com/send?phone={item['wa_phone']}"
               f"&text={urllib.parse.quote(item['message'])}")
        page.goto(url)
        compose = 'footer div[contenteditable="true"]'
        invalid = ('div[role="dialog"]:has-text("no es válido"), div[role="dialog"]:has-text("invalid"), '
                   'div[data-animate-modal-popup="true"]:has-text("no es válido")')
        deadline = time.time() + 60
        while time.time() < deadline:
            if page.query_selector(invalid):
                return "sin_whatsapp", "El número no tiene WhatsApp"
            box = page.query_selector(compose)
            if box and (box.inner_text() or "").strip():
                break
            page.wait_for_timeout(1000)
        else:
            return "error", "No cargó el chat"
        page.wait_for_timeout(random.randint(1500, 4000))   # "leer" antes de enviar
        before = len(page.query_selector_all("div.message-out"))
        page.keyboard.press("Enter")
        for _ in range(20):
            page.wait_for_timeout(1000)
            box = page.query_selector(compose)
            sent_bubble = len(page.query_selector_all("div.message-out")) > before
            if sent_bubble or (box and not (box.inner_text() or "").strip()):
                page.wait_for_timeout(2500)
                return "enviado", ""
        return "error", "El mensaje no salió de la caja de texto"

    def _in_window(self, s):
        h = datetime.now().hour
        return s["hora_inicio"] <= h < s["hora_fin"]

    def _run(self):
        enviados_seguidos = 0
        while True:
            try:
                if self._login_requested:
                    self._login_requested = False
                    self.estado = "Abriendo WhatsApp Web..."
                    ok = self._ensure_session(wait_qr_seconds=300)
                    self.estado = "Sesión lista" if ok else "No se completó el inicio de sesión"
                    continue

                s = self.db.get_settings()
                if not s["envio_activo"]:
                    self.estado, self.proximo_envio = "Detenido", None
                    if self._page is not None:
                        self._close_browser()
                    self._sleep(3600)
                    continue
                if not self._in_window(s):
                    self.estado = f"Fuera de horario (envía de {s['hora_inicio']} a {s['hora_fin']} h)"
                    self._close_browser()
                    self._sleep(300)
                    continue
                if self.sent_today() >= s["limite_diario"]:
                    self.estado = f"Límite diario alcanzado ({s['limite_diario']}). Sigue mañana."
                    self._close_browser()
                    self._sleep(600)
                    continue
                item = self.db.query("SELECT * FROM queue WHERE estado='pendiente' ORDER BY id LIMIT 1", one=True)
                if not item:
                    self.estado, self.proximo_envio = "Cola vacía", None
                    self._close_browser()
                    self._sleep(600)
                    continue
                falta = self._next_allowed - time.time()
                if falta > 0:
                    self._sleep(falta)
                    continue
                if not self._ensure_session(wait_qr_seconds=300):
                    self._sleep(30)
                    continue

                place = self.db.query("SELECT name FROM places WHERE id=?", (item["place_id"],), one=True) or {}
                nombre = place.get("name", item["wa_phone"])
                self.estado = f"Enviando a {nombre}..."
                try:
                    resultado, error = self._send_one(item)
                except Exception as e:
                    resultado, error = "error", str(e)[:200]
                    self._close_browser()
                ahora = self.db.now()
                self.db.execute("UPDATE queue SET estado=?, sent_at=?, error=? WHERE id=?",
                                (resultado, ahora, error, item["id"]))
                self.db.execute("UPDATE places SET estado=?, sent_at=? WHERE id=?",
                                (resultado, ahora, item["place_id"]))
                self._say({"enviado": "✅ Enviado a ", "sin_whatsapp": "⚪ Sin WhatsApp: "}
                          .get(resultado, "❌ Error con ") + f"{nombre}" + (f" ({error})" if error and resultado == "error" else ""))

                if resultado != "enviado":
                    # números sin WhatsApp: no cuentan para el límite, pero igual se espera un poco
                    self._next_allowed = time.time() + random.uniform(15, 40)
                    continue
                enviados_seguidos += 1
                if s["pausa_cada"] and enviados_seguidos % s["pausa_cada"] == 0:
                    espera = random.uniform(s["pausa_larga_min"] * 60, s["pausa_larga_min"] * 90)
                else:
                    espera = random.uniform(s["demora_min"], s["demora_max"])
                self.proximo_envio = datetime.fromtimestamp(time.time() + espera).strftime("%H:%M:%S")
                self.estado = f"Esperando {int(espera)} s para el próximo mensaje"
                self._next_allowed = time.time() + espera
            except Exception as e:
                logging.exception("Error en el hilo de envío")
                self._say(f"Error inesperado: {e}")
                self._close_browser()
                self._sleep(30)
