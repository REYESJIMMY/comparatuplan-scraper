"""
Scraper oficial CRC — comparador.crcom.gov.co
Consume la API JSON directamente, sin Playwright.
14.449 planes · 1.807 páginas · 8 planes por página
"""

import asyncio
import logging
import aiohttp

log = logging.getLogger(__name__)

BASE_URL = "https://comparador.crcom.gov.co/api/comparador/planes"
PAGE_SIZE = 8

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    "https://comparador.crcom.gov.co/",
    "Accept":     "application/json",
}

# ──────────────────────────────────────────────
# NORMALIZAR UN PLAN
# ──────────────────────────────────────────────
def normalizar(raw: dict) -> dict:
    p = raw.get("plan", raw)
    dur = p.get("duracion") or {}

    return {
        # Identificación
        "nombre":        p.get("nombre"),
        "operador":      _get_operador(raw),
        "url_plan":      p.get("url"),
        "fecha":         p.get("fecha"),
        "fuente":        "CRC",

        # Precio
        "precio":        p.get("valor_iva", 0),
        "precio_mensual": dur.get("valorMensual"),

        # Duración
        "duracion_valor": dur.get("valor"),
        "duracion_unidad": dur.get("unidad"),

        # Tipo de servicio
        "modalidad":     p.get("modalidad"),          # PRE / POS
        "tipo_plan":     p.get("tipo"),               # Cerrado / Abierto
        "tiene_telefonia":       p.get("tieneTelefonia", False),
        "tiene_internet_fijo":   p.get("tieneInternetFijo", False),
        "tiene_television":      p.get("tieneTelevision", False),
        "tiene_telefonia_movil": p.get("tieneTelefoniaMovil", False),
        "tiene_internet_movil":  p.get("tieneInternetMovil", False),

        # Tipo resumen
        "tipo": _tipo_resumen(p),
    }

def _get_operador(raw: dict) -> str:
    proveedor = raw.get("proveedor")
    if isinstance(proveedor, dict):
        return proveedor.get("nombre", "Desconocido").strip().title()
    if isinstance(proveedor, str):
        return proveedor.strip().title()
    return "Desconocido"

def _tipo_resumen(p: dict) -> str:
    if p.get("tieneTelefoniaMovil") or p.get("tieneInternetMovil"):
        return "movil"
    if p.get("tieneInternetFijo") and p.get("tieneTelevision") and p.get("tieneTelefonia"):
        return "triple_play"
    if p.get("tieneInternetFijo") and p.get("tieneTelevision"):
        return "duo_internet_tv"
    if p.get("tieneInternetFijo"):
        return "internet_hogar"
    if p.get("tieneTelevision"):
        return "television"
    if p.get("tieneTelefonia"):
        return "telefonia_fija"
    return "otro"


# ──────────────────────────────────────────────
# FETCH DE UNA PÁGINA
# ──────────────────────────────────────────────
async def fetch_page(session: aiohttp.ClientSession, page: int) -> tuple[list, int]:
    params = {"TipoUsuario": "Ciudadano", "sort": "ASC", "page": page}
    async with session.get(BASE_URL, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        resp.raise_for_status()
        data = await resp.json(content_type=None)
    return data.get("data", []), data.get("last_page", 1)


# ──────────────────────────────────────────────
# SCRAPER PRINCIPAL
# ──────────────────────────────────────────────
async def scrape_crc(max_pages: int = None) -> list[dict]:
    """
    max_pages: límite de páginas (None = todas).
    Cada página tiene 8 planes.
    """
    all_plans = []

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # Página 1 para saber el total
        raw, last_page = await fetch_page(session, 1)
        all_plans.extend([normalizar(r) for r in raw])
        log.info(f"Página 1/{last_page} — {len(raw)} planes")

        limit = min(last_page, max_pages) if max_pages else last_page

        # Páginas 2 en adelante (concurrencia de 5)
        sem = asyncio.Semaphore(5)

        async def fetch_safe(pg):
            async with sem:
                try:
                    rows, _ = await fetch_page(session, pg)
                    return [normalizar(r) for r in rows]
                except Exception as e:
                    log.warning(f"Error página {pg}: {e}")
                    return []

        tasks = [fetch_safe(pg) for pg in range(2, limit + 1)]
        results = await asyncio.gather(*tasks)

        for i, batch in enumerate(results, start=2):
            all_plans.extend(batch)
            if i % 100 == 0:
                log.info(f"Progreso: página {i}/{limit} — {len(all_plans)} planes")

    log.info(f"✅ Total planes descargados: {len(all_plans)}")
    return all_plans


# ──────────────────────────────────────────────
# TEST LOCAL
# ──────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    # Prueba con solo 3 páginas (24 planes)
    planes = asyncio.run(scrape_crc(max_pages=2))

    print(f"\n✅ Planes obtenidos: {len(planes)}")
    for p in planes[:2]:
        print(p)