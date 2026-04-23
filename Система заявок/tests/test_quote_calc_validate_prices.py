import unittest


class QuoteCalcValidatePricesTests(unittest.TestCase):
    def test_accepts_valid_vps_rate(self) -> None:
        from web_admin.quote_calc import quote_calc_validate_prices

        ok, error, normalized = quote_calc_validate_prices({"vps_eur_uah_rate": 42})
        self.assertTrue(ok)
        self.assertEqual(error, "")
        self.assertGreater(float(normalized["vps_eur_uah_rate"]), 0)

    def test_rejects_zero_or_negative_vps_rate(self) -> None:
        from web_admin.quote_calc import quote_calc_validate_prices

        ok, error, _ = quote_calc_validate_prices({"vps_eur_uah_rate": 0})
        self.assertFalse(ok)
        self.assertIn("EUR→UAH", error)

        ok, error, _ = quote_calc_validate_prices({"vps_eur_uah_rate": -1})
        self.assertFalse(ok)
        # Негативне значення може бути відсічене загальним правилом "ціна не може бути від'ємною".
        self.assertTrue(("EUR→UAH" in error) or ("не може бути від'ємною" in error))

    def test_rejects_negative_price(self) -> None:
        from web_admin.quote_calc import quote_calc_validate_prices

        ok, error, _ = quote_calc_validate_prices({"vps_ipv4_eur": -0.01})
        self.assertFalse(ok)
        self.assertIn("не може бути від'ємною", error)


if __name__ == "__main__":
    unittest.main()

