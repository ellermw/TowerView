import httpx
import logging
from typing import List, Dict, Any, Optional
from .base import BaseProvider

logger = logging.getLogger(__name__)


class EmbyProvider(BaseProvider):
    def __init__(self, server, credentials):
        super().__init__(server, credentials)
        # Support multiple credential field names for Emby
        self.api_key = credentials.get("api_key") or credentials.get("token") or credentials.get("api_token")
        self.admin_token = credentials.get("admin_token") or credentials.get("api_token") or credentials.get("token")
        logger.debug(f"Emby provider initialized - has_api_key: {'Yes' if self.api_key else 'No'}, has_admin_token: {'Yes' if self.admin_token else 'No'}")
        logger.debug(f"Available credential keys: {list(credentials.keys())}")

    async def connect(self) -> bool:
        """Test connection to Emby server"""
        try:
            logger.debug(f"Testing Emby connection to: {self.base_url}")
            if self.api_key:
                logger.debug(f"Using API key for authentication")
            else:
                logger.warning("No API key provided")
                return False

            async with httpx.AsyncClient(verify=False) as client:
                # Ensure base_url doesn't end with slash to avoid double slashes
                base_url = self.base_url.rstrip('/')
                url = f"{base_url}/System/Info"
                headers = {"X-Emby-Token": self.api_key} if self.api_key else {}

                logger.debug(f"Emby connection URL: {url}")

                response = await client.get(
                    url,
                    headers=headers,
                    timeout=10.0
                )

                logger.debug(f"Emby connection test - Status: {response.status_code}")
                if response.status_code != 200:
                    logger.warning(f"Emby connection error: {response.text[:200]}")
                else:
                    logger.info("Emby connection successful")

                return response.status_code == 200
        except Exception as e:
            logger.error(f"Emby connection error: {e}")
            return False

    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with Emby"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                # Emby authentication doesn't require API key for initial auth
                auth_data = {
                    "Username": username,
                    "Password": password,
                    "Pw": password  # Some Emby versions use Pw instead
                }

                # Add client identification headers
                headers = {
                    "X-Emby-Client": "TowerView",
                    "X-Emby-Device-Name": "TowerView",
                    "X-Emby-Device-Id": "towerview-auth",
                    "X-Emby-Client-Version": "1.0.0",
                    "Content-Type": "application/json"
                }

                # Try authentication without API key first (for user auth)
                response = await client.post(
                    f"{self.base_url}/Users/AuthenticateByName",
                    json=auth_data,
                    headers=headers,
                    timeout=10.0
                )

                if response.status_code != 200:
                    logger.warning(f"Emby auth failed: {response.status_code} - {response.text}")
                    return None

                data = response.json()
                user = data.get("User", {})

                return {
                    "user_id": user.get("Id"),
                    "username": user.get("Name"),
                    "email": user.get("Email"),
                    "token": data.get("AccessToken")
                }

        except Exception as e:
            logger.error(f"Emby authentication error: {str(e)}")
            return None

    async def list_active_sessions(self) -> List[Dict[str, Any]]:
        """Get active Emby sessions"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                base_url = self.base_url.rstrip('/')
                url = f"{base_url}/Sessions"
                logger.debug(f"Fetching Emby sessions from: {url}")

                response = await client.get(
                    url,
                    headers={"X-Emby-Token": self.admin_token or self.api_key},
                    timeout=10.0
                )

                logger.debug(f"Emby sessions response - Status: {response.status_code}")
                if response.status_code != 200:
                    logger.warning(f"Emby sessions error: {response.text}")
                    return []

                sessions_data = response.json()
                logger.info(f"Emby sessions raw data: {sessions_data[:500] if sessions_data else 'Empty'}")
                sessions = []

                for session in sessions_data:
                    # Skip monitoring tool sessions
                    if session.get("Client") == "TowerView":
                        logger.debug(f"Skipping TowerView monitoring session {session.get('Id')}")
                        continue

                    # Only process sessions with actual media playback
                    item = session.get("NowPlayingItem")
                    play_state = session.get("PlayState", {})

                    if not item:
                        logger.debug(f"Skipping Emby session {session.get('Id')} - no NowPlayingItem")
                        continue

                    logger.debug(f"Processing Emby session ID: {session.get('Id')} with media: {item.get('Name')} of type {item.get('Type')}")

                    # Get media info with fallbacks
                    media_title = item.get("Name") or "Unknown Media"
                    media_type = item.get("Type", "unknown").lower()  # Emby uses "Episode", "Movie", etc.

                    # Convert Emby media types to our standard format
                    if media_type == "movie":
                        media_type = "movie"
                    elif media_type == "episode":
                        media_type = "episode"
                    else:
                        media_type = "unknown"

                    # Get streaming details
                    media_streams = item.get("MediaStreams", [])
                    video_stream = next((s for s in media_streams if s.get("Type") == "Video"), {})
                    audio_stream = next((s for s in media_streams if s.get("Type") == "Audio"), {})

                    # Get transcoding info to check if we're transcoding
                    transcoding_info = session.get("TranscodingInfo", {})
                    play_method = play_state.get("PlayMethod", "").lower()
                    # Only consider it transcoding if PlayMethod is "transcode"
                    # DirectStream means the video is not being transcoded (though container might be remuxed)
                    is_transcoding = play_method == "transcode"

                    # Parse resolution and bitrate
                    def get_resolution():
                        # Get the actual playing resolution
                        height = None
                        width = None

                        # If we're transcoding, use the transcoded resolution
                        if is_transcoding and transcoding_info and transcoding_info.get("Height"):
                            height = transcoding_info.get("Height")
                            width = transcoding_info.get("Width")
                            original_height = video_stream.get("Height")
                            if original_height and original_height != height:
                                logger.info(f"Emby transcoding - Playing: {height}p (transcoded from {original_height}p)")
                        # Otherwise use the original resolution
                        elif video_stream.get("Height"):
                            height = video_stream.get("Height")
                            width = video_stream.get("Width")

                        # Debug logging for resolution detection
                        if "Together" in media_title:
                            logger.info(f"Together resolution - Playing Height: {height}, Width: {width}, Is Transcoding: {is_transcoding}")

                        if height:
                            # Consider anything >= 2000 pixels as 4K (covers cinema 4K at 2048p and UHD at 2160p)
                            if height >= 2000:
                                return "4K"
                            elif height >= 1080:
                                return "1080p"
                            elif height >= 720:
                                return "720p"
                            elif height >= 480:
                                return "480p"
                            else:
                                return f"{height}p"
                        return "Unknown"

                    # Get bitrate for bandwidth calculation
                    def get_session_bitrate():
                        # Try video stream bitrate first
                        if video_stream.get("BitRate"):
                            return video_stream.get("BitRate")
                        # Try item bitrate
                        if item.get("Bitrate"):
                            return item.get("Bitrate")
                        return 0

                    session_bitrate = get_session_bitrate()
                    # Convert bits per second to kbps
                    session_bandwidth_kbps = session_bitrate // 1000 if session_bitrate else 0

                    logger.debug(f"Emby session bandwidth calculation: {session_bitrate} -> {session_bandwidth_kbps} kbps")

                    # Determine if this is transcoding and if it's hardware accelerated
                    play_method = play_state.get("PlayMethod", "").lower()
                    is_transcoding = play_method == "transcode"
                    is_hw_transcode = False
                    hw_decode_title = None
                    hw_encode_title = None

                    # Check TranscodingInfo for hardware acceleration indicators
                    transcoding_info = session.get("TranscodingInfo", {})
                    if is_transcoding and transcoding_info:
                        video_codec = transcoding_info.get("VideoCodec", "").lower()

                        # Log what we're getting for debugging
                        logger.debug(f"Emby TranscodingInfo - VideoCodec: '{transcoding_info.get('VideoCodec')}', IsVideoDirect: {transcoding_info.get('IsVideoDirect')}, Full info: {transcoding_info}")

                        # Common hardware codec suffixes and indicators
                        hw_codecs = ["_vaapi", "_qsv", "_nvenc", "_videotoolbox", "_v4l2m2m", "_amf", "h264_vaapi", "h264_qsv", "h264_nvenc", "hevc_vaapi", "hevc_qsv", "hevc_nvenc"]

                        # Check if the video codec indicates hardware acceleration
                        for hw_suffix in hw_codecs:
                            if hw_suffix in video_codec:
                                is_hw_transcode = True
                                # Extract the hardware type
                                if "vaapi" in video_codec:
                                    hw_decode_title = "VA-API"
                                    hw_encode_title = "VA-API"
                                elif "qsv" in video_codec:
                                    hw_decode_title = "QuickSync"
                                    hw_encode_title = "QuickSync"
                                elif "nvenc" in video_codec or "nvdec" in video_codec:
                                    hw_decode_title = "NVDEC"
                                    hw_encode_title = "NVENC"
                                elif "videotoolbox" in video_codec:
                                    hw_decode_title = "VideoToolbox"
                                    hw_encode_title = "VideoToolbox"
                                elif "amf" in video_codec:
                                    hw_decode_title = "AMF"
                                    hw_encode_title = "AMF"
                                break

                        # Note: IsVideoDirect can be False even for DirectStream (container remuxing)
                        # We rely on PlayMethod to determine if video is being transcoded

                    # Get source resolution for reference
                    def get_source_resolution():
                        height = video_stream.get("Height")
                        width = video_stream.get("Width")

                        # Check if it's Dolby Vision for debug logging
                        video_range = video_stream.get("VideoRange", "")
                        is_dv = "dolby" in video_range.lower()

                        # Debug log for all Dolby Vision content
                        if is_dv:
                            logger.info(f"Emby - Dolby Vision content '{item.get('Name', 'Unknown')}' - Height: {height}, Width: {width}")

                        # Check both height and width for 4K detection
                        # 4K UHD is 3840x2160, but sometimes dimensions might be swapped or video might be portrait
                        if height and width:
                            # Standard 4K detection
                            if height >= 2000 or width >= 3800:
                                return "4K"
                            elif height >= 1080 or width >= 1920:
                                return "1080p"
                            elif height >= 720 or width >= 1280:
                                return "720p"
                            elif height >= 480:
                                return "480p"
                            else:
                                return f"{height}p"
                        elif height:
                            # Fallback to height only
                            if height >= 2000:
                                return "4K"
                            elif height >= 1080:
                                return "1080p"
                            elif height >= 720:
                                return "720p"
                            elif height >= 480:
                                return "480p"
                            else:
                                return f"{height}p"
                        return "Unknown"

                    # Build session data with stable identifier
                    emby_session_id = session.get("Id")
                    playing_resolution = get_resolution()
                    source_resolution = get_source_resolution()

                    session_data = {
                        "session_id": emby_session_id,
                        "user_id": session.get("UserId"),
                        "username": session.get("UserName"),
                        "media_id": item.get("Id"),
                        "media_title": media_title,
                        "media_type": media_type,
                        "state": "playing" if not play_state.get("IsPaused", True) else "paused",
                        "progress": play_state.get("PositionTicks", 0) // 10000000,  # Convert to seconds
                        "progress_ms": play_state.get("PositionTicks", 0) // 10000,  # Convert to milliseconds
                        "duration_ms": item.get("RunTimeTicks", 0) // 10000 if item.get("RunTimeTicks") else 0,
                        "progress_seconds": play_state.get("PositionTicks", 0) // 10000000,
                        "duration_seconds": item.get("RunTimeTicks", 0) // 10000000 if item.get("RunTimeTicks") else 0,
                        "device": session.get("DeviceName"),
                        "platform": session.get("Client"),

                        # Additional media details
                        "title": media_title,
                        "full_title": media_title,
                        "year": str(item.get("ProductionYear")) if item.get("ProductionYear") else None,
                        "summary": item.get("Overview"),
                        "runtime": item.get("RunTimeTicks", 0) // 10000000 if item.get("RunTimeTicks") else 0,
                        "library_section": "Unknown Library",  # Emby doesn't provide this in session data

                        # Streaming details
                        "video_decision": "transcode" if is_transcoding else play_method,
                        "original_resolution": source_resolution,  # Original/source resolution
                        "stream_resolution": playing_resolution if is_transcoding else None,  # Transcoded resolution (only when transcoding)
                        "original_bitrate": str(video_stream.get("BitRate", 0) // 1000) if video_stream.get("BitRate") else "0",
                        "stream_bitrate": str(session_bandwidth_kbps),
                        "video_codec": transcoding_info.get("VideoCodec", video_stream.get("Codec", "Unknown")) if transcoding_info else video_stream.get("Codec", "Unknown"),
                        "audio_codec": transcoding_info.get("AudioCodec", audio_stream.get("Codec", "Unknown")) if transcoding_info else audio_stream.get("Codec", "Unknown"),
                        "container": transcoding_info.get("Container", item.get("Container", "Unknown")) if transcoding_info else item.get("Container", "Unknown"),
                        "session_bandwidth": str(session_bandwidth_kbps),

                        # Hardware transcoding info (for compatibility with Plex fields)
                        "transcode_hw_requested": is_hw_transcode,
                        "transcode_hw_decode": is_hw_transcode,
                        "transcode_hw_encode": is_hw_transcode,
                        "transcode_hw_full_pipeline": is_hw_transcode,
                        "transcode_hw_decode_title": hw_decode_title,
                        "transcode_hw_encode_title": hw_encode_title,

                        # HDR detection
                        "is_hdr": video_stream.get("ColorTransfer") == "smpte2084" or video_stream.get("VideoRange") in ["HDR", "HDR10"],
                        "is_dolby_vision": video_stream.get("VideoRange") == "DolbyVision" or video_stream.get("ExtendedVideoType") == "DolbyVision",

                        # Quality profile for UI display (with HDR) - use playing resolution
                        "quality_profile": self._build_quality_profile(playing_resolution, video_stream),

                        # Product info
                        "product": session.get("Client", "Unknown"),

                        # For TV episodes, get series info
                        "grandparent_title": None,
                        "parent_title": None,
                    }

                    # Calculate progress percentage
                    if session_data["duration_ms"] > 0:
                        session_data["progress_percent"] = (session_data["progress_ms"] / session_data["duration_ms"]) * 100
                    else:
                        session_data["progress_percent"] = 0

                    # If this is an episode, get series information
                    if media_type == "episode":
                        session_data["grandparent_title"] = item.get("SeriesName", "Unknown Series")
                        session_data["parent_title"] = f"Season {item.get('ParentIndexNumber', '?')}"
                        session_data["season_number"] = item.get("ParentIndexNumber")
                        session_data["episode_number"] = item.get("IndexNumber")
                        # Build full title
                        title_parts = []
                        if session_data["grandparent_title"]:
                            title_parts.append(session_data["grandparent_title"])
                        if session_data["parent_title"]:
                            title_parts.append(session_data["parent_title"])
                        if session_data["title"]:
                            title_parts.append(session_data["title"])
                        session_data["full_title"] = " - ".join(title_parts)

                    sessions.append(session_data)
                    logger.info(f"Added Emby session: {media_title} ({media_type})")

                # Sort sessions by session_id for consistent ordering
                sessions.sort(key=lambda x: x.get('session_id', ''))
                logger.info(f"Returning {len(sessions)} Emby sessions in sorted order")
                return sessions

        except Exception:
            return []

    def _build_quality_profile(self, resolution: str, video_stream: Dict) -> str:
        """Build a quality profile string including HDR information"""
        parts = []

        # Add resolution
        if resolution and resolution != "Unknown":
            parts.append(resolution)

        # Check for HDR/Dolby Vision
        if video_stream.get("VideoRange") == "DolbyVision" or video_stream.get("ExtendedVideoType") == "DolbyVision":
            parts.append("DoVi")
        elif video_stream.get("ColorTransfer") == "smpte2084" or video_stream.get("VideoRange") in ["HDR", "HDR10"]:
            parts.append("HDR")

        # Add video codec
        codec = video_stream.get("Codec", "").upper()
        if codec:
            parts.append(codec)

        return " ".join(parts) if parts else "Unknown"

    async def get_version_info(self) -> Dict[str, Any]:
        """Get Emby server version information"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                # Get server info
                response = await client.get(
                    f"{self.base_url}/System/Info",
                    headers={"X-Emby-Token": self.api_key},
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()

                    # Get latest version from Docker Hub
                    latest_version = await self._get_latest_version(client)

                    current_version = data.get("Version", "Unknown")

                    return {
                        "current_version": current_version,
                        "server_name": data.get("ServerName", "Emby Server"),
                        "operating_system": data.get("OperatingSystem", "Unknown"),
                        "architecture": data.get("SystemArchitecture", "Unknown"),
                        "product": "Emby Server",
                        "latest_version": latest_version,
                        "update_available": self._compare_versions(current_version, latest_version) if latest_version else False,
                        "has_update_available": data.get("HasUpdateAvailable", False)  # Emby's own update check
                    }

                return {}

        except Exception as e:
            logger.error(f"Error getting Emby version info: {e}")
            return {}

    async def _get_latest_version(self, client: httpx.AsyncClient) -> Optional[str]:
        """Get the latest Emby version from Docker Hub"""
        try:
            response = await client.get(
                "https://hub.docker.com/v2/repositories/emby/embyserver/tags?page_size=20",
                timeout=10.0
            )

            if response.status_code == 200:
                data = response.json()
                tags = data.get("results", [])

                # Filter for stable version tags (format: X.Y.Z.X)
                import re
                version_pattern = re.compile(r'^(\d+)\.(\d+)\.(\d+)\.(\d+)$')

                versions = []
                for tag in tags:
                    tag_name = tag.get("name", "")
                    match = version_pattern.match(tag_name)
                    if match:
                        versions.append(tag_name)

                # Sort versions and return the latest
                if versions:
                    versions.sort(key=lambda v: [int(x) for x in v.split('.')], reverse=True)
                    return versions[0]

            return None

        except Exception:
            # Docker Hub API error
            return None

    def _compare_versions(self, current: str, latest: str) -> bool:
        """Compare version strings to determine if update is available"""
        try:
            # Parse version strings (e.g., "4.7.14.0")
            current_parts = current.split(".")
            latest_parts = latest.split(".")

            for i in range(min(len(current_parts), len(latest_parts))):
                curr_num = int(current_parts[i])
                latest_num = int(latest_parts[i])

                if latest_num > curr_num:
                    return True
                elif latest_num < curr_num:
                    return False

            return False
        except (ValueError, IndexError, AttributeError):
            return False

    async def list_users(self) -> List[Dict[str, Any]]:
        """Get all Emby users"""
        try:
            if not self.api_key:
                logger.warning("No API key available for listing Emby users")
                return []

            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    f"{self.base_url}/Users",
                    headers={"X-Emby-Token": self.api_key},
                    timeout=10.0
                )

                if response.status_code != 200:
                    return []

                users_data = response.json()
                users = []

                for user in users_data:
                    # Get last activity date and format it
                    last_activity = user.get("LastActivityDate")
                    if last_activity:
                        # Emby returns ISO format datetime, convert to a readable format
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
                            last_activity = dt.isoformat()
                        except:
                            pass

                    user_data = {
                        "user_id": user.get("Id"),
                        "username": user.get("Name"),
                        "email": user.get("EmailAddress"),
                        "thumb": user.get("PrimaryImageTag"),
                        "admin": user.get("Policy", {}).get("IsAdministrator", False),
                        "disabled": user.get("Policy", {}).get("IsDisabled", False),
                        "hidden": user.get("Policy", {}).get("IsHidden", False),
                        "last_activity": last_activity,
                        "last_login": user.get("LastLoginDate"),
                    }
                    users.append(user_data)

                return users

        except Exception as e:
            logger.error(f"Error fetching Emby users: {e}")
            return []

    async def get_user(self, provider_user_id: str) -> Optional[Dict[str, Any]]:
        """Get Emby user information"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    f"{self.base_url}/Users/{provider_user_id}",
                    headers={"X-Emby-Token": self.api_key},
                    timeout=10.0
                )

                if response.status_code != 200:
                    return None

                user = response.json()

                return {
                    "user_id": user.get("Id"),
                    "username": user.get("Name"),
                    "email": user.get("Email"),
                    "last_activity": user.get("LastActivityDate"),
                    "last_login": user.get("LastLoginDate")
                }

        except Exception:
            return None

    async def terminate_session(self, provider_session_id: str) -> bool:
        """Terminate an Emby session"""
        try:
            logger.info(f"Attempting to terminate Emby session: {provider_session_id}")
            async with httpx.AsyncClient(verify=False) as client:
                base_url = self.base_url.rstrip('/')
                headers = {
                    "X-Emby-Token": self.admin_token or self.api_key,
                    "Content-Type": "application/json"
                }

                # First, send a message to the user
                message_url = f"{base_url}/Sessions/{provider_session_id}/Message"
                message_data = {
                    "Header": "Playback Stopped",
                    "Text": "Your playback has been stopped by an administrator.",
                    "TimeoutMs": 5000
                }

                logger.debug(f"Emby - Sending message to session: {provider_session_id}")
                try:
                    message_response = await client.post(
                        message_url,
                        json=message_data,
                        headers=headers,
                        timeout=10.0
                    )
                    logger.debug(f"Message response - Status: {message_response.status_code}")
                except Exception as msg_error:
                    logger.debug(f"Message send error (non-critical): {msg_error}")

                # Method 1: Try the Playing/Stop endpoint (similar to Jellyfin)
                stop_url = f"{base_url}/Sessions/{provider_session_id}/Playing/Stop"
                logger.debug(f"Emby termination - Method 1: Sending stop to {stop_url}")

                try:
                    stop_response = await client.post(
                        stop_url,
                        headers=headers,
                        timeout=10.0
                    )
                    logger.debug(f"Stop response - Status: {stop_response.status_code}")

                    if stop_response.status_code in [200, 204, 404]:
                        logger.debug("Method 1 successful")
                        return True
                except Exception as e:
                    logger.debug(f"Method 1 failed: {e}")

                # Method 2: Try sending a general Stop command
                command_url = f"{base_url}/Sessions/{provider_session_id}/Command"
                command_data = {"Name": "Stop"}

                logger.debug(f"Emby termination - Method 2: Sending command to {command_url}")
                command_response = await client.post(
                    command_url,
                    json=command_data,
                    headers=headers,
                    timeout=10.0
                )

                logger.debug(f"Command response - Status: {command_response.status_code}, Text: {command_response.text[:200] if command_response.text else 'Empty'}")

                if command_response.status_code in [200, 204, 404]:
                    logger.debug("Method 2 successful")
                    return True

                # Method 3: Try the System/Sessions/Logout endpoint
                logout_url = f"{base_url}/System/Sessions/Logout"
                params = {"Id": provider_session_id}

                logger.debug(f"Emby termination - Method 3: Logout via {logout_url} with session ID {provider_session_id}")
                logout_response = await client.post(
                    logout_url,
                    params=params,
                    headers=headers,
                    timeout=10.0
                )

                logger.debug(f"Logout response - Status: {logout_response.status_code}")
                success = logout_response.status_code in [200, 204, 404]

                logger.info(f"Emby termination final result: {success}")
                return success

        except Exception as e:
            logger.error(f"Error terminating Emby session {provider_session_id}: {e}")
            return False

    async def modify_user(self, provider_user_id: str, changes: Dict[str, Any]) -> bool:
        """Modify Emby user settings"""
        try:
            # First get the current user data
            user_data = await self.get_user(provider_user_id)
            if not user_data:
                return False

            # Update with changes
            user_data.update(changes)

            async with httpx.AsyncClient(verify=False) as client:
                response = await client.post(
                    f"{self.base_url}/Users/{provider_user_id}",
                    json=user_data,
                    headers={"X-Emby-Token": self.admin_token or self.api_key},
                    timeout=10.0
                )
                return response.status_code in [200, 204]

        except Exception:
            return False

    async def list_libraries(self) -> List[Dict[str, Any]]:
        """Get Emby libraries"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                # First try the VirtualFolders endpoint
                response = await client.get(
                    f"{self.base_url}/Library/VirtualFolders",
                    headers={"X-Emby-Token": self.admin_token or self.api_key},
                    timeout=10.0
                )

                if response.status_code == 200:
                    libraries_data = response.json()
                    libraries = []

                    for library in libraries_data:
                        libraries.append({
                            "id": library.get("ItemId", library.get("Id")),
                            "title": library.get("Name"),
                            "type": library.get("CollectionType")
                        })

                    logger.info(f"Found {len(libraries)} Emby libraries via VirtualFolders")
                    return libraries

                # If VirtualFolders fails, try the user views endpoint
                logger.warning(f"VirtualFolders failed with {response.status_code}, trying user views")

                # Get current user info to get user ID
                user_response = await client.get(
                    f"{self.base_url}/Users/Me",
                    headers={"X-Emby-Token": self.admin_token or self.api_key},
                    timeout=10.0
                )

                if user_response.status_code == 200:
                    user_data = user_response.json()
                    user_id = user_data.get("Id")

                    # Get views for this user
                    views_response = await client.get(
                        f"{self.base_url}/Users/{user_id}/Views",
                        headers={"X-Emby-Token": self.admin_token or self.api_key},
                        timeout=10.0
                    )

                    if views_response.status_code == 200:
                        views_data = views_response.json()
                        libraries = []

                        for item in views_data.get("Items", []):
                            libraries.append({
                                "id": item.get("Id"),
                                "title": item.get("Name"),
                                "type": item.get("CollectionType", item.get("Type"))
                            })

                        logger.info(f"Found {len(libraries)} Emby libraries via user views")
                        return libraries

                logger.error(f"Failed to fetch Emby libraries")
                return []

        except Exception as e:
            logger.error(f"Error fetching Emby libraries: {e}")
            return []

    async def change_user_password(self, provider_user_id: str, new_password: str, current_password: Optional[str] = None) -> bool:
        """Change Emby user password"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                # Prepare password data
                password_data = {
                    "NewPw": new_password
                }

                # If current password provided, add it (for non-admin changes)
                if current_password:
                    password_data["CurrentPw"] = current_password
                else:
                    # Admin changing another user's password
                    password_data["ResetPassword"] = True

                response = await client.post(
                    f"{self.base_url}/Users/{provider_user_id}/Password",
                    json=password_data,
                    headers={"X-Emby-Token": self.admin_token or self.api_key},
                    timeout=10.0
                )

                return response.status_code in [200, 204]

        except Exception as e:
            logger.error(f"Failed to change Emby user password: {e}")
            return False

    async def get_user_library_access(self, provider_user_id: str) -> Dict[str, Any]:
        """Get user's current library access"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                # Get full user object which contains the policy
                user_url = f"{self.base_url}/Users/{provider_user_id}"
                logger.info(f"Emby fetching user from: {user_url}")

                response = await client.get(
                    user_url,
                    headers={"X-Emby-Token": self.admin_token or self.api_key},
                    timeout=10.0
                )

                logger.info(f"Emby get_user_library_access status: {response.status_code}")

                if response.status_code != 200:
                    logger.error(f"Failed to get Emby user for {provider_user_id}: status={response.status_code}, response={response.text}")
                    return {"library_ids": [], "all_libraries": False}

                user = response.json()
                policy = user.get("Policy", {})

                logger.info(f"Emby user {provider_user_id} has Policy: {bool(policy)}")
                if policy:
                    logger.info(f"Emby EnableAllFolders: {policy.get('EnableAllFolders')}")
                    logger.info(f"Emby EnabledFolders: {policy.get('EnabledFolders')}")

                # Check if user has access to all libraries
                all_libraries = policy.get("EnableAllFolders", False)

                # Get enabled folder IDs
                enabled_folders = policy.get("EnabledFolders", [])

                result = {
                    "library_ids": enabled_folders,
                    "all_libraries": all_libraries
                }
                logger.info(f"Emby returning library access: {result}")
                return result
        except Exception as e:
            logger.error(f"Failed to get Emby user library access: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"library_ids": [], "all_libraries": False}

    async def set_library_access(self, provider_user_id: str, library_ids: List[str]) -> bool:
        """Set library access for Emby user"""
        try:
            # Get current user policy
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    f"{self.base_url}/Users/{provider_user_id}/Policy",
                    headers={"X-Emby-Token": self.admin_token or self.api_key},
                    timeout=10.0
                )

                if response.status_code != 200:
                    return False

                policy = response.json()
                policy["EnabledFolders"] = library_ids

                # Update the policy
                response = await client.post(
                    f"{self.base_url}/Users/{provider_user_id}/Policy",
                    json=policy,
                    headers={"X-Emby-Token": self.admin_token or self.api_key},
                    timeout=10.0
                )

                return response.status_code in [200, 204]

        except Exception:
            return False

    async def set_user_library_access(self, provider_user_id: str, library_ids: List[str], all_libraries: bool = False) -> bool:
        """Set library access for Emby user with all_libraries support"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                # Get current user to access the full Policy object
                user_url = f"{self.base_url}/Users/{provider_user_id}"
                response = await client.get(
                    user_url,
                    headers={"X-Emby-Token": self.admin_token or self.api_key},
                    timeout=10.0
                )

                if response.status_code != 200:
                    logger.error(f"Failed to get Emby user {provider_user_id}: {response.status_code}")
                    return False

                user = response.json()
                policy = user.get("Policy", {})

                # Update library access settings
                policy["EnableAllFolders"] = all_libraries
                if not all_libraries:
                    policy["EnabledFolders"] = library_ids
                else:
                    # When all libraries are enabled, clear the specific list
                    policy["EnabledFolders"] = []

                # Update the policy
                policy_url = f"{self.base_url}/Users/{provider_user_id}/Policy"
                response = await client.post(
                    policy_url,
                    json=policy,
                    headers={"X-Emby-Token": self.admin_token or self.api_key},
                    timeout=10.0
                )

                if response.status_code in [200, 204]:
                    logger.info(f"Successfully updated library access for Emby user {provider_user_id}")
                    return True
                else:
                    logger.error(f"Failed to update Emby user policy: {response.status_code} - {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Exception setting Emby library access: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    async def get_media_info(self, provider_media_id: str) -> Optional[Dict[str, Any]]:
        """Get Emby media information"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    f"{self.base_url}/Items/{provider_media_id}",
                    headers={"X-Emby-Token": self.admin_token or self.api_key},
                    timeout=10.0
                )

                if response.status_code != 200:
                    return None

                item = response.json()

                return {
                    "id": item.get("Id"),
                    "title": item.get("Name"),
                    "type": item.get("MediaType"),
                    "runtime": item.get("RunTimeTicks", 0) // 10000000,  # Convert to seconds
                    "year": item.get("ProductionYear"),
                    "summary": item.get("Overview"),
                    "rating": item.get("CommunityRating"),
                    "genres": item.get("Genres", [])
                }

        except Exception:
            return None