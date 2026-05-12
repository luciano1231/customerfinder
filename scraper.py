from playwright.async_api import async_playwright
import urllib.parse
import asyncio

async def run_scraper(rubro, ciudad, limit=10):
    query = f"{rubro} en {ciudad}"
    encoded = urllib.parse.quote(query)
    url = f"https://www.google.com/maps/search/{encoded}"
    
    results = []
    
    async with async_playwright() as p:
        # headless=True para que no abra la ventana visiblemente e interrumpa
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(locale="es-AR")
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Esperar a que cargue el panel de resultados
            try:
                feed = page.locator('div[role="feed"]')
                await feed.wait_for(timeout=15000)
            except:
                print("No se encontró el contenedor de resultados.")
                return results

            visited = set()
            
            while len(results) < limit:
                items = await page.locator('a[href*="https://www.google.com/maps/place/"]').all()
                added_in_pass = False
                
                for item in items:
                    if len(results) >= limit: break
                    
                    href = await item.get_attribute("href")
                    if not href or href in visited: continue
                    visited.add(href)
                    added_in_pass = True
                    
                    try:
                        # Extraer nombre directo del atributo aria-label (mucho más preciso)
                        name = await item.get_attribute("aria-label")
                        
                        # Clic en el local para ver detalles (teléfono y web)
                        await item.click()
                        await page.wait_for_timeout(2500) # Tiempo de carga del panel
                        
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
                        
                        if name and name != "Resultados":
                            results.append({
                                "name": name,
                                "phone": phone,
                                "has_web": has_web,
                                "url": href
                            })
                            print(f"Local extraído: {name}")
                            
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
            print("Error principal:", e)
        finally:
            await browser.close()
            
    return results
