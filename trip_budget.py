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
    python trip_budget.py --dest thailand --origin delhi --days 21 --month 2 --year 2027
    python trip_budget.py --dest portugal --origin new_york --days 14 --month 7 --year 2027 --style comfort
"""

import argparse
import random
import statistics
from datetime import date

BASE_YEAR = 2024

# --- Illustrative data -------------------------------------------------------
# Baseline daily cost per person in USD at BASE_YEAR prices, "budget" style.
# flight = one-off round trip from a reference origin.
PROFILES = {'seasia': {'lodging': [1.25, 1.25, 1.1, 0.95, 0.8, 0.8, 0.85, 0.85, 0.8, 0.9, 1.1, 1.3], 'activities': [1.1, 1.1, 1.05, 1, 0.9, 0.9, 0.95, 0.95, 0.9, 0.95, 1.05, 1.15], 'flight': [1.2, 1.1, 1, 0.95, 0.85, 0.85, 0.95, 0.95, 0.85, 0.9, 1, 1.3]}, 'med': {'lodging': [0.75, 0.75, 0.85, 1, 1.1, 1.2, 1.5, 1.55, 1.2, 0.95, 0.8, 0.85], 'activities': [0.85, 0.85, 0.9, 1, 1.05, 1.1, 1.2, 1.2, 1.1, 1, 0.9, 0.9], 'flight': [0.8, 0.8, 0.9, 1, 1.1, 1.2, 1.4, 1.4, 1.1, 1, 0.85, 1]}, 'carib': {'lodging': [1.3, 1.3, 1.25, 1, 0.8, 0.8, 0.9, 0.9, 0.75, 0.85, 1, 1.35], 'activities': [1.15, 1.15, 1.15, 1, 0.9, 0.9, 0.95, 0.95, 0.85, 0.9, 1, 1.15], 'flight': [1.2, 1.15, 1.15, 1, 0.85, 0.9, 1.05, 1, 0.8, 0.85, 0.95, 1.3]}, 'sasia': {'lodging': [1.2, 1.15, 1.05, 0.9, 0.8, 0.75, 0.75, 0.8, 0.9, 1.1, 1.25, 1.3], 'activities': [1.1, 1.1, 1, 0.95, 0.9, 0.85, 0.85, 0.9, 0.95, 1.05, 1.15, 1.2], 'flight': [1.2, 1.05, 1, 0.95, 0.85, 0.8, 0.85, 0.9, 0.95, 1.05, 1.15, 1.35]}, 'shsum': {'lodging': [1.4, 1.35, 1.1, 0.9, 0.8, 0.75, 0.8, 0.8, 0.9, 1, 1.1, 1.35], 'activities': [1.25, 1.2, 1.05, 0.95, 0.85, 0.8, 0.85, 0.85, 0.9, 1, 1.05, 1.2], 'flight': [1.35, 1.25, 1, 0.9, 0.85, 0.8, 0.9, 0.9, 0.9, 1, 1.05, 1.4]}, 'andes': {'lodging': [0.9, 0.85, 0.85, 0.9, 1, 1.25, 1.4, 1.35, 1.1, 0.95, 0.85, 0.95], 'activities': [0.9, 0.9, 0.9, 0.95, 1, 1.15, 1.25, 1.25, 1.1, 1, 0.9, 0.95], 'flight': [1.05, 0.9, 0.9, 0.9, 0.95, 1.15, 1.3, 1.2, 1, 0.95, 0.9, 1.25]}, 'eastasia': {'lodging': [0.9, 0.9, 1.2, 1.25, 1, 0.9, 1.05, 1.2, 0.95, 1.1, 1.2, 1], 'activities': [0.95, 0.95, 1.15, 1.15, 1, 0.95, 1.05, 1.15, 1, 1.05, 1.1, 1], 'flight': [1.1, 0.95, 1.15, 1.2, 1, 0.9, 1.05, 1.25, 0.95, 1, 1.05, 1.2]}, 'safari': {'lodging': [1.15, 0.95, 0.85, 0.8, 0.8, 0.95, 1.3, 1.4, 1.3, 1.1, 0.85, 1.1], 'activities': [1.1, 0.95, 0.9, 0.85, 0.85, 0.95, 1.25, 1.3, 1.2, 1.05, 0.9, 1.1], 'flight': [1.2, 0.95, 0.9, 0.85, 0.85, 1, 1.3, 1.3, 1.1, 1, 0.9, 1.3]}, 'shoulder': {'lodging': [0.85, 0.9, 1.1, 1.25, 1.15, 0.9, 0.85, 0.85, 1.15, 1.3, 1.05, 0.95], 'activities': [0.9, 0.95, 1.1, 1.2, 1.1, 0.95, 0.9, 0.9, 1.1, 1.2, 1, 0.95], 'flight': [0.85, 0.85, 1, 1.15, 1.05, 1, 1.1, 1.1, 1.05, 1.1, 0.9, 1.1]}}

# name, lodging, food, transport, activities, region, season profile, inflation % 2015-2024
ROWS = [
    ('Thailand', 14, 12, 6, 8, 'SEA', 'seasia', [-0.9, 0.2, 0.7, 1.1, 0.7, -0.8, 1.2, 6.1, 1.2, 0.4]),
    ('Vietnam', 11, 10, 6, 7, 'SEA', 'seasia', [0.6, 2.7, 3.5, 3.5, 2.8, 3.2, 1.8, 3.2, 3.3, 3.6]),
    ('Indonesia', 13, 9, 5, 8, 'SEA', 'seasia', [6.4, 3.5, 3.8, 3.3, 2.8, 2.0, 1.6, 4.2, 3.7, 2.3]),
    ('Cambodia', 10, 8, 5, 10, 'SEA', 'seasia', [1.2, 3.0, 2.9, 2.5, 1.9, 2.9, 2.9, 5.3, 2.1, 0.8]),
    ('Malaysia', 15, 9, 5, 8, 'SEA', 'seasia', [2.1, 2.1, 3.8, 1.0, 0.7, -1.1, 2.5, 3.3, 2.5, 1.8]),
    ('Philippines', 14, 10, 5, 10, 'SEA', 'seasia', [0.7, 1.3, 2.9, 5.2, 2.5, 2.6, 3.9, 5.8, 6.0, 3.3]),
    ('India', 12, 7, 4, 6, 'SAS', 'sasia', [4.9, 4.5, 3.6, 3.4, 4.8, 6.2, 5.5, 6.7, 5.7, 5.0]),
    ('Nepal', 9, 7, 4, 9, 'SAS', 'sasia', [7.2, 9.9, 4.5, 4.1, 4.6, 6.1, 3.6, 6.3, 7.7, 5.4]),
    ('Japan', 38, 25, 12, 14, 'EAS', 'eastasia', [0.8, -0.1, 0.5, 1.0, 0.5, 0.0, -0.2, 2.5, 3.3, 2.7]),
    ('South Korea', 32, 18, 8, 10, 'EAS', 'eastasia', [0.7, 1.0, 1.9, 1.5, 0.4, 0.5, 2.5, 5.1, 3.6, 2.3]),
    ('China', 24, 12, 6, 10, 'EAS', 'eastasia', [1.4, 2.0, 1.6, 2.1, 2.9, 2.5, 0.9, 2.0, 0.2, 0.2]),
    ('Morocco', 18, 11, 5, 8, 'MENA', 'shoulder', [1.5, 1.6, 0.7, 1.6, 0.2, 0.7, 1.4, 6.6, 6.1, 0.9]),
    ('Jordan', 20, 11, 5, 15, 'MENA', 'shoulder', [-0.9, -0.8, 3.3, 4.5, 0.7, 0.4, 1.3, 4.2, 2.1, 1.6]),
    ('Portugal', 30, 22, 10, 12, 'EUR', 'med', [0.5, 0.6, 1.4, 1.0, 0.3, -0.1, 1.3, 7.8, 4.3, 2.4]),
    ('Spain', 38, 24, 10, 14, 'EUR', 'med', [-0.5, -0.2, 2.0, 1.7, 0.7, -0.3, 3.1, 8.4, 3.5, 2.8]),
    ('Italy', 45, 26, 10, 16, 'EUR', 'med', [0.1, -0.1, 1.3, 1.2, 0.6, -0.1, 1.9, 8.7, 5.9, 1.1]),
    ('Greece', 40, 22, 9, 12, 'EUR', 'med', [-1.1, 0.0, 1.1, 0.8, 0.5, -1.3, 0.6, 9.3, 4.2, 2.7]),
    ('Croatia', 35, 22, 8, 12, 'EUR', 'med', [-0.3, -0.6, 1.3, 1.6, 0.8, 0.0, 2.7, 10.7, 8.4, 3.0]),
    ('Germany', 40, 26, 12, 14, 'EUR', 'med', [0.7, 0.4, 1.7, 1.9, 1.4, 0.5, 3.2, 8.7, 6.0, 2.2]),
    ('France', 45, 28, 12, 16, 'EUR', 'med', [0.1, 0.3, 1.2, 2.1, 1.3, 0.5, 2.1, 5.9, 5.7, 2.3]),
    ('United Kingdom', 50, 28, 14, 16, 'EUR', 'med', [0.4, 1.0, 2.6, 2.3, 1.7, 0.9, 2.6, 9.1, 7.3, 2.5]),
    ('Mexico', 20, 15, 8, 10, 'CAM', 'carib', [2.7, 2.8, 6.0, 4.9, 3.6, 3.4, 5.7, 7.9, 5.5, 4.7]),
    ('Costa Rica', 30, 16, 6, 16, 'CAM', 'carib', [0.8, 0.0, 1.6, 2.2, 2.1, 0.7, 1.7, 8.3, 0.5, 0.8]),
    ('Colombia', 15, 10, 4, 10, 'CAM', 'carib', [5.0, 7.5, 4.3, 3.2, 3.5, 2.5, 3.5, 10.2, 11.7, 6.6]),
    ('Peru', 14, 9, 5, 12, 'SAM', 'andes', [3.5, 3.6, 2.8, 1.3, 2.1, 1.8, 4.0, 7.9, 6.3, 2.4]),
    ('Ecuador', 13, 8, 4, 10, 'SAM', 'andes', [4.0, 1.7, 0.4, -0.2, 0.3, -0.3, 0.1, 3.5, 2.2, 1.5]),
    ('Bolivia', 10, 7, 4, 8, 'SAM', 'andes', [4.1, 3.6, 2.8, 2.3, 1.8, 0.9, 0.7, 1.7, 2.6, 5.1]),
    ('Chile', 22, 15, 6, 10, 'SAM', 'shsum', [4.3, 3.8, 2.2, 2.3, 2.5, 3.0, 4.5, 11.6, 7.6, 3.9]),
    ('Brazil', 20, 13, 6, 10, 'SAM', 'shsum', [9.0, 8.7, 3.4, 3.7, 3.7, 3.2, 8.3, 9.3, 4.6, 4.4]),
    ('Australia', 40, 25, 12, 16, 'OCE', 'shsum', [1.5, 1.3, 2.0, 1.9, 1.6, 0.9, 2.8, 6.6, 5.6, 3.2]),
    ('New Zealand', 38, 22, 12, 18, 'OCE', 'shsum', [0.3, 0.6, 1.9, 1.6, 1.6, 1.7, 3.9, 7.2, 5.7, 2.9]),
    ('South Africa', 20, 12, 6, 14, 'AFR', 'safari', [4.6, 6.3, 5.3, 4.6, 4.1, 3.3, 4.5, 6.9, 5.9, 4.4]),
    ('Kenya', 18, 10, 6, 20, 'AFR', 'safari', [6.6, 6.3, 8.0, 4.7, 5.2, 5.3, 6.1, 7.7, 7.7, 4.5]),
    ('Tanzania', 18, 10, 6, 22, 'AFR', 'safari', [5.6, 5.2, 5.3, 3.5, 3.4, 3.3, 3.7, 4.4, 3.8, 3.1]),
]

DATA = {
    n.lower().replace(' ', '_'): {
        'daily': {'lodging': l, 'food': f, 'transport': t, 'activities': a},
        'region': rg, 'inflation': inf, 'season': PROFILES[p],
    }
    for n, l, f, t, a, rg, p, inf in ROWS
}

# Round-trip economy fares in USD (2024, average season): home region -> destination region
COLS = ['SEA', 'SAS', 'EAS', 'EUR', 'MENA', 'CAM', 'SAM', 'OCE', 'AFR']
FLIGHTS = {'SAS': [350, 200, 450, 650, 350, 1400, 1500, 800, 550], 'SEA': [200, 350, 350, 800, 600, 1500, 1600, 450, 900], 'EAS': [350, 500, 250, 900, 800, 1300, 1600, 600, 1100], 'EUR': [750, 600, 900, 200, 250, 800, 950, 1500, 700], 'NAM': [1100, 1200, 900, 650, 900, 350, 900, 1500, 1300], 'SAM': [1600, 1700, 1700, 950, 1100, 500, 300, 1700, 1200], 'MENA': [650, 350, 750, 350, 200, 1100, 1200, 1200, 500], 'AFR': [850, 650, 1000, 700, 500, 1300, 1000, 1400, 350], 'OCE': [450, 1100, 700, 1600, 1500, 1500, 1500, 300, 1500]}
ORIGINS = {c.lower().replace(' ', '_'): r for c, r in {'Delhi': 'SAS', 'Mumbai': 'SAS', 'Bengaluru': 'SAS', 'Singapore': 'SEA', 'Bangkok': 'SEA', 'Tokyo': 'EAS', 'Hong Kong': 'EAS', 'London': 'EUR', 'Frankfurt': 'EUR', 'Madrid': 'EUR', 'New York': 'NAM', 'Los Angeles': 'NAM', 'Toronto': 'NAM', 'Sao Paulo': 'SAM', 'Dubai': 'MENA', 'Johannesburg': 'AFR', 'Sydney': 'OCE'}.items()}

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


def forecast(dest, origin, days, month, year, style, flights=True, seed=42):
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
    fare = FLIGHTS[ORIGINS[origin]][COLS.index(d["region"])] if flights else 0
    flight_base = fare * season["flight"][month - 1]

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


def report(dest, origin, days, month, year, style, flights=True):
    r = forecast(dest, origin, days, month, year, style, flights)
    month_name = date(2000, month, 1).strftime("%B")
    buffer = r["expected"] * CONTINGENCY

    print(f"\nTrip: {origin.replace('_', ' ').title()} to {dest.replace('_', ' ').title()} | {days} days | {month_name} {year} | {style}")
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
    ap.add_argument("--origin", choices=sorted(ORIGINS), required=True, help="home city for flight cost")
    ap.add_argument("--no-flights", action="store_true", help="leave flights out of the budget")
    ap.add_argument("--days", type=int, required=True)
    ap.add_argument("--month", type=int, choices=range(1, 13), required=True, metavar="1-12")
    ap.add_argument("--year", type=int, default=date.today().year + 1)
    ap.add_argument("--style", choices=sorted(STYLE), default="budget")
    a = ap.parse_args()
    report(a.dest, a.origin, a.days, a.month, a.year, a.style, not a.no_flights)


if __name__ == "__main__":
    main()
