
#Test added for Client Change Request (Task 5)

import tempfile
import unittest
from pathlib import Path

from supplydesk.service import OrderService


class ExpressDeliveryTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "state.json"
        self.service = OrderService(self.path)

    def item(self, product_id, quantity):
        return [{"product_id": product_id, "quantity": quantity}]

    def test_regular_express_two_notebooks(self):
        quote = self.service.quote(
            "regular", self.item("notebook", 2), "express"
        )
        self.assertEqual(quote["subtotal_cents"], 1000)
        self.assertEqual(quote["discount_cents"], 0)
        self.assertEqual(quote["delivery_cents"], 1200)
        self.assertEqual(quote["total_cents"], 2200)

    def test_student_express_two_hoodies(self):
        quote = self.service.quote(
            "student", self.item("hoodie", 2), "express"
        )
        self.assertEqual(quote["subtotal_cents"], 8000)
        self.assertEqual(quote["discount_cents"], 800)
        self.assertEqual(quote["delivery_cents"], 1200)
        self.assertEqual(quote["total_cents"], 8400)

    def test_express_fee_never_waived(self):
        items = self.item("hoodie", 3)

        standard = self.service.quote(
            "regular", items, "delivery"
        )
        express = self.service.quote(
            "regular", items, "express"
        )

        self.assertEqual(standard["total_cents"], 12000)
        self.assertEqual(standard["delivery_cents"], 0)
        self.assertEqual(express["delivery_cents"], 1200)
        self.assertEqual(express["total_cents"], 13200)

    def test_express_order_matches_quote(self):
        items = self.item("hoodie", 2)

        quote = self.service.quote("student", items, "express")
        order = self.service.place_order(
            "student", items, "express"
        )

        for key in (
            "fulfillment", "items", "subtotal_cents",
            "discount_cents", "delivery_cents", "total_cents"
        ):
            self.assertEqual(quote[key], order[key])

        self.assertEqual(order["status"], "placed")

    def test_express_order_persists_and_cancels(self):
        order = self.service.place_order(
            "regular", self.item("notebook", 2), "express"
        )

        reopened = OrderService(self.path)
        saved = reopened.get_order(order["order_id"])

        self.assertEqual(saved, order)
        self.assertEqual(saved["fulfillment"], "express")
        self.assertEqual(saved["delivery_cents"], 1200)

        cancelled = reopened.cancel_order(order["order_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(cancelled["fulfillment"], "express")
        self.assertEqual(cancelled["items"], order["items"])
        self.assertEqual(cancelled["delivery_cents"], 1200)
        self.assertEqual(cancelled["total_cents"], 2200)

    def test_invalid_fulfillment_rejected(self):
        with self.assertRaises(ValueError):
            self.service.quote(
                "regular", self.item("notebook", 1), "overnight"
            )

        with self.assertRaises(ValueError):
            self.service.place_order(
                "regular", self.item("notebook", 1), "overnight"
            )

    def test_pickup_and_default_unchanged(self):
        items = self.item("notebook", 2)

        default = self.service.quote("regular", items)
        pickup = self.service.quote("regular", items, "pickup")

        self.assertEqual(default, pickup)
        self.assertEqual(pickup["delivery_cents"], 0)


if __name__ == "__main__":
    unittest.main()
