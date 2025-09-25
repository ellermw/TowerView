"""
Netdata Cloud integration service with OAuth2 authentication
"""
import aiohttp
import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class NetdataCloudService:
    """Service for Netdata Cloud API integration"""

    # Updated to correct Netdata Cloud API v2 endpoints
    BASE_URL = "https://app.netdata.cloud/api/v2"
    OAUTH_URL = "https://app.netdata.cloud/oauth/authorize"
    TOKEN_URL = "https://app.netdata.cloud/oauth/token"

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

    def get_oauth_url(self, client_id: str, redirect_uri: str, state: str) -> str:
        """Generate OAuth2 authorization URL for Netdata Cloud"""
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "read",
            "state": state
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.OAUTH_URL}?{query}"

    async def exchange_code_for_token(self, code: str, client_id: str, client_secret: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri
        }

        try:
            async with self.session.post(self.TOKEN_URL, data=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error = await response.text()
                    logger.error(f"Failed to exchange code: {error}")
                    return {}
        except Exception as e:
            logger.error(f"Error exchanging code: {e}")
            return {}

    async def _request(self, endpoint: str, token: str, method: str = "GET", data: Optional[Dict] = None) -> Any:
        """Make authenticated request to Netdata Cloud API"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }

        try:
            print(f"DEBUG: Making {method} request to {url}")
            print(f"DEBUG: Headers being sent: {headers}")
            logger.info(f"Making {method} request to {url}")
            logger.info(f"Headers being sent: {headers}")
            if method == "GET":
                async with self.session.get(url, headers=headers) as response:
                    response_text = await response.text()
                    logger.info(f"Response status: {response.status}")
                    logger.info(f"Response headers: {dict(response.headers)}")
                    logger.info(f"Response body: {response_text[:500] if response_text else 'Empty'}")

                    if response.status == 200:
                        try:
                            import json
                            result = json.loads(response_text) if response_text else {}
                            logger.info(f"Parsed JSON successfully: {type(result)}")
                            return result
                        except Exception as e:
                            logger.error(f"Failed to parse JSON: {e}")
                            return {}
                    else:
                        logger.error(f"Netdata API error: {response.status} - {response_text}")
                        return {}
            elif method == "POST":
                async with self.session.post(url, headers=headers, json=data) as response:
                    response_text = await response.text()
                    if response.status == 200:
                        try:
                            return await response.json() if response_text else {}
                        except:
                            return {}
                    else:
                        logger.error(f"Netdata API error: {response.status} - {response_text}")
                        return {}
        except Exception as e:
            logger.error(f"Failed to fetch from Netdata Cloud: {e}")
            return {}

    async def get_spaces(self, token: str) -> List[Dict[str, Any]]:
        """Get all spaces accessible to the user"""
        response = await self._request("/spaces", token)
        # API returns array directly, not wrapped in data field
        if isinstance(response, list):
            return response
        return response.get("data", []) if isinstance(response, dict) else []

    async def get_rooms(self, token: str, space_id: str) -> List[Dict[str, Any]]:
        """Get all rooms in a space"""
        response = await self._request(f"/spaces/{space_id}/rooms", token)
        # API returns array directly, not wrapped in data field
        if isinstance(response, list):
            return response
        return response.get("data", []) if isinstance(response, dict) else []

    async def get_nodes(self, token: str, space_id: str, room_id: str = None) -> List[Dict[str, Any]]:
        """Get all nodes (agents) in a space or room"""
        # Get all rooms first if no room_id specified
        if not room_id:
            rooms = await self.get_rooms(token, space_id)
            if rooms:
                # Use the first room (usually "All nodes")
                room_id = rooms[0].get("id")
            else:
                return []

        endpoint = f"/spaces/{space_id}/rooms/{room_id}/nodes"
        response = await self._request(endpoint, token)

        # API returns array directly, not wrapped in data field
        if isinstance(response, list):
            nodes = response
        else:
            nodes = response.get("data", []) if isinstance(response, dict) else []

        # Extract relevant node information
        result = []
        for i, node in enumerate(nodes):
            # Log first node structure for debugging
            if i == 0:
                logger.info(f"Sample node structure: {json.dumps(node, indent=2) if isinstance(node, dict) else node}")

            # Handle case where node might be a string (node ID) instead of dict
            if isinstance(node, str):
                # If node is just a string ID, create minimal node info
                result.append({
                    "id": node,
                    "name": node,
                    "hostname": node,
                    "os": "",
                    "version": "",
                    "status": "unknown",
                    "last_seen": 0,
                    "machine_guid": node,
                    "charts": {},
                    "capabilities": []
                })
            else:
                # Check various possible status field locations
                # The state field can be a string like "reachable" or "unreachable"
                status = "offline"
                last_seen = 0

                # Check for status based on state field
                state = node.get("state", "")
                if state == "reachable":
                    status = "online"
                elif state == "unreachable":
                    status = "offline"
                elif state == "online":
                    status = "online"

                # Also check other possible status indicators
                if node.get("isOnline"):
                    status = "online"
                elif node.get("reachable"):
                    status = "online"

                # Get last seen timestamp - convert to milliseconds if needed
                # The API doesn't seem to provide a last_seen timestamp, so we'll use current time for online nodes
                if status == "online":
                    from datetime import datetime
                    last_seen = int(datetime.utcnow().timestamp() * 1000)
                else:
                    last_seen = 0

                result.append({
                    "id": node.get("id", ""),
                    "name": node.get("name", node.get("hostname", "")),
                    "hostname": node.get("hostname", node.get("name", "")),
                    "os": node.get("osName", node.get("os", node.get("osname", ""))),
                    "version": node.get("version", node.get("netdataVersion", "")),
                    "status": status,
                    "last_seen": last_seen,
                    "machine_guid": node.get("machineGUID", node.get("machine_guid", node.get("machineGuid", ""))),
                    "charts": node.get("charts", {}),
                    "capabilities": node.get("capabilities", [])
                })

        return result

    async def get_node_charts(self, token: str, space_id: str, node_id: str) -> Dict[str, Any]:
        """Get available charts (metrics) for a node - using contexts"""
        # Use the contexts endpoint to get available metrics
        response = await self._request(f"/contexts?nodes={node_id}", token)

        # Convert contexts to charts-like format
        charts = {}
        if isinstance(response, list):
            for context in response:
                if isinstance(context, dict):
                    context_id = context.get("id", "")
                    charts[context_id] = context
                elif isinstance(context, str):
                    charts[context] = {"id": context}

        return charts

    async def get_node_data(self, token: str, space_id: str, node_id: str, chart: str,
                           after: int = -600, points: int = 60) -> Dict[str, Any]:
        """
        Get metric data for a specific chart

        Args:
            token: API token
            space_id: Netdata Cloud space ID
            node_id: Node (agent) ID
            chart: Chart ID (e.g., 'system.cpu', 'gpu.intel_gpu_busy')
            after: Seconds to look back (negative value)
            points: Number of data points to return
        """
        # Use the global data endpoint with node filter
        endpoint = "/data"
        params = f"?nodes={node_id}&contexts={chart}&after={after}&points={points}&format=json"

        response = await self._request(endpoint + params, token)
        return response

    async def get_docker_containers(self, token: str, space_id: str, node_id: str) -> List[Dict[str, Any]]:
        """Get list of Docker containers on a node"""
        containers = []

        # Get all charts to find docker container charts
        charts = await self.get_node_charts(token, space_id, node_id)

        # Docker container charts follow pattern: cgroup_<container_name>.cpu, cgroup_<container_name>.mem, etc.
        container_names = set()
        for chart_id in charts.keys():
            if chart_id.startswith('cgroup_'):
                # Extract container name from chart ID
                parts = chart_id.split('.')
                if len(parts) > 0:
                    container_name = parts[0].replace('cgroup_', '')
                    container_names.add(container_name)

        for name in container_names:
            containers.append({
                "name": name,
                "id": name,
                "display_name": name.replace('_', ' ').title()
            })

        return sorted(containers, key=lambda x: x['name'])

    async def get_container_metrics(self, token: str, space_id: str, node_id: str, container_name: str) -> Dict[str, Any]:
        """Get metrics for a specific Docker container"""
        metrics = {
            "cpu_usage": 0,
            "memory_usage": 0,
            "memory_used_mb": 0,
            "memory_limit_mb": 0,
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            # CPU usage for container
            cpu_chart = f"cgroup_{container_name}.cpu"
            cpu_data = await self.get_node_data(token, space_id, node_id, cpu_chart, after=-60, points=1)
            if cpu_data:
                parsed = self._parse_metric_data(cpu_data)
                # Docker CPU is usually reported as percentage
                metrics["cpu_usage"] = sum(parsed.values())

            # Memory usage for container
            mem_chart = f"cgroup_{container_name}.mem"
            mem_data = await self.get_node_data(token, space_id, node_id, mem_chart, after=-60, points=1)
            if mem_data:
                parsed = self._parse_metric_data(mem_data)
                # Memory values are in bytes, convert to MB
                cache = parsed.get("cache", 0) / (1024 * 1024)
                rss = parsed.get("rss", 0) / (1024 * 1024)
                used = cache + rss

                # Try to get memory limit
                limit_chart = f"cgroup_{container_name}.mem_limit"
                limit_data = await self.get_node_data(token, space_id, node_id, limit_chart, after=-60, points=1)
                if limit_data:
                    limit_parsed = self._parse_metric_data(limit_data)
                    limit = sum(limit_parsed.values()) / (1024 * 1024)
                else:
                    # Fallback: estimate from host total memory
                    limit = 8192  # Default 8GB limit assumption

                metrics["memory_used_mb"] = used
                metrics["memory_limit_mb"] = limit
                if limit > 0:
                    metrics["memory_usage"] = (used / limit) * 100

        except Exception as e:
            logger.error(f"Error fetching container metrics for {container_name}: {e}")

        return metrics

    async def get_gpu_metrics(self, token: str, space_id: str, node_id: str) -> Dict[str, Any]:
        """Get GPU metrics from a node"""
        gpu_data = {
            "nvidia": {},
            "intel": {},
            "amd": {},
            "timestamp": datetime.utcnow().isoformat()
        }

        # Get available charts
        charts = await self.get_node_charts(token, space_id, node_id)

        # Look for GPU-related charts
        for chart_id, chart_info in charts.items():
            chart_lower = chart_id.lower()

            # NVIDIA GPU metrics
            if 'nvidia' in chart_lower or 'gpu_nvidia' in chart_lower:
                data = await self.get_node_data(token, space_id, node_id, chart_id, after=-60, points=1)
                if data:
                    gpu_data["nvidia"][chart_id] = self._parse_metric_data(data)

            # Intel GPU metrics (from intel_gpu_top)
            elif 'intel' in chart_lower or 'gpu.intel' in chart_lower:
                data = await self.get_node_data(token, space_id, node_id, chart_id, after=-60, points=1)
                if data:
                    gpu_data["intel"][chart_id] = self._parse_metric_data(data)

            # AMD GPU metrics
            elif 'amd' in chart_lower or 'gpu_amd' in chart_lower or 'radeon' in chart_lower:
                data = await self.get_node_data(token, space_id, node_id, chart_id, after=-60, points=1)
                if data:
                    gpu_data["amd"][chart_id] = self._parse_metric_data(data)

        return gpu_data

    async def get_system_metrics(self, token: str, space_id: str, node_id: str) -> Dict[str, Any]:
        """Get general system metrics from a node"""
        metrics = {
            "cpu_usage": 0,
            "memory_usage": 0,
            "memory_used_gb": 0,
            "memory_total_gb": 0,
            "network_rx_mbps": 0,
            "network_tx_mbps": 0,
            "disk_read_mbps": 0,
            "disk_write_mbps": 0,
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            # CPU usage
            cpu_data = await self.get_node_data(token, space_id, node_id, "system.cpu", after=-60, points=1)
            if cpu_data:
                parsed = self._parse_metric_data(cpu_data)
                # Sum all non-idle CPU usage
                for key, value in parsed.items():
                    if 'idle' not in key.lower():
                        metrics["cpu_usage"] += value

            # Memory usage
            mem_data = await self.get_node_data(token, space_id, node_id, "system.ram", after=-60, points=1)
            if mem_data:
                parsed = self._parse_metric_data(mem_data)
                used = parsed.get("used", 0)
                free = parsed.get("free", 0)
                cached = parsed.get("cached", 0)
                buffers = parsed.get("buffers", 0)

                total = used + free + cached + buffers
                if total > 0:
                    metrics["memory_usage"] = (used / total) * 100
                    metrics["memory_used_gb"] = used / (1024 * 1024 * 1024)
                    metrics["memory_total_gb"] = total / (1024 * 1024 * 1024)

            # Network usage
            net_data = await self.get_node_data(token, space_id, node_id, "system.net", after=-60, points=1)
            if net_data:
                parsed = self._parse_metric_data(net_data)
                # Convert from kilobits to megabits
                metrics["network_rx_mbps"] = parsed.get("received", 0) / 1000
                metrics["network_tx_mbps"] = parsed.get("sent", 0) / 1000

            # Disk I/O
            disk_data = await self.get_node_data(token, space_id, node_id, "system.io", after=-60, points=1)
            if disk_data:
                parsed = self._parse_metric_data(disk_data)
                # Convert from kilobytes to megabytes
                metrics["disk_read_mbps"] = parsed.get("in", 0) / 1024
                metrics["disk_write_mbps"] = parsed.get("out", 0) / 1024

        except Exception as e:
            logger.error(f"Error fetching system metrics: {e}")

        return metrics

    def _parse_metric_data(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Parse metric data from Netdata API response"""
        result = {}

        if not data:
            return result

        # Handle new API v2 format
        if "results" in data:
            # New format: data.results[0].data
            results = data.get("results", [])
            if results and isinstance(results, list):
                first_result = results[0]
                data_points = first_result.get("data", [])
                labels = first_result.get("labels", [])
                dimensions = first_result.get("dimensions", {})

                # Parse the latest data point
                if data_points and isinstance(data_points, list):
                    latest = data_points[-1] if data_points else []  # Get most recent
                    if latest and isinstance(latest, list):
                        # First element is timestamp, rest are values
                        for i, (dim_id, dim_info) in enumerate(dimensions.items(), 1):
                            if i < len(latest):
                                dim_name = dim_info.get("name", dim_id)
                                result[dim_name] = float(latest[i]) if latest[i] is not None else 0

        # Fallback to old format
        elif "data" in data:
            data_points = data.get("data", [])
            if data_points:
                latest = data_points[0] if isinstance(data_points[0], list) else data_points
                dimensions = data.get("dimension_names", [])
                dimension_ids = data.get("dimension_ids", [])

                for i, dim_name in enumerate(dimensions):
                    if i < len(latest) - 1:
                        value = latest[i + 1] if isinstance(latest, list) else latest.get(dimension_ids[i], 0)
                        result[dim_name] = float(value) if value is not None else 0

        return result

    async def test_connection(self, token: str) -> bool:
        """Test if the API token is valid"""
        try:
            print(f"DEBUG: Testing connection with token: {token[:50]}...")
            logger.info(f"Testing connection with token: {token[:20]}...")
            # Try to get spaces - this is a simple endpoint that should work with a valid token
            spaces = await self.get_spaces(token)
            logger.info(f"Spaces response type: {type(spaces)}, content: {spaces}")

            if spaces and isinstance(spaces, list) and len(spaces) > 0:
                logger.info(f"Successfully connected to Netdata Cloud. Found {len(spaces)} spaces.")
                return True

            logger.warning(f"No spaces found or invalid response format. Response: {spaces}")
            return False

        except Exception as e:
            logger.error(f"Test connection failed with exception: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    async def save_integration(self, user_id: int, token: str, space_id: str = None) -> bool:
        """Save Netdata integration settings to database"""
        from ..models.settings import NetdataIntegration

        try:
            # If no space_id provided, get the first available space
            if not space_id:
                spaces = await self.get_spaces(token)
                if spaces and isinstance(spaces, list) and len(spaces) > 0:
                    if isinstance(spaces[0], dict):
                        space_id = spaces[0].get("id")
                        logger.info(f"Auto-selected space: {spaces[0].get('name', 'Unknown')} ({space_id})")
                    else:
                        space_id = spaces[0]
                        logger.info(f"Auto-selected space ID: {space_id}")

            # Check if integration already exists
            integration = self.db.query(NetdataIntegration).filter_by(created_by_id=user_id).first()

            if not integration:
                integration = NetdataIntegration(
                    name="Netdata Cloud",
                    created_by_id=user_id
                )
                self.db.add(integration)

            # Update settings
            integration.api_token = token  # In production, encrypt this
            integration.space_id = space_id
            integration.enabled = True
            integration.updated_at = datetime.utcnow()

            # Get and cache nodes
            if space_id:
                nodes = await self.get_nodes(token, space_id)
                integration.cached_nodes = nodes
                integration.nodes_updated_at = datetime.utcnow()
                logger.info(f"Cached {len(nodes)} nodes from Netdata Cloud")

            self.db.commit()
            return True
        except Exception as e:
            import traceback
            logger.error(f"Failed to save integration: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.db.rollback()
            return False