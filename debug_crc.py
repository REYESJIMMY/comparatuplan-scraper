"""
Ejecuta: python debug_crc.py
Guarda el HTML real para inspeccionar los selectores correctos.
"""
import asyncio
from playwright.async_api import async_playwright

URL = "https://comparador.crcom.gov.co/api/paginas/claro"

async def debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"Cargando {URL}...")
        await page.goto(URL, timeout=60000, wait_until="networkidle")
        await page.wait_for_timeout(5000)  # Espera 5s para JS

        html = await page.content()
        await browser.close()

    # Guarda el HTML completo
    with open("debug_claro.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ HTML guardado en debug_claro.html ({len(html)} caracteres)")

    # Muestra un fragmento
    print("\n--- FRAGMENTO DEL HTML ---")
    print(html[2000:4000])

asyncio.run(debug())