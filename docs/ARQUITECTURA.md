# Documentación Técnica — Scraper CRC Colombia
## ComparaTuPlan.com

---

## 1. ANÁLISIS DEL ORIGEN DE DATOS

### Resultado del análisis con DevTools / web_fetch

| Aspecto | Resultado |
|---|---|
| Tecnología frontend | Nuxt.js (Vue SSR) |
| Tipo de datos | API REST JSON pública |
| Renderizado JS requerido | ❌ NO — API directa |
| Autenticación | ❌ Ninguna |
| CSRF / Tokens | ❌ No requeridos |
| Rate limiting detectado | ⚠️ Suave (respeta concurrencia baja) |
| Paginación | page=1..N, 8 planes por página |

### Endpoint principal confirmado

```
GET https://comparador.crcom.gov.co/api/comparador/planes
```

**Parámetros:**
| Parámetro | Valor | Descripción |
|---|---|---|
| TipoUsuario | Ciudadano | Tipo de consulta |
| sort | ASC | Orden |
| page | 1..1807 | Página actual |

**Headers mínimos requeridos:**
```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
Referer: https://comparador.crcom.gov.co/
Accept: application/json
```

### Estructura de respuesta confirmada

```json
{
  "data": [...],     // Array de 8 planes por página
  "total": 14449,    // Total de planes
  "page": 1,
  "last_page": 1807  // Total de páginas
}
```

### Estructura de un plan

```json
{
  "id": "699440a83e8e5d87647a74b8",   // ID único MongoDB — CLAVE PRIMARIA
  "plan": {
    "nombre": "Bolsa de 50 SMS",
    "valor_iva": 1000,                 // Precio con IVA
    "modalidad": "PRE",               // PRE=prepago, POS=pospago
    "tipo": "Cerrado",
    "fecha": "2026-02-17",
    "url": "https://...",
    "tieneTelefonia": false,
    "tieneInternetFijo": false,
    "tieneTelevision": false,
    "tieneTelefoniaMovil": true,
    "tieneInternetMovil": false,
    "duracion": {
      "valor": 1,
      "unidad": "día",
      "valorMensual": 30000
    },
    "telMovil": {
      "unidad_medida": "MINUTOS",
      "um_mismo_proveedor": 0,
      "um_otro_proveedor": 0,
      "sms_mismo_proveedor": 50
    },
    "internetMovil": {
      "capacidad_datos": 500          // En MB
    }
  },
  "proveedor": {
    "nit": 900420122,
    "nombre": "VIRGIN"
  },
  "logo": "/logos/operadores/virgin.png",
  "updatedAt": "2026-02-17T05:07:19.000Z",
  "ubicacion": [{
    "departamento": { "name": "NACIONAL", "code": 0 },
    "municipio": { "name": "NACIONAL", "cod_dane": 0 }
  }],
  "tipoUsuario": "Ciudadano"
}
```

---

## 2. FLUJO DE EJECUCIÓN

```
main.py
  └── scrape_crc(max_pages=None)          # scrapers/crc.py
        ├── GET /api/comparador/planes?page=1  → obtiene last_page
        ├── asyncio.Semaphore(5)           # máx 5 requests simultáneos
        ├── GET pages 2..N (concurrente)
        └── normalizar(raw) por cada plan
              └── retorna lista de dicts

  └── send_plans(planes)                   # webhook_sender.py
        ├── preparar(p)                    # mapea campos CRC → Supabase
        ├── deduplica por id_crc
        └── POST /rest/v1/planes en lotes de 100
              └── on_conflict=id_crc (upsert)
```

---

## 3. TABLA SUPABASE — ESQUEMA

```sql
planes (
  id                    uuid PRIMARY KEY,
  id_crc                text UNIQUE,      -- ID original de la CRC
  operador              text NOT NULL,
  nombre                text NOT NULL,
  tipo                  text,             -- internet|movil|tv|paquete|otro
  modalidad             text,             -- prepago|pospago
  precio                numeric,          -- precio con IVA (por duración)
  precio_mensual        numeric,          -- valorMensual de la CRC
  duracion_valor        integer,
  duracion_unidad       text,             -- día|mes|año
  velocidad_mbps        numeric,          -- NULL en planes CRC (no expuesto)
  datos_gb              numeric,
  minutos               integer,
  canales_tv            integer,
  url_origen            text,
  fuente                text DEFAULT 'CRC',
  tiene_telefonia       boolean,
  tiene_internet_fijo   boolean,
  tiene_television      boolean,
  tiene_telefonia_movil boolean,
  tiene_internet_movil  boolean,
  activo                boolean DEFAULT true,
  fecha_actualizacion   timestamptz DEFAULT now()
)
```

---

## 4. FRECUENCIA RECOMENDADA

| Tarea | Frecuencia | Motivo |
|---|---|---|
| Scraping completo | 1x/día (7:00 AM) | CRC actualiza sus datos diariamente |
| Marcar inactivos | Después del scraping | Planes que desaparecen de la CRC |
| Health check | Cada 6h | Verificar que el endpoint responde |

---

## 5. POSIBLES CAMBIOS Y MONITOREO

### Señales de alerta
- `last_page` cae por debajo de 1700 → probable cambio en la API
- Respuesta 403/429 → rate limiting activado
- Cambio en estructura del JSON → campo `data` ausente

### Recomendaciones
- Guardar `last_page` de cada ejecución en `scraping_logs`
- Alertar por WhatsApp si el total de planes baja > 10%
- Mantener `debug_planes.json` como muestra de referencia

---

## 6. TÉRMINOS DE USO

La CRC publica estos datos como **información pública sin restricciones**:
- El aviso legal de la página indica que es una herramienta para *"informar al público"*
- No requiere autenticación ni registro
- Se respeta con: semáforo de 5 conexiones, 1 ejecución diaria
