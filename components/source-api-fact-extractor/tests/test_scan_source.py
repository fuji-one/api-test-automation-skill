from __future__ import annotations


def test_scan_source_detects_http_api_count(facts):
    assert facts["summary"]["api_count"] == 3
    assert facts["summary"]["http_api_count"] == 3


def test_scan_source_outputs_unknowns(facts):
    assert facts["summary"]["unknown_count"] > 0
    project_unknown_types = {unknown["unknown_type"] for unknown in facts.get("project_unknowns", [])}
    assert "AUTH_HINT_GLOBAL" in project_unknown_types
    api_unknown_types = {unknown["unknown_type"] for api in facts["apis"] for unknown in api["unknowns"]}
    assert "AUTH_HINT" not in api_unknown_types


def test_scan_source_skips_agent_fixture_dirs(tmp_path):
    from scan_source import scan

    write_controller(
        tmp_path / "service" / "src" / "main" / "java" / "com" / "example" / "LiveController.java",
        "LiveController",
        "/api/live",
    )
    write_controller(
        tmp_path
        / ".agents"
        / "skills"
        / "source-api-fact-extractor"
        / "examples"
        / "sample-java-project"
        / "src"
        / "main"
        / "java"
        / "com"
        / "example"
        / "FixtureController.java",
        "FixtureController",
        "/api/fixture",
    )

    facts = scan(tmp_path, tmp_path / "out")
    paths = {api["entry"]["path"] for api in facts["apis"]}

    assert "/api/live" in paths
    assert "/api/fixture" not in paths


def test_scan_source_marks_no_param_request_as_none(tmp_path):
    from scan_source import scan

    write_controller(
        tmp_path / "service" / "src" / "main" / "java" / "com" / "example" / "NoParamController.java",
        "NoParamController",
        "/api/no-param",
    )

    facts = scan(tmp_path, tmp_path / "out")
    api = next(item for item in facts["apis"] if item["entry"]["path"] == "/api/no-param")
    api_unknown_types = {unknown["unknown_type"] for unknown in api["unknowns"]}

    assert api["entry"]["request_type"] == "NONE"
    assert "REQUEST_TYPE" not in api_unknown_types


def test_scan_source_does_not_mark_map_body_as_missing_dto(tmp_path):
    from scan_source import scan

    write_file(
        tmp_path / "service" / "src" / "main" / "java" / "com" / "example" / "MapBodyController.java",
        """
package com.example;

import java.util.Map;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class MapBodyController {
    @PostMapping("/api/map-body")
    public String callback(@RequestBody Map<String, Object> body) {
        return String.valueOf(body.get("userId"));
    }
}
""",
    )

    facts = scan(tmp_path, tmp_path / "out")
    api = next(item for item in facts["apis"] if item["entry"]["path"] == "/api/map-body")
    descriptions = [unknown["description"] for unknown in api["unknowns"]]

    assert api["entry"]["request_type"] == "Map<String, Object>"
    assert not any("Map<String" in item or "Object" in item for item in descriptions)


def test_scan_source_preserves_evidence_line_numbers_after_block_comments(tmp_path):
    from scan_source import scan

    write_file(
        tmp_path / "service" / "src" / "main" / "java" / "com" / "example" / "CommentedController.java",
        """
package com.example;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * A long class comment.
 *
 * It must not shift evidence line numbers.
 */
@RestController
public class CommentedController {

    /**
     * A long method comment.
     *
     * It must not shift evidence line numbers.
     */
    @PostMapping("/api/commented")
    public String create() {
        return "ok";
    }
}
""",
    )

    facts = scan(tmp_path, tmp_path / "out")
    api = next(item for item in facts["apis"] if item["entry"]["path"] == "/api/commented")
    evidence = api["entry"]["source_evidence"]
    line_no = int(evidence.split(":", 1)[1].split(" ", 1)[0])
    source_line = (tmp_path / "service" / "src" / "main" / "java" / "com" / "example" / "CommentedController.java").read_text(
        encoding="utf-8"
    ).splitlines()[line_no - 1]

    assert "public String create()" in source_line


def test_scan_source_marks_framework_injected_param_as_not_applicable(tmp_path):
    from scan_source import scan

    write_file(
        tmp_path / "service" / "src" / "main" / "java" / "com" / "example" / "LocaleController.java",
        """
package com.example;

import java.util.Locale;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class LocaleController {
    @GetMapping("/api/locale")
    public String current(Locale locale) {
        return locale.toLanguageTag();
    }
}
""",
    )

    facts = scan(tmp_path, tmp_path / "out")
    api = next(item for item in facts["apis"] if item["entry"]["path"] == "/api/locale")
    param = api["contract"]["request_parameters"][0]

    assert api["entry"]["request_type"] == "NONE"
    assert param["source"] == "N/A"
    assert api["contract"]["request_fields"] == []
    assert not any(unknown["unknown_type"] == "REQUEST_BINDING_SOURCE" for unknown in api["unknowns"])


def test_scan_source_adds_unknown_for_unannotated_business_param(tmp_path):
    from scan_source import scan

    write_file(
        tmp_path / "service" / "src" / "main" / "java" / "com" / "example" / "PlainParamController.java",
        """
package com.example;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class PlainParamController {
    @PostMapping("/api/plain-param")
    public String submit(PlainReq req) {
        return req.name;
    }
}
""",
    )
    write_file(
        tmp_path / "service" / "src" / "main" / "java" / "com" / "example" / "PlainReq.java",
        """
package com.example;

public class PlainReq {
    public String name;
}
""",
    )

    facts = scan(tmp_path, tmp_path / "out")
    api = next(item for item in facts["apis"] if item["entry"]["path"] == "/api/plain-param")
    unknown_types = {unknown["unknown_type"] for unknown in api["unknowns"]}

    assert api["entry"]["request_type"] == "PlainReq"
    assert "REQUEST_BINDING_SOURCE" in unknown_types


def write_controller(path, class_name: str, route: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
package com.example;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class {class_name} {{
    @GetMapping("{route}")
    public String get() {{
        return "ok";
    }}
}}
""".lstrip(),
        encoding="utf-8",
    )


def write_file(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip(), encoding="utf-8")
