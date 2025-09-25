import httpx
from typing import List, Dict, Any, Optional
from .base import BaseProvider


class JellyfinProvider(BaseProvider):
    def __init__(self, server, credentials):
        super().__init__(server, credentials)
        # Support multiple credential field names
        self.api_key = credentials.get("api_key") or credentials.get("api_token") or credentials.get("token")
        self.admin_token = credentials.get("admin_token") or credentials.get("api_token") or credentials.get("token")
        print(f"Jellyfin provider initialized with credentials: {list(credentials.keys())}")

    async def connect(self) -> bool:
        """Test connection to Jellyfin server"""
        try:
            print(f"Testing Jellyfin connection to: {self.base_url}")
            print(f"Using API key: {self.api_key[:10]}..." if self.api_key else "No API key provided")

            async with httpx.AsyncClient() as client:
                # Ensure base_url doesn't end with slash to avoid double slashes
                base_url = self.base_url.rstrip('/')
                url = f"{base_url}/System/Info"
                headers = {"Authorization": f"MediaBrowser Token={self.api_key}"}

                response = await client.get(
                    url,
                    headers=headers,
                    timeout=10.0
                )

                print(f"Jellyfin connection test - URL: {url}")
                print(f"Response status: {response.status_code}")
                print(f"Response text: {response.text[:200]}...")

                return response.status_code == 200
        except Exception as e:
            print(f"Jellyfin connection error: {e}")
            return False

    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with Jellyfin"""
        try:
            async with httpx.AsyncClient() as client:
                auth_data = {
                    "Username": username,
                    "Pw": password
                }

                response = await client.post(
                    f"{self.base_url}/Users/AuthenticateByName",
                    json=auth_data,
                    headers={"Authorization": f"MediaBrowser Token={self.api_key}"},
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
        """Get active Jellyfin sessions"""
        try:
            async with httpx.AsyncClient() as client:
                base_url = self.base_url.rstrip('/')
                url = f"{base_url}/Sessions"
                print(f"Fetching Jellyfin sessions from: {url}")

                response = await client.get(
                    url,
                    headers={"Authorization": f"MediaBrowser Token={self.admin_token or self.api_key}"},
                    timeout=10.0
                )

                print(f"Jellyfin sessions response - Status: {response.status_code}")
                if response.status_code != 200:
                    print(f"Jellyfin sessions error: {response.text}")
                else:
                    print(f"Jellyfin sessions data: {response.text[:800]}...")
                    # Let's examine the full session structure
                    session_json = response.json()
                    if session_json:
                        print(f"First session structure keys: {list(session_json[0].keys())}")
                        if 'NowPlayingItem' in session_json[0]:
                            print(f"NowPlayingItem keys: {list(session_json[0]['NowPlayingItem'].keys())}")
                        else:
                            print("No NowPlayingItem found - this is why media shows as unknown")

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
                        print(f"Skipping session {session.get('Id')} - no NowPlayingItem")
                        continue

                    print(f"Processing session with media: {item.get('Name')} of type {item.get('Type')}")

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
                    def extract_resolution(display_title):
                        if not display_title:
                            return "Unknown"

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

                    print(f"Session bandwidth calculation: {session_bitrate} -> {session_bandwidth_kbps} kbps")

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
                        "video_decision": play_state.get("PlayMethod", "unknown").lower(),
                        "original_resolution": extract_resolution(video_stream.get("DisplayTitle")),
                        "original_bitrate": str(video_stream.get("BitRate", 0) // 1000) if video_stream.get("BitRate") else "0",
                        "stream_bitrate": str(session_bandwidth_kbps),
                        "video_codec": video_stream.get("Codec", "Unknown"),
                        "audio_codec": audio_stream.get("Codec", "Unknown"),
                        "container": item.get("Container", "Unknown"),
                        "session_bandwidth": str(session_bandwidth_kbps),

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
                    print(f"Added session: {media_title} ({media_type})")

                return sessions

        except Exception:
            return []

    async def list_users(self) -> List[Dict[str, Any]]:
        """Get all Jellyfin users"""
        try:
            async with httpx.AsyncClient() as client:
                base_url = self.base_url.rstrip('/')
                url = f"{base_url}/Users"
                print(f"Fetching Jellyfin users from: {url}")

                response = await client.get(
                    url,
                    headers={"Authorization": f"MediaBrowser Token={self.admin_token or self.api_key}"},
                    timeout=10.0
                )

                print(f"Jellyfin users response - Status: {response.status_code}")
                if response.status_code != 200:
                    print(f"Jellyfin users error: {response.text}")
                    return []
                else:
                    print(f"Jellyfin users data: {response.text[:500]}...")

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
            print(f"Error fetching Jellyfin users: {e}")
            return []

    async def get_user(self, provider_user_id: str) -> Optional[Dict[str, Any]]:
        """Get Jellyfin user information"""
        try:
            async with httpx.AsyncClient() as client:
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
            print(f"Attempting to terminate Jellyfin session: {provider_session_id}")
            async with httpx.AsyncClient() as client:
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

                print(f"Jellyfin - Sending stop message to session: {provider_session_id}")
                message_response = await client.post(
                    message_url,
                    json=message_data,
                    headers=headers,
                    timeout=10.0
                )
                print(f"Message response - Status: {message_response.status_code}")

                # Now send the actual stop command using the Playstate endpoint
                stop_url = f"{base_url}/Sessions/{provider_session_id}/Playing/Stop"
                print(f"Jellyfin termination - Sending stop command to: {stop_url}")

                # The stop endpoint doesn't need a body
                stop_response = await client.post(
                    stop_url,
                    headers=headers,
                    timeout=10.0
                )

                print(f"Jellyfin stop response - Status: {stop_response.status_code}, Text: {stop_response.text[:200] if stop_response.text else 'Empty'}")

                # Success can be 200, 204, or even 404 (session already gone)
                success = stop_response.status_code in [200, 204, 404]

                if not success:
                    # Try alternative method using the general command endpoint
                    print("First method failed, trying alternative command method")
                    command_url = f"{base_url}/Sessions/{provider_session_id}/Command"
                    command_data = {"Name": "Stop"}

                    command_response = await client.post(
                        command_url,
                        json=command_data,
                        headers=headers,
                        timeout=10.0
                    )

                    print(f"Command response - Status: {command_response.status_code}")
                    success = command_response.status_code in [200, 204, 404]

                print(f"Jellyfin termination final result: {success}")
                return success

        except Exception as e:
            print(f"Error terminating Jellyfin session {provider_session_id}: {e}")
            return False

    async def modify_user(self, provider_user_id: str, changes: Dict[str, Any]) -> bool:
        """Modify Jellyfin user settings"""
        try:
            # Get current user policy
            async with httpx.AsyncClient() as client:
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

    async def list_libraries(self) -> List[Dict[str, Any]]:
        """Get Jellyfin libraries"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/Library/VirtualFolders",
                    headers={"Authorization": f"MediaBrowser Token={self.admin_token or self.api_key}"},
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
        """Set library access for Jellyfin user"""
        return await self.modify_user(provider_user_id, {"enabled_folders": library_ids})

    async def get_media_info(self, provider_media_id: str) -> Optional[Dict[str, Any]]:
        """Get Jellyfin media information"""
        try:
            async with httpx.AsyncClient() as client:
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