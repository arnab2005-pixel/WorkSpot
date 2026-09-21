import type { Profile, Recommendation, Session } from "@workspot/shared";
import { MongoClient, type Collection } from "mongodb";

const now = () => new Date().toISOString();

export interface Store {
  createSession(language: Session["language"]): Promise<Session>;
  getSession(id: string): Promise<Session | undefined>;
  deleteSession(id: string): Promise<boolean>;
  updateSession(id: string, patch: Partial<Session>): Promise<Session | undefined>;
  getRecommendations(profile: Profile): Promise<Recommendation[]>;
}

const recommendations: Recommendation[] = [
  { id: "tailor-edp-01", type: "Training", title: "Self Employed Tailor (सिलाई दर्जी)", provider: "Skill India Digital Hub / PM-AJAY", location: "District Skill Center, Cantt", match: 96, explanation: "NSQF Level 4 training with hands-on garment cutting, machine operation, free toolkit, and ₹1,500 monthly stipend.", tags: ["NSQF Level 4", "Free Toolkit", "Stipend ₹1500/mo", "3 Months"] },
  { id: "pm-ajay-gia-01", type: "Government support", title: "PM-AJAY Capital Asset Grant (GIA)", provider: "District Project Implementation Unit (DPIU)", location: "District Welfare Office", match: 98, explanation: "Capital subsidy of up to 50% or ₹50,000 to purchase machinery, work tools, and initial inventory under PM-AJAY.", tags: ["₹50,000 Capital Grant", "50% Subsidy", "DPIU Fast-track"] },
  { id: "solar", type: "Training", title: "Solar PV Installation", provider: "Skill India Digital", location: "District training centre", match: 94, explanation: "Builds on your hands-on ability and has growing local demand, with training within your travel preference.", tags: ["Modern sector", "NSQF aligned", "3 months"] },
  { id: "bamboo", type: "Self-employment", title: "Bamboo Enterprise Starter", provider: "ODOP cluster support", location: "Local cluster", match: 91, explanation: "Matches your craft experience and can help you turn existing skills into a stronger local livelihood.", tags: ["Your experience", "Tool support", "Local"] },
  { id: "ev", type: "Training", title: "EV Two-Wheeler Service", provider: "Skill India Digital", location: "Within 15 km", match: 86, explanation: "A practical modern trade with nearby demand and an accessible entry path for new technicians.", tags: ["Future-ready", "Apprenticeship", "6 months"] },
  { id: "credit", type: "Government support", title: "Micro-enterprise working capital", provider: "NSFDC", location: "Online application support", match: 79, explanation: "May support tools and working capital if you choose self-employment after training.", tags: ["Financial support", "Eligibility check"] }
];

class MemoryStore implements Store {
  private sessions = new Map<string, Session>();

  async createSession(language: Session["language"]): Promise<Session> {
    const timestamp = now();
    const session: Session = { id: `ws_${Math.random().toString(36).slice(2, 10)}`, language, state: "consent", profile: { currentWork: "", skills: [], craft: "", mobility: "15 km", intent: "Either", aspirations: "", district: "" }, createdAt: timestamp, updatedAt: timestamp };
    this.sessions.set(session.id, session);
    return session;
  }

  async getSession(id: string) { return this.sessions.get(id); }

  async deleteSession(id: string) { return this.sessions.delete(id); }

  async updateSession(id: string, patch: Partial<Session>) {
    const existing = this.sessions.get(id);
    if (!existing) return undefined;
    const updated = { ...existing, ...patch, updatedAt: now() };
    this.sessions.set(id, updated);
    return updated;
  }

  async getRecommendations(_profile: Profile) { return recommendations; }
}

export async function createStore(): Promise<Store> {
  if (!process.env.MONGODB_URI) return new MemoryStore();
  const client = new MongoClient(process.env.MONGODB_URI);
  await client.connect();
  const db = client.db(process.env.MONGODB_DB ?? "workspot");
  const sessions = db.collection<Session>("sessions");
  const recs = db.collection<Recommendation>("recommendations");
  return new MongoStore(sessions, recs);
}

class MongoStore implements Store {
  constructor(private sessions: Collection<Session>, private recs: Collection<Recommendation>) {}
  async createSession(language: Session["language"]): Promise<Session> {
    const timestamp = now();
    const session: Session = { id: `ws_${Math.random().toString(36).slice(2, 10)}`, language, state: "consent", profile: { currentWork: "", skills: [], craft: "", mobility: "15 km", intent: "Either", aspirations: "", district: "" }, createdAt: timestamp, updatedAt: timestamp };
    await this.sessions.insertOne(session);
    return session;
  }
  async getSession(id: string) { return (await this.sessions.findOne({ id }, { projection: { _id: 0 } })) ?? undefined; }
  async deleteSession(id: string) { const result = await this.sessions.deleteOne({ id }); return result.deletedCount > 0; }
  async updateSession(id: string, patch: Partial<Session>) { await this.sessions.updateOne({ id }, { $set: { ...patch, updatedAt: now() } }); return this.getSession(id); }
  async getRecommendations(profile: Profile) { const stored = await this.recs.find({}, { projection: { _id: 0 } }).limit(8).toArray(); return stored.length ? stored : new MemoryStore().getRecommendations(profile); }
}
