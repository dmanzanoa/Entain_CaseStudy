from __future__ import annotations

from pathlib import Path

import pandas as pd

from bet_pipeline.validate import read_bets, utc_now_iso, validate_dataframe


FEATURE_COLUMNS = [
    "customer_id",
    "first_bet_datetime",
    "twentieth_bet_datetime",
    "bets_used",
    "total_betting_amount",
    "mean_betting_amount",
    "mean_price",
    "pct_racing",
    "pct_cash",
    "pct_return",
    "total_payout",
    "total_return_for_entain",
    "feature_generated_at",
]


def build_customer_features(valid_bets: pd.DataFrame, generated_at: str | None = None) -> pd.DataFrame:
    generated_at = generated_at or utc_now_iso()
    first_twenty = valid_bets.loc[valid_bets["bet_num"].between(1, 20)].copy()
    if first_twenty.empty:
        return pd.DataFrame(columns=FEATURE_COLUMNS)

    first_twenty = first_twenty.sort_values(["customer_id", "bet_num", "bet_datetime", "bet_id"])
    grouped = first_twenty.groupby("customer_id", sort=True)

    features = grouped.agg(
        first_bet_datetime=("bet_datetime", "min"),
        bets_used=("bet_id", "count"),
        total_betting_amount=("betting_amount", "sum"),
        mean_betting_amount=("betting_amount", "mean"),
        mean_price=("price", "mean"),
        pct_racing=("category", lambda values: (values == "racing").mean()),
        pct_cash=("stake_type", lambda values: (values == "cash").mean()),
        pct_return=("bet_result", lambda values: (values == "return").mean()),
        total_payout=("payout", "sum"),
        total_return_for_entain=("return_for_entain", "sum"),
    ).reset_index()

    twentieth = first_twenty.loc[first_twenty["bet_num"].eq(20), ["customer_id", "bet_datetime"]].rename(
        columns={"bet_datetime": "twentieth_bet_datetime"}
    )
    features = features.merge(twentieth, on="customer_id", how="left")
    features["feature_generated_at"] = generated_at
    return features[FEATURE_COLUMNS].sort_values("customer_id").reset_index(drop=True)


def write_feature_outputs(features: pd.DataFrame, output_dir: str | Path) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    features.to_parquet(output_path / "customer_features.parquet", index=False)


def run_build_features(input_path: str | Path, output_dir: str | Path) -> pd.DataFrame:
    valid_bets, _, _ = validate_dataframe(read_bets(input_path))
    features = build_customer_features(valid_bets)
    write_feature_outputs(features, output_dir)
    return features
