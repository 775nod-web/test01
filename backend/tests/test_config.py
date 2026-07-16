"""ポート・ホスト解決と、データモード判定の優先順位を検証する単体テスト。"""

from backend.config import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    resolve_data_mode,
    resolve_host,
    resolve_port,
)


def test_resolve_host_defaults_to_zero_zero_zero_zero() -> None:
    assert resolve_host(env={}) == DEFAULT_HOST


def test_resolve_host_uses_uvicorn_host_when_set() -> None:
    assert resolve_host(env={"UVICORN_HOST": "127.0.0.1"}) == "127.0.0.1"


def test_resolve_port_defaults_to_8000() -> None:
    assert resolve_port(env={}) == DEFAULT_PORT


def test_resolve_port_uses_port_when_only_port_set() -> None:
    assert resolve_port(env={"PORT": "3000"}) == 3000


def test_resolve_port_prefers_uvicorn_port_over_port() -> None:
    env = {"PORT": "3000", "UVICORN_PORT": "4000"}
    assert resolve_port(env=env) == 4000


def test_resolve_port_prefers_databricks_app_port_over_others() -> None:
    env = {"PORT": "3000", "UVICORN_PORT": "4000", "DATABRICKS_APP_PORT": "5000"}
    assert resolve_port(env=env) == 5000


def test_resolve_port_ignores_empty_string_values() -> None:
    env = {"DATABRICKS_APP_PORT": "", "UVICORN_PORT": "", "PORT": "6000"}
    assert resolve_port(env=env) == 6000


def test_resolve_data_mode_is_demo_when_unconfigured() -> None:
    assert resolve_data_mode(env={}) == "demo"


def test_resolve_data_mode_is_demo_when_partially_configured() -> None:
    env = {
        "DATABRICKS_SERVER_HOSTNAME": "example.cloud.databricks.com",
        "DATABRICKS_HTTP_PATH": "/sql/1.0/warehouses/abc",
    }
    assert resolve_data_mode(env=env) == "demo"


def test_resolve_data_mode_is_databricks_when_fully_configured() -> None:
    env = {
        "DATABRICKS_SERVER_HOSTNAME": "example.cloud.databricks.com",
        "DATABRICKS_HTTP_PATH": "/sql/1.0/warehouses/abc",
        "DATABRICKS_TOKEN": "dummy-token",
    }
    assert resolve_data_mode(env=env) == "databricks"
