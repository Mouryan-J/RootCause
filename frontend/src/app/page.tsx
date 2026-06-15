import IncidentForm from '@/components/IncidentForm'

export default function HomePage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">New Incident</h1>
        <p className="mt-1 text-sm text-gray-400">
          Submit an incident for autonomous root cause analysis. Results are ready in seconds.
        </p>
      </div>
      <IncidentForm />
    </div>
  )
}
