import type {
  ActivityResponse,
  AIAgentLog,
  AttentionCase,
  Booking,
  MarketplaceSeed,
  OpsBriefResponse,
  SimulationSnapshot,
} from "./types";

const API_BASE_URL =
  (
    process.env.NEXT_PUBLIC_API_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://localhost:8000"
  ).replace(/\/+$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = init?.body
    ? { "Content-Type": "application/json", ...init.headers }
    : init?.headers;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`);
  }

  return response.json() as Promise<T>;
}

export function getMarketplaceSeed() {
  return request<MarketplaceSeed>("/marketplace/seed");
}

export function getDashboard() {
  return request<SimulationSnapshot>("/dashboard", { cache: "no-store" });
}

export function getActivity() {
  return request<ActivityResponse>("/activity", { cache: "no-store" });
}

export function getAIAgentLog() {
  return request<AIAgentLog[]>("/ops/ai-log", { cache: "no-store" });
}

export function getAttentionCases() {
  return request<AttentionCase[]>("/ops/attention", { cache: "no-store" });
}

export function getHighValueBookings() {
  return request<Booking[]>("/ops/high-value", { cache: "no-store" });
}

export function getOpsBrief() {
  return request<OpsBriefResponse>("/ops/brief", { cache: "no-store" });
}

export function approveAIFollowUp(caseId: string) {
  return request<AttentionCase>(`/ops/attention/${caseId}/approve`, {
    method: "POST",
  });
}

export function selectHumanRescue(caseId: string) {
  return request<AttentionCase>(`/ops/attention/${caseId}/human-rescue`, {
    method: "POST",
  });
}

export function startSimulation() {
  return request<SimulationSnapshot>("/simulation/start", { method: "POST" });
}

export function resetSimulation() {
  return request<SimulationSnapshot>("/simulation/reset", { method: "POST" });
}

export function updateAutopilot(enabled: boolean) {
  return request<SimulationSnapshot>("/autopilot", {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });
}
