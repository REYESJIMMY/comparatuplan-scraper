"""
Muestra la estructura completa del primer plan.
Ejecuta: python debug_crc4.py
"""
import asyncio
import json
import aiohttp

URL = "https://comparador.crcom.gov.co/api/comparador/planes"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://comparador.crcom.gov.co/",
    "Accept": "application/json",
}

async def debug():
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(URL, params={"TipoUsuario": "Ciudadano", "sort": "ASC", "page": 1}) as resp:
            data = await resp.json(content_type=None)

    primer_plan = data["data"][0]
    print("=== ESTRUCTURA COMPLETA DEL PRIMER PLAN ===")
    print(json.dumps(primer_plan, ensure_ascii=False, indent=2))

asyncio.run(debug())