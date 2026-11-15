import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_vercel_sends_api_to_fastapi_and_falls_back_to_spa():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    services = config["services"]
    rewrites = config["rewrites"]

    assert services["backend"]["root"] == "backend/"
    assert services["backend"]["framework"] == "fastapi"
    assert services["backend"]["entrypoint"] == "app.main:app"
    assert services["frontend"]["root"] == "frontend/"
    assert services["frontend"]["framework"] == "vite"
    assert services["frontend"]["rewrites"] == [
        {"source": "/(.*)", "destination": "/index.html"},
    ]
    assert rewrites[0] == {
        "source": "/api/(.*)",
        "destination": {"service": "backend"},
    }
    assert rewrites[-1] == {
        "source": "/(.*)",
        "destination": {"service": "frontend"},
    }
