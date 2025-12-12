import httpx
import json
import logging
from typing import Any, Dict, List, NoReturn
from urllib.parse import quote, unquote
from .config import ArgoCDConnection
from .exceptions import (
    AuthenticationError,
    ArgoCDAPIError,
    ArgoCDTimeoutError,
    PermissionDeniedError,
)

logger = logging.getLogger(__name__)


class ArgoCDConnector:
    """Async client for Argo CD API.

    Authentication:
        Uses browser session cookie (argocd.token) for authentication.
        Set ARGOCD_SESSION_<CONNECTION_NAME> environment variable with
        the cookie value from your browser.

    Credentials are reloaded from .env before each request to support
    token rotation without server restart.
    """

    def __init__(self, connection: ArgoCDConnection):
        self.connection = connection
        cookies = {"argocd.token": connection.session_token or ""}

        self.client = httpx.AsyncClient(
            base_url=str(connection.url),
            cookies=cookies,
            timeout=connection.timeout,
            verify=connection.verify_ssl,
            follow_redirects=True,
        )

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    def _refresh_credentials(self) -> None:
        """Refresh credentials from .env before making a request."""
        session_token = self.connection.reload_session_token()
        self.client.cookies.set("argocd.token", session_token)

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Process a successful response: check cookie refresh, parse JSON.

        Args:
            response: The httpx response object

        Returns:
            Parsed JSON response, or empty dict if no content
        """
        self._check_and_update_session_cookie(response)
        if response.content:
            try:
                return response.json()
            except json.JSONDecodeError as e:
                # Argo CD log endpoints can return NDJSON (newline-delimited JSON)
                # which triggers JSONDecodeError("Extra data") when parsed as a
                # single JSON document.
                if e.msg != "Extra data":
                    raise

                items = []
                for line in response.text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        items.append(json.loads(line))
                    except json.JSONDecodeError:
                        items.append({"line": line})

                lines: List[str] = []
                for item in items:
                    if not isinstance(item, dict):
                        continue

                    # Common shapes observed in log streaming endpoints.
                    result = item.get("result")
                    if isinstance(result, str):
                        lines.append(result)
                        continue
                    if isinstance(result, dict):
                        content = result.get("content")
                        if isinstance(content, str):
                            lines.append(content)
                            continue

                    content = item.get("content")
                    if isinstance(content, str):
                        lines.append(content)

                payload: Dict[str, Any] = {"items": items}
                if lines and len(lines) == len(items):
                    payload["lines"] = lines
                return payload
        return {}

    def _handle_http_error(self, e: httpx.HTTPStatusError, operation: str) -> NoReturn:
        """Convert HTTP errors to appropriate custom exceptions.

        This method always raises an exception and never returns normally.

        Args:
            e: The httpx HTTPStatusError
            operation: Description of the operation (e.g., "read", "write", "delete")

        Raises:
            AuthenticationError: For 401 responses
            PermissionDeniedError: For 403 responses
            ArgoCDAPIError: For other HTTP errors
        """
        if e.response.status_code == 401:
            # Attempt to capture any rotated cookie even on auth failures
            self._check_and_update_session_cookie(e.response)
            raise AuthenticationError(self.connection.connection_name)
        elif e.response.status_code == 403:
            raise PermissionDeniedError(self.connection.connection_name, operation)
        else:
            raise ArgoCDAPIError(
                e.response.status_code,
                e.response.text,
                self.connection.connection_name,
            )

    async def _get(self, endpoint: str, **params) -> Dict[str, Any]:
        """Execute a GET request to Argo CD API."""
        self._refresh_credentials()
        try:
            response = await self.client.get(f"/api/v1{endpoint}", params=params)
            response.raise_for_status()
            return self._handle_response(response)
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e, "read")
        except httpx.TimeoutException:
            raise ArgoCDTimeoutError(
                self.connection.timeout, self.connection.connection_name
            )

    def _check_and_update_session_cookie(self, response: httpx.Response) -> None:
        """
        Check response headers for refreshed session cookie and update if found.
        Argo CD may rotate session tokens via Set-Cookie headers.
        """
        if not self.connection.session_token:
            return

        # Look for Set-Cookie headers
        set_cookie_headers = response.headers.get_list("set-cookie")

        for cookie_header in set_cookie_headers:
            # Parse cookie header manually for argocd.token
            if "argocd.token=" in cookie_header:
                # Extract cookie value (format: argocd.token=VALUE; Path=/; ...)
                parts = cookie_header.split(";")
                for part in parts:
                    part = part.strip()
                    if part.startswith("argocd.token="):
                        new_token = part.split("=", 1)[1]
                        # URL decode if needed
                        new_token = unquote(new_token)

                        # Only update if it's different from current token
                        if new_token != self.connection.session_token:
                            logger.info(
                                f"Session token rotated for {self.connection.connection_name}. "
                                f"Old: {self.connection.session_token[:16]}... "
                                f"New: {new_token[:16]}..."
                            )

                            # Update in memory and persist to .env
                            self.connection.update_session_token(
                                new_token, persist=True
                            )

                            # Update httpx client cookies
                            self.client.cookies.set("argocd.token", new_token)

                        break

    # ==================== Applications API ====================

    async def list_applications(
        self,
        projects: List[str] | None = None,
        selector: str | None = None,
    ) -> List[Dict[str, Any]]:
        """List all applications.

        Args:
            projects: Optional list of project names to filter by
            selector: Optional label selector to filter applications

        Returns:
            List of application objects
        """
        params = {}
        if projects:
            params["projects"] = projects
        if selector:
            params["selector"] = selector

        result = await self._get("/applications", **params)
        return result.get("items", [])

    async def get_application(self, name: str) -> Dict[str, Any]:
        """Get application details by name.

        Args:
            name: Application name

        Returns:
            Application object with full details
        """
        return await self._get(f"/applications/{name}")

    async def get_application_resource_tree(self, name: str) -> Dict[str, Any]:
        """Get the resource tree for an application.

        Args:
            name: Application name

        Returns:
            Resource tree with all Kubernetes resources
        """
        return await self._get(f"/applications/{name}/resource-tree")

    async def get_application_managed_resources(
        self,
        name: str,
        group: str | None = None,
        kind: str | None = None,
        namespace: str | None = None,
        resource_name: str | None = None,
    ) -> Dict[str, Any]:
        """Get managed resources for an application.

        Args:
            name: Application name
            group: Optional API group to filter
            kind: Optional resource kind to filter
            namespace: Optional namespace to filter
            resource_name: Optional resource name to filter

        Returns:
            List of managed resources
        """
        params = {}
        if group:
            params["group"] = group
        if kind:
            params["kind"] = kind
        if namespace:
            params["namespace"] = namespace
        if resource_name:
            params["name"] = resource_name

        return await self._get(f"/applications/{name}/managed-resources", **params)

    async def get_application_logs(
        self,
        name: str,
        namespace: str | None = None,
        pod_name: str | None = None,
        container: str | None = None,
        tail_lines: int | None = None,
        since_seconds: int | None = None,
    ) -> Dict[str, Any]:
        """Get logs for an application's pods.

        Args:
            name: Application name
            namespace: Optional namespace
            pod_name: Optional pod name to get logs from
            container: Optional container name
            tail_lines: Number of lines from the end to return
            since_seconds: Return logs from last N seconds

        Returns:
            Log entries
        """
        params = {}
        if namespace:
            params["namespace"] = namespace
        if pod_name:
            params["podName"] = pod_name
        if container:
            params["container"] = container
        if tail_lines:
            params["tailLines"] = tail_lines
        if since_seconds:
            params["sinceSeconds"] = since_seconds

        return await self._get(f"/applications/{name}/logs", **params)

    # ==================== Projects API ====================

    async def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects.

        Returns:
            List of project objects
        """
        result = await self._get("/projects")
        return result.get("items", [])

    async def get_project(self, name: str) -> Dict[str, Any]:
        """Get project details by name.

        Args:
            name: Project name

        Returns:
            Project object with full details
        """
        return await self._get(f"/projects/{name}")

    # ==================== Clusters API ====================

    async def list_clusters(self) -> List[Dict[str, Any]]:
        """List all registered clusters.

        Returns:
            List of cluster objects
        """
        result = await self._get("/clusters")
        return result.get("items", [])

    async def get_cluster(self, server: str) -> Dict[str, Any]:
        """Get cluster details by server URL.

        Args:
            server: Cluster server URL (will be URL-encoded)

        Returns:
            Cluster object with full details
        """
        encoded_server = quote(server, safe="")
        return await self._get(f"/clusters/{encoded_server}")

    # ==================== Repositories API ====================

    async def list_repositories(self) -> List[Dict[str, Any]]:
        """List all configured repositories.

        Returns:
            List of repository objects
        """
        result = await self._get("/repositories")
        return result.get("items", [])

    async def get_repository(self, repo: str) -> Dict[str, Any]:
        """Get repository details by URL.

        Args:
            repo: Repository URL (will be URL-encoded)

        Returns:
            Repository object with full details
        """
        encoded_repo = quote(repo, safe="")
        return await self._get(f"/repositories/{encoded_repo}")

    # ==================== Settings/Version API ====================

    async def get_settings(self) -> Dict[str, Any]:
        """Get Argo CD settings.

        Returns:
            Settings object
        """
        return await self._get("/settings")

    async def get_version(self) -> Dict[str, Any]:
        """Get Argo CD version information.

        Returns:
            Version information
        """
        # Version endpoint doesn't have /v1 prefix
        self._refresh_credentials()
        try:
            response = await self.client.get("/api/version")
            response.raise_for_status()
            return self._handle_response(response)
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e, "read")
        except httpx.TimeoutException:
            raise ArgoCDTimeoutError(
                self.connection.timeout, self.connection.connection_name
            )
