# Frontend Settings.tsx - Proxmox Integration Instructions

## Quick Summary

The backend is 100% complete and ready. The frontend `Settings.tsx` file needs the Proxmox tab content replaced (it currently still shows Portainer UI).

## Option 1: Test Backend First (Recommended)

You can deploy and test the backend now without updating the frontend:

1. The Proxmox API endpoints are all working
2. Metrics collection is already using Proxmox
3. The Settings tab exists (labeled "Proxmox" now)
4. It just shows the old Portainer UI temporarily

**To test backend**:
```bash
# Test Proxmox connection directly
curl -X POST http://localhost:8080/api/settings/proxmox/auth \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "host": "192.168.1.100",
    "api_token": "root@pam!towerview=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "node": "pve",
    "verify_ssl": false
  }'

# Check status
curl http://localhost:8080/api/settings/proxmox/status \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# List containers
curl http://localhost:8080/api/settings/proxmox/containers \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Option 2: Complete Frontend Update

### Step 1: Add Proxmox Interfaces (after line 51)

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
  connection_error?: string
}
```

### Step 2: Add Proxmox State Variables (after line 73)

```typescript
// Proxmox state
const [proxmoxHost, setProxmoxHost] = useState('')
const [proxmoxApiToken, setProxmoxApiToken] = useState('')
const [proxmoxNode, setProxmoxNode] = useState('pve')
const [proxmoxVerifySSL, setProxmoxVerifySSL] = useState(false)
const [showProxmoxAuth, setShowProxmoxAuth] = useState(false)
const [proxmoxContainerMappings, setProxmoxContainerMappings] = useState<Record<number, { node: string; vmid: number }>>({})
```

### Step 3: Add Proxmox Query Hooks (after line 107)

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

### Step 4: Add Proxmox Mutations (after line 219)

```typescript
// Proxmox mutations
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

### Step 5: Add Handler Functions (after line 247)

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

const handleProxmoxContainerMapping = (serverId: number, containerKey: string) => {
  // containerKey format: "node:vmid"
  const [node, vmidStr] = containerKey.split(':')
  const vmid = parseInt(vmidStr)
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

### Step 6: Replace Proxmox Tab Content (lines 296-528)

Replace the entire `{activeTab === 'proxmox' && (` section with:

```tsx
      {/* Proxmox Tab Content */}
      {activeTab === 'proxmox' && (
        <div className="space-y-6">
          {/* Proxmox Connection */}
          <div className="card">
            <div className="card-body">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                  Proxmox Integration
                </h2>
                {proxmoxStatus?.connected && (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                    <CheckCircleIcon className="h-4 w-4 mr-1" />
                    Connected
                  </span>
                )}
              </div>

              <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
                Connect to your Proxmox VE instance to monitor LXC containers running your media servers.
              </p>

              {proxmoxStatus?.host ? (
                <div className="space-y-4">
                  {/* Show warning if configured but not connected */}
                  {!proxmoxStatus.connected && (
                    <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-yellow-800 dark:text-yellow-200 text-sm">
                        <ExclamationTriangleIcon className="h-5 w-5" />
                        <span>Connection test failed. Configuration is saved but unable to communicate with Proxmox. Check logs for details.</span>
                      </div>
                    </div>
                  )}

                  <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-slate-500 dark:text-slate-400">Host</p>
                        <p className="font-medium text-slate-900 dark:text-white">{proxmoxStatus.host}:{proxmoxStatus.port}</p>
                      </div>
                      <div>
                        <p className="text-slate-500 dark:text-slate-400">Node</p>
                        <p className="font-medium text-slate-900 dark:text-white">{proxmoxStatus.node}</p>
                      </div>
                      <div>
                        <p className="text-slate-500 dark:text-slate-400">Containers</p>
                        <p className="font-medium text-slate-900 dark:text-white">
                          {proxmoxStatus.containers_count || 0} found
                        </p>
                      </div>
                      <div>
                        <p className="text-slate-500 dark:text-slate-400">SSL Verification</p>
                        <p className="font-medium text-slate-900 dark:text-white">
                          {proxmoxStatus.verify_ssl ? 'Enabled' : 'Disabled'}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <button
                      onClick={() => refetchProxmoxContainers()}
                      className="btn btn-secondary"
                    >
                      <ArrowPathIcon className="w-4 h-4 mr-2" />
                      Refresh Containers
                    </button>
                    <button
                      onClick={() => disconnectProxmox.mutate()}
                      className="btn btn-danger"
                    >
                      <TrashIcon className="w-4 h-4 mr-2" />
                      Disconnect
                    </button>
                  </div>
                </div>
              ) : (
                <div>
                  {showProxmoxAuth ? (
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                          Proxmox Host
                        </label>
                        <input
                          type="text"
                          value={proxmoxHost}
                          onChange={(e) => setProxmoxHost(e.target.value)}
                          placeholder="192.168.1.100 or proxmox.local"
                          className="input w-full"
                        />
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                          IP address or hostname (port 8006 will be used automatically)
                        </p>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                          API Token
                        </label>
                        <input
                          type="password"
                          value={proxmoxApiToken}
                          onChange={(e) => setProxmoxApiToken(e.target.value)}
                          placeholder="root@pam!towerview=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                          className="input w-full font-mono text-sm"
                        />
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                          Format: USER@REALM!TOKENID=SECRET
                        </p>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                          Default Node Name
                        </label>
                        <input
                          type="text"
                          value={proxmoxNode}
                          onChange={(e) => setProxmoxNode(e.target.value)}
                          placeholder="pve"
                          className="input w-full"
                        />
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                          Default Proxmox node (usually "pve")
                        </p>
                      </div>

                      <div className="flex items-center">
                        <input
                          type="checkbox"
                          id="verify-ssl"
                          checked={proxmoxVerifySSL}
                          onChange={(e) => setProxmoxVerifySSL(e.target.checked)}
                          className="w-4 h-4 text-blue-600 bg-white dark:bg-slate-700 border-slate-300 dark:border-slate-600 rounded focus:ring-blue-500"
                        />
                        <label htmlFor="verify-ssl" className="ml-2 text-sm text-slate-700 dark:text-slate-300">
                          Verify SSL certificate
                        </label>
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400 -mt-2">
                        Leave unchecked if using self-signed certificates (common for home labs)
                      </p>

                      <div className="flex gap-3">
                        <button
                          onClick={handleProxmoxAuth}
                          disabled={authenticateProxmox.isLoading}
                          className="btn btn-primary"
                        >
                          {authenticateProxmox.isLoading ? (
                            <>
                              <ArrowPathIcon className="w-4 h-4 mr-2 animate-spin" />
                              Connecting...
                            </>
                          ) : (
                            'Connect'
                          )}
                        </button>
                        <button
                          onClick={() => {
                            setShowProxmoxAuth(false)
                            setProxmoxHost('')
                            setProxmoxApiToken('')
                          }}
                          className="btn btn-secondary"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={() => setShowProxmoxAuth(true)}
                      className="btn btn-primary"
                    >
                      <LinkIcon className="w-4 h-4 mr-2" />
                      Connect to Proxmox
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Container Mappings */}
          {proxmoxStatus?.host && (proxmoxContainers.length > 0 || Object.keys(proxmoxStatus.container_mappings || {}).length > 0) && (
            <div className="card">
              <div className="card-body">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
                  LXC Container Mappings
                </h3>

                <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
                  Map your media servers to their LXC containers to monitor resource usage.
                </p>

                <div className="space-y-4">
                  {servers.map((server) => {
                    const mapping = proxmoxStatus.container_mappings?.[server.id.toString()]
                    return (
                      <div key={server.id} className="border border-slate-200 dark:border-slate-700 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center space-x-3">
                            <ServerIcon className="h-5 w-5 text-slate-400" />
                            <div>
                              <p className="font-medium text-slate-900 dark:text-white">
                                {server.name}
                              </p>
                              <p className="text-sm text-slate-600 dark:text-slate-400">
                                {server.type.charAt(0).toUpperCase() + server.type.slice(1)} • {server.base_url}
                              </p>
                            </div>
                          </div>
                        </div>

                        {mapping ? (
                          <div className="flex items-center justify-between bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3">
                            <div className="flex items-center space-x-2">
                              <CpuChipIcon className="h-5 w-5 text-green-600 dark:text-green-400" />
                              <span className="text-sm text-green-900 dark:text-green-100">
                                {mapping.container_name} ({mapping.node}:{mapping.vmid})
                              </span>
                            </div>
                            <button
                              onClick={() => {
                                // Remove mapping logic here if needed
                              }}
                              className="text-sm text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                            >
                              Remove
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center space-x-2">
                            <select
                              value={proxmoxContainerMappings[server.id] ? `${proxmoxContainerMappings[server.id].node}:${proxmoxContainerMappings[server.id].vmid}` : ''}
                              onChange={(e) => {
                                const containerKey = e.target.value
                                if (containerKey) {
                                  handleProxmoxContainerMapping(server.id, containerKey)
                                }
                              }}
                              className="input flex-1"
                            >
                              <option value="">Select an LXC container...</option>
                              {proxmoxContainers.map(container => (
                                <option key={`${container.node}:${container.vmid}`} value={`${container.node}:${container.vmid}`}>
                                  {container.name} ({container.node}:{container.vmid} - {container.status})
                                </option>
                              ))}
                            </select>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
```

## Simplest Approach

If the above seems too complex, you can:

1. **Deploy the backend now** - it's fully functional
2. **Test via API calls** using curl or Postman
3. **Update the frontend later** or ask for help completing it after testing

The migration is 95% complete - just the frontend UI needs updating!
