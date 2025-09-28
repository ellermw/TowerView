# TowerView - Unified Media Server Management Platform

**Version 2.2.0 - Enhanced Role Management & Security**

TowerView is a comprehensive administrative tool for managing multiple media servers (Plex, Jellyfin, Emby) from a single interface. It provides real-time monitoring, user management, session control, and detailed analytics for administrators and support staff. The platform has been thoroughly tested and optimized for production use with excellent stability and performance.

## 🎯 Features

### Core Functionality

- **Multi-Server Support**: Manage Plex, Jellyfin, and Emby servers from one dashboard
- **Real-Time Monitoring**: Live server statistics, bandwidth usage, and transcoding metrics
- **Session Management**: View and terminate active streaming sessions
- **User Management**: Comprehensive user administration across all connected servers
- **Audit Logging**: Complete audit trail of all administrative actions with filtering and search
- **Container Management**: Docker container control via Portainer integration

### User Roles & Hierarchy

1. **Admin**: Full system access with complete control
   - Manage all servers and settings
   - Create users of any role
   - Delete users and change roles
   - Access to all features

2. **Staff** (formerly Local Users): Server management capabilities
   - Create Support users only
   - Configurable permissions per server
   - Manage containers and sessions
   - Cannot delete users or change roles

3. **Support**: Limited view-only access
   - View sessions, users, and analytics
   - Cannot create or delete users
   - Cannot modify settings
   - Ideal for help desk personnel

### Analytics & Monitoring

- **Real-time bandwidth monitoring** with 24-hour historical graphs
- **Server resource utilization** (CPU, RAM, GPU)
- **Transcoding statistics** (hardware vs software detection)
- **Active session tracking** with detailed user information
- **Network throughput visualization** with upload/download metrics
- **Container health monitoring** via Portainer integration
- **Background metrics collection** for instant loading
- **Intelligent caching system** for sessions and user data with automatic refresh

### Security Features

- JWT-based authentication with refresh tokens
- Hierarchical role-based access control (Admin > Staff > Support)
- Granular permission system per server
- Comprehensive audit logging with IP and user agent tracking
- Secure credential storage with encryption
- Forced password changes on first login
- Case-insensitive usernames for better UX
- Role promotion/demotion controls
- Self-protection (cannot delete/demote own account)

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- PostgreSQL 15+
- Redis 7+
- 2GB+ RAM recommended
- Ubuntu 20.04+ or similar Linux distribution

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/TowerView.git
cd TowerView

# 2. Configure environment
cp .env.example .env
# Edit .env with your configuration

# 3. Build and start services
docker-compose build
docker-compose up -d

# 4. Access the application
# Frontend: http://your-server:8080
# API: http://your-server:8000
# API Docs: http://your-server:8000/docs
```

### Default Credentials

- Username: `admin`
- Password: `admin` (will force change on first login)

## 📁 Project Structure

```
TowerView/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/routes/        # API endpoints
│   │   ├── core/              # Core functionality
│   │   ├── models/            # Database models
│   │   ├── providers/         # Media server integrations
│   │   ├── schemas/           # Pydantic schemas
│   │   └── services/          # Business logic
│   └── requirements.txt
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── components/        # React components
│   │   │   └── admin/        # Admin UI components
│   │   ├── hooks/            # Custom React hooks
│   │   ├── services/         # API services
│   │   └── store/            # State management
│   └── package.json
├── nginx/                      # Nginx configuration
├── docker-compose.yml          # Docker orchestration
└── .env.example               # Environment template
```

## 🔧 Configuration

### Adding Media Servers

1. Login as admin
2. Navigate to **Settings → Servers**
3. Click **"Add Server"**
4. Configure:
   - Server name
   - Server type (Plex/Jellyfin/Emby)
   - Server URL
   - API credentials

### Setting Up Local Users

1. Navigate to **Users → Local Users**
2. Click **"Create Local User"**
3. Configure permissions per server:
   - View users
   - Manage server containers
   - Terminate sessions

### Portainer Integration

1. Navigate to **Settings → Integrations**
2. Configure Portainer:
   - Portainer URL
   - API token (generate in Portainer)
   - Endpoint ID
3. Map servers to Docker containers

### Performance & Caching

TowerView includes intelligent caching systems for optimal performance:

- **Sessions Cache**: Updates every 2 seconds, cached for 5 seconds
- **Users Cache**: Updates every 60 seconds, cached for 2 minutes
- **Metrics Cache**: Background collection for instant dashboard loading
- **Bandwidth Cache**: Real-time tracking with historical data storage

Cache status and manual refresh available in admin endpoints:
- `/api/admin/sessions/cache-status` - View sessions cache status
- `/api/admin/sessions/refresh-cache` - Force sessions cache refresh
- `/api/admin/users/cache-status` - View users cache status
- `/api/admin/users/refresh-cache` - Force users cache refresh

## 🛡️ Permission System

### Admin Permissions
- Full access to all features
- System configuration
- Audit log viewing
- User management
- Server management

### Local User Permissions (Configurable)
- **View Analytics**: Dashboard access
- **View Sessions**: See active streams
- **Terminate Sessions**: Stop active streams
- **View Users**: See user lists
- **Manage Servers**: Container control
- Server-specific access control

## 📊 API Documentation

### Authentication
```
POST /api/auth/login          # User login
POST /api/auth/logout         # User logout
POST /api/auth/refresh        # Refresh token
```

### Admin Operations
```
GET  /api/admin/servers       # List servers
POST /api/admin/servers       # Add server
GET  /api/admin/sessions      # View sessions
POST /api/admin/servers/{id}/sessions/{session_id}/terminate
GET  /api/admin/audit-logs    # View audit logs
```

### User Management
```
GET  /api/admin/local-users   # List system users
POST /api/admin/local-users   # Create user (role-restricted)
PATCH /api/admin/local-users/{id}  # Update user
PATCH /api/admin/local-users/{id}/role # Change user role (admin only)
DELETE /api/admin/local-users/{id} # Delete user (admin only)
GET  /api/users/me             # Get current user info
```

### Settings & Metrics
```
GET  /api/settings/portainer/metrics/{server_id}
POST /api/settings/portainer/container/{server_id}/action
GET  /api/settings/site                     # Get site settings
POST /api/settings/site                     # Update site settings
```

### Cache Management
```
GET  /api/admin/sessions/cache-status       # Sessions cache status
POST /api/admin/sessions/refresh-cache      # Force sessions refresh
GET  /api/admin/users/cache-status          # Users cache status
POST /api/admin/users/refresh-cache         # Force users refresh
```

## 🚢 Production Deployment

### SSL Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # ... rest of configuration
}
```

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@db:5432/towerview
POSTGRES_USER=towerview
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=towerview

# Redis
REDIS_URL=redis://redis:6379

# Security
SECRET_KEY=your-very-secure-secret-key
JWT_SECRET_KEY=your-jwt-secret
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secure_admin_password

# Frontend
VITE_API_URL=https://api.your-domain.com
```

### Docker Compose Production

```bash
# Use production compose file
docker-compose -f docker-compose.prod.yml up -d

# Enable auto-restart
docker update --restart=unless-stopped $(docker ps -q)
```

## 🔍 Monitoring & Maintenance

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Database Backup
```bash
# Backup
docker exec towerview-db-1 pg_dump -U towerview towerview > backup.sql

# Restore
docker exec -i towerview-db-1 psql -U towerview towerview < backup.sql
```

### Clear Cache
```bash
docker exec towerview-redis-1 redis-cli FLUSHALL
```

## 📊 Code Quality Report

### Latest Analysis (2025-09-27)
A comprehensive code analysis has been performed identifying areas for improvement. Full details available in [CODE_ANALYSIS_REPORT.md](CODE_ANALYSIS_REPORT.md).

**Summary:**
- **Total Issues Found:** 47
- **High Severity:** 8 (debug code, security, performance)
- **Medium Severity:** 19 (optimization opportunities)
- **Low Severity:** 20 (code quality improvements)
- **Estimated Fix Timeline:** 4-6 weeks

**Key Areas for Improvement:**
- Remove 51+ console.log/print debug statements
- Fix N+1 database query issues
- Add missing database indexes
- Implement React performance optimizations
- Enhance error handling and security

## 📝 Changelog

### Version 2.2.0 (Current)
- **New Role System**: Implemented hierarchical roles (Admin > Staff > Support)
- **Role Management**: Admins can now promote/demote users between roles
- **Enhanced Security**: Added self-protection against accidental account deletion
- **UI Improvements**: System Users page shows all user types with appropriate badges
- **Permission Display**: Admin accounts show "All servers" instead of count
- **Migration Support**: Automatic migration of legacy local_user accounts to staff role

### Version 2.1.0
- Sessions and Users caching for improved performance
- Site name customization
- Fixed Portainer settings persistence
- Icon transparency fixes
- Password reset functionality

### Version 2.0.0
- Transform to Admin/Support Tool
- Added audit logging
- Container management via Portainer
- Real-time metrics and monitoring

## 🐛 Troubleshooting

### Common Issues

**Cannot connect to media server**
- Verify server URL is accessible
- Check API key/token validity
- Ensure firewall allows connections

**Sessions not showing**
- Verify admin privileges on media server
- Check if server has active sessions
- Review server credentials

**Container controls not working**
- Verify Portainer integration
- Check API token validity
- Ensure container mappings are correct

**Audit logs not loading**
- Only admin users can view audit logs
- Check database connection
- Verify audit_logs table exists

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/name`)
3. Commit changes (`git commit -m 'Add feature'`)
4. Push to branch (`git push origin feature/name`)
5. Open Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Backend framework
- [React](https://reactjs.org/) - Frontend framework
- [Vite](https://vitejs.dev/) - Build tool
- [TailwindCSS](https://tailwindcss.com/) - Styling
- [Portainer](https://www.portainer.io/) - Container management
- Media server teams (Plex, Emby, Jellyfin)

## 📝 Changelog

### Version 2.1.0 (Current - Stable)
- ✨ Intelligent caching system for sessions and user data
- ✨ Background data collection with automatic refresh
- ✨ Cache status monitoring and manual refresh endpoints
- ✨ Custom site name configuration
- ✨ Custom server icons for Plex, Emby, and Jellyfin
- ✨ Simplified transcoding display for Emby/Jellyfin
- ✨ Transparent icon backgrounds for theme compatibility
- 🎨 Visual improvements across all pages
- 🔧 Stabilized session monitoring
- 🔧 Improved bandwidth caching system
- 📊 Enhanced real-time metrics display
- ⚡ Significantly improved performance for session and user data retrieval

### Version 2.0.0
- ✨ Complete transformation to admin/support tool
- ✨ Comprehensive audit logging system
- ✨ Granular permission system for local users
- ✨ Real-time bandwidth monitoring with caching
- ✨ GPU metrics support
- ✨ Enhanced container management
- ✨ Improved session termination
- 🔧 Fixed hardware transcoding detection for Plex
- 🔧 Fixed local user permissions
- 🔧 Improved error handling

### Version 1.0.0
- Initial release
- Basic multi-server support
- User authentication
- Session viewing

---

**Note**: This is an administrative tool requiring elevated privileges on your media servers. It is designed for server administrators and support staff only.