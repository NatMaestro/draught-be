#!/usr/bin/env python
"""Quick API smoke test. Requires server running: python manage.py runserver [port]"""
import json
import os
import sys
import urllib.request
import urllib.error

BASE = os.environ.get("DRAUGHT_API_URL", "http://127.0.0.1:8000/api")


def req(method, path, data=None, token=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=10) as res:
            return res.getcode(), json.loads(res.read().decode())
    except urllib.error.URLError as e:
        if "ConnectionRefusedError" in str(e) or "10061" in str(e) or "refused" in str(e).lower():
            print("\nConnection refused. Is the server running?")
            print("Start it in another terminal:  python manage.py runserver 8000")
            print(f"(This script is using: {BASE})")
            sys.exit(1)
        raise


def main():
    print("1. Register...")
    code, data = req("POST", "/auth/register/", {
        "username": "smoketest",
        "email": "smoke@test.com",
        "password": "pass1234",
        "password_confirm": "pass1234",
    })
    assert code == 201, data
    print("   OK", data)

    print("2. Login...")
    code, data = req("POST", "/auth/login/", {"username": "smoketest", "password": "pass1234"})
    assert code == 200, data
    token = data["access"]
    print("   OK (got token)")

    print("3. Create game (AI)...")
    code, game = req("POST", "/games/", {"is_ai": True, "ai_difficulty": "easy"}, token)
    assert code == 201, game
    game_id = game["id"]
    print("   OK game_id:", game_id)
    assert game["board_state"] and len(game["board_state"]) == 10
    assert game["board_state"][0][0] == 2, " (0,0) should have piece"

    print("4. Get game...")
    code, _ = req("GET", f"/games/{game_id}/", token=token)
    assert code == 200
    print("   OK")

    print("5. Legal moves (6,0)...")
    code, data = req("GET", f"/games/{game_id}/legal-moves/?row=6&col=0", token=token)
    assert code == 200
    print("   OK moves:", len(data.get("moves", [])))

    print("6. Make move...")
    code, data = req("POST", f"/games/{game_id}/move/", {
        "from_row": 6, "from_col": 0, "to_row": 5, "to_col": 1,
    }, token)
    assert code == 200, data
    print("   OK turn:", data.get("current_turn"), "winner:", data.get("winner"))

    print("7. Profile...")
    code, data = req("GET", "/users/profile/", token=token)
    assert code == 200
    print("   OK", data.get("username"), "rating:", data.get("rating"))

    print("\nAll API smoke tests passed.")


if __name__ == "__main__":
    main()
