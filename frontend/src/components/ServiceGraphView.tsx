'use client'

import type { ServiceGraph } from '@/types/incident'

const NODE_W = 140
const NODE_H = 36
const H_GAP = 20
const CALLER_Y = 20
const SERVICE_Y = 130
const DEP_Y = 240
const SVG_H = 300

const DEP_TYPE_COLORS: Record<string, string> = {
  database: '#1e3a5f',
  cache: '#1a3a2a',
  service: '#2a1f3d',
  queue: '#3a2a1a',
}

const DEP_TYPE_TEXT: Record<string, string> = {
  database: '#60a5fa',
  cache: '#4ade80',
  service: '#a78bfa',
  queue: '#fb923c',
}

function rowX(count: number, index: number, svgWidth: number): number {
  const totalWidth = count * NODE_W + (count - 1) * H_GAP
  const startX = (svgWidth - totalWidth) / 2
  return startX + index * (NODE_W + H_GAP)
}

function NodeBox({
  x, y, label, depType, highlight = false,
}: {
  x: number; y: number; label: string; depType?: string; highlight?: boolean
}) {
  const fill = highlight ? '#450a0a' : (depType ? DEP_TYPE_COLORS[depType] ?? '#1e1e2e' : '#1e1e2e')
  const border = highlight ? '#dc2626' : '#374151'
  const textColor = highlight ? '#fca5a5' : (depType ? DEP_TYPE_TEXT[depType] ?? '#d1d5db' : '#d1d5db')

  return (
    <g>
      <rect
        x={x} y={y} width={NODE_W} height={NODE_H} rx={6}
        fill={fill} stroke={border} strokeWidth={highlight ? 1.5 : 1}
      />
      <text
        x={x + NODE_W / 2} y={y + NODE_H / 2 + 1}
        textAnchor="middle" dominantBaseline="middle"
        fontSize={11} fill={textColor} fontFamily="monospace"
      >
        {label.length > 16 ? label.slice(0, 15) + '…' : label}
      </text>
      {depType && (
        <text
          x={x + NODE_W / 2} y={y + NODE_H - 8}
          textAnchor="middle" dominantBaseline="middle"
          fontSize={8} fill={textColor} opacity={0.6} fontFamily="monospace"
        >
          {depType}
        </text>
      )}
    </g>
  )
}

function Arrow({ x1, y1, x2, y2 }: { x1: number; y1: number; x2: number; y2: number }) {
  return (
    <line
      x1={x1} y1={y1} x2={x2} y2={y2}
      stroke="#374151" strokeWidth={1.5}
      markerEnd="url(#arrowhead)"
    />
  )
}

export default function ServiceGraphView({ service, graph }: { service: string; graph: ServiceGraph }) {
  const callers = graph.depended_on_by
  const deps = graph.depends_on

  if (callers.length === 0 && deps.length === 0) return null

  const allCounts = [callers.length, 1, deps.length]
  const maxCount = Math.max(...allCounts, 1)
  const svgWidth = Math.max(400, maxCount * (NODE_W + H_GAP) + H_GAP * 2)

  const serviceX = (svgWidth - NODE_W) / 2
  const serviceCX = serviceX + NODE_W / 2
  const serviceCY_top = SERVICE_Y
  const serviceCY_bot = SERVICE_Y + NODE_H

  return (
    <section>
      <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-3">
        Service Dependency Graph
      </h2>
      <div className="rounded-lg border border-gray-800 bg-gray-950 p-2 overflow-x-auto">
        <svg width={svgWidth} height={SVG_H} className="mx-auto">
          <defs>
            <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="6" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" fill="#4b5563" />
            </marker>
          </defs>

          {/* Arrows: callers → service */}
          {callers.map((c, i) => {
            const cx = rowX(callers.length, i, svgWidth) + NODE_W / 2
            return <Arrow key={i} x1={cx} y1={CALLER_Y + NODE_H} x2={serviceCX} y2={serviceCY_top} />
          })}

          {/* Arrows: service → deps */}
          {deps.map((d, i) => {
            const cx = rowX(deps.length, i, svgWidth) + NODE_W / 2
            return <Arrow key={i} x1={serviceCX} y1={serviceCY_bot} x2={cx} y2={DEP_Y} />
          })}

          {/* Caller nodes */}
          {callers.map((c, i) => (
            <NodeBox
              key={i}
              x={rowX(callers.length, i, svgWidth)}
              y={CALLER_Y}
              label={c.name}
              depType={c.dep_type}
            />
          ))}

          {/* Service node (highlighted) */}
          <NodeBox x={serviceX} y={SERVICE_Y} label={service} highlight />

          {/* Dependency nodes */}
          {deps.map((d, i) => (
            <NodeBox
              key={i}
              x={rowX(deps.length, i, svgWidth)}
              y={DEP_Y}
              label={d.name}
              depType={d.dep_type}
            />
          ))}

          {/* Labels */}
          {callers.length > 0 && (
            <text x={8} y={CALLER_Y + NODE_H / 2 + 4} fontSize={9} fill="#6b7280" fontFamily="sans-serif">
              callers
            </text>
          )}
          {deps.length > 0 && (
            <text x={8} y={DEP_Y + NODE_H / 2 + 4} fontSize={9} fill="#6b7280" fontFamily="sans-serif">
              depends on
            </text>
          )}
        </svg>
      </div>
    </section>
  )
}
