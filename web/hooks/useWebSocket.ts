"use client"

import { useEffect, useRef, useState, useCallback } from 'react'

interface Trade {
  tx_hash: string
  wallet: string
  wallet_short: string
  side: 'BUY' | 'SELL'
  outcome: string
  size: number
  price: number
  value_usd: number
  market: string
  timestamp: string
  is_alert: boolean
}

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

interface Stats {
  total_wallets: number
  total_trades: number
  active_markets: number
  unread_alerts: number
  total_volume_usd: number
}

interface WebSocketMessage {
  type: 'init' | 'trade' | 'alert' | 'stats' | 'pong'
  trades?: Trade[]
  alerts?: Alert[]
  data?: any
}

interface UseWebSocketReturn {
  trades: Trade[]
  alerts: Alert[]
  stats: Stats | null
  isConnected: boolean
  reconnect: () => void
}

export function useWebSocket(url: string): UseWebSocketReturn {
  const [trades, setTrades] = useState<Trade[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [isConnected, setIsConnected] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>()
  const reconnectAttempts = useRef(0)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    try {
      const ws = new WebSocket(url)

      ws.onopen = () => {
        console.log('[WS] Connected to ARGUS Command Center')
        setIsConnected(true)
        reconnectAttempts.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)

          switch (message.type) {
            case 'init':
              // Initial data load
              if (message.trades) {
                setTrades(message.trades)
              }
              if (message.alerts) {
                setAlerts(message.alerts)
              }
              break

            case 'trade':
              // New trade received
              setTrades((prev) => [message.data, ...prev].slice(0, 100))
              break

            case 'alert':
              // New alert received
              setAlerts((prev) => [message.data, ...prev].slice(0, 50))
              break

            case 'stats':
              // Stats update
              setStats(message.data)
              break

            case 'pong':
              // Heartbeat response
              break

            default:
              console.log('[WS] Unknown message type:', message.type)
          }
        } catch (error) {
          console.error('[WS] Failed to parse message:', error)
        }
      }

      ws.onerror = (error) => {
        console.error('[WS] WebSocket error:', error)
      }

      ws.onclose = () => {
        console.log('[WS] Disconnected from ARGUS Command Center')
        setIsConnected(false)

        // Attempt reconnection with exponential backoff
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
        reconnectAttempts.current++

        console.log(`[WS] Reconnecting in ${delay}ms...`)
        reconnectTimeoutRef.current = setTimeout(connect, delay)
      }

      wsRef.current = ws
    } catch (error) {
      console.error('[WS] Failed to connect:', error)
    }
  }, [url])

  const reconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
    }
    reconnectAttempts.current = 0
    connect()
  }, [connect])

  useEffect(() => {
    connect()

    // Heartbeat ping every 30 seconds
    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping')
      }
    }, 30000)

    return () => {
      clearInterval(pingInterval)
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [connect])

  return {
    trades,
    alerts,
    stats,
    isConnected,
    reconnect,
  }
}
