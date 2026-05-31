# Design Note

## Components and Responsibilities

The raw betting data landing area stores the delivered `bets.csv` file as untrusted input. The batch scheduler or job trigger starts the local workflow and passes input and output paths to the pipeline.

The validation job owns the business contract. It checks required columns, identifiers, ordering fields, numeric constraints, allowed domains, `payout`, and `return_for_entain`. It writes valid records to the curated validated-bets layer and invalid records plus a machine-readable report to quarantine.

The curated validated-bets layer is the clean input for downstream work. It contains only rows that passed the rules. The invalid-record quarantine contains the original invalid rows with explicit failed-rule names so an operator can inspect and correct source issues.

The customer feature generation job reads validated bets and creates customer-level features from valid records whose `bet_num` is between 1 and 20. In a broader ML system the output is versionable by path or run timestamp, for example `features/run_date=2026-05-31/customer_features.parquet` or `features/source_snapshot=2024-10-bets-v1/customer_features.parquet`, and can be loaded into a feature store or serving table. In the local implementation, feature output versioning is minimal: the pipeline writes to the output path provided by the CLI and includes `feature_generated_at` in the generated dataset.

The metadata, schema-contract, and configuration layer defines the data contract that every pipeline run must follow. For the raw bets input, it would define required columns, expected types, allowed values, primary-key expectations, ordering expectations, payout rules, `return_for_entain` rules, and stable validation-rule names. For the customer feature output, it would define feature names, types, source columns, aggregation formulas, and the first-20-bets window. In this local implementation those rules live in code constants such as `REQUIRED_COLUMNS`, `ALLOWED_CATEGORIES`, `ALLOWED_STAKE_TYPES`, and `ALLOWED_RESULTS`. In production, the same contract could be versioned separately, reviewed before changes are released, and stored with run metadata so downstream consumers know exactly which schema and feature-definition version produced a dataset.

Logging, monitoring, and alerting capture row counts, invalid counts, failure counts by rule, feature row counts, runtime, and failed jobs. Alerts should fire on job failure, missing input, schema changes, large invalid-rate changes, and unexpected drops in customer feature counts.

Downstream consumers include batch model training, batch scoring, BI and analytics, CRM activation, and operational decisioning. They consume the feature table through a documented schema: stable column names, types, generation time, and clear semantics for `bets_used`.

The rerun, backfill, and correction path starts when source data changes or defects are found in quarantine. Corrected data is landed again, the validation job reruns, and feature output is regenerated for the affected data window or full dataset. Outputs should be written deterministically so repeated runs with the same input produce the same validated rows and feature values except for generation timestamps.

## Batch Processing Choice

Batch processing fits this task because the input is a CSV file and the requested features are customer aggregates over the first 20 bets. A local batch job is simpler to reproduce, test, and rerun than a streaming system.

Streaming might fit if features needed to update immediately after every bet or power real-time operational decisions. Even then, the same validation contract and feature definitions would need to be shared with the streaming path to avoid training-serving skew.

## Schema Safety

The pipeline validates required columns before processing. Rule names are stable and included in `validation_report.json`, which makes failures machine-readable. In production, schema versions would be recorded with each output, and downstream consumers would depend on a compatibility policy for column additions, removals, and semantic changes.

A metadata and schema-contract layer would describe both the input contract and the feature-output contract. For the raw `bets.csv` input, the contract would include required column names, expected data types, allowed values, nullable fields, primary-key expectations, ordering expectations, and business rules such as `betting_amount > 0`, `price > 1`, payout formulas, and `return_for_entain` formulas. Each rule would have a stable rule identifier, for example `price_gt_1` or `payout_matches_contract`, so validation reports can be compared across runs.

For the customer feature output, the contract would define each feature name, type, aggregation logic, source fields, and feature window. For example, `total_betting_amount` would be documented as the sum of `betting_amount` over valid bets where `bet_num` is between 1 and 20, grouped by `customer_id`. `pct_racing` would be documented as the share of those valid first-20 bets where `category == "racing"`. This protects downstream training, scoring, BI, and CRM users from silently changing feature definitions.

Each published output would also carry run metadata such as source file or source snapshot identifier, schema version, feature-definition version, pipeline code version, generation timestamp, row counts, invalid-record counts, and validation status. In this local exercise, `validation_report.json` and `feature_generated_at` provide a small version of that idea. In a production ML system, the same metadata would be stored next to the output dataset or in a metadata table so a model training run can later answer exactly which data contract and feature definitions produced its training data.

Schema evolution should be explicit. Adding a new optional feature can be backward compatible, but removing a feature, renaming a feature, changing a type, or changing an aggregation definition should create a new feature-definition version and require downstream consumer review. This prevents training-serving skew and avoids breaking batch scoring jobs that expect a stable feature table.

## Invalid Records

Invalid records are isolated in `invalid_bets.parquet` with `_row_number` and `validation_errors`. `_row_number` points back to the original CSV line, and `validation_errors` lists the failed rule names, such as `betting_amount_gt_0`, `price_gt_1`, or `payout_matches_contract`. The validation job also writes `validation_report.json`, which surfaces total invalid rows and failure counts by rule. In production, these outputs would be sent to operators through job logs, dashboards, and alerts when invalid counts are above expected thresholds or when new rule failures appear.

Operators would investigate invalid rows from the quarantine output rather than searching the raw file manually. For example, they could filter `invalid_bets.parquet` for `payout_matches_contract`, inspect the affected `_row_number`, compare the source values with the contract, and decide whether the issue is a source-system defect, a data-entry defect, or a contract change that needs review. Corrected source data would then be re-landed and the batch pipeline rerun, producing a fresh validation report and feature output.

The feature job validates the raw input first and only uses rows that pass validation. For the first-20-bets feature window, the deterministic rule is: take valid records where `bet_num` is between 1 and 20, grouped by `customer_id`. If a customer has an invalid raw record with `bet_num = 7`, that row is not replaced by `bet_num = 21`; it is excluded, and the customer's `bets_used` becomes 19 if the other first-20 rows are valid. This keeps the feature definition stable: every run with the same input and rules uses the same bet-number window and produces the same result, except for `feature_generated_at`.

## Feature Consistency

Feature consistency means that every producer and consumer uses the same definition for a feature over time. For example, `total_betting_amount` means the sum of `betting_amount` over valid bets where `bet_num` is between 1 and 20. `pct_cash` means the share of those same valid first-20 bets where `stake_type == "cash"`. These definitions should not change silently, because a model trained with one interpretation of a feature may behave incorrectly if batch scoring later uses a different interpretation.

In this local implementation, feature definitions live in package code and tests. The code defines the selected window, grouping key, aggregation formulas, and output column names. The tests protect some of the expected behavior, such as excluding bets with `bet_num > 20`. The README also documents the output columns and the handling of invalid first-20 records.

In production, each feature definition should be published with metadata such as owner, description, source columns, source table, aggregation logic, feature window, expected type, null-handling behavior, and version. Training, scoring, BI, CRM, and operational consumers would read from the same versioned feature output or feature store table. If a definition changes, such as changing the window from first 20 bets to first 30 bets, that should create a new feature-definition version and trigger downstream review rather than silently overwriting the old meaning.

A shared feature contract or feature registry should be the source of truth. Each feature would be defined once with its name, type, units, owner, freshness expectation, null-handling rule, transformation logic, and version. Producers would be validated against that contract before publishing features, including schema, types, ranges, timestamps, and semantic checks. Consumers would bind to a feature name and version from the registry rather than copying transformation logic into model-training, scoring, or reporting code. Automated tests, data quality checks, drift checks, and alerts would detect when produced feature values no longer match expectations. In short, consistency comes from centralized definitions, enforced schemas, versioned semantics, and automated validation.

## Downstream Consumption

Downstream systems consume the customer feature output as a stable table keyed by `customer_id`. In this local implementation, the interface is the `customer_features.parquet` file written by the feature job. Its contract is the documented set of feature columns, their data types, and their meanings, including the fact that all aggregates are based on valid bets where `bet_num` is between 1 and 20.

Batch model training would read a versioned feature snapshot and join it to labels by `customer_id`. Batch scoring would read the same feature columns and apply a trained model to produce predictions. BI and analytics tools would use the feature table for customer-level reporting. CRM activation or operational decisioning systems could consume selected features such as `pct_return`, `total_betting_amount`, or `total_return_for_entain` to support campaigns or decisions.

The contract these consumers rely on is not only the file format. They rely on stable column names, expected types, feature-definition versions, generation timestamp, source snapshot metadata, and documented handling of incomplete first-20 windows through `bets_used`. In production, consumers should bind to a specific feature set version or schema version so a breaking feature change does not silently affect training, scoring, or reporting jobs.

## Logging, Metrics, and Alerts

In production, each batch run should log the input path or source snapshot, output paths, pipeline version, schema version, feature-definition version, start time, end time, runtime, and final status. The validation job should log total rows, valid rows, invalid rows, invalid-rate percentage, failure counts by rule, and examples or references to quarantined records. The feature job should log customer feature row count, distribution of `bets_used`, missing `twentieth_bet_datetime` count, null counts by feature, and basic numeric summaries for important features such as `total_betting_amount`, `mean_price`, `total_payout`, and `total_return_for_entain`.

Metrics should be stored over time so operators can compare each run with previous runs. Useful measures include input row-count changes, invalid-rate trends, rule-level failure trends, number of customers generated, percentage of customers with fewer than 20 valid bets, feature null rates, feature distribution drift, runtime, and output file size. These metrics help distinguish normal source-data variation from data-quality or pipeline defects.

Alerts should fire on job failure, missing or unreadable input, missing required columns, unexpected schema changes, invalid rates above a threshold, sudden spikes in a specific validation rule, zero valid rows, unexpectedly low feature row counts, unusually high `bets_used < 20`, write failures, and large feature-distribution shifts. Alerts should include links or references to the validation report and invalid-record quarantine so operators can investigate quickly.

## Idempotency and Backfills

The workflow takes explicit input and output paths. For production use, outputs should be partitioned by run date, source snapshot, or data date. A rerun for the same source snapshot should overwrite or publish the same versioned output atomically. Backfills would run the same validation and feature logic over historical source snapshots.

## Trade-offs and Assumptions

The implementation uses Parquet because it preserves types and is appropriate for downstream ML batch consumers. This is a better fit than CSV for typed feature data, but it means consumers need a Parquet-capable reader such as pandas with pyarrow.

The pipeline treats `bet_num` as the authoritative customer order, as requested. It enforces duplicate `customer_id` and `bet_num` pairs as invalid because duplicate ordering keys would make first-20 feature generation ambiguous. It also assumes `bet_num` starts at 1 and that the first-20 feature window means valid records with `bet_num` between 1 and 20, not the first 20 valid records after skipping invalid early bets.

The validation approach is strict: invalid records are quarantined rather than repaired automatically. This protects downstream consumers from broken contracts, but it can reduce `bets_used` for customers with invalid records in the first-20 window. The design makes that data-quality issue visible instead of hiding it by backfilling later bets.

The workflow is local and batch-oriented because the input is a CSV file and the task does not require real-time serving. This keeps the solution reproducible and easy to run in Docker, but it does not provide low-latency feature updates. If the business needed real-time decisions after each bet, a streaming or incremental feature pipeline would be needed.

The local implementation keeps versioning minimal. It writes to the CLI output path and includes `feature_generated_at`, but it does not create immutable run folders or store source snapshot IDs, schema versions, and feature-definition versions next to every output. In production, those would be required for stronger lineage and model reproducibility.
