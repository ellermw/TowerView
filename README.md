# TowerView - Multi-Server Media Monitoring & Management Platform

A comprehensive media server monitoring and management application for Plex, Emby, and Jellyfin servers. TowerView provides real-time session monitoring, user management, server analytics, and Docker container control through a unified dashboard.

## 🎯 Features

### Core Features
- **🔗 Multi-Server Support**: Monitor multiple Plex, Emby, and Jellyfin servers from a single interface
- **🔐 Dual Authentication**: Admin login and media user login using provider credentials
- **⚡ Real-time Monitoring**: Live session tracking with configurable polling or WebSocket updates
- **🎛️ Admin Controls**: Terminate sessions and manage user access across servers
- **📊 User Dashboard**: Personal watch history and statistics for media users
- **🌐 Modern UI**: Responsive design with dark mode support

### New Advanced Features
- **📈 Server Analytics**: Real-time CPU, Memory, and GPU usage monitoring via Portainer integration
- **🐳 Docker Container Control**: Start, stop, and restart media server containers directly from the UI
- **🔄 Dual Update Modes**: Choose between WebSocket (real-time) or polling (2-second intervals)
- **🗂️ Unified Server Management**: Combined server list and analytics view grouped by server type
- **👥 Local User Management**: Create and manage local application users with permissions
- **⚙️ Settings Integration**: Configure Portainer, Netdata Cloud, and container mappings
- **📱 Responsive Server Cards**: Visual server status with inline metrics and controls
- **🎨 Server Type Theming**: Color-coded server cards by type (Plex/Emby/Jellyfin)

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend │    │  FastAPI Backend │    │ Background Worker│
│  (Vite + TS)    │◄──►│  (PostgreSQL)   │◄──►│   (Celery)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         └──────────────►│     Redis       │◄─────────────┘
                        │ (Cache/Queue)   │
                        └─────────────────┘
                                 │
                        ┌─────────────────┐
                        │     Nginx       │
                        │ (Reverse Proxy) │
                        └─────────────────┘
                                 │
                ┌────────────────┴────────────────┐
                │                                 │
        ┌─────────────────┐            ┌─────────────────┐
        │  Media Servers  │            │   Portainer     │
        │Plex/Emby/Jellyfin│           │ (Docker Mgmt)   │
        └─────────────────┘            └─────────────────┘
```

## 🚀 Quick Start

### Using Docker Compose (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/TowerView.git
cd TowerView

# 2. Configure environment
cp .env.example .env
# Edit .env with your configuration

# 3. Start the application
docker-compose up -d

# 4. Access the application
# Through nginx (WebSocket support): http://localhost:8080
# Direct frontend access: http://localhost:3002
# Backend API: http://localhost:8000
# API Documentation: http://localhost:8000/docs
```

### First-Time Setup

1. Access the application at `http://localhost:8080`
2. Login with default credentials:
   - Username: `admin`
   - Password: `admin` (change immediately)
3. Navigate to Settings to configure:
   - Portainer integration for server metrics
   - Container mappings for Docker control
4. Add your media servers in the Servers section

## 📁 Project Structure

```
TowerView/
├── backend/                 # FastAPI backend application
│   ├── app/
│   │   ├── api/            # API routes
│   │   │   └── routes/     # Organized route modules
│   │   │       ├── admin.py
│   │   │       ├── auth.py
│   │   │       ├── media_user.py
│   │   │       ├── settings.py
│   │   │       └── websocket.py
│   │   ├── core/           # Core functionality
│   │   │   ├── auth.py
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── security.py
│   │   │   └── token_cache.py
│   │   ├── models/         # SQLAlchemy models
│   │   │   ├── server.py
│   │   │   ├── session.py
│   │   │   ├── user.py
│   │   │   ├── settings.py
│   │   │   └── user_permission.py
│   │   ├── providers/      # Media server connectors
│   │   │   ├── plex.py
│   │   │   ├── emby.py
│   │   │   └── jellyfin.py
│   │   ├── schemas/        # Pydantic schemas
│   │   └── services/       # Business logic
│   │       ├── auth_service.py
│   │       ├── portainer_service.py
│   │       ├── netdata_service.py
│   │       └── netdata_cloud_service.py
│   ├── alembic/            # Database migrations
│   └── requirements.txt
├── frontend/                # React frontend (Vite + TypeScript)
│   ├── src/
│   │   ├── components/     # React components
│   │   │   ├── admin/      # Admin components
│   │   │   │   ├── AdminHome.tsx
│   │   │   │   ├── UnifiedServerManagement.tsx
│   │   │   │   ├── ServerStatsRealTime.tsx
│   │   │   │   ├── ServerModal.tsx
│   │   │   │   ├── SessionsList.tsx
│   │   │   │   ├── UsersList.tsx
│   │   │   │   ├── LocalUsersManagement.tsx
│   │   │   │   └── Settings.tsx
│   │   │   └── Layout.tsx
│   │   ├── hooks/          # Custom React hooks
│   │   │   └── useWebSocketMetrics.ts
│   │   ├── pages/          # Page components
│   │   ├── services/       # API services
│   │   ├── store/          # State management (Zustand)
│   │   └── utils/          # Utilities
│   ├── package.json
│   └── vite.config.ts
├── worker/                  # Background worker
│   └── worker/
│       ├── tasks.py        # Celery tasks
│       └── celery_app.py
├── nginx/                   # Nginx configuration
│   └── nginx.conf          # WebSocket-enabled config
├── docker-compose.yml       # Development environment
└── .env.example            # Environment template
```

## 🛠️ Development

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (for local frontend development)
- Python 3.11+ (for local backend development)

### Development Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f [service]
# Services: backend, frontend, worker, worker-beat, db, redis, nginx

# Rebuild after changes
docker-compose build [service]
docker-compose restart [service]

# Database operations
docker exec towerview-backend-1 alembic upgrade head  # Run migrations
docker exec towerview-backend-1 alembic revision --autogenerate -m "description"  # Create migration

# Shell access
docker exec -it towerview-backend-1 bash
docker exec -it towerview-frontend-1 sh

# Stop all services
docker-compose down
```

## 🔧 Configuration

### Environment Variables

Key configuration in `.env`:

```bash
# Database
DATABASE_URL=postgresql://mediaapp:change_me@db:5432/mediaapp

# Redis
REDIS_URL=redis://redis:6379

# Security
SECRET_KEY=your-very-secure-secret-key-here
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin  # Change in production!

# Frontend (if using custom API URL)
VITE_API_URL=  # Leave empty for default proxy
```

### Portainer Integration

1. Install Portainer on your Docker host
2. Generate an API token in Portainer
3. Configure in TowerView Settings:
   - Portainer URL: `https://portainer.your-domain.com`
   - API Token: Your generated token
   - Map containers to media servers

### WebSocket vs Polling Mode

- **Polling Mode (Default)**: Updates every 2 seconds, works everywhere
- **WebSocket Mode**: Real-time updates at 500ms intervals
  - Requires access through nginx (port 8080)
  - Enable by clicking the mode toggle in server cards

## 📊 API Endpoints

### Core Endpoints
- `POST /api/auth/login` - User authentication
- `GET /api/admin/servers` - List all servers
- `GET /api/admin/sessions` - List active sessions
- `DELETE /api/admin/sessions/{id}/terminate` - Terminate session
- `GET /api/admin/users` - List media users

### Settings & Metrics
- `GET /api/settings/portainer/metrics/{server_id}` - Get server metrics
- `POST /api/settings/portainer/container/{server_id}/action` - Container control
- `GET /api/settings/portainer/containers` - List Docker containers
- `POST /api/settings/portainer/auth` - Configure Portainer

### WebSocket
- `WS /api/ws/metrics` - Real-time metrics streaming

## 🚢 Production Deployment

### Using Docker Compose

```bash
# 1. Configure production environment
cp .env.example .env.prod
# Edit with production values

# 2. Generate secure secrets
openssl rand -base64 32  # For SECRET_KEY

# 3. Update docker-compose.yml for production
# - Remove volume mounts for source code
# - Set restart policies
# - Configure SSL in nginx

# 4. Deploy
docker-compose -f docker-compose.prod.yml up -d

# 5. Set up SSL with Let's Encrypt
# Configure nginx with SSL certificates
```

### Nginx WebSocket Configuration

The included nginx configuration supports WebSocket connections for real-time updates:

```nginx
location /api/ws/ {
    proxy_pass http://backend/api/ws/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 86400s;
}
```

## 🔐 Security Features

- **Encrypted Credentials**: All provider credentials encrypted with Fernet
- **JWT Authentication**: Secure token-based auth with refresh tokens
- **RBAC**: Role-based access (admin, media user, local user)
- **Rate Limiting**: Configured in nginx
- **CORS Protection**: Restrictive CORS policies
- **SQL Injection Protection**: SQLAlchemy ORM with parameterized queries
- **XSS Protection**: React's built-in XSS protection
- **Secure Headers**: Security headers configured in nginx

## 🐛 Troubleshooting

### Metrics Not Loading
- Ensure Portainer is configured in Settings
- Check container mappings are correct
- Verify Portainer API token is valid
- Check browser console for errors

### WebSocket Connection Issues
- Access the app through nginx (port 8080), not direct (port 3002)
- Check browser console for WebSocket errors
- Ensure nginx is running: `docker ps | grep nginx`

### Container Control Not Working
- Verify Portainer integration in Settings
- Check user has admin permissions
- Ensure Docker socket is accessible to Portainer

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) for the excellent backend framework
- [React](https://reactjs.org/) and [Vite](https://vitejs.dev/) for the frontend
- [TailwindCSS](https://tailwindcss.com/) for styling
- [Portainer](https://www.portainer.io/) for Docker management
- [Plex](https://www.plex.tv/), [Emby](https://emby.media/), and [Jellyfin](https://jellyfin.org/) for their APIs