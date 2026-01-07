"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { formatCurrency, formatTime } from "@/lib/utils"
import { Activity } from "lucide-react"

interface Trade {
  tx_hash: string
  wallet_short: string
  side: 'BUY' | 'SELL'
  outcome: string
  value_usd: number
  market: string
  timestamp: string
  is_alert: boolean
}

interface LiveFeedProps {
  trades: Trade[]
}

export function LiveFeed({ trades }: LiveFeedProps) {
  return (
    <Card className="glass-panel h-full flex flex-col overflow-hidden border-emerald-900/30">
      <CardHeader className="pb-3">
        <CardTitle className="text-emerald-400 flex items-center gap-2">
          <Activity className="w-5 h-5 animate-pulse" />
          LIVE FEED
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto p-4 space-y-2">
        {trades.length === 0 ? (
          <div className="text-center text-zinc-600 py-8">
            Awaiting live trades...
          </div>
        ) : (
          trades.slice(0, 20).map((trade) => (
            <div
              key={trade.tx_hash}
              className={`p-3 rounded-lg border transition-all hover:border-zinc-700 ${
                trade.is_alert
                  ? 'bg-amber-900/20 border-amber-800/50'
                  : 'bg-zinc-900/30 border-zinc-800/50'
              }`}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Badge variant={trade.side === 'BUY' ? 'buy' : 'sell'} className="text-xs">
                    {trade.side}
                  </Badge>
                  <span className="text-xs text-zinc-500">
                    {formatTime(trade.timestamp)}
                  </span>
                </div>
                <span className={`text-sm font-bold ${
                  trade.value_usd > 1000 ? 'text-emerald-400' : 'text-zinc-300'
                }`}>
                  {formatCurrency(trade.value_usd)}
                </span>
              </div>

              <div className="space-y-1">
                <div className="text-xs text-zinc-400 font-mono">
                  {trade.wallet_short}
                </div>
                <div className="text-xs text-zinc-300 line-clamp-2">
                  {trade.market}
                </div>
              </div>

              {trade.is_alert && (
                <div className="mt-2 text-xs text-amber-400 flex items-center gap-1">
                  🚨 Alert triggered
                </div>
              )}
            </div>
          ))
        )}
      </CardContent>
    </Card>
  )
}
