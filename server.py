from flask import Flask, send_from_directory, jsonify, request, Response, send_file
import asyncio
import json
import os
import queue
import re
import threading
import unicodedata

import db
from excel_utils import create_excel_file
from whatsapp import Sender, build_message

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)   # para que funcione igual desde el lanzador, el .bat o la consola

app = Flask(__name__, static_folder='public', static_url_path='')
db.init()
sender = Sender(db)

current_search = {"running": False, "stop": False}


def ok(**kw):
    return jsonify({"success": True, **kw})


def fail(msg, code=400):
    return jsonify({"success": False, "error": msg}), code


@app.route('/')
def serve_index():
    return send_from_directory('public', 'index.html')


@app.route('/api/status')
def status():
    return jsonify({"status": "Servidor Python funcionando correctamente"})


# ---------------- búsquedas ----------------
@app.route('/api/search_stream')
def search_stream():
    from scraper import run_scraper, split_cities
    rubro = request.args.get('rubro', '').strip()
    ciudades = split_cities(request.args.get('ciudades', ''))
    limit = max(1, min(int(request.args.get('limit', 20)), 120))
    if not rubro or not ciudades:
        return fail("Completá el rubro y al menos una ciudad.")
    if current_search["running"]:
        return fail("Ya hay una búsqueda en curso.")

    search_id = db.execute("INSERT INTO searches (created, rubro, ciudades) VALUES (?,?,?)",
                           (db.now(), rubro, " ; ".join(ciudades)))
    q = queue.Queue()
    current_search.update(running=True, stop=False)

    def on_result(p):
        db.upsert_place(p)
        db.execute("INSERT OR IGNORE INTO search_places VALUES (?,?)", (search_id, p["id"]))
        row = db.query("SELECT * FROM places WHERE id=?", (p["id"],), one=True)
        q.put({"status": "result", "data": db.place_to_api(row)})

    def background():
        try:
            asyncio.run(run_scraper(rubro, ciudades, limit, on_result=on_result,
                                    log=lambda m: q.put({"status": "log", "message": m}),
                                    should_stop=lambda: current_search["stop"]))
            q.put({"status": "done"})
        except Exception as e:
            q.put({"status": "error", "message": str(e)})
        finally:
            total = db.query("SELECT COUNT(*) n FROM search_places WHERE search_id=?", (search_id,), one=True)["n"]
            if total:
                db.execute("UPDATE searches SET total=? WHERE id=?", (total, search_id))
            else:
                db.execute("DELETE FROM searches WHERE id=?", (search_id,))
            current_search["running"] = False

    threading.Thread(target=background, daemon=True).start()

    def generate():
        yield f"data: {json.dumps({'status': 'start', 'search_id': search_id})}\n\n"
        while True:
            try:
                item = q.get(timeout=15)
            except queue.Empty:
                yield ": ping\n\n"
                continue
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            if item["status"] in ("done", "error"):
                break

    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/search/stop', methods=['POST'])
def search_stop():
    current_search["stop"] = True
    return ok()


@app.route('/api/searches')
def api_searches():
    return jsonify(db.query("""
        SELECT s.*, COUNT(p.id) AS total,
               SUM(CASE WHEN p.estado IN ('enviado','respondio','no_interesa') THEN 1 ELSE 0 END) AS contactados
        FROM searches s LEFT JOIN search_places sp ON sp.search_id = s.id LEFT JOIN places p ON p.id = sp.place_id
        GROUP BY s.id ORDER BY s.id DESC"""))


@app.route('/api/searches/<int:sid>/places')
def api_search_places(sid):
    rows = db.query("""SELECT p.* FROM places p JOIN search_places sp ON sp.place_id = p.id
                       WHERE sp.search_id=? ORDER BY p.reviews DESC""", (sid,))
    return jsonify([db.place_to_api(r) for r in rows])


@app.route('/api/searches/<int:sid>', methods=['DELETE'])
def api_delete_search(sid):
    db.execute("DELETE FROM search_places WHERE search_id=?", (sid,))
    db.execute("DELETE FROM searches WHERE id=?", (sid,))
    # borrar solo los locales que no están en otra búsqueda y nunca fueron contactados
    db.execute("""DELETE FROM places WHERE estado='nuevo'
                  AND id NOT IN (SELECT place_id FROM search_places)""")
    return ok()


# ---------------- contactos ----------------
@app.route('/api/places')
def api_places():
    estado = request.args.get('estado', '')
    sql, params = "SELECT * FROM places", []
    if estado:
        sql += " WHERE estado=?"
        params.append(estado)
    sql += " ORDER BY COALESCE(sent_at, '') DESC, reviews DESC"
    return jsonify([db.place_to_api(r) for r in db.query(sql, params)])


@app.route('/api/places/update', methods=['POST'])
def api_place_update():
    d = request.json or {}
    if d.get("estado") is not None:
        db.execute("UPDATE places SET estado=? WHERE id=?", (d["estado"], d["id"]))
        if d["estado"] in ("no_interesa", "respondio"):
            db.execute("UPDATE queue SET estado='cancelado' WHERE place_id=? AND estado='pendiente'", (d["id"],))
    if d.get("notas") is not None:
        db.execute("UPDATE places SET notas=? WHERE id=?", (d["notas"], d["id"]))
    return ok()


@app.route('/api/excel', methods=['POST'])
def api_excel():
    d = request.json or {}
    ids = d.get("ids", [])
    marks = ",".join("?" for _ in ids) or "''"
    rows = [db.place_to_api(r) for r in db.query(
        f"SELECT * FROM places WHERE id IN ({marks}) ORDER BY reviews DESC", ids)]
    path, name = create_excel_file(d.get("title") or "Locales", rows)
    return send_file(path, as_attachment=True, download_name=name,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# ---------------- plantillas ----------------
def _norm(s):
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def pick_template(place, templates):
    """La plantilla cuyo rubro coincide con la categoría del local; si no, la general."""
    texto = _norm(f"{place.get('categoria')} {place.get('rubro')} {place.get('name')}")
    best, best_len = None, 0
    for t in templates:
        for kw in [_norm(k).strip() for k in (t["rubros"] or "").split(",")]:
            # palabra completa, con plural opcional: "bar" coincide con "bares" pero no con "barbería"
            if kw and re.search(rf"\b{re.escape(kw)}(s|es)?\b", texto) and len(kw) > best_len:
                best, best_len = t, len(kw)
    return best or next((t for t in templates if t["is_default"]), templates[0] if templates else None)


@app.route('/api/templates', methods=['GET', 'POST'])
def api_templates():
    if request.method == 'POST':
        d = request.json or {}
        if not d.get("name") or not d.get("body"):
            return fail("Completá el nombre y el mensaje.")
        if d.get("is_default"):
            db.execute("UPDATE templates SET is_default=0")
        if d.get("id"):
            db.execute("UPDATE templates SET name=?, rubros=?, body=?, is_default=? WHERE id=?",
                       (d["name"], d.get("rubros", ""), d["body"], 1 if d.get("is_default") else 0, d["id"]))
        else:
            db.execute("INSERT INTO templates (name, rubros, body, is_default) VALUES (?,?,?,?)",
                       (d["name"], d.get("rubros", ""), d["body"], 1 if d.get("is_default") else 0))
        return ok()
    return jsonify(db.query("SELECT * FROM templates ORDER BY is_default DESC, name"))


@app.route('/api/templates/<int:tid>', methods=['DELETE'])
def api_delete_template(tid):
    db.execute("DELETE FROM templates WHERE id=?", (tid,))
    if not db.query("SELECT 1 FROM templates WHERE is_default=1"):
        db.execute("UPDATE templates SET is_default=1 WHERE id=(SELECT MIN(id) FROM templates)")
    return ok()


@app.route('/api/templates/import', methods=['POST'])
def api_import_templates():
    """Recupera las plantillas que antes se guardaban solo en el navegador."""
    existentes = {t["name"] for t in db.query("SELECT name FROM templates")}
    n = 0
    for t in request.json or []:
        if t.get("name") and t.get("content") and t["name"] not in existentes:
            db.execute("INSERT INTO templates (name, rubros, body) VALUES (?,?,?)", (t["name"], "", t["content"]))
            n += 1
    return ok(importadas=n)


@app.route('/api/preview', methods=['POST'])
def api_preview():
    d = request.json or {}
    templates = db.query("SELECT * FROM templates")
    elegido = d.get("template_id", "auto")
    out = []
    for pid in d.get("ids", []):
        p = db.query("SELECT * FROM places WHERE id=?", (pid,), one=True)
        if not p:
            continue
        t = pick_template(p, templates) if elegido == "auto" else next(
            (x for x in templates if x["id"] == int(elegido)), None)
        out.append({"id": pid, "name": p["name"], "wa_phone": p["wa_phone"], "estado": p["estado"],
                    "tel_tipo": p["tel_tipo"], "template_id": t["id"] if t else None,
                    "template": t["name"] if t else "-", "message": build_message(t["body"], p) if t else ""})
    return jsonify(out)


# ---------------- cola de envío ----------------
@app.route('/api/queue', methods=['GET', 'POST'])
def api_queue():
    if request.method == 'POST':
        agregados, salteados = 0, []
        contactados = db.contacted_phones()
        en_cola = {r["wa_phone"] for r in db.query("SELECT wa_phone FROM queue WHERE estado='pendiente'")}
        for it in (request.json or {}).get("items", []):
            p = db.query("SELECT * FROM places WHERE id=?", (it["id"],), one=True)
            if not p or not p["wa_phone"]:
                salteados.append((p or {}).get("name", "?") + " (sin teléfono válido)")
                continue
            if p["wa_phone"] in contactados or p["wa_phone"] in en_cola:
                salteados.append(p["name"] + " (ya contactado o en cola)")
                continue
            if not (it.get("message") or "").strip():
                salteados.append(p["name"] + " (mensaje vacío)")
                continue
            db.execute("INSERT INTO queue (place_id, wa_phone, message, template_id, created) VALUES (?,?,?,?,?)",
                       (p["id"], p["wa_phone"], it["message"].strip(), it.get("template_id"), db.now()))
            db.execute("UPDATE places SET estado='en_cola' WHERE id=?", (p["id"],))
            en_cola.add(p["wa_phone"])
            agregados += 1
        sender.wake()
        return ok(agregados=agregados, salteados=salteados)
    rows = db.query("""SELECT q.*, p.name, p.categoria FROM queue q LEFT JOIN places p ON p.id = q.place_id
                       ORDER BY CASE q.estado WHEN 'pendiente' THEN 0 ELSE 1 END, q.id DESC LIMIT 500""")
    return jsonify(rows)


@app.route('/api/queue/<int:qid>', methods=['DELETE'])
def api_queue_cancel(qid):
    item = db.query("SELECT * FROM queue WHERE id=? AND estado='pendiente'", (qid,), one=True)
    if item:
        db.execute("UPDATE queue SET estado='cancelado' WHERE id=?", (qid,))
        db.execute("UPDATE places SET estado='nuevo' WHERE id=? AND estado='en_cola'", (item["place_id"],))
    return ok()


@app.route('/api/queue/cancel_all', methods=['POST'])
def api_queue_cancel_all():
    db.execute("UPDATE places SET estado='nuevo' WHERE estado='en_cola'")
    db.execute("UPDATE queue SET estado='cancelado' WHERE estado='pendiente'")
    return ok()


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    if request.method == 'POST':
        vals = {k: int(v) for k, v in (request.json or {}).items() if str(v).lstrip("-").isdigit()}
        if vals.get("demora_min", 1) < 30:
            return fail("La demora mínima no puede ser menor a 30 segundos.")
        db.set_settings(vals)
        sender.wake()
        return ok()
    return jsonify(db.get_settings())


@app.route('/api/sender')
def api_sender():
    return jsonify(sender.status())


@app.route('/api/sender/<accion>', methods=['POST'])
def api_sender_action(accion):
    if accion not in ("start", "stop"):
        return fail("Acción inválida")
    db.set_settings({"envio_activo": 1 if accion == "start" else 0})
    sender.wake()
    return ok()


@app.route('/api/wa_login', methods=['POST'])
def api_wa_login():
    sender.request_login()
    return ok()


# ---------------- filtros guardados ----------------
@app.route('/api/presets', methods=['GET', 'POST'])
def api_presets():
    if request.method == 'POST':
        d = request.json or {}
        db.execute("INSERT INTO presets (rubro, ciudades, limite) VALUES (?,?,?)",
                   (d.get("rubro"), d.get("ciudades"), int(d.get("limite") or 20)))
        return ok()
    return jsonify(db.query("SELECT * FROM presets ORDER BY id"))


@app.route('/api/presets/<int:pid>', methods=['DELETE'])
def api_delete_preset(pid):
    db.execute("DELETE FROM presets WHERE id=?", (pid,))
    return ok()


if __name__ == '__main__':
    print("\n======================================================")
    print("-> Prospector Pro iniciado")
    print("-> Panel disponible en: http://localhost:5000")
    print("======================================================\n")
    app.run(port=5000, debug=False, threaded=True)
