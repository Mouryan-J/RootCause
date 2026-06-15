import Link from 'next/link'
import ResultsPoller from '@/components/ResultsPoller'

export default async function IncidentPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Analysis Results</h1>
          <p className="mt-1 text-sm text-gray-400">
            Live updates until analysis completes.
          </p>
        </div>
        <Link
          href="/"
          className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
        >
          ← New incident
        </Link>
      </div>
      <ResultsPoller id={id} />
    </div>
  )
}
