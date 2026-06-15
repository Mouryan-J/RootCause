'use client'

import { useEffect, useState } from 'react'

const STORAGE_KEY = 'rootcause_api_key'
const AUTH_REQUIRED = process.env.NEXT_PUBLIC_AUTH_REQUIRED === 'true'

export default function ApiKeyGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false)
  const [hasKey, setHasKey] = useState(false)
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    setHasKey(!!stored)
    setReady(true)
  }, [])

  // Auth disabled or key already stored — render app immediately
  if (!AUTH_REQUIRED || (ready && hasKey)) {
    return <>{children}</>
  }

  // Hydrating — avoid flash
  if (!ready) return null

  function save(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim()) {
      setError('Please enter your API key')
      return
    }
    localStorage.setItem(STORAGE_KEY, input.trim())
    setHasKey(true)
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm space-y-6">
        <div>
          <p className="text-red-500 font-mono text-2xl font-bold">⬡</p>
          <h1 className="mt-2 text-xl font-bold">RootCause</h1>
          <p className="mt-1 text-sm text-gray-400">Enter your API key to continue.</p>
        </div>

        <form onSubmit={save} className="space-y-4">
          <input
            type="password"
            value={input}
            onChange={(e) => { setInput(e.target.value); setError(null) }}
            placeholder="sk-..."
            autoFocus
            className="w-full rounded-lg bg-gray-900 border border-gray-700 px-4 py-2.5 text-sm text-gray-100 placeholder-gray-600 focus:border-red-500 focus:outline-none font-mono"
          />
          {error && <p className="text-xs text-red-400">{error}</p>}
          <button
            type="submit"
            className="w-full rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-500 transition-colors"
          >
            Connect
          </button>
        </form>

        <button
          onClick={() => {
            localStorage.removeItem(STORAGE_KEY)
            setHasKey(false)
            setInput('')
          }}
          className="text-xs text-gray-600 hover:text-gray-400 transition-colors hidden"
          id="logout-btn"
        >
          Clear key
        </button>
      </div>
    </div>
  )
}

/** Call from anywhere to clear the stored API key (e.g. on 401). */
export function clearApiKey() {
  if (typeof window !== 'undefined') {
    localStorage.removeItem(STORAGE_KEY)
  }
}
