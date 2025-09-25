"""
Portainer integration service for Docker container monitoring
"""
import aiohttp
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class PortainerService:
    """Service for Portainer API integration"""

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

    async def authenticate(self, url: str, username: str, password: str) -> Dict[str, Any]:
        """Authenticate with Portainer and get JWT token"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        auth_url = f"{url}/api/auth"
        data = {
            "username": username,
            "password": password
        }

        try:
            async with self.session.post(auth_url, json=data, ssl=False) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "jwt": result.get("jwt"),
                        "message": "Authentication successful"
                    }
                else:
                    error = await response.text()
                    logger.error(f"Portainer auth failed: {error}")
                    return {
                        "success": False,
                        "message": f"Authentication failed: {response.status}"
                    }
        except Exception as e:
            logger.error(f"Error connecting to Portainer: {e}")
            return {
                "success": False,
                "message": f"Connection error: {str(e)}"
            }

    async def get_endpoints(self, url: str, token: str) -> List[Dict[str, Any]]:
        """Get list of Docker endpoints (environments) from Portainer"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            async with self.session.get(f"{url}/api/endpoints", headers=headers, ssl=False) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to get endpoints: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching endpoints: {e}")
            return []

    async def get_containers(self, url: str, token: str, endpoint_id: int = 1) -> List[Dict[str, Any]]:
        """Get list of Docker containers from Portainer"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            # Portainer API for Docker containers
            containers_url = f"{url}/api/endpoints/{endpoint_id}/docker/containers/json?all=true"

            async with self.session.get(containers_url, headers=headers, ssl=False) as response:
                if response.status == 200:
                    containers = await response.json()
                    # Filter and format container data
                    result = []
                    for container in containers:
                        # Extract container name (remove leading /)
                        names = container.get("Names", [])
                        name = names[0].lstrip("/") if names else "unknown"

                        result.append({
                            "id": container.get("Id"),
                            "name": name,
                            "image": container.get("Image"),
                            "state": container.get("State"),
                            "status": container.get("Status"),
                            "created": container.get("Created")
                        })

                    return result
                else:
                    logger.error(f"Failed to get containers: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching containers: {e}")
            return []

    async def get_container_stats(self, url: str, token: str, container_id: str, endpoint_id: int = 1) -> Dict[str, Any]:
        """Get real-time stats for a specific container"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            # Docker stats endpoint through Portainer
            stats_url = f"{url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/stats?stream=false"

            async with self.session.get(stats_url, headers=headers, ssl=False) as response:
                if response.status == 200:
                    stats = await response.json()

                    # Parse Docker stats format
                    cpu_percent = 0.0
                    memory_usage_mb = 0
                    memory_limit_mb = 0
                    memory_percent = 0.0

                    # Calculate CPU percentage
                    if stats.get("cpu_stats") and stats.get("precpu_stats"):
                        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                                   stats["precpu_stats"]["cpu_usage"]["total_usage"]
                        system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                                      stats["precpu_stats"]["system_cpu_usage"]

                        if system_delta > 0 and cpu_delta > 0:
                            cpu_count = len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [1]))
                            cpu_percent = (cpu_delta / system_delta) * cpu_count * 100.0

                    # Calculate memory usage
                    if stats.get("memory_stats"):
                        memory_stats = stats["memory_stats"]
                        memory_usage = memory_stats.get("usage", 0)
                        memory_limit = memory_stats.get("limit", 0)

                        # Get more accurate memory usage (exclude cache/buffers)
                        stats_details = memory_stats.get("stats", {})

                        # Try different methods to get actual memory usage
                        if "rss" in stats_details:
                            # RSS (Resident Set Size) is actual physical memory used
                            memory_usage = stats_details["rss"]
                        elif "active_anon" in stats_details:
                            # Active anonymous memory (heap, stack)
                            memory_usage = stats_details["active_anon"]
                        else:
                            # Fallback: subtract cache from total usage
                            cache = stats_details.get("cache", 0)
                            memory_usage = memory_usage - cache if memory_usage > cache else memory_usage

                        memory_usage_mb = memory_usage / (1024 * 1024)

                        # Check if limit is reasonable (less than 1TB, more than container usage)
                        # If not, it's probably showing host memory
                        if memory_limit > 1099511627776 or memory_limit == 9223372036854771712:
                            # Limit is unrestricted or showing host memory
                            # Try to get host memory from /proc/meminfo through container
                            memory_limit_mb = 0  # Will be set as "unlimited"
                            memory_percent = 0  # Can't calculate percentage without real limit
                        else:
                            memory_limit_mb = memory_limit / (1024 * 1024)
                            if memory_limit > 0:
                                memory_percent = (memory_usage / memory_limit) * 100.0

                    return {
                        "cpu_percent": round(cpu_percent, 1),
                        "memory_usage_mb": round(memory_usage_mb, 1),
                        "memory_limit_mb": round(memory_limit_mb, 1),
                        "memory_percent": round(memory_percent, 1),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    logger.error(f"Failed to get container stats: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Error fetching container stats: {e}")
            return {}

    async def get_gpu_stats(self, url: str, token: str, container_id: str, endpoint_id: int = 1) -> Dict[str, Any]:
        """Get GPU stats by executing intel_gpu_top in the container"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            # Create exec instance to run intel_gpu_top
            exec_url = f"{url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/exec"
            exec_data = {
                "AttachStdout": True,
                "AttachStderr": True,
                "Cmd": ["sh", "-c", "timeout 1 intel_gpu_top -J -s 100 2>/dev/null | head -2 | tail -1"],
                "Privileged": True
            }

            async with self.session.post(exec_url, headers=headers, json=exec_data, ssl=False) as response:
                if response.status == 201:
                    exec_result = await response.json()
                    exec_id = exec_result.get("Id")

                    # Start the exec instance
                    start_url = f"{url}/api/endpoints/{endpoint_id}/docker/exec/{exec_id}/start"
                    start_data = {
                        "Detach": False,
                        "Tty": False
                    }

                    async with self.session.post(start_url, headers=headers, json=start_data, ssl=False) as start_response:
                        if start_response.status == 200:
                            output = await start_response.text()

                            # Parse intel_gpu_top JSON output
                            import json as json_module
                            try:
                                # Clean the output - remove any non-JSON data
                                lines = output.strip().split('\n')
                                for line in lines:
                                    if line.strip().startswith('{'):
                                        gpu_data = json_module.loads(line.strip())

                                        # Extract GPU usage percentages
                                        engines = gpu_data.get("engines", {})

                                        # Get render/3D usage (main GPU usage)
                                        render_usage = engines.get("Render/3D", {}).get("busy", 0)

                                        # Get video decode/encode usage
                                        video_usage = engines.get("Video", {}).get("busy", 0)
                                        video_enhance = engines.get("VideoEnhance", {}).get("busy", 0)

                                        # Get overall GPU busy percentage
                                        gpu_busy = gpu_data.get("engines-busy", 0)

                                        return {
                                            "gpu_usage": round(gpu_busy, 1),
                                            "render_usage": round(render_usage, 1),
                                            "video_usage": round(video_usage, 1),
                                            "video_enhance": round(video_enhance, 1),
                                            "available": True
                                        }
                            except json_module.JSONDecodeError:
                                logger.debug(f"Could not parse intel_gpu_top output: {output}")

                    return {"available": False, "gpu_usage": 0}
                else:
                    return {"available": False, "gpu_usage": 0}
        except Exception as e:
            logger.debug(f"GPU stats not available: {e}")
            return {"available": False, "gpu_usage": 0}

    async def save_integration(self, user_id: int, url: str, token: str, endpoint_id: int = 1) -> bool:
        """Save Portainer integration settings to database"""
        from ..models.settings import PortainerIntegration

        try:
            # Get the actual endpoint ID from Portainer
            endpoints = await self.get_endpoints(url, token)
            if endpoints and len(endpoints) > 0:
                # Use the first endpoint's ID
                actual_endpoint_id = endpoints[0].get('Id', endpoint_id)
                logger.info(f"Using Portainer endpoint ID: {actual_endpoint_id}")
            else:
                actual_endpoint_id = endpoint_id
                logger.warning(f"No endpoints found, using default ID: {actual_endpoint_id}")

            # Check if integration already exists
            integration = self.db.query(PortainerIntegration).filter_by(created_by_id=user_id).first()

            if not integration:
                integration = PortainerIntegration(
                    name="Portainer",
                    created_by_id=user_id
                )
                self.db.add(integration)

            # Update settings
            integration.url = url
            integration.api_token = token  # In production, encrypt this
            integration.endpoint_id = actual_endpoint_id
            integration.enabled = True
            integration.updated_at = datetime.utcnow()

            # Get and cache containers using the correct endpoint ID
            containers = await self.get_containers(url, token, actual_endpoint_id)
            integration.cached_containers = containers
            integration.containers_updated_at = datetime.utcnow()
            logger.info(f"Cached {len(containers)} containers from Portainer")

            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save integration: {e}")
            self.db.rollback()
            return False

    async def test_connection(self, url: str, token: str) -> bool:
        """Test if the Portainer connection is valid"""
        try:
            endpoints = await self.get_endpoints(url, token)
            return len(endpoints) > 0
        except Exception as e:
            logger.error(f"Test connection failed: {e}")
            return False

    async def container_action(self, url: str, token: str, container_id: str, action: str, endpoint_id: int = 1) -> Dict[str, Any]:
        """Perform an action on a container (start, stop, restart, pause, unpause)"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        headers = {
            "Authorization": f"Bearer {token}"
        }

        # Map actions to Docker API endpoints
        action_map = {
            "start": "start",
            "stop": "stop",
            "restart": "restart",
            "pause": "pause",
            "unpause": "unpause",
            "kill": "kill"
        }

        if action not in action_map:
            return {
                "success": False,
                "message": f"Invalid action: {action}"
            }

        try:
            action_url = f"{url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/{action_map[action]}"

            async with self.session.post(action_url, headers=headers, ssl=False) as response:
                if response.status in [200, 204]:
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
                        "message": f"Failed to {action} container: {response.status}",
                        "error": error
                    }
        except Exception as e:
            logger.error(f"Error performing container action: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }

    async def get_container_info(self, url: str, token: str, container_id: str, endpoint_id: int = 1) -> Dict[str, Any]:
        """Get detailed information about a specific container"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            info_url = f"{url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/json"

            async with self.session.get(info_url, headers=headers, ssl=False) as response:
                if response.status == 200:
                    container_info = await response.json()

                    # Extract relevant information
                    return {
                        "id": container_info.get("Id"),
                        "name": container_info.get("Name", "").lstrip("/"),
                        "state": container_info.get("State", {}).get("Status"),
                        "running": container_info.get("State", {}).get("Running", False),
                        "paused": container_info.get("State", {}).get("Paused", False),
                        "restarting": container_info.get("State", {}).get("Restarting", False),
                        "image": container_info.get("Config", {}).get("Image"),
                        "created": container_info.get("Created"),
                        "started_at": container_info.get("State", {}).get("StartedAt"),
                        "ports": container_info.get("NetworkSettings", {}).get("Ports", {}),
                        "mounts": container_info.get("Mounts", [])
                    }
                else:
                    logger.error(f"Failed to get container info: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Error fetching container info: {e}")
            return {}