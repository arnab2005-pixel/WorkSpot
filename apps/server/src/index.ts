import Fastify from "fastify";
import cors from "@fastify/cors";
import websocket from "@fastify/websocket";
import { profileSchema, languages, type Language } from "@workspot/shared";
import { createStore } from "./store.js";

const app = Fastify({ logger: true });
await app.register(cors, { origin: true });
await app.register(websocket);
const store = await createStore();

app.get("/health", async () => ({ ok: true, service: "workspot-api" }));

app.post<{ Body: { language?: Language } }>("/session", async (request, reply) => {
  const language = request.body?.language ?? "English";
  if (!languages.includes(language)) return reply.code(400).send({ error: "Unsupported language" });
  return store.createSession(language);
});

app.get<{ Params: { id: string } }>("/session/:id", async (request, reply) => {
  const session = await store.getSession(request.params.id);
  return session ?? reply.code(404).send({ error: "Session not found" });
});

app.delete<{ Params: { id: string } }>("/session/:id", async (request, reply) => {
  const deleted = await store.deleteSession(request.params.id);
  return deleted ? { ok: true } : reply.code(404).send({ error: "Session not found" });
});

app.post<{ Params: { id: string }; Body: { profile: unknown; state?: string } }>("/session/:id/profile", async (request, reply) => {
  const profile = profileSchema.safeParse(request.body?.profile);
  if (!profile.success) return reply.code(400).send({ error: "Invalid profile", details: profile.error.flatten() });
  const session = await store.updateSession(request.params.id, { profile: profile.data, state: (request.body.state as never) ?? "results" });
  return session ?? reply.code(404).send({ error: "Session not found" });
});

app.get<{ Params: { sessionId: string } }>("/recommendations/:sessionId", async (request, reply) => {
  const session = await store.getSession(request.params.sessionId);
  if (!session) return reply.code(404).send({ error: "Session not found" });
  return store.getRecommendations(session.profile);
});

app.post("/followup/schedule", async () => ({ scheduled: true, message: "A district desk follow-up can be scheduled here." }));

app.get("/tts/:lang/:promptId", async (request) => ({ cached: true, ...request.params }));
app.post("/tts/dynamic", async () => ({ queued: true }));

app.get("/interview", { websocket: true }, (socket) => {
  socket.on("message", (raw) => {
    try {
      const message = JSON.parse(raw.toString()) as { type: string };
      socket.send(JSON.stringify({ type: "ack", received: message.type, serverTime: new Date().toISOString() }));
    } catch {
      socket.send(JSON.stringify({ type: "error_fallback", message: "We could not understand that message." }));
    }
  });
});

const port = Number(process.env.PORT ?? 4000);
app.listen({ port, host: "0.0.0.0" }).catch((error) => { app.log.error(error); process.exit(1); });
