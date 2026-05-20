from bosgenesis_k8s_inspector_mcp.config import AppConfig, PROJECT_ROOT, load_yaml_file, resolve_config_path


def test_load_yaml_file_resolves_default_config_from_any_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    policy = load_yaml_file("config/policy.yaml")

    assert "pods" in policy["allowed_read_resources"]


def test_missing_container_config_path_falls_back_to_local_config():
    config_path = resolve_config_path("/app/config/policy.yaml")

    assert config_path.name == "policy.yaml"
    assert config_path.exists()


def test_k8s_auth_mode_supports_local_alias(monkeypatch):
    monkeypatch.setenv("K8S_AUTH_MODE", "kubeconfig")

    assert AppConfig().k8s_auth_mode == "kubeconfig"


def test_kubeconfig_supports_local_alias_and_repo_relative_paths(monkeypatch):
    monkeypatch.chdir(PROJECT_ROOT.parent)
    monkeypatch.setenv("KUBECONFIG", "./kube/config")

    assert AppConfig().kubeconfig_path == str(PROJECT_ROOT / "kube" / "config")
