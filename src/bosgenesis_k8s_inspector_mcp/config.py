from __future__ import annotations

import os
import re
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
    allowed_namespaces: str | None = Field(default=None)
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
        self._runtime_namespace: str | None = None

    @property
    def namespace(self) -> str:
        return self._runtime_namespace or str(
            self.env.allowed_namespace
            or self.settings.get("kubernetes", {}).get("allowed_namespace")
            or self.policy.get("namespace_boundary", {}).get("allowed_namespace")
            or "bosgenesis"
        )

    @property
    def allowed_namespaces(self) -> list[str]:
        values: list[str] = []
        raw_env = os.getenv("BOSGENESIS_ALLOWED_NAMESPACES") or self.env.allowed_namespaces
        if raw_env:
            values.extend(_split_csv(raw_env))
        values.extend(_as_list(self.settings.get("kubernetes", {}).get("allowed_namespaces")))
        boundary = self.policy.get("namespace_boundary", {})
        values.extend(_as_list(boundary.get("allowed_namespaces")))
        if not values:
            single_values = [
                self.env.allowed_namespace,
                self.settings.get("kubernetes", {}).get("allowed_namespace"),
                boundary.get("allowed_namespace"),
                "bosgenesis",
            ]
            values.extend(str(value).strip() for value in single_values if value)
        deduped = []
        for value in values:
            namespace = self.validate_namespace_name(value)
            if namespace not in deduped:
                deduped.append(namespace)
        return deduped

    @property
    def configured_namespace(self) -> str:
        return str(
            self.env.allowed_namespace
            or self.settings.get("kubernetes", {}).get("allowed_namespace")
            or self.policy.get("namespace_boundary", {}).get("allowed_namespace")
            or "bosgenesis"
        )

    @property
    def namespace_access(self) -> dict[str, str]:
        access: dict[str, str] = {}
        access.update(_as_dict(self.settings.get("kubernetes", {}).get("namespace_access")))
        access.update(_as_dict(self.policy.get("namespace_boundary", {}).get("namespace_access")))
        return {self.validate_namespace_name(key): str(value) for key, value in access.items()}

    def namespace_access_mode(self, namespace: str) -> str:
        return self.namespace_access.get(namespace, "read_write")

    def set_runtime_namespace(self, namespace: str) -> str:
        namespace = self.assert_allowed_namespace(namespace)
        self._runtime_namespace = namespace
        return namespace

    def assert_allowed_namespace(self, namespace: str | None) -> str:
        namespace = self.validate_namespace_name(namespace)
        allowed = self.allowed_namespaces
        if namespace not in allowed:
            allowed_text = ", ".join(allowed)
            raise ValueError(
                f"namespace '{namespace}' is not allowed. Allowed namespaces: {allowed_text}"
            )
        return namespace

    @staticmethod
    def validate_namespace_name(namespace: str | None) -> str:
        namespace = str(namespace or "").strip()
        if not re.fullmatch(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?", namespace):
            raise ValueError("namespace must be a Kubernetes RFC1123 label")
        if len(namespace) > 63:
            raise ValueError("namespace must be 63 characters or fewer")
        return namespace

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


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _split_csv(value)
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _as_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key).strip(): str(item).strip() for key, item in value.items() if str(key).strip()}
