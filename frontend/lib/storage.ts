import type { HistoryRecord } from "./types";

const KEY = "mockmate_history";

export function getHistory(): HistoryRecord[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]") as HistoryRecord[];
  } catch {
    return [];
  }
}

export function saveHistory(record: HistoryRecord): void {
  const history = getHistory();
  const idx = history.findIndex((r) => r.session_id === record.session_id);
  if (idx >= 0) history[idx] = record;
  else history.unshift(record);
  localStorage.setItem(KEY, JSON.stringify(history));
}

export function deleteHistory(session_id: string): void {
  const history = getHistory().filter((r) => r.session_id !== session_id);
  localStorage.setItem(KEY, JSON.stringify(history));
}
