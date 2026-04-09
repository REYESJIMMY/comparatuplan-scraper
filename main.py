import asyncio
import logging
import sys

from scrapers.crc import scrape_crc
from webhook_sender import send_plans

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

BATCH_SIZE = 100


async def main():
    # Detectar modo test: python main.py --test
    modo_test = "--test" in sys.argv
    max_pages = 3 if modo_test else None

    if modo_test:
        log.info("🧪 Modo TEST — solo 3 páginas (~24 planes)")
    else:
        log.info("🚀 Iniciando scraper CRC Colombia — modo completo...")

    planes = await scrape_crc(max_pages=max_pages)
    log.info(f"📦 Total planes descargados: {len(planes)}")

    if not planes:
        log.warning("⚠️ No se encontraron planes")
        sys.exit(1)

    await send_plans(planes)
    log.info("✅ Todos los planes enviados a Supabase correctamente")


if __name__ == "__main__":
    asyncio.run(main())
