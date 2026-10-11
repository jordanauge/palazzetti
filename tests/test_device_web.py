"""Opt-in ESP HTTP tests: set PLZ_DEVICE_URL; replaces then restores its existing map."""

import base64
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.skipif(not os.environ.get("PLZ_DEVICE_URL"), reason="requires an explicitly selected ESP")


def test_live_map_storage_and_cache():
    base = os.environ["PLZ_DEVICE_URL"].rstrip("/")
    secrets = yaml.safe_load((Path(__file__).parents[1] / "example/secrets.yaml").read_text())
    authorization = "Basic " + base64.b64encode(
        (secrets["web_username"] + ":" + secrets["web_password"]).encode()
    ).decode()

    def request(path, data=None, content_type="application/json", authenticated=True):
        headers = {"Content-Type": content_type}
        if authenticated:
            headers["Authorization"] = authorization
        with urllib.request.urlopen(
            urllib.request.Request(base + path, data=data, headers=headers), timeout=20
        ) as response:
            return response.read()

    original = request("/memory/map")

    def rejected(body, status=400):
        with pytest.raises(urllib.error.HTTPError) as caught:
            request("/memory/map", body)
        assert caught.value.code == status
        caught.value.read()
        caught.value.close()
        assert request("/memory/map") == original

    try:
        for path in ("/memory", "/memory/map", "/memory/cache"):
            with pytest.raises(urllib.error.HTTPError) as caught:
                request(path, authenticated=False)
            assert caught.value.code == 401
            caught.value.read()
            caught.value.close()
        with pytest.raises(urllib.error.HTTPError) as caught:
            request("/memory/map", b"{}", authenticated=False)
        assert caught.value.code == 401
        caught.value.read()
        caught.value.close()
        assert request("/memory/map") == original
        rejected(b"{broken")
        rejected(b"{}")
        rejected(b'{"format":1.5,"maps":[]}')
        rejected(original + b" " * (8193 - len(original)), 413)
        data = {"format": 1, "maps": [{"id": "fixture", "interval_ms": 86400000, "fields": [
            {"id": "field", "mem": "ram", "addr": 0, "width": 1}
        ]}]}
        for override in (
            {"addr": 8192}, {"addr": -1}, {"addr": 8191, "width": 2, "encoding": "uint16_le"},
            {"width": 2}, {"width": 0}, {"encoding": "bogus"}, {"interval_ms": 99},
            {"interval_ms": 100.5}, {"mem": "flash"},
            {"scale": True}, {"offset": "wrong"},
        ):
            field = {"id": "field", "mem": "ram", "addr": 0, "width": 1, **override}
            data["maps"][0]["fields"] = [field]
            rejected(json.dumps(data).encode())
        data["maps"][0]["fields"] = [
            {"id": str(i), "mem": "ram", "addr": i * 2, "width": 2, "encoding": "uint16_le"}
            for i in range(33)
        ]
        rejected(json.dumps(data).encode())
        data["maps"][0]["fields"].pop()
        bounded = json.dumps(data).encode()
        bounded += b" " * (8192 - len(bounded))
        assert len(bounded) == 8192
        request("/memory/map", bounded)
        assert request("/memory/map") == bounded
        state = json.loads(request("/memory/cache"))
        assert len(state["bytes"]) == 64
        assert all(byte["interval_ms"] == 86400000 for byte in state["bytes"])
        request("/memory/override", b"mem=ram&addr=0&interval_ms=1000", "application/x-www-form-urlencoded")
        state = json.loads(request("/memory/cache"))
        byte = next(byte for byte in state["bytes"] if byte["addr"] == 0)
        assert byte["override"] and byte["interval_ms"] == 1000
        request("/memory/override", b"mem=ram&addr=0&interval_ms=0", "application/x-www-form-urlencoded")
        assert not json.loads(request("/memory/cache"))["bytes"][0]["override"]
        request("/memory/map", original)
        # Disconnect during a raw upload: staging must not replace the valid document.
        url = urllib.parse.urlparse(base)
        with socket.create_connection((url.hostname, url.port or 80), timeout=5) as connection:
            header = (
                f"POST /memory/map HTTP/1.1\r\nHost: {url.hostname}\r\n"
                f"Authorization: {authorization}\r\nContent-Type: application/json\r\n"
                f"Content-Length: {len(bounded)}\r\nConnection: close\r\n\r\n"
            )
            connection.sendall(header.encode() + bounded[:200])
        assert request("/memory/map") == original
    finally:
        request("/memory/map", original)
