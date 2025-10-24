# Proxmox Integration - Migration from Portainer

## Overview
TowerView has been migrated from Portainer (Docker container monitoring) to Proxmox VE (LXC container monitoring). This change reflects the new hosting architecture where media servers run in LXC containers on Proxmox instead of Docker containers.

## What's Been Completed

### 1. Backend Services
- **Created** `/backend/app/services/proxmox_service.py` - Full Proxmox API integration
  - Authentication using API tokens
  - List LXC containers across all nodes
  - Collect real-time metrics (CPU, RAM)
  - Container control (start/stop/shutdown/reboot)

### 2. Database Models
- **Added** `ProxmoxIntegration` model to `/backend/app/models/settings.py`
  - Stores Proxmox host, port, node, API token
  - Container mappings: `{server_id: {"node": "pve", "vmid": 100}}`
  - Marked `PortainerIntegration` as DEPRECATED (kept for backward compatibility)

### 3. Database Migration
- **Created** `/backend/alembic/versions/add_proxmox_integration.py`
  - Creates `proxmox_integrations` table
  - Run with: `alembic upgrade head`

### 4. Metrics Collection
- **Updated** `/backend/app/services/metrics_cache_service.py`
  - Replaced Portainer API calls with Proxmox API calls
  - Now fetches metrics from LXC containers via Proxmox API
  - Collects: CPU %, RAM usage/limit, container status

### 5. API Routes
- **Created** `/backend/app/api/routes/settings/proxmox.py`
  - `POST /settings/proxmox/auth` - Test connection and save credentials
  - `GET /settings/proxmox/status` - Get integration status
  - `GET /settings/proxmox/containers` - List all LXC containers
  - `POST /settings/proxmox/container-mapping` - Map server to LXC
  - `GET /settings/proxmox/metrics/{server_id}` - Get container metrics
  - `POST /settings/proxmox/container/{server_id}/action` - Control containers

- **Updated** `/backend/app/api/routes/settings/__init__.py` - Registered Proxmox router

### 6. Frontend (Partially Complete)
- **Tab renamed** from "Portainer" to "Proxmox" in Settings.tsx
- **TODO**: Complete frontend component replacement (see below)

## What Still Needs to Be Done

### Frontend Settings Component

The Settings.tsx file needs manual completion. Here's what needs to be replaced:

#### 1. **Add Proxmox Interfaces** (top of file, around line 35)
```typescript
interface ProxmoxContainer {
  vmid: number
  name: string
  node: string
  status: string
  maxmem: number
  cpus: number
}

interface ProxmoxIntegration {
  connected: boolean
  enabled?: boolean
  host?: string
  port?: number
  node?: string
  verify_ssl?: boolean
  container_mappings?: Record<string, { node: string; vmid: number; container_name: string }>
  containers_count?: number
  updated_at?: string
}
```

#### 2. **Replace State Variables** (around line 68-73)
```typescript
// Remove Portainer state
const [portainerUrl, setPortainerUrl] = useState('')
const [portainerUsername, setPortainerUsername] = useState('')
const [portainerPassword, setPortainerPassword] = useState('')
const [showPortainerAuth, setShowPortainerAuth] = useState(false)
const [portainerContainerMappings, setPortainerContainerMappings] = useState<Record<number, string>>({})

// Add Proxmox state
const [proxmoxHost, setProxmoxHost] = useState('')
const [proxmoxApiToken, setProxmoxApiToken] = useState('')
const [proxmoxNode, setProxmoxNode] = useState('pve')
const [proxmoxVerifySSL, setProxmoxVerifySSL] = useState(false)
const [showProxmoxAuth, setShowProxmoxAuth] = useState(false)
const [proxmoxContainerMappings, setProxmoxContainerMappings] = useState<Record<number, {node: string, vmid: number}>>({})
```

#### 3. **Replace Query Hooks** (around line 92-107)
```typescript
// Fetch Proxmox integration status
const { data: proxmoxStatus, refetch: refetchProxmoxStatus } = useQuery<ProxmoxIntegration>(
  'proxmox-status',
  () => api.get('/settings/proxmox/status').then(res => res.data),
  { refetchInterval: 30000 }
)

// Fetch Proxmox containers
const { data: proxmoxContainers = [], refetch: refetchProxmoxContainers } = useQuery<ProxmoxContainer[]>(
  'proxmox-containers',
  () => api.get('/settings/proxmox/containers').then(res => res.data),
  { enabled: proxmoxStatus?.connected ?? false }
)
```

#### 4. **Replace Mutations** (around line 173-247)
```typescript
const authenticateProxmox = useMutation(
  (data: { host: string; api_token: string; node?: string; verify_ssl?: boolean }) =>
    api.post('/settings/proxmox/auth', data),
  {
    onSuccess: (res) => {
      toast.success(res.data.message || 'Connected to Proxmox successfully')
      queryClient.invalidateQueries('proxmox-status')
      queryClient.invalidateQueries('proxmox-containers')
      setShowProxmoxAuth(false)
      setProxmoxHost('')
      setProxmoxApiToken('')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to connect to Proxmox')
    }
  }
)

const setProxmoxContainerMapping = useMutation(
  (data: { server_id: number; node: string; vmid: number; container_name: string }) =>
    api.post('/settings/proxmox/container-mapping', data),
  {
    onSuccess: () => {
      queryClient.invalidateQueries('proxmox-status')
      toast.success('Container mapping saved')
    },
    onError: () => {
      toast.error('Failed to save container mapping')
    }
  }
)

const disconnectProxmox = useMutation(
  () => api.delete('/settings/proxmox/disconnect'),
  {
    onSuccess: () => {
      queryClient.invalidateQueries('proxmox-status')
      queryClient.invalidateQueries('proxmox-containers')
      toast.success('Proxmox disconnected successfully')
    },
    onError: () => {
      toast.error('Failed to disconnect Proxmox')
    }
  }
)
```

#### 5. **Replace Handler Functions**
```typescript
const handleProxmoxAuth = () => {
  if (!proxmoxHost) {
    toast.error('Please enter Proxmox host')
    return
  }
  if (!proxmoxApiToken) {
    toast.error('Please enter API token')
    return
  }
  authenticateProxmox.mutate({
    host: proxmoxHost,
    api_token: proxmoxApiToken,
    node: proxmoxNode,
    verify_ssl: proxmoxVerifySSL
  })
}

const handleProxmoxContainerMapping = (serverId: number, vmid: number, node: string) => {
  const container = proxmoxContainers.find(c => c.vmid === vmid && c.node === node)
  if (container) {
    setProxmoxContainerMapping.mutate({
      server_id: serverId,
      node: node,
      vmid: vmid,
      container_name: container.name
    })
  }
}
```

#### 6. **Replace Tab Content** (lines 296-528)
Replace the entire Portainer tab section with Proxmox equivalent:
- Title: "Proxmox Integration"
- Description: "Connect to your Proxmox VE instance to monitor LXC containers running your media servers."
- Input fields: Host (IP or hostname), API Token, Node name, Verify SSL checkbox
- Container mapping shows: Node:VMID format (e.g., "pve:100")

## Deployment Steps

### 1. On Development Machine (Current Location)
```bash
# Commit all changes
git add .
git commit -m "Migrate from Portainer to Proxmox for LXC monitoring"
git push origin main
```

### 2. On Proxmox VM (Where TowerView will run)
```bash
# Pull latest code
cd /path/to/TowerView
git pull origin main

# Run database migration
cd backend
alembic upgrade head

# Restart services
docker-compose down
docker-compose up -d
# OR if using production:
docker-compose -f docker-compose.production.yml restart
```

### 3. Create Proxmox API Token
On your Proxmox host, create an API token for TowerView:

```bash
# Via CLI:
pveum user token add root@pam towerview --privsep 0

# Or via Web UI:
# Datacenter → Permissions → API Tokens → Add
# User: root@pam
# Token ID: towerview
# Privilege Separation: No (unchecked)
```

This will output a token like:
```
root@pam!towerview=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### 4. Configure TowerView
1. Navigate to Settings → Proxmox tab
2. Enter Proxmox host (e.g., `192.168.1.100` or `proxmox.local`)
3. Paste the full API token from step 3
4. Enter node name (usually `pve`)
5. Keep "Verify SSL" unchecked (if using self-signed certs)
6. Click "Connect"
7. Map each media server to its LXC container (node + VMID)

## Testing Checklist

- [ ] Backend starts without errors
- [ ] Database migration runs successfully
- [ ] Proxmox tab appears in Settings
- [ ] Can connect to Proxmox with API token
- [ ] LXC containers list appears
- [ ] Can map servers to LXC containers
- [ ] Metrics appear on dashboard (CPU/RAM)
- [ ] Container controls work (start/stop)
- [ ] Metrics update every 2 seconds

## Rollback Plan

If issues occur, the Portainer code is still present but marked as DEPRECATED:
1. Portainer models still exist in database
2. Portainer routes still registered (commented out if needed)
3. Can re-enable Portainer tab in frontend

## Notes

- **SSL Certificates**: Most home Proxmox installations use self-signed certificates. Set `verify_ssl: false` in the integration.
- **API Token Format**: Must include full format: `USER@REALM!TOKENID=SECRET`
- **Node Names**: Common default is `pve`, but check your Proxmox cluster
- **VMIDs**: LXC container IDs (e.g., 100, 101, 102...)
- **Multiple Nodes**: The system supports multiple Proxmox nodes in a cluster

## Architecture Benefits

### Before (Portainer):
- Required separate Portainer instance
- Docker-specific metrics
- Container ID mapping complexity
- Token auto-refresh complexity

### After (Proxmox):
- Direct API access to Proxmox
- Native LXC support
- Stable VM IDs
- Permanent API tokens (no refresh needed)
- Better suited for Proxmox-based hosting

## File Reference

### New Files:
- `/backend/app/services/proxmox_service.py`
- `/backend/app/api/routes/settings/proxmox.py`
- `/backend/alembic/versions/add_proxmox_integration.py`

### Modified Files:
- `/backend/app/models/settings.py` - Added ProxmoxIntegration model
- `/backend/app/models/user.py` - Added proxmox_integrations relationship
- `/backend/app/services/metrics_cache_service.py` - Replaced Portainer with Proxmox
- `/backend/app/api/routes/settings/__init__.py` - Registered Proxmox router
- `/frontend/src/components/admin/Settings.tsx` - Tab renamed (needs completion)

### Deprecated But Kept:
- All Portainer-related files (for backward compatibility during transition)
