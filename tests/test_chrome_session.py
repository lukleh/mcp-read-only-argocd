from types import SimpleNamespace

import mcp_read_only_argocd.chrome_session as chrome_session


def test_extract_connection_domain_from_url():
    assert (
        chrome_session.extract_connection_domain("https://argocd.example.com/apps")
        == "argocd.example.com"
    )


def test_extract_connection_domain_from_host_value():
    assert (
        chrome_session.extract_connection_domain("argocd.example.com:443/apps")
        == "argocd.example.com"
    )


def test_load_session_token_from_chrome_prefers_exact_domain(monkeypatch):
    cookies = [
        SimpleNamespace(
            name=chrome_session.ARGOCD_SESSION_COOKIE,
            domain=".example.com",
            value="parent-token",
        ),
        SimpleNamespace(
            name=chrome_session.ARGOCD_SESSION_COOKIE,
            domain=".argocd.example.com",
            value="exact-token",
        ),
    ]

    monkeypatch.setattr(chrome_session, "_profile_cookie_file", lambda: None)
    monkeypatch.setattr(chrome_session, "_load_chrome_cookie_jar", lambda _: cookies)

    assert (
        chrome_session.load_session_token_from_chrome("https://argocd.example.com")
        == "exact-token"
    )


def test_load_session_token_from_chrome_ignores_non_session_argocd_cookies(
    monkeypatch,
):
    cookies = [
        SimpleNamespace(
            name="argocd.token_expiry",
            domain=".argocd.example.com",
            value="not-a-session-token",
        )
    ]

    monkeypatch.setattr(chrome_session, "_profile_cookie_file", lambda: None)
    monkeypatch.setattr(chrome_session, "_load_chrome_cookie_jar", lambda _: cookies)

    assert (
        chrome_session.load_session_token_from_chrome("https://argocd.example.com")
        is None
    )
