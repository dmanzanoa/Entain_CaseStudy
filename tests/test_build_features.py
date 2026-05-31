import unittest

import pandas as pd

from bet_pipeline.build_features import build_customer_features


class FeatureTests(unittest.TestCase):
    def test_features_use_valid_first_twenty_bets(self):
        valid_bets = pd.DataFrame(
            [
                {
                    "bet_id": 1,
                    "customer_id": "11111111-1111-1111-1111-111111111111",
                    "bet_datetime": pd.Timestamp("2024-10-01 10:00:00"),
                    "bet_num": 1,
                    "betting_amount": 10.0,
                    "price": 2.0,
                    "category": "racing",
                    "stake_type": "cash",
                    "bet_result": "return",
                    "payout": 20.0,
                    "return_for_entain": -10.0,
                    "_row_number": 2,
                },
                {
                    "bet_id": 2,
                    "customer_id": "11111111-1111-1111-1111-111111111111",
                    "bet_datetime": pd.Timestamp("2024-10-02 10:00:00"),
                    "bet_num": 21,
                    "betting_amount": 30.0,
                    "price": 4.0,
                    "category": "sports",
                    "stake_type": "bonus",
                    "bet_result": "no-return",
                    "payout": 0.0,
                    "return_for_entain": 0.0,
                    "_row_number": 3,
                },
            ]
        )

        features = build_customer_features(valid_bets, generated_at="2024-10-03T00:00:00+00:00")

        self.assertEqual(len(features), 1)
        row = features.iloc[0]
        self.assertEqual(row["bets_used"], 1)
        self.assertEqual(row["total_betting_amount"], 10.0)
        self.assertEqual(row["pct_racing"], 1.0)


if __name__ == "__main__":
    unittest.main()
