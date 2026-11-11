"""Operations used by the command-line order desk."""

from supplydesk.storage import JsonStore

#Refactoring 2: Replaced magic numbers with these named constants to make code easier to understand
MIN_QUANTITY = 1
MAX_QUANTITY = 99

STUDENT_DISCOUNT_MIN_CENTS = 5000
STUDENT_DISCOUNT_PERCENT = 10

FREE_DELIVERY_MIN_CENTS = 10000
DELIVERY_FEE_CENTS = 600

#Added Express Delivery Fee for Client Change Request
EXPRESS_DELIVERY_FEE_CENTS = 1200


class OrderService:
    def __init__(self, state_path=".supplydesk/state.json"):
        self.store = JsonStore(state_path)

    def catalog(self):
        return self.store.load()["catalog"]
    
    def quote(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        return self._build_quote(
            state, customer_type, items, fulfillment
    )

    def _build_quote(self, state, customer_type, items, fulfillment):
        if customer_type not in ("regular", "student"):
            raise ValueError("Customer type must be regular or student.")
        if fulfillment not in ("pickup", "delivery", "express"):
            raise ValueError("Fulfillment must be pickup, delivery, or express.")
        if not isinstance(items, list) or not items:
            raise ValueError("An order must contain at least one item.")
        lines = []
        subtotal = 0

        #AI Recommendation 2: Initiates "requested_quantities" variable
        requested_quantities = {}

        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Each item must contain a product_id and quantity.")
            product = None
            for candidate in state["catalog"]:
                if candidate["product_id"] == item.get("product_id"):
                    product = candidate
                    break
            if product is None:
                raise ValueError("Unknown product.")
            quantity = item.get("quantity")
            
            #Refactoring 2: Replaced magic numbers with the constants
            if type(quantity) is not int or quantity < MIN_QUANTITY or quantity > MAX_QUANTITY:
                raise ValueError(f"Quantity must be an integer from {MIN_QUANTITY} to {MAX_QUANTITY}.")


            #AI Recommendation 2: This checks the combined requested quantity while preserving the original item lines in quotes and orders.
            product_id = product["product_id"]

            requested_quantities[product_id] = (
                requested_quantities.get(product_id, 0) + quantity
            )

            if requested_quantities[product_id] > product["stock"]:
                raise ValueError("Not enough stock for " + product_id + ".")

            line_total = product["unit_price_cents"] * quantity
            subtotal += line_total
            lines.append({
                "product_id": product["product_id"],
                "name": product["name"],
                "unit_price_cents": product["unit_price_cents"],
                "quantity": quantity,
                "line_total_cents": line_total,
            })

        #Refactoring 2: Replaced magic numbers with the constants
        discount = 0
        if customer_type == "student" and subtotal >= STUDENT_DISCOUNT_MIN_CENTS: #AI Reccomendation 3: This corrects the student discount boundary
            discount = (subtotal * STUDENT_DISCOUNT_PERCENT + 50) // 100
        delivery = 0
        if fulfillment == "express":
            delivery = EXPRESS_DELIVERY_FEE_CENTS
        elif fulfillment == "delivery" and subtotal - discount < FREE_DELIVERY_MIN_CENTS:
            delivery = DELIVERY_FEE_CENTS
        return {
            "customer_type": customer_type,
            "fulfillment": fulfillment,
            "items": lines,
            "subtotal_cents": subtotal,
            "discount_cents": discount,
            "delivery_cents": delivery,
            "total_cents": subtotal - discount + delivery,
        }

    def place_order(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()

        quote_data = self._build_quote(
            state, customer_type, items, fulfillment
        )

    
        order = {
            "order_id": "ORD-" + str(state["next_order_number"]).zfill(4),
            "status": "placed",
            **quote_data,
        }


        for line in quote_data["items"]:
            for product in state["catalog"]:
                if product["product_id"] == line["product_id"]:
                    product["stock"] -= line["quantity"]
        state["next_order_number"] += 1
        state["orders"].append(order)
        self.store.save(state)
        return order

    def list_orders(self):
        return self.store.load()["orders"]

    def get_order(self, order_id):
        state = self.store.load()
        for order in state["orders"]:
            if order["order_id"] == order_id:
                return order
        raise ValueError("Unknown order: " + order_id)

    def cancel_order(self, order_id):
        state = self.store.load()
        order = None
        for candidate in state["orders"]:
            if candidate["order_id"] == order_id:
                order = candidate
                break
        if order is None:
            raise ValueError("Unknown order: " + order_id)
        
        #AI Recommendation 1: This change prevents inventory from being restored a second time
        if order["status"] == "cancelled": return order

        for line in order["items"]:
            for product in state["catalog"]:
                if product["product_id"] == line["product_id"]:
                    product["stock"] += line["quantity"]
        order["status"] = "cancelled"
        self.store.save(state)
        return order
