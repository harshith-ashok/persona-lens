"""End-to-end load test: N concurrent audio sessions (+ optional /recognize timing).

  python testing/loadtest.py --user NAME --password PASS --audio convo.wav -n 3 [--image face.jpg]

Needs the backend on :8120 and the local Supabase (reads ANON_KEY from ../.env).
"""
import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent


def env(key):
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1]


def login(user, password):
    r = requests.post("http://localhost:8000/auth/v1/token?grant_type=password",
                      headers={"apikey": env("ANON_KEY")},
                      json={"email": f"{user.lower()}@persona-lens.local", "password": password})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def one_session(api, headers, audio):
    sid = requests.post(f"{api}/session/start", headers=headers, data={"mode": "audio"}).json()["id"]
    t0 = time.perf_counter()
    with open(audio, "rb") as f:
        r = requests.post(f"{api}/session/{sid}/end", headers=headers, files={"audio": f})
    accepted = time.perf_counter() - t0
    while True:
        s = requests.get(f"{api}/session/{sid}", headers=headers).json()
        if s["status"] in ("ended", "resolved", "failed"):
            return {"status": s["status"], "accepted": accepted, "done": time.perf_counter() - t0,
                    "timings": s.get("timings") or {}}
        time.sleep(0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--image")
    ap.add_argument("-n", type=int, default=3, help="concurrent sessions")
    ap.add_argument("--api", default="http://localhost:8120")
    a = ap.parse_args()

    headers = login(a.user, a.password)

    if a.image:
        times = []
        for _ in range(5):
            t = time.perf_counter()
            with open(a.image, "rb") as f:
                requests.post(f"{a.api}/recognize", headers=headers, files={"file": f}).raise_for_status()
            times.append(time.perf_counter() - t)
        print(f"/recognize  first {times[0]:.2f}s  then median {statistics.median(times[1:]):.2f}s")

    t = time.perf_counter()
    with ThreadPoolExecutor(a.n) as pool:
        results = list(pool.map(lambda _: one_session(a.api, headers, a.audio), range(a.n)))
    wall = time.perf_counter() - t

    print(f"{a.n} concurrent sessions, wall {wall:.1f}s")
    for i, r in enumerate(results, 1):
        print(f"  #{i} {r['status']:9} accepted in {r['accepted']:.2f}s, done in {r['done']:.1f}s  stages {r['timings']}")


if __name__ == "__main__":
    main()
