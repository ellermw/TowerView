# TowerView - Multi-Server Media Monitoring

A comprehensive media server monitoring and management application for Plex, Emby, and Jellyfin servers. TowerView provides real-time session monitoring, user management, and analytics across multiple media servers from a single dashboard.

## 🎯 Features

- **🔗 Multi-Server Support**: Monitor multiple Plex, Emby, and Jellyfin servers from a single interface
- **🔐 Dual Authentication**: Admin login and media user login using provider credentials
- **⚡ Real-time Monitoring**: Live session tracking with WebSocket updates
- **🎛️ Admin Controls**: Terminate sessions and manage user access across servers
- **📊 User Dashboard**: Personal watch history and statistics for media users
- **📁 Server Grouping**: Organize servers into logical groups
- **📋 Audit Logging**: Track all administrative actions
- **🔒 Encrypted Credentials**: Secure storage of provider credentials
- **🌐 Modern UI**: Responsive design with dark mode support

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend │    │  FastAPI Backend │    │ Background Worker│
│  (TailwindCSS)  │◄──►│  (PostgreSQL)   │◄──►│   (Celery)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         └──────────────►│     Redis       │◄─────────────┘
                        │ (Cache/Queue)   │
                        └─────────────────┘
                                 │
                        ┌─────────────────┐
                        │  Media Servers  │
                        │ Plex/Emby/Jellyfin│
                        └─────────────────┘
```

## 🚀 Quick Start

### Option 1: Automated Setup (Recommended)

```bash
git clone <repository-url>
cd towerview
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### Option 2: Manual Setup

```bash
# 1. Clone and setup environment
git clone <repository-url>
cd towerview
cp .env.example .env
# Edit .env with your configuration

# 2. Start with Docker Compose
make dev

# 3. Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## 📁 Project Structure

```
towerview/
├── backend/              # FastAPI backend application
│   ├── app/
│   │   ├── api/         # API routes
│   │   ├── core/        # Core functionality (auth, config, database)
│   │   ├── models/      # SQLAlchemy models
│   │   ├── providers/   # Media server connectors
│   │   ├── schemas/     # Pydantic schemas
│   │   └── services/    # Business logic
│   ├── alembic/         # Database migrations
│   └── requirements.txt
├── frontend/             # React frontend application
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── pages/       # Page components
│   │   ├── services/    # API services
│   │   ├── store/       # State management
│   │   └── utils/       # Utilities
│   └── package.json
├── worker/               # Background worker
│   └── worker/
│       ├── tasks.py     # Celery tasks
│       └── celery_app.py
├── nginx/                # Nginx configuration
├── scripts/              # Setup and utility scripts
├── docker-compose.yml    # Development environment
├── docker-compose.prod.yml # Production environment
└── Makefile             # Development commands
```

## 🛠️ Development

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (for local frontend development)
- Python 3.11+ (for local backend development)

### Development Commands

```bash
# Start development environment
make dev

# View logs
make logs
make logs-backend
make logs-worker
make logs-frontend

# Database operations
make db-migrate
make db-create-migration MESSAGE="your migration message"
make db-reset

# Shell access
make shell-backend
make shell-worker
make shell-db

# Health check
make health

# Cleanup
make clean
make clean-all
```

### Local Development Setup

#### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Setup database
export DATABASE_URL="postgresql://user:pass@localhost/towerview"
alembic upgrade head

# Run development server
uvicorn app.main:app --reload
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

#### Worker
```bash
cd worker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start worker
celery -A worker.celery_app worker --loglevel=info

# Start scheduler (in another terminal)
celery -A worker.celery_app beat --loglevel=info
```

## 🔧 Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Database
DATABASE_URL=postgresql://mediaapp:change_me@localhost:5432/mediaapp

# Redis
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your-very-secure-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# Admin Account
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secure_password_here

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Frontend
REACT_APP_API_URL=http://localhost:8000
```

### Provider Configuration

After starting the application, add your media servers through the admin interface:

1. Login as admin
2. Navigate to "Servers" section
3. Click "Add Server"
4. Provide server details and API credentials

#### Getting API Credentials

**Plex:**
- Go to Plex Web App → Settings → Account → Privacy → "Show Advanced"
- Copy your X-Plex-Token from the URL

**Emby:**
- Dashboard → API Keys → Create new API key

**Jellyfin:**
- Dashboard → API Keys → Create new API key

## 🚢 Production Deployment

### Using Docker Compose (Recommended)

```bash
# 1. Create production environment file
cp .env.example .env
# Edit .env with production values

# 2. Generate secure secrets
openssl rand -base64 32  # Use for SECRET_KEY
openssl rand -base64 16  # Use for ADMIN_PASSWORD

# 3. Deploy
make prod

# 4. Check status
docker-compose -f docker-compose.prod.yml ps
make prod-logs
```

### Production Environment Variables

```bash
# Required for production
SECRET_KEY=your-production-secret-key
POSTGRES_PASSWORD=your-secure-db-password
ADMIN_PASSWORD=your-admin-password

# Optional
POSTGRES_USER=mediaapp
POSTGRES_DB=mediaapp
REACT_APP_API_URL=https://your-domain.com
```

### SSL/HTTPS Setup

1. Obtain SSL certificates (Let's Encrypt recommended)
2. Place certificates in `nginx/ssl/`
3. Update `nginx/nginx.conf` to enable HTTPS
4. Update `REACT_APP_API_URL` to use HTTPS

## 📊 Usage

### Admin Interface

- **Dashboard**: Overview of all servers and active sessions
- **Servers**: Add, configure, and manage media servers
- **Sessions**: View and terminate active playback sessions
- **Users**: Manage media users across servers
- **Audit Logs**: Review administrative actions

### Media User Interface

- **Dashboard**: Personal session overview and statistics
- **Watch History**: Browse past viewing sessions
- **Statistics**: Detailed viewing analytics

### API Endpoints

- `GET /api/admin/sessions` - List all active sessions
- `POST /api/admin/servers` - Add new server
- `DELETE /api/admin/sessions/{id}/terminate` - Terminate session
- `GET /api/me/stats` - Get user statistics
- `WebSocket /api/ws` - Real-time updates

## 🔐 Security

- **Encrypted Credentials**: All provider credentials are encrypted before storage
- **JWT Authentication**: Secure token-based authentication
- **RBAC**: Role-based access control (admin vs media user)
- **Rate Limiting**: API rate limiting via Nginx
- **Audit Logging**: All admin actions are logged
- **CORS Protection**: Configured CORS policies
- **SQL Injection Protection**: SQLAlchemy ORM with parameterized queries

## 🐛 Troubleshooting

### Common Issues

**Database Connection Error:**
```bash
# Check if database is running
docker-compose ps db

# View database logs
docker-compose logs db

# Reset database
make db-reset
```

**Worker Not Polling:**
```bash
# Check worker status
docker-compose logs worker

# Restart worker
docker-compose restart worker worker-beat
```

**Frontend Build Issues:**
```bash
# Clear node modules and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Logs

```bash
# All services
make logs

# Specific service
make logs-backend
make logs-worker
make logs-frontend

# Follow logs in real-time
docker-compose logs -f
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Tautulli](https://tautulli.com/) for inspiration
- [FastAPI](https://fastapi.tiangolo.com/) for the excellent framework
- [React](https://reactjs.org/) and [TailwindCSS](https://tailwindcss.com/) for the frontend
- [Plex](https://www.plex.tv/), [Emby](https://emby.media/), and [Jellyfin](https://jellyfin.org/) for their APIs