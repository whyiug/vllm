import importlib.util
import sys
import types
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples/online_serving/disaggregated_encoder/disagg_epd_proxy.py"
)


def load_module(monkeypatch: pytest.MonkeyPatch):
    aiohttp = types.ModuleType("aiohttp")

    class DummyClientSession:
        pass

    aiohttp.ClientSession = DummyClientSession
    monkeypatch.setitem(sys.modules, "aiohttp", aiohttp)

    uvicorn = types.ModuleType("uvicorn")
    uvicorn.run = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "uvicorn", uvicorn)

    fastapi = types.ModuleType("fastapi")

    class DummyFastAPI:
        def __init__(self, *args, **kwargs):
            self.state = types.SimpleNamespace()

        def post(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

    class DummyHTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)

    class DummyRequest:
        pass

    fastapi.FastAPI = DummyFastAPI
    fastapi.HTTPException = DummyHTTPException
    fastapi.Request = DummyRequest
    monkeypatch.setitem(sys.modules, "fastapi", fastapi)

    responses = types.ModuleType("fastapi.responses")

    class DummyJSONResponse:
        pass

    class DummyStreamingResponse:
        def __init__(self, *args, **kwargs):
            pass

    responses.JSONResponse = DummyJSONResponse
    responses.StreamingResponse = DummyStreamingResponse
    monkeypatch.setitem(sys.modules, "fastapi.responses", responses)

    spec = importlib.util.spec_from_file_location("test_disagg_epd_proxy_module",
                                                  MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_args_rejects_empty_server_lists(monkeypatch: pytest.MonkeyPatch):
    module = load_module(monkeypatch)

    with pytest.raises(SystemExit):
        module.parse_args([
            "--encode-servers-urls",
            ",,",
            "--prefill-servers-urls",
            "disable",
            "--decode-servers-urls",
            ",",
        ])


def test_parse_args_rejects_empty_prefill_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
):
    module = load_module(monkeypatch)

    with pytest.raises(SystemExit):
        module.parse_args([
            "--encode-servers-urls",
            "http://e1:8001",
            "--prefill-servers-urls",
            ",,",
            "--decode-servers-urls",
            "http://d1:8003",
        ])


def test_parse_args_allows_disabled_prefill(monkeypatch: pytest.MonkeyPatch):
    module = load_module(monkeypatch)

    args = module.parse_args([
        "--encode-servers-urls",
        " http://e1:8001 , http://e2:8002 ",
        "--prefill-servers-urls",
        "disable",
        "--decode-servers-urls",
        " http://d1:8003 ",
    ])

    assert args.e_urls == ["http://e1:8001", "http://e2:8002"]
    assert args.p_urls == []
    assert args.d_urls == ["http://d1:8003"]
