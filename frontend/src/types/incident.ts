export type Severity = 'critical' | 'high' | 'medium' | 'low'
export type AnalysisStatus = 'queued' | 'processing' | 'complete' | 'failed'

export interface IncidentRequest {
  title: string
  description: string
  service: string
  severity: Severity
  started_at: string
  resolved_at?: string
  logs?: string
  metrics?: Record<string, unknown>
  labels?: Record<string, string>
}

export interface IncidentResponse {
  incident_id: string
  status: AnalysisStatus
  created_at: string
  message: string
}

export interface RootCause {
  description: string
  confidence: number
  evidence: string[]
}

export interface IncidentListItem {
  incident_id: string
  title: string
  service: string
  severity: Severity
  status: AnalysisStatus
  created_at: string
  completed_at?: string
}

export interface AnalysisResult {
  incident_id: string
  status: AnalysisStatus
  created_at: string
  completed_at?: string
  service: string
  root_causes: RootCause[]
  contributing_factors: string[]
  remediation_steps: string[]
  summary?: string
  runbooks_referenced: string[]
  model_used?: string
}

export interface GraphNode {
  name: string
  dep_type: string
}

export interface ServiceGraph {
  depends_on: GraphNode[]
  depended_on_by: GraphNode[]
}
