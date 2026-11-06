"""Security regression tests use fake HTTP and isolated in-memory databases only."""
from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "components/api-test-framework-generator/assets/api-test-framework-template"


def load_file(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def runner():
    return load_file(ROOT / "scripts/run_live_request_evidence.py", "security_requester")


@pytest.fixture
def template(monkeypatch):
    monkeypatch.syspath_prepend(str(TEMPLATE))
    for key in list(sys.modules):
        if key == "core" or key.startswith("core."):
            monkeypatch.delitem(sys.modules, key)
    return lambda name: importlib.import_module("core." + name)


def execute_plan(runner, tmp_path, steps, **extra):
    plan = {"env": {"env_name": "test", "base_urls": {"demo": "https://example.test"}},
            "request_scope": {"mutating_requests_allowed": False}, "steps": steps, **extra}
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(plan), encoding="utf-8")
    output = tmp_path / "evidence"
    return runner.run(path, output, None), output


def step(**overrides):
    return {"case_id": "CASE-1", "step_id": "request", "module": "demo", "method": "POST",
            "path": "/items", "expected_status": 200, **overrides}


@pytest.mark.parametrize("path,name,ref", [
    ("/orders/verify", "verify order", "contract#order"),
    ("/authorizations/delete", "delete", "contract#authorization"),
    ("/items", "auth setup", "auth/token"),
    ("/admin/delete/login", "login", "contract#login"),
])
def test_keywords_never_grant_mutation_permission(runner, monkeypatch, tmp_path, path, name, ref):
    calls = []
    monkeypatch.setattr(runner, "request_json", lambda *args: calls.append(args))
    result, _ = execute_plan(runner, tmp_path, [step(path=path, name=name, source_contract_ref=ref)])
    assert result == 1
    assert calls == []


@pytest.mark.parametrize("changes", [
    {"expected_status": None, "cleanup_required": False, "cleanup_exemption_reason": "read-only contract"},
    {},
    {"cleanup": {"required": False}},
    {"cleanup": {"required": True, "ownership_key": "marker"}},
    {"request_decision": "unknown_requires_review", "method": "GET"},
])
def test_invalid_execution_plan_is_blocked_before_network(runner, monkeypatch, tmp_path, changes):
    calls = []
    monkeypatch.setattr(runner, "request_json", lambda *args: calls.append(args))
    result, _ = execute_plan(runner, tmp_path, [step(request_decision="request_allowed", **{k:v for k,v in changes.items() if k != "request_decision"})] if "request_decision" not in changes else [step(**changes)])
    assert result == 1
    assert not calls


def test_secret_aliases_are_redacted_in_all_evidence_outputs(runner, monkeypatch, tmp_path):
    secrets = {key: "sensitive-" + key for key in ("access_token", "refresh_token", "accessToken", "sessionSecret", "session_secret", "X-API-Key", "aes_key", "public_key", "id_token", "csrfToken")}
    monkeypatch.setattr(runner, "request_json", lambda *args: (200, {"data": secrets}))
    result, output = execute_plan(runner, tmp_path, [step(method="GET", extract={"session_key": "$.data.session_secret"}, assertions_ref="contract#response")])
    assert result == 0
    content = "\n".join(p.read_text(encoding="utf-8") for p in output.iterdir())
    assert all(value not in content for value in secrets.values())
    evidence = yaml.safe_load((output / "runtime_evidence.yaml").read_text(encoding="utf-8"))
    assert evidence["evidence_items"][0]["redacted"] is True


@pytest.mark.parametrize("request_fails", [False, True])
def test_planned_cleanup_runs_after_success_or_ambiguous_write(runner, monkeypatch, tmp_path, request_fails):
    state = set()
    calls = []
    def request(method, url, headers, body, timeout):
        calls.append(url)
        if url.endswith("/items"):
            state.add(body["marker"])
            if request_fails:
                raise TimeoutError("ambiguous response")
            return 200, {"data": {"id": 7}}
        if url.endswith("/cleanup"):
            state.discard(body["marker"])
            return 200, {"cleaned": True}
        return 200, {"remaining": len(state)}
    monkeypatch.setattr(runner, "request_json", request)
    cleanup = {"required": True, "ownership_key": "request.body.marker", "failure_path_ownership": "request.body.marker", "step_ids": ["cleanup"], "verification_step_ids": ["verify"]}
    steps = [step(request_decision="request_allowed", body={"marker": "this-run-only"}, cleanup=cleanup),
             step(step_id="cleanup", method="DELETE", path="/cleanup", request_decision="request_allowed", body={"marker": "this-run-only"}, cleanup_required=False, cleanup_exemption_reason="current-run cleanup action"),
             step(step_id="verify", method="GET", path="/verify", assertions_ref="contract#zero-residue", response_assertions={"$.remaining":0})]
    result, _ = execute_plan(runner, tmp_path, steps)
    assert result == 0
    assert not state
    assert len(calls) == 3


def sql_command(sql="DELETE FROM owned_records WHERE id=:record_id", **overrides):
    return {"sql": sql, "source_refs": ["contract#cleanup"], "target_tables": ["owned_records"],
            "cleanup_identity": {"field": "id"}, "ownership": {"keys": ["id"]},
            "params": {"record_id": 1, "tenant": 10}, "expected_effect": {"affected_rows": 1}, **overrides}


@pytest.mark.parametrize("sql", [
    "DELETE FROM owned_records WHERE tenant_id=:tenant",
    "DELETE FROM owned_records WHERE id=:record_id OR tenant_id=:tenant",
    "DELETE FROM owned_records WHERE id<>:record_id",
    "DELETE FROM owned_records WHERE id=:record_id OR TRUE",
    "DELETE FROM owned_records WHERE EXISTS (SELECT 1 FROM other WHERE id=:record_id)",
    "DELETE FROM owned_records WHERE tenant_id=:tenant /* id=:record_id */",
])
def test_broad_cleanup_sql_never_reaches_database(template, sql):
    executor = template("sql_executor")
    command = sql_command(sql)
    with pytest.raises(ValueError):
        executor.SqlSafetyValidator.validate_command("CASE", "SQL 后置清理", command, command["params"])


def test_exact_cleanup_preserves_unrelated_rows(template):
    from sqlalchemy import create_engine, text
    module = template("sql_executor")
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE owned_records(id INTEGER PRIMARY KEY, tenant_id INTEGER)"))
        connection.execute(text("INSERT INTO owned_records VALUES (1,10),(2,10),(3,20)"))
    module.SqlExecutor(engine, {}).cleanup("CASE", [sql_command()])
    with engine.connect() as connection:
        assert connection.execute(text("SELECT id FROM owned_records ORDER BY id")).scalars().all() == [2,3]
    engine.dispose()


def test_excessive_rowcount_rolls_back_mutation(template):
    from sqlalchemy import create_engine, text
    module = template("sql_executor")
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE owned_records(id INTEGER, value INTEGER)"))
        connection.execute(text("INSERT INTO owned_records VALUES (1,0),(1,0)"))
    command = sql_command("UPDATE owned_records SET value=1 WHERE id=:record_id", expected_effect={"affected_rows_min":1,"affected_rows_max":1})
    with pytest.raises(AssertionError, match="上限"):
        module.SqlExecutor(engine, {}).cleanup("CASE", [command])
    with engine.connect() as connection:
        assert connection.execute(text("SELECT value FROM owned_records")).scalars().all() == [0,0]
    engine.dispose()


def test_unbounded_minimum_rowcount_is_rejected(template):
    module = template("sql_executor")
    command = sql_command(expected_effect={"affected_rows_min":1})
    with pytest.raises(ValueError, match="上限"):
        module.SqlSafetyValidator.validate_command("CASE", "SQL 后置清理", command, command["params"])


def test_cleanup_failure_blocks_downstream_release(runner, monkeypatch, tmp_path):
    def request(method, url, headers, body, timeout):
        if url.endswith("/cleanup"):
            raise TimeoutError("cleanup unavailable")
        return 200, {"data":{"id":7},"remaining":1}
    monkeypatch.setattr(runner, "request_json", request)
    cleanup = {"required":True,"ownership_key":"request.body.marker","failure_path_ownership":"request.body.marker","step_ids":["cleanup"],"verification_step_ids":["verify"]}
    steps = [step(request_decision="request_allowed",body={"marker":"this-run"},cleanup=cleanup),
             step(step_id="cleanup",method="DELETE",path="/cleanup",request_decision="request_allowed",cleanup_required=False,cleanup_exemption_reason="cleanup action"),
             step(step_id="verify",method="GET",path="/verify",assertions_ref="contract#zero-residue",response_assertions={"$.remaining":0})]
    result, output = execute_plan(runner,tmp_path,steps)
    assert result == 1
    status = yaml.safe_load((output/"runtime_stage_status.yaml").read_text(encoding="utf-8"))
    evidence = yaml.safe_load((output/"runtime_evidence.yaml").read_text(encoding="utf-8"))
    assert status["next_stage_allowed"] is False
    assert all(item["script_materialization_ready"] is False for item in evidence["evidence_items"])


def test_composite_ownership_and_parameter_aliases_remain_supported(template):
    module = template("sql_executor")
    command = sql_command("DELETE FROM owned_records WHERE id=:record_id AND tenant_id=:tenant AND (status='A' OR status='B')",ownership={"keys":["id","tenant_id"]})
    module.SqlSafetyValidator.validate_command("CASE","SQL 后置清理",command,command["params"])


def test_client_diagnostics_redact_raw_response_and_exceptions(template, monkeypatch):
    from requests import Response
    module = template("client")
    client = module.HttpClient("https://example.test",10)
    client.set_auth_context({"enabled":False,"session_secret":"a-known-session-secret"})
    response=Response();response.status_code=500
    response._content=b'{"session_secret":"a-known-session-secret","access_token":"a-raw-access-token"}'
    assert "a-known-session-secret" not in client._redact_response_text(response)
    assert "a-raw-access-token" not in client._redact_response_text(response)
    attachments=[]
    monkeypatch.setattr(module.allure,"attach",lambda body,**kwargs:attachments.append(body))
    client._attach_transport_decode_failure("POST","/items?token=a-query-token",response,ValueError("bad data a-known-session-secret"))
    assert "a-known-session-secret" not in "".join(attachments)
    assert "a-query-token" not in "".join(attachments)
    client.session.close()


def test_shared_redaction_preserves_extract_rules_and_masks_embedded_json(template):
    module = template("security_redaction")
    assert module.redact({"extract":{"auth_token":"$.data.token"}})["extract"]["auth_token"] == "$.data.token"
    assert "sensitive-value" not in module.redact('failure: password="sensitive-value"')
    assert "sensitive-value" not in module.redact(json.dumps({"session_secret":"sensitive-value"}))


def test_cipher_preserves_wire_format_without_subprocess(template, monkeypatch):
    import subprocess
    module = template("transport_crypto")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: pytest.fail("crypto must remain in process"))
    codec = module.AesDataEnvelopeCodec(module.TransportEncryptionPolicy({"public_key":"0123456789abcdef0123456789abcdef"}))
    plaintext = '{"message":"中文","value":1}'
    encoded = codec._openssl_aes_256_ecb(plaintext, "0123456789abcdef0123456789abcdef", False)
    # Independent .NET AES/ECB/PKCS7 vector, rather than a round-trip alone.
    assert encoded == "2uhXI/VY9UXMO7bzM9RdzM4ejtBiR/QTdlH4NJSMaWo="
    assert codec._openssl_aes_256_ecb(encoded, "0123456789abcdef0123456789abcdef", True) == plaintext
    with pytest.raises(ValueError, match="输入或密钥"):
        codec._openssl_aes_256_ecb("invalid ciphertext", "0123456789abcdef0123456789abcdef", True)
