# MotionfulData Shopify / ERPNext v16 Compatibility Patches

## Purpose

This branch maintains a small, controlled compatibility layer between
ERPNext/Frappe v16 and Shopify for MotionfulData / ProdigySlay.

The goal is NOT to create a heavily customized fork.

Patches are accepted only when an issue is:

1. Systemic and repeatable
2. Required for reliable production integration
3. Not safely solvable through configuration
4. Testable
5. Documented
6. Suitable for removal if upstream later resolves the issue

## Architecture Principle

Shopify is the ecommerce authority.

ERPNext is the operational ERP and inventory/accounting system of record.

External marketplace titles do not define ERPNext master data.

Product identity flows through SKU / Item Code:

External Channel
    ↓
Shopify
    ↓
SKU
    ↓
ERPNext Item Code
    ↓
ERPNext canonical Item Name

Marketplace titles may vary across Shopify, Amazon, TikTok Shop,
Facebook / Instagram, or other connected channels.

ERPNext Item Name remains authoritative after SKU mapping succeeds.

## Patch 001 — Shopify OAuth 2.0 Client Credentials

### Problem

Shopify's newer authentication model requires OAuth 2.0 client credentials
rather than relying solely on the older static-token model.

### Solution

Backported OAuth 2.0 Client Credentials support into the v16
ecommerce_integrations Shopify connector.

Important functions:

- refresh_oauth_token()
- get_valid_access_token()

## Patch 002 — Canonical ERPNext Item Name for Shopify Orders

### Incident

Date: 2026-09-14

Shopify Order:
- #1397
- Shopify ID: 7519878709562
- Source: Amazon / Codisto
- SKU: PS-HC-HM-500ML-G01

The Shopify order webhook reached ERPNext successfully.

Sales Order creation failed because Shopify supplied an Amazon SEO product
title longer than ERPNext's 140-character Sales Order Item.item_name limit.

Integration log error:

Sales Order Item, Row 1: 'Item Name' ... will get truncated,
as max characters allowed is 140

The subsequent fulfillment webhook also failed because no Sales Order existed:

Sales Order not found for syncing delivery note.

### Root Cause

ecommerce_integrations/shopify/order.py

get_order_items() used:

    "item_name": shopify_item.get("name")

This incorrectly treats the external marketplace listing title as the
authoritative ERPNext transaction item name.

### Systemic Risk

This is not Amazon-specific.

Any Shopify-originating channel can cause the same failure if its line-item
name exceeds ERPNext's field limit, including:

- Amazon
- TikTok Shop
- Facebook / Instagram
- Shopify apps / marketplaces
- future external channels

### Correct Behavior

Once Shopify SKU resolves to an ERPNext Item Code:

1. Use ERPNext Item.item_name.
2. Use the external Shopify name only as a fallback.
3. Truncate the fallback defensively to 140 characters.
4. Do not allow external marketplace naming to break order ingestion.

Target logic:

    item_code = get_item_code(shopify_item)

    item_name = (
        frappe.db.get_value("Item", item_code, "item_name")
        or (shopify_item.get("name") or "")[:140]
    )

### Recovery Rule

After deploying the fix, replay failed order #1397 through the native
Shopify connector logic.

Do NOT:

- insert Sales Orders directly with SQL
- insert Delivery Notes directly with SQL
- modify Stock Ledger Entries
- manually alter delivered_qty

Use ecommerce_integrations.shopify.order.sync_sales_order() so standard
ERPNext and connector business logic remains authoritative.

## Deployment Model

Source:

GitHub ecommerce_integrations fork
    ↓
version-16-shopify-oauth branch
    ↓
motionfuldata-infrastructure GitHub Actions
    ↓
GHCR immutable image
    ↓
ERPNext server deployment

Do NOT patch application source directly inside running production containers.

## Key Production Commands

### Application versions

    sudo docker compose \
      --project-name motionfuldata-erp \
      -f /opt/docker/gitops/erpnext/docker-compose.yml \
      -f /opt/docker/gitops/erpnext/docker-compose.shopify-sit.yml \
      exec -T backend \
      bench --site erp.motionfuldata.com version

### Container status

    sudo docker compose \
      --project-name motionfuldata-erp \
      -f /opt/docker/gitops/erpnext/docker-compose.yml \
      -f /opt/docker/gitops/erpnext/docker-compose.shopify-sit.yml \
      ps

### Recent connector errors

    sudo docker compose \
      --project-name motionfuldata-erp \
      -f /opt/docker/gitops/erpnext/docker-compose.yml \
      -f /opt/docker/gitops/erpnext/docker-compose.shopify-sit.yml \
      logs --tail=200 backend queue-short queue-long scheduler \
      | grep -iE 'shopify|traceback|error|exception|failed'

### Verify OAuth functions

    sudo docker compose \
      --project-name motionfuldata-erp \
      -f /opt/docker/gitops/erpnext/docker-compose.yml \
      -f /opt/docker/gitops/erpnext/docker-compose.shopify-sit.yml \
      exec -T backend \
      bash -lc '
      grep -n \
        "def refresh_oauth_token\|def get_valid_access_token" \
        apps/ecommerce_integrations/ecommerce_integrations/shopify/oauth.py
      '

### Inspect Shopify order mapping code

    sudo docker compose \
      --project-name motionfuldata-erp \
      -f /opt/docker/gitops/erpnext/docker-compose.yml \
      -f /opt/docker/gitops/erpnext/docker-compose.shopify-sit.yml \
      exec -T backend \
      bash -lc '
      sed -n "139,175p" \
        apps/ecommerce_integrations/ecommerce_integrations/shopify/order.py
      '

## Engineering Rule

Patch connector code only for systemic defects.

OAuth authentication incompatibility:
CODE PATCH

Marketplace title can break every future marketplace order:
CODE PATCH

One historical inventory-count mismatch:
OPERATIONAL RECONCILIATION

One failed historical order after the systemic bug is corrected:
REPLAY / RECOVERY
