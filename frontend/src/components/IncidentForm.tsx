'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { submitIncident } from '@/lib/api'
import type { Severity } from '@/types/incident'

const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low']

const SEVERITY_COLORS: Record<Severity, string> = {
  critical: 'text-red-400',
  high: 'text-orange-400',
  medium: 'text-yellow-400',
  low: 'text-green-400',
}

export default function IncidentForm() {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const [form, setForm] = useState({
    title: '',
    description: '',
    service: '',
    severity: 'high' as Severity,
    started_at: new Date().toISOString().slice(0, 16),
    logs: '',
  })

  const set = (field: keyof typeof form) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => setForm((f) => ({ ...f, [field]: e.target.value }))

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const { incident_id } = await submitIncident({
        title: form.title,
        description: form.description,
        service: form.service,
        severity: form.severity,
        started_at: new Date(form.started_at).toISOString(),
        logs: form.logs || undefined,
      })
      router.push(`/incidents/${incident_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Submission failed')
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className="block text-sm font-medium text-gray-300 mb-1.5">Title</label>
          <input
            required
            value={form.title}
            onChange={set('title')}
            placeholder="e.g. API gateway returning 502s on /checkout"
            className="w-full rounded-lg bg-gray-900 border border-gray-700 px-4 py-2.5 text-sm text-gray-100 placeholder-gray-600 focus:border-red-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1.5">Service</label>
          <input
            required
            value={form.service}
            onChange={set('service')}
            placeholder="e.g. payment-service"
            className="w-full rounded-lg bg-gray-900 border border-gray-700 px-4 py-2.5 text-sm text-gray-100 placeholder-gray-600 focus:border-red-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1.5">Severity</label>
          <select
            value={form.severity}
            onChange={set('severity')}
            className="w-full rounded-lg bg-gray-900 border border-gray-700 px-4 py-2.5 text-sm text-gray-100 focus:border-red-500 focus:outline-none"
          >
            {SEVERITIES.map((s) => (
              <option key={s} value={s} className={SEVERITY_COLORS[s]}>
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </option>
            ))}
          </select>
        </div>

        <div className="sm:col-span-2">
          <label className="block text-sm font-medium text-gray-300 mb-1.5">Started at</label>
          <input
            type="datetime-local"
            required
            value={form.started_at}
            onChange={set('started_at')}
            className="w-full rounded-lg bg-gray-900 border border-gray-700 px-4 py-2.5 text-sm text-gray-100 focus:border-red-500 focus:outline-none"
          />
        </div>

        <div className="sm:col-span-2">
          <label className="block text-sm font-medium text-gray-300 mb-1.5">Description</label>
          <textarea
            required
            rows={4}
            value={form.description}
            onChange={set('description')}
            placeholder="Describe what happened, what was the impact, and any initial hypotheses…"
            className="w-full rounded-lg bg-gray-900 border border-gray-700 px-4 py-2.5 text-sm text-gray-100 placeholder-gray-600 focus:border-red-500 focus:outline-none resize-none"
          />
        </div>

        <div className="sm:col-span-2">
          <label className="block text-sm font-medium text-gray-300 mb-1.5">
            Logs <span className="text-gray-500">(optional)</span>
          </label>
          <textarea
            rows={6}
            value={form.logs}
            onChange={set('logs')}
            placeholder="Paste relevant log lines here…"
            className="w-full rounded-lg bg-gray-900 border border-gray-700 px-4 py-2.5 text-sm text-gray-100 placeholder-gray-600 font-mono focus:border-red-500 focus:outline-none resize-none"
          />
        </div>
      </div>

      {error && (
        <p className="rounded-lg bg-red-950 border border-red-800 px-4 py-3 text-sm text-red-300">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-lg bg-red-600 px-6 py-3 text-sm font-semibold text-white hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? 'Submitting…' : 'Analyze Incident'}
      </button>
    </form>
  )
}
