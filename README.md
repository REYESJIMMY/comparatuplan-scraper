# comparatuplan-scraper

Scraper oficial para sincronizar el comparador de planes de la CRC Colombia
con la base de datos Supabase de **ComparaTuPlan.com**.

## Análisis técnico previo

| Aspecto | Resultado |
|---|---|
| Fuente | https://comparador.crcom.gov.co |
| Tipo | API REST JSON pública (sin auth) |
| Renderizado JS | ❌ No requerido |
| Total planes | ~14.449 |
| Páginas | ~1.807 (8 planes/página) |
| Clave única | Campo `id` (MongoDB ObjectId) |
| Actualización CRC | Diaria (hora específica) |

## Instalación

```bash
# 1. Clonar
git clone https://github.com/REYESJIMMY/comparatuplan-scraper
cd comparatuplan-scraper

# 2. Entorno virtual
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 3. Dependencias
pip install aiohttp python-dotenv

# 4. Variables de entorno
copy .env.example .env
# Editar .env con tus claves de Supabase
```

## Uso

```bash
# Scraping completo (~14.000 planes, ~2 min)
python main.py

# Test rápido (3 páginas = 24 planes)
python main.py --test

# Número de páginas personalizado
python main.py --pages 100
```

## Automatización (GitHub Actions)

El archivo `.github/workflows/scraper_diario.yml` ejecuta el scraper
todos los días a las **7:10 AM hora Colombia**.

Configurar en GitHub → Settings → Secrets:
- `SUPABASE_WEBHOOK_URL`
- `SUPABASE_SERVICE_KEY`
- `SUPABASE_ANON_KEY`
- `WEBHOOK_SECRET`

## Estructura

```
comparatuplan-scraper/
├── scrapers/
│   └── crc.py           # Scraper CRC — fetch + normalización
├── docs/
│   └── ARQUITECTURA.md  # Documentación técnica completa
├── main.py              # Orquestador (CLI)
├── webhook_sender.py    # Envío a Supabase REST API
├── .env.example         # Variables de entorno (plantilla)
└── .github/
    └── workflows/
        └── scraper_diario.yml  # GitHub Actions
```

## Salida de datos normalizada

```python
{
  "id_crc":        "699440a83e8e5d87647a74b8",  # ID CRC (clave única)
  "operador":      "Virgin",
  "nombre":        "Bolsa de 50 SMS",
  "tipo":          "movil",           # internet|movil|tv|paquete|otro
  "modalidad":     "prepago",         # prepago|pospago
  "precio":        1000,              # precio con IVA (por duración)
  "precio_mensual": 30000,            # equivalente mensual
  "duracion_valor": 1,
  "duracion_unidad": "día",
  "datos_gb":      None,              # MB→GB (None si no aplica)
  "minutos":       None,              # -1 = ilimitado
  "tiene_telefonia_movil": True,
  "tiene_internet_movil":  False,
  # ... más flags de servicio
}
```

## Monitoreo

- Revisar `scraping_logs` en Supabase después de cada ejecución
- Si `total_planes` baja más del 10% → revisar endpoint CRC
- GitHub Actions notifica por email si el workflow falla
