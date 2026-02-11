import os
import time
import csv
import requests

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
MODEL_CSV = os.environ.get("MODEL_CSV", "my_dd_model_probs.csv")
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "300"))

SPORT = "basketball_nba"
REGIONS = "us"
BOOKMAKERS = "draftkings"
MARKETS = "player_double_double"
ODDS_FORMAT = "american"
EV_THRESHOLD = 0.20


def american_to_implied(odds: int) -> float:
odds = int(odds)
if odds < 0:
return abs(odds) / (abs(odds) + 100.0)
return 100.0 / (odds + 100.0)


def expected_value(model_p: float, odds: int) -> float:
odds = int(odds)
if odds > 0:
profit = odds / 100.0
else:
profit = 100.0 / abs(odds)
return model_p * profit - (1.0 - model_p)


def post_discord(message: str) -> None:
if not DISCORD_WEBHOOK:
print(message)
return
requests.post(DISCORD_WEBHOOK, json={"content": message}, timeout=20)


def load_model_probs(path: str) -> dict:
out = {}
with open(path, newline="", encoding="utf-8") as f:
r = csv.DictReader(f)
for row in r:
player = row["player"].strip().lower()
out[player] = float(row["model_p"])
return out


def fetch_events() -> list:
url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/events"
r = requests.get(url, params={"apiKey": ODDS_API_KEY}, timeout=30)
r.raise_for_status()
return r.json()


def fetch_event_odds(event_id: str) -> dict:
url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/events/{event_id}/odds"
params = {
"apiKey": ODDS_API_KEY,
"regions": REGIONS,
"bookmakers": BOOKMAKERS,
"markets": MARKETS,
"oddsFormat": ODDS_FORMAT,
}
r = requests.get(url, params=params, timeout=30)
r.raise_for_status()
return r.json()


def main() -> None:
if not ODDS_API_KEY:
raise SystemExit("Missing ODDS_API_KEY env var")
if not DISCORD_WEBHOOK:
raise SystemExit("Missing DISCORD_WEBHOOK env var")

model = load_model_probs(MODEL_CSV)
seen = set()

while True:
try:
events = fetch_events()
for ev in events:
data = fetch_event_odds(ev["id"])
for bk in data.get("bookmakers", []):
if bk.get("key") != "draftkings":
continue
for mkt in bk.get("markets", []):
if mkt.get("key") != MARKETS:
continue
for out in mkt.get("outcomes", []):
# Keep only "Yes"
if str(out.get("name", "")).lower() != "yes":
continue

player = (out.get("description") or "").strip()
odds = out.get("price")
if not player or odds is None:
continue

player_key = player.lower()
model_p = model.get(player_key)
if model_p is None:
continue

ev_per_1 = expected_value(model_p, odds)
if ev_per_1 >= EV_THRESHOLD:
key = (ev["id"], player_key, int(odds))
if key in seen:
continue
seen.add(key)

imp = american_to_implied(odds)
msg = (
f"🔥 20%+ EV DOUBLE DOUBLE\n"
f"Player: {player}\n"
f"Odds: {odds} (implied {imp:.1%})\n"
f"Model P: {model_p:.1%}\n"
f"EV: {ev_per_1*100:.1f}% per $1\n"
f"{ev.get('away_team')} @ {ev.get('home_team')}"
)
post_discord(msg)

time.sleep(POLL_SECONDS)
except Exception as e:
print("Error:", e)
time.sleep(60)


if __name__ == "__main__":
main()