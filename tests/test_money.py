import unittest

from lib.kalshi_paper import money


class DollarsToMicroTest(unittest.TestCase):
    def test_kalshi_dollar_strings(self):
        self.assertEqual(money.dollars_to_micro("0.56"), 560_000)
        self.assertEqual(money.dollars_to_micro("0.5600"), 560_000)
        self.assertEqual(money.dollars_to_micro("1"), 1_000_000)
        self.assertEqual(money.dollars_to_micro("100.00"), 100_000_000)
        self.assertEqual(money.dollars_to_micro("1,000.00".replace(",", "")), 1_000_000_000)

    def test_half_cent(self):
        self.assertEqual(money.dollars_to_micro("0.005"), 5_000)
        self.assertEqual(money.dollars_to_micro("0.015"), 15_000)

    def test_negative(self):
        self.assertEqual(money.dollars_to_micro("-0.25"), -250_000)

    def test_no_float_drift(self):
        # 0.1 + 0.2 != 0.3 in floats; micro-dollars must be exact.
        total = money.dollars_to_micro("0.10") + money.dollars_to_micro("0.20")
        self.assertEqual(total, money.dollars_to_micro("0.30"))

    def test_floats_rejected(self):
        with self.assertRaises(TypeError):
            money.dollars_to_micro(0.56)

    def test_bool_rejected(self):
        with self.assertRaises(TypeError):
            money.dollars_to_micro(True)

    def test_sub_micro_precision_rejected(self):
        with self.assertRaises(ValueError):
            money.dollars_to_micro("0.0000001")

    def test_garbage_rejected(self):
        for bad in ("", "abc", "1.2.3", "NaN", "Infinity"):
            with self.assertRaises(ValueError, msg=bad):
                money.dollars_to_micro(bad)


class MicroToDollarsTest(unittest.TestCase):
    def test_round_trip(self):
        for s in ("0.56", "1.00", "0.005", "100.00", "-0.25", "0.00"):
            self.assertEqual(money.micro_to_dollars(money.dollars_to_micro(s)), s)

    def test_minimum_two_decimals_trims_zeros(self):
        self.assertEqual(money.micro_to_dollars(560_000), "0.56")
        self.assertEqual(money.micro_to_dollars(1_000_000), "1.00")
        self.assertEqual(money.micro_to_dollars(1_234_567), "1.234567")
        self.assertEqual(money.micro_to_dollars(5_000), "0.005")

    def test_requires_int(self):
        with self.assertRaises(TypeError):
            money.micro_to_dollars(1.5)


class CeilToCentTest(unittest.TestCase):
    def test_rounds_up_to_whole_cent(self):
        self.assertEqual(money.ceil_to_cent_micro(14_700), 20_000)   # 0.0147 -> 0.02
        self.assertEqual(money.ceil_to_cent_micro(17_500), 20_000)   # 0.0175 -> 0.02
        self.assertEqual(money.ceil_to_cent_micro(1_732_500), 1_740_000)  # 1.7325 -> 1.74

    def test_exact_cents_unchanged(self):
        self.assertEqual(money.ceil_to_cent_micro(10_000), 10_000)
        self.assertEqual(money.ceil_to_cent_micro(1_750_000), 1_750_000)
        self.assertEqual(money.ceil_to_cent_micro(0), 0)


class FillPriceTest(unittest.TestCase):
    def test_valid_open_interval(self):
        for micro in (1, 10_000, 500_000, 999_999):
            self.assertEqual(money.validate_fill_price(micro), micro)

    def test_boundaries_and_outside_rejected(self):
        for micro in (0, 1_000_000, -1, 1_500_000):
            with self.assertRaises(ValueError, msg=str(micro)):
                money.validate_fill_price(micro)

    def test_requires_int(self):
        with self.assertRaises(TypeError):
            money.validate_fill_price(0.5)


if __name__ == "__main__":
    unittest.main()
