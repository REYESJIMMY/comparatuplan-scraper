"""
Intercepta todas las llamadas de red del sitio CRC
para encontrar el endpoint real de los datos.
Ejecuta: python debug_crc2.py
"""
import asyncio
from playwright.async_api import async_playwright

URL = "https://comparador.crcom.gov.co/"

async def debug():
    llamadas = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Intercepta todas las peticiones de red
        def on_request(request):
            if any(x in request.url for x in ["api", "json", "data", "planes", "tarifas"]):
                llamadas.append(f"REQUEST  {request.method} {request.url}")

        def on_response(response):
            if any(x in response.url for x in ["api", "json", "data", "planes", "tarifas"]):
                llamadas.append(f"RESPONSE {response.status} {response.url}")

        page.on("request",  on_request)
        page.on("response", on_response)

        print(f"Cargando {URL} e interceptando red...")
        await page.goto(URL, timeout=60000, wait_until="networkidle")
        await page.wait_for_timeout(5000)

        await browser.close()

    print(f"\n✅ Llamadas de red encontradas: {len(llamadas)}\n")
    for l in llamadas:
        print(l)

asyncio.run(debug())