from __future__ import annotations


def create_api(facts):
    return next(api for api in facts["apis"] if api["entry"]["method_name"] == "create")


def test_extract_contracts_detects_request_dto_fields(facts):
    api = create_api(facts)
    fields = {field["field_name"]: field for field in api["contract"]["request_fields"]}
    assert "userId" in fields
    assert fields["userId"]["field_type"] == "Long"
    assert fields["accountName"]["field_type"] == "String"


def test_extract_contracts_detects_validation_and_enum_values(facts):
    api = create_api(facts)
    fields = {field["field_name"]: field for field in api["contract"]["request_fields"]}
    assert "@NotNull" in fields["userId"]["validation_annotation"]
    assert fields["userId"]["required"] == "YES"
    assert "NORMAL" in fields["status"]["enum_values"]
    assert "FROZEN" in fields["status"]["enum_values"]
