from bosgenesis_k8s_inspector_mcp.audit import AuditLogger


def test_audit_emit_allows_resource_name(tmp_path, monkeypatch):
    monkeypatch.setattr("bosgenesis_k8s_inspector_mcp.audit.config.env.audit_log_file", str(tmp_path / "audit.jsonl"))
    audit_logger = AuditLogger()

    event = audit_logger.emit(
        action="get",
        resource="pods",
        namespace="bosgenesis",
        name="example-pod",
        status="success",
    )

    assert event["name"] == "example-pod"
    assert (tmp_path / "audit.jsonl").exists()


def test_audit_emit_includes_signoz_fields(tmp_path, monkeypatch):
    monkeypatch.setattr("bosgenesis_k8s_inspector_mcp.audit.config.env.audit_log_file", str(tmp_path / "audit.jsonl"))
    audit_logger = AuditLogger()

    event = audit_logger.emit(
        action="apply",
        resource="configmaps",
        namespace="bosgenesis",
        name="codex-mcp-test",
        status="success",
        actor="codex",
        request={"kind": "ConfigMap", "dry_run": True},
        tool="k8s_apply_manifest",
        decision="allowed",
    )

    assert event["actor"] == "codex"
    assert event["tool"] == "k8s_apply_manifest"
    assert event["operation"] == "apply"
    assert event["namespace"] == "bosgenesis"
    assert event["resource_kind"] == "ConfigMap"
    assert event["resource_name"] == "codex-mcp-test"
    assert event["dry_run"] is True
    assert event["decision"] == "allowed"
    assert event["status"] == "success"
    assert event["reason"] is None
    assert event["correlation_id"]
