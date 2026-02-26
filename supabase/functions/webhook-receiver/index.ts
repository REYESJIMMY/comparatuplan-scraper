// supabase/functions/webhook-receiver/index.ts
import { serve }        from "https://deno.land/std@0.177.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { crypto }       from "https://deno.land/std@0.177.0/crypto/mod.ts";

const WEBHOOK_SECRET   = Deno.env.get("WEBHOOK_SECRET")!;
const SUPABASE_URL     = Deno.env.get("DB_URL")!;
const SUPABASE_SVC_KEY = Deno.env.get("DB_SERVICE_KEY")!;
const META_TOKEN       = Deno.env.get("META_WA_TOKEN") ?? "";
const META_PHONE_ID    = Deno.env.get("META_PHONE_ID") ?? "";
const ADMIN_NUMBERS    = (Deno.env.get("WA_ADMIN_TO") ?? "").split(",").filter(Boolean);

const sb = createClient(SUPABASE_URL, SUPABASE_SVC_KEY);

// ═══════════════════════════════════════════════════════
// WHATSAPP HELPER
// ═══════════════════════════════════════════════════════
async function sendWhatsApp(to: string, message: string): Promise<boolean> {
  if (!META_TOKEN || !META_PHONE_ID) return false;
  try {
    const r = await fetch(
      `https://graph.facebook.com/v19.0/${META_PHONE_ID}/messages`,
      {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${META_TOKEN}`,
          "Content-Type":  "application/json",
        },
        body: JSON.stringify({
          messaging_product: "whatsapp",
          to,
          type: "text",
          text: { body: message },
        }),
      },
    );
    return r.ok;
  } catch (e) {
    console.error("WA send error:", e);
    return false;
  }
}

async function broadcastWA(numbers: string[], message: string) {
  if (!numbers.length || !META_TOKEN) return;
  await Promise.all(numbers.map(n => sendWhatsApp(n, message)));
}

// ═══════════════════════════════════════════════════════
// MENSAJES WHATSAPP
// ═══════════════════════════════════════════════════════
const msgs = {
  scrapingDone: (r: Record<string, unknown>) => {
    const fuentes = (r.fuentes as {fuente:string;planes:number;error?:string}[]) ?? [];
    const errores = fuentes.filter(f => f.error).map(f => f.fuente);
    const cambios = r.cambios as {bajas:number;subidas:number;nuevos:number} | undefined;
    const now     = new Date().toLocaleString("es-CO", { timeZone: "America/Bogota" });
    return (
      `🤖 *ComparaTuPlan — Reporte Diario*\n` +
      `${"─".repeat(30)}\n` +
      `📅 ${now}\n` +
      `✅ Planes guardados: *${r.total_ok}*\n` +
      `⏱️ Duración: ${r.duracion_s}s\n` +
      (errores.length ? `❌ Errores: ${errores.join(", ")}\n` : ``) +
      (cambios
        ? `\n📊 *Cambios:*\n🔽 Bajas: *${cambios.bajas}*\n🔺 Subidas: *${cambios.subidas}*\n🆕 Nuevos: *${cambios.nuevos}*\n`
        : ``) +
      `\n_Próxima actualización: mañana 7:00 AM_`
    );
  },

  scrapingError: (fuente: string, error: string) =>
    `🚨 *ALERTA — Scraping Fallido*\n` +
    `${"─".repeat(30)}\n` +
    `🔴 Fuente: *${fuente}*\n` +
    `❌ ${error.slice(0, 250)}\n` +
    `⏰ ${new Date().toLocaleString("es-CO", { timeZone: "America/Bogota" })}\n\n` +
    `_Revisar GitHub Actions._`,

  priceDrop: (plan: Record<string, unknown>) => {
    const diff = (plan.precio_anterior as number) - (plan.precio_nuevo as number);
    const pct  = Math.round(diff / (plan.precio_anterior as number) * 100);
    return (
      `🎉 *¡Precio bajó!*\n` +
      `${"─".repeat(30)}\n` +
      `📶 *${plan.operador} — ${plan.nombre}*\n\n` +
      `💸 Antes: $${(plan.precio_anterior as number).toLocaleString("es-CO")}\n` +
      `✅ Ahora: *$${(plan.precio_nuevo as number).toLocaleString("es-CO")}/mes*\n` +
      `🔽 Ahorro: *$${diff.toLocaleString("es-CO")} (${pct}% menos)*\n\n` +
      `👉 Contratar: wa.me/573057876992`
    );
  },

  newPlan: (plan: Record<string, unknown>) =>
    `🆕 *Nuevo Plan Detectado*\n` +
    `${"─".repeat(30)}\n` +
    `📶 *${plan.operador} — ${plan.nombre}*\n` +
    `💰 $${(plan.precio as number).toLocaleString("es-CO")}/mes\n` +
    `⚡ ${plan.velocidad_mbps ?? 0} Mbps\n` +
    `🏷️ Tipo: ${plan.tipo}\n` +
    `⏰ ${new Date().toLocaleString("es-CO", { timeZone: "America/Bogota" })}`,
};

// ═══════════════════════════════════════════════════════
// VERIFICAR FIRMA HMAC-SHA256
// ═══════════════════════════════════════════════════════
async function verifySignature(body: string, sig: string, ts: string): Promise<boolean> {
  if (Math.abs(Date.now() / 1000 - parseInt(ts)) > 300) return false;
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(WEBHOOK_SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const buf      = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(body));
  const expected = "sha256=" + Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, "0")).join("");
  return expected === sig;
}

// ═══════════════════════════════════════════════════════
// HANDLERS
// ═══════════════════════════════════════════════════════
async function handleBatch(data: Record<string, unknown>) {
  const planes = data.planes as Record<string, unknown>[];
  if (!planes?.length) return { ok: 0 };
  const { error } = await sb.rpc("upsert_planes", { planes_json: planes });
  if (error) throw new Error(error.message);
  console.log(`✅ Lote ${data.lote} (${data.fuente}): ${planes.length} planes`);
  return { ok: planes.length };
}

async function handleDone(data: Record<string, unknown>) {
  const fuentes = (data.fuentes as {fuente:string;planes:number;error?:string}[]) ?? [];
  for (const f of fuentes) {
    await sb.from("scraping_logs").insert({
      fuente:     f.fuente,
      planes_ok:  f.planes  ?? 0,
      planes_err: f.error   ? 1 : 0,
      duracion_s: data.duracion_s,
      error_msg:  f.error   ?? null,
    });
  }
  await sb.rpc("marcar_inactivos_antiguos");
  await broadcastWA(ADMIN_NUMBERS, msgs.scrapingDone(data));
}

async function handleError(data: Record<string, unknown>) {
  await sb.from("scraping_logs").insert({
    fuente:     data.fuente,
    planes_ok:  0,
    planes_err: 1,
    error_msg:  data.error,
  });
  await broadcastWA(ADMIN_NUMBERS,
    msgs.scrapingError(data.fuente as string, data.error as string));
}

async function handlePlanUpdated(data: Record<string, unknown>) {
  const diff = (data.precio_anterior as number) - (data.precio_nuevo as number);
  await sb.from("precios_historial").insert({
    plan_id:         data.plan_id,
    precio_anterior: data.precio_anterior,
    precio_nuevo:    data.precio_nuevo,
    diferencia:      data.diferencia,
  });
  if (diff > 500) {
    const { data: subs } = await sb
      .from("suscripciones_precio")
      .select("numero_wa")
      .eq("plan_id", data.plan_id);
    const numeros = (subs ?? []).map((s: {numero_wa:string}) => s.numero_wa);
    if (numeros.length) await broadcastWA(numeros, msgs.priceDrop(data));
    await broadcastWA(ADMIN_NUMBERS, msgs.priceDrop(data));
  }
}

async function handleNewPlan(data: Record<string, unknown>) {
  await broadcastWA(ADMIN_NUMBERS, msgs.newPlan(data));
}

// ═══════════════════════════════════════════════════════
// SERVIDOR PRINCIPAL
// ═══════════════════════════════════════════════════════
serve(async (req: Request) => {
  if (req.method !== "POST")
    return new Response("Method Not Allowed", { status: 405 });

  const body = await req.text();
  const sig  = req.headers.get("X-Webhook-Signature") ?? "";
  const ts   = req.headers.get("X-Webhook-Timestamp")  ?? "0";

  if (!await verifySignature(body, sig, ts))
    return new Response(JSON.stringify({ error: "Unauthorized" }),
      { status: 401, headers: { "Content-Type": "application/json" } });

  let payload: { event: string; data: Record<string, unknown> };
  try {
    payload = JSON.parse(body);
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON" }),
      { status: 400, headers: { "Content-Type": "application/json" } });
  }

  console.log(`📨 Evento recibido: [${payload.event}]`);

  try {
    let result: unknown = { ok: true };
    switch (payload.event) {
      case "scraping.start":  break;
      case "scraping.batch":  result = await handleBatch(payload.data);  break;
      case "scraping.done":   await handleDone(payload.data);            break;
      case "scraping.error":  await handleError(payload.data);           break;
      case "plan.updated":    await handlePlanUpdated(payload.data);     break;
      case "plan.new":        await handleNewPlan(payload.data);         break;
      default: console.warn("Evento desconocido:", payload.event);
    }
    return new Response(
      JSON.stringify({ received: true, event: payload.event, result }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  } catch (err) {
    return new Response(
      JSON.stringify({ error: String(err) }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
});