"use client"

import { useWebSocket } from "@/hooks/useWebSocket"
import { TopBar } from "@/components/dashboard/TopBar"
import { PanopticonTable } from "@/components/dashboard/PanopticonTable"
import { LiveFeed } from "@/components/dashboard/LiveFeed"
import { AlertsStream } from "@/components/dashboard/AlertsStream"

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws/live'

export default function Dashboard() {
  const { trades, alerts, stats, isConnected } = useWebSocket(WS_URL)

  return (
    <div className="min-h-screen bg-zinc-950 p-4 sm:p-6">
      {/* Top Bar - Global Market Stats */}
      <TopBar stats={stats} isConnected={isConnected} />

      {/* Bento Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 sm:gap-6">
        {/* Left Panel - Main Content (Panopticon) */}
        <div className="lg:col-span-8 space-y-4 sm:space-y-6">
          <PanopticonTable trades={trades} />
        </div>

        {/* Right Panel - Live Feed + Alerts */}
        <div className="lg:col-span-4 grid grid-rows-2 gap-4 sm:gap-6">
          <LiveFeed trades={trades} />
          <AlertsStream alerts={alerts} />
        </div>
      </div>

      {/* Footer */}
      <div className="mt-6 text-center text-xs text-zinc-600">
        <p>
          ARGUS Command Center v2.0 • The All-Seeing Intelligence Layer
        </p>
      </div>
    </div>
  )
}
