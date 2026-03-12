#!/usr/bin/env python3
"""
Test script for Cambium backend API endpoints.
Verifies predict-action and add-reward return 200 OK and valid responses.
Run with backend at localhost:8000 (or set CAMBIUM_API_URL env var).
"""
import json
import os
import sys
import urllib.request
import urllib.error

BASE = os.getenv("CAMBIUM_API_URL", "http://localhost:8000")


def make_request(method, endpoint, data=None, timeout=10):
    """Make HTTP request and return (status_code, body_str, error)"""
    url = BASE + endpoint
    try:
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=body, method=method)
        else:
            req = urllib.request.Request(url, method=method)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8"), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        return e.code, body, str(e)
    except Exception as e:
        return None, None, str(e)


# Realistic observation payload (matches mod's buildObservationJson format)
SAMPLE_OBSERVATION = {
    "player": {
        "health": 20.0,
        "x": 4.5,
        "y": 17.0,
        "z": 38.0,
        "yaw": 90.0,
        "pitch": 0.0,
        "armor": 8
    },
    "entities": [
        {
            "isProjectile": False,
            "isPlayer": True,
            "health": 20.0,
            "armor": 8,
            "handDamage": 1.0,
            "relativeX": 0.5,
            "relativeY": 0.0,
            "relativeZ": 8.0,
            "veloX": 0,
            "veloY": 0,
            "veloZ": 0,
            "facingYaw": -90,
            "facingPitch": 0
        }
    ],
    "blocks": [],
    "inventory": []
}

SAMPLE_ACTION_SPACE = {
    "enableMovement": False,
    "enableJump": False,
    "enableSneak": False,
    "enableSprint": False,
    "enableAttack": False,
    "enableUseItem": False,
    "enableHotbar": False,
    "enableLook": True,
    "movementBins": 8,
    "yawBins": 9,
    "pitchBins": 5
}

PREDICT_PAYLOAD = {
    "observation": SAMPLE_OBSERVATION,
    "action_space": SAMPLE_ACTION_SPACE,
    "bot_name": "Bot1"
}

ADD_REWARD_PAYLOAD = {
    "bot_name": "Bot1",
    "events": [{"type": "good_aim", "amount": 0.5}],
    "current_state": {
        "player": {
            "health": 20,
            "x": 4.5,
            "y": 17,
            "z": 38,
            "yaw": 90,
            "pitch": 0,
            "armor": 8
        }
    }
}


def test_predict_v01():
    """Test /predict-action-v0.1 - the main endpoint the mod calls"""
    print("\n=== Testing POST /predict-action-v0.1 ===")
    status, body, err = make_request("POST", "/predict-action-v0.1", PREDICT_PAYLOAD)
    if err:
        print(f"  FAIL: Request error: {err}")
        return False
    if status != 200:
        print(f"  FAIL: Status {status} (expected 200)")
        print(f"  Body: {body[:500]}")
        return False
    try:
        data = json.loads(body)
        if "action" not in data:
            print(f"  FAIL: No 'action' in response. Keys: {list(data.keys())}")
            return False
        action = data["action"]
        required = ["movement", "jump", "attack", "yaw", "pitch"]
        for k in required:
            if k not in action:
                print(f"  FAIL: Action missing key '{k}'")
                return False
        print(f"  OK: Status 200, action keys present")
        print(f"  Action sample: movement={action.get('movement')} yaw={action.get('yaw')} pitch={action.get('pitch')}")
        return True
    except json.JSONDecodeError as e:
        print(f"  FAIL: Invalid JSON: {e}")
        return False


def test_predict_v01_minimal():
    """Test with minimal/malformed observation - should not crash"""
    print("\n=== Testing /predict-action-v0.1 with minimal observation ===")
    payload = {
        "observation": {"player": {"health": 10, "x": 0, "y": 0, "z": 0, "yaw": 0, "pitch": 0}},
        "action_space": SAMPLE_ACTION_SPACE,
        "bot_name": "Bot1"
    }
    status, body, err = make_request("POST", "/predict-action-v0.1", payload)
    if err:
        print(f"  FAIL: {err}")
        return False
    if status != 200:
        print(f"  FAIL: Status {status}")
        return False
    print(f"  OK: Handles minimal observation")
    return True


def test_predict_v01_empty_entities():
    """Test with empty entities - common case when no enemy visible"""
    print("\n=== Testing /predict-action-v0.1 with empty entities ===")
    payload = {
        "observation": {
            "player": {"health": 20, "x": 4, "y": 17, "z": 30, "yaw": 0, "pitch": 0, "armor": 8},
            "entities": []
        },
        "action_space": SAMPLE_ACTION_SPACE,
        "bot_name": "Bot1"
    }
    status, body, err = make_request("POST", "/predict-action-v0.1", payload)
    if err:
        print(f"  FAIL: {err}")
        return False
    if status != 200:
        print(f"  FAIL: Status {status}")
        return False
    print(f"  OK: Handles empty entities")
    return True


def test_add_reward():
    """Test POST /add-reward/"""
    print("\n=== Testing POST /add-reward/ ===")
    status, body, err = make_request("POST", "/add-reward/", ADD_REWARD_PAYLOAD)
    if err:
        print(f"  FAIL: {err}")
        return False
    if status != 200:
        print(f"  FAIL: Status {status}")
        return False
    try:
        data = json.loads(body)
        if data.get("status") != "success":
            print(f"  WARN: status={data.get('status')} message={data.get('message')}")
        print(f"  OK: Status 200")
        return True
    except json.JSONDecodeError:
        print(f"  FAIL: Invalid JSON")
        return False


def test_rapid_fire():
    """Send many predict requests rapidly - simulates bot tick rate, catches memory/thread issues"""
    print("\n=== Testing rapid predict calls (50 requests) ===")
    failures = 0
    for i in range(50):
        status, body, err = make_request("POST", "/predict-action-v0.1", PREDICT_PAYLOAD, timeout=5)
        if err or status != 200:
            failures += 1
            if failures <= 2:
                print(f"  Request {i+1}: status={status} err={err}")
    if failures > 0:
        print(f"  FAIL: {failures}/50 requests failed")
        return False
    print(f"  OK: All 50 requests succeeded")
    return True


def test_health():
    """Test basic connectivity"""
    print("\n=== Testing GET / (health/root) ===")
    status, body, err = make_request("GET", "/")
    if err:
        print(f"  FAIL: Cannot connect - {err}")
        return False
    print(f"  OK: Backend reachable (status {status})")
    return True


def main():
    print("Cambium API Endpoint Tests")
    print(f"Base URL: {BASE}")
    
    tests = [
        test_health,
        test_predict_v01,
        test_predict_v01_minimal,
        test_predict_v01_empty_entities,
        test_add_reward,
        test_rapid_fire,
    ]
    
    passed = sum(1 for t in tests if t())
    total = len(tests)
    print(f"\n=== Result: {passed}/{total} tests passed ===")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
