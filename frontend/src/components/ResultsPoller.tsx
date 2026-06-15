'use client'

import { useEffect, useRef, useState } from 'react'
import { getIncident } from '@/lib/api'
import type { AnalysisResult, AnalysisStatus, RootCause } from '@/types/incident'

const TERMINAL: AnalysisStatus[] = ['complete', 'failed']

const STATUS_BADGE: Record<AnalysisStatus, string> = {
  queued: 'bg-gray-800 text-gray-300',
  processing: 'bg-blue-950 text-blue-300',
  complete: 'bg-green-950 text-green-300',
  failed: 'bg-red-950 text-red-400',
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 75 ? 'bg-red-500' : pct >= 50 ? 'bg-orange-500' : 'bg-yellow-500'
  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="flex-1 h-1.5 rounded-full bg-gray-800">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500 w-8 text-right">{pct}%</span>
    </div>
  )
}

function RootCauseCard({ rc }: { rc: RootCause }) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-4 space-y-2">
      <p className="text-sm text-gray-100">{rc.description}</p>
      <ConfidenceBar value={rc.confidence} />
      {rc.evidence.length > 0 && (
        <ul className="mt-2 space-y-1">
          {rc.evidence.map((e, i) => (
            <li key={i} className="text-xs text-gray-500 before:content-['›'] before:mr-1.5">
              {e}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4 text-blue-400" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  )
}

export default function ResultsPoller({ id }: { id: string }) {
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    async function poll() {
      try {
        const data = await getIncident(id)
        setResult(data)
        if (TERMINAL.includes(data.status)) {
          if (intervalRef.current) clearInterval(intervalRef.current)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Fetch failed')
        if (intervalRef.current) clearInterval(intervalRef.current)
      }
    }

    poll()
    intervalRef.current = setInterval(poll, 2000)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [id])

  if (error) {
    return (
      <div className="rounded-lg bg-red-950 border border-red-800 px-4 py-3 text-sm text-red-300">
        {error}
      </div>
    )
  }

  if (!result) {
    return (
      <div className="flex items-center gap-3 text-sm text-gray-400">
        <Spinner />
        Loading…
      </div>
    )
  }

  const isLive = !TERMINAL.includes(result.status)

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <p className="text-xs text-gray-500 font-mono">{result.incident_id}</p>
          <p className="text-xs text-gray-600">
            Started {new Date(result.created_at).toLocaleString()}
            {result.completed_at && (
              <> · Completed {new Date(result.completed_at).toLocaleString()}</>
            )}
          </p>
        </div>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_BADGE[result.status]}`}
        >
          {isLive && <Spinner />}
          {result.status}
        </span>
      </div>

      {/* Summary */}
      {result.summary && (
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-3">
            Summary
          </h2>
          <p className="text-sm text-gray-300 leading-relaxed">{result.summary}</p>
        </section>
      )}

      {/* Root Causes */}
      {result.root_causes.length > 0 && (
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-3">
            Root Causes
          </h2>
          <div className="space-y-3">
            {result.root_causes.map((rc, i) => (
              <RootCauseCard key={i} rc={rc} />
            ))}
          </div>
        </section>
      )}

      {/* Contributing Factors */}
      {result.contributing_factors.length > 0 && (
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-3">
            Contributing Factors
          </h2>
          <ul className="space-y-2">
            {result.contributing_factors.map((f, i) => (
              <li key={i} className="flex gap-2 text-sm text-gray-300">
                <span className="text-gray-600 select-none">·</span>
                {f}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Remediation Steps */}
      {result.remediation_steps.length > 0 && (
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-3">
            Remediation Steps
          </h2>
          <ol className="space-y-2">
            {result.remediation_steps.map((step, i) => (
              <li key={i} className="flex gap-3 text-sm text-gray-300">
                <span className="text-gray-600 select-none tabular-nums w-4">{i + 1}.</span>
                {step}
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* Runbooks */}
      {result.runbooks_referenced.length > 0 && (
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-3">
            Runbooks Referenced
          </h2>
          <div className="flex flex-wrap gap-2">
            {result.runbooks_referenced.map((rb, i) => (
              <span
                key={i}
                className="rounded-md bg-gray-800 px-2.5 py-1 text-xs font-mono text-gray-300"
              >
                {rb}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Model */}
      {result.model_used && (
        <p className="text-xs text-gray-600">
          Analyzed by <span className="font-mono">{result.model_used}</span>
        </p>
      )}

      {/* In-progress placeholder */}
      {isLive && result.root_causes.length === 0 && (
        <div className="flex items-center gap-3 text-sm text-gray-500">
          <Spinner />
          Analysis in progress…
        </div>
      )}
    </div>
  )
}
