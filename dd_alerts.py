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
MARKETS = "player_props"
ODDS_FORMAT = "american"
EV_THRESHOLD = 0.10


def american_to_implied(odds):
    odds = int(odds)
    if odds < 0:
        return abs(odds) / (abs(odds) + 100.0)
    return 100.0 / (odds + 100.0)


def expected_value(model_p, odds):
    odds = int(odds)

    if odds > 0:
        profit = odds / 100.0
    else:
        profit = 100.0 / abs(odds)

    return model_p * profit - (1.0 - model_p)


def post_discord(message):
    if not DISCORD_WEBHOOK:
        print(message)
        return

    requests.post(
        DISCORD_WEBHOOK,
        json={"content": message},
        timeout=10
    )


def load_model_probs(path):
    out = {}

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            player = row["player"].strip().lower()
            out[player] = float(row["model_p"])

    return out


def main():
    if not ODDS_API_KEY:
        raise SystemExit("Missing ODDS_API_KEY")

    if not DISCORD_WEBHOOK:
        raise SystemExit("Missing DISCORD_WEBHOOK")

    model = load_model_probs(MODEL_CSV)
    seen = set()

    while True:
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
            params = {
                "apiKey": ODDS_API_KEY,
                "regions": REGIONS,
                "markets": MARKETS,
                "bookmakers": BOOKMAKERS,
                "oddsFormat": ODDS_FORMAT
            }

            response = requests.get(url, params=params)
            games = response.json()

            for game in games:
                for bookmaker in game.get("bookmakers", []):
                    for market in bookmaker.get("markets", []):
                        for outcome in market.get("outcomes", []):

                            player = (outcome.get("description") or "").strip()
                            odds = outcome.get("price")

                            if not player or odds is None:
                                continue

                            model_p = model.get(player.lower())
                            if model_p is None:
                                continue

                            ev = expected_value(model_p, odds)

                            if ev >= EV_THRESHOLD:
                                key = (game.get("id"), player.lower(), int(odds))
                                if key in seen:
                                    continue

                                seen.add(key)

                                message = (
                                    f"🔥 +EV Player Prop\n"
                                    f"Player: {player}\n"
                                    f"Odds: {odds}\n"
                                    f"Model Prob: {model_p:.3f}\n"
                                    f"EV: {ev*100:.1f}%"
                                )

                                post_discord(message)

            time.sleep(POLL_SECONDS)

        except Exception as e:
            print("Error:", e)
            time.sleep(60)


if __name__ == "__main__":
    main()
