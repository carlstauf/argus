"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { formatTime } from "@/lib/utils"
import { AlertTriangle, Bell } from "lucide-react"

interface Alert {
  id: string
  type: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  title: string
  description: string
  confidence: number
  wallet: string
  timestamp: string
}

interface AlertsStreamProps {
  alerts: Alert[]
}

const severityConfig = {
  CRITICAL: {
    color: 'text-red-400',
    bg: 'bg-red-900/20',
    border: 'border-red-800/50',
    icon: '🔴',
  },
  HIGH: {
    color: 'text-amber-400',
    bg: 'bg-amber-900/20',
    border: 'border-amber-800/50',
    icon: '🟡',
  },
  MEDIUM: {
    color: 'text-blue-400',
    bg: 'bg-blue-900/20',
    border: 'border-blue-800/50',
    icon: '🔵',
  },
  LOW: {
    color: 'text-zinc-400',
    bg: 'bg-zinc-900/20',
    border: 'border-zinc-800/50',
    icon: '⚪',
  },
}

export function AlertsStream({ alerts }: AlertsStreamProps) {
  return (
    <Card className="glass-panel h-full flex flex-col overflow-hidden border-amber-900/30">
      <CardHeader className="pb-3">
        <CardTitle className="text-amber-400 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5" />
          INTELLIGENCE ALERTS
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto p-4 space-y-3">
        {alerts.length === 0 ? (
          <div className="text-center text-zinc-600 py-8">
            <Bell className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <div className="text-sm">No alerts detected</div>
          </div>
        ) : (
          alerts.map((alert) => {
            const config = severityConfig[alert.severity] || severityConfig.LOW

            return (
              <div
                key={alert.id}
                className={`p-3 rounded-lg border transition-all hover:border-zinc-700 ${config.bg} ${config.border}`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm">{config.icon}</span>
                    <Badge variant="outline" className="text-xs">
                      {alert.severity}
                    </Badge>
                  </div>
                  <span className="text-xs text-zinc-500">
                    {formatTime(alert.timestamp)}
                  </span>
                </div>

                <div className="space-y-2">
                  <div className={`text-sm font-semibold ${config.color}`}>
                    {alert.title}
                  </div>

                  <div className="text-xs text-zinc-400 line-clamp-3">
                    {alert.description}
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t border-zinc-800/50">
                    <div className="text-xs text-zinc-500 font-mono">
                      {alert.wallet.slice(0, 10)}...
                    </div>
                    <div className="text-xs text-zinc-500">
                      Confidence: {(alert.confidence * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </CardContent>
    </Card>
  )
}
