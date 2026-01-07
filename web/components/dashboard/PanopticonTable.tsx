"use client"

import { useMemo } from "react"
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { formatCurrency, formatTime, truncateAddress } from "@/lib/utils"
import { ArrowUpDown, Eye } from "lucide-react"
import { useState } from "react"

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

interface PanopticonTableProps {
  trades: Trade[]
}

export function PanopticonTable({ trades }: PanopticonTableProps) {
  const [sorting, setSorting] = useState<SortingState>([])

  const columns = useMemo<ColumnDef<Trade>[]>(
    () => [
      {
        accessorKey: "timestamp",
        header: ({ column }) => {
          return (
            <button
              className="flex items-center gap-1 hover:text-cyan-400 transition-colors"
              onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
            >
              TIME
              <ArrowUpDown className="w-3 h-3" />
            </button>
          )
        },
        cell: ({ row }) => (
          <span className="text-zinc-500 text-xs font-mono">
            {formatTime(row.original.timestamp)}
          </span>
        ),
        size: 80,
      },
      {
        accessorKey: "wallet_short",
        header: "WALLET",
        cell: ({ row }) => (
          <span className="text-cyan-400 font-mono text-xs">
            {row.original.wallet_short}
          </span>
        ),
        size: 120,
      },
      {
        accessorKey: "side",
        header: "SIDE",
        cell: ({ row }) => (
          <Badge variant={row.original.side === 'BUY' ? 'buy' : 'sell'}>
            {row.original.side}
          </Badge>
        ),
        size: 60,
      },
      {
        accessorKey: "outcome",
        header: "OUTCOME",
        cell: ({ row }) => (
          <span className="text-xs text-zinc-400">{row.original.outcome}</span>
        ),
        size: 60,
      },
      {
        accessorKey: "value_usd",
        header: ({ column }) => {
          return (
            <button
              className="flex items-center gap-1 hover:text-cyan-400 transition-colors"
              onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
            >
              VALUE
              <ArrowUpDown className="w-3 h-3" />
            </button>
          )
        },
        cell: ({ row }) => (
          <span className={`font-bold ${
            row.original.value_usd > 1000 ? 'text-emerald-400' : 'text-zinc-300'
          }`}>
            {formatCurrency(row.original.value_usd)}
          </span>
        ),
        size: 100,
      },
      {
        accessorKey: "market",
        header: "MARKET",
        cell: ({ row }) => (
          <div className="flex items-center gap-2">
            {row.original.is_alert && (
              <span className="text-amber-400 text-xs">🚨</span>
            )}
            <span className="text-xs text-zinc-300 truncate max-w-[300px]">
              {row.original.market}
            </span>
          </div>
        ),
      },
    ],
    []
  )

  const table = useReactTable({
    data: trades,
    columns,
    state: {
      sorting,
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <Card className="glass-panel border-red-900/30 overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-red-400 flex items-center gap-2">
            <Eye className="w-5 h-5" />
            THE PANOPTICON
          </CardTitle>
          <span className="text-xs text-zinc-500">
            Last {trades.length} trades • Live updates
          </span>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-zinc-900/50 border-b border-zinc-800">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th
                      key={header.id}
                      className="px-4 py-3 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider"
                      style={{ width: header.column.columnDef.size }}
                    >
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody className="divide-y divide-zinc-800/50">
              {table.getRowModel().rows.length === 0 ? (
                <tr>
                  <td
                    colSpan={columns.length}
                    className="px-4 py-8 text-center text-zinc-600"
                  >
                    Awaiting live data...
                  </td>
                </tr>
              ) : (
                table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    className={`hover:bg-zinc-900/30 transition-colors ${
                      row.original.is_alert ? 'bg-amber-900/10' : ''
                    }`}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-4 py-3">
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext()
                        )}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}
