import type { ActivityResponse, MarketplaceSeed, SimulationSnapshot } from "./types";

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
