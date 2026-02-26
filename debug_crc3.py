"""
Consulta directa al API real de la CRC.
Ejecuta: python debug_crc3.py
"""
import asyncio
import json
import aiohttp

URL = "https://comparador.crcom.gov.co/api/comparador/planes"

PARAMS = {
    "TipoUsuario": "Ciudadano",
    "sort": "ASC",
    "page": 1,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://comparador.crcom.gov.co/",
    "Accept": "application/json",
}

async def debug():
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(URL, params=PARAMS) as resp:
            print(f"Status: {resp.status}")
            print(f"Content-Type: {resp.content_type}\n")

            data = await resp.json(content_type=None)

            # Guarda el JSON completo
            with open("debug_planes.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print("✅ JSON guardado en debug_planes.json")
            print(f"\n--- CLAVES PRINCIPALES ---")
            if isinstance(data, dict):
                for k, v in data.items():
                    print(f"  {k}: {type(v).__name__} = {str(v)[:120]}")
            elif isinstance(data, list):
                print(f"Lista de {len(data)} elementos")
                print(json.dumps(data[0], ensure_ascii=False, indent=2)[:800])

asyncio.run(debug())