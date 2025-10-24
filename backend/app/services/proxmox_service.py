"""
Proxmox integration service for LXC container monitoring
"""
import aiohttp
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ProxmoxService:
    """Service for Proxmox VE API integration"""

    def __init__(self, db: Session):
        self.db = db
        self.session = None

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    def _get_auth_header(self, api_token: str) -> Dict[str, str]:
        """Generate authorization header for Proxmox API"""
        return {
            "Authorization": f"PVEAPIToken={api_token}"
        }

    async def test_connection(self, host: str, api_token: str, verify_ssl: bool = False) -> Dict[str, Any]:
        """
        Test connection to Proxmox API

        Args:
            host: Proxmox host (e.g., "192.168.1.100" or "proxmox.local")
            api_token: API token in format "USER@REALM!TOKENID=UUID"
            verify_ssl: Whether to verify SSL certificates

        Returns:
            Dict with success status and message
        """
        if not self.session:
            self.session = aiohttp.ClientSession()

        # Ensure host has protocol
        if not host.startswith(('http://', 'https://')):
            host = f"https://{host}"

        # Ensure host has port
        if ':8006' not in host:
            host = f"{host}:8006"

        url = f"{host}/api2/json/version"
        headers = self._get_auth_header(api_token)

        try:
            async with self.session.get(url, headers=headers, ssl=verify_ssl) as response:
                if response.status == 200:
                    data = await response.json()
                    version = data.get('data', {}).get('version', 'unknown')
                    return {
                        "success": True,
                        "message": f"Connected to Proxmox VE {version}",
                        "version": version
                    }
                elif response.status == 401:
                    return {
                        "success": False,
                        "message": "Authentication failed. Check your API token."
                    }
                else:
                    error = await response.text()
                    logger.error(f"Proxmox connection test failed: {error}")
                    return {
                        "success": False,
                        "message": f"Connection failed: HTTP {response.status}"
                    }
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Cannot connect to Proxmox host {host}: {e}")
            return {
                "success": False,
                "message": f"Cannot connect to host: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error testing Proxmox connection: {e}")
            return {
                "success": False,
                "message": f"Connection error: {str(e)}"
            }

    async def get_nodes(self, host: str, api_token: str, verify_ssl: bool = False) -> List[Dict[str, Any]]:
        """
        Get list of Proxmox nodes in the cluster

        Returns:
            List of nodes with their status
        """
        if not self.session:
            self.session = aiohttp.ClientSession()

        if not host.startswith(('http://', 'https://')):
            host = f"https://{host}"
        if ':8006' not in host:
            host = f"{host}:8006"

        url = f"{host}/api2/json/nodes"
        headers = self._get_auth_header(api_token)

        try:
            async with self.session.get(url, headers=headers, ssl=verify_ssl) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', [])
                else:
                    logger.error(f"Failed to get nodes: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching nodes: {e}")
            return []

    async def get_lxc_containers(self, host: str, node: str, api_token: str, verify_ssl: bool = False) -> List[Dict[str, Any]]:
        """
        Get list of LXC containers on a specific node

        Args:
            host: Proxmox host
            node: Node name (e.g., "pve")
            api_token: API token
            verify_ssl: Whether to verify SSL

        Returns:
            List of LXC containers with basic info
        """
        if not self.session:
            self.session = aiohttp.ClientSession()

        if not host.startswith(('http://', 'https://')):
            host = f"https://{host}"
        if ':8006' not in host:
            host = f"{host}:8006"

        url = f"{host}/api2/json/nodes/{node}/lxc"
        headers = self._get_auth_header(api_token)

        try:
            async with self.session.get(url, headers=headers, ssl=verify_ssl) as response:
                if response.status == 200:
                    data = await response.json()
                    containers = data.get('data', [])

                    # Format container data
                    result = []
                    for container in containers:
                        result.append({
                            "vmid": container.get("vmid"),
                            "name": container.get("name"),
                            "status": container.get("status"),
                            "node": node,
                            "maxmem": container.get("maxmem", 0),
                            "maxdisk": container.get("maxdisk", 0),
                            "cpus": container.get("cpus", 1)
                        })

                    return result
                else:
                    logger.error(f"Failed to get LXC containers: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching LXC containers: {e}")
            return []

    async def get_all_lxc_containers(self, host: str, api_token: str, verify_ssl: bool = False) -> List[Dict[str, Any]]:
        """
        Get all LXC containers across all nodes

        Returns:
            List of all LXC containers with node information
        """
        nodes = await self.get_nodes(host, api_token, verify_ssl)
        all_containers = []

        for node in nodes:
            node_name = node.get('node')
            if node_name:
                containers = await self.get_lxc_containers(host, node_name, api_token, verify_ssl)
                all_containers.extend(containers)

        return all_containers

    async def get_container_stats(self, host: str, node: str, vmid: int, api_token: str, verify_ssl: bool = False) -> Dict[str, Any]:
        """
        Get real-time stats for a specific LXC container

        Args:
            host: Proxmox host
            node: Node name
            vmid: Container VM ID
            api_token: API token
            verify_ssl: Whether to verify SSL

        Returns:
            Dict with CPU, memory, disk, and network stats
        """
        if not self.session:
            self.session = aiohttp.ClientSession()

        if not host.startswith(('http://', 'https://')):
            host = f"https://{host}"
        if ':8006' not in host:
            host = f"{host}:8006"

        url = f"{host}/api2/json/nodes/{node}/lxc/{vmid}/status/current"
        headers = self._get_auth_header(api_token)

        try:
            async with self.session.get(url, headers=headers, ssl=verify_ssl) as response:
                if response.status == 200:
                    data = await response.json()
                    stats = data.get('data', {})

                    # Extract metrics
                    cpu_percent = (stats.get('cpu', 0) * 100)  # CPU is returned as decimal (0.0-1.0 per core)
                    mem_used = stats.get('mem', 0)  # bytes
                    mem_max = stats.get('maxmem', 0)  # bytes
                    mem_percent = (mem_used / mem_max * 100) if mem_max > 0 else 0

                    # Convert to GB for display
                    mem_used_gb = mem_used / (1024**3)
                    mem_max_gb = mem_max / (1024**3)

                    return {
                        "cpu_percent": round(cpu_percent, 1),
                        "memory_usage_mb": round(mem_used / (1024**2), 1),
                        "memory_limit_mb": round(mem_max / (1024**2), 1),
                        "memory_percent": round(mem_percent, 1),
                        "memory_used_gb": round(mem_used_gb, 2),
                        "memory_total_gb": round(mem_max_gb, 2),
                        "status": stats.get("status"),
                        "uptime": stats.get("uptime", 0),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    logger.error(f"Failed to get container stats: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Error fetching container stats for VMID {vmid}: {e}")
            return {}

    async def container_action(self, host: str, node: str, vmid: int, action: str, api_token: str, verify_ssl: bool = False) -> Dict[str, Any]:
        """
        Perform an action on an LXC container

        Args:
            host: Proxmox host
            node: Node name
            vmid: Container VM ID
            action: Action to perform (start, stop, shutdown, reboot)
            api_token: API token
            verify_ssl: Whether to verify SSL

        Returns:
            Dict with success status and message
        """
        if not self.session:
            self.session = aiohttp.ClientSession()

        if not host.startswith(('http://', 'https://')):
            host = f"https://{host}"
        if ':8006' not in host:
            host = f"{host}:8006"

        # Map actions to API endpoints
        valid_actions = ['start', 'stop', 'shutdown', 'reboot']
        if action not in valid_actions:
            return {
                "success": False,
                "message": f"Invalid action: {action}. Valid actions: {', '.join(valid_actions)}"
            }

        url = f"{host}/api2/json/nodes/{node}/lxc/{vmid}/status/{action}"
        headers = self._get_auth_header(api_token)

        try:
            async with self.session.post(url, headers=headers, ssl=verify_ssl) as response:
                if response.status == 200:
                    return {
                        "success": True,
                        "message": f"Container {action} successful",
                        "action": action
                    }
                else:
                    error = await response.text()
                    logger.error(f"Container action failed: {error}")
                    return {
                        "success": False,
                        "message": f"Failed to {action} container: HTTP {response.status}"
                    }
        except Exception as e:
            logger.error(f"Error performing container action: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }

    async def get_container_config(self, host: str, node: str, vmid: int, api_token: str, verify_ssl: bool = False) -> Dict[str, Any]:
        """
        Get LXC container configuration

        Returns:
            Dict with container configuration details
        """
        if not self.session:
            self.session = aiohttp.ClientSession()

        if not host.startswith(('http://', 'https://')):
            host = f"https://{host}"
        if ':8006' not in host:
            host = f"{host}:8006"

        url = f"{host}/api2/json/nodes/{node}/lxc/{vmid}/config"
        headers = self._get_auth_header(api_token)

        try:
            async with self.session.get(url, headers=headers, ssl=verify_ssl) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', {})
                else:
                    logger.error(f"Failed to get container config: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Error fetching container config: {e}")
            return {}
