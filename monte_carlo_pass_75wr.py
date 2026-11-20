"""
Monte Carlo Simulation: 75% Win-Rate GBPUSD/EURUSD Institutional Setup
══════════════════════════════════════════════════════════════════════
Simulates 10,000 challenge runs on FTMO / The5ers rules.
"""

import numpy as np

def run_simulation():
    N_RUNS = 10000
    WIN_RATE = 0.75       # 75% backtested win rate on GBPUSD & EURUSD FVG retests
    RR = 1.2             # 1:1.2 Risk to Reward
    RISK_USD = 80.0      # 0.8% risk per trade ($80 loss on SL)
    REWARD_USD = RISK_USD * RR  # $96 profit on TP
    
    DAILY_LOSS_LIMIT = 500.0
    MAX_LOSS_LIMIT = 1000.0
    PROFIT_TARGET = 1000.0
    
    passed_count = 0
    failed_daily_count = 0
    failed_max_count = 0
    trades_to_pass = []

    for _ in range(N_RUNS):
        balance = 10000.0
        peak = 10000.0
        trades_today = 0
        pnl_today = 0.0
        total_trades = 0
        failed = False
        
        while balance < 10000.0 + PROFIT_TARGET:
            # 1 to 2 trades per day
            total_trades += 1
            trades_today += 1
            
            # Outcome
            is_win = np.random.random() < WIN_RATE
            pnl = REWARD_USD if is_win else -RISK_USD
            
            balance += pnl
            pnl_today += pnl
            if balance > peak:
                peak = balance
                
            # Check Daily Loss
            if pnl_today <= -DAILY_LOSS_LIMIT:
                failed_daily_count += 1
                failed = True
                break
                
            # Check Max Loss
            if (10000.0 - balance) >= MAX_LOSS_LIMIT:
                failed_max_count += 1
                failed = True
                break
                
            # New trading day after 2 trades
            if trades_today >= 2:
                trades_today = 0
                pnl_today = 0.0
                
            # Timeout guard (max 200 trades)
            if total_trades > 200:
                failed = True
                break
                
        if not failed and balance >= 10000.0 + PROFIT_TARGET:
            passed_count += 1
            trades_to_pass.append(total_trades)

    pass_rate = (passed_count / N_RUNS) * 100
    avg_trades = np.mean(trades_to_pass) if trades_to_pass else 0
    avg_days = avg_trades / 1.5 # ~1.5 trades per day

    print("=" * 70)
    print("      MONTE CARLO PASSING PROBABILITY (10,000 SIMULATIONS)")
    print("=" * 70)
    print(f"Strategy:              GBPUSD & EURUSD Kill Zone FVG Retest")
    print(f"Win Rate:              {WIN_RATE * 100:.1f}%")
    print(f"Risk:Reward:           1:{RR:.1f}")
    print(f"Risk Per Trade:        ${RISK_USD:.2f} (0.8% of $10,000)")
    print(f"Reward Per Trade:      ${REWARD_USD:.2f} (+{RR*0.8:.2f}%)")
    print(f"Pass Rate:             {pass_rate:.2f}% 🔥🔥🔥")
    print(f"Daily Breach Rate:     {(failed_daily_count / N_RUNS) * 100:.2f}%")
    print(f"Max Drawdown Breach:   {(failed_max_count / N_RUNS) * 100:.2f}%")
    print(f"Average Trades to Pass:{avg_trades:.1f} trades")
    print(f"Average Days to Pass:  {avg_days:.1f} trading days (~2 to 3 weeks)")
    print("=" * 70)

if __name__ == "__main__":
    run_simulation()
