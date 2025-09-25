# The Tower - View | Multi-Server Media Monitoring & Management Platform

A comprehensive media server monitoring and management application for Plex, Emby, and Jellyfin servers. The Tower - View provides real-time session monitoring, user management, server analytics, and Docker container control through a unified dashboard designed for administrators and support staff.

## 🎯 Features

### Core Features
- **🔗 Multi-Server Support**: Monitor multiple Plex, Emby, and Jellyfin servers from a single interface
- **🔐 Dual Authentication**: Admin and local user authentication with permission-based access control
- **⚡ Real-time Monitoring**: Live session tracking with WebSocket updates or configurable polling
- **🎛️ Admin Controls**: Terminate sessions and manage user access across servers
- **📊 Advanced Analytics**: Real-time CPU, Memory, and GPU monitoring with background metrics caching
- **🌐 Modern UI**: Responsive dark-themed design optimized for monitoring workflows

### New Advanced Features
- **🚀 Background Metrics Caching**: Instant metrics loading with automatic background collection every 2 seconds
- **👥 Permission-Based Access Control**: Granular permissions for local users
  - View Analytics, Sessions, Users, Audit Logs
  - Manage Users, Servers, Settings
  - Terminate Sessions
- **🔒 Case-Insensitive Usernames**: Enhanced user experience with case-insensitive login (passwords remain case-sensitive)
- **🔄 Forced Password Changes**: Security feature requiring password changes on first login
- **📈 Portainer Integration**: Docker container metrics and control with API token authentication
- **⚙️ Netdata Cloud Integration**: Advanced server monitoring capabilities
- **🎨 Dark Theme UI**: Consistent dark theme across all modals and components
- **📱 Responsive Server Cards**: Visual server status with inline metrics and controls

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend │    │  FastAPI Backend │    │ Background Tasks │
│  (Vite + TS)    │◄──►│  (PostgreSQL)   │◄──►│ (Metrics Cache)  │
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
git clone https://github.com/ellermw/TowerView.git
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
   - Password: `admin` (you will be forced to change this)
3. Navigate to Settings to configure:
   - Portainer integration with API token for server metrics
   - Container mappings for Docker control
   - Netdata Cloud integration (optional)
4. Add your media servers in the Servers section
5. Create local users with specific permissions for support staff

## 📁 Project Structure

```
TowerView/
├── backend/                 # FastAPI backend application
│   ├── app/
│   │   ├── api/            # API routes
│   │   │   └── routes/     # Organized route modules
│   │   │       ├── admin.py
│   │   │       ├── auth.py
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
│   │       ├── netdata_cloud_service.py
│   │       └── metrics_cache_service.py
│   ├── alembic/            # Database migrations
│   └── requirements.txt
├── frontend/                # React frontend (Vite + TypeScript)
│   ├── src/
│   │   ├── components/     # React components
│   │   │   ├── admin/      # Admin components
│   │   │   │   ├── AdminHome.tsx
│   │   │   │   ├── ServerManagement.tsx
│   │   │   │   ├── ServerStatsRealTime.tsx
│   │   │   │   ├── SessionsList.tsx
│   │   │   │   ├── UsersList.tsx
│   │   │   │   ├── LocalUsersManagement.tsx
│   │   │   │   └── Settings.tsx
│   │   │   ├── Layout.tsx
│   │   │   └── ErrorBoundary.tsx
│   │   ├── hooks/          # Custom React hooks
│   │   │   ├── useWebSocketMetrics.ts
│   │   │   └── usePermissions.ts
│   │   ├── pages/          # Page components
│   │   ├── services/       # API services
│   │   ├── store/          # State management (Zustand)
│   │   └── utils/          # Utilities
│   ├── package.json
│   └── vite.config.ts
├── nginx/                   # Nginx configuration
│   └── nginx.conf          # WebSocket-enabled config
├── docker-compose.yml       # Development environment
└── .env.example            # Environment template
```

## 🛡️ Permissions System

Local users can be granted specific permissions:

- **View Analytics**: Access to dashboard analytics
- **View Sessions**: View active media sessions
- **Terminate Sessions**: Ability to stop active sessions
- **View Users**: View media user list
- **Manage Users**: Create/edit/delete local users
- **Manage Servers**: Start/stop/restart servers (create/delete is admin-only)
- **View Audit Logs**: Access to audit trail
- **Manage Settings**: Configure system settings

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
# Services: backend, frontend, db, redis, nginx

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
ADMIN_PASSWORD=admin  # You will be forced to change this

# Frontend (if using custom API URL)
VITE_API_URL=  # Leave empty for default proxy
```

### Portainer Integration

1. Install Portainer on your Docker host
2. Generate an API token in Portainer
3. Configure in The Tower - View Settings:
   - Portainer URL: `https://portainer.your-domain.com`
   - API Token: Your generated token
   - Enable "Use API Token" option
   - Map containers to media servers

### Background Metrics Collection

The application automatically collects metrics in the background every 2 seconds:
- Metrics are cached in memory for instant access
- All users share the same cached data for efficiency
- No duplicate API calls or rate limiting issues
- WebSocket connections receive cached data in real-time

## 📊 API Endpoints

### Core Endpoints
- `POST /api/auth/login` - User authentication (admin/local)
- `GET /api/admin/servers` - List all servers
- `GET /api/admin/sessions` - List active sessions
- `DELETE /api/admin/sessions/{id}/terminate` - Terminate session
- `GET /api/admin/users` - List media users
- `GET /api/admin/local-users` - Manage local users

### Settings & Metrics
- `GET /api/settings/portainer/metrics/{server_id}` - Get cached server metrics
- `POST /api/settings/portainer/container/{server_id}/action` - Container control
- `GET /api/settings/portainer/containers` - List Docker containers
- `POST /api/settings/portainer/auth` - Configure Portainer

### WebSocket
- `WS /api/ws/metrics` - Real-time metrics streaming from cache

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
- **RBAC**: Role-based access (admin, local user with permissions)
- **Case-Insensitive Usernames**: Better UX while maintaining password security
- **Forced Password Changes**: Security policy for initial logins
- **Rate Limiting**: Configured in nginx
- **CORS Protection**: Restrictive CORS policies
- **SQL Injection Protection**: SQLAlchemy ORM with parameterized queries
- **XSS Protection**: React's built-in XSS protection
- **Secure Headers**: Security headers configured in nginx

## 🐛 Troubleshooting

### Metrics Not Loading
- Ensure Portainer is configured in Settings with API token
- Check container mappings are correct
- Verify Portainer API token is valid
- Check backend logs: `docker-compose logs -f backend`

### WebSocket Connection Issues
- Access the app through nginx (port 8080), not direct (port 3002)
- Check browser console for WebSocket errors
- Ensure nginx is running: `docker ps | grep nginx`

### Container Control Not Working
- Verify Portainer integration in Settings
- Check user has appropriate permissions
- Ensure Docker socket is accessible to Portainer

### Local User Login Issues
- Usernames are case-insensitive (MikeTest = miketest)
- Passwords remain case-sensitive
- Ensure "Local User" tab is selected on login page

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