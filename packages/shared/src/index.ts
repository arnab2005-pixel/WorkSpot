import { z } from "zod";

export const languages = [
  "English",
  "Hindi",
  "Bengali",
  "Marathi",
  "Tamil",
  "Telugu",
  "Kannada",
  "Malayalam",
  "Gujarati",
  "Punjabi",
  "Odia",
  "Assamese",
  "Bhojpuri",
  "Maithili",
  "Urdu"
] as const;
export type Language = (typeof languages)[number];

export const interviewStates = ["idle", "language", "consent", "interview", "results", "confirm", "done"] as const;
export type InterviewState = (typeof interviewStates)[number];

export const profileSchema = z.object({
  currentWork: z.string().default(""),
  skills: z.array(z.string()).default([]),
  craft: z.string().default(""),
  mobility: z.enum(["0 km", "15 km", "50 km", "Out of district"]).default("15 km"),
  intent: z.enum(["Wage employment", "Self-employment", "Either"]).default("Either"),
  aspirations: z.string().default(""),
  district: z.string().default(""),
  age: z.number().int().min(14).max(100).optional()
});

export type Profile = z.infer<typeof profileSchema>;

export const recommendationSchema = z.object({
  id: z.string(),
  type: z.enum(["Training", "Job", "Self-employment", "Government support"]),
  title: z.string(),
  provider: z.string(),
  location: z.string(),
  match: z.number().min(0).max(100),
  explanation: z.string(),
  tags: z.array(z.string())
});

export type Recommendation = z.infer<typeof recommendationSchema>;

export const sessionSchema = z.object({
  id: z.string(),
  language: z.enum(languages),
  state: z.enum(interviewStates),
  profile: profileSchema,
  createdAt: z.string(),
  updatedAt: z.string()
});

export type Session = z.infer<typeof sessionSchema>;

export const questionFlow = [
  { id: "work", label: "Current work", prompt: "What work or activity do you do today?" },
  { id: "skills", label: "Skills", prompt: "What are you good at or enjoy doing?" },
  { id: "intent", label: "Work preference", prompt: "Would you prefer a job, your own work, or either?" },
  { id: "mobility", label: "Travel distance", prompt: "How far can you travel for an opportunity?" }
] as const;

export function nextInterviewState(state: InterviewState): InterviewState {
  const order: InterviewState[] = ["idle", "language", "consent", "interview", "results", "confirm", "done"];
  return order[Math.min(order.indexOf(state) + 1, order.length - 1)];
}
