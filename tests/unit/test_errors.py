from tenderlens.core.errors import error_payload


def test_error_payload_has_stable_shape() -> None:
    payload = error_payload(code="invalid_document", message="Invalid document.")

    assert payload == {
        "error": {
            "code": "invalid_document",
            "message": "Invalid document.",
            "details": {},
        }
    }
