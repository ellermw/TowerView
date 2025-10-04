# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TowerView is a unified media server management platform that provides a single administrative interface for managing multiple media servers (Plex, Jellyfin, Emby). It includes real-time monitoring, user management, session control, analytics, and Docker container management via Portainer integration.

**Current Version:** 2.3.13

## Architecture

### Multi-Container Options

TowerView supports two deployment modes:

1. **Production (2 containers)**: All-in-one container + PostgreSQL - recommended for production
2. **Development (7 containers)**: Microservices architecture with separate containers for each service

### Core Components

- **Backend**: FastAPI application with JWT authentication
- **Frontend**: React + TypeScript + Vite + TailwindCSS
- **Worker**: Celery workers for background tasks (server polling, analytics)
- **Beat Scheduler**: Celery Beat for periodic tasks
- **Database**: PostgreSQL for persistent storage
- **Cache**: Redis for caching and task queue
- **Proxy**: Nginx for routing and static file serving

## Development Commands

### Full Development Stack (7 containers)

```bash
# Start all services (with Makefile)
make dev                    # Start with logs
make dev-detached          # Start in background

# View logs (with Makefile)
make logs                   # All services
make logs-backend          # Backend only
make logs-frontend         # Frontend only
make logs-worker           # Worker only

# Database operations (with Makefile)
make db-migrate            # Run migrations
make db-create-migration MESSAGE="description"
make db-reset              # Reset database

# Shell access (with Makefile)
make shell-backend         # Backend container shell
make shell-worker          # Worker container shell
make shell-db             # PostgreSQL shell

# Manual Docker commands
docker-compose up -d       # Start all services
docker-compose logs -f backend  # View backend logs
docker-compose down        # Stop services
```

### Backend Development

```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Run backend directly (ensure DB and Redis are running)
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Database migrations (Alembic)
cd backend
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

### Frontend Development

```bash
# Install dependencies
cd frontend
npm install

# Run dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Type checking
npx tsc --noEmit
```

### Worker Development

```bash
# Run Celery worker
cd worker
celery -A worker.celery_app worker --loglevel=info

# Run Celery Beat scheduler
cd worker
celery -A worker.celery_app beat --loglevel=info
```

## Key Architectural Patterns

### Provider Pattern

Media server integrations follow a provider pattern with a common base interface:

- **Base**: `backend/app/providers/base.py` - Abstract base class defining provider interface
- **Implementations**: `plex.py` (1162 lines), `emby.py` (891 lines), `jellyfin.py` (829 lines)
- **Factory**: `backend/app/providers/factory.py` - Creates appropriate provider instances

Each provider implements these key methods:
- `connect()` - Initialize connection to media server
- `authenticate_user()` - Verify user credentials
- `list_active_sessions()` - Fetch active streaming sessions
- `list_users()` - Fetch all media server users
- `terminate_session()` - Stop a streaming session
- `modify_user()` - Update user settings
- `list_libraries()` - Get available libraries
- `set_library_access()` - Manage user library permissions
- `get_media_info()` - Retrieve media details

### Caching Architecture

Multiple cache layers for performance:

1. **Sessions Cache** (`sessions_cache_service.py`): Updates every 2s, cached for 5s
2. **Users Cache** (`users_cache_service.py`): Updates every 60s, cached for 2min
3. **Metrics Cache** (`metrics_cache_service.py`): Background collection for instant dashboard loads
4. **Bandwidth Cache** (`bandwidth_cache.py`): Real-time bandwidth tracking with 90-second history (18 data points at 5-second intervals)

All cache services start on application startup via the FastAPI `lifespan` context manager in `backend/app/main.py`.

### Authentication & Authorization

- **JWT-based authentication** with access and refresh tokens
- **Hierarchical roles**: Admin > Staff > Support
- **Dual authentication modes**:
  - Staff authentication for TowerView users
  - Media user authentication (Plex OAuth, Emby/Jellyfin direct)
- **Permission system**: Granular per-server permissions for Staff users stored in `UserPermission` model
- **Plex OAuth**: Dynamically detects frontend URL from request headers (Origin/Referer) or `FRONTEND_URL` environment variable for proper OAuth redirects

### Background Tasks

Celery workers handle scheduled tasks defined in `worker/worker/tasks.py`:

- **poll_all_servers** (every 30s): Poll all enabled servers for active sessions
- **cleanup_old_sessions** (every 5min): Remove sessions older than 30 days
- **sync_users_task**: On-demand sync of users from media servers
- **sync_libraries_task**: On-demand sync of library information

Beat schedule defined in `worker/worker/celeryconfig.py`.

## Database Models

Core models in `backend/app/models/`:

- **User**: TowerView users (admin/staff/support) and media server users
- **Server**: Media server configurations
- **Credential**: Encrypted credentials for media servers
- **Session**: Active streaming sessions
- **AuditLog**: Complete audit trail of administrative actions
- **PlaybackEvent/DailyAnalytics**: Playback metrics and aggregated analytics
- **UserPermission**: Per-server permissions for staff users
- **SystemSettings**: Site configuration (name, Portainer integration)

## Frontend Architecture

### State Management

- **Zustand** for global state (auth, server selection)
- **React Query** for server state and caching
- **Local state** for component-specific UI state

Main stores in `frontend/src/store/`:
- `authStore.ts` - Authentication state with persistence

### Component Organization

- `components/admin/` - Admin-specific components (Servers, Users, Analytics, Settings)
- `components/` - Shared components (Layout, ErrorBoundary, Modals)
- `pages/` - Top-level page components
- `services/` - API client services
- `hooks/` - Custom React hooks

### API Integration

API client in `frontend/src/services/api.ts` handles:
- Request/response interceptors
- Automatic token refresh
- Error handling and retries
- Type-safe API calls

## API Routes

Routes defined in `backend/app/api/routes/` (modularized in subdirectories):

### Authentication (`auth.py` - 27,025 lines)
- `POST /api/auth/login` - Staff login
- `POST /api/auth/media/username` - Media user login
- `POST /api/auth/media/plex/oauth` - Plex OAuth flow
- `POST /api/auth/refresh` - Refresh token
- `POST /api/auth/change-password` - Password change

### Admin Operations (`admin/` subdirectory)
- Server management: CRUD operations for media servers
- Session management: View/terminate sessions, cache control
- User management: System and media user operations
- Analytics: Bandwidth, playback statistics
- Audit logs: Administrative action tracking

### Settings (`settings/` subdirectory)
- Portainer integration: Container management, metrics
- Site settings: Application configuration
- Sync settings: Automatic sync intervals

### WebSocket
- `/api/ws/metrics` - Real-time metrics updates

## Environment Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Database
DATABASE_URL=postgresql://mediaapp:password@db:5432/mediaapp

# Redis
REDIS_URL=redis://redis:6379

# Security (generate new keys for production)
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-key

# Admin credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secure_password
```

## Important Implementation Notes

### Container Synchronization

TowerView automatically syncs Docker container mappings every 5 minutes via `container_sync_service.py`. This handles container ID changes when containers are recreated. Manual sync available in Settings > Portainer.

### Credential Encryption

Media server credentials are encrypted before storage using Fernet encryption. See `backend/app/core/security.py` for `credential_encryption` implementation.

### HDR and Resolution Detection

Version 2.3.2+ includes comprehensive HDR detection across all providers. HDR fields include:
- HDR10, Dolby Vision, HDR10+
- 4K detection supports cinema formats (>= 2000 pixels)
- Resolution shows actual playing resolution (direct play vs transcoded)

**Transcoding Resolution Detection (Plex):**
- During transcoding, Plex only provides the transcoded resolution in session data
- Original resolution is inferred using smart defaults:
  - 4K libraries: Original assumed to be 4K
  - 1080p transcode: Assumed from 1080p source (codec conversion more common than 4K downscaling)
  - Lower quality transcodes: Assumed from 1080p source
  - Direct play: Uses videoResolution field with height-based fallback
- Always provides a resolution value (never shows "Unknown" in UI)

See provider implementations for details.

### Plex OAuth Flow

Plex supports both direct username/password and OAuth authentication. OAuth flow:
1. Generate PIN via Plex API
2. User authorizes at plex.tv/link
3. Poll for PIN completion
4. Exchange PIN for auth token

Implemented in `backend/app/api/routes/auth.py` and `frontend/src/components/MediaLoginModal.tsx`.

### Library Access Management

**Full Implementation** for Emby and Jellyfin users:

- **Frontend** (`frontend/src/components/admin/UsersList.tsx`):
  - Libraries button in user management interface
  - Modal displays all available libraries sorted alphabetically
  - Pre-checks libraries based on current user access
  - Success toast notification on save
  - Auto-closes modal after successful save
  - Error handling with toast notifications

- **Backend** (`backend/app/api/routes/admin/libraries.py`):
  - `GET /servers/{server_id}/libraries` - List all libraries
  - `GET /servers/{server_id}/users/{user_id}/libraries` - Get user's current access
  - `POST /servers/{server_id}/users/{user_id}/libraries` - Set library access
  - Audit logging for all library access changes

- **Provider Methods** (Emby/Jellyfin):
  - `list_libraries()` - Get all libraries from the server
  - `get_user_library_access(user_id)` - Get current library access (returns `{library_ids: [], all_libraries: bool}`)
  - `set_user_library_access(user_id, library_ids, all_libraries)` - Update library access
  - Uses Emby/Jellyfin Policy API (`EnableAllFolders` and `EnabledFolders` fields)

**Important Notes**:
- Library IDs are strings in Emby/Jellyfin
- `all_libraries=True` means user has access to all libraries (EnabledFolders cleared)
- `all_libraries=False` means user has access only to specified library_ids
- Libraries sorted alphabetically by name for better UX
- Audit logs track changes with server name, library count, and all_libraries status

## Common Patterns

### Adding a New Media Server Provider

1. Create new provider class extending `BaseProvider` in `backend/app/providers/`
2. Implement required methods: `get_sessions()`, `get_users()`, `terminate_session()`, etc.
3. Add provider type to `ServerType` enum in models
4. Update factory in `providers/factory.py`
5. Add frontend UI for provider-specific settings

### Adding a New Background Task

1. Define task in `worker/worker/tasks.py` with `@celery_app.task` decorator
2. Add beat schedule to `worker/worker/celery_app.py` if periodic
3. Ensure proper error handling and logging
4. Consider task time limits and retries

### Adding a New API Endpoint

1. Add route to appropriate router in `backend/app/api/routes/`
2. Define Pydantic schemas in `backend/app/schemas/`
3. Implement business logic in `backend/app/services/`
4. Add audit logging for admin actions
5. Update frontend API service in `frontend/src/services/`

### Adding Cache Management

1. Create cache service extending the pattern in existing cache services
2. Start/stop service in FastAPI `lifespan` context (`backend/app/main.py`)
3. Add cache status and refresh endpoints in admin routes
4. Configure appropriate TTL and refresh intervals

## File Structure

Key directories and files:
- `backend/app/providers/` - Media server provider implementations
- `backend/app/api/routes/admin/` - Modularized admin endpoints
- `backend/app/services/` - Business logic and cache services
- `frontend/src/components/admin/AdminHome.tsx` - Main dashboard (bandwidth graphs, sessions)
- `worker/worker/tasks.py` - Background task definitions
- `supervisord.conf` - Production process management
- `deploy.sh` - Automated production deployment script

## Testing

Limited automated tests exist in `backend/tests/`. When adding tests:

- Backend: Use pytest with FastAPI TestClient
- Frontend: Use Vitest + React Testing Library
- Integration: Test against actual media server instances or mocks

## Production Deployment

Use `deploy.sh` for automated production deployment:

```bash
./deploy.sh
```

This script:
- Generates secure passwords
- Builds the all-in-one container
- Starts services using `docker-compose.production.yml`
- Displays admin credentials

For manual deployment:

```bash
docker-compose -f docker-compose.production.yml up -d
```

## Logging

- Backend logging configured in `backend/app/main.py`
- Plex provider has DEBUG logging enabled for hardware transcoding details
- View logs: `docker-compose logs -f [service]`

## Database Backups

```bash
# Backup
docker exec towerview-db-1 pg_dump -U towerview towerview > backup.sql

# Restore
docker exec -i towerview-db-1 psql -U towerview towerview < backup.sql
```

## Security Considerations

- Never commit `.env` files or credentials
- Rotate JWT secrets in production
- Use strong passwords for admin accounts
- Enable SSL/TLS in production (configure nginx)
- Credential encryption uses Fernet symmetric encryption
- Audit logs track all administrative actions with IP and user agent

## Password Hash Stability

**Problem**: After container rebuilds, bcrypt password hashes may become incompatible, causing login failures.

**Solution Implemented**:
1. **Stable bcrypt configuration** (`backend/app/core/security.py`):
   - Explicit `bcrypt__ident="2b"` for consistent hash prefix
   - Fixed `bcrypt__rounds=12` for stability

2. **Automatic migration** (`backend/app/core/password_migration.py`):
   - Runs on every application startup
   - Detects incompatible password hashes
   - Auto-resets affected passwords to "admin" with `must_change_password=True`
   - Logs all migrations for admin awareness

3. **Startup integration** (`backend/app/main.py`):
   - `startup_password_check()` runs during application lifespan
   - Transparent to users - no manual intervention needed

**What happens on container rebuild**:
- Application starts → checks all staff user passwords
- If hashes are incompatible → automatically resets to "admin"
- Affected users see migration in logs
- Users must change password on next login

This prevents the recurring "incorrect credentials" issue after Docker updates.

## Troubleshooting Common Issues

### Sessions Not Loading
Sessions are cached for 5 seconds. Force refresh:
```bash
curl -X POST http://localhost:8080/api/admin/sessions/refresh-cache
```

### Container Metrics Show 0%
Container IDs may have changed. System auto-syncs every 5 minutes, or manually sync in Settings > Portainer.

### Plex Session Termination Fails
- Ensure using Plex admin token (not Plex.tv token)
- Check Plex Pass subscription for termination features
- Verify token has admin permissions
- Local sessions may not be terminable remotely

### Plex OAuth Issues

**Fixed in v2.3.12**: Plex OAuth now works correctly with proper URL format and required headers.

**OAuth Flow**:
1. Frontend requests PIN from backend (`/api/auth/media/oauth/plex/init`)
2. Backend generates PIN and returns OAuth URL with `#?` format (required by Plex web app)
3. User authorizes in Plex, which redirects to `/oauth/callback`
4. Frontend polls for PIN completion every 2 seconds
5. When authenticated, stops polling and calls `/api/auth/media/authenticate` with the token
6. Backend validates token and matches user to configured Plex servers

**Key Implementation Details**:
- OAuth URL format: `https://app.plex.tv/auth#?clientID=...&code=...&forwardUrl=...` (note `#?` not `?`)
- All Plex API calls require `X-Plex-Client-Identifier` header
- Frontend URL auto-detected from `Origin` or `Referer` headers (no configuration needed)
- Manual override available via `FRONTEND_URL` environment variable if auto-detection fails
- Polling stops immediately upon successful authentication to prevent concurrent requests
- PIN expires 10 seconds after authorization (tight window requires efficient handling)

**Troubleshooting**:
- If stuck on Plex logo screen: Check that OAuth URL uses `#?` format (backend logs show generated URL)
- If "Invalid Plex token" error: Ensure `X-Plex-Client-Identifier` header is present in all Plex API requests
- If PIN expired error: Check network latency; authentication must complete within 10 seconds of authorization
- Debug: Check backend logs for "Plex OAuth: Using Origin header for forwardUrl" to verify URL detection

### Bandwidth Graph Issues
- Fixed in v2.3.6: Y-axis now properly scales to show all server bandwidth ranges
- Previously was using minimum of maximums instead of true minimum
- Graph now correctly displays individual server lines at different bandwidth levels
- Check browser console for debug logs showing detected servers and bandwidth values

### Staff User Permission Issues
- Fixed in v2.3.6: Staff users can now properly terminate sessions
- Permission checks now use UserPermission table instead of server ownership
- Username conflict checks only validate among system users (admin/staff/support)

### Audit Logs Not Loading
- Fixed in v2.3.6: Created missing audit log endpoints
- Implemented paginated response format
- Fixed Pydantic v2 compatibility (use `from_attributes` instead of `orm_mode`)
- Session usernames now properly captured before termination

### Login Failures After Rebuild

Password hashes are automatically migrated on startup. Check backend logs for migration status.

### Servers Not Loading for Admin Users
- Fixed in v2.3.9: Admin users now see all servers regardless of ownership
- Previously admins were restricted to servers they owned
- Permission checks updated: admins can now view, update, and delete any server
- Staff/support users still restricted to servers they own
- Issue was in `/backend/app/api/routes/admin/servers.py` permission logic

### 4K Transcode Auto-Termination

New feature in v2.3.9 allows automatic termination of 4K to 1080p (or below) transcodes:
- **Location**: Settings > General > 4K Transcode Auto-Termination
- **Features**:
  - Enable/disable toggle
  - Custom termination message (Plex only)
  - Server-specific selection (checkboxes for each server)
  - 5-second grace period before termination
  - Cooldown period to prevent re-termination
- **Implementation**:
  - Service: `/backend/app/services/transcode_termination_service.py`
  - API: `/backend/app/api/routes/settings/transcode.py`
  - Frontend: Settings component with server selection UI
  - Integrated with sessions cache service for real-time monitoring
- **Known Issues Fixed in v2.3.10**:
  - Fixed audit log schema mismatch causing false "Failed to save" error
  - Settings were saving correctly but audit log creation was failing

### Analytics Page

New dedicated Analytics page in v2.3.11:
- **Location**: Navigation bar between Management and Audit Logs
- **Access**: Visible to all system users (Admin, Staff, Support) but NOT media users
- **Features**:
  - Server filter: View analytics for all servers or a specific server
  - Time period filter: Last 24 Hours, 7 Days, 30 Days, 180 Days, 365 Days (defaults to 7 days)
  - Category filter: Top Users, Top Movies, Top TV Shows, Top Libraries, Top Devices
  - Summary cards: Total Sessions, Active Users, Watch Time, Completion Rate, Transcode Rate
  - Detailed tables: Shows up to 100 items per category (vs 5 on dashboard)
  - Category-specific view: Only selected category displayed at a time (no "show all" option)
- **Implementation**:
  - Frontend: `/frontend/src/components/admin/Analytics.tsx`
  - Route: `/admin/analytics` in AdminDashboard.tsx
  - Navigation: Layout.tsx with role-based visibility
  - Backend: Uses existing `/admin/analytics` endpoint with 100-item limit
  - Data source: `analytics_service.py` queries playback_events table
- **React Query Configuration**:
  - `staleTime: 0` - Always fetch fresh data on filter change
  - `cacheTime: 0` - No caching to ensure filters work correctly
  - Query key includes filters for proper cache invalidation
