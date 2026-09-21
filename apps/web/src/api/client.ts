/**
 * WorkSpot API Client
 * Connects the web kiosk frontend to PM-AJAY backend endpoints.
 */

import type { Profile, Recommendation } from "@workspot/shared";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

export interface SessionResponse {
  id: string;
  session_id: string;
  language: string;
  state: string;
  initial_prompt_indic: string;
  mock_audio_url: string;
  profile: Profile;
  createdAt: string;
  updatedAt: string;
  options?: string[];
}

export interface InteractResponse {
  session_id: string;
  current_state: string;
  spoken_response_indic: string;
  updated_slots: Record<string, any>;
  profile: Profile;
  recommended_courses: Recommendation[];
  eligible_for_gia_asset_grant: boolean;
  max_capital_subsidy_inr: number;
  credit_desk_routing: string | null;
  is_complete: boolean;
  options?: string[];
}

export interface AdvisorResponse {
  reply: string;
  suggestions: string[];
}

export async function createSession(
  language: string = "Hindi",
  phoneNumber?: string,
  district: string = "UP_VARANASI"
): Promise<SessionResponse> {
  const url = `${API_BASE}/api/v1/session`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      language,
      phone_number: phoneNumber,
      district,
    }),
  });

  if (!res.ok) {
    throw new Error(`Failed to create session: ${res.statusText}`);
  }
  return res.json();
}

export async function getSession(sessionId: string): Promise<SessionResponse> {
  const url = `${API_BASE}/api/v1/session/${encodeURIComponent(sessionId)}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to get session: ${res.statusText}`);
  }
  return res.json();
}

export async function deleteSession(sessionId: string): Promise<boolean> {
  try {
    const url = `${API_BASE}/api/v1/session/${encodeURIComponent(sessionId)}`;
    const res = await fetch(url, { method: "DELETE" });
    return res.ok;
  } catch {
    return false;
  }
}

export async function sendInteraction(
  sessionId: string,
  transcript: string,
  language: string = "Hindi"
): Promise<InteractResponse> {
  const url = `${API_BASE}/api/v1/interact`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      user_transcript: transcript,
      language,
    }),
  });

  if (!res.ok) {
    throw new Error(`Failed to send interaction: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchRecommendations(sessionId: string): Promise<Recommendation[]> {
  const url = `${API_BASE}/api/v1/recommendations/${encodeURIComponent(sessionId)}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch recommendations: ${res.statusText}`);
  }
  return res.json();
}

export async function sendAdvisorChat(
  sessionId: string | null,
  message: string,
  language: string = "Hindi"
): Promise<AdvisorResponse> {
  const url = `${API_BASE}/api/v1/advisor/chat`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      language,
    }),
  });

  if (!res.ok) {
    throw new Error(`Failed to chat with advisor: ${res.statusText}`);
  }
  return res.json();
}

export async function transcribeAudio(
  audioBlob: Blob,
  sessionId?: string,
  language: string = "hi"
): Promise<string> {
  const url = `${API_BASE}/api/v1/audio/transcribe`;
  const formData = new FormData();
  formData.append("file", audioBlob, "recording.webm");
  if (sessionId) formData.append("session_id", sessionId);
  formData.append("language", language);

  const res = await fetch(url, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(`Failed to transcribe audio: ${res.statusText}`);
  }
  const data = await res.json();
  return data.transcript || "";
}

/**
 * Upload a prerecorded audio file and process it as a conversational turn in one call.
 * The backend transcribes the audio and feeds the result into the FSM.
 */
export async function uploadAudioAndInteract(
  audioFile: File | Blob,
  sessionId: string,
  language: string = "Hindi",
  filename?: string,
): Promise<InteractResponse> {
  const url = `${API_BASE}/api/v1/audio/interact`;
  const formData = new FormData();
  formData.append("file", audioFile, filename || (audioFile instanceof File ? audioFile.name : "upload.wav"));
  formData.append("session_id", sessionId);
  formData.append("language", language);

  const res = await fetch(url, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(`Failed to upload audio: ${res.statusText}`);
  }
  return res.json();
}
