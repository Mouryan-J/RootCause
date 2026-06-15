import type { AnalysisResult, IncidentRequest, IncidentResponse } from '@/types/incident'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

function authHeaders(): Record<string, string> {
  if (typeof window === 'undefined') return {}
  const key = localStorage.getItem('rootcause_api_key')
  return key ? { Authorization: `Bearer ${key}` } : {}
}

export async function submitIncident(data: IncidentRequest): Promise<IncidentResponse> {
  const res = await fetch(`${BASE_URL}/incidents/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Submit failed (${res.status}): ${text}`)
  }
  return res.json() as Promise<IncidentResponse>
}

export async function getIncident(id: string): Promise<AnalysisResult> {
  const res = await fetch(`${BASE_URL}/incidents/${id}`, {
    cache: 'no-store',
    headers: authHeaders(),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Fetch failed (${res.status}): ${text}`)
  }
  return res.json() as Promise<AnalysisResult>
}
