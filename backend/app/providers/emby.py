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
        print(f"Emby provider initialized - api_key: {'Yes' if self.api_key else 'No'}, admin_token: {'Yes' if self.admin_token else 'No'}")
        print(f"Available credential keys: {list(credentials.keys())}")

    async def connect(self) -> bool:
        """Test connection to Emby server"""
        try:
            print(f"Testing Emby connection to: {self.base_url}")
            if self.api_key:
                print(f"Using API key: {self.api_key[:10]}...{self.api_key[-10:] if len(self.api_key) > 20 else 'N/A'}")
            else:
                print("No API key provided")
                return False

            async with httpx.AsyncClient() as client:
                # Ensure base_url doesn't end with slash to avoid double slashes
                base_url = self.base_url.rstrip('/')
                url = f"{base_url}/System/Info"
                headers = {"X-Emby-Token": self.api_key} if self.api_key else {}

                print(f"Emby connection URL: {url}")

                response = await client.get(
                    url,
                    headers=headers,
                    timeout=10.0
                )

                print(f"Emby connection test - Status: {response.status_code}")
                if response.status_code != 200:
                    print(f"Emby connection error: {response.text[:200]}")
                else:
                    print("Emby connection successful")

                return response.status_code == 200
        except Exception as e:
            print(f"Emby connection error: {e}")
            return False

    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with Emby"""
        try:
            async with httpx.AsyncClient() as client:
                auth_data = {
                    "Username": username,
                    "Password": password,
                    "Pw": password  # Some Emby versions use Pw instead
                }

                response = await client.post(
                    f"{self.base_url}/Users/AuthenticateByName",
                    json=auth_data,
                    headers={"X-Emby-Token": self.api_key},
                    timeout=10.0
                )

                if response.status_code != 200:
                    return None

                data = response.json()
                user = data.get("User", {})

                return {
                    "user_id": user.get("Id"),
                    "username": user.get("Name"),
                    "email": user.get("Email"),
                    "token": data.get("AccessToken")
                }

        except Exception:
            return None

    async def list_active_sessions(self) -> List[Dict[str, Any]]:
        """Get active Emby sessions"""
        try:
            async with httpx.AsyncClient() as client:
                base_url = self.base_url.rstrip('/')
                url = f"{base_url}/Sessions"
                print(f"Fetching Emby sessions from: {url}")

                response = await client.get(
                    url,
                    headers={"X-Emby-Token": self.admin_token or self.api_key},
                    timeout=10.0
                )

                print(f"Emby sessions response - Status: {response.status_code}")
                if response.status_code != 200:
                    print(f"Emby sessions error: {response.text}")
                    return []

                sessions_data = response.json()
                print(f"Emby sessions raw data: {sessions_data[:500] if sessions_data else 'Empty'}")
                sessions = []

                for session in sessions_data:
                    # Skip monitoring tool sessions
                    if session.get("Client") == "TowerView":
                        print(f"Skipping TowerView monitoring session {session.get('Id')}")
                        continue

                    # Only process sessions with actual media playback
                    item = session.get("NowPlayingItem")
                    play_state = session.get("PlayState", {})

                    if not item:
                        print(f"Skipping Emby session {session.get('Id')} - no NowPlayingItem")
                        continue

                    print(f"Processing Emby session ID: {session.get('Id')} with media: {item.get('Name')} of type {item.get('Type')}")

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

                    # Parse resolution and bitrate
                    def get_resolution():
                        if video_stream.get("Height"):
                            height = video_stream.get("Height")
                            if height >= 2160:
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

                    print(f"Emby session bandwidth calculation: {session_bitrate} -> {session_bandwidth_kbps} kbps")

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
                        print(f"Emby TranscodingInfo - VideoCodec: '{transcoding_info.get('VideoCodec')}', IsVideoDirect: {transcoding_info.get('IsVideoDirect')}, Full info: {transcoding_info}")

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

                        # Also check if IsVideoDirect is false (indicates transcoding)
                        if transcoding_info.get("IsVideoDirect") == False:
                            is_transcoding = True

                    # Build session data with stable identifier
                    emby_session_id = session.get("Id")
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
                        "original_resolution": get_resolution(),
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

                        # Quality profile for UI display
                        "quality_profile": get_resolution(),

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
                    print(f"Added Emby session: {media_title} ({media_type})")

                # Sort sessions by session_id for consistent ordering
                sessions.sort(key=lambda x: x.get('session_id', ''))
                print(f"Returning {len(sessions)} Emby sessions in sorted order")
                return sessions

        except Exception:
            return []

    async def get_version_info(self) -> Dict[str, Any]:
        """Get Emby server version information"""
        try:
            async with httpx.AsyncClient() as client:
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
        except:
            return False

    async def list_users(self) -> List[Dict[str, Any]]:
        """Get all Emby users"""
        try:
            if not self.api_key:
                print("No API key available for listing Emby users")
                return []

            async with httpx.AsyncClient() as client:
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
                    user_data = {
                        "user_id": user.get("Id"),
                        "username": user.get("Name"),
                        "email": user.get("EmailAddress"),
                        "thumb": user.get("PrimaryImageTag"),
                        "admin": user.get("Policy", {}).get("IsAdministrator", False),
                        "disabled": user.get("Policy", {}).get("IsDisabled", False),
                        "hidden": user.get("Policy", {}).get("IsHidden", False),
                    }
                    users.append(user_data)

                return users

        except Exception as e:
            print(f"Error fetching Emby users: {e}")
            return []

    async def get_user(self, provider_user_id: str) -> Optional[Dict[str, Any]]:
        """Get Emby user information"""
        try:
            async with httpx.AsyncClient() as client:
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
            print(f"Attempting to terminate Emby session: {provider_session_id}")
            async with httpx.AsyncClient() as client:
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

                print(f"Emby - Sending message to session: {provider_session_id}")
                try:
                    message_response = await client.post(
                        message_url,
                        json=message_data,
                        headers=headers,
                        timeout=10.0
                    )
                    print(f"Message response - Status: {message_response.status_code}")
                except Exception as msg_error:
                    print(f"Message send error (non-critical): {msg_error}")

                # Method 1: Try the Playing/Stop endpoint (similar to Jellyfin)
                stop_url = f"{base_url}/Sessions/{provider_session_id}/Playing/Stop"
                print(f"Emby termination - Method 1: Sending stop to {stop_url}")

                try:
                    stop_response = await client.post(
                        stop_url,
                        headers=headers,
                        timeout=10.0
                    )
                    print(f"Stop response - Status: {stop_response.status_code}")

                    if stop_response.status_code in [200, 204, 404]:
                        print("Method 1 successful")
                        return True
                except Exception as e:
                    print(f"Method 1 failed: {e}")

                # Method 2: Try sending a general Stop command
                command_url = f"{base_url}/Sessions/{provider_session_id}/Command"
                command_data = {"Name": "Stop"}

                print(f"Emby termination - Method 2: Sending command to {command_url}")
                command_response = await client.post(
                    command_url,
                    json=command_data,
                    headers=headers,
                    timeout=10.0
                )

                print(f"Command response - Status: {command_response.status_code}, Text: {command_response.text[:200] if command_response.text else 'Empty'}")

                if command_response.status_code in [200, 204, 404]:
                    print("Method 2 successful")
                    return True

                # Method 3: Try the System/Sessions/Logout endpoint
                logout_url = f"{base_url}/System/Sessions/Logout"
                params = {"Id": provider_session_id}

                print(f"Emby termination - Method 3: Logout via {logout_url} with session ID {provider_session_id}")
                logout_response = await client.post(
                    logout_url,
                    params=params,
                    headers=headers,
                    timeout=10.0
                )

                print(f"Logout response - Status: {logout_response.status_code}")
                success = logout_response.status_code in [200, 204, 404]

                print(f"Emby termination final result: {success}")
                return success

        except Exception as e:
            print(f"Error terminating Emby session {provider_session_id}: {e}")
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

            async with httpx.AsyncClient() as client:
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
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/Library/VirtualFolders",
                    headers={"X-Emby-Token": self.admin_token or self.api_key},
                    timeout=10.0
                )

                if response.status_code != 200:
                    return []

                libraries_data = response.json()
                libraries = []

                for library in libraries_data:
                    libraries.append({
                        "id": library.get("ItemId"),
                        "title": library.get("Name"),
                        "type": library.get("CollectionType")
                    })

                return libraries

        except Exception:
            return []

    async def set_library_access(self, provider_user_id: str, library_ids: List[str]) -> bool:
        """Set library access for Emby user"""
        try:
            # Get current user policy
            async with httpx.AsyncClient() as client:
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

    async def get_media_info(self, provider_media_id: str) -> Optional[Dict[str, Any]]:
        """Get Emby media information"""
        try:
            async with httpx.AsyncClient() as client:
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