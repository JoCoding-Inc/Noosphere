export const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public isRetryable: boolean,
    public body?: unknown
  ) { super(message) }
}

async function fetchWithRetry(
  url: string,
  options: RequestInit = {},
  timeoutMs = 30000,
  maxRetries = 2
): Promise<Response> {
  let lastError: Error = new Error('Unknown error')
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    try {
      const res = await fetch(url, { ...options, signal: controller.signal })
      clearTimeout(timer)
      if (res.ok) return res
      const body = await res.json().catch(() => null)
      const isRetryable = res.status >= 500
      if (!isRetryable || attempt === maxRetries) {
        throw new ApiError(`HTTP ${res.status}`, res.status, isRetryable, body)
      }
      lastError = new ApiError(`HTTP ${res.status}`, res.status, true, body)
    } catch (err) {
      clearTimeout(timer)
      if (err instanceof ApiError) throw err
      lastError = err as Error
      if (attempt === maxRetries) throw lastError
    }
    // 지수 백오프
    await new Promise(r => setTimeout(r, 500 * Math.pow(2, attempt)))
  }
  throw lastError
}

export async function startSimulation(config: import('./types').SimConfig): Promise<{ sim_id: string }> {
  const res = await fetchWithRetry(`${API_BASE}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  }, 120000)
  return res.json()
}

export async function getResults(sim_id: string): Promise<import('./types').SimResults> {
  const res = await fetchWithRetry(`${API_BASE}/results/${sim_id}`)
  return res.json()
}

export async function getHistory(): Promise<import('./types').HistoryItem[]> {
  const res = await fetchWithRetry(`${API_BASE}/history`)
  return res.json()
}

export function exportPdfUrl(sim_id: string): string {
  return `${API_BASE}/export/${sim_id}`
}

export function exportJsonUrl(sim_id: string): string {
  return `${API_BASE}/export/${sim_id}/json`
}

export function exportJson(simId: string): void {
  const url = exportJsonUrl(simId)
  const a = document.createElement('a')
  a.href = url
  a.download = `${simId}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

export async function cancelSimulation(sim_id: string): Promise<void> {
  await fetchWithRetry(`${API_BASE}/simulate/${sim_id}/cancel`, { method: 'POST' })
}

export async function resumeSimulation(sim_id: string): Promise<{ sim_id: string; resuming_from_round: number }> {
  const res = await fetchWithRetry(`${API_BASE}/simulate/${sim_id}/resume`, { method: 'POST' })
  return res.json()
}

export async function getSimulationStatus(sim_id: string): Promise<{ status: string; last_round: number }> {
  const res = await fetchWithRetry(`${API_BASE}/simulate/${sim_id}/status`)
  return res.json()
}

export async function deleteSimulation(sim_id: string): Promise<void> {
  await fetchWithRetry(`${API_BASE}/simulate/${sim_id}`, { method: 'DELETE' })
}
