"""
Monte Carlo Prop Firm Challenge Passing Simulation
Calculates the exact statistical probability of passing FTMO ($10,000 account):
- Target: +$1,000 (+10%)
- Max Drawdown: -$1,000 (-10%)
- Max Daily Loss: -$500 (-5%)
Evaluates different strategies:
Strategy 1: Rapid 1-Minute Micro-Scalper (Over-leveraged, 15 trades/day)
Strategy 2: Institutional ICT Sniper (1% risk, 1:2 R:R, 1-2 trades/day, 48% Win Rate)
Strategy 3: Conservative ICT Swing (0.5% risk, 1:2.5 R:R, 1 trade/day, 45% Win Rate)
"""

import numpy as np

def simulate_strategy(name, win_rate, rr, risk_pct, trades_per_day, n_simulations=5000):
    account_size = 10000.0
    profit_target = 1000.0  # +10%
    max_loss = 1000.0       # -10%
    daily_loss_limit = 500.0 # -5%

    passed = 0
    blown_max_loss = 0
    blown_daily_loss = 0
    days_to_pass = []

    for _ in range(n_simulations):
        balance = account_size
        day = 1
        current_daily_loss = 0

        while True:
            # Simulate a day's trades
            day_pnl = 0
            failed_daily = False

            for _ in range(trades_per_day):
                risk_usd = balance * (risk_pct / 100.0)
                reward_usd = risk_usd * rr

                # Coin flip based on win rate
                is_win = np.random.rand() < win_rate
                trade_pnl = reward_usd if is_win else -risk_usd

                balance += trade_pnl
                day_pnl += trade_pnl

                # Check Max Loss
                if balance <= (account_size - max_loss):
                    blown_max_loss += 1
                    failed_daily = True
                    break

                # Check Daily Loss
                if day_pnl <= -daily_loss_limit:
                    blown_daily_loss += 1
                    failed_daily = True
                    break

                # Check Target Hit
                if balance >= (account_size + profit_target):
                    passed += 1
                    days_to_pass.append(day)
                    failed_daily = True
                    break

            if failed_daily or balance >= (account_size + profit_target) or balance <= (account_size - max_loss):
                break

            day += 1
            if day > 180: # timeout after 6 months
                break

    pass_rate = (passed / n_simulations) * 100
    fail_rate = ((blown_max_loss + blown_daily_loss) / n_simulations) * 100
    avg_days = np.mean(days_to_pass) if days_to_pass else 0

    return {
        "name": name,
        "pass_rate": pass_rate,
        "fail_rate": fail_rate,
        "avg_days": avg_days,
        "blown_daily": (blown_daily_loss / n_simulations) * 100,
        "blown_max": (blown_max_loss / n_simulations) * 100,
    }

print("=" * 75)
print("     MONTE CARLO PROP FIRM PASSING SIMULATION (5,000 CHALLENGES)")
print("=" * 75)

res1 = simulate_strategy("1. Rapid M1 Scalper (Chop, 15 trades/day, 35% WR, 1:1.2 RR, 0.5% risk)",
                         win_rate=0.35, rr=1.2, risk_pct=0.5, trades_per_day=15)

res2 = simulate_strategy("2. ICT Sniper (London/NY Open, 1-2 trades/day, 48% WR, 1:2.0 RR, 1.0% risk)",
                         win_rate=0.48, rr=2.0, risk_pct=1.0, trades_per_day=2)

res3 = simulate_strategy("3. Conservative ICT (Kill Zones, 1 trade/day, 46% WR, 1:2.5 RR, 0.75% risk)",
                         win_rate=0.46, rr=2.5, risk_pct=0.75, trades_per_day=1)

for r in [res1, res2, res3]:
    print(f"\n{r['name']}:")
    print(f"  PASS RATE:           {r['pass_rate']:5.1f}% 🎯")
    print(f"  FAIL / BLOW RATE:    {r['fail_rate']:5.1f}% ⚠️ (Daily Loss Violations: {r['blown_daily']:.1f}%)")
    print(f"  AVG TIME TO PASS:    {r['avg_days']:5.1f} Trading Days (~{r['avg_days']/5:.1f} weeks)")

print("\n" + "=" * 75)
