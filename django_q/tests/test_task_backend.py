import importlib
import pytest


def test_backend_import_on_unsupported_version(monkeypatch):
    from django_q import conf

    monkeypatch.setattr(conf.Conf, "SUPPORTS_TASK_BACKEND", False)

    with pytest.raises(NotImplementedError):
        importlib.reload(importlib.import_module("django_q.backend.task_backend"))


def test_backend_import_on_supported_version(monkeypatch):
    from django_q import conf

    monkeypatch.setattr(conf.Conf, "SUPPORTS_TASK_BACKEND", True)

    module = importlib.reload(importlib.import_module("django_q.backend.task_backend"))

    assert hasattr(module, "DjangoQ2Backend")
