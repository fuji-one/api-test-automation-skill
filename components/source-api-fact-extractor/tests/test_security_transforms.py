from __future__ import annotations

import json


def test_security_transforms_extract_api_rules_and_secret_reference(tmp_path):
    from extract_call_chain import build_call_chains
    from extract_java_api import SourceFile, build_api_inventory, parse_java_files
    from extract_security_transforms import build_security_transforms
    from render_docs import render_all

    files = [
        SourceFile(
            path=tmp_path / "src/main/java/com/example/AuthController.java",
            rel_path="src/main/java/com/example/AuthController.java",
            text="""
package com.example;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class AuthController {
    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    @PostMapping("/login")
    public String login(LoginReq req) {
        String token = authService.login(req);
        return token;
    }
}
""".lstrip(),
        ),
        SourceFile(
            path=tmp_path / "src/main/java/com/example/AuthService.java",
            rel_path="src/main/java/com/example/AuthService.java",
            text="""
package com.example;

public class AuthService {
    private final RedisTokenPort redisTokenPort;

    public String login(LoginReq req) {
        String phoneEnc = CryptoUtils.encrypt(req.getPhone());
        String phoneHash = HashUtils.sha256(req.getPhone());
        String token = redisTokenPort.createToken(1L);
        return token;
    }
}
""".lstrip(),
        ),
        SourceFile(
            path=tmp_path / "src/main/resources/application.yml",
            rel_path="src/main/resources/application.yml",
            text="""
acme:
  crypto:
    aes-key: abcdefgh12345678
tencent:
  callbackSecret: callback-secret-value
spring:
  datasource:
    password: abc#def123
openai:
  max-tokens: 1000
""".lstrip(),
        ),
    ]
    classes = parse_java_files(files)
    inventory = build_api_inventory(classes)
    call_chains = build_call_chains(inventory, classes)
    bundle = build_security_transforms(inventory, classes, files, call_chains)
    api_id = inventory[0]["api_id"]
    transforms = bundle["api_transforms"][api_id]

    assert {item["transform_type"] for item in transforms} >= {"FIELD_ENCRYPT", "FIELD_HASH", "TOKEN_GENERATE"}
    encrypt_transform = next(item for item in transforms if item["transform_type"] == "FIELD_ENCRYPT")
    assert encrypt_transform["algorithm"] == "UNKNOWN"
    assert encrypt_transform["config_key"] == "UNKNOWN"
    assert any(ref["config_key"] == "acme.crypto.aes-key" for ref in bundle["secret_config_refs"])
    aes_ref = next(ref for ref in bundle["secret_config_refs"] if ref["config_key"] == "acme.crypto.aes-key")
    assert aes_ref["secret_ref"] == "config.acme.crypto.aes-key"
    assert "config_value" not in aes_ref
    assert aes_ref["config_value_masked"] != "abcdefgh12345678"
    password_ref = next(ref for ref in bundle["secret_config_refs"] if ref["config_key"] == "spring.datasource.password")
    assert password_ref["secret_ref"] == "config.spring.datasource.password"
    assert "config_value" not in password_ref
    assert all(ref["config_key"] != "openai.max-tokens" for ref in bundle["secret_config_refs"])

    facts = {
        "project": {"name": "sample", "scan_root": str(tmp_path), "generated_at": "now"},
        "project_unknowns": [],
        "project_security_transforms": bundle["project_transforms"],
        "secret_config_refs": bundle["secret_config_refs"],
        "apis": [
            {
                "api_id": api_id,
                "module": inventory[0]["module"],
                "entry": {
                    "entry_type": inventory[0]["entry_type"],
                    "class_name": inventory[0]["class_name"],
                    "method_name": inventory[0]["method_name"],
                    "http_method": inventory[0]["http_method"],
                    "path": inventory[0]["path"],
                    "rpc_interface": inventory[0]["rpc_interface"],
                    "request_type": inventory[0]["request_type"],
                    "response_type": inventory[0]["response_type"],
                    "auth_hint": inventory[0]["auth_hint"],
                    "source_evidence": inventory[0]["source_evidence"],
                },
                "contract": {
                    "response_wrapper": "UNKNOWN",
                    "response_body_type": "String",
                    "request_parameters": [],
                    "request_fields": [],
                    "response_fields": [],
                },
                "call_chain": call_chains[api_id],
                "business_rules": [],
                "db_side_effects": [],
                "security_transforms": transforms,
                "unknowns": [],
            }
        ],
        "summary": {
            "api_count": 1,
            "http_api_count": 1,
            "rpc_api_count": 0,
            "unknown_path_count": 0,
            "write_api_count": 0,
            "read_api_count": 0,
            "business_rule_count": 0,
            "security_transform_count": len(transforms),
            "secret_config_ref_count": len(bundle["secret_config_refs"]),
            "error_code_count": 0,
            "unknown_count": 0,
        },
    }
    render_all(facts, tmp_path / "out")
    source_facts = tmp_path / "out" / "docs" / "source-facts"
    rendered = (source_facts / "08-security-transform-facts.md").read_text(encoding="utf-8")
    json_data = json.loads((source_facts / "source-api-facts.json").read_text(encoding="utf-8"))

    assert "FIELD_ENCRYPT" in rendered
    assert "abcdefgh12345678" not in rendered
    assert "abcdefgh12345678" not in json.dumps(json_data, ensure_ascii=False)
    assert all("config_value" not in ref for ref in json_data["secret_config_refs"])
    assert all(ref["secret_ref"].startswith("config.") for ref in json_data["secret_config_refs"])
