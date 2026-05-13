from flask import Flask, send_from_directory, jsonify, request
import os
from datetime import datetime

app = Flask(__name__, static_folder='public', static_url_path='')

@app.route('/')
def serve_index():
    return send_from_directory('public', 'index.html')

@app.route('/api/status')
def status():
    return jsonify({"status": "Servidor Python funcionando correctamente"})

@app.route('/api/search', methods=['POST'])
def search_maps():
    data = request.json
    rubro = data.get('rubro', 'Restaurantes')
    ciudad = data.get('ciudad', 'Corrientes')
    limit = int(data.get('limit', 10))
    
    try:
        import asyncio
        from scraper import run_scraper
        # Ejecutamos el scraper
        results = asyncio.run(run_scraper(rubro, ciudad, limit))
        return jsonify({"success": True, "results": results})
    except Exception as e:
        print(f"Error en endpoint /api/search: {e}")
        return jsonify({"success": False, "error": str(e)})

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
        return jsonify({"success": True, "results": results})
    except Exception as e:
        print(f"Error en envío masivo: {e}")
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    print("\n======================================================")
    print("-> Prospector Pro Server (Python) iniciado correctamente")
    print("-> Panel de Control disponible en: http://localhost:5000")
    print("======================================================\n")
    # debug=True para desarrollo
    app.run(port=5000, debug=True)
