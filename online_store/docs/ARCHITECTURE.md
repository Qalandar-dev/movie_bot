# Online Store — Architecture and Delivery Plan

Status: **Phases 1–2 complete.** Phases 3+ need approval before work starts.
Last updated: 2026-11-23.

---

## 0. Repository findings (Phase 1)

| Finding | Decision |
|---|---|
| The repository contains a working Telegram **movie bot** (Aiogram 3.15, SQLite, ~1.4k lines) at the root. | It is **not modified**. The store lives in its own directory, `online_store/`, so both projects coexist. Moving the store to its own repository later is a plain `git mv`. |
| No code from the movie bot is reusable for e-commerce (different domain, SQLite, no services layer). | Nothing is imported from it. |
| Sandbox: Python 3.13, Node 22, Docker, PostgreSQL 16, Redis available. | Backend targets Python 3.12 in Docker (`>=3.12,<3.14` supported). |
| The official Click (`docs.click.uz`) and Payme (`developer.help.paycom.uz`) documentation hosts could **not** be reached from this environment (DNS blocked by the network policy). | No payment protocol details are written into code yet. See §7 for what is needed before Phase 9. |

---

## 1. Architecture

**Modular monolith.** One Python codebase (`backend/`) produces one Docker image
that runs as four processes: `api`, `bot`, `worker`, `migrate`. The admin panel is
a separate Next.js app. Business rules exist **only** in the backend service layer.

```
                    ┌──────────── Nginx (only public port; TLS) ────────────┐
                    │  /api/*, /media/* → api        everything else → frontend
                    └───────────────┬───────────────────────────┬──────────┘
 Telegram users                     │                           │
      │                    ┌────────▼────────┐          ┌───────▼────────┐
      ▼                    │  FastAPI (api)  │◄─────────│ Next.js admin  │ (browser calls same origin)
 ┌──────────┐  HTTP, int.  │  routers        │          └────────────────┘
 │ Aiogram  │─────────────►│   ↓             │◄──── Click / Payme callbacks (HTTPS)
 │  (bot)   │  bot secret  │  services  ◄────┼──────┐
 └────┬─────┘              │   ↓             │      │ same service layer, in-process
      │ FSM                │  repositories   │  ┌───┴──────────┐
      ▼                    └───┬─────────┬───┘  │ worker (arq) │──► Telegram Bot API
   Redis ◄─────────────────────┘         │      └──────────────┘    (notifications)
   (FSM, cache, rate limits, job queue)  ▼
                                    PostgreSQL
```

Key decisions:

| Decision | Why |
|---|---|
| **Bot → API over HTTP** (internal network, `BOT_API_SECRET` + `X-Telegram-User-Id`) instead of importing services. | The bot is a thin client like the admin panel, so the API is the single enforcement point for validation, rate limits and auth. The customer endpoints in the spec are exactly what the bot needs. The bot can scale and be restarted independently. |
| **Worker uses services in-process.** | Jobs (reservation expiry, reports) are backend logic; an HTTP hop adds nothing. |
| **arq** for background jobs. | Asyncio-native, Redis-backed, cron support, one small dependency. Celery would add a second model and more infrastructure. Trade-off: arq pins `redis<6`, so `redis==5.3.1` is used. |
| **Layering:** `api` (HTTP only) → `services` (rules, transactions) → `repositories` (queries) → `models`. | Services never import FastAPI and raise domain errors (`AppError` subclasses) that the API maps to one error format. |
| **Explicit transactions.** Sessions never auto-commit; each service method owns its unit of work. | Required for inventory and payment correctness. |
| **Money = `NUMERIC(14,2)` UZS, Python `Decimal`, JSON as string.** | No float rounding. Payme amounts are converted at the adapter boundary (see §7). |
| **Same-origin admin panel.** The browser calls `/api/v1/...` on the panel's own origin. | The refresh token can be an `HttpOnly; Secure; SameSite=Strict` cookie scoped to `/api/v1/admin/auth`, and production needs no CORS. |

---

## 2. Directory structure

```
online_store/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI factory
│   │   ├── core/                    # config, logging (redaction), exceptions, security, redis
│   │   ├── database/                # Base + mixins, async session, Alembic migrations
│   │   ├── models/                  # SQLAlchemy models (Phase 3)
│   │   ├── schemas/                 # Pydantic DTOs
│   │   ├── repositories/            # query objects
│   │   ├── services/                # business rules: catalog, cart, checkout, orders,
│   │   │                            #   inventory, delivery, promo, payments, auth, reports
│   │   ├── api/
│   │   │   ├── middleware.py        # request id, security headers, access log
│   │   │   ├── deps.py              # auth/permission dependencies (Phase 5)
│   │   │   └── v1/                  # public, customer (bot), admin/, payments/
│   │   ├── bot/                     # main, handlers/, keyboards/, middlewares/, states/,
│   │   │                            #   filters/, api_client.py, texts.py (Uzbek copy)
│   │   ├── integrations/
│   │   │   ├── payments/            # base.py (interface), click.py, payme.py, mock.py
│   │   │   ├── notifications/       # Telegram sender
│   │   │   └── storage/             # local + S3-compatible interface
│   │   └── workers/                 # arq settings + jobs
│   ├── tests/
│   ├── Dockerfile  alembic.ini  pyproject.toml  uv.lock
├── frontend/
│   ├── src/app/                     # routes: (auth)/login, (panel)/dashboard, products, …
│   ├── src/components/ui/           # shadcn/ui components
│   ├── src/features/<domain>/       # tables, forms, hooks per domain
│   ├── src/lib/  src/services/  src/hooks/  src/types/  src/test/
│   ├── Dockerfile  package.json  package-lock.json  components.json
├── docker/nginx/nginx.conf
├── scripts/                         # create_admin, seed_regions (Phase 3/5)
├── docs/                            # this file, ERD, payment notes, runbook
├── docker-compose.yml               # base stack
├── docker-compose.override.yml      # development (auto-loaded)
├── docker-compose.prod.yml          # production overrides
├── .env.example
└── README.md
```

Changes from the suggested layout: `integrations/storage/` (the upload storage
abstraction), the split Compose files, and the `migrate` one-shot service. Each
backend Dockerfile sits inside its own build context, not at the root.

---

## 3. Data model (Phase 3)

Conventions: UUID v4 primary keys (except `Region`/`District`/`Role`, which use
small integers as stable reference data), `created_at`/`updated_at` everywhere,
timestamps in UTC (`timestamptz`) shown in Asia/Tashkent, deterministic constraint
names, money `NUMERIC(14,2)`.

```
Role 1─* AdminUser 1─* AdminSession (refresh tokens)        AuditLog *─1 AdminUser
User 1─1 Cart 1─* CartItem *─1 ProductVariant
User 1─* Address *─1 District *─1 Region
Category 1─* Category (parent)     Category 1─* Product 1─* ProductImage
Product 1─* ProductVariant 1─1 Inventory 1─* InventoryMovement
User 1─* Order 1─* OrderItem (snapshots) *─0..1 ProductVariant
Order *─1 DeliveryMethod      Order 1─* OrderStatusHistory
Order 1─* Payment 1─* PaymentTransaction
PromoCode 1─* PromoCodeRedemption *─1 Order
DeliveryMethod 1─* DeliveryRate *─1 Region (*─0..1 District)
User 1─* Review *─1 Product          User 1─* Notification
StoreSetting (key → JSON value)
```

| Entity | Notes |
|---|---|
| **User** | `telegram_id` (unique, bigint), names, username, `phone` (E.164), `phone_verified` (true **only** when it came from Telegram's contact share with a matching `user_id`), `is_blocked`. |
| **AdminUser / Role** | Roles `super_admin`, `manager`, `operator` hold a permission list. Argon2id password hashes, `is_active`, `last_login_at`. |
| **AdminSession** *(added)* | One row per refresh-token family: hashed token, `expires_at`, `revoked_at`, user agent/IP. Needed for rotation and reuse detection. |
| **Category** | Self-referencing `parent_id`, `slug` unique, `sort_order`, `is_active`, image. A category that still has products cannot be deleted (FK `RESTRICT` plus a service check with a clear error); deactivate or reassign instead. |
| **Product** | `name`, `slug`, `description`, `category_id`, `is_active`, `deleted_at` (soft delete, because orders reference it). |
| **ProductVariant** | **Every product has at least one variant** (a simple product has one default variant), so the cart, stock and orders work the same everywhere. `sku` unique, `attributes` JSONB (`{"o‘lcham": "M", "rang": "qora"}`), `price`, `discount_price` (CHECK `< price`), `is_active`. |
| **Inventory** | One per variant: `on_hand`, `reserved`, CHECK `0 ≤ reserved ≤ on_hand`, `low_stock_threshold` (null = store default). |
| **InventoryMovement** | Append-only: `type` (`restock`, `adjustment`, `reserve`, `release`, `sale`, `return`), signed `quantity`, `reason`, `order_id?`, `admin_user_id?`. |
| **Cart / CartItem** | Unique `(cart_id, variant_id)`. Prices are **not** stored here; they are always recomputed. |
| **Region / District** | Seeded with Uzbekistan's 14 top-level divisions (Republic of Karakalpakstan, 12 viloyats, Tashkent city) and their districts/cities. `is_active`, `sort_order`, names in Uzbek Latin. |
| **DeliveryMethod** | `code`, `kind` (`courier`/`pickup`), name, `is_active`. |
| **DeliveryRate** *(added)* | `(method, region, district?)` → `price`, `free_threshold?`, `eta_min_days`, `eta_max_days`, `pickup_address?`, `is_active`. The spec's Region/District/DeliveryMethod need this join table to configure prices per area. |
| **Address** | Owned by the user: district, street address, landmark (*mo‘ljal*), recipient name and phone. |
| **Order** | `number` (human-readable, e.g. `OS-000123`), `status`, `payment_status`, `delivery_status` (three separate fields); **snapshots** of recipient, address, delivery method, fee, subtotal, discount, total; `idempotency_key` with unique `(user_id, idempotency_key)`; `reservation_expires_at`; customer note and `internal_note`. |
| **OrderItem** | Snapshot of product name, SKU, variant attributes, unit price and line total. `variant_id` is nullable (`SET NULL`) so history survives deletion. |
| **OrderStatusHistory** *(added)* | Who changed which status, from what to what, when, and why. |
| **Payment** | One per payment attempt: `provider`, `amount`, `status`, `is_simulated`. |
| **PaymentTransaction** | Provider transaction: unique `(provider, external_id)`, provider state, amounts, timestamps (create/perform/cancel), cancel reason, a redacted raw request/response. |
| **PromoCode / PromoCodeRedemption** *(added)* | Percentage or fixed discount, `max_discount`, `min_order_amount`, validity window, `usage_limit`, `per_user_limit`. A redemption row per order lets limits be enforced under lock. |
| **Review, Notification, AuditLog, StoreSetting** | As specified. AuditLog records actor, action, entity, entity id, a before/after diff and IP. |

### Inventory integrity policy (please confirm)

1. **At order creation** stock is *reserved*, in the same transaction as the
   order insert:
   `UPDATE inventory SET reserved = reserved + :q WHERE variant_id = :v AND on_hand - reserved >= :q`.
   This conditional update is atomic and cannot oversell. If 0 rows change, the
   order fails with a clear "only N left" error. Variants are locked in a fixed
   order (by id) to avoid deadlocks.
2. **Payment confirmed** (or admin confirms a cash order): `on_hand -= q, reserved -= q` (`sale` movement).
3. **Unpaid online order** past `reservation_expires_at` (default 30 min): the worker cancels it and releases the reservation (`release`).
4. **Cancel before shipping:** the reservation is released, or a `return` movement is recorded if the stock was already deducted.
5. **Refund after delivery:** stock comes back only when an admin marks the goods as returned to stock (damaged goods do not return to sellable stock).

### State machines (enforced in services)

Order: `pending → confirmed → processing → shipped → out_for_delivery → delivered`;
`pending|confirmed|processing → cancelled`; `delivered|cancelled(paid) → refunded`.
Payment: `pending → processing → paid | failed | cancelled`; `paid → refunded`.
Delivery: `awaiting_dispatch → preparing → shipped → out_for_delivery → delivered | delivery_failed`;
`delivery_failed → out_for_delivery | returned`. Moving delivery to
`shipped/out_for_delivery/delivered` advances the order status with it.

Customer cancellation is allowed while the order is `pending` or `confirmed`. A
paid order then goes into the refund flow; it never silently becomes "cancelled".

---

## 4. API design (`/api/v1`)

Conventions: JSON; errors are `{"error": {code, message, details?, request_id}}`;
list endpoints return `{items, total, page, page_size}` and take `?page=&page_size=&q=&sort=-created_at`
plus domain filters; `POST /orders` and `POST /payments` require an
`Idempotency-Key` header; OpenAPI at `/api/v1/docs` (disabled in production).

| Group | Auth | Endpoints |
|---|---|---|
| Health | none | `GET /health/live`, `GET /health/ready` ✅ (done) |
| Public catalog | none | `GET /products` (filters: category, price range, in stock, discounted; sort: price, newest, popular), `GET /products/{id}`, `GET /categories`, `GET /categories/{id}/products`, `GET /regions`, `GET /regions/{id}/districts`, `GET /delivery/quote` |
| Customer (bot) | bot secret + `X-Telegram-User-Id` | `POST /customers/register`, `POST /customers/phone` (contact share), `GET /profile`, `GET/POST/PATCH /addresses`, `GET /cart`, `POST /cart/items`, `PATCH/DELETE /cart/items/{id}`, `POST /cart/promo`, `POST /checkout/preview`, `POST /orders`, `GET /orders`, `GET /orders/{id}`, `POST /orders/{id}/cancel` |
| Payments | customer / provider | `POST /payments` (returns the provider redirect URL), `GET /payments/{id}`, `POST /payments/webhook/click`, `POST /payments/webhook/payme` (provider-mandated formats and auth) |
| Admin auth | — | `POST /admin/auth/login`, `POST /admin/auth/refresh` (cookie, rotation), `POST /admin/auth/logout`, `GET /admin/auth/me` |
| Admin | JWT + permission | `GET /admin/dashboard`; CRUD for `products` (+`/images`, `/variants`), `categories`, `inventory` (+`/movements`, `/adjust`), `orders` (+`/status`, `/delivery-status`, `/notes`, `/payments`), `customers`, `promo-codes`, `regions`, `districts`, `delivery-methods`, `delivery-rates`, `staff`, `settings`, `audit-log`; `GET /admin/reports/{sales,categories,products,customers,payments,statuses}` with `?format=csv` |

Permission matrix (backend-enforced; the frontend only mirrors it):

| Area | super_admin | manager | operator |
|---|---|---|---|
| Dashboard, reports | ✔ | ✔ | — |
| Products, categories, inventory | ✔ | ✔ | view |
| Orders: view / status / notes | ✔ | ✔ | ✔ |
| Orders: refund | ✔ | ✔ | — |
| Customers | ✔ | ✔ | view |
| Promo codes, delivery config | ✔ | ✔ | — |
| Staff, store settings, audit log | ✔ | — | — |

---

## 5. Admin panel pages (Phase 7)

`/login` · `/` Dashboard (KPI cards, revenue chart, low stock, best sellers) ·
`/orders`, `/orders/[id]` (timeline, status actions, payment details, internal notes) ·
`/products`, `/products/new`, `/products/[id]` (variants, images, stock) ·
`/categories` (tree with drag-to-sort) · `/inventory` (stock list, adjust dialog, history) ·
`/customers`, `/customers/[id]` · `/promo-codes` · `/delivery` (regions → districts → rates) ·
`/reports` (date range, CSV export) · `/staff` · `/audit-log` · `/settings`.

Shared UI: sidebar plus top bar, data tables (server-side pagination, sort and filters synced to the URL),
modal forms (React Hook Form + Zod), confirmation dialogs for destructive actions,
toasts, skeleton/empty/error states, mobile drawer navigation. Routes are protected by
a session check in the panel layout; any 401 triggers one silent refresh, then a redirect to `/login`.

---

## 6. Telegram bot flow (Phase 6)

```
/start → registered? ─no→ "Raqamni yuborish" contact button → verify contact.user_id == from.id → main menu
                    └yes→ main menu
Main menu (reply keyboard): 🛍 Katalog · 🔎 Qidirish · 🛒 Savat · 📦 Buyurtmalarim · 👤 Profil · ☎️ Aloqa
Katalog → categories (inline, nested, paginated) → product list (sort/filter buttons, 8 per page)
        → product card (photo album, price/discount, variant pickers: o‘lcham, rang) → ➕ Savatga
Savat → items with ➖/➕/🗑, promo code, subtotal → Rasmiylashtirish
Checkout FSM: name → phone (contact or saved) → region → district → delivery method (prices from API)
        → address → landmark/instructions → summary (items, delivery fee, discount, total)
        → ✅ Tasdiqlash  (one Idempotency-Key per checkout session, so a double tap cannot create two orders)
        → payment method: Click | Payme → pay button (URL) → result shown only after the backend confirms
Buyurtmalarim → list → details (status, payment status, delivery status) → cancel if allowed
Notifications: order confirmed / shipped / delivered / payment received / cancelled
```

Engineering: routers per feature, `RedisStorage` FSM with TTL, middlewares for
user context, throttling and error handling (friendly Uzbek message plus a logged
traceback), callback-data factories, and all text in one `texts.py`. Handlers only
call `api_client` and render the result.

---

## 7. Payments (Phase 9) — requirements and blockers

Architecture: a `PaymentProvider` interface (`create_payment(order) → redirect URL`,
`handle_callback(request) → provider response`, `refund?`) with adapters
`ClickPaymentProvider`, `PaymePaymentProvider` and `MockPaymentProvider`. A shared
`PaymentService` owns the rules:

- validate amount and order ownership against our records (never trust the callback amount alone);
- idempotency via unique `(provider, external_id)` plus a row lock on the payment;
- repeated callbacks return the original result and never double-apply;
- only a verified provider callback (or an admin action with an audit entry) sets `paid`; a redirect back from the provider never does;
- every callback is stored redacted in `PaymentTransaction`;
- `PAYMENT_MODE=mock` marks payments `is_simulated=true`, shown with a "TEST" badge in the panel and bot, and live mode refuses to start without credentials (already enforced in config).

**Blocked until provided** (no protocol detail is written from memory):

1. Access to the official docs: allow `docs.click.uz` and `developer.help.paycom.uz` in this environment's network settings, or paste the relevant pages (Click SHOP API Prepare/Complete and payment link; Payme Merchant API methods, error codes, checkout initialization).
2. Sandbox merchant credentials: Click `service_id`, `merchant_id`, `merchant_user_id`, `secret_key`; Payme merchant id plus test key.
3. A public HTTPS URL for the callbacks (registered in each merchant cabinet).
4. Fiscalization (OFD/IKPU codes): Uzbek receipts may require product IKPU codes and package codes in payment data. **Please confirm with your accountant/provider** whether you need this; if so, `ProductVariant` gets `ikpu_code`/`package_code` fields in Phase 3.

---

## 8. Delivery system (Phase 8)

- Region/District reference data is seeded by migration; admins can rename, deactivate and reorder it.
- An admin creates **delivery methods** (e.g. "Kuryer", "Olib ketish — Chilonzor filiali", "Pochta") and **rates** per region, optionally overridden per district.
- Fee resolution: district rate → region rate → method unavailable. If the subtotal after discount ≥ `free_threshold` (rate-level, else store-level), the fee is 0.
- Quote = `{method, price, eta_min_days, eta_max_days, free_applied}`; the order stores a snapshot.
- Delivery status is updated manually by staff, and every change notifies the customer. **No live courier tracking is claimed**; a courier API can plug in later as another status source.

---

## 9. Roadmap

| Phase | Scope | Done when |
|---|---|---|
| 1–2 ✅ | Plan, structure, config, logging, errors, security primitives, Docker (dev/prod), Nginx, CI-ready tooling | Stack runs, health is green, tests pass |
| 3 | Models, initial migration, region/district seed, ERD doc | Migration up/down on a clean DB, constraint tests |
| 4 | Repositories + services (catalog, cart, promo, delivery quote, inventory, order state machines) | Unit and DB tests incl. concurrent oversell test |
| 5 | Auth (login, refresh rotation, logout, RBAC deps), public, customer and admin APIs, rate limiting, `create_admin` script | API tests incl. permission matrix |
| 6 | Telegram bot | Handler tests with a mocked API/Bot |
| 7 | Admin panel | Component tests, a Playwright smoke test of key flows |
| 8 | Checkout, orders, inventory and delivery end-to-end | Order lifecycle tests |
| 9 | Click + Payme adapters (needs §7 inputs) | Callback validation, signature, idempotency and amount tests |
| 10 | Worker jobs: notifications, reservation expiry, low stock, scheduled reports | Job tests |
| 11 | Security hardening, CI (GitHub Actions), coverage gaps | Security review checklist |
| 12 | Docs, backup/restore runbook, production deployment guide | Fresh-server deploy rehearsal |

## 10. Environment variables

Every variable is documented inline in [`../.env.example`](../.env.example) and in
the README table. Production refuses to start on default or weak secrets, `DEBUG=true`,
wildcard CORS, or `PAYMENT_MODE=live` without credentials.

## Open decisions for the business owner

1. **Cash on delivery** (*naqd pul / karta kuryerga*) — the spec lists only Click and Payme. Many Uzbek shoppers expect COD. Add it?
2. Confirm the **stock reservation policy** above (30 min hold for online payments).
3. **Fiscal receipts / IKPU codes** — required for your business type?
4. Production **domain names** (e.g. `shop.example.uz`, `admin.example.uz`) for TLS and CORS.
