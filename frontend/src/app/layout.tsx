import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import './globals.css'
import ApiKeyGate from '@/components/ApiKeyGate'

const geistSans = Geist({ variable: '--font-geist-sans', subsets: ['latin'] })
const geistMono = Geist_Mono({ variable: '--font-geist-mono', subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'RootCause — Incident RCA Copilot',
  description: 'Autonomous incident root cause analysis and remediation using multi-agent AI.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full`}>
      <body className="min-h-full bg-gray-950 text-gray-100 antialiased">
        <header className="border-b border-gray-800 px-6 py-4">
          <div className="mx-auto max-w-4xl flex items-center gap-3">
            <span className="text-red-500 font-mono text-lg font-bold">⬡</span>
            <span className="font-semibold tracking-tight">RootCause</span>
            <span className="text-gray-500 text-sm">Incident RCA Copilot</span>
          </div>
        </header>
        <ApiKeyGate>
          <main className="mx-auto max-w-4xl px-6 py-10">{children}</main>
        </ApiKeyGate>
      </body>
    </html>
  )
}
