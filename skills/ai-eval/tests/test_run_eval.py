"""Entry-point wiring that has to happen before any HTTP client exists."""

import ssl
from collections.abc import Iterator

import pytest
import truststore

import run_eval


@pytest.fixture
def restore_ssl() -> Iterator[None]:
    yield
    truststore.extract_from_ssl()


@pytest.mark.usefixtures("restore_ssl")
def test_os_trust_store_replaces_ssl_context() -> None:
    run_eval._use_os_trust_store()

    assert ssl.SSLContext is truststore.SSLContext
    assert isinstance(ssl.create_default_context(), truststore.SSLContext)
