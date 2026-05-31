from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = [
    "bet_id",
    "customer_id",
    "bet_datetime",
    "bet_num",
    "betting_amount",
    "price",
    "category",
    "stake_type",
    "bet_result",
    "payout",
    "return_for_entain",
]

ALLOWED_CATEGORIES = {"sports", "racing"}
ALLOWED_STAKE_TYPES = {"cash", "bonus"}
ALLOWED_RESULTS = {"return", "no-return"}
FLOAT_TOLERANCE = 1e-6


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_bets(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def expected_payout(row: pd.Series) -> float:
    if row["bet_result"] == "no-return":
        return 0.0
    if row["stake_type"] == "cash":
        return row["betting_amount"] * row["price"]
    return row["betting_amount"] * (row["price"] - 1.0)


def expected_return_for_entain(row: pd.Series) -> float:
    if row["bet_result"] == "no-return" and row["stake_type"] == "cash":
        return row["betting_amount"]
    if row["bet_result"] == "no-return" and row["stake_type"] == "bonus":
        return 0.0
    if row["bet_result"] == "return" and row["stake_type"] == "cash":
        return row["betting_amount"] - row["payout"]
    return -row["payout"]


def _is_uuid(value: object) -> bool:
    try:
        uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return False
    return True


def _close_enough(actual: object, expected: float) -> bool:
    try:
        actual_float = float(actual)
    except (TypeError, ValueError):
        return False
    return math.isclose(actual_float, expected, rel_tol=FLOAT_TOLERANCE, abs_tol=FLOAT_TOLERANCE)


def validate_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    checked = df.copy()
    checked["_row_number"] = checked.index + 2
    checked["validation_errors"] = ""

    def add_error(mask: pd.Series, rule: str) -> None:
        checked.loc[mask, "validation_errors"] = checked.loc[mask, "validation_errors"].apply(
            lambda current: rule if not current else f"{current};{rule}"
        )

    numeric_columns = ["bet_id", "bet_num", "betting_amount", "price", "payout", "return_for_entain"]
    parsed = {column: pd.to_numeric(checked[column], errors="coerce") for column in numeric_columns}
    parsed_datetime = pd.to_datetime(checked["bet_datetime"], errors="coerce")

    add_error(parsed["bet_id"].isna(), "bet_id_is_integer")
    add_error(parsed["bet_id"].notna() & (parsed["bet_id"] % 1 != 0), "bet_id_is_integer")
    add_error(parsed["bet_id"].duplicated(keep=False), "bet_id_is_unique")
    add_error(~checked["customer_id"].map(_is_uuid), "customer_id_is_uuid")
    add_error(parsed_datetime.isna(), "bet_datetime_is_parseable")
    add_error(parsed["bet_num"].isna(), "bet_num_is_integer")
    add_error(parsed["bet_num"].notna() & (parsed["bet_num"] % 1 != 0), "bet_num_is_integer")
    add_error(parsed["bet_num"].notna() & (parsed["bet_num"] < 1), "bet_num_is_positive")
    add_error(parsed["betting_amount"].isna() | (parsed["betting_amount"] <= 0), "betting_amount_gt_0")
    add_error(parsed["price"].isna() | (parsed["price"] <= 1), "price_gt_1")
    add_error(~checked["category"].isin(ALLOWED_CATEGORIES), "category_allowed")
    add_error(~checked["stake_type"].isin(ALLOWED_STAKE_TYPES), "stake_type_allowed")
    add_error(~checked["bet_result"].isin(ALLOWED_RESULTS), "bet_result_allowed")
    add_error(parsed["payout"].isna(), "payout_is_numeric")
    add_error(parsed["return_for_entain"].isna(), "return_for_entain_is_numeric")

    duplicate_order = checked.assign(_bet_num=parsed["bet_num"]).duplicated(
        ["customer_id", "_bet_num"], keep=False
    )
    add_error(duplicate_order, "customer_bet_num_is_unique")

    typed = checked.assign(
        bet_id=parsed["bet_id"],
        bet_num=parsed["bet_num"],
        betting_amount=parsed["betting_amount"],
        price=parsed["price"],
        payout=parsed["payout"],
        return_for_entain=parsed["return_for_entain"],
        bet_datetime=parsed_datetime,
    )

    payout_prerequisites = (
        parsed["betting_amount"].notna()
        & parsed["price"].notna()
        & parsed["payout"].notna()
        & checked["stake_type"].isin(ALLOWED_STAKE_TYPES)
        & checked["bet_result"].isin(ALLOWED_RESULTS)
    )
    payout_mismatch = payout_prerequisites & ~typed.apply(
        lambda row: _close_enough(row["payout"], expected_payout(row)), axis=1
    )
    add_error(payout_mismatch, "payout_matches_contract")

    typed = checked.assign(
        bet_id=parsed["bet_id"],
        bet_num=parsed["bet_num"],
        betting_amount=parsed["betting_amount"],
        price=parsed["price"],
        payout=parsed["payout"],
        return_for_entain=parsed["return_for_entain"],
        bet_datetime=parsed_datetime,
    )
    return_prerequisites = (
        parsed["betting_amount"].notna()
        & parsed["payout"].notna()
        & parsed["return_for_entain"].notna()
        & checked["stake_type"].isin(ALLOWED_STAKE_TYPES)
        & checked["bet_result"].isin(ALLOWED_RESULTS)
    )
    return_mismatch = return_prerequisites & ~typed.apply(
        lambda row: _close_enough(row["return_for_entain"], expected_return_for_entain(row)), axis=1
    )
    add_error(return_mismatch, "return_for_entain_matches_contract")

    typed = checked.assign(
        bet_id=parsed["bet_id"].astype("Int64"),
        bet_num=parsed["bet_num"].astype("Int64"),
        betting_amount=parsed["betting_amount"],
        price=parsed["price"],
        payout=parsed["payout"],
        return_for_entain=parsed["return_for_entain"],
        bet_datetime=parsed_datetime,
    )

    invalid_mask = typed["validation_errors"].ne("")
    valid = typed.loc[~invalid_mask, REQUIRED_COLUMNS + ["_row_number"]].copy()
    invalid = typed.loc[invalid_mask, REQUIRED_COLUMNS + ["_row_number", "validation_errors"]].copy()

    failure_counts: dict[str, int] = {}
    for errors in invalid["validation_errors"]:
        for rule in str(errors).split(";"):
            failure_counts[rule] = failure_counts.get(rule, 0) + 1

    report = {
        "generated_at": utc_now_iso(),
        "total_rows": int(len(typed)),
        "valid_rows": int(len(valid)),
        "invalid_rows": int(len(invalid)),
        "failure_counts_by_rule": dict(sorted(failure_counts.items())),
    }
    return valid, invalid, report


def write_validation_outputs(valid: pd.DataFrame, invalid: pd.DataFrame, report: dict, output_dir: str | Path) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    valid.to_parquet(output_path / "valid_bets.parquet", index=False)
    invalid.to_parquet(output_path / "invalid_bets.parquet", index=False)
    with (output_path / "validation_report.json").open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)


def run_validation(input_path: str | Path, output_dir: str | Path) -> dict:
    valid, invalid, report = validate_dataframe(read_bets(input_path))
    write_validation_outputs(valid, invalid, report, output_dir)
    return report
