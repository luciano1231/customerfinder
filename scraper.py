from playwright.async_api import async_playwright
import urllib.parse
import asyncio

async def run_scraper(rubro, ciudades, limit=10, sent_phones=None, on_result=None):
    results = []
    
    async with async_playwright() as p:
        # headless=True para que no abra la ventana visiblemente e interrumpa
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(locale="es-AR")
        
        try:
            for ciudad in ciudades:
                if not ciudad.strip(): continue
                print(f"Buscando {rubro} en {ciudad}...")
                query = f"{rubro} en {ciudad.strip()}"
                encoded = urllib.parse.quote(query)
                url = f"https://www.google.com/maps/search/{encoded}"
                
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    
                    # Esperar a que cargue el panel de resultados
                    try:
                        feed = page.locator('div[role="feed"]')
                        await feed.wait_for(timeout=15000)
                    except:
                        print(f"No se encontró el contenedor de resultados para {ciudad}.")
                        continue
        
                    visited = set()
                    city_results = 0
                    
                    while city_results < limit:
                        items = await page.locator('a[href*="https://www.google.com/maps/place/"]').all()
                        added_in_pass = False
                        
                        for item in items:
                            if city_results >= limit: break
                            
                            href = await item.get_attribute("href")
                            if not href or href in visited: continue
                            visited.add(href)
                            added_in_pass = True
                            
                            try:
                                # Extraer nombre directo del atributo aria-label (mucho más preciso)
                                name = await item.get_attribute("aria-label")
                                
                                # Clic en el local para ver detalles (teléfono y web)
                                await item.click()
                                await page.wait_for_timeout(1000) # Reducido a 1s para acelerar búsquedas masivas
                                
                                if not name or name == "Resultados":
                                    try:
                                        name = await page.locator('h1').last.inner_text()
                                    except: pass
                                
                                phone = "No tiene"
                                try:
                                    phone_loc = page.locator('button[data-item-id^="phone:tel:"]').first
                                    if await phone_loc.count() > 0:
                                        aria = await phone_loc.get_attribute("aria-label")
                                        if aria:
                                            phone = aria.replace("Teléfono: ", "").replace("Phone: ", "").strip()
                                except: pass
                                
                                has_web = False
                                try:
                                    web_loc = page.locator('a[data-item-id="authority"]').first
                                    if await web_loc.count() > 0:
                                        has_web = True
                                except: pass
                                
                                if phone == "No tiene":
                                    print(f"Saltando {name}, no tiene número de teléfono.")
                                    continue
                                    
                                # Limpiar teléfono para comparar
                                clean_phone = phone.replace(" ", "").replace("-", "").replace("+", "")
                                if clean_phone.startswith("0"): 
                                    clean_phone = "54" + clean_phone[1:]
                                if not clean_phone.startswith("54"): 
                                    clean_phone = "54" + clean_phone
                                    
                                if sent_phones and clean_phone in sent_phones:
                                    print(f"Saltando {name}, mensaje ya enviado anteriormente.")
                                    continue
                                
                                if name and name != "Resultados":
                                    local_data = {
                                        "name": name,
                                        "phone": phone,
                                        "has_web": has_web,
                                        "url": href
                                    }
                                    results.append(local_data)
                                    city_results += 1
                                    if on_result:
                                        on_result(local_data)
                                    print(f"Local extraído: {name} - {phone}")
                                    
                            except Exception as e:
                                print(f"Error procesando local: {e}")
                        
                        if not added_in_pass:
                            # Scroll down para cargar más
                            await feed.hover()
                            await page.mouse.wheel(0, 10000)
                            await page.wait_for_timeout(2000)
                            
                            items_after = await page.locator('a[href*="https://www.google.com/maps/place/"]').count()
                            if items_after <= len(visited):
                                break
                                
                except Exception as e:
                    print(f"Error en la ciudad {ciudad}: {e}")
                    
        except Exception as e:
            print("Error principal:", e)
        finally:
            await browser.close()
            
    return results
