"""Tiny operator CLI over the live API.

Usage (backend running on localhost:8000, or set VANTA_API):
    python scripts/vanta_cli.py brief
    python scripts/vanta_cli.py ask "Will X happen?" --category finance
    python scripts/vanta_cli.py resolve 5 --outcome yes
    python scripts/vanta_cli.py alerts
    python scripts/vanta_cli.py note 5 "Resolution needs the official filing, not press coverage."
    python scripts/vanta_cli.py notes 5
"""

import argparse
import json
import os
import sys

import httpx

API = os.environ.get("VANTA_API", "http://localhost:8000")


def _headers() -> dict:
    key = os.environ.get("VANTA_API_KEY")
    return {"X-API-Key": key} if key else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("brief")
    sub.add_parser("alerts")
    ask = sub.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--category", default="technology")
    ask.add_argument("--horizon", type=int, default=90)
    resolve = sub.add_parser("resolve")
    resolve.add_argument("question_id", type=int)
    resolve.add_argument("--outcome", choices=["yes", "no"], required=True)
    note = sub.add_parser("note")
    note.add_argument("question_id", type=int)
    note.add_argument("body")
    notes = sub.add_parser("notes")
    notes.add_argument("question_id", type=int)
    args = parser.parse_args()

    with httpx.Client(base_url=API, headers=_headers(), timeout=120) as client:
        if args.command == "brief":
            for item in client.get("/api/brief").json():
                print(f"{item['rank']}. [{item['category']}] {item['question']}")
                print(f"   {item['one_liner']}")
        elif args.command == "alerts":
            for alert in client.get("/api/alerts").json():
                print(f"[{alert['kind']:4s}] {alert['value']:+.0%}  {alert['question']}")
        elif args.command == "ask":
            response = client.post(
                "/api/questions",
                json={"question": args.question, "category": args.category, "horizon_days": args.horizon},
            )
            if response.status_code != 201:
                print(f"error {response.status_code}: {response.text}", file=sys.stderr)
                return 1
            detail = response.json()
            forecast = detail["latest_forecast"]
            print(f"#{detail['id']} vanta {forecast['probability']:.0%} conf {forecast['confidence']}/10")
            print(forecast["reasoning"])
        elif args.command == "resolve":
            response = client.post(
                f"/api/questions/{args.question_id}/resolve",
                json={"outcome": args.outcome == "yes"},
            )
            if response.status_code != 200:
                print(f"error {response.status_code}: {response.text}", file=sys.stderr)
                return 1
            print(json.dumps(response.json()["latest_forecast"], indent=1))
        elif args.command == "note":
            response = client.post(f"/api/questions/{args.question_id}/notes", json={"body": args.body})
            if response.status_code != 201:
                print(f"error {response.status_code}: {response.text}", file=sys.stderr)
                return 1
            print(f"note {response.json()['id']} saved")
        elif args.command == "notes":
            for item in client.get(f"/api/questions/{args.question_id}/notes").json():
                print(f"[{item['created_at'][:10]}] {item['body']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
