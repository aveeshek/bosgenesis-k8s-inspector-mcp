from bosgenesis_k8s_inspector_mcp.k8s_client import auth_diagnostics
from bosgenesis_k8s_inspector_mcp.k8s_client import _client_bearer_auth_configured
from bosgenesis_k8s_inspector_mcp.k8s_client import _client_authorization_header_configured
from bosgenesis_k8s_inspector_mcp.k8s_client import _load_direct_incluster_client


def test_auth_diagnostics_does_not_expose_token_value():
    diagnostics = auth_diagnostics()

    assert "auth_mode" in diagnostics
    assert "serviceaccount_token_readable" in diagnostics
    assert "token" not in diagnostics


def test_direct_incluster_client_configures_bearer_token(monkeypatch, tmp_path):
    token_path = tmp_path / "token"
    ca_path = tmp_path / "ca.crt"
    token_path.write_text("unit-token", encoding="utf-8")
    ca_path.write_text("unit-ca", encoding="utf-8")
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.96.0.1")
    monkeypatch.setenv("KUBERNETES_SERVICE_PORT", "443")
    monkeypatch.setattr(
        "bosgenesis_k8s_inspector_mcp.k8s_client.SERVICEACCOUNT_TOKEN_PATH", token_path
    )
    monkeypatch.setattr(
        "bosgenesis_k8s_inspector_mcp.k8s_client.SERVICEACCOUNT_CA_PATH", ca_path
    )

    api_client = _load_direct_incluster_client()
    auth_settings = api_client.configuration.auth_settings()

    assert auth_settings["BearerToken"]["key"] == "authorization"
    assert auth_settings["BearerToken"]["value"] == "Bearer unit-token"
    assert api_client.default_headers["Authorization"] == "Bearer unit-token"
    assert _client_bearer_auth_configured() is False
    assert _client_authorization_header_configured() is False
