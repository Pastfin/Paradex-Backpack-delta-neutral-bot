# Paradex + Backpack Delta Neutral Bot

Parallel trading bot for Paradex and Backpack with multi-threading. Supports multiple accounts, monitoring LTV per trade, and stopping individual threads if limits are exceeded. Based on the original Paradex bot.

## Setup
- Clone: `git clone https://github.com/Pastfin/Paradex-Backpack-delta-neutral-bot`
- Install: `pip install -r requirements.txt` (use Docker/Linux if issues arise)

## Configuration
- `data/accounts_backpack.xlsx`: Add `api_key`, `api_secret`, `proxy`, `is_active`  
  - API keys can be created here: [Backpack API Settings](https://backpack.exchange/portfolio/settings/api-keys)
- `data/accounts_paradex.xlsx`: Same format as the original Paradex bot.
- `data/active_pairs.xlsx`: Contains trading pairs available on both Paradex and Backpack. Keep only the pairs you want to trade.
- `data/config.json`: Same parameters as the original bot (`order_value_usd`, `accounts_per_trade`, etc.)

## Features
- Start Trading: Opens delta-neutral positions across Paradex and Backpack.
- Close Positions: Closes all active trades.
- Volume Monitoring & Pair Selection: Collects volume data and allows convenient selection of trading pairs.

Full guide: [Instructions](https://teletype.in/@pastfin/A_1fEYZvl5C)