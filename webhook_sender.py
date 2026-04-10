"""
webhook_sender.py — ComparaTuPlan.com
=======================================
Envía los planes normalizados directamente a Supabase REST API.
Usa upsert con on_conflict=id_crc para actualización incremental.

Estrategia:
  - Deduplica por id_crc dentro de cada lote (evita duplicados del scraper)
  - Lotes de 100 planes por request (equilibrio velocidad/estabilidad)
  - Service Key para bypass de RLS
  - on_conflict=id_crc: INSERT si nuevo, UPDATE si ya existe
"""

import json
import logging
import os
import time

import aiohttp
from dotenv import load_dotenv

load_dotenv(override=False)

# ── Configuración ──────────────────────────────────────────────────────────────
# Lee SUPABASE_URL directamente (sin hacer replace frágil sobre WEBHOOK_URL)
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY  = os.getenv("SUPABASE_SERVICE_KEY", "")
BATCH_SIZE   = 100

log = logging.getLogger(__name__)

# Mapeo modalidad CRC → Supabase
MODALIDAD_MAP = {
    "PRE":     "prepago",
    "POS":     "pospago",
    "PREPAGO": "prepago",
    "POSPAGO": "pospago",
}

# Mapeo tipo a valores permitidos por check constraint de Supabase
TIPO_MAP = {
    "internet_hogar": "internet",
    "duo_internet_tv": "paquete",
    "triple_play":    "paquete",
    "telefonia_fija": "otro",
}

TIPOS_VALIDOS = {"internet", "movil", "tv", "paquete", "otro",
                 "internet_hogar", "triple_play", "duo_internet_tv",
                 "telefonia_fija"}

HEADERS = {
    "Content-Type":  "application/json",
    "Authorization": f"Bearer {SERVICE_KEY}",
    "apikey":        SERVICE_KEY,
    "Prefer":        "resolution=merge-duplicates,return=minimal",
}


def preparar(p: dict) -> dict:
    """
    Adapta un plan normalizado por crc.py al esquema exacto
    de la tabla `planes` en Supabase.
    """
    modalidad_raw = (p.get("modalidad") or "").upper()
    tipo_raw      = p.get("tipo", "otro")
    tipo          = TIPO_MAP.get(tipo_raw, tipo_raw)

    if tipo not in TIPOS_VALIDOS:
        tipo = "otro"

    return {
        "id_crc":                p.get("id_crc"),
        "operador":              p.get("operador", "Desconocido"),
        "nombre":                p.get("nombre", "Sin nombre"),
        "fuente":                p.get("fuente", "CRC"),
        "url_origen":            p.get("url_plan"),
        "tipo":                  tipo,
        "modalidad":             MODALIDAD_MAP.get(modalidad_raw, modalidad_raw.lower() or None),
        "precio":                p.get("precio", 0),
        "precio_mensual":        p.get("precio_mensual"),
        "duracion_valor":        p.get("duracion_valor"),
        "duracion_unidad":       p.get("duracion_unidad"),
        "velocidad_mbps":        p.get("velocidad_mbps"),
        "datos_gb":              p.get("datos_gb"),
        "minutos":               p.get("minutos"),
        "canales_tv":            p.get("canales_tv"),
        "tiene_telefonia":       p.get("tiene_telefonia", False),
        "tiene_internet_fijo":   p.get("tiene_internet_fijo", False),
        "tiene_television":      p.get("tiene_television", False),
        "tiene_telefonia_movil": p.get("tiene_telefonia_movil", False),
        "tiene_internet_movil":  p.get("tiene_internet_movil", False),
        "activo":                True,
    }


async def _enviar_lote(
    session: aiohttp.ClientSession,
    lote: list[dict],
    lote_num: int,
    total_lotes: int
) -> int:
    """Envía un lote a Supabase REST API con upsert."""
    url  = f"{SUPABASE_URL}/rest/v1/planes?on_conflict=id_crc"
    body = json.dumps(lote, ensure_ascii=False, default=str)

    async with session.post(
        url,
        data=body.encode("utf-8"),
        headers=HEADERS,
        timeout=aiohttp.ClientTimeout(total=30),
    ) as resp:
        text = await resp.text()
        if resp.status not in (200, 201):
            raise Exception(f"Supabase {resp.status}: {text[:300]}")
        log.info(f"  Lote {lote_num}/{total_lotes} → {len(lote)} planes ✅")
        return len(lote)


async def send_plans(planes: list[dict], fuente: str = "CRC") -> None:
    """
    Envía todos los planes a Supabase en lotes de BATCH_SIZE.
    Hace upsert por id_crc (INSERT nuevo / UPDATE existente).
    """
    if not SUPABASE_URL:
        raise ValueError("❌ Falta SUPABASE_URL en las variables de entorno")
    if not SERVICE_KEY:
        raise ValueError("❌ Falta SUPABASE_SERVICE_KEY en las variables de entorno")

    t0 = time.time()

    # Preparar y deduplicar por id_crc
    preparados = [preparar(p) for p in planes]
    seen: set  = set()
    unicos: list[dict] = []

    for p in preparados:
        key = p.get("id_crc")
        if key:
            if key not in seen:
                seen.add(key)
                unicos.append(p)
        else:
            unicos.append(p)

    total       = len(unicos)
    total_lotes = (total + BATCH_SIZE - 1) // BATCH_SIZE
    total_ins   = 0

    log.info(f"🚀 Enviando {total} planes únicos en {total_lotes} lotes a Supabase...")

    async with aiohttp.ClientSession() as session:
        for i in range(0, total, BATCH_SIZE):
            lote_num = (i // BATCH_SIZE) + 1
            lote     = unicos[i:i + BATCH_SIZE]
            total_ins += await _enviar_lote(session, lote, lote_num, total_lotes)

    duracion = round(time.time() - t0, 1)
    log.info(f"✅ Completado en {duracion}s — {total_ins} planes enviados a Supabase")


# ── Test local ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    plan_test = [{
        "id_crc": "test-local-001",
        "operador": "Test Operador",
        "nombre": "Plan Test Local",
        "tipo": "internet",
        "modalidad": "pospago",
        "precio": 89900,
        "precio_mensual": 89900,
        "fuente": "CRC",
    }]

    asyncio.run(send_plans(plan_test))
