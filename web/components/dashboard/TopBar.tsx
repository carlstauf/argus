"use client"

import { formatCurrency, formatNumber } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Eye, Activity } from "lucide-react"

interface TopBarProps {
  stats: {
    total_wallets: number
    total_trades: number
    active_markets: number
    unread_alerts: number
    total_volume_usd: number
  } | null
  isConnected: boolean
}

export function TopBar({ stats, isConnected }: TopBarProps) {
  return (
    <div className="glass-panel flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
      {/* ARGUS Branding */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <Eye className="w-6 h-6 text-cyan-400" />
          <h1 className="text-2xl font-bold tracking-tight text-cyan-400">
            ARGUS
          </h1>
        </div>
        <div className="text-sm text-zinc-500 hidden sm:block">
          Command Center
        </div>
      </div>

      {/* Global Market Stats - Scrolling Ticker */}
      <div className="flex items-center gap-4 sm:gap-6 overflow-x-auto flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-xs text-zinc-500 whitespace-nowrap">MARKETS</span>
          <span className="text-lg font-bold text-cyan-400 whitespace-nowrap">
            {stats ? formatNumber(stats.active_markets) : '---'}
          </span>
        </div>

        <div className="h-6 w-px bg-zinc-800 flex-shrink-0" />

        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-xs text-zinc-500 whitespace-nowrap">VOLUME</span>
          <span className="text-lg font-bold text-emerald-400 whitespace-nowrap">
            {stats ? formatCurrency(stats.total_volume_usd) : '---'}
          </span>
        </div>

        <div className="h-6 w-px bg-zinc-800 flex-shrink-0 hidden sm:block" />

        <div className="flex items-center gap-2 flex-shrink-0 hidden sm:flex">
          <span className="text-xs text-zinc-500 whitespace-nowrap">WALLETS</span>
          <span className="text-lg font-bold whitespace-nowrap">
            {stats ? formatNumber(stats.total_wallets) : '---'}
          </span>
        </div>

        <div className="h-6 w-px bg-zinc-800 flex-shrink-0 hidden md:block" />

        <div className="flex items-center gap-2 flex-shrink-0 hidden md:flex">
          <span className="text-xs text-zinc-500 whitespace-nowrap">TRADES</span>
          <span className="text-lg font-bold whitespace-nowrap">
            {stats ? formatNumber(stats.total_trades) : '---'}
          </span>
        </div>

        <div className="h-6 w-px bg-zinc-800 flex-shrink-0 hidden lg:block" />

        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-xs text-zinc-500 whitespace-nowrap">ALERTS</span>
          <Badge variant={stats && stats.unread_alerts > 0 ? "alert" : "outline"}>
            {stats ? stats.unread_alerts : 0}
          </Badge>
        </div>
      </div>

      {/* Connection Status */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <Activity
          className={`w-4 h-4 ${
            isConnected ? 'text-emerald-400 animate-pulse' : 'text-zinc-600'
          }`}
        />
        <span className={`text-xs whitespace-nowrap ${isConnected ? 'text-emerald-400' : 'text-zinc-600'}`}>
          {isConnected ? 'LIVE' : 'OFFLINE'}
        </span>
      </div>
    </div>
  )
}
