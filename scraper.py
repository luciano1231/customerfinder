"""Buscador de locales en Google Maps (Playwright)."""
from playwright.async_api import async_playwright
import urllib.parse
import asyncio
import re
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from whatsapp import clean_argentina_phone, phone_type

# Con el user-agent por defecto de Playwright, Google muestra una "vista limitada"
# (sin cantidad de reseñas ni horario semanal).
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
WORKERS = 2

REDES = ("instagram.com", "facebook.com", "fb.com", "wa.me", "whatsapp.com", "linktr.ee", "tiktok.com",
         "linkin.bio", "beacons.ai", "taplink")
PLATAFORMAS = ("fu.do", "fudo", "tento.solutions", "tucan.la", "alacarta.online", "meniu", "menu.", "carta.",
               "pedidosya", "rappi")
NO_ES_WEB = (".gov.ar", "booking.com", "bit.ly", "google.", "tripadvisor")


def norm(s):
    return re.sub(r"[ \xa0 ]", " ", s or "")


def split_cities(text):
    """Ciudades separadas por ';' o por renglón. 'Corrientes, Argentina' es UNA ciudad."""
    if isinstance(text, list):
        return [c.strip() for c in text if c.strip()]
    return [c.strip() for c in re.split(r"[;\n]", text or "") if c.strip()]


def web_tipo(web, links):
    w = (web or "").lower()
    todos = " ".join(links).lower() + " " + w
    if "fu.do" in todos or "fudo" in todos:
        return "FUDO"
    if any(k in w for k in PLATAFORMAS):
        return "Plataforma menú/pedidos"
    if not w or any(k in w for k in NO_ES_WEB):
        return "Sin web"
    if "instagram.com" in w:
        return "Solo Instagram"
    if "facebook.com" in w or "fb.com" in w:
        return "Solo Facebook"
    if any(k in w for k in REDES):
        return "Red social / link"
    return "Web propia"


def _to_min(t):
    t = t.strip().lower().replace(".", "").replace(" ", "")
    m = re.match(r"(\d{1,2})(?::(\d{2}))?(am|pm)?", t)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap == "pm" and h != 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    return h * 60 + mi


def es_nocturno(horarios):
    """True si algún día cierra a las 23:00 o más tarde (o pasada la medianoche)."""
    for dia in horarios:
        if "24 horas" in dia.lower():
            return True
        for a, b in re.findall(r"[Dd]e (.+?) a ([^,]+?)(?= y |,|$)", dia):
            ini, fin = _to_min(a), _to_min(b)
            if fin is None:
                continue
            if fin >= 23 * 60 or fin == 0 or (ini is not None and fin < ini):
                return True
    return False


def place_key(href):
    return href.split("?")[0].split("/data=")[0]


async def _collect_links(page, query, limit, log):
    url = "https://www.google.com/maps/search/" + urllib.parse.quote(query) + "?hl=es"
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    sel = 'a[href*="/maps/place/"]'
    try:
        await page.locator('div[role="feed"]').wait_for(timeout=20000)
    except Exception:
        # Maps a veces abre directo la ficha cuando hay un único resultado
        return [page.url] if "/maps/place/" in page.url else []
    last = -1
    for _ in range(40):
        n = await page.locator(sel).count()
        if n >= limit:
            break
        if n == last:
            await page.wait_for_timeout(2500)
            if await page.locator(sel).count() == n:
                break
        last = n
        await page.evaluate("""() => { const f = document.querySelector('div[role="feed"]');
                                      if (f) f.scrollTop = f.scrollHeight; }""")
        await page.wait_for_timeout(1800)
        if await page.locator("text=Llegaste al final de la lista").count():
            break
    links = await page.locator(sel).evaluate_all("els => els.map(e => e.href)")
    log(f"{query}: {len(links)} locales en la lista")
    return links[:limit]


async def _scrape_place(page, href):
    await page.goto(href, wait_until="domcontentloaded", timeout=60000)
    await page.locator("h1").last.wait_for(timeout=25000)
    await page.wait_for_timeout(1500)
    main = page.locator('div[role="main"]').last
    labels = [norm(x) for x in await main.locator("[aria-label]").evaluate_all(
        "els => els.map(e => e.getAttribute('aria-label'))")]
    hrefs = await main.locator("a[href]").evaluate_all("els => els.map(e => e.href)")
    externos = [h for h in hrefs if "google." not in h and not h.startswith("tel:")]

    def label_value(prefix):
        return next((l[len(prefix):].strip() for l in labels if l.startswith(prefix)), "")

    rating = next((float(m.group(1).replace(",", ".")) for l in labels
                   if (m := re.match(r"([\d,\.]+) estrellas", l))), None)
    reviews = next((int(re.sub(r"\D", "", m.group(1))) for l in labels
                    if (m := re.match(r"([\d\.]+) reseñas?", l))), 0)
    try:
        categoria = norm(await main.locator('button[jsaction*="category"]').first.inner_text(timeout=2000))
    except Exception:
        categoria = ""
    web = ""
    w = main.locator('a[data-item-id="authority"]').first
    if await w.count():
        web = await w.get_attribute("href") or ""
    horarios = [l.split(", Copiar")[0] for l in labels
                if re.match(r"^(lunes|martes|miércoles|jueves|viernes|sábado|domingo)", l)]
    phone = label_value("Teléfono:")
    return {
        "id": place_key(href),
        "name": norm(await page.locator("h1").last.inner_text()).strip(),
        "phone": phone,
        "wa_phone": clean_argentina_phone(phone) if phone else None,
        "tel_tipo": phone_type(phone),
        "address": label_value("Dirección:"),
        "categoria": categoria,
        "rating": rating,
        "reviews": reviews,
        "web": web,
        "web_tipo": web_tipo(web, externos),
        "instagram": next((h for h in externos if "instagram.com" in h), ""),
        "horarios": horarios,
        "nocturno": es_nocturno(horarios),
        "maps_url": href.split("?")[0],
    }


async def run_scraper(rubro, ciudades, limit=20, on_result=None, log=print, should_stop=lambda: False):
    """Busca `rubro` en cada ciudad y llama a on_result(local) por cada ficha leída."""
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = await browser.new_context(locale="es-AR", user_agent=USER_AGENT,
                                        viewport={"width": 1400, "height": 900})
        try:
            page = await ctx.new_page()
            for ciudad in split_cities(ciudades):
                if should_stop():
                    break
                log(f"Buscando {rubro} en {ciudad}...")
                try:
                    links = await _collect_links(page, f"{rubro} en {ciudad}", limit, log)
                except Exception as e:
                    log(f"No se pudo buscar en {ciudad}: {e}")
                    continue
                seen, unique = set(), []
                for h in links:
                    if place_key(h) not in seen:
                        seen.add(place_key(h))
                        unique.append(h)
                queue = asyncio.Queue()
                for h in unique:
                    queue.put_nowait((h, 0))

                async def worker():
                    pg = await ctx.new_page()
                    while not queue.empty() and not should_stop():
                        h, intento = await queue.get()
                        try:
                            d = await _scrape_place(pg, h)
                        except Exception:
                            if intento < 2:
                                await pg.wait_for_timeout(6000)
                                queue.put_nowait((h, intento + 1))
                            continue
                        d["rubro"], d["ciudad"] = rubro, ciudad
                        results.append(d)
                        if on_result:
                            on_result(d)
                        await pg.wait_for_timeout(1000)
                    await pg.close()

                await asyncio.gather(*[worker() for _ in range(WORKERS)])
        finally:
            await browser.close()
    return results
