# ARGUS Command Center - Frontend

The web frontend for ARGUS Command Center, built with Next.js 14, TypeScript, and Tailwind CSS.

## Features

- **Real-time Dashboard**: Live trade monitoring with WebSocket integration
- **The Panopticon**: High-performance trade table with sorting and filtering
- **Live Feed**: Real-time trade stream with alert highlighting
- **Intelligence Alerts**: Severity-based alert system with confidence scores
- **Responsive Design**: Mobile-first design that works on all devices

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Backend API running on `http://localhost:8000`

### Installation

```bash
# Install dependencies
npm install

# Run development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the dashboard.

### Environment Variables

Create a `.env.local` file in the `web` directory:

```bash
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/live
```

For production, use `wss://` for secure WebSocket connections.

## Project Structure

```
web/
├── app/                    # Next.js app directory
│   ├── page.tsx           # Main dashboard page
│   ├── layout.tsx         # Root layout
│   └── globals.css        # Global styles
├── components/
│   ├── dashboard/         # Dashboard components
│   │   ├── TopBar.tsx     # Top navigation bar
│   │   ├── PanopticonTable.tsx  # Main trade table
│   │   ├── LiveFeed.tsx   # Live trade feed
│   │   └── AlertsStream.tsx     # Alert stream
│   └── ui/                # Reusable UI components
├── hooks/
│   └── useWebSocket.ts    # WebSocket hook
└── lib/
    └── utils.ts           # Utility functions
```

## Tech Stack

- **Next.js 14**: React framework with App Router
- **TypeScript**: Type safety
- **Tailwind CSS**: Utility-first CSS
- **TanStack Table**: High-performance table component
- **Lucide React**: Icon library
- **WebSocket API**: Real-time data streaming

## Development

```bash
# Development server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Lint code
npm run lint
```

## Deployment

See the main [DEPLOYMENT.md](../DEPLOYMENT.md) for deployment instructions.

### Vercel Deployment

1. Push your code to GitHub
2. Import project in Vercel
3. Set environment variable `NEXT_PUBLIC_WS_URL` to your production WebSocket URL
4. Deploy!

## WebSocket Protocol

The frontend connects to the backend WebSocket endpoint at `/ws/live` and receives:

- **Init messages**: Initial data load with trades and alerts
- **Trade updates**: New trades as they occur
- **Alert updates**: Intelligence alerts from the engine
- **Stats updates**: Real-time statistics

See [README_WEB.md](../README_WEB.md) for detailed WebSocket protocol documentation.
