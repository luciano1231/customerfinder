from flask import Flask, send_from_directory, jsonify, request, Response
import os
from datetime import datetime

app = Flask(__name__, static_folder='public', static_url_path='')

@app.route('/')
def serve_index():
    return send_from_directory('public', 'index.html')

@app.route('/api/status')
def status():
    return jsonify({"status": "Servidor Python funcionando correctamente"})

import json

SENT_HISTORY_FILE = 'sent_history.json'

def get_sent_phones():
    if os.path.exists(SENT_HISTORY_FILE):
        with open(SENT_HISTORY_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def add_sent_phone(phone):
    phones = get_sent_phones()
    # Limpiamos igual que en whatsapp.py para mantener consistencia
    clean_phone = phone.replace(" ", "").replace("-", "").replace("+", "")
    if clean_phone.startswith("0"): 
        clean_phone = "54" + clean_phone[1:]
    if not clean_phone.startswith("54"): 
        clean_phone = "54" + clean_phone
        
    if clean_phone not in phones:
        phones.append(clean_phone)
        with open(SENT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(phones, f)

@app.route('/api/search', methods=['POST'])
def search_maps():
    data = request.json
    rubro = data.get('rubro', 'Restaurantes')
    ciudad = data.get('ciudad', 'Corrientes')
    limit = int(data.get('limit', 10))
    
    ciudades = [c.strip() for c in ciudad.split(',') if c.strip()]
    sent_phones = get_sent_phones()
    all_results = []
    
    try:
        import asyncio
        from scraper import run_scraper
        for c in ciudades:
            # Ejecutamos el scraper para cada ciudad
            results = asyncio.run(run_scraper(rubro, c, limit, sent_phones))
            all_results.extend(results)
        return jsonify({"success": True, "results": all_results})
    except Exception as e:
        print(f"Error en endpoint /api/search: {e}")
        return jsonify({"success": False, "error": str(e)})

import queue
import threading

@app.route('/api/search_stream', methods=['GET'])
def search_maps_stream():
    rubro = request.args.get('rubro', 'Restaurantes')
    ciudad = request.args.get('ciudad', 'Corrientes')
    limit = int(request.args.get('limit', 10))
    
    ciudades = [c.strip() for c in ciudad.split(',') if c.strip()]
    sent_phones = get_sent_phones()
    
    q = queue.Queue()
    
    def background_scraper():
        import asyncio
        from scraper import run_scraper
        try:
            asyncio.run(run_scraper(
                rubro, ciudades, limit, sent_phones, 
                on_result=lambda r: q.put({"type": "result", "data": r})
            ))
            q.put({"type": "done"})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})

    # Ejecutar en un hilo paralelo para no bloquear el generador SSE
    threading.Thread(target=background_scraper).start()
    
    def generate():
        while True:
            item = q.get()
            if item["type"] == "done":
                yield f"data: {json.dumps({'status': 'done'})}\n\n"
                break
            elif item["type"] == "error":
                yield f"data: {json.dumps({'status': 'error', 'message': item['message']})}\n\n"
                break
            else:
                yield f"data: {json.dumps({'status': 'result', 'data': item['data']})}\n\n"
                
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/wa_auth', methods=['POST'])
def wa_auth():
    try:
        import asyncio
        from whatsapp import authenticate
        asyncio.run(authenticate())
        return jsonify({"success": True, "message": "Autenticación finalizada"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/send', methods=['POST'])
def send_bulk_messages():
    data = request.json
    clients = data.get('clients', [])
    template = data.get('template', '')
    
    if not clients or not template:
        return jsonify({"success": False, "error": "Faltan clientes seleccionados o plantilla de mensaje."})
        
    # 2. Enviar mensajes usando Playwright
    try:
        import asyncio
        from whatsapp import send_messages
        results = asyncio.run(send_messages(clients, template))
        
        # Registrar los teléfonos a los que se envió exitosamente
        for res in results:
            if res.get('status') == 'Enviado':
                add_sent_phone(res.get('phone'))
                
        return jsonify({"success": True, "results": results})
    except Exception as e:
        print(f"Error en envío masivo: {e}")
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    print("\n======================================================")
    print("-> Prospector Pro Server (Python) iniciado correctamente")
    print("-> Panel de Control disponible en: http://localhost:5000")
    print("======================================================\n")
    # debug=False para producción y para evitar bugs del reloader al ejecutar sin consola
    app.run(port=5000, debug=False)
