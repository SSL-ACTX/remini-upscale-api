"""
Creator: Seuriin (SSL-ACTX)

A Python library for enhancing images using the unofficial Remini API.

This module provides an API wrapper to programmatically enhance images,
handling authentication, uploading, processing, and downloading automatically.
"""

import asyncio
import base64
import hashlib
import json
import logging
import mimetypes
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

# --- Logger Setup ---
log = logging.getLogger(__name__)

# Pillow check
try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

# --- Module Constants ---
REMINI_API_BASE_URL = "https://a.android.api.remini.ai/v1/mobile"
REMINI_ORACLE_API_BASE_URL = "https://api.remini.ai/v1/mobile/oracle"
DEFAULT_TOKEN_FILE = os.path.join(tempfile.gettempdir(), "remini_identity_token.json")

# --- Custom Exception ---
class ReminiError(Exception):
    """Custom exception for all Remini API-related errors."""
    pass

# --- Private Helper Functions ---
def _generate_device_ids() -> Dict[str, str]:
    """Generates a consistent set of new device IDs for a session."""
    android_id = uuid.uuid4().hex[:16]
    return {
        "android_id": android_id,
        "aaid": str(uuid.uuid4()),
        "backup_persistent_id": f"{android_id}_com.bigwinepot.nwdn.international",
        "non_backup_persistent_id": str(uuid.uuid4()),
    }

def _calculate_md5_base64(file_path: str) -> str:
    """Calculates the MD5 hash of a file and returns it Base64 encoded."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return base64.b64encode(hash_md5.digest()).decode("utf-8")

def _get_image_metadata(file_path: str) -> Dict[str, Any]:
    """Extracts size, and if Pillow is available, width and height for image metadata."""
    metadata = {"size": os.path.getsize(file_path)}
    if _PIL_AVAILABLE:
        try:
            with Image.open(file_path) as img:
                metadata["width"], metadata["height"] = img.size
        except Exception:
            pass
    return metadata

# --- Main Class ---
class Remini:
    """A client for the unofficial Remini API."""
    def __init__(self, token_path: str = DEFAULT_TOKEN_FILE):
        """Initializes the Remini API client."""
        self.token_path = token_path
        self.identity_token: Optional[str] = None
        self._device_ids = _generate_device_ids()
        self._android_headers = self._create_android_headers()

    def _create_android_headers(self) -> Dict[str, str]:
        """Creates the base headers for API requests."""
        return {
            "bsp-id": "com.bigwinepot.nwdn.international.android",
            "build-number": "202514479",
            "build-version": "3.7.1020",
            "country": "US",
            "device-manufacturer": "Samsung",
            "device-model": "SM-G998B",
            "device-type": "6.8",
            "language": "en",
            "locale": "en_US",
            "os-version": "33",
            "platform": "Android",
            "timezone": "America/New_York",
            "android-id": self._device_ids["android_id"],
            "aaid": self._device_ids["aaid"],
            "accept-encoding": "gzip",
            "user-agent": "okhttp/4.12.0",
        }

    def _get_common_headers(self, content_type: Optional[str] = None) -> Dict[str, str]:
        headers = self._android_headers.copy()
        if self.identity_token:
            headers["identity-token"] = self.identity_token
        if content_type:
            headers["content-type"] = content_type
        return headers

    def _load_identity_token(self):
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, "r") as f:
                    data = json.load(f)
                    self.identity_token = data.get("identity_token")
            except (json.JSONDecodeError, IOError):
                self.identity_token = None

    def _save_identity_token(self):
        if self.identity_token:
            with open(self.token_path, "w") as f:
                json.dump({"identity_token": self.identity_token}, f, indent=4)

    async def _login(self):
        self._load_identity_token()
        if self.identity_token and await self._get_user_profile():
            log.info("Successfully logged in with existing token.")
            return

        log.info("No valid token found. Requesting a new one...")
        await self._get_setup()
        if not await self._get_user_profile():
            raise ReminiError("Failed to activate user profile even with a new token.")
        log.info("New token acquired and user profile activated.")

    async def _get_setup(self):
        headers = self._get_common_headers()
        headers.update({
            "first-install-timestamp": f"{int(datetime.now(timezone.utc).timestamp() * 1000) / 1000:.0f}E9",
            "backup-persistent-id": self._device_ids["backup_persistent_id"],
            "non-backup-persistent-id": self._device_ids["non_backup_persistent_id"],
            "environment": "Production",
            "settings-response-version": "v2",
            "is-app-running-in-background": "false",
            "is-old-user": "true",
            "app-set-id": "d44bd45a-a45d-4470-9674-7348a8e3fb71",
        })
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{REMINI_ORACLE_API_BASE_URL}/setup", headers=headers)
                response.raise_for_status()
                data = response.json()
            token = data.get("settings", {}).get("__identity__", {}).get("token")
            if not token:
                raise ReminiError(f"Token not found in setup response: {data}")
            self.identity_token = token
            self._save_identity_token()
        except httpx.HTTPStatusError as e:
            raise ReminiError(f"HTTP error during setup: {e.response.status_code} - {e.response.text}") from e

    async def _get_user_profile(self) -> bool:
        if not self.identity_token:
            return False
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{REMINI_API_BASE_URL}/users/@me", headers=self._get_common_headers())
                response.raise_for_status()
            user_data = response.json()
            log.info(f"User profile activated. Balance: {user_data.get('balance', 'N/A')}")
            return True
        except httpx.HTTPStatusError:
            return False

    async def _upload_file_to_gcs(self, upload_url: str, file_path: str, additional_headers: Dict[str, str]):
        try:
            with open(file_path, "rb") as f:
                file_content = f.read()
            gcs_headers = additional_headers.copy()
            gcs_headers["Content-Length"] = str(len(file_content))
            gcs_headers["User-Agent"] = self._android_headers["user-agent"]
            async with httpx.AsyncClient() as client:
                response = await client.put(upload_url, headers=gcs_headers, content=file_content, timeout=120.0)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ReminiError(f"GCS upload failed: {e.response.status_code} - {e.response.text}") from e

    async def _create_image_task(self, file_path: str, feature_payload: Dict[str, Any]) -> str:
        mime_type = mimetypes.guess_type(file_path)[0] or "image/jpeg"
        request_body = {
            "image_content_type": mime_type,
            "image_md5": _calculate_md5_base64(file_path),
            "feature": feature_payload,
            "metadata": _get_image_metadata(file_path),
            "options": {"high_quality_output": False, "save_input": True},
        }
        try:
            headers = self._get_common_headers("application/json; charset=UTF-8")
            async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
                response = await client.post(f"{REMINI_API_BASE_URL}/tasks", json=request_body)
                response.raise_for_status()
            upload_info = response.json()
            task_id = upload_info.get("task_id")
            upload_url = upload_info.get("upload_url")
            upload_headers = upload_info.get("upload_headers")
            if not all([task_id, upload_url, upload_headers]):
                raise ReminiError(f"Missing required fields in task response: {upload_info}")
        except httpx.HTTPStatusError as e:
            raise ReminiError(f"Upload URL request failed: {e.response.status_code} - {e.response.text}") from e
        await self._upload_file_to_gcs(upload_url, file_path, upload_headers)
        return task_id

    async def _reprocess_image_task(self, base_task_id: str, feature_payload: Dict[str, Any]) -> str:
        """Sends a request to reprocess an existing task with a new feature."""
        try:
            headers = self._get_common_headers("application/json; charset=UTF-8")
            async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
                response = await client.post(f"{REMINI_API_BASE_URL}/tasks/{base_task_id}/reprocess", json={"feature": feature_payload})
                response.raise_for_status()
            data = response.json()
            new_task_id = data.get("task_id")
            if not new_task_id:
                raise ReminiError(f"Reprocessing did not return a new task ID: {data}")
            return new_task_id
        except httpx.HTTPStatusError as e:
            raise ReminiError(f"Reprocessing request failed: {e.response.status_code} - {e.response.text}") from e

    async def _ping_for_processing(self, task_id: str):
        try:
            headers = self._get_common_headers()
            headers["content-length"] = "0"
            async with httpx.AsyncClient(headers=headers) as client:
                response = await client.post(f"{REMINI_API_BASE_URL}/tasks/{task_id}/process")
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ReminiError(f"Processing ping failed: {e.response.status_code} - {e.response.text}") from e

    async def _poll_status_http(self, task_id: str) -> Optional[str]:
        """Polls for task completion and returns the output URL."""
        log.info(f"Polling for status of task {task_id}...")
        while True:
            await asyncio.sleep(5)
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{REMINI_API_BASE_URL}/tasks/{task_id}", headers=self._get_common_headers())
                if response.status_code == 404:
                    log.debug(f"Task {task_id} not found yet, continuing to poll...")
                    continue
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                raise ReminiError(f"HTTP polling failed: {e.response.status_code} - {e.response.text}") from e

            status = data.get("status")
            log.info(f"Task {task_id} status: {status}")
            if status == "completed":
                outputs = data.get("result", {}).get("outputs")
                if outputs and isinstance(outputs, list) and outputs[0].get("url"):
                    return outputs[0]["url"]
                return None # Completed but no URL
            elif status in ["failed", "error"]:
                raise ReminiError(f"Task failed during processing: {data.get('errors')}")

    async def _download_file(self, url: str, output_path: str):
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", url, headers={"user-agent": self._android_headers["user-agent"]}, timeout=120.0) as response:
                    response.raise_for_status()
                    with open(output_path, "wb") as f:
                        async for chunk in response.aiter_bytes():
                            f.write(chunk)
        except httpx.HTTPStatusError as e:
            raise ReminiError(f"Download failed: {e.response.status_code} - {e.response.text}") from e

    async def _process_common(self, image_path: str, output_path: Optional[str], verbose: bool, final_url: Optional[str]):
        """Common logic for processing and downloading."""
        if verbose and not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

        if not final_url:
            raise ReminiError("Processing failed, no final URL was generated.")

        if not output_path:
            name, ext = os.path.splitext(os.path.basename(image_path))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"{name}_remini_{timestamp}{ext}"

        log.info(f"Downloading enhanced image to: {output_path}")
        await self._download_file(final_url, output_path)
        log.info("Download finished successfully.")

    async def process(self, image_path: str, output_path: Optional[str] = None, verbose: bool = True):
        """Enhances an image with the default 'enhance' feature."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Input file not found: {image_path}")

        await self._login()

        log.info("Submitting image for standard enhancement...")
        feature = {"type": "enhance", "models": []}
        task_id = await self._create_image_task(image_path, feature)
        log.info(f"Image uploaded. Task ID: {task_id}")

        await self._ping_for_processing(task_id)
        final_url = await self._poll_status_http(task_id)

        await self._process_common(image_path, output_path, verbose, final_url)

    async def stylize(self, image_path: str, style: str, output_path: Optional[str] = None, verbose: bool = True):
        """Applies a stylization effect to an image (e.g., 'toon')."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Input file not found: {image_path}")

        await self._login()

        log.info("Step 1/4: Creating a base task for stylization...")
        base_feature = {"type": "enhance", "models": []}
        base_task_id = await self._create_image_task(image_path, base_feature)
        log.info(f"Base task created. Task ID: {base_task_id}")

        await self._ping_for_processing(base_task_id)
        base_task_url = await self._poll_status_http(base_task_id)
        if not base_task_url:
             raise ReminiError("Base task did not complete successfully. Cannot proceed with stylization.")
        log.info("Step 2/4: Base task completed.")

        log.info(f"Step 3/4: Reprocessing with '{style}' style...")
        style_feature = {"type": "stylization-v2", "pipelines": [{"id": style}]}
        reprocess_task_id = await self._reprocess_image_task(base_task_id, style_feature)
        log.info(f"Reprocessing started. New task ID: {reprocess_task_id}")

        log.info("Step 4/4: Waiting for stylization to complete...")
        final_url = await self._poll_status_http(reprocess_task_id)

        await self._process_common(image_path, output_path, verbose, final_url)
