from playwright.async_api import async_playwright
import os
import urllib.parse
import asyncio

SESSION_DIR = os.path.join(os.getcwd(), "wa_session")

async def authenticate():
    print("Abriendo WhatsApp Web para autenticación...")
    async with async_playwright() as p:
        # headless=False para que puedas ver el código QR
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            viewport={"width": 1000, "height": 700}
        )
        
        # Tomar la pestaña que se abre por defecto
        if len(browser.pages) > 0:
            page = browser.pages[0]
        else:
            page = await browser.new_page()
            
        await page.goto("https://web.whatsapp.com/")
        
        try:
            print("Esperando a que inicies sesión o cierres la ventana...")
            # Detectamos si el panel de chats aparece (lo que significa éxito)
            await page.wait_for_selector('div[id="pane-side"]', timeout=300000) # Espera 5 min max
            print("¡Sesión iniciada con éxito! Guardando contexto...")
            await page.wait_for_timeout(3000) # Tiempo para que guarde cookies
        except Exception as e:
            print("Tiempo de espera agotado o ventana cerrada.")
            
        await browser.close()
        return True

async def send_messages(clients, template):
    # clients debe ser una lista de diccionarios: [{"phone": "0379...", "name": "Local A"}]
    async with async_playwright() as p:
        # Usamos headless=False para que la usuaria vea cómo se envían los mensajes (da confianza)
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            viewport={"width": 1000, "height": 700}
        )
        
        if len(browser.pages) > 0:
            page = browser.pages[0]
        else:
            page = await browser.new_page()
            
        results = []
            
        for client in clients:
            phone = client['phone']
            name = client['name']
            
            # Limpieza del número para Argentina
            clean_phone = phone.replace(" ", "").replace("-", "").replace("+", "")
            
            # Reglas simples para Corrientes, Arg (esto se puede ajustar a futuro)
            # Si empieza con 0 (ej: 0379), se lo quitamos y agregamos el 54
            if clean_phone.startswith("0"): 
                clean_phone = "54" + clean_phone[1:]
            
            # Si no tiene código de país, asumimos Argentina (54)
            if not clean_phone.startswith("54"): 
                clean_phone = "54" + clean_phone
                
            msg = template.replace("{nombre}", name)
            encoded_msg = urllib.parse.quote(msg)
            
            url = f"https://web.whatsapp.com/send?phone={clean_phone}&text={encoded_msg}"
            
            try:
                await page.goto(url, wait_until="domcontentloaded")
                
                # Esperar el botón de enviar
                send_button = page.locator('span[data-icon="send"]')
                await send_button.wait_for(timeout=20000)
                await send_button.click()
                
                # Esperar a que el mensaje salga de la bandeja
                await page.wait_for_timeout(3000)
                results.append({"phone": phone, "status": "Enviado"})
                print(f"Mensaje enviado a {name} ({clean_phone})")
                
            except Exception as e:
                print(f"Error con {name} ({phone}): {e}")
                results.append({"phone": phone, "status": "Error"})
                
        await browser.close()
        return results

if __name__ == "__main__":
    # Comando de prueba
    asyncio.run(authenticate())
