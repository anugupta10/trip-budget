#!/usr/bin/env python3
"""
Predictive Packing: backpacking trip budget forecaster.

Method
------
1. Start from a baseline daily cost per category (in USD, for BASE_YEAR).
2. Inflate it to the trip year by simulating many possible inflation paths,
   drawn from the mean and volatility of historical inflation.
3. Apply a seasonal multiplier for the travel month (lodging, activities, flights).
4. Report a range (P10 / expected / P90) plus a contingency buffer.

NOTE: All numbers in DATA below are illustrative placeholders. Replace them with
real figures (World Bank CPI API, your own past trip spending, Numbeo, etc.)
before relying on the output. No model can give an *exact* budget; the range
is the honest answer.

Usage
-----
    python trip_budget.py --dest thailand --days 21 --month 2 --year 2027
    python trip_budget.py --dest portugal --days 14 --month 7 --year 2027 --style comfort
"""

import argparse
import random
import statistics
from datetime import date

BASE_YEAR = 2024

# --- Illustrative data -------------------------------------------------------
# Baseline daily cost per person in USD at BASE_YEAR prices, "budget" style.
# flight = one-off round trip from a reference origin.
DATA = {
    "thailand": {
        "daily": {"lodging": 14, "food": 12, "transport": 6, "activities": 8},
        "flight": 900,
        "inflation": [-0.9, 0.2, 0.7, 1.1, 0.7, -0.8, 1.2, 6.1, 1.2, 0.4],  # 2015-2024 %
        # Month 1..12 multipliers by category (1.0 = average)
        "season": {
            "lodging":    [1.25, 1.25, 1.1, 0.95, 0.8, 0.8, 0.85, 0.85, 0.8, 0.9, 1.1, 1.3],
            "activities": [1.1, 1.1, 1.05, 1.0, 0.9, 0.9, 0.95, 0.95, 0.9, 0.95, 1.05, 1.15],
            "flight":     [1.2, 1.1, 1.0, 0.95, 0.85, 0.85, 0.95, 0.95, 0.85, 0.9, 1.0, 1.3],
        },
    },
    "portugal": {
        "daily": {"lodging": 30, "food": 22, "transport": 10, "activities": 12},
        "flight": 850,
        "inflation": [0.5, 0.6, 1.4, 1.0, 0.3, -0.1, 1.3, 7.8, 4.3, 2.4],
        "season": {
            "lodging":    [0.75, 0.75, 0.85, 1.0, 1.1, 1.2, 1.5, 1.55, 1.2, 0.95, 0.8, 0.85],
            "activities": [0.85, 0.85, 0.9, 1.0, 1.05, 1.1, 1.2, 1.2, 1.1, 1.0, 0.9, 0.9],
            "flight":     [0.8, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4, 1.4, 1.1, 1.0, 0.85, 1.0],
        },
    },
    "vietnam": {
        "daily": {"lodging": 11, "food": 10, "transport": 6, "activities": 7},
        "flight": 950,
        "inflation": [0.6, 2.7, 3.5, 3.5, 2.8, 3.2, 1.8, 3.2, 3.3, 3.6],
        "season": {
            "lodging":    [1.15, 1.2, 1.05, 0.95, 0.9, 0.85, 0.9, 0.9, 0.9, 0.95, 1.05, 1.2],
            "activities": [1.05, 1.1, 1.0, 1.0, 0.95, 0.9, 0.95, 0.95, 0.95, 1.0, 1.0, 1.1],
            "flight":     [1.25, 1.15, 1.0, 0.95, 0.85, 0.85, 0.9, 0.9, 0.85, 0.9, 1.0, 1.25],
        },
    },
    "mexico": {
        "daily": {"lodging": 20, "food": 15, "transport": 8, "activities": 10},
        "flight": 700,
        "inflation": [2.7, 2.8, 6.0, 4.9, 3.6, 3.4, 5.7, 7.9, 5.5, 4.7],
        "season": {
            "lodging":    [1.3, 1.3, 1.25, 1.0, 0.8, 0.8, 0.9, 0.9, 0.75, 0.85, 1.0, 1.35],
            "activities": [1.15, 1.15, 1.15, 1.0, 0.9, 0.9, 0.95, 0.95, 0.85, 0.9, 1.0, 1.15],
            "flight":     [1.2, 1.15, 1.15, 1.0, 0.85, 0.9, 1.05, 1.0, 0.8, 0.85, 0.95, 1.3],
        },
    },
}

# Travel style scales daily costs.
STYLE = {"shoestring": 0.75, "budget": 1.0, "comfort": 1.8}

CONTINGENCY = 0.10   # 10% buffer for the unexpected
N_SIMS = 5000


# --- Model -------------------------------------------------------------------
def inflation_stats(history_pct):
    """Blend long-run and recent mean so one old shock doesn't dominate."""
    long_mean = statistics.mean(history_pct)
    recent_mean = statistics.mean(history_pct[-3:])
    mean = 0.5 * long_mean + 0.5 * recent_mean
    std = statistics.stdev(history_pct)
    return mean / 100, std / 100


def simulate_inflation_factor(mean, std, years, rng):
    """Compound a random annual inflation path over `years` years."""
    factor = 1.0
    for _ in range(years):
        factor *= 1 + rng.gauss(mean, std)
    return factor


def forecast(dest, days, month, year, style, seed=42):
    d = DATA[dest]
    years = max(year - BASE_YEAR, 0)
    mean, std = inflation_stats(d["inflation"])
    rng = random.Random(seed)

    scale = STYLE[style]
    season = d["season"]
    base_lodging = d["daily"]["lodging"] * season["lodging"][month - 1]
    base_activities = d["daily"]["activities"] * season["activities"][month - 1]
    base_food = d["daily"]["food"]
    base_transport = d["daily"]["transport"]
    daily_base = (base_lodging + base_activities + base_food + base_transport) * scale
    flight_base = d["flight"] * season["flight"][month - 1]

    totals, breakdowns = [], []
    for _ in range(N_SIMS):
        f = simulate_inflation_factor(mean, std, years, rng)
        parts = {
            "lodging": base_lodging * scale * days * f,
            "food": base_food * scale * days * f,
            "transport": base_transport * scale * days * f,
            "activities": base_activities * scale * days * f,
            "flight": flight_base * f,
        }
        totals.append(sum(parts.values()))
        breakdowns.append(parts)

    totals_sorted = sorted(totals)
    pct = lambda p: totals_sorted[int(p * (N_SIMS - 1))]
    expected_parts = {k: statistics.mean(b[k] for b in breakdowns) for k in breakdowns[0]}

    return {
        "p10": pct(0.10),
        "expected": statistics.mean(totals),
        "p90": pct(0.90),
        "parts": expected_parts,
        "inflation_mean": mean,
        "inflation_std": std,
        "years": years,
        "daily_today": daily_base,
    }


def report(dest, days, month, year, style):
    r = forecast(dest, days, month, year, style)
    month_name = date(2000, month, 1).strftime("%B")
    buffer = r["expected"] * CONTINGENCY

    print(f"\nTrip: {dest.title()} | {days} days | {month_name} {year} | {style}")
    print(f"Inflation assumption: {r['inflation_mean']*100:.1f}%/yr "
          f"(±{r['inflation_std']*100:.1f}), compounded {r['years']} yrs from {BASE_YEAR}\n")
    print(f"{'Category':<12}{'Expected (USD)':>16}")
    print("-" * 28)
    for k, v in r["parts"].items():
        print(f"{k.title():<12}{v:>16,.0f}")
    print("-" * 28)
    print(f"{'Expected':<12}{r['expected']:>16,.0f}")
    print(f"{'Range P10-P90':<12}{r['p10']:>8,.0f} - {r['p90']:,.0f}")
    print(f"{'+ Buffer 10%':<12}{buffer:>16,.0f}")
    print(f"\nSuggested budget to save: ${r['p90'] + buffer:,.0f} "
          f"(P90 + buffer; ~${(r['p90'] + buffer) / days:,.0f}/day all-in)\n")


def main():
    ap = argparse.ArgumentParser(description="Backpacking trip budget forecaster")
    ap.add_argument("--dest", choices=sorted(DATA), required=True)
    ap.add_argument("--days", type=int, required=True)
    ap.add_argument("--month", type=int, choices=range(1, 13), required=True, metavar="1-12")
    ap.add_argument("--year", type=int, default=date.today().year + 1)
    ap.add_argument("--style", choices=sorted(STYLE), default="budget")
    a = ap.parse_args()
    report(a.dest, a.days, a.month, a.year, a.style)


if __name__ == "__main__":
    main()
