'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { listIncidents } from '@/lib/api'
import type { IncidentListItem, Severity, AnalysisStatus } from '@/types/incident'

const SEVERITY_COLORS: Record<Severity, string> = {
  critical: 'text-red-400',
  high: 'text-orange-400',
  medium: 'text-yellow-400',
  low: 'text-green-400',
}

const STATUS_BADGE: Record<AnalysisStatus, string> = {
  queued: 'bg-gray-800 text-gray-300',
  processing: 'bg-blue-950 text-blue-300',
  complete: 'bg-green-950 text-green-300',
  failed: 'bg-red-950 text-red-400',
}

function timeAgo(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export default function HistoryPage() {
  const [incidents, setIncidents] = useState<IncidentListItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listIncidents()
      .then(setIncidents)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Incident History</h1>
          <p className="mt-1 text-sm text-gray-400">Recent incidents and their analysis status.</p>
        </div>
        <Link
          href="/"
          className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500 transition-colors"
        >
          + New incident
        </Link>
      </div>

      {loading && (
        <p className="text-sm text-gray-500">Loading…</p>
      )}

      {error && (
        <div className="rounded-lg bg-red-950 border border-red-800 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {!loading && !error && incidents.length === 0 && (
        <div className="rounded-lg border border-gray-800 bg-gray-900 px-6 py-12 text-center">
          <p className="text-sm text-gray-500">No incidents yet.</p>
          <Link href="/" className="mt-3 inline-block text-sm text-red-400 hover:text-red-300">
            Submit your first incident →
          </Link>
        </div>
      )}

      {incidents.length > 0 && (
        <div className="rounded-lg border border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900">
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Service</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Severity</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">When</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {incidents.map((inc) => (
                <tr key={inc.incident_id} className="hover:bg-gray-900 transition-colors">
                  <td className="px-4 py-3">
                    <Link
                      href={`/incidents/${inc.incident_id}`}
                      className="text-gray-100 hover:text-red-400 transition-colors font-medium"
                    >
                      {inc.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-400">{inc.service}</td>
                  <td className={`px-4 py-3 font-medium capitalize ${SEVERITY_COLORS[inc.severity]}`}>
                    {inc.severity}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_BADGE[inc.status]}`}>
                      {inc.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">{timeAgo(inc.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
