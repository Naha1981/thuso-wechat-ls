import { createHmac, timingSafeEqual } from "node:crypto";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

function validSignature(raw: Uint8Array, header: string | null, secret: string) {
  if (!header?.startsWith("sha256=")) return false;
  const expected = createHmac("sha256", secret).update(raw).digest("hex");
  const supplied = header.slice(7);
  if (expected.length !== supplied.length) return false;
  return timingSafeEqual(Buffer.from(expected), Buffer.from(supplied));
}

Deno.serve(async (req) => {
  const verifyToken = Deno.env.get("WHATSAPP_VERIFY_TOKEN");
  const appSecret = Deno.env.get("WHATSAPP_APP_SECRET");
  const internalUrl = Deno.env.get("INTERNAL_API_URL");
  const internalSecret = Deno.env.get("INTERNAL_WEBHOOK_SECRET");
  if (!verifyToken || !appSecret || !internalUrl || !internalSecret) return json({ error: "misconfigured" }, 500);

  if (req.method === "GET") {
    const u = new URL(req.url);
    if (u.searchParams.get("hub.verify_token") !== verifyToken) return new Response("Forbidden", { status: 403 });
    return new Response(u.searchParams.get("hub.challenge") ?? "", { status: 200 });
  }
  if (req.method !== "POST") return new Response("Method Not Allowed", { status: 405 });

  const raw = new Uint8Array(await req.arrayBuffer());
  if (raw.byteLength > 1_048_576) return new Response("Payload too large", { status: 413 });
  if (!validSignature(raw, req.headers.get("x-hub-signature-256"), appSecret)) return new Response("Unauthorized", { status: 401 });

  const forward = await fetch(`${internalUrl.replace(/\/$/, "")}/api/v1/webhooks/whatsapp`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-internal-webhook-secret": internalSecret, "x-hub-signature-256": req.headers.get("x-hub-signature-256")! },
    body: raw,
  });
  return new Response(await forward.text(), { status: forward.status, headers: { "content-type": "application/json" } });
});
