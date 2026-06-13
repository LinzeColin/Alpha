# Alpha Decision Log

## 2026-06-13: GitHub Is Authoritative

Decision: Use `https://github.com/LinzeColin/Alpha` as the authoritative project backup and continuity surface.

Reason: Future agents need a stable, inspectable state source for code, docs, tests, rules, and handoff.

Consequence: Every meaningful run must commit and push code/docs/test evidence unless blocked.

## 2026-06-13: Execution Boundary

Decision: Alpha will automate paper trading, risk checks, approval queues, and broker-ready order tickets. It will not autonomously submit real-money broker orders.

Reason: Trading systems must preserve owner control at the real-money execution boundary.

Consequence: Committed defaults keep `live_trading.enabled: false`; live candidates enter an approval queue as tickets.

## 2026-06-13: Five-Minute Candidate Refresh

Decision: The order-intent loop has a default refresh cadence of 300 seconds.

Reason: The user requires timely candidate updates while still keeping risk checks and review gates explicit.

Consequence: `paper_trading_loop.run_forever()` remains available for CLI use, and the FastAPI dashboard lifecycle starts an app-managed automatic paper loop that runs immediately and then sleeps for the configured interval.
