# TowerView - Unified Media Server Management Platform

## Version 2.3.14 - Jellyfin Library Management Fix

TowerView is a comprehensive administrative tool for managing multiple media servers (Plex, Jellyfin, Emby) from a single interface. It provides real-time monitoring, user management, session control, and detailed analytics for administrators and support staff. Now with a streamlined 2-container deployment option for production use.

## 🎯 Features

### Core Functionality

- **Multi-Server Support**: Manage Plex, Jellyfin, and Emby servers from one dashboard
- **Real-Time Monitoring**: Live server statistics, bandwidth usage, and transcoding metrics
- **Session Management**: View and terminate active streaming sessions
- **User Management**: Comprehensive user administration across all connected servers
- **Audit Logging**: Complete audit trail of all administrative actions with filtering and search
- **Container Management**: Docker container control via Portainer integration

### Navigation Structure

- **Dashboard**: Main overview with server stats and active sessions
- **Management** (dropdown menu):
  - **Servers**: Add/edit/remove media servers
  - **Users**: View media server users (password management for Emby/Jellyfin only)
  - **System Users**: Create and manage TowerView users (admin only)
- **Analytics**: Detailed analytics page with category filtering (admin/staff/support only)
- **Audit Logs**: View all system activity (admin only)
- **Settings**: System configuration and integrations

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

- **Dedicated Analytics Page**: Comprehensive analytics with category-based filtering
  - Filter by server, time period (24H, 7D, 30D, 180D, 365D), and category
  - Categories: Top Users, Top Movies, Top TV Shows, Top Libraries, Top Devices
  - Shows up to 100 items per category (vs 5 on dashboard)
  - Summary cards: Total Sessions, Active Users, Watch Time, Completion Rate, Transcode Rate
  - Available to Admin, Staff, and Support users
- **Real-time bandwidth monitoring** with 90-second historical view (5-second intervals)
- **Server-side bandwidth caching** for immediate history on dashboard load
- **Enhanced bandwidth graph** with separated Y-axis labels and full-width display
- **Server resource utilization** (CPU, RAM, GPU)
- **Transcoding statistics** (hardware vs software detection)
- **4K Transcode Auto-Termination**: Automatically terminate 4K to 1080p/lower transcodes with configurable grace period
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
- **Automatic password hash migration** - prevents login issues after Docker updates

### Authentication Methods

**Staff Authentication**: ✅ Fully functional
- Admin, Staff, and Support users can log in using the Staff tab
- Complete access to all TowerView features based on role permissions
- Role-based access control with hierarchical permissions

**Media User Authentication**: ✅ Fully working!
- **Plex**: Supports both direct username/password and OAuth authentication (OAuth fixed in v2.3.12)
- **Emby**: Direct authentication with username and password
- **Jellyfin**: Direct authentication with username and password
- Smart server selection automatically matches users to their correct servers
- Seamless login experience for media server users
- OAuth uses proper `#?` URL format and required Plex headers

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- 2GB+ RAM recommended
- Ubuntu 20.04+ or similar Linux distribution
- Ports 80/8080 available (configurable)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/TowerView.git
cd TowerView

# 2. Configure environment (optional)
cp .env.example .env
# Edit .env to set DB_PASSWORD, SECRET_KEY, ADMIN_PASSWORD

# 3. Start the containers
docker-compose up -d

# That's it! TowerView will be available at:
# - Frontend: http://localhost:8080
# - Backend API: http://localhost:8080/api
```

The production build uses a single all-in-one container that includes:
- Frontend (React + Nginx)
- Backend (FastAPI)
- Worker (Celery)
- Beat Scheduler
- Redis
- Served via Nginx on port 8080 (configurable via `HTTP_PORT` in .env)

### Alternative Deployment Method

```bash
# Using the automated deployment script
./deploy.sh

# The script will:
# - Generate secure passwords
# - Build the containers
# - Start the services
# - Display your admin credentials
```

### Default Credentials

- Username: `admin`
- Password: `admin` (will force change on first login)

## 🏗️ Architecture

TowerView uses an all-in-one container architecture for simplicity:

```
┌─────────────────────────────────────────┐
│          All-in-One Container           │
│  ┌────────────┐  ┌──────────────────┐  │
│  │   Nginx    │  │  FastAPI Backend  │  │
│  │  (Port 80) │  │   (Port 8000)     │  │
│  └────────────┘  └──────────────────┘  │
│  ┌────────────┐  ┌──────────────────┐  │
│  │   Redis    │  │  Celery Workers   │  │
│  │ (Internal) │  │  + Beat Scheduler │  │
│  └────────────┘  └──────────────────┘  │
└─────────────────────────────────────────┘
                    ↓
         ┌──────────────────┐
         │   PostgreSQL DB   │
         │    (Separate)     │
         └──────────────────┘
```

## 📁 Project Structure

```
TowerView/
├── backend/                        # FastAPI backend
│   ├── app/
│   │   ├── api/routes/            # API endpoints
│   │   ├── core/                  # Core functionality
│   │   ├── models/                # Database models
│   │   ├── providers/             # Media server integrations
│   │   ├── schemas/               # Pydantic schemas
│   │   └── services/              # Business logic
│   └── requirements.txt
├── frontend/                       # React frontend
│   ├── src/
│   │   ├── components/            # React components
│   │   ├── hooks/                # Custom React hooks
│   │   ├── services/             # API services
│   │   └── store/                # State management
│   └── package.json
├── worker/                         # Celery background tasks
├── nginx/                          # Nginx configuration
├── docker-compose.yml              # Production setup (2 containers)
├── Dockerfile.combined             # All-in-one production container
├── supervisord.conf                # Process manager for production
├── deploy.sh                       # Automated deployment script
└── .env.example                   # Environment template
```

## 🔧 Configuration

### Adding Media Servers

1. Login as admin
2. Navigate to **Management → Servers** (from the dropdown menu)
3. Click **"Add New Server"**
4. Configure:
   - Server name
   - Server type (Plex/Jellyfin/Emby)
   - Server URL (e.g., https://plex.example.com)
   - API Key/Token (from your media server)
5. Click **"Test Connection"** to verify
6. Click **"Add Server"** to save

### Creating Staff/Support Users

1. Navigate to **Management → System Users** (admin only)
2. Click **"Create User"**
3. Configure:
   - Username (case-insensitive)
   - Password (min 8 characters)
   - User Type (Staff or Support)
   - Permissions (Staff users only):
     - Select which servers they can access
     - Set permissions per server (view sessions, terminate, etc.)

### Portainer Integration

1. Navigate to **Settings** (in top menu)
2. Find the **Portainer Configuration** section
3. Configure:
   - Portainer URL (e.g., https://portainer.example.com)
   - Username (your Portainer username)
   - Password (your Portainer password)
   - Endpoint ID (usually 1 for local, check Portainer)
4. Click **"Save Settings"**
5. Map servers to containers in the **Docker Container Mapping** section

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

### Staff User Permissions (Configurable per Server)
- **View Analytics**: Dashboard and analytics access
- **View Sessions**: See active streaming sessions
- **Terminate Sessions**: Stop active streams
- **View Users**: See user lists
- **Manage Servers**: Container control (start/stop/restart)
- Each permission can be set independently per server

### Support User Permissions (Fixed)
- View-only access to dashboard and analytics
- Cannot modify any settings or terminate sessions
- Cannot create or manage users
- Ideal for help desk and monitoring roles

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

## 📝 Changelog

### Version 2.3.14 (Current)

- **Jellyfin Library Management Fix**:
  - Fixed double-slash URL issue in Jellyfin provider (`//Users/` → `/Users/`)
  - Added `base_url.rstrip('/')` to prevent trailing slash conflicts
  - Fixed `get_user_library_access()` method URL construction
  - Fixed `set_user_library_access()` method URL construction
  - Libraries now pre-check correctly for Jellyfin users
  - Saving library changes now works properly for Jellyfin
  - No more 404 errors when fetching user policy from Jellyfin

### Version 2.3.13

- **Library Management Feature - Complete Implementation**:
  - Added library access management for Emby and Jellyfin users
  - Implemented `set_user_library_access()` method in Emby and Jellyfin providers
  - Fixed duplicate API endpoint conflict (removed conflicting route from users.py)
  - Libraries now properly pre-check based on current user access
  - Libraries sorted alphabetically by name for better UX
  - Added success toast notification when saving library changes
  - Modal now auto-closes after successful save
  - Proper error handling with toast notifications
  - Fixed audit logging to use correct AuditService.log_action() method
  - Comprehensive library management now working for all provider types

### Version 2.3.12

- **Plex OAuth Authentication Fix**:
  - Fixed OAuth URL format to use `https://app.plex.tv/auth#?` (hash-based parameters required by Plex)
  - Added required `X-Plex-Client-Identifier` header to all Plex API requests
  - Fixed "Invalid Plex token" error by including client identifier in resource and user API calls
  - Improved polling mechanism to prevent concurrent authentication requests
  - Added `isAuthenticating` state flag to stop polling immediately upon success
  - Enhanced error logging for better OAuth troubleshooting
  - Plex OAuth now works reliably within the 10-second PIN expiry window
  - Updated CLAUDE.md with comprehensive OAuth flow documentation

### Version 2.3.11

- **Analytics Page**:
  - New dedicated Analytics page accessible from navigation bar
  - Visible to Admin, Staff, and Support users (not media users)
  - Category-based filtering: Top Users, Movies, TV Shows, Libraries, Devices
  - Time period filters: Last 24 Hours, 7 Days, 30 Days, 180 Days, 365 Days
  - Server-specific filtering or view all servers combined
  - Shows up to 100 items per category (vs 5 on dashboard)
  - Summary cards for quick overview of key metrics
  - Only selected category displayed at a time (no "show all" option)
  - Located between Management and Audit Logs in navigation

### Version 2.3.10

- **Bug Fixes**:
  - Fixed transcode settings save error - audit log was using old schema fields
  - Settings were saving correctly but showing "Failed to save" error message
  - Corrected audit log to use new schema (actor_id, actor_username, actor_type, target, target_name)

### Version 2.3.9

- **4K Transcode Auto-Termination Feature**:
  - Automatically terminate 4K to 1080p or below transcodes
  - Configurable 5-second grace period before termination
  - Server-specific selection (choose which servers to apply)
  - Custom termination message for Plex users
  - Cooldown period to prevent re-termination
  - Located in Settings > General
- **Admin Permission Fixes**:
  - Fixed admin users unable to see servers they don't own
  - Admins now have full access to view, update, and delete all servers
  - Fixed permission checks in server API endpoints
  - Staff/Support users still restricted to their own servers
- **Bug Fixes**:
  - Resolved "no servers available" issue for admins
  - Fixed 403 errors on server version endpoints for admins

### Version 2.3.8

- **Enhanced Bandwidth Graph UI**:
  - Separated Y-axis labels for cleaner appearance
  - Full-width graph display for better data visualization
  - Improved server legend alignment
- **Session Termination Improvements**:
  - Enhanced Plex session termination with proper error handling
  - Better handling of already-terminated sessions
  - Fixed concurrent termination issues

### Version 2.3.7
- **Bandwidth Monitoring Enhancements**:
  - Improved bandwidth graph with better scaling and visualization
  - Enhanced real-time metrics collection
  - Fixed bandwidth calculation edge cases

### Version 2.3.6
- **Staff User Permissions**:
  - Fixed Staff users unable to terminate sessions (was incorrectly checking server ownership)
  - Added proper permission checks using UserPermission table
  - Staff users can now terminate sessions based on their assigned permissions
  - Fixed username conflict checks to only validate among system users
- **Audit Logging Fixes**:
  - Created missing audit log endpoints (`/api/admin/audit-logs`)
  - Implemented paginated response format for audit logs
  - Fixed Pydantic v2 compatibility (changed `orm_mode` to `from_attributes`)
  - Fixed audit logs showing "Unknown" username when terminating sessions
  - Session info now retrieved before termination for accurate logging
- **Bandwidth Graph Visualization**:
  - Fixed Y-axis scaling issue causing all servers to appear at same bandwidth level
  - Corrected minimum bandwidth calculation (was using min of maximums instead of true minimum)
  - Graph now properly displays individual server bandwidth lines at correct positions
  - Improved scaling logic to handle servers with very different bandwidth ranges
- **UI Improvements**:
  - Disabled React Query retries for session termination to prevent error message spam
  - Added proper error handling for missing UserService methods

### Version 2.3.5
- **Docker Optimization**:
  - Added automatic Docker log rotation (10MB max per file, 3 files retained)
  - Configured system-wide log limits in `/etc/docker/daemon.json`
  - Prevents disk space issues from runaway container logs
  - All docker-compose files updated with logging configuration
- **Password Hash Stability**:
  - Implemented stable bcrypt configuration to prevent hash incompatibility after rebuilds
  - Added automatic password migration script that runs on startup
  - Detects and fixes incompatible password hashes transparently
  - Prevents "incorrect credentials" errors after Docker updates
  - Created `backend/app/core/password_migration.py` for hash validation
  - Added comprehensive logging for password migrations
- **UI Improvements**:
  - Fixed progress bar time display to show minutes:seconds or hours:minutes:seconds
  - Removed total bandwidth line from graph for cleaner visualization
  - Total bandwidth still displayed below graph with individual server breakdowns
- **Documentation**:
  - Added `CLAUDE.md` with detailed architecture and development guidelines
  - Updated security documentation with password stability information

### Version 2.3.4
- **Bug Fixes**:
  - Fixed library access management for Emby/Jellyfin users - libraries now properly pre-check based on current user access
  - Resolved race condition in library modal that was clearing selections before API data loaded

### Version 2.3.3
- **UI Improvements**:
  - Removed Sessions page from navigation (active sessions available on Dashboard)
  - Combined duplicate library names in analytics (libraries with same name across servers are grouped)
  - Removed password management button for Plex users (feature not supported by Plex API)
- **Bug Fixes**:
  - Fixed media user profile display showing "Local User" instead of "Media User"
  - Fixed Plex OAuth authentication completion issues
  - Fixed transcode resolution display (now correctly shows source and target resolutions)

### Version 2.3.2
- **HDR & Resolution Improvements**:
  - Fixed HDR detection for all media server types (Plex, Jellyfin, Emby)
  - Added comprehensive HDR field detection including HDR10, Dolby Vision, and HDR10+
  - Fixed resolution reporting to show actual playing resolution (direct play vs transcoded)
  - Improved 4K detection to support cinema 4K formats (2048p) and non-standard resolutions
  - Fixed Emby resolution detection for DirectStream vs Transcode scenarios
- **Bug Fixes**:
  - Fixed admin login 500 error caused by bcrypt compatibility issue
  - Fixed Pydantic schema stripping HDR fields from API responses
  - Corrected resolution threshold logic for 4K content (now >= 2000 pixels)

### Version 2.3.1
- **Bug Fixes**:
  - Fixed media users unable to see active sessions on dashboard
  - Fixed Jellyfin authentication issues with special characters in passwords
  - Fixed Plex OAuth PIN expiration with automatic renewal
  - Updated database visibility settings for media user access
- **UI Improvements**:
  - Removed unnecessary transcode details from session cards
  - Simplified server metrics display (removed Portainer configuration prompts)
  - Media users now properly see sessions from all visible servers
  - Improved Plex OAuth flow with expiration warnings

### Version 2.3.0
- **Optimized Docker Architecture**: New 2-container production setup (reduced from 7)
- **Server Visibility Controls**: Admins can control which servers media users can see
- **Username Privacy**: Media users see censored usernames (first letter + asterisks) for other users
- **SSL Certificate Support**: Fixed authentication with self-signed certificates (Jellyfin/Emby)
- **Automated Deployment**: Added `deploy.sh` script for one-command production setup
- **Enhanced Caching**: Improved session and user data caching with automatic refresh
- **Bug Fixes**:
  - Fixed Plex OAuth redirect issues
  - Fixed server visibility settings not persisting
  - Resolved Jellyfin authentication failures with valid credentials
  - Fixed media user session visibility

### Version 2.2.2
- **Media User Authentication Fixed**: All three providers now working
- **Plex Enhancement**: Added direct username/password option alongside OAuth
- **Emby/Jellyfin Fix**: Corrected authentication headers and methods
- **Smart Server Selection**: Automatically matches users to correct servers
- **Session Expired Loop Fix**: Authentication failures no longer trigger session expiration
- **Improved Error Handling**: Clear error messages for invalid credentials

### Version 2.2.1
- **Authentication System Update**: Temporarily disabled media user authentication
- **Improved Error Handling**: Clear messaging for authentication status
- **Stability Fix**: Resolved "session expired" loop issues
- **User Guidance**: Updated login page to direct users to Staff authentication

### Version 2.2.0
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

---

**Note**: This is an administrative tool requiring elevated privileges on your media servers. It is designed for server administrators and support staff only.