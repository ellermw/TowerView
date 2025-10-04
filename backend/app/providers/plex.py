import httpx
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from .base import BaseProvider
from ..core.token_cache import token_cache

logger = logging.getLogger(__name__)


class PlexProvider(BaseProvider):

    def __init__(self, server, credentials):
        super().__init__(server, credentials)
        # Check for API key first, then token, for Plex authentication
        self.token = credentials.get("api_key") or credentials.get("token") if credentials else None
        self.username = credentials.get("username") if credentials else None
        self.password = credentials.get("password") if credentials else None
        self.client_id = credentials.get("client_id", "towerview-app") if credentials else "towerview-app"
        self.server_id = server.id  # Track server ID for cache key
        logger.debug(f"PlexProvider init for server {server.id}: username={self.username}, has_password={'Yes' if self.password else 'No'}, has_token={'Yes' if self.token else 'No'}")

    async def connect(self) -> bool:
        """Test connection to Plex server with Plex.tv authentication"""
        try:
            # Ensure we have a valid token (checks cache first, avoids rate limiting)
            await self._ensure_valid_token()

            if not self.token:
                logger.debug("No valid token available after authentication attempt")
                return False

            # Test connection to the server
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/",
                    headers={"X-Plex-Token": self.token},
                    timeout=10.0
                )
                logger.debug(f"Plex server connection test - Status: {response.status_code}")
                return response.status_code == 200
        except Exception as e:
            logger.debug(f"Plex connection error: {e}")
            return False

    async def _ensure_valid_token(self) -> None:
        """Ensure we have a valid token, using Redis cache to avoid rate limiting"""
        # If we already have an API key/token from credentials, use it
        # This is the server admin token which has full permissions
        if self.token:
            logger.debug(f"Using existing API key/token for server {self.server_id}")
            return

        # Only use Plex.tv auth if we don't have a server admin token
        # Check Redis cache for valid Plex.tv user token
        cached_data = token_cache.get_token(self.server_id)
        if cached_data and cached_data.get("token"):
            self.token = cached_data["token"]
            expiry = datetime.fromisoformat(cached_data.get("expiry", "1970-01-01"))
            remaining = (expiry - datetime.utcnow()).total_seconds()
            logger.debug(f"Using cached Plex.tv token for server {self.server_id} (expires in {remaining:.0f}s)")
            return

        # If we don't have username/password, we can't authenticate with Plex.tv
        if not self.username or not self.password:
            logger.debug("No Plex.tv credentials available for authentication")
            return

        # Check for active rate limit cooldown
        cooldown_until = token_cache.get_rate_limit_info(self.server_id)
        if cooldown_until and datetime.utcnow() < cooldown_until:
            remaining = (cooldown_until - datetime.utcnow()).total_seconds()
            logger.debug(f"Skipping Plex.tv auth - rate limit cooldown ({remaining:.1f}s remaining)")
            return

        logger.debug("Getting fresh Plex.tv token...")
        current_time = datetime.utcnow()

        new_token = await self._authenticate_with_plex_tv()
        if new_token:
            self.token = new_token
            # Set token to expire in 23 hours (Plex tokens are valid for 24 hours)
            token_expiry = current_time + timedelta(hours=23)

            # Store in Redis cache
            token_cache.set_token(self.server_id, new_token, token_expiry)
            logger.debug(f"Successfully refreshed Plex.tv token for server {self.server_id}")
        else:
            logger.debug(f"Failed to refresh Plex.tv token for server {self.server_id}")

    async def _authenticate_with_plex_tv(self) -> Optional[str]:
        """Authenticate with Plex.tv and get user token with Plex Pass privileges"""
        try:
            async with httpx.AsyncClient() as client:
                # Step 1: Authenticate with Plex.tv
                auth_data = {
                    "user[login]": self.username,
                    "user[password]": self.password
                }
                headers = {
                    "X-Plex-Client-Identifier": self.client_id,
                    "X-Plex-Product": "TowerView",
                    "X-Plex-Version": "1.0.0",
                    "X-Plex-Device": "TowerView",
                    "X-Plex-Device-Name": "TowerView Server Monitor",
                    "X-Plex-Platform": "Web",
                    "X-Plex-Platform-Version": "1.0"
                }

                logger.debug("Authenticating with Plex.tv...")
                response = await client.post(
                    "https://plex.tv/users/sign_in.json",
                    data=auth_data,
                    headers=headers,
                    timeout=10.0
                )

                logger.debug(f"Plex.tv auth response - Status: {response.status_code}")
                if response.status_code == 429:
                    logger.debug("Plex.tv rate limiting detected - will wait 10 minutes before next attempt")
                    # Set rate limit cooldown in Redis cache
                    token_cache.set_rate_limit(self.server_id, cooldown_minutes=10)
                    return None
                elif response.status_code != 201:
                    logger.debug(f"Plex.tv authentication failed: {response.text}")
                    return None

                auth_result = response.json()
                if "user" not in auth_result or "authToken" not in auth_result["user"]:
                    logger.debug("Invalid Plex.tv response structure")
                    return None

                user_token = auth_result["user"]["authToken"]
                logger.debug(f"Got Plex.tv user token with Plex Pass privileges")
                return user_token

        except Exception as e:
            logger.debug(f"Plex.tv authentication error: {e}")
            return None

    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with Plex.tv"""
        try:
            # First authenticate with Plex.tv
            async with httpx.AsyncClient() as client:
                auth_data = {
                    "user[login]": username,
                    "user[password]": password
                }
                headers = {
                    "X-Plex-Client-Identifier": self.client_id,
                    "X-Plex-Product": "Towerview",
                    "X-Plex-Version": "1.0"
                }

                response = await client.post(
                    "https://plex.tv/users/sign_in.xml",
                    data=auth_data,
                    headers=headers,
                    timeout=10.0
                )

                if response.status_code != 201:
                    return None

                # Parse XML response to get user token and info
                # For simplicity, assuming XML parsing logic here
                # In a real implementation, you'd use xml.etree.ElementTree
                user_info = self._parse_plex_user_response(response.text)

                if not user_info:
                    return None

                # Verify user has access to this server
                if await self._verify_server_access(user_info["token"]):
                    return user_info

                return None

        except Exception:
            return None

    async def _verify_server_access(self, user_token: str) -> bool:
        """Verify user has access to this specific server"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/",
                    headers={"X-Plex-Token": user_token},
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception:
            return False

    def _parse_plex_user_response(self, xml_response: str) -> Optional[Dict[str, Any]]:
        """Parse Plex user authentication response"""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_response)

            # Extract user information from XML
            user_elem = root.find('.//user')
            if user_elem is not None:
                return {
                    "user_id": user_elem.get("id"),
                    "email": user_elem.get("email"),
                    "token": user_elem.get("authenticationToken") or user_elem.get("authToken")
                }
        except Exception as e:
            logger.error(f"Error parsing Plex user response: {e}")

        return None

    async def list_active_sessions(self) -> List[Dict[str, Any]]:
        """Get active Plex sessions with detailed information"""
        try:
            # Ensure we have a valid token (avoid rate limiting)
            await self._ensure_valid_token()
            if not self.token:
                logger.debug("No valid Plex token available")
                return []

            logger.debug(f"Fetching Plex sessions (authenticated)")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/status/sessions",
                    headers={"X-Plex-Token": self.token},
                    timeout=10.0
                )

                logger.debug(f"Plex sessions response - Status: {response.status_code}")
                if response.status_code != 200:
                    logger.debug(f"Plex sessions error: {response.text[:200]}")
                    return []

                logger.debug(f"Plex sessions XML response: {response.text[:500] if response.text else 'None/Empty'}")

                # Check if response text is valid before parsing
                if not response.text or response.text.strip() == "":
                    logger.debug("Plex sessions response is empty or None")
                    return []

                # Parse XML response
                import xml.etree.ElementTree as ET
                try:
                    root = ET.fromstring(response.text)
                except ET.ParseError as e:
                    logger.error(f"Error parsing Plex sessions XML: {e}")
                    return []
                except Exception as e:
                    logger.error(f"Error parsing Plex sessions: {e}")
                    return []

                sessions = []

                for video in root.findall('.//Video'):
                    # Basic session info
                    session_key = video.get("sessionKey")
                    rating_key = video.get("ratingKey")

                    # Get client identifier for termination
                    player_elem = video.find('Player')
                    client_id = player_elem.get("machineIdentifier") if player_elem is not None else None
                    device_id = player_elem.get("address") if player_elem is not None else None

                    logger.debug(f"Plex session found - sessionKey: {session_key}, ratingKey: {rating_key}, clientId: {client_id}, deviceId: {device_id}")
                    session_data = {
                        "session_id": session_key,
                        "client_id": client_id,  # Store for termination
                        "media_id": video.get("ratingKey"),
                        "media_type": video.get("type"),
                        "state": "unknown",
                        "progress_ms": int(video.get("viewOffset", 0)),
                        "duration_ms": int(video.get("duration", 0)),

                        # Media details
                        "title": video.get("title"),
                        "grandparent_title": video.get("grandparentTitle"),  # Show name
                        "parent_title": video.get("parentTitle"),  # Season
                        "year": video.get("year"),
                        "summary": video.get("summary"),
                        "content_rating": video.get("contentRating"),
                        "library_section": video.get("librarySectionTitle"),
                        "_library_section_title": video.get("librarySectionTitle"),  # Keep for 4K detection

                        # User info
                        "user_id": None,
                        "username": None,
                        "user_thumb": None,

                        # Player info
                        "device": None,
                        "platform": None,
                        "product": None,
                        "version": None,
                        "address": None,
                        "location": None,

                        # Streaming details
                        "video_decision": None,
                        "original_resolution": None,
                        "original_bitrate": None,
                        "stream_bitrate": None,
                        "video_codec": None,
                        "audio_codec": None,
                        "audio_channels": None,
                        "container": None,
                        "video_profile": None,
                        "is_4k": False,
                        "is_hdr": False,
                        "is_dolby_vision": False,
                    }

                    # Calculate progress percentage
                    if session_data["duration_ms"] > 0:
                        session_data["progress_percent"] = (session_data["progress_ms"] / session_data["duration_ms"]) * 100
                        session_data["progress_seconds"] = session_data["progress_ms"] // 1000
                        session_data["duration_seconds"] = session_data["duration_ms"] // 1000
                    else:
                        session_data["progress_percent"] = 0
                        session_data["progress_seconds"] = 0
                        session_data["duration_seconds"] = 0

                    # Extract User info
                    user_elem = video.find('User')
                    if user_elem is not None:
                        session_data["user_id"] = user_elem.get("id")
                        session_data["username"] = user_elem.get("title")
                        session_data["user_thumb"] = user_elem.get("thumb")

                    # Extract Player info
                    player_elem = video.find('Player')
                    if player_elem is not None:
                        session_data["state"] = player_elem.get("state", "unknown")
                        session_data["device"] = player_elem.get("title")
                        session_data["platform"] = player_elem.get("platform")
                        session_data["product"] = player_elem.get("product")
                        session_data["version"] = player_elem.get("version")
                        session_data["address"] = player_elem.get("address")
                        session_data["location"] = player_elem.get("local") == "1" and "local" or "remote"

                    # Extract Session info - IMPORTANT: Get the real session ID for termination
                    session_elem = video.find('Session')
                    if session_elem is not None:
                        # Store the actual session ID - this is what's needed for termination!
                        actual_session_id = session_elem.get("id")
                        if actual_session_id:
                            session_data["session_id"] = actual_session_id  # Override with real session ID
                        session_data["session_bandwidth"] = session_elem.get("bandwidth")
                        session_data["session_location"] = session_elem.get("location")

                    # Extract TranscodeSession info for hardware transcoding details
                    transcode_elem = video.find('TranscodeSession')
                    # Debug: Log whether TranscodeSession exists
                    logger.info(f"TranscodeSession found for {session_data.get('title')}: {transcode_elem is not None}")
                    if transcode_elem is not None:
                        # Debug logging
                        logger.debug(f"TranscodeSession attributes for {session_data.get('title')}:")
                        logger.debug(f"  transcodeHwRequested: {transcode_elem.get('transcodeHwRequested')}")
                        logger.debug(f"  transcodeHwDecoding: {transcode_elem.get('transcodeHwDecoding')}")
                        logger.debug(f"  transcodeHwEncoding: {transcode_elem.get('transcodeHwEncoding')}")
                        logger.debug(f"  transcodeHwDecodingTitle: {transcode_elem.get('transcodeHwDecodingTitle')}")
                        logger.debug(f"  transcodeHwEncodingTitle: {transcode_elem.get('transcodeHwEncodingTitle')}")
                        logger.debug(f"  transcodeHwFullPipeline: {transcode_elem.get('transcodeHwFullPipeline')}")

                        session_data["transcode_hw_requested"] = transcode_elem.get("transcodeHwRequested") == "1"
                        session_data["transcode_hw_decode"] = transcode_elem.get("transcodeHwDecoding") == "1"
                        session_data["transcode_hw_encode"] = transcode_elem.get("transcodeHwEncoding") == "1"
                        session_data["transcode_hw_decode_title"] = transcode_elem.get("transcodeHwDecodingTitle")
                        session_data["transcode_hw_encode_title"] = transcode_elem.get("transcodeHwEncodingTitle")
                        session_data["transcode_hw_full_pipeline"] = transcode_elem.get("transcodeHwFullPipeline") == "1"
                        session_data["transcode_throttled"] = transcode_elem.get("throttled") == "1"
                        speed = transcode_elem.get("speed")
                        if speed:
                            try:
                                session_data["transcode_speed"] = float(speed)
                            except (ValueError, TypeError):
                                session_data["transcode_speed"] = None

                        # Get transcoded resolution if available from TranscodeSession
                        transcode_width = transcode_elem.get("width")
                        transcode_height = transcode_elem.get("height")

                        # Debug log
                        if "All of You" in session_data.get("title", ""):
                            logger.info(f"All of You - TranscodeSession width={transcode_width}, height={transcode_height}")

                        if transcode_height:
                            h = int(transcode_height)
                            if h >= 2000:
                                session_data["stream_resolution"] = "4K"
                            elif h >= 1080:
                                session_data["stream_resolution"] = "1080p"
                            elif h >= 720:
                                session_data["stream_resolution"] = "720p"
                            elif h >= 480:
                                session_data["stream_resolution"] = "480p"
                            elif h >= 360:
                                session_data["stream_resolution"] = "360p"
                            elif h >= 240:
                                session_data["stream_resolution"] = "SD"
                            else:
                                # Very low resolution
                                session_data["stream_resolution"] = f"{h}p"
                    else:
                        # No TranscodeSession found, but check if transcoding
                        if session_data.get("video_decision") == "transcode":
                            logger.info(f"WARNING: Transcoding but no TranscodeSession for {session_data.get('title')}")

                    # Extract Media info for transcoding details
                    media_elem = video.find('Media')
                    if media_elem is not None:
                        session_data["video_codec"] = media_elem.get("videoCodec")
                        session_data["audio_codec"] = media_elem.get("audioCodec")
                        session_data["audio_channels"] = media_elem.get("audioChannels")
                        session_data["container"] = media_elem.get("container")
                        session_data["original_bitrate"] = media_elem.get("bitrate")

                        # Get resolution info
                        video_res = media_elem.get("videoResolution")
                        media_height = media_elem.get("height")
                        media_width = media_elem.get("width")

                        # Check Part element first for transcoding decision
                        part_elem = media_elem.find('Part')
                        if part_elem is not None:
                            session_data["video_decision"] = part_elem.get("decision", "unknown")

                        # Debug log for resolution
                        if "All of You" in session_data.get("title", ""):
                            logger.info(f"All of You - videoResolution from Media: {video_res}")
                            logger.info(f"All of You - Media dimensions: {media_width}x{media_height}")
                            logger.info(f"All of You - Video decision: {session_data.get('video_decision')}")
                            # Log all Media attributes
                            logger.info(f"All of You - Media attributes: {media_elem.attrib}")

                        # For transcoding, videoResolution is the source, height/width is transcoded
                        # For direct play, videoResolution is the actual resolution
                        is_transcoding = session_data.get("video_decision") == "transcode"

                        if is_transcoding:
                            # During transcoding, Plex Media element shows transcoded info, not source!
                            # We need to infer source resolution from library name or other metadata
                            library = session_data.get("_library_section_title", "")

                            # Check if it's from a 4K library
                            if "4K" in library or "2160" in library:
                                session_data["original_resolution"] = "4K"

                            # If TranscodeSession didn't provide stream_resolution, use Media height
                            if not session_data.get("stream_resolution") and media_height:
                                h = int(media_height)
                                # This is the transcoded resolution
                                if h >= 2000:
                                    session_data["stream_resolution"] = "4K"
                                elif h >= 1080:
                                    session_data["stream_resolution"] = "1080p"
                                elif h >= 720:
                                    session_data["stream_resolution"] = "720p"
                                elif h >= 480:
                                    session_data["stream_resolution"] = "480p"
                                elif h >= 360:
                                    session_data["stream_resolution"] = "360p"
                                elif h >= 240:
                                    session_data["stream_resolution"] = "SD"
                                else:
                                    session_data["stream_resolution"] = f"{h}p"

                            # Try to infer original resolution if not already set
                            if not session_data.get("original_resolution"):
                                # Get the stream resolution (either from TranscodeSession or Media height)
                                stream_res = session_data.get("stream_resolution")
                                if stream_res:
                                    # Parse the stream resolution to determine source
                                    if stream_res == "4K":
                                        # 4K transcode is likely from 4K source
                                        session_data["original_resolution"] = "4K"
                                    elif stream_res == "1080p":
                                        # 1080p transcode could be from 1080p (codec conversion) or 4K
                                        # Default to 1080p since it's more common for codec conversion
                                        session_data["original_resolution"] = "1080p"
                                    elif stream_res in ["720p", "480p", "360p", "SD"]:
                                        # Lower quality transcodes are usually from 1080p sources
                                        session_data["original_resolution"] = "1080p"
                                    else:
                                        # Default to 1080p for any unrecognized format
                                        session_data["original_resolution"] = "1080p"
                                else:
                                    # No stream resolution found, default to 1080p
                                    session_data["original_resolution"] = "1080p"
                        else:
                            # Direct play - use videoResolution
                            if video_res:
                                session_data["original_resolution"] = video_res
                            elif media_height:
                                # Fallback to height-based detection if videoResolution is missing
                                h = int(media_height)
                                if h >= 2000:
                                    session_data["original_resolution"] = "4K"
                                elif h >= 1080:
                                    session_data["original_resolution"] = "1080p"
                                elif h >= 720:
                                    session_data["original_resolution"] = "720p"
                                elif h >= 480:
                                    session_data["original_resolution"] = "480p"
                                else:
                                    session_data["original_resolution"] = "SD"
                            else:
                                # Last resort - assume 1080p as it's most common
                                session_data["original_resolution"] = "1080p"

                        session_data["is_4k"] = video_res == "4k"

                        # Debug final resolutions
                        if "All of You" in session_data.get("title", ""):
                            logger.info(f"All of You - Final: original_resolution={session_data.get('original_resolution')}, stream_resolution={session_data.get('stream_resolution')}")

                        # Extract more Part info
                        if part_elem is not None:

                            # Extract detailed stream info
                            video_stream = part_elem.find('Stream[@streamType="1"]')  # Video stream
                            if video_stream is not None:
                                session_data["video_profile"] = video_stream.get("profile")
                                session_data["stream_bitrate"] = video_stream.get("bitrate")

                                # Debug logging for HDR detection
                                colorTrc = video_stream.get("colorTrc")
                                colorRange = video_stream.get("colorRange")
                                colorSpace = video_stream.get("colorSpace")
                                colorPrimaries = video_stream.get("colorPrimaries")
                                DOVIPresent = video_stream.get("DOVIPresent")
                                DOVILevel = video_stream.get("DOVILevel")
                                profile = video_stream.get("profile", "").lower()

                                logger.debug(f"HDR Debug for {session_data.get('title')}: colorTrc={colorTrc}, colorRange={colorRange}, colorSpace={colorSpace}, colorPrimaries={colorPrimaries}, DOVIPresent={DOVIPresent}, DOVILevel={DOVILevel}, profile={profile}")

                                # Check for HDR/Dolby Vision
                                # HDR10 is indicated by colorTrc=smpte2084 or colorPrimaries=bt2020
                                # Also check for Main 10 profile which indicates HDR
                                session_data["is_hdr"] = (
                                    colorTrc == "smpte2084" or
                                    colorPrimaries in ["bt2020", "bt2020nc"] or
                                    colorSpace in ["bt2020nc", "bt2020"] or
                                    "main 10" in profile or
                                    "main10" in profile
                                )
                                session_data["is_dolby_vision"] = (
                                    DOVIPresent == "1" or
                                    DOVILevel is not None
                                )

                                # Log the HDR detection result
                                logger.info(f"HDR Detection for {session_data.get('title')}: is_hdr={session_data['is_hdr']}, is_dolby_vision={session_data['is_dolby_vision']}")

                                # Build quality description
                                quality_parts = []
                                if session_data["original_resolution"]:
                                    quality_parts.append(session_data["original_resolution"].upper())
                                if session_data["is_dolby_vision"]:
                                    quality_parts.append("DoVi")
                                elif session_data["is_hdr"]:
                                    quality_parts.append("HDR")
                                if session_data["video_codec"]:
                                    quality_parts.append(session_data["video_codec"].upper())
                                session_data["quality_profile"] = " ".join(quality_parts)

                    # Build full title for shows
                    if session_data["media_type"] == "episode":
                        title_parts = []
                        if session_data["grandparent_title"]:
                            title_parts.append(session_data["grandparent_title"])
                        if session_data["parent_title"]:
                            title_parts.append(session_data["parent_title"])
                        if session_data["title"]:
                            title_parts.append(session_data["title"])
                        session_data["full_title"] = " - ".join(title_parts)
                    else:
                        session_data["full_title"] = session_data["title"] or "Unknown"

                    sessions.append(session_data)

                    # Log critical session data for debugging
                    if "Together" in session_data.get("title", ""):
                        logger.info(f"Added Together session with is_hdr={session_data.get('is_hdr')}, quality_profile={session_data.get('quality_profile')}")

                return sessions

        except Exception as e:
            logger.error(f"Error parsing Plex sessions: {e}")
            return []

    async def get_version_info(self) -> Dict[str, Any]:
        """Get Plex server version information"""
        try:
            # Ensure we have a valid token
            await self._ensure_valid_token()

            if not self.token:
                logger.debug("No valid token available for getting Plex version")
                return {}

            async with httpx.AsyncClient() as client:
                # Get server info which includes version
                response = await client.get(
                    f"{self.base_url}/",
                    headers={"X-Plex-Token": self.token, "Accept": "application/json"},
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()
                    media_container = data.get("MediaContainer", {})

                    # Get latest version from Docker Hub
                    latest_version = await self._get_latest_version(client)

                    current_version = media_container.get("version", "Unknown")

                    return {
                        "current_version": current_version,
                        "platform": media_container.get("platform", "Unknown"),
                        "platform_version": media_container.get("platformVersion", "Unknown"),
                        "device": media_container.get("device", "Unknown"),
                        "product": media_container.get("product", "Plex Media Server"),
                        "latest_version": latest_version,
                        "update_available": self._compare_versions(current_version, latest_version) if latest_version else False
                    }

                return {}

        except Exception as e:
            logger.error(f"Error getting Plex version info: {e}")
            return {}

    async def _get_latest_version(self, client: httpx.AsyncClient) -> Optional[str]:
        """Get the latest Plex version from Docker Hub"""
        try:
            logger.info("Fetching Plex latest version from Docker Hub...")
            response = await client.get(
                "https://hub.docker.com/v2/repositories/plexinc/pms-docker/tags?page_size=20",
                timeout=10.0
            )

            if response.status_code == 200:
                data = response.json()
                tags = data.get("results", [])

                # Filter for version tags (format: X.Y.Z.XXXXX-XXXXXXX)
                import re
                version_pattern = re.compile(r'^(\d+)\.(\d+)\.(\d+)\.(\d+)-([\w]+)$')

                versions = []
                for tag in tags:
                    tag_name = tag.get("name", "")
                    # Skip 'latest' and other non-version tags
                    if tag_name in ['latest', 'plex-user-test', 'beta', 'public']:
                        continue
                    match = version_pattern.match(tag_name)
                    if match:
                        versions.append(tag_name)

                # Sort versions and return the latest
                if versions:
                    # Sort by version numbers
                    versions.sort(key=lambda v: [int(x) for x in v.split('-')[0].split('.')], reverse=True)
                    logger.info(f"Found Plex versions: {versions[:3]}, returning: {versions[0]}")
                    return versions[0]
                else:
                    logger.debug("No Plex versions found in tags")

            return None

        except Exception as e:
            logger.debug(f"Could not fetch latest Plex version: {e}")
            return None

    def _compare_versions(self, current: str, latest: str) -> bool:
        """Compare version strings to determine if update is available"""
        try:
            # Parse version strings (e.g., "1.32.5.7349-8f4248874")
            current_parts = current.split("-")[0].split(".")
            latest_parts = latest.split("-")[0].split(".")

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
        """Get all Plex users with access to this server"""
        try:
            # Ensure we have a valid token
            await self._ensure_valid_token()

            if not self.token:
                logger.debug("No valid token available for listing Plex users")
                return []

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/accounts",
                    headers={"X-Plex-Token": self.token},
                    timeout=10.0
                )

                if response.status_code != 200:
                    return []

                # Parse XML response
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.text)
                users = []

                for account in root.findall('.//Account'):
                    user_data = {
                        "user_id": account.get("id"),
                        "username": account.get("name"),
                        "email": account.get("email"),
                        "thumb": account.get("thumb"),
                        "home": account.get("home") == "1",
                        "guest": account.get("guest") == "1",
                        "restricted": account.get("restricted") == "1",
                        "protected": account.get("protected") == "1",
                        "admin": account.get("admin") == "1",
                        "last_activity": None,  # Plex doesn't provide this in the accounts API
                        "last_login": None,  # Plex doesn't provide this directly
                    }
                    users.append(user_data)

                return users

        except Exception as e:
            logger.error(f"Error fetching Plex users: {e}")
            return []

    async def get_user(self, provider_user_id: str) -> Optional[Dict[str, Any]]:
        """Get Plex user information"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/accounts/{provider_user_id}",
                    headers={"X-Plex-Token": self.token},
                    timeout=10.0
                )

                if response.status_code != 200:
                    return None

                data = response.json()
                account = data.get("MediaContainer", {}).get("Account", [{}])[0]

                return {
                    "user_id": account.get("id"),
                    "username": account.get("name"),
                    "email": account.get("email"),
                    "thumb": account.get("thumb")
                }

        except Exception:
            return None

    async def terminate_session(self, provider_session_id: str, message: str = None) -> bool:
        """Terminate a Plex session - requires server admin token or Plex Pass"""
        try:
            # Check if we have any token at all
            if not self.token and not (self.username and self.password):
                logger.debug("No Plex authentication available for termination")
                return False

            # If we're using username/password, ensure we have a fresh Plex.tv token
            if self.username and self.password:
                await self._ensure_valid_token()
                if not self.token:
                    logger.debug("Failed to get Plex.tv token for termination")
                    return False

            async with httpx.AsyncClient() as client:
                base_url = self.base_url.rstrip('/')
                logger.info(f"================= PLEX TERMINATION ATTEMPT =================")
                logger.debug(f"Server: {self.base_url}")
                logger.debug(f"Session ID: {provider_session_id}")
                logger.debug(f"Token present: {'Yes' if self.token else 'No'}")
                logger.debug(f"Token type: {'Admin' if not (self.username and self.password) else 'User (Plex.tv)'}")

                # First, get the current session to find the client identifier
                session_info = None
                try:
                    response = await client.get(
                        f"{base_url}/status/sessions",
                        headers={"X-Plex-Token": self.token},
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        import xml.etree.ElementTree as ET
                        root = ET.fromstring(response.text)
                        for video in root.findall('.//Video'):
                            if video.get("sessionKey") == provider_session_id:
                                player_elem = video.find('Player')
                                if player_elem is not None:
                                    session_info = {
                                        "client_id": player_elem.get("machineIdentifier"),
                                        "address": player_elem.get("address"),
                                        "device_id": player_elem.get("device")
                                    }
                                    logger.debug(f"Found Plex Pass session info: {session_info}")
                                break
                except Exception as e:
                    logger.debug(f"Could not get session info: {e}")

                # Track which methods reported success
                methods_attempted = []

                # Method 0: Use the official Plex API endpoint with the correct session ID
                # This is what Plex Web Dashboard uses - it needs the Session.id not sessionKey!
                terminate_url = f"{base_url}/status/sessions/terminate"
                logger.debug(f"Attempting Method 0 - Official Plex terminate endpoint: {terminate_url}")
                logger.debug(f"Using session ID: {provider_session_id}")

                try:
                    # Use DELETE with sessionId parameter - this is what works!
                    # Use provided message or default
                    reason = message if message else "Terminated by TowerView admin"
                    response = await client.delete(
                        terminate_url,
                        params={"sessionId": provider_session_id, "reason": reason},
                        headers={
                            "X-Plex-Token": self.token,
                            "Accept": "application/json"
                        },
                        timeout=10.0
                    )
                    logger.debug(f"Method 0 terminate - Status: {response.status_code}")
                    if response.status_code in [200, 202, 204]:
                        logger.info("Session termination successful!")
                        return True
                    else:
                        logger.debug(f"Method 0 failed with status {response.status_code}")
                except Exception as e:
                    logger.debug(f"Method 0 failed: {e}")

                # Method 1: Direct transcode session termination (most reliable for transcoded content)
                # This works even without Plex Pass for transcoded sessions
                url1 = f"{base_url}/video/:/transcode/universal/stop"
                params1 = {"session": provider_session_id}
                logger.debug(f"Attempting Method 1 - Transcode stop: {url1}")

                try:
                    response = await client.get(
                        url1,
                        params=params1,
                        headers={"X-Plex-Token": self.token},
                        timeout=10.0
                    )
                    logger.debug(f"Method 1 transcode stop - Status: {response.status_code}")
                    if response.status_code in [200, 202, 204]:
                        logger.debug("Method 1 (Transcode stop) returned success code")
                        methods_attempted.append(("Transcode stop", response.status_code))
                except Exception as e:
                    logger.debug(f"Method 1 transcode stop failed: {e}")

                # Method 2: Tautulli's method - POST to terminate with reason
                url2 = f"{base_url}/status/sessions/terminate"
                data2 = {
                    "sessionKey": provider_session_id,
                    "reason": "Terminated by TowerView"
                }
                logger.debug(f"Attempting Tautulli termination (Method 2) - POST terminate: {url2}, Data: {data2}")

                try:
                    response = await client.post(
                        url2,
                        data=data2,
                        headers={"X-Plex-Token": self.token},
                        timeout=10.0
                    )
                    logger.debug(f"Method 2 termination attempt - Status: {response.status_code}, Text: {response.text[:200]}")

                    if response.status_code in [200, 202, 204]:
                        logger.debug("Method 2 (Tautulli POST) returned success code")
                        methods_attempted.append(("POST terminate", response.status_code))
                    else:
                        logger.debug(f"Method 2 failed with status {response.status_code}")
                except Exception as e:
                    logger.debug(f"Method 2 failed: {e}")

                # Method 3: Try with form-encoded format
                url3 = f"{base_url}/status/sessions/terminate"
                headers2 = {
                    "X-Plex-Token": self.token,
                    "Content-Type": "application/x-www-form-urlencoded"
                }
                data2 = f"sessionKey={provider_session_id}&reason=Terminated%20by%20TowerView"
                logger.debug(f"Attempting Tautulli termination (Method 2) - Form data: {url2}")

                try:
                    response = await client.post(
                        url2,
                        content=data2,
                        headers=headers2,
                        timeout=10.0
                    )
                    logger.debug(f"Method 2 termination attempt - Status: {response.status_code}, Text: {response.text[:200]}")

                    if response.status_code in [200, 202, 204]:
                        logger.debug("Method 2 (Form data) returned success code")
                        methods_attempted.append(("Form data", response.status_code))
                    else:
                        logger.debug(f"Method 2 failed with status {response.status_code}")
                except Exception as e:
                    logger.debug(f"Method 2 failed: {e}")

                # Method 3: Plex Pass - Client command with machine identifier
                if session_info and session_info.get("client_id"):
                    url3 = f"{base_url}/player/playback/stop"
                    headers3 = {
                        "X-Plex-Token": self.token,
                        "X-Plex-Target-Client-Identifier": session_info["client_id"]
                    }
                    logger.debug(f"Attempting Plex Pass termination (Method 3) - Client stop: {url3} with client {session_info['client_id']}")

                    response = await client.get(
                        url3,
                        headers=headers3,
                        timeout=10.0
                    )
                    logger.debug(f"Method 3 termination attempt - Status: {response.status_code}, Text: {response.text[:200]}")

                    if response.status_code in [200, 202, 204]:
                        logger.debug("Method 3 (Plex Pass client command) returned success code")
                        methods_attempted.append(("Client stop", response.status_code))

                # Method 4: Plex Pass - Direct session management API
                if session_info and session_info.get("client_id"):
                    url4 = f"{base_url}/system/players/{session_info['client_id']}/playback/stop"
                    logger.debug(f"Attempting Plex Pass termination (Method 4) - System players API: {url4}")

                    try:
                        response = await client.put(
                            url4,
                            headers={"X-Plex-Token": self.token},
                            timeout=10.0
                        )
                        logger.debug(f"Method 4 termination attempt - Status: {response.status_code}, Text: {response.text[:200]}")

                        if response.status_code in [200, 202, 204]:
                            logger.debug("Method 4 (Plex Pass system players) returned success code")
                            methods_attempted.append(("System players", response.status_code))
                    except Exception as e:
                        logger.debug(f"Method 4 failed: {e}")

                # Method 5: Send stop command to client directly via /clients endpoint
                if session_info and session_info.get("client_id"):
                    url5 = f"{base_url}/clients/{session_info['client_id']}/timeline/poll"
                    params5 = {
                        "commandID": "1",
                        "wait": "0",
                        "type": "video",
                        "state": "stopped"
                    }
                    logger.debug(f"Attempting Method 5 - Client timeline stop: {url5}")

                    try:
                        response = await client.get(
                            url5,
                            params=params5,
                            headers={"X-Plex-Token": self.token},
                            timeout=10.0
                        )
                        logger.debug(f"Method 5 timeline stop attempt - Status: {response.status_code}")
                        if response.status_code in [200, 202, 204]:
                            logger.debug("Method 5 (Client timeline) returned success code")
                            methods_attempted.append(("Client timeline", response.status_code))
                    except Exception as e:
                        logger.debug(f"Method 5 failed: {e}")

                # Method 6: Try terminating using session ID as a query parameter
                url6 = f"{base_url}/status/sessions/terminate"
                params6 = {"sessionId": provider_session_id}
                logger.debug(f"Attempting Method 6 - Terminate with query param: {url6}?sessionId={provider_session_id}")

                try:
                    response = await client.get(
                        url6,
                        params=params6,
                        headers={"X-Plex-Token": self.token},
                        timeout=10.0
                    )
                    logger.debug(f"Method 6 GET terminate attempt - Status: {response.status_code}")
                    if response.status_code in [200, 202, 204]:
                        logger.debug("Method 6 (GET with sessionId param) returned success code")
                        methods_attempted.append(("GET terminate", response.status_code))
                except Exception as e:
                    logger.debug(f"Method 6 failed: {e}")

                # If any methods claimed success, wait and verify the session is gone
                if methods_attempted:
                    logger.debug(f"\nMethods that returned success codes: {methods_attempted}")
                    logger.debug("Waiting 2 seconds then verifying session termination...")

                    # Wait for termination to take effect
                    import asyncio
                    await asyncio.sleep(2.0)

                    # Check if session still exists
                    try:
                        verify_response = await client.get(
                            f"{base_url}/status/sessions",
                            headers={"X-Plex-Token": self.token},
                            timeout=10.0
                        )

                        if verify_response.status_code == 200:
                            import xml.etree.ElementTree as ET
                            root = ET.fromstring(verify_response.text)

                            # Check if the session still exists
                            session_still_exists = False
                            for video in root.findall('.//Video'):
                                if video.get("sessionKey") == provider_session_id:
                                    session_still_exists = True
                                    logger.warning(f" Session {provider_session_id} still exists after termination attempts!")
                                    break

                            if not session_still_exists:
                                logger.info(f" Session {provider_session_id} has been terminated and no longer exists")
                                return True
                            else:
                                logger.error(f" Session {provider_session_id} still exists despite success responses")
                                logger.debug("Checking server capabilities...")
                                # Check server capabilities to diagnose the issue
                                try:
                                    capabilities_response = await client.get(
                                        f"{base_url}/",
                                        headers={"X-Plex-Token": self.token},
                                        timeout=10.0
                                    )
                                    if capabilities_response.status_code == 200:
                                        logger.debug(f"Server accessible. Checking termination settings...")

                                        # Check if termination is enabled in server preferences
                                        prefs_response = await client.get(
                                            f"{base_url}/:/prefs",
                                            headers={"X-Plex-Token": self.token},
                                            timeout=10.0
                                        )
                                        if prefs_response.status_code == 200:
                                            logger.debug("Server preferences accessible - token has admin permissions")
                                except Exception as e:
                                    logger.debug(f"Could not check server capabilities: {e}")
                    except Exception as e:
                        logger.debug(f"Could not verify session termination: {e}")
                        # Assume success if we can't verify
                        return True

                logger.info(f"================= ALL METHODS FAILED =================")
                logger.debug(f"Plex termination failed for session {provider_session_id}")
                logger.debug(f"Server: {self.base_url}")
                logger.debug(f"Token present: {'Yes' if self.token else 'No'}")
                logger.debug(f"Client ID found: {session_info.get('client_id') if session_info else 'No'}")
                logger.debug(f"")
                logger.debug(f"Termination failed - Common reasons:")
                logger.debug(f"1. Client not controllable (remote control disabled in Plex client)")
                logger.debug(f"2. DirectPlay sessions require client cooperation to stop")
                logger.debug(f"3. The /clients endpoint is empty (client not advertising)")
                logger.debug(f"4. Only transcoded sessions can be forcefully terminated")
                logger.debug(f"Note: Admin token is valid but client isn't accepting remote commands")
                logger.debug(f"Note: Tautulli uses server admin token to terminate sessions")
                logger.info(f"===============================================")
                return False

        except Exception as e:
            logger.error(f"Error terminating Plex session {provider_session_id}: {e}")
            return False

    async def modify_user(self, provider_user_id: str, changes: Dict[str, Any]) -> bool:
        """Modify Plex user settings"""
        # Plex has limited user modification capabilities
        return False

    async def list_libraries(self) -> List[Dict[str, Any]]:
        """Get Plex libraries"""
        try:
            # Ensure we have a token for Plex
            if not self.token:
                # Try to get token from Plex.tv
                if self.username and self.password:
                    await self._get_plex_tv_token()

                if not self.token:
                    logger.warning(f"No token available for Plex server {self.server.name}")
                    return []

            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    f"{self.base_url}/library/sections",
                    headers={"X-Plex-Token": self.token, "Accept": "application/json"},
                    timeout=10.0
                )

                if response.status_code != 200:
                    logger.warning(f"Failed to get Plex libraries: {response.status_code}")
                    return []

                libraries = []

                # Try to parse as JSON first (if Accept header worked)
                try:
                    data = response.json()
                    for section in data.get("MediaContainer", {}).get("Directory", []):
                        libraries.append({
                            "id": section.get("key"),
                            "title": section.get("title"),
                            "type": section.get("type")
                        })
                except (KeyError, ValueError, TypeError):
                    # Fall back to XML parsing if JSON fails
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(response.text)
                    for directory in root.findall('.//Directory'):
                        libraries.append({
                            "id": directory.get("key"),
                            "title": directory.get("title"),
                            "type": directory.get("type")
                        })

                logger.info(f"Found {len(libraries)} Plex libraries")
                return libraries

        except Exception as e:
            logger.error(f"Error fetching Plex libraries: {str(e)}")
            return []

    async def get_user_library_access(self, provider_user_id: str) -> Dict[str, Any]:
        """Get user's current library access"""
        # Plex uses a different library access model (shared servers/libraries)
        # For now, return all libraries as accessible for Plex users
        try:
            libraries = await self.list_libraries()
            library_ids = [lib.get("id") for lib in libraries]
            return {
                "library_ids": library_ids,
                "all_libraries": True
            }
        except Exception as e:
            logger.error(f"Failed to get Plex user library access: {e}")
            return {"library_ids": [], "all_libraries": False}

    async def set_library_access(self, provider_user_id: str, library_ids: List[str]) -> bool:
        """Set library access for Plex user"""
        # Plex library access management would require more complex implementation
        return False

    async def get_media_info(self, provider_media_id: str) -> Optional[Dict[str, Any]]:
        """Get Plex media information"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/library/metadata/{provider_media_id}",
                    headers={"X-Plex-Token": self.token},
                    timeout=10.0
                )

                if response.status_code != 200:
                    return None

                data = response.json()
                metadata = data.get("MediaContainer", {}).get("Metadata", [{}])[0]

                return {
                    "id": metadata.get("ratingKey"),
                    "title": metadata.get("title"),
                    "type": metadata.get("type"),
                    "runtime": metadata.get("duration", 0) // 1000,  # Convert to seconds
                    "year": metadata.get("year"),
                    "summary": metadata.get("summary"),
                    "rating": metadata.get("rating"),
                    "thumb": metadata.get("thumb")
                }

        except Exception:
            return None