import httpx
import logging
from typing import List, Dict, Any, Optional
from .base import BaseProvider

logger = logging.getLogger(__name__)


class JellyfinProvider(BaseProvider):
    def __init__(self, server, credentials):
        super().__init__(server, credentials)
        # Support multiple credential field names
        self.api_key = credentials.get("api_key") or credentials.get("api_token") or credentials.get("token")
        self.admin_token = credentials.get("admin_token") or credentials.get("api_token") or credentials.get("token")
        logger.debug(f"Jellyfin provider initialized with credentials: {list(credentials.keys())}")

    async def connect(self) -> bool:
        """Test connection to Jellyfin server"""
        try:
            logger.debug(f"Testing Jellyfin connection to: {self.base_url}")
            logger.debug(f"Using API key: {self.api_key[:10]}..." if self.api_key else "No API key provided")

            async with httpx.AsyncClient(verify=False) as client:
                # Ensure base_url doesn't end with slash to avoid double slashes
                base_url = self.base_url.rstrip('/')
                url = f"{base_url}/System/Info"
                headers = {"Authorization": f"MediaBrowser Token={self.api_key}"}

                response = await client.get(
                    url,
                    headers=headers,
                    timeout=10.0
                )

                logger.debug(f"Jellyfin connection test - URL: {url}")
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response text: {response.text[:200]}...")

                return response.status_code == 200
        except Exception as e:
            logger.error(f"Jellyfin connection error: {e}")
            return False

    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with Jellyfin"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                base_url = self.base_url.rstrip('/')

                # Try the standard Jellyfin/Emby authentication format
                headers = {
                    "X-Emby-Authorization": f'MediaBrowser Client="TowerView", Device="TowerView", DeviceId="towerview-auth", Version="1.0.0"',
                    "Content-Type": "application/json"
                }

                # Jellyfin expects Username and Pw fields
                auth_data = {
                    "Username": username,
                    "Pw": password  # Note: Jellyfin uses "Pw" not "Password"
                }

                response = await client.post(
                    f"{base_url}/Users/AuthenticateByName",
                    json=auth_data,
                    headers=headers,
                    timeout=10.0
                )

                if response.status_code != 200:
                    logger.warning(f"Jellyfin auth failed: {response.status_code} - {response.text}")
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
            logger.error(f"Jellyfin authentication error: {str(e)}")
            return None

    async def list_active_sessions(self) -> List[Dict[str, Any]]:
        """Get active Jellyfin sessions"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                base_url = self.base_url.rstrip('/')
                url = f"{base_url}/Sessions"
                logger.debug(f"Fetching Jellyfin sessions from: {url}")

                response = await client.get(
                    url,
                    headers={"Authorization": f"MediaBrowser Token={self.admin_token or self.api_key}"},
                    timeout=10.0
                )

                logger.debug(f"Jellyfin sessions response - Status: {response.status_code}")
                if response.status_code != 200:
                    logger.warning(f"Jellyfin sessions error: {response.text}")
                else:
                    logger.debug(f"Jellyfin sessions data: {response.text[:800]}...")
                    # Let's examine the full session structure
                    session_json = response.json()
                    if session_json:
                        logger.debug(f"First session structure keys: {list(session_json[0].keys())}")
                        if 'NowPlayingItem' in session_json[0]:
                            logger.debug(f"NowPlayingItem keys: {list(session_json[0]['NowPlayingItem'].keys())}")
                        else:
                            logger.debug("No NowPlayingItem found - this is why media shows as unknown")

                if response.status_code != 200:
                    return []

                sessions_data = response.json()
                sessions = []

                for session in sessions_data:
                    # Only process sessions with actual media playback
                    item = session.get("NowPlayingItem")
                    play_state = session.get("PlayState", {})

                    # Skip sessions without NowPlayingItem - these are just idle connections
                    if not item:
                        logger.debug(f"Skipping session {session.get('Id')} - no NowPlayingItem")
                        continue

                    logger.debug(f"Processing session with media: {item.get('Name')} of type {item.get('Type')}")

                    # Get media info with fallbacks
                    media_title = item.get("Name") or item.get("OriginalTitle") or "Unknown Media"
                    media_type = item.get("Type", "unknown").lower()  # Jellyfin uses "Movie", "Episode", etc.

                    # Convert Jellyfin media types to our standard format
                    if media_type == "movie":
                        media_type = "movie"
                    elif media_type == "episode":
                        media_type = "episode"
                    else:
                        media_type = item.get("MediaType", "unknown").lower()

                    # Get transcoding/streaming info
                    transcoding_info = session.get("TranscodingInfo", {})
                    media_streams = item.get("MediaStreams", [])

                    # Find video and audio streams
                    video_stream = next((s for s in media_streams if s.get("Type") == "Video"), {})
                    audio_stream = next((s for s in media_streams if s.get("Type") == "Audio"), {})

                    # Parse resolution from DisplayTitle (extract just the resolution part)
                    def extract_resolution(display_title=None, height=None):
                        if display_title:
                            # Look for common resolution patterns like 1080p, 720p, 4K, etc.
                            import re

                            # Check for 4K variations
                            if re.search(r'4K|2160p', display_title, re.IGNORECASE):
                                return "4K"

                            # Check for standard resolutions
                            resolution_match = re.search(r'(\d{3,4}p)', display_title)
                            if resolution_match:
                                return resolution_match.group(1)

                        # Fallback to height if available
                        if height:
                            if height >= 2000:  # Include cinema 4K
                                return "4K"
                            elif height >= 1080:
                                return "1080p"
                            elif height >= 720:
                                return "720p"
                            elif height >= 480:
                                return "480p"
                            else:
                                return f"{height}p"

                        # Final fallback to video stream height
                        if video_stream.get("Height"):
                            height = video_stream.get("Height")
                            if height >= 2000:  # Include cinema 4K
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

                    # Parse bitrate from various sources
                    def get_session_bitrate():
                        # Try transcoding info first
                        if transcoding_info.get("Bitrate"):
                            return transcoding_info.get("Bitrate")

                        # Try video stream bitrate
                        if video_stream.get("BitRate"):
                            return video_stream.get("BitRate")

                        # Try original bitrate from item
                        if item.get("Bitrate"):
                            return item.get("Bitrate")

                        return 0

                    # Calculate bandwidth (convert bits to kbps)
                    session_bitrate = get_session_bitrate()
                    # Jellyfin bitrates are often in bits per second, so convert to kbps
                    session_bandwidth_kbps = session_bitrate // 1000 if session_bitrate else 0

                    # If the value seems too high (>100Mbps = 100,000 kbps), it might be in different units
                    if session_bandwidth_kbps > 100000:
                        # Might be in different units, divide further
                        session_bandwidth_kbps = session_bandwidth_kbps // 1000

                    logger.debug(f"Session bandwidth calculation: {session_bitrate} -> {session_bandwidth_kbps} kbps")

                    # Determine if this is transcoding and if it's hardware accelerated
                    play_method = play_state.get("PlayMethod", "").lower()
                    is_transcoding = play_method == "transcode"
                    is_hw_transcode = False
                    hw_decode_title = None
                    hw_encode_title = None

                    # Check TranscodingInfo for hardware acceleration indicators
                    if is_transcoding and transcoding_info:
                        video_codec = transcoding_info.get("VideoCodec", "").lower()
                        audio_codec = transcoding_info.get("AudioCodec", "").lower()

                        # Log what we're getting for debugging
                        logger.debug(f"Jellyfin TranscodingInfo - VideoCodec: '{transcoding_info.get('VideoCodec')}', IsVideoDirect: {transcoding_info.get('IsVideoDirect')}, Full info: {transcoding_info}")

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

                    # Build session data
                    session_data = {
                        "session_id": session.get("Id"),
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
                        "device": session.get("DeviceName") or session.get("Client"),
                        "platform": session.get("Client") or session.get("ApplicationVersion"),

                        # Additional media details
                        "title": media_title,
                        "full_title": media_title,
                        "year": str(item.get("ProductionYear")) if item.get("ProductionYear") else None,
                        "summary": item.get("Overview"),
                        "content_rating": item.get("OfficialRating"),
                        "runtime": item.get("RunTimeTicks", 0) // 10000000 if item.get("RunTimeTicks") else 0,
                        "library_section": item.get("LibraryName", "Unknown Library"),

                        # Streaming details
                        "video_decision": "transcode" if is_transcoding else play_method,
                        "original_resolution": extract_resolution(video_stream.get("DisplayTitle"), video_stream.get("Height")),  # Source resolution
                        "stream_resolution": extract_resolution(None, transcoding_info.get("Height")) if is_transcoding and transcoding_info.get("Height") else None,  # Transcoded resolution
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

                        # HDR detection (Jellyfin uses similar format to Emby)
                        "is_hdr": video_stream.get("ColorTransfer") == "smpte2084" or video_stream.get("VideoRange") in ["HDR", "HDR10"],
                        "is_dolby_vision": video_stream.get("VideoRange") == "DolbyVision" or video_stream.get("ExtendedVideoType") == "DolbyVision",

                        # Quality profile for UI display (with HDR)
                        "quality_profile": self._build_quality_profile(extract_resolution(video_stream.get("DisplayTitle")), video_stream),

                        # Product info
                        "product": session.get("Client", "Unknown"),

                        # For TV episodes, get series info
                        "grandparent_title": None,  # Will be set below for episodes
                        "parent_title": None,       # Will be set below for episodes
                    }

                    # Calculate progress percentage
                    if session_data["duration_ms"] > 0:
                        session_data["progress_percent"] = (session_data["progress_ms"] / session_data["duration_ms"]) * 100
                    else:
                        session_data["progress_percent"] = 0

                    # If this is an episode, we need to get series information
                    if media_type == "episode" and item.get("ParentId"):
                        # We would need to make another API call to get series info
                        # For now, use available data
                        session_data["grandparent_title"] = item.get("SeriesName", "Unknown Series")
                        session_data["parent_title"] = f"Season {item.get('ParentIndexNumber', '?')}"

                    sessions.append(session_data)
                    logger.debug(f"Added session: {media_title} ({media_type})")

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

    async def list_users(self) -> List[Dict[str, Any]]:
        """Get all Jellyfin users"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                base_url = self.base_url.rstrip('/')
                url = f"{base_url}/Users"
                logger.debug(f"Fetching Jellyfin users from: {url}")

                response = await client.get(
                    url,
                    headers={"Authorization": f"MediaBrowser Token={self.admin_token or self.api_key}"},
                    timeout=10.0
                )

                logger.debug(f"Jellyfin users response - Status: {response.status_code}")
                if response.status_code != 200:
                    logger.warning(f"Jellyfin users error: {response.text}")
                    return []
                else:
                    logger.debug(f"Jellyfin users data: {response.text[:500]}...")

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
                        "last_activity": user.get("LastActivityDate"),
                        "last_login": user.get("LastLoginDate"),
                    }
                    users.append(user_data)

                return users

        except Exception as e:
            logger.error(f"Error fetching Jellyfin users: {e}")
            return []

    async def get_user(self, provider_user_id: str) -> Optional[Dict[str, Any]]:
        """Get Jellyfin user information"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    f"{self.base_url}/Users/{provider_user_id}",
                    headers={"Authorization": f"MediaBrowser Token={self.admin_token or self.api_key}"},
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
        """Terminate a Jellyfin session"""
        try:
            logger.info(f"Attempting to terminate Jellyfin session: {provider_session_id}")
            async with httpx.AsyncClient(verify=False) as client:
                base_url = self.base_url.rstrip('/')

                # First try sending a message to the client to stop playback
                message_url = f"{base_url}/Sessions/{provider_session_id}/Message"
                headers = {
                    "Authorization": f"MediaBrowser Token={self.admin_token or self.api_key}",
                    "Content-Type": "application/json"
                }

                # Send a message to stop playback
                message_data = {
                    "Header": "Playback Stopped",
                    "Text": "Your playback has been stopped by an administrator.",
                    "TimeoutMs": 5000
                }

                logger.debug(f"Jellyfin - Sending stop message to session: {provider_session_id}")
                message_response = await client.post(
                    message_url,
                    json=message_data,
                    headers=headers,
                    timeout=10.0
                )
                logger.debug(f"Message response - Status: {message_response.status_code}")

                # Now send the actual stop command using the Playstate endpoint
                stop_url = f"{base_url}/Sessions/{provider_session_id}/Playing/Stop"
                logger.debug(f"Jellyfin termination - Sending stop command to: {stop_url}")

                # The stop endpoint doesn't need a body
                stop_response = await client.post(
                    stop_url,
                    headers=headers,
                    timeout=10.0
                )

                logger.debug(f"Jellyfin stop response - Status: {stop_response.status_code}, Text: {stop_response.text[:200] if stop_response.text else 'Empty'}")

                # Success can be 200, 204, or even 404 (session already gone)
                success = stop_response.status_code in [200, 204, 404]

                if not success:
                    # Try alternative method using the general command endpoint
                    logger.debug("First method failed, trying alternative command method")
                    command_url = f"{base_url}/Sessions/{provider_session_id}/Command"
                    command_data = {"Name": "Stop"}

                    command_response = await client.post(
                        command_url,
                        json=command_data,
                        headers=headers,
                        timeout=10.0
                    )

                    logger.debug(f"Command response - Status: {command_response.status_code}")
                    success = command_response.status_code in [200, 204, 404]

                logger.info(f"Jellyfin termination final result: {success}")
                return success

        except Exception as e:
            logger.error(f"Error terminating Jellyfin session {provider_session_id}: {e}")
            return False

    async def modify_user(self, provider_user_id: str, changes: Dict[str, Any]) -> bool:
        """Modify Jellyfin user settings"""
        try:
            # Get current user policy
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    f"{self.base_url}/Users/{provider_user_id}/Policy",
                    headers={"Authorization": f"MediaBrowser Token={self.admin_token or self.api_key}"},
                    timeout=10.0
                )

                if response.status_code != 200:
                    return False

                policy = response.json()

                # Update policy with changes
                if "enabled_folders" in changes:
                    policy["EnabledFolders"] = changes["enabled_folders"]
                if "is_administrator" in changes:
                    policy["IsAdministrator"] = changes["is_administrator"]
                if "is_disabled" in changes:
                    policy["IsDisabled"] = changes["is_disabled"]

                # Update the policy
                response = await client.post(
                    f"{self.base_url}/Users/{provider_user_id}/Policy",
                    json=policy,
                    headers={"Authorization": f"MediaBrowser Token={self.admin_token or self.api_key}"},
                    timeout=10.0
                )

                return response.status_code in [200, 204]

        except Exception:
            return False

    async def change_user_password(self, provider_user_id: str, new_password: str, current_password: Optional[str] = None) -> bool:
        """Change Jellyfin user password"""
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
                    headers={"Authorization": f"MediaBrowser Token={self.admin_token or self.api_key}"},
                    timeout=10.0
                )

                return response.status_code in [200, 204]

        except Exception as e:
            logger.error(f"Failed to change Jellyfin user password: {e}")
            return False

    async def list_libraries(self) -> List[Dict[str, Any]]:
        """Get Jellyfin libraries"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                # Clean the base URL to avoid double slashes
                clean_url = self.base_url.rstrip('/')

                # First try the VirtualFolders endpoint
                response = await client.get(
                    f"{clean_url}/Library/VirtualFolders",
                    headers={"Authorization": f"MediaBrowser Token={self.admin_token or self.api_key}"},
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

                    logger.info(f"Found {len(libraries)} Jellyfin libraries via VirtualFolders")
                    return libraries

                # If VirtualFolders fails, try the user views endpoint
                logger.warning(f"VirtualFolders failed with {response.status_code}, trying user views")

                # Get current user info to get user ID
                # Note: Remove double slash in URL
                clean_url = self.base_url.rstrip('/')
                user_response = await client.get(
                    f"{clean_url}/Users/Me",
                    headers={"Authorization": f"MediaBrowser Token={self.admin_token or self.api_key}"},
                    timeout=10.0
                )

                if user_response.status_code == 200:
                    user_data = user_response.json()
                    user_id = user_data.get("Id")

                    # Get views for this user
                    views_response = await client.get(
                        f"{clean_url}/Users/{user_id}/Views",
                        headers={"Authorization": f"MediaBrowser Token={self.admin_token or self.api_key}"},
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

                        logger.info(f"Found {len(libraries)} Jellyfin libraries via user views")
                        return libraries

                logger.error(f"Failed to fetch Jellyfin libraries")
                return []

        except Exception as e:
            logger.error(f"Error fetching Jellyfin libraries: {e}")
            return []

    async def get_user_library_access(self, provider_user_id: str) -> Dict[str, Any]:
        """Get user's current library access"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                # Get full user object which contains the policy
                base = self.base_url.rstrip('/')
                user_url = f"{base}/Users/{provider_user_id}"
                logger.info(f"Jellyfin fetching user from: {user_url}")

                response = await client.get(
                    user_url,
                    headers={"Authorization": f"MediaBrowser Token={self.admin_token or self.api_key}"},
                    timeout=10.0
                )

                logger.info(f"Jellyfin get_user_library_access status: {response.status_code}")

                if response.status_code != 200:
                    logger.error(f"Failed to get Jellyfin user for {provider_user_id}: status={response.status_code}, response={response.text}")
                    return {"library_ids": [], "all_libraries": False}

                user = response.json()
                policy = user.get("Policy", {})

                logger.info(f"Jellyfin user {provider_user_id} has Policy: {bool(policy)}")
                if policy:
                    logger.info(f"Jellyfin EnableAllFolders: {policy.get('EnableAllFolders')}")
                    logger.info(f"Jellyfin EnabledFolders: {policy.get('EnabledFolders')}")

                # Check if user has access to all libraries
                all_libraries = policy.get("EnableAllFolders", False)

                # Get enabled folder IDs
                enabled_folders = policy.get("EnabledFolders", [])

                result = {
                    "library_ids": enabled_folders,
                    "all_libraries": all_libraries
                }
                logger.info(f"Jellyfin returning library access: {result}")
                return result
        except Exception as e:
            logger.error(f"Failed to get Jellyfin user library access: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"library_ids": [], "all_libraries": False}

    async def set_library_access(self, provider_user_id: str, library_ids: List[str]) -> bool:
        """Set library access for Jellyfin user"""
        return await self.modify_user(provider_user_id, {"enabled_folders": library_ids})

    async def set_user_library_access(self, provider_user_id: str, library_ids: List[str], all_libraries: bool = False) -> bool:
        """Set library access for Jellyfin user with all_libraries support"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                # Get current user to access the full Policy object
                base = self.base_url.rstrip('/')
                user_url = f"{base}/Users/{provider_user_id}"
                response = await client.get(
                    user_url,
                    headers={"Authorization": f"MediaBrowser Token={self.admin_token or self.api_key}"},
                    timeout=10.0
                )

                if response.status_code != 200:
                    logger.error(f"Failed to get Jellyfin user {provider_user_id}: {response.status_code}")
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
                policy_url = f"{base}/Users/{provider_user_id}/Policy"
                response = await client.post(
                    policy_url,
                    json=policy,
                    headers={"Authorization": f"MediaBrowser Token={self.admin_token or self.api_key}"},
                    timeout=10.0
                )

                if response.status_code in [200, 204]:
                    logger.info(f"Successfully updated library access for Jellyfin user {provider_user_id}")
                    return True
                else:
                    logger.error(f"Failed to update Jellyfin user policy: {response.status_code} - {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Exception setting Jellyfin library access: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    async def get_media_info(self, provider_media_id: str) -> Optional[Dict[str, Any]]:
        """Get Jellyfin media information"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    f"{self.base_url}/Items/{provider_media_id}",
                    headers={"Authorization": f"MediaBrowser Token={self.admin_token or self.api_key}"},
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

    async def get_version_info(self) -> Dict[str, Any]:
        """Get Jellyfin server version information"""
        try:
            async with httpx.AsyncClient(verify=False) as client:
                # Get server info
                base_url = self.base_url.rstrip('/')
                response = await client.get(
                    f"{base_url}/System/Info",
                    headers={"Authorization": f"MediaBrowser Token={self.api_key}"},
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()

                    # Get latest version from Docker Hub
                    latest_version = await self._get_latest_version(client)

                    current_version = data.get("Version", "Unknown")

                    return {
                        "current_version": current_version,
                        "server_name": data.get("ServerName", "Jellyfin Server"),
                        "operating_system": data.get("OperatingSystem", "Unknown"),
                        "architecture": data.get("Architecture", "Unknown"),
                        "product": "Jellyfin",
                        "latest_version": latest_version,
                        "update_available": self._compare_versions(current_version, latest_version) if latest_version else False,
                    }

                return {}

        except Exception as e:
            logger.error(f"Error getting Jellyfin version info: {e}")
            return {}

    async def _get_latest_version(self, client: httpx.AsyncClient) -> Optional[str]:
        """Get the latest Jellyfin version from Docker Hub"""
        try:
            logger.info("Fetching Jellyfin latest version from Docker Hub...")
            response = await client.get(
                "https://hub.docker.com/v2/repositories/jellyfin/jellyfin/tags?page_size=20",
                timeout=10.0
            )
            logger.debug(f"Docker Hub response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                tags = data.get("results", [])

                # Filter for version tags (stable X.Y.Z or RC X.Y.Z-rcN)
                import re
                version_pattern = re.compile(r'^(\d+)\.(\d+)\.(\d+)(?:-rc\d+)?$')

                versions = []
                for tag in tags:
                    tag_name = tag.get("name", "")
                    # Skip architecture-specific and date-based tags
                    if 'amd64' in tag_name or 'arm64' in tag_name or tag_name.isdigit() or 'unstable' in tag_name or 'preview' in tag_name:
                        continue
                    match = version_pattern.match(tag_name)
                    if match:
                        versions.append(tag_name)

                # Sort versions and return the latest
                if versions:
                    # Sort considering RC versions
                    def version_key(v):
                        parts = v.replace('-rc', '.').split('.')
                        return [int(x) if x.isdigit() else 0 for x in parts]
                    versions.sort(key=version_key, reverse=True)
                    logger.info(f"Found Jellyfin versions: {versions[:3]}, returning: {versions[0]}")
                    return versions[0]
                else:
                    # Fallback to known latest stable if no tags found
                    logger.debug("No versions found in Docker Hub, using fallback")
                    return "10.10.7"  # Latest stable as of Sept 2024

            logger.debug(f"Docker Hub returned non-200 status: {response.status_code}")
            return None

        except Exception as e:
            # Docker Hub API error
            logger.error(f"Error fetching from Docker Hub: {e}")
            return None

    def _compare_versions(self, current: str, latest: str) -> bool:
        """Compare version strings to determine if update is available"""
        try:
            # Parse version strings (e.g., "10.8.13")
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

        except Exception:
            return False