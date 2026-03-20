const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function startSimulation(config: import('./types').SimConfig): Promise<{ sim_id: string }> {
  const res = await fetch(`${API_BASE}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })
  if (!res.ok) throw new Error(`Failed to start simulation: ${res.status}`)
  return res.json()
}

export function streamSimulation(sim_id: string): EventSource {
  return new EventSource(`${API_BASE}/simulate-stream/${sim_id}`)
}

export async function getResults(sim_id: string): Promise<import('./types').SimResults> {
  const res = await fetch(`${API_BASE}/results/${sim_id}`)
  if (!res.ok) throw new Error(`Failed to get results: ${res.status}`)
  return res.json()
}

export async function getHistory(): Promise<import('./types').HistoryItem[]> {
  const res = await fetch(`${API_BASE}/history`)
  if (!res.ok) throw new Error('Failed to get history')
  return res.json()
}

export function exportPdfUrl(sim_id: string): string {
  return `${API_BASE}/export/${sim_id}`
}

export async function cancelSimulation(sim_id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/simulate/${sim_id}/cancel`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to cancel: ${res.status}`)
}
