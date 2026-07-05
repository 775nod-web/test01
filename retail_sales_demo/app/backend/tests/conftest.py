import pytest

from backend import access_control, audit


@pytest.fixture(autouse=True)
def no_live_dependencies(monkeypatch):
    """Every test runs with no live Databricks connection. Default identity is
    an "admin" context (sees all stores, can view PII) so existing tests that
    don't care about access control keep working; tests that DO care override
    access_control.get_access_context again within the test body."""
    monkeypatch.setattr(
        access_control,
        "get_access_context",
        lambda user_email: access_control.AccessContext(
            user_email=user_email, allowed_store_ids=None, roles=set()
        ),
    )
    monkeypatch.setattr(audit, "record_access", lambda **kwargs: None)
