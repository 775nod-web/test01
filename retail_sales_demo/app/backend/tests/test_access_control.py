from backend import access_control
from backend.access_control import AccessContext


def test_resolve_effective_store_ids_admin_passthrough():
    # allowed=None means "admin" — whatever was requested passes through unchanged.
    assert access_control.resolve_effective_store_ids(["S001"], None) == ["S001"]
    assert access_control.resolve_effective_store_ids(None, None) is None


def test_resolve_effective_store_ids_no_request_returns_allowed_set():
    assert access_control.resolve_effective_store_ids(None, ["S001", "S002"]) == ["S001", "S002"]


def test_resolve_effective_store_ids_intersects():
    assert access_control.resolve_effective_store_ids(["S001", "S003"], ["S001", "S002"]) == ["S001"]


def test_resolve_effective_store_ids_denies_when_no_overlap():
    assert access_control.resolve_effective_store_ids(["S999"], ["S001", "S002"]) == []


def test_resolve_effective_store_ids_denies_all_when_no_mapping_rows():
    assert access_control.resolve_effective_store_ids(["S001"], []) == []


def test_mask_customer_id_keeps_prefix():
    assert access_control.mask_customer_id("CUST12345") == "CUST*****"


def test_mask_customer_id_handles_short_values():
    assert access_control.mask_customer_id("AB") == "**"


def test_mask_customer_id_passes_through_falsy():
    assert access_control.mask_customer_id(None) is None
    assert access_control.mask_customer_id("") == ""


def test_can_view_pii_true_for_admin():
    ctx = AccessContext(user_email="hq@example.com", allowed_store_ids=None, roles=set())
    assert ctx.can_view_pii is True


def test_can_view_pii_false_for_store_scoped_without_role():
    ctx = AccessContext(user_email="store1@example.com", allowed_store_ids=["S001"], roles=set())
    assert ctx.can_view_pii is False


def test_can_view_pii_true_with_explicit_role():
    ctx = AccessContext(user_email="dq@example.com", allowed_store_ids=["S001"], roles={"PII_VIEWER"})
    assert ctx.can_view_pii is True


def test_can_view_audit_log_requires_role_or_admin():
    scoped = AccessContext(user_email="store1@example.com", allowed_store_ids=["S001"], roles=set())
    assert scoped.can_view_audit_log is False

    with_role = AccessContext(user_email="dq@example.com", allowed_store_ids=["S001"], roles={"AUDIT_VIEWER"})
    assert with_role.can_view_audit_log is True

    admin = AccessContext(user_email="hq@example.com", allowed_store_ids=None, roles=set())
    assert admin.can_view_audit_log is True
