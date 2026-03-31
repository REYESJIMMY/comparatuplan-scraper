"""
main.py — ComparaTuPlan.com
============================
Orquestador del scraper CRC Colombia.
Descarga los ~14.000 planes y los sincroniza con Supabase.

Uso:
  python main.py                    # Scraping completo
  python main.py --test             # Solo 3 páginas (24 planes)
  python main.py --pages 50         # Límite personalizado

Programación sugerida (cron / GitHub Actions):
  0 7 * * *  cd /path/to/scraper && python main.py
"""

import asyncio
import logging
import sys
import time

from scrapers.crc import scrape_crc
from webhook_sender import send_plans

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)


async def main(max_pages: int = None) -> None:
    t0 = time.time()
    modo = f"TEST ({max_pages} páginas)" if max_pages else "COMPLETO"
    log.info(f"🚀 Iniciando scraper CRC Colombia — Modo: {modo}")

    # ── 1. Descargar planes ───────────────────────────────────────────────────
    try:
        planes = await scrape_crc(max_pages=max_pages)
    except Exception as e:
        log.error(f"❌ Error en scraping: {e}")
        raise

    log.info(f"📦 Total planes descargados: {len(planes)}")

    if not planes:
        log.warning("⚠️ No se encontraron planes — abortando")
        return

    # ── 2. Enviar a Supabase ──────────────────────────────────────────────────
    try:
        await send_plans(planes)
    except Exception as e:
        log.error(f"❌ Error enviando a Supabase: {e}")
        raise

    duracion = round(time.time() - t0, 1)
    log.info(f"✅ Pipeline completado en {duracion}s — {len(planes)} planes sincronizados")


if __name__ == "__main__":
    # Parsear argumentos simples
    max_pages = None

    if "--test" in sys.argv:
        max_pages = 3
        print("🔧 Modo TEST: solo 3 páginas (24 planes)")

    elif "--pages" in sys.argv:
        idx = sys.argv.index("--pages")
        if idx + 1 < len(sys.argv):
            max_pages = int(sys.argv[idx + 1])
            print(f"🔧 Modo PARCIAL: {max_pages} páginas")

    asyncio.run(main(max_pages=max_pages))