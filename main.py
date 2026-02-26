import asyncio
import logging
from scrapers.crc import scrape_crc
from webhook_sender import send_plans

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# Tamaño del lote que se envía al webhook por vez
BATCH_SIZE = 100

async def main():
    log.info("🚀 Iniciando scraper CRC Colombia...")

    planes = await scrape_crc()  # Todas las páginas
    log.info(f"📦 Total planes descargados: {len(planes)}")

    if not planes:
        log.warning("⚠️ No se encontraron planes")
        return

    # Enviar en lotes de 100 para no saturar el webhook
    total_lotes = (len(planes) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(0, len(planes), BATCH_SIZE):
        lote = planes[i:i + BATCH_SIZE]
        lote_num = (i // BATCH_SIZE) + 1
        log.info(f"Enviando lote {lote_num}/{total_lotes} ({len(lote)} planes)...")
        await send_plans(lote)

    log.info("✅ Todos los planes enviados a Supabase correctamente")

if __name__ == "__main__":
    asyncio.run(main())