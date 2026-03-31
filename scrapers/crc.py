"""
scrapers/crc.py — ComparaTuPlan.com
====================================
Scraper oficial del comparador de la CRC Colombia.
Endpoint: https://comparador.crcom.gov.co/api/comparador/planes

Análisis previo confirmó:
  - API REST JSON pública, sin autenticación ni tokens
  - No requiere renderizado JS (no se usa Playwright)
  - Paginación: page=1..N, 8 planes/página (~1807 páginas, ~14.449 planes)
  - ID único por plan: campo "id" (MongoDB ObjectId)
  - Actualización diaria por parte de la CRC

Uso:
  from scrapers.crc import scrape_crc
  planes = await scrape_crc()           # todas las páginas
  planes = await scrape_crc(max_pages=5)  # solo 5 páginas (prueba)
"""

import asyncio
import logging
import aiohttp

log = logging.getLogger(__name__)

# ── Configuración ──────────────────────────────────────────────────────────────
BASE_URL   = "https://comparador.crcom.gov.co/api/comparador/planes"
PAGE_SIZE  = 8       # Planes por página (fijo en la API de la CRC)
SEMAPHORE  = 5       # Máx conexiones simultáneas — respetar servidores CRC
TIMEOUT_S  = 30      # Segundos por request

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    "https://comparador.crcom.gov.co/",
    "Accept":     "application/json",
}

# ── Mapeo de tipo resumido ──────────────────────────────────────────────────────
def _tipo_resumen(p: dict) -> str:
    """
    Clasifica el plan según sus flags de servicio.
    Resultado mapeado al check constraint de Supabase:
      internet | movil | tv | paquete | otro
    """
    tiene_fijo   = p.get("tieneInternetFijo", False)
    tiene_tv     = p.get("tieneTelevision", False)
    tiene_tel    = p.get("tieneTelefonia", False)
    tiene_movil  = p.get("tieneTelefoniaMovil", False) or p.get("tieneInternetMovil", False)

    if tiene_movil:
        return "movil"
    if tiene_fijo and tiene_tv and tiene_tel:
        return "paquete"        # Triple play
    if tiene_fijo and tiene_tv:
        return "paquete"        # Dúo internet+TV
    if tiene_fijo:
        return "internet"
    if tiene_tv:
        return "tv"
    if tiene_tel:
        return "otro"           # Solo telefonía fija
    return "otro"


def _get_operador(raw: dict) -> str:
    """Extrae y normaliza el nombre del operador."""
    proveedor = raw.get("proveedor")
    if isinstance(proveedor, dict):
        return proveedor.get("nombre", "Desconocido").strip().title()
    if isinstance(proveedor, str):
        return proveedor.strip().title()
    return "Desconocido"


def normalizar(raw: dict) -> dict:
    """
    Transforma un plan raw de la API de la CRC al esquema
    interno de ComparaTuPlan (tabla `planes` en Supabase).

    Campos importantes:
      - id_crc        : ID único original de la CRC (MongoDB ObjectId)
      - precio        : valor_iva (precio con IVA por duración del plan)
      - precio_mensual: duracion.valorMensual (precio mensual equivalente)
      - datos_gb      : internetMovil.capacidad_datos (en MB → convertir si necesario)
      - minutos       : telMovil.um_mismo_proveedor (-1 = ilimitado)
    """
    p   = raw.get("plan", raw)
    dur = p.get("duracion") or {}

    # Internet móvil
    inet_movil  = p.get("internetMovil") or {}
    datos_mb    = inet_movil.get("capacidad_datos")  # en MB
    datos_gb    = round(datos_mb / 1024, 2) if datos_mb and datos_mb > 0 else None
    datos_gb    = -1 if datos_mb == -1 else datos_gb  # -1 = ilimitado

    # Telefonía móvil
    tel_movil   = p.get("telMovil") or {}
    minutos     = tel_movil.get("um_mismo_proveedor")
    if minutos is not None and minutos < 0:
        minutos = -1  # -1 = ilimitado

    return {
        # ── Identificación ──────────────────────────────
        "id_crc":        raw.get("id"),           # ID único CRC — clave primaria
        "nombre":        p.get("nombre"),
        "operador":      _get_operador(raw),
        "url_plan":      p.get("url"),
        "fecha":         p.get("fecha"),
        "fuente":        "CRC",

        # ── Precio ──────────────────────────────────────
        "precio":         p.get("valor_iva", 0),  # precio con IVA (por duración)
        "precio_mensual": dur.get("valorMensual"), # equivalente mensual

        # ── Duración ────────────────────────────────────
        "duracion_valor":  dur.get("valor"),
        "duracion_unidad": dur.get("unidad"),      # día | mes | año

        # ── Clasificación ────────────────────────────────
        "modalidad":  p.get("modalidad"),          # PRE | POS
        "tipo_plan":  p.get("tipo"),               # Cerrado | Abierto
        "tipo":       _tipo_resumen(p),            # internet|movil|tv|paquete|otro

        # ── Características técnicas ─────────────────────
        "datos_gb":   datos_gb,                    # GB (-1 = ilimitado, None = N/A)
        "minutos":    minutos,                     # min (-1 = ilimitado, None = N/A)
        # velocidad_mbps: no expuesta en la API de la CRC → None

        # ── Flags de servicio ────────────────────────────
        "tiene_telefonia":       p.get("tieneTelefonia", False),
        "tiene_internet_fijo":   p.get("tieneInternetFijo", False),
        "tiene_television":      p.get("tieneTelevision", False),
        "tiene_telefonia_movil": p.get("tieneTelefoniaMovil", False),
        "tiene_internet_movil":  p.get("tieneInternetMovil", False),
    }


# ── Fetch de una página ────────────────────────────────────────────────────────
async def fetch_page(
    session: aiohttp.ClientSession,
    page: int
) -> tuple[list, int]:
    """
    Descarga una página de la API CRC.
    Retorna (lista_de_planes_raw, last_page).
    """
    params = {
        "TipoUsuario": "Ciudadano",
        "sort":        "ASC",
        "page":        page,
    }
    async with session.get(
        BASE_URL,
        params=params,
        timeout=aiohttp.ClientTimeout(total=TIMEOUT_S)
    ) as resp:
        resp.raise_for_status()
        data = await resp.json(content_type=None)
    return data.get("data", []), data.get("last_page", 1)


# ── Scraper principal ──────────────────────────────────────────────────────────
async def scrape_crc(max_pages: int = None) -> list[dict]:
    """
    Descarga todos los planes del comparador CRC.

    Args:
        max_pages: Límite de páginas (None = todas ~1807).
                   Usar max_pages=5 para pruebas rápidas.

    Returns:
        Lista de dicts normalizados listos para Supabase.
    """
    all_plans: list[dict] = []

    async with aiohttp.ClientSession(headers=HEADERS) as session:

        # ── Página 1: obtener total de páginas ──────────
        raw_p1, last_page = await fetch_page(session, 1)
        all_plans.extend([normalizar(r) for r in raw_p1])
        log.info(f"Página 1/{last_page} — {len(raw_p1)} planes obtenidos")

        limit = min(last_page, max_pages) if max_pages else last_page

        if limit <= 1:
            log.info(f"✅ Total: {len(all_plans)} planes")
            return all_plans

        # ── Páginas 2..N con semáforo de concurrencia ───
        sem = asyncio.Semaphore(SEMAPHORE)

        async def fetch_safe(pg: int) -> list[dict]:
            async with sem:
                try:
                    rows, _ = await fetch_page(session, pg)
                    return [normalizar(r) for r in rows]
                except aiohttp.ClientResponseError as e:
                    log.warning(f"HTTP {e.status} en página {pg} — reintentando...")
                    await asyncio.sleep(2)
                    try:
                        rows, _ = await fetch_page(session, pg)
                        return [normalizar(r) for r in rows]
                    except Exception as e2:
                        log.error(f"Error irrecuperable página {pg}: {e2}")
                        return []
                except Exception as e:
                    log.warning(f"Error página {pg}: {e}")
                    return []

        tasks   = [fetch_safe(pg) for pg in range(2, limit + 1)]
        results = await asyncio.gather(*tasks)

        for i, batch in enumerate(results, start=2):
            all_plans.extend(batch)
            if i % 200 == 0:
                log.info(f"Progreso: {i}/{limit} páginas — {len(all_plans)} planes")

    log.info(f"✅ Total planes descargados: {len(all_plans)}")
    return all_plans


# ── Test local ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    planes = asyncio.run(scrape_crc(max_pages=3))

    print(f"\n✅ Planes obtenidos: {len(planes)}")
    print(f"\n── Ejemplo plan #1 ──")
    print(json.dumps(planes[0], ensure_ascii=False, indent=2))
    print(f"\n── Tipos encontrados ──")
    from collections import Counter
    tipos = Counter(p["tipo"] for p in planes)
    for tipo, count in tipos.most_common():
        print(f"  {tipo}: {count}")