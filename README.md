# Entain Bet Pipeline

Batch oriented Python pipeline for the `bets.csv` data file. It validates raw betting records, writes invalid records explicitly, and builds customer-level features from each customer's first 20 bets.

## Project shape

```text
candidate_submission/
  pyproject.toml
  setup.py
  Dockerfile
  README.md
  src/bet_pipeline/
  tests/
  docs/
  outputs/
```

## Commands

The CLI accepts any CSV path through `--input`. The example commands below assume the repository is next to a `data/` folder that contains `bets.csv`:

```text
JobApplications/
  data/
    bets.csv
  candidate_submission/
```

From the project directory:

```bash
python -m pip install -e .
bet-pipeline validate --input ../data/bets.csv --output outputs/validation/
bet-pipeline build-features --input ../data/bets.csv --output outputs/features/
```

If your file is somewhere else, replace `../data/bets.csv` with that path.

Equivalent runnable modules:

```bash
PYTHONPATH=src python -m bet_pipeline.cli validate --input ../data/bets.csv --output outputs/validation/
PYTHONPATH=src python -m bet_pipeline.cli build-features --input ../data/bets.csv --output outputs/features/
```

## Docker

```bash
docker build -t entain-bet-pipeline .
docker run --rm -v $(pwd)/../data:/data -v $(pwd)/outputs:/outputs entain-bet-pipeline validate --input /data/bets.csv --output /outputs/validation/
docker run --rm -v $(pwd)/../data:/data -v $(pwd)/outputs:/outputs entain-bet-pipeline build-features --input /data/bets.csv --output /outputs/features/
```

## Validation outputs

`bet-pipeline validate` writes:

- `valid_bets.parquet`
- `invalid_bets.parquet`
- `validation_report.json`

Invalid rows are not silently ignored. Each invalid row includes `validation_errors`, a semicolon-separated list of failed rules. The report includes row counts and failure counts by rule.

Validation covers:

- required columns
- `bet_id` integer and unique
- `customer_id` UUID format
- parseable `bet_datetime`
- integer positive `bet_num`
- unique `customer_id` and `bet_num` pairs
- `betting_amount > 0`
- `price > 1`
- allowed `category`, `stake_type`, and `bet_result`
- payout contract
- `return_for_entain` contract

## Feature output

`bet-pipeline build-features` writes:

- `customer_features.parquet`

Parquet is used because `pyarrow` is available in the package dependencies and it preserves column types better than CSV for downstream ML consumers.

The feature job validates the raw input first, then builds customer features from validated rows with `bet_num` between 1 and 20. If invalid records appear in a customer's first 20 raw bets, those records are excluded and `bets_used` shows how many valid first-20 records contributed. This keeps the behavior deterministic and makes affected customers visible to downstream checks. In other words, the deterministic rule is to take valid records where `bet_num` is between 1 and 20, grouped by `customer_id`. If a customer has an invalid raw record with `bet_num = 7`, that row is not replaced by `bet_num = 21`; it is excluded, and the customer's `bets_used` becomes 19 if the other first-20 rows are valid. This keeps the feature definition stable: every run with the same input and rules uses the same bet-number window and produces the same result, except for `feature_generated_at`.

Feature columns:

- `customer_id`
- `first_bet_datetime`
- `twentieth_bet_datetime`
- `bets_used`
- `total_betting_amount`
- `mean_betting_amount`
- `mean_price`
- `pct_racing`
- `pct_cash`
- `pct_return`
- `total_payout`
- `total_return_for_entain`
- `feature_generated_at`

## Tests

After installing the package:

```bash
python -m pip install -e .
python -m unittest discover -s tests
```

Or, without installing the package:

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

If editable install fails in an older or offline Python environment, upgrade packaging tools first:

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
```

If package installation is not possible, the pipeline can still be run with the module form shown above, as long as `pandas` and `pyarrow` are available in the Python environment.

## Design documents

- [Architecture diagram](docs/architecture.md)
- [Design note](docs/design_note.md)
