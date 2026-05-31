import unittest

import pandas as pd

from bet_pipeline.validate import validate_dataframe


class ValidationTests(unittest.TestCase):
    def test_contract_rules_mark_invalid_rows(self):
        df = pd.DataFrame(
            [
                {
                    "bet_id": 1,
                    "customer_id": "11111111-1111-1111-1111-111111111111",
                    "bet_datetime": "2024-10-01 10:00:00",
                    "bet_num": 1,
                    "betting_amount": 10,
                    "price": 3.0,
                    "category": "sports",
                    "stake_type": "cash",
                    "bet_result": "return",
                    "payout": 30.0,
                    "return_for_entain": -20.0,
                },
                {
                    "bet_id": 2,
                    "customer_id": "11111111-1111-1111-1111-111111111111",
                    "bet_datetime": "2024-10-01 11:00:00",
                    "bet_num": 2,
                    "betting_amount": 0.0,
                    "price": 3.0,
                    "category": "sports",
                    "stake_type": "cash",
                    "bet_result": "return",
                    "payout": 30.0,
                    "return_for_entain": -20.0,
                },
            ]
        )

        valid, invalid, report = validate_dataframe(df)

        self.assertEqual(len(valid), 1)
        self.assertEqual(len(invalid), 1)
        self.assertEqual(report["failure_counts_by_rule"]["betting_amount_gt_0"], 1)

    def test_payout_and_return_are_validated(self):
        df = pd.DataFrame(
            [
                {
                    "bet_id": 1,
                    "customer_id": "11111111-1111-1111-1111-111111111111",
                    "bet_datetime": "2024-10-01 10:00:00",
                    "bet_num": 1,
                    "betting_amount": 10.0,
                    "price": 3.0,
                    "category": "racing",
                    "stake_type": "bonus",
                    "bet_result": "return",
                    "payout": 99.0,
                    "return_for_entain": -99.0,
                }
            ]
        )

        _, invalid, report = validate_dataframe(df)

        self.assertEqual(len(invalid), 1)
        self.assertEqual(report["failure_counts_by_rule"]["payout_matches_contract"], 1)
        
    
    def test_validation_error_rules(self):
        base = {
            "bet_id": 1,
            "customer_id": "11111111-1111-1111-1111-111111111111",
            "bet_datetime": "2024-10-01 10:00:00",
            "bet_num": 1,
            "betting_amount": 10.0,
            "price": 3.0,
            "category": "sports",
            "stake_type": "cash",
            "bet_result": "return",
            "payout": 30.0,
            "return_for_entain": -20.0,
        }

        cases = [
            ("betting_amount_gt_0", {"betting_amount": 0.0}),
            ("price_gt_1", {"price": 1.0}),
            ("category_allowed", {"category": "casino"}),
            ("stake_type_allowed", {"stake_type": "free"}),
            ("bet_result_allowed", {"bet_result": "won"}),
            ("customer_id_is_uuid", {"customer_id": "bad-id"}),
            ("bet_datetime_is_parseable", {"bet_datetime": "bad-date"}),
            ("payout_matches_contract", {"payout": 999.0}),
            ("return_for_entain_matches_contract", {"return_for_entain": 999.0}),
        ]

        for expected_rule, overrides in cases:
            with self.subTest(expected_rule=expected_rule):
                row = {**base, **overrides}
                df = pd.DataFrame([row])

                _, invalid, report = validate_dataframe(df)

                self.assertEqual(len(invalid), 1)
                self.assertIn(expected_rule, report["failure_counts_by_rule"])
                
    def test_duplicate_bet_id_is_invalid(self):
        row = {
            "bet_id": "1",
            "customer_id": "11111111-1111-1111-1111-111111111111",
            "bet_datetime": "2024-10-01 10:00:00",
            "bet_num": 1,
            "betting_amount": 10,
            "price": 3.0,
            "category": "sports",
            "stake_type": "cash",
            "bet_result": "return",
            "payout": 30.0,
            "return_for_entain": -20.0,
        }

        df = pd.DataFrame([row, {**row, "customer_id": "22222222-2222-2222-2222-222222222222"}])

        _, invalid, report = validate_dataframe(df)

        self.assertEqual(len(invalid), 2)
        self.assertIn("bet_id_is_unique", report["failure_counts_by_rule"])
        
if __name__ == "__main__":
    unittest.main()
