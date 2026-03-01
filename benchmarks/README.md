# Benchmarks

This directory holds Becker backtest output CSV files used to populate the `benchmarks` database table.

## Expected Files

| File | Source | Description |
|------|--------|-------------|
| `politics_drill.csv` | `backtest_four_drills.py` | Politics subcategory benchmarks |
| `entertainment_drill.csv` | `backtest_four_drills.py` | Entertainment benchmarks |
| `world_events_drill.csv` | `backtest_four_drills.py` | World events benchmarks |
| `business_drill.csv` | `backtest_four_drills.py` | Business/corporate benchmarks |
| `backtest_cat_overview.csv` | `backtest_categories_deep.py` | Top-level category overview |
| `mlb_drill.csv` | `backtest_drilldowns.py` | MLB sports benchmarks |
| `tennis_drill.csv` | `backtest_drilldowns.py` | Tennis benchmarks |

## Import

After running migrations, import all files:

```bash
python scripts/import_benchmarks.py benchmarks/
```

Or from inside the API container:

```bash
docker-compose exec api python scripts/import_benchmarks.py /benchmarks
```
