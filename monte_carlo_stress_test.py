import numpy as np

np.random.seed(42)

def simulate(rr, win_rate, risk=75.0, start_bal=9988.73, n_sims=10000, max_trades=100):
    reward = risk * rr
    expectancy = (win_rate * reward) - ((1 - win_rate) * risk)
    
    reach_10500 = 0
    reach_11000 = 0
    dd_breaches = 0
    max_dds = []
    trades_to_10500 = []
    
    for _ in range(n_sims):
        bal = start_bal
        trades = 0
        hit_500 = False
        hit_1000 = False
        peak = bal
        max_dd = 0
        
        while trades < max_trades:
            trades += 1
            win = np.random.rand() < win_rate
            if win:
                bal += reward
            else:
                bal -= risk
            
            dd = peak - bal
            if dd > max_dd:
                max_dd = dd
            if bal > peak:
                peak = bal
                
            if bal >= 10500 and not hit_500:
                hit_500 = True
                trades_to_10500.append(trades)
            if bal >= 11000:
                hit_1000 = True
                break
            if bal <= 9500: # breach $500 daily buffer
                dd_breaches += 1
                break
                
        if hit_500: reach_10500 += 1
        if hit_1000: reach_11000 += 1
        max_dds.append(max_dd)
        
    return {
        'rr': f"1:{rr}",
        'win_rate': f"{int(win_rate*100)}%",
        'reward': f"${reward:.2f}",
        'expectancy_per_trade': round(expectancy, 2),
        'prob_10500_pct': round((reach_10500 / n_sims) * 100, 1),
        'prob_11000_pct': round((reach_11000 / n_sims) * 100, 1),
        'dd_breach_pct': round((dd_breaches / n_sims) * 100, 2),
        'avg_max_dd': round(np.mean(max_dds), 2),
        'p95_max_dd': round(np.percentile(max_dds, 95), 2),
        'avg_trades_to_500': round(np.mean(trades_to_10500) if trades_to_10500 else 0, 1)
    }

scenarios = [
    # 1:1.0 RR (Win +$75)
    (1.0, 0.60), (1.0, 0.65), (1.0, 0.70),
    # 1:2.0 RR (Win +$150)
    (2.0, 0.45), (2.0, 0.50), (2.0, 0.55), (2.0, 0.60),
    # 1:3.0 RR (Win +$225)
    (3.0, 0.35), (3.0, 0.40), (3.0, 0.45), (3.0, 0.50)
]

print(f"{'RR':<6} | {'Reward':<8} | {'WinRate':<8} | {'Expectancy':<11} | {'P(+5%)':<8} | {'P(+10%)':<9} | {'DD Breach %':<12} | {'Avg Max DD':<11} | {'95% Max DD':<11} | {'Avg Trades to +5%'}")
print("-" * 115)
for rr, wr in scenarios:
    r = simulate(rr, wr)
    print(f"{r['rr']:<6} | {r['reward']:<8} | {r['win_rate']:<8} | ${r['expectancy_per_trade']:<10} | {r['prob_10500_pct']:<7}% | {r['prob_11000_pct']:<8}% | {r['dd_breach_pct']:<11}% | ${r['avg_max_dd']:<10} | ${r['p95_max_dd']:<10} | {r['avg_trades_to_500']}")
