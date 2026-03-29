"""Tests for NDJSON parsing in Argo CD log responses."""

import httpx

from mcp_read_only_argocd.argocd_connector import ArgoCDConnector
from mcp_read_only_argocd.config import ArgoCDConnection


def test_handle_response_parses_ndjson():
    conn = ArgoCDConnection(
        connection_name="test",
        url="https://argocd.example.com",
        session_token="dummy",
    )
    connector = ArgoCDConnector(conn)

    mock_response = httpx.Response(
        status_code=200,
        headers={"content-type": "application/x-ndjson"},
        content=b'{"content":"line1"}\n{"content":"line2"}\n',
    )

    parsed = connector._handle_response(mock_response)

    assert parsed["items"][0]["content"] == "line1"
    assert parsed["items"][1]["content"] == "line2"
    assert parsed["lines"] == ["line1", "line2"]
