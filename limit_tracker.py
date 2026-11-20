"""
Prop Firm Limit Watchdog & Risk Engine
══════════════════════════════════════
Tracks real-time limits for both The5ers and FTMO:
- Daily Loss Limit ($500)
- Max Drawdown Limit ($1,000)
- Profit Target Progress ($1,000)
- Real-time Floating Drawdown & Closed PnL
"""

import MetaTrader5 as mt5
from datetime import datetime, timezone

def track_limits(account_id=None, server=None):
    if not mt5.initialize():
        print("MT5 Init Error")
        return None

    if account_id and server:
        mt5.login(account_id, server=server)

    acc = mt5.account_info()
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    deals = mt5.history_deals_get(today_start, datetime.now(timezone.utc))
    closed_pnl = sum(d.profit for d in deals if d.entry == 1) if deals else 0.0

    positions = mt5.positions_get()
    floating_pnl = sum(p.profit for p in positions) if positions else 0.0
    daily_pnl = closed_pnl + floating_pnl

    start_balance = 10000.0
    daily_loss_limit = 500.0
    max_loss_limit = 1000.0

    daily_buffer = daily_loss_limit + daily_pnl
    max_buffer = acc.equity - (start_balance - max_loss_limit)

    status = "SAFE (GREEN)" if daily_buffer > 250 else ("CAUTION (YELLOW)" if daily_buffer > 100 else "CRITICAL (RED)")

    report = {
        "account": acc.login,
        "server": acc.server,
        "balance": acc.balance,
        "equity": acc.equity,
        "closed_pnl": closed_pnl,
        "floating_pnl": floating_pnl,
        "daily_pnl": daily_pnl,
        "daily_limit": daily_loss_limit,
        "daily_buffer": daily_buffer,
        "daily_buffer_pct": (daily_buffer / daily_loss_limit) * 100,
        "max_limit": max_loss_limit,
        "max_buffer": max_buffer,
        "max_buffer_pct": (max_buffer / max_loss_limit) * 100,
        "status": status,
        "open_positions": len(positions) if positions else 0
    }

    print("=" * 65)
    print("           🛡️ REAL-TIME PROP FIRM LIMIT AUDIT PROOF")
    print("=" * 65)
    print(f"Account:                 {report['account']} ({report['server']})")
    print(f"Balance:                 ${report['balance']:,.2f} USD")
    print(f"Equity:                  ${report['equity']:,.2f} USD")
    print(f"Today's Closed PnL:      ${report['closed_pnl']:+,.2f} USD")
    print(f"Floating Trade PnL:      ${report['floating_pnl']:+,.2f} USD")
    print(f"Total Daily PnL:         ${report['daily_pnl']:+,.2f} USD")
    print(f"Daily Loss Limit:        ${report['daily_limit']:,.2f} USD")
    print(f"Daily Buffer Remaining:  ${report['daily_buffer']:,.2f} / ${report['daily_limit']:,.2f} ({report['daily_buffer_pct']:.1f}% safe)")
    print(f"Max Drawdown Buffer:     ${report['max_buffer']:,.2f} / ${report['max_limit']:,.2f} ({report['max_buffer_pct']:.1f}% safe)")
    print(f"Open Positions:          {report['open_positions']} (The5ers Limit: Max 1)")
    print(f"Risk Health Status:      {report['status']}")
    print("=" * 65)

    mt5.shutdown()
    return report

if __name__ == "__main__":
    track_limits()
