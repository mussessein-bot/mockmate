import type {
  CreateSessionPayload,
  StartResponse,
  RespondResponse,
  SessionSummary,
  InterviewInterface,
  CorrectionResponse,
  JobAnalysisResponse,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API ${path} failed (${res.status}): ${err}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getSession: (sessionId: string) =>
    apiFetch<{ persona: string; interview_interface: InterviewInterface }>(`/api/sessions/${sessionId}`),

  createSession: (payload: CreateSessionPayload) =>
    apiFetch<{
      session_id: string;
      state: string;
      active_dimensions: string[];
      interview_interface: InterviewInterface;
    }>("/api/sessions", { method: "POST", body: JSON.stringify(payload) }),

  startInterview: (sessionId: string) =>
    apiFetch<StartResponse>(`/api/interview/${sessionId}/start`, { method: "POST" }),

  respond: (sessionId: string, transcript: string) =>
    apiFetch<RespondResponse>(`/api/interview/${sessionId}/respond`, {
      method: "POST",
      body: JSON.stringify({ transcript }),
    }),

  pause: (sessionId: string) =>
    apiFetch<{ paused: boolean }>(`/api/interview/${sessionId}/pause`, { method: "POST" }),

  resume: (sessionId: string) =>
    apiFetch<{ resumed: boolean }>(`/api/interview/${sessionId}/resume`, { method: "POST" }),

  replayAudio: (sessionId: string) =>
    apiFetch<{ audio_url: string }>(`/api/interview/${sessionId}/replay-audio`),

  finalize: (sessionId: string) =>
    apiFetch<SessionSummary>(`/api/sessions/${sessionId}/finalize`, { method: "POST" }),

  getFeedback: (sessionId: string) =>
    apiFetch<SessionSummary>(`/api/sessions/${sessionId}/feedback`),

  analyzeRole: (payload: { target_role: string; target_company?: string; job_description?: string; language?: string }) =>
    apiFetch<JobAnalysisResponse>("/api/analyze-role", {
      method: "POST",
      body: JSON.stringify({ language: "zh", ...payload }),
    }),

  refineAnalysis: (payload: { target_role: string; target_company?: string; job_description?: string; user_note: string; language?: string }) =>
    apiFetch<JobAnalysisResponse>("/api/refine-analysis", {
      method: "POST",
      body: JSON.stringify({ language: "zh", ...payload }),
    }),

  webSearchAnalyze: (payload: { target_role: string; target_company?: string; job_description?: string; language?: string }) =>
    apiFetch<JobAnalysisResponse>("/api/web-search-analyze", {
      method: "POST",
      body: JSON.stringify({ language: "zh", ...payload }),
    }),

  submitCorrection: (sessionId: string, tags: string[], note?: string) =>
    apiFetch<CorrectionResponse>(`/api/interview/${sessionId}/correction`, {
      method: "POST",
      body: JSON.stringify({ tags, note: note || null }),
    }),

  ttsPreview: (persona: string, language: string) =>
    apiFetch<{ audio_url: string }>("/api/tts/preview", {
      method: "POST",
      body: JSON.stringify({ persona, language }),
    }),

  parsePdf: async (file: File): Promise<{ text: string }> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/api/parse-pdf`, { method: "POST", body: form });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`parse-pdf failed (${res.status}): ${err}`);
    }
    return res.json();
  },

  transcribe: async (sessionId: string, blob: Blob, ext = "webm"): Promise<{ transcript: string }> => {
    const form = new FormData();
    form.append("file", blob, `audio.${ext}`);
    const res = await fetch(`${BASE}/api/interview/${sessionId}/transcribe`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`transcribe failed (${res.status}): ${err}`);
    }
    return res.json();
  },
};

export function audioUrl(path: string): string {
  if (path.startsWith("http")) return path;
  return `${BASE}${path}`;
}
