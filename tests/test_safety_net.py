
"""Additional safety-net tests for Campus Supply Desk."""

from pathlib import Path
import tempfile
import unittest

from supplydesk.service import OrderService


class SafetyNetTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "state.json"
        self.service = OrderService(self.path)

    def item(self, product_id, quantity):
        return [{"product_id": product_id, "quantity": quantity}]

    def stock(self, product_id):
        return next(
            p["stock"] for p in self.service.catalog()
            if p["product_id"] == product_id
        )

    # CATEGORY 1: NORMAL BEHAVIOR

    def test_placing_order_reduces_stock(self):
        before = self.stock("notebook")
        order = self.service.place_order(
            "regular", self.item("notebook", 3)
        )
        self.assertEqual(order["order_id"], "ORD-0001")
        self.assertEqual(order["status"], "placed")
        self.assertEqual(self.stock("notebook"), before - 3)
        self.assertEqual(len(self.service.list_orders()), 1)

    def test_regular_delivery_above_free_shipping(self):
        quote = self.service.quote(
            "regular", self.item("hoodie", 3), "delivery"
        )
        self.assertEqual(quote["subtotal_cents"], 12000)
        self.assertEqual(quote["delivery_cents"], 0)
        self.assertEqual(quote["total_cents"], 12000)

    # CATEGORY 2: BOUNDARY BEHAVIOR

    def test_student_discount_at_exact_threshold(self):
        quote = self.service.quote(
            "student", self.item("notebook", 10)
        )
        self.assertEqual(quote["subtotal_cents"], 5000)
        self.assertEqual(quote["discount_cents"], 500)
        self.assertEqual(quote["total_cents"], 4500)

    def test_quantity_zero_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.quote(
                "regular", self.item("notebook", 0)
            )

    def test_quantity_100_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.quote(
                "regular", self.item("notebook", 100)
            )

    # CATEGORY 3: INVALID OR EXCEPTIONAL BEHAVIOR

    def test_invalid_customer_type(self):
        with self.assertRaises(ValueError):
            self.service.quote(
                "visitor", self.item("notebook", 1)
            )

    def test_unknown_product(self):
        with self.assertRaises(ValueError):
            self.service.place_order(
                "regular", self.item("invalid-product", 1)
            )
        self.assertFalse(self.path.exists())

    def test_boolean_quantity_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.quote(
                "regular", self.item("notebook", True)
            )

    def test_duplicate_lines_cannot_exceed_stock(self):
        # Hoodies start with 5 units in stock.
        items = [
            {"product_id": "hoodie", "quantity": 3},
            {"product_id": "hoodie", "quantity": 3},
        ]
        with self.assertRaises(ValueError):
            self.service.place_order("regular", items)

        self.assertEqual(self.stock("hoodie"), 5)
        self.assertEqual(len(self.service.list_orders()), 0)
        self.assertFalse(self.path.exists())

    def test_cancel_twice_does_not_double_restock(self):
        order = self.service.place_order(
            "regular", self.item("notebook", 2)
        )
        self.service.cancel_order(order["order_id"])
        stock_after_first_cancel = self.stock("notebook")

        result = self.service.cancel_order(order["order_id"])

        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(
            self.stock("notebook"), stock_after_first_cancel
        )
        self.assertEqual(len(self.service.list_orders()), 1)

    # CATEGORY 4: BEHAVIOR TO PRESERVE

    def test_quote_does_not_create_save_file(self):
        before = self.stock("notebook")
        quote = self.service.quote(
            "regular", self.item("notebook", 2)
        )
        self.assertEqual(quote["total_cents"], 1000)
        self.assertEqual(self.stock("notebook"), before)
        self.assertFalse(self.path.exists())

    def test_quote_matches_placed_order(self):
        items = self.item("hoodie", 2)
        quote = self.service.quote(
            "student", items, "delivery"
        )
        order = self.service.place_order(
            "student", items, "delivery"
        )
        for key in (
            "items", "subtotal_cents", "discount_cents",
            "delivery_cents", "total_cents"
        ):
            self.assertEqual(quote[key], order[key])

    def test_order_persists_after_reopening(self):
        order = self.service.place_order(
            "regular", self.item("mug", 2)
        )
        reopened = OrderService(self.path)

        self.assertEqual(
            reopened.get_order(order["order_id"]), order
        )
        self.assertEqual(
            next(p["stock"] for p in reopened.catalog()
                 if p["product_id"] == "mug"),
            6
        )

    def test_cancelled_order_id_not_reused(self):
        first = self.service.place_order(
            "regular", self.item("notebook", 1)
        )
        self.service.cancel_order(first["order_id"])

        second = self.service.place_order(
            "regular", self.item("notebook", 1)
        )
        self.assertEqual(second["order_id"], "ORD-0002")
        self.assertEqual(len(self.service.list_orders()), 2)


if __name__ == "__main__":
    unittest.main()
