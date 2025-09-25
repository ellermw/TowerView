"""
Netdata integration service for system metrics
"""
import aiohttp
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class NetdataService:
    """Service for fetching metrics from Netdata"""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize Netdata service

        Args:
            base_url: Netdata base URL (e.g., http://server:19999)
            api_key: Optional API key if Netdata requires authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = None

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def _request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a request to Netdata API"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        url = f"{self.base_url}{endpoint}"
        headers = {}
        if self.api_key:
            headers['X-Auth-Token'] = self.api_key

        try:
            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Netdata API error: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Failed to fetch from Netdata: {e}")
            return {}

    async def get_gpu_metrics(self) -> Dict[str, Any]:
        """
        Fetch GPU metrics from Netdata

        Returns GPU utilization, memory usage, temperature, and power consumption
        """
        gpu_metrics = {
            "nvidia": [],
            "intel": [],
            "amd": [],
            "total_gpu_count": 0,
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            # Get available charts to find GPU-related ones
            charts = await self._request('/api/v1/charts')

            if not charts:
                return gpu_metrics

            # Process NVIDIA GPU metrics
            nvidia_gpus = await self._get_nvidia_metrics(charts)
            gpu_metrics["nvidia"] = nvidia_gpus

            # Process Intel GPU metrics
            intel_gpus = await self._get_intel_metrics(charts)
            gpu_metrics["intel"] = intel_gpus

            # Process AMD GPU metrics
            amd_gpus = await self._get_amd_metrics(charts)
            gpu_metrics["amd"] = amd_gpus

            gpu_metrics["total_gpu_count"] = len(nvidia_gpus) + len(intel_gpus) + len(amd_gpus)

        except Exception as e:
            logger.error(f"Error fetching GPU metrics: {e}")

        return gpu_metrics

    async def _get_nvidia_metrics(self, charts: Dict) -> List[Dict[str, Any]]:
        """Fetch NVIDIA GPU metrics"""
        nvidia_gpus = []

        try:
            # Look for nvidia-smi charts
            for chart_id, chart_info in charts.get('charts', {}).items():
                if 'nvidia' in chart_id.lower() or 'gpu' in chart_id.lower():
                    # Fetch current values for this chart
                    data = await self._request(f'/api/v1/data', {
                        'chart': chart_id,
                        'points': 1,
                        'after': -1,
                        'options': 'jsonwrap'
                    })

                    if data and 'latest_values' in data:
                        gpu_info = self._parse_nvidia_data(chart_id, data)
                        if gpu_info:
                            nvidia_gpus.append(gpu_info)

        except Exception as e:
            logger.error(f"Error fetching NVIDIA metrics: {e}")

        return nvidia_gpus

    async def _get_intel_metrics(self, charts: Dict) -> List[Dict[str, Any]]:
        """Fetch Intel GPU metrics"""
        intel_gpus = []

        try:
            # Look for intel_gpu charts
            for chart_id, chart_info in charts.get('charts', {}).items():
                if 'intel' in chart_id.lower() and 'gpu' in chart_id.lower():
                    # Fetch current values
                    data = await self._request(f'/api/v1/data', {
                        'chart': chart_id,
                        'points': 1,
                        'after': -1,
                        'options': 'jsonwrap'
                    })

                    if data and 'latest_values' in data:
                        gpu_info = self._parse_intel_data(chart_id, data)
                        if gpu_info:
                            intel_gpus.append(gpu_info)

        except Exception as e:
            logger.error(f"Error fetching Intel metrics: {e}")

        return intel_gpus

    async def _get_amd_metrics(self, charts: Dict) -> List[Dict[str, Any]]:
        """Fetch AMD GPU metrics"""
        amd_gpus = []

        try:
            # Look for AMD/Radeon charts
            for chart_id, chart_info in charts.get('charts', {}).items():
                if ('amd' in chart_id.lower() or 'radeon' in chart_id.lower()) and 'gpu' in chart_id.lower():
                    # Fetch current values
                    data = await self._request(f'/api/v1/data', {
                        'chart': chart_id,
                        'points': 1,
                        'after': -1,
                        'options': 'jsonwrap'
                    })

                    if data and 'latest_values' in data:
                        gpu_info = self._parse_amd_data(chart_id, data)
                        if gpu_info:
                            amd_gpus.append(gpu_info)

        except Exception as e:
            logger.error(f"Error fetching AMD metrics: {e}")

        return amd_gpus

    def _parse_nvidia_data(self, chart_id: str, data: Dict) -> Optional[Dict[str, Any]]:
        """Parse NVIDIA GPU data from Netdata response"""
        try:
            values = data.get('latest_values', [])
            labels = data.get('dimension_names', [])

            gpu_info = {
                "id": chart_id,
                "name": f"NVIDIA GPU {chart_id.split('.')[-1] if '.' in chart_id else '0'}",
                "utilization": 0,
                "memory_used_mb": 0,
                "memory_total_mb": 0,
                "temperature": 0,
                "power_watts": 0
            }

            # Map Netdata dimensions to our metrics
            for i, label in enumerate(labels):
                if i < len(values):
                    value = values[i]
                    label_lower = label.lower()

                    if 'utilization' in label_lower and 'gpu' in label_lower:
                        gpu_info["utilization"] = float(value)
                    elif 'memory' in label_lower and 'used' in label_lower:
                        gpu_info["memory_used_mb"] = float(value)
                    elif 'memory' in label_lower and 'total' in label_lower:
                        gpu_info["memory_total_mb"] = float(value)
                    elif 'temperature' in label_lower:
                        gpu_info["temperature"] = float(value)
                    elif 'power' in label_lower:
                        gpu_info["power_watts"] = float(value)

            return gpu_info

        except Exception as e:
            logger.error(f"Error parsing NVIDIA data: {e}")
            return None

    def _parse_intel_data(self, chart_id: str, data: Dict) -> Optional[Dict[str, Any]]:
        """Parse Intel GPU data from Netdata response"""
        try:
            values = data.get('latest_values', [])
            labels = data.get('dimension_names', [])

            gpu_info = {
                "id": chart_id,
                "name": "Intel GPU",
                "utilization": 0,
                "frequency_mhz": 0,
                "rc6_residency": 0  # Power saving state
            }

            # Map Netdata dimensions to our metrics
            for i, label in enumerate(labels):
                if i < len(values):
                    value = values[i]
                    label_lower = label.lower()

                    if 'busy' in label_lower or 'utilization' in label_lower:
                        gpu_info["utilization"] = float(value)
                    elif 'frequency' in label_lower:
                        gpu_info["frequency_mhz"] = float(value)
                    elif 'rc6' in label_lower:
                        gpu_info["rc6_residency"] = float(value)

            return gpu_info

        except Exception as e:
            logger.error(f"Error parsing Intel data: {e}")
            return None

    def _parse_amd_data(self, chart_id: str, data: Dict) -> Optional[Dict[str, Any]]:
        """Parse AMD GPU data from Netdata response"""
        try:
            values = data.get('latest_values', [])
            labels = data.get('dimension_names', [])

            gpu_info = {
                "id": chart_id,
                "name": f"AMD GPU {chart_id.split('.')[-1] if '.' in chart_id else '0'}",
                "utilization": 0,
                "memory_used_mb": 0,
                "temperature": 0
            }

            # Map Netdata dimensions to our metrics
            for i, label in enumerate(labels):
                if i < len(values):
                    value = values[i]
                    label_lower = label.lower()

                    if 'gpu' in label_lower and ('busy' in label_lower or 'utilization' in label_lower):
                        gpu_info["utilization"] = float(value)
                    elif 'vram' in label_lower or ('memory' in label_lower and 'used' in label_lower):
                        gpu_info["memory_used_mb"] = float(value)
                    elif 'temperature' in label_lower:
                        gpu_info["temperature"] = float(value)

            return gpu_info

        except Exception as e:
            logger.error(f"Error parsing AMD data: {e}")
            return None

    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get overall system metrics"""
        metrics = {
            "cpu_usage": 0,
            "memory_usage": 0,
            "network_rx_mbps": 0,
            "network_tx_mbps": 0,
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            # Get CPU usage
            cpu_data = await self._request('/api/v1/data', {
                'chart': 'system.cpu',
                'points': 1,
                'after': -1,
                'options': 'jsonwrap'
            })

            if cpu_data and 'latest_values' in cpu_data:
                # Sum all CPU dimensions except idle
                labels = cpu_data.get('dimension_names', [])
                values = cpu_data.get('latest_values', [])

                for i, label in enumerate(labels):
                    if i < len(values) and 'idle' not in label.lower():
                        metrics["cpu_usage"] += float(values[i])

            # Get memory usage
            mem_data = await self._request('/api/v1/data', {
                'chart': 'system.ram',
                'points': 1,
                'after': -1,
                'options': 'jsonwrap'
            })

            if mem_data and 'latest_values' in mem_data:
                labels = mem_data.get('dimension_names', [])
                values = mem_data.get('latest_values', [])

                used = 0
                total = 0
                for i, label in enumerate(labels):
                    if i < len(values):
                        if 'used' in label.lower():
                            used = float(values[i])
                        elif 'total' in label.lower():
                            total = float(values[i])

                if total > 0:
                    metrics["memory_usage"] = (used / total) * 100

            # Get network usage
            net_data = await self._request('/api/v1/data', {
                'chart': 'system.net',
                'points': 1,
                'after': -1,
                'options': 'jsonwrap'
            })

            if net_data and 'latest_values' in net_data:
                labels = net_data.get('dimension_names', [])
                values = net_data.get('latest_values', [])

                for i, label in enumerate(labels):
                    if i < len(values):
                        # Convert from kilobits to megabits
                        if 'received' in label.lower():
                            metrics["network_rx_mbps"] = float(values[i]) / 1000
                        elif 'sent' in label.lower():
                            metrics["network_tx_mbps"] = float(values[i]) / 1000

        except Exception as e:
            logger.error(f"Error fetching system metrics: {e}")

        return metrics