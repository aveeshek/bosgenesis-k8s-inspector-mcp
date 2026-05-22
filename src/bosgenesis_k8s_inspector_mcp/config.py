from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvSettings(BaseSettings):
    """Environment-driven settings.

    Keep secrets and environment-specific values outside source code.
    This class is intentionally easy to replace with Vault-backed loading later.
    """

    model_config = SettingsConfigDict(env_prefix="BOSGENESIS_", env_file=".env", extra="ignore")

    run_mode: str = Field(default="api")
    allowed_namespace: str = Field(default="bosgenesis")
    k8s_auth_mode: str = Field(default="in_cluster")
    kubeconfig_path: str = Field(default="/config/kubeconfig")
    kubeconfig_context: str | None = Field(default=None)
    settings_file: str = Field(default="config/settings.yaml")
    policy_file: str = Field(default="config/policy.yaml")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8080)
    api_key: str | None = Field(default=None)
    mcp_allowed_hosts: str = Field(
        default=(
            "localhost,127.0.0.1,k8s-inspector.bosgenesis.local,"
            "bosgenesis-k8s-inspector-mcp,"
            "bosgenesis-k8s-inspector-mcp.bosgenesis.svc,"
            "bosgenesis-k8s-inspector-mcp.bosgenesis.svc.cluster.local"
        )
    )
    audit_log_file: str = Field(default="/tmp/bosgenesis-k8s-inspector-audit.jsonl")
    otel_enabled: bool = Field(default=True)
    otel_service_name: str = Field(default="bosgenesis-k8s-inspector-mcp")
    otel_exporter_otlp_endpoint: str = Field(default="http://signoz-otel-collector.signoz:4317")
    otel_exporter_otlp_insecure: bool = Field(default=True)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_config_path(path: str | Path) -> Path:
    p = Path(path)
    if p.exists():
        return p
    parts = p.parts
    if "config" in parts:
        config_index = parts.index("config")
        local_config_path = PROJECT_ROOT.joinpath(*parts[config_index:])
        if local_config_path.exists():
            return local_config_path
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p


def load_yaml_file(path: str | Path) -> dict[str, Any]:
    p = resolve_config_path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_env_aliases(path: str | Path = ".env") -> dict[str, str]:
    p = resolve_config_path(path)
    if not p.exists():
        return {}

    aliases: dict[str, str] = {}
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            aliases[key.strip()] = value.strip().strip('"').strip("'")
    return aliases


def resolve_runtime_path(path: str | Path) -> str:
    p = Path(path)
    if p.exists():
        return str(p)
    if p.is_absolute():
        return str(p)
    return str(PROJECT_ROOT / p)


class AppConfig:
    def __init__(self) -> None:
        self.env = EnvSettings()
        self.env_aliases = load_env_aliases()
        self.settings = load_yaml_file(self.env.settings_file)
        self.policy = load_yaml_file(self.env.policy_file)

    @property
    def namespace(self) -> str:
        return str(
            self.env.allowed_namespace
            or self.settings.get("kubernetes", {}).get("allowed_namespace")
            or self.policy.get("namespace_boundary", {}).get("allowed_namespace")
            or "bosgenesis"
        )

    @property
    def require_api_key(self) -> bool:
        return bool(self.settings.get("api", {}).get("require_api_key", True))

    @property
    def k8s_auth_mode(self) -> str:
        return str(
            os.getenv("BOSGENESIS_K8S_AUTH_MODE")
            or os.getenv("K8S_AUTH_MODE")
            or self.env_aliases.get("K8S_AUTH_MODE")
            or self.env.k8s_auth_mode
            or self.settings.get("kubernetes", {}).get("auth_mode")
            or "in_cluster"
        )

    @property
    def kubeconfig_path(self) -> str:
        path = (
            os.getenv("BOSGENESIS_KUBECONFIG_PATH")
            or os.getenv("KUBECONFIG")
            or self.env_aliases.get("KUBECONFIG")
            or self.env.kubeconfig_path
            or self.settings.get("kubernetes", {}).get("kubeconfig_path")
            or "/config/kubeconfig"
        )
        return resolve_runtime_path(path)

    @property
    def kubeconfig_context(self) -> str | None:
        return (
            os.getenv("K8S_CONTEXT")
            or self.env_aliases.get("K8S_CONTEXT")
            or self.env.kubeconfig_context
            or self.settings.get("kubernetes", {}).get("kubeconfig_context")
            or None
        )

    @property
    def mcp_allowed_hosts(self) -> list[str]:
        raw = self.env.mcp_allowed_hosts
        return [host.strip() for host in raw.split(",") if host.strip()]


config = AppConfig()
