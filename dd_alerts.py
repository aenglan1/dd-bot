import os
import time
import requests
import pandas as pd
from datetime import datetime

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
MODEL_CSV = os.environ.get("MODEL_CSV", "my_dd_model_probs.csv")
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", 300))

SPORT = "basketball_nba"
REGIONS = "us"
BOOKMAKERS = "draftkings"
MARKETS = "player_double_double"
ODDS_FORMAT = "american"

EV_THRESHOLD = 0.20

def american_to_implied(odds):
if odds < 0:
return abs(odds) / (abs(odds) + 100)
return 100 / (odds + 100)

def expected_value(model_p, odds):
if odds > 0:
profit = odds / 100
else:
profit = 100 / abs(odds)
return model_p * profit - (1 - model_p)

def post_discord(message):
requests.post(DISCORD_WEBHOOK, json={"content": message})

def main():
model_df = pd.read_csv(MODEL_CSV)
model_df["player"] = model_df["player"].str.lower()

while True:
try:
events_url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/events"
events = requests.get(events_url, params={"apiKey": ODDS_API_KEY}).json()

for event in events:
odds_url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/events/{event['id']}/odds"
odds_data = requests.get(odds_url, params={
"apiKey": ODDS_API_KEY,
"regions": REGIONS,
"bookmakers": BOOKMAKERS,
"markets": MARKETS,
"oddsFormat": ODDS_FORMAT
}).json()

for bookmaker in odds_data.get("bookmakers", []):
for market in bookmaker.get("markets", []):
for outcome in market.get("outcomes", []):
if outcome["name"].lower() != "yes":
continue

player = outcome["description"].lower()
odds = int(outcome["price"])

match = model_df[model_df["player"] == player]
if match.empty:
continue

model_p = float(match["model_p"].values[0])
ev = expected_value(model_p, odds)

if ev >= EV_THRESHOLD:
implied = american_to_implied(odds)
message = (
f"🔥 20%+ EV DOUBLE DOUBLE\n"
f"Player: {player.title()}\n"
f"Odds: {odds}\n"
f"Model P: {model_p:.2%}\n"
f"Implied P: {implied:.2%}\n"
f"EV: {ev:.2%}\n"
f"{event['away_team']} @ {event['home_team']}"
)
post_discord(message)

time.sleep(POLL_SECONDS)

except Exception as e:
print("Error:", e)
time.sleep(60)

if __name__ == "__main__":
main()
