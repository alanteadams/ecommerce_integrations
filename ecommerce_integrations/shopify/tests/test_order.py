# Copyright (c) 2021, Frappe and Contributors
# See LICENSE

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from ecommerce_integrations.shopify.order import get_order_items


class TestOrder(IntegrationTestCase):
	def test_sync_with_variants(self):
		pass

	@patch("ecommerce_integrations.shopify.order.get_item_code", return_value="_Test Item")
	def test_fully_discounted_line_is_marked_free(self, _):
		# 100% discount code allocated across the line -> nets to 0
		line_items = [
			{
				"name": "Free Tea",
				"quantity": 2,
				"price": "13.95",
				"product_exists": True,
				"discount_allocations": [{"amount": "27.90"}],
			},
			# partially discounted line must stay a normal, priced row
			{
				"name": "Discounted Tea",
				"quantity": 1,
				"price": "10.00",
				"product_exists": True,
				"discount_allocations": [{"amount": "1.00"}],
			},
		]

		items = get_order_items(
			line_items, frappe._dict(warehouse="_Test Warehouse"), delivery_date=None, taxes_inclusive=False
		)

		self.assertEqual(items[0]["rate"], 0)
		self.assertEqual(items[0]["is_free_item"], 1)
		self.assertEqual(items[1]["rate"], 9.0)
		self.assertEqual(items[1]["is_free_item"], 0)

	@patch("ecommerce_integrations.shopify.order.get_item_code", return_value="PS-HC-HM-500ML-G01")
	@patch(
		"ecommerce_integrations.shopify.order.frappe.db.get_value",
		return_value="Chebe Moisture Retention Hydration Mist - 500 mL - Legacy",
	)
	def test_external_marketplace_title_uses_erpnext_item_name(self, _, __):
		long_external_title = (
			"Prodigyslay Hydration Hair Mist for Dry Natural Hair, Moisturizing Spray "
			"for 4C Curly Hair, Aloe, Biotin & Chebe, Lightweight, Non-Greasy "
			"Leave-In Spray, 16.9 oz"
		)

		line_items = [
			{
				"name": long_external_title,
				"quantity": 1,
				"price": "24.99",
				"product_exists": True,
				"discount_allocations": [],
			}
		]

		items = get_order_items(
			line_items,
			frappe._dict(warehouse="_Test Warehouse"),
			delivery_date=None,
			taxes_inclusive=False,
		)

		self.assertEqual(items[0]["item_code"], "PS-HC-HM-500ML-G01")
		self.assertEqual(
			items[0]["item_name"],
			"Chebe Moisture Retention Hydration Mist - 500 mL - Legacy",
		)
		self.assertLessEqual(len(items[0]["item_name"]), 140)

	@patch("ecommerce_integrations.shopify.order.get_item_code", return_value="_Test Item")
	@patch("ecommerce_integrations.shopify.order.frappe.db.get_value", return_value=None)
	def test_external_title_fallback_is_truncated_to_140_characters(self, _, __):
		long_external_title = "X" * 200

		line_items = [
			{
				"name": long_external_title,
				"quantity": 1,
				"price": "10.00",
				"product_exists": True,
				"discount_allocations": [],
			}
		]

		items = get_order_items(
			line_items,
			frappe._dict(warehouse="_Test Warehouse"),
			delivery_date=None,
			taxes_inclusive=False,
		)

		self.assertEqual(items[0]["item_name"], "X" * 140)
		self.assertEqual(len(items[0]["item_name"]), 140)
