from __future__ import annotations


def test_extract_java_api_detects_paths_and_methods(facts):
    entries = {(api["entry"]["http_method"], api["entry"]["path"]) for api in facts["apis"]}
    assert ("POST", "/api/accounts") in entries
    assert ("GET", "/api/accounts/{accountId}") in entries
    assert ("GET", "/api/users/{userId}/profile") in entries


def test_extract_java_api_detects_controller_names(facts):
    classes = {api["entry"]["class_name"] for api in facts["apis"]}
    assert "AccountController" in classes
    assert "UserController" in classes


def test_extract_java_api_does_not_parse_return_call_as_method(tmp_path):
    from extract_java_api import SourceFile, parse_java_class

    path = tmp_path / "VerifyService.java"
    source = SourceFile(
        path=path,
        rel_path="src/main/java/com/example/VerifyService.java",
        text="""
package com.example;

public class VerifyService {
    public Boolean verify(VerifyReq req) {
        return verify(req.getOrderId(), req.getToken());
    }

    public Boolean retry(Order order, Extra extra) {
        // Refresh retry timestamp before the next check.
        saveOrUpdate(order.getId(), order.getNo(), extra.getToken(), extra.getPackageName());
        return true;
    }

    private Boolean verify(Long orderId, String token) {
        return true;
    }

    private void saveOrUpdate(Long orderId, String orderNo, String token, String packageName) {
    }
}
""".lstrip(),
    )

    java_class = parse_java_class(source)
    assert java_class is not None
    verify_params = [method.params for method in java_class.methods if method.name == "verify"]

    assert "VerifyReq req" in verify_params
    assert "Long orderId, String token" in verify_params
    assert "req.getOrderId(), req.getToken()" not in verify_params

    save_params = [method.params for method in java_class.methods if method.name == "saveOrUpdate"]
    assert save_params == ["Long orderId, String orderNo, String token, String packageName"]
