# ARGUS Command Center - Deployment Guide

## Quick Start (Development)

### Automated Startup
```bash
./start_web.sh
```

This will start both backend and frontend automatically.

### Manual Startup

**Terminal 1 - Backend:**
```bash
cd api
python server.py
```

**Terminal 2 - Frontend:**
```bash
cd web
npm run dev
```

Then open `http://localhost:3000`

---

## Production Deployment

### Backend (FastAPI)

#### Option 1: Docker
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY api/requirements.txt .
RUN pip install -r requirements.txt

COPY src ./src
COPY api ./api

CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t argus-backend .
docker run -p 8000:8000 --env-file .env argus-backend
```

#### Option 2: Cloud Platform (Heroku, Railway, Render)

**Procfile:**
```
web: uvicorn api.server:app --host 0.0.0.0 --port $PORT
```

**Environment Variables:**
- `DATABASE_URL` - PostgreSQL connection string
- `FRESH_WALLET_HOURS` - Alert threshold (default: 72)
- `WHALE_THRESHOLD_USD` - Large trade threshold (default: 1000)

#### Option 3: VPS with Systemd

**systemd service file** (`/etc/systemd/system/argus-backend.service`):
```ini
[Unit]
Description=ARGUS Command Center Backend
After=network.target postgresql.service

[Service]
Type=simple
User=argus
WorkingDirectory=/opt/argus
Environment="PATH=/opt/argus/venv/bin"
ExecStart=/opt/argus/venv/bin/uvicorn api.server:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable argus-backend
sudo systemctl start argus-backend
```

---

### Frontend (Next.js)

#### Option 1: Vercel (Recommended)

1. Push code to GitHub
2. Import project in Vercel
3. Set environment variables:
   - `NEXT_PUBLIC_WS_URL=wss://your-backend.com/ws/live`
   - `NEXT_PUBLIC_API_URL=https://your-backend.com/api`
4. Deploy

#### Option 2: Netlify

```bash
cd web
npm run build
```

Deploy the `.next` directory.

#### Option 3: Self-Hosted with PM2

```bash
cd web
npm run build

# Install PM2
npm install -g pm2

# Start Next.js
pm2 start npm --name "argus-frontend" -- start

# Save PM2 config
pm2 save
pm2 startup
```

#### Option 4: Docker

```dockerfile
FROM node:18-alpine

WORKDIR /app
COPY web/package*.json ./
RUN npm ci --only=production

COPY web .
RUN npm run build

CMD ["npm", "start"]
```

---

## Database Setup (PostgreSQL)

### Local Development
```bash
# Install PostgreSQL
brew install postgresql  # macOS
sudo apt install postgresql  # Ubuntu

# Create database
createdb argus

# Initialize schema
python argus.py init
```

### Production (Managed PostgreSQL)

Recommended providers:
- **Supabase** (free tier available)
- **Neon** (serverless PostgreSQL)
- **AWS RDS**
- **DigitalOcean Managed Database**

Update `.env` with connection string:
```
DATABASE_URL=postgresql://user:password@host:5432/argus?sslmode=require
```

---

## SSL/TLS Configuration

### Backend (HTTPS + WSS)

#### Using Nginx as Reverse Proxy

```nginx
server {
    listen 443 ssl http2;
    server_name api.argus.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # REST API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket
    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### Frontend

Update `.env.local`:
```
NEXT_PUBLIC_WS_URL=wss://api.argus.example.com/ws/live
NEXT_PUBLIC_API_URL=https://api.argus.example.com/api
```

---

## Monitoring & Logging

### Backend Logs
```bash
# Using systemd
sudo journalctl -u argus-backend -f

# Using PM2
pm2 logs argus-backend
```

### Frontend Logs
```bash
pm2 logs argus-frontend
```

### Health Checks

**Backend:**
```bash
curl http://localhost:8000/
```

**WebSocket:**
```bash
wscat -c ws://localhost:8000/ws/live
```

---

## Performance Optimization

### Backend
- Enable gzip compression in Uvicorn
- Use connection pooling for PostgreSQL
- Cache market stats with Redis (optional)

### Frontend
- Enable Next.js Image Optimization
- Use CDN for static assets
- Enable HTTP/2

### Database
- Create indexes on frequently queried columns:
```sql
CREATE INDEX idx_trades_executed_at ON trades(executed_at DESC);
CREATE INDEX idx_trades_wallet ON trades(wallet_address);
CREATE INDEX idx_alerts_created_at ON alerts(created_at DESC);
```

---

## Security Checklist

- [ ] Use environment variables for secrets
- [ ] Enable HTTPS/WSS in production
- [ ] Configure CORS properly in `server.py`
- [ ] Set up database backups
- [ ] Enable rate limiting (optional)
- [ ] Use strong PostgreSQL passwords
- [ ] Keep dependencies updated

---

## Scaling

### Horizontal Scaling

**Backend:**
- Run multiple Uvicorn workers
- Use load balancer (Nginx, HAProxy)
- Share WebSocket connections via Redis Pub/Sub

**Frontend:**
- Deploy to CDN edge locations
- Use Next.js ISR for static pages

**Database:**
- Use read replicas for queries
- Partition large tables by date

---

## Troubleshooting

### WebSocket Connection Issues
1. Check CORS settings in `server.py`
2. Verify WebSocket URL uses `ws://` (dev) or `wss://` (prod)
3. Check firewall rules for port 8000

### Database Connection Errors
1. Verify `DATABASE_URL` is correct
2. Check PostgreSQL is running
3. Ensure database user has proper permissions

### Frontend Build Errors
1. Clear Next.js cache: `rm -rf web/.next`
2. Reinstall dependencies: `cd web && npm ci`
3. Check TypeScript errors: `npm run build`

---

## Environment Variables Reference

### Backend (.env)
```bash
DATABASE_URL=postgresql://user:pass@host:5432/argus
FRESH_WALLET_HOURS=72
WHALE_THRESHOLD_USD=1000
ANOMALY_SIGMA=2.0
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/live
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

---

## Backup & Recovery

### Database Backup
```bash
pg_dump argus > backup_$(date +%Y%m%d).sql
```

### Restore
```bash
psql argus < backup_20240101.sql
```

### Automated Backups (Cron)
```bash
0 2 * * * pg_dump argus | gzip > /backups/argus_$(date +\%Y\%m\%d).sql.gz
```

---

For more information, see `README_WEB.md`
