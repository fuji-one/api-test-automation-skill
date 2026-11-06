from __future__ import annotations


def test_business_rules_detect_error_codes(facts):
    error_codes = {
        rule["error_code"]
        for api in facts["apis"]
        for rule in api["business_rules"]
        if rule["error_code"] != "UNKNOWN"
    }
    assert "ACCOUNT_EXISTS" in error_codes
    assert "ACCOUNT_NOT_FOUND" in error_codes
    assert "ACCOUNT_FROZEN" in error_codes
    assert "NEGATIVE_BALANCE" in error_codes


def test_business_rules_detect_param_validation(facts):
    rule_types = {rule["rule_type"] for api in facts["apis"] for rule in api["business_rules"]}
    assert "PARAM_VALIDATION" in rule_types
    assert "ERROR_CODE" in rule_types or "STATE_MACHINE" in rule_types
