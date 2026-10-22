# LOOM&LEAF — Django fashion storefront

A complete, database-backed clothing storefront built with Django 6, Bootstrap 5.3 and
vanilla JavaScript. The visual direction is premium editorial monochrome: oversized
typography, local fashion photography, generous whitespace and restrained UI.

> **This is a demonstration store.** Products, inventory, policies and the brand are
> sample data. It does not fulfil real orders. Sample reviews are explicitly labelled
> “Sample data” in the storefront.

---

## 1. What works

### Storefront
- Editorial homepage: hero campaign, black category strip, new-season editorial,
  store benefits, “Best of LOOM&LEAF” grid, collection banners, newsletter section.
- Responsive header with announcement bar, desktop navigation, search overlay,
  mobile menu, account dropdown, live cart and wishlist counts.
- Configurable announcement and hero copy through Django admin.
- Catalogue at `/products/`, Men and Unisex department routes, new arrivals, collections and search. Legacy Women/Kids records remain stored but are hidden from storefront listings.
- Server-side filtering (department, collection, price, size, colour, availability,
  sale), sorting, pagination and bookmarkable GET URLs.
- Product pages with local image gallery, size/colour selection, JavaScript-assisted
  stock availability, quantity limits, care details, shipping/returns, reviews and
  related products.
- Persistent anonymous session cart and authenticated carts, merged at login.
- Wishlist (login required), wishlist add-to-bag and empty states.
- Coupon application with clear success/error messaging.
- Registration, login (username or email), logout, password change and secure email-based
  password reset, profile editing, saved addresses, order history and secure order access.
- Custom 404 and 500 pages, empty states and accessible toast notifications.

### Checkout & orders
- Server-recomputed prices, discounts, shipping and totals.
- Cash on Delivery checkout with transactional stock decrement.
- Order snapshots: product name, SKU, size, colour, quantity, unit price and line total.
- Idempotent checkout submission (refresh/replay returns the existing order).
- Order tracking timeline, status history and customer cancellation where allowed.
- Razorpay **test-mode** integration: server-created gateway orders, signature
  verification, gateway amount verification, idempotent confirmation, failed-payment
  handling. Requires test keys (see below).
- Coupon usage is recorded against successful orders only, with global and per-customer
  limits enforced inside the order transaction.

### Administration
- Custom staff dashboard at `/dashboard/` with metrics, products/inventory, orders, customers, promotions and reports.
- Staff-only daily order downloads as PDF and Excel (`.xlsx`) from `/dashboard/reports/`.
- Order confirmation and delivery-completed emails, plus one reminder after 24 hours for signed-in customers with a saved cart.
- Schedule `python manage.py send_cart_reminders` hourly on the host; it is not auto-run by Django.
- Django admin for catalogue, variants, images, orders, payments, coupons, reviews,
  customers, addresses, newsletter subscribers, pages, contact messages and site settings.
- Product stock and merchandising flags editable inline.
- Order status changes through controlled actions only (invalid transitions rejected).
- Review approval/unpublishing actions; demo reviews are labelled in the storefront.
- Staff access follows Django permissions. Only superusers see every section.

---

## 2. Requirements

- Python **3.12+** (developed and tested on Python 3.14.7 / Windows)
- Django 6.1.x, Pillow, razorpay SDK, python-dotenv (see `requirements.txt`)
- SQLite (included with Python)
- No Node.js required. Bootstrap, Bootstrap Icons and Inter/Instrument Serif fonts are
  vendored locally in `static/` so the storefront works offline (Razorpay's checkout SDK
  is the only remote script, loaded only on the payment page).

---

## 3. Windows / PowerShell quick start

From the project root (`D:\loom-leaf-freebuff`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env      # optional; local defaults work without it
python manage.py migrate
python manage.py seed_products
python manage.py createsuperuser
python manage.py runserver
```

Open <http://127.0.0.1:8000/>.

If PowerShell blocks activation, run once for the current user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Seed data

`python manage.py seed_products` is idempotent. Running it repeatedly will not create
duplicate products, variants, images, pages, coupons or sample reviews. It will not
overwrite existing stock you edited in admin.

It creates:
- 2 departments (Men and Unisex) and 3 collections
- 12 demonstration products (4 Men, 8 Unisex) with local images and adult size/colour variants
- sample sizes, colours, stock levels (including some sold-out combinations)
- policy/about pages
- coupons `WELCOME10`, `FLAT200`, `LOOMSEASON`
- three clearly-labelled **sample** reviews (`is_demo=True`, shown with a “Sample data” badge)

To skip sample reviews: `python manage.py seed_products --skip-demo-reviews`.

Product photography is local (`static/images`, copied to `media/` by the seed command).
Sources: Unsplash and Pexels, used under their respective free-use licences. Replace the
files with your own licensed photography before any real brand launch.

---

## 4. Environment variables

Copy `.env.example` to `.env` and adjust. Never commit `.env`.

| Variable | Purpose | Default |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Django signing secret | local development fallback |
| `DJANGO_DEBUG` | Debug mode | `True` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts | `127.0.0.1,localhost` |
| `SITE_URL` | Canonical origin (used in payment URLs) | `http://127.0.0.1:8000` |
| `RAZORPAY_KEY_ID` | Razorpay test key id | empty (Razorpay disabled) |
| `RAZORPAY_KEY_SECRET` | Razorpay test secret | empty |
| `DJANGO_EMAIL_BACKEND` | Email backend | console (local); SMTP for live mail |
| `DEFAULT_FROM_EMAIL` | From address | hello@loomandleaf.example |
| `EMAIL_HOST`, `EMAIL_PORT` | SMTP endpoint | unset / 587 |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP credentials | unset |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | SMTP transport security | TLS enabled / SSL disabled |

For production, set a strong `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, a real
`DJANGO_ALLOWED_HOSTS`, HTTPS, and a production database. The development server is not a
production server. No production credentials are present in the repository.

---

## 5. Razorpay test-mode setup

Razorpay is implemented but stays disabled until test credentials are configured. Cash on
Delivery works with no setup.

1. Create a Razorpay account and open **Dashboard → Account & Settings → API Keys**.
2. Generate **Test Mode** keys.
3. Add them to `.env`:
   ```dotenv
   RAZORPAY_KEY_ID=rzp_test_xxxxxxxx
   RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxx
   SITE_URL=http://127.0.0.1:8000
   ```
4. Restart the Django server and select **Razorpay — Test mode** at checkout.

What happens server-side:
- The order total is recalculated from the database and converted to paise.
- A Razorpay order is created with the official Python SDK; only the public key id and
  gateway order id are sent to the browser. The secret never appears in HTML or JS.
- On callback, the HMAC-SHA256 signature is verified, the gateway payment is fetched and
  checked for matching `order_id`, amount, currency and status, then the payment and order
  are updated in a transaction. Replays are idempotent.
- Invalid signatures never mark an order paid.

**Not implemented:** Razorpay webhooks, automatic refunds from the dashboard, and expiry
cleanup for abandoned pending payments. An abandoned Razorpay order remains “Pending” with
stock reserved until an administrator cancels it. Test-mode success was verified in
automated tests with mocked gateway responses; it has **not** been verified against live
Razorpay credentials in this environment because no test keys were supplied. Do not use
real payment credentials.

---

## 6. Admin

1. `python manage.py createsuperuser`
2. Visit `/admin/`
3. A superuser can manage everything. For limited staff, grant only the model permissions
   they need under **Authentication and Authorization → Users**; `is_staff` alone allows
   dashboard login but not editing.

Helpful admin areas:
- **Catalog → Products** — copy, price/sale price, images, variants (size/colour/SKU/stock).
- **Catalog → Product variants** — stock editable directly in the list.
- **Orders → Orders** — read-only financial fields, inlines for items/history/payments;
  use the “Action” menu to Confirm, Process, Pack, Ship, Deliver, Cancel, or mark COD paid.
- **Coupons → Coupons** — active flag, dates, limits and caps.
- **Reviews → Reviews** — approve/unpublish; verified-purchase flags are computed.
- **Core → Site settings** — announcement, hero copy, shipping flat rate, free-shipping
  threshold, contact details.
- **Core → Pages** — shipping, returns, privacy, terms and about content.

---

## 7. Key URLs

| Path | Purpose |
| --- | --- |
| `/` | Homepage |
| `/products/` | Full catalogue |
| `/products/<slug>/` | Product detail |
| `/men/`, `/unisex/` | Men and Unisex department catalogues |
| `/new-arrivals/` | New arrivals |
| `/collections/`, `/collections/<slug>/` | Editorial collections |
| `/search/?q=…` | Database search |
| `/cart/` | Bag |
| `/wishlist/` | Wishlist (login required) |
| `/checkout/` | Checkout (login required) |
| `/orders/<order_number>/` | Order confirmation & tracking (owner only) |
| `/orders/<order_number>/pay/` | Razorpay payment page |
| `/accounts/register/`, `/accounts/login/`, `/accounts/logout/` | Auth |
| `/accounts/password-reset/` | Request a one-time password reset link by email |
| `/account/`, `/account/orders/`, `/account/password/` | Account |
| `/newsletter/subscribe/` | Newsletter |
| `/shipping-policy/`, `/returns-policy/`, `/privacy-policy/`, `/terms/` | Policies |
| `/admin/` | Django admin |
| `/dashboard/reports/` | Staff reports and daily PDF/Excel downloads |

---

## 8. Project layout

```
manage.py
requirements.txt
.env.example
config/            settings, root URLs, WSGI/ASGI
core/              homepage, site settings, pages, contact, context processor
catalog/           categories, collections, products, images, sizes, colours, variants, filters
accounts/          profiles, addresses, auth views/forms
cart/              carts, cart items, services, login merge signal
wishlist/          persistent wishlist
coupons/           coupons and redemptions
orders/            checkout, orders, order items, status history, payments, Razorpay services
reviews/            moderated reviews
templates/         base + components + feature templates + feature templates
static/            vendored CSS/JS/fonts, local photography, style.css, main.js, checkout.js
media/             uploaded/seed product images (created by seed/migrations)
screenshots/       QA captures at desktop/tablet/mobile
```

Business logic lives in `cart/services.py` and `orders/services.py`; templates only render
already-validated data. Money uses `Decimal` throughout, never floats.

---

## 9. Testing & verification

Run the complete Django test suite:

```powershell
python manage.py check
python manage.py test
```

Verified in this workspace (Python 3.14.7, Django 6.1.2):

- `python manage.py check` — **no issues**
- `python manage.py test` — **95 tests, all passing** (~30 s)
- Migrations apply cleanly on a fresh database.
- Idempotent seed verified by running it twice.
- Manual browser checks at 1440, 1024, 768 and 390 px: homepage, catalogue, filters,
  product page, cart, coupon, checkout, order tracking, login, search overlay, mobile menu.
- Manual COD checkout created an order, decremented stock, applied the coupon and showed
  the tracking page. Test order/customer artifacts were removed afterwards.
- Razorpay signature/payment logic covered by automated tests with mocked gateway calls.
  Live test credentials were not available, so no live gateway payment was attempted.

Coverage highlights: catalogue filters/sort/search, cart quantity/variant validation,
session cart merge, coupons (expired/minimum/caps/usage/per-customer), COD order creation,
idempotency, stock revalidation, order ownership, cancellation stock restore, Razorpay
signatures and amount checks, duplicate callbacks, review moderation/verification,
wishlist privacy, newsletter validation, admin permissions and actions, CSRF rejection.

---

## 10. Known limitations / not done

- **Razorpay live verification pending test credentials.** The integration is coded,
  signature-checked and unit-tested, but no real gateway transaction was run.
- Email defaults to the console backend until working SMTP credentials are configured. The hourly cart reminder command must be scheduled by the host; it is not run automatically by Django's web server.
- No courier integration; tracking is driven by administrator status updates.
- No refunds, exchange workflow, returns request form, or payment webhooks.
- No guest checkout: a signed-in account is required so order ownership can be enforced.
- Pending Razorpay orders reserve stock until an admin cancels them; there is no automatic
  expiry job.
- Orders are priced in INR only; shipping/COD rules are India-focused.
- Photography and brand copy are demonstration content, not a real retailer.
- The abandoned-cart notification command needs a host scheduler; reminder email content is plain text and sends only to signed-in customers.
- SQLite is used for local development. For production, move to PostgreSQL/MySQL and
  keep the existing `select_for_update` + conditional stock-update logic.
- No email verification, two-factor auth, or social login.
- No automated visual regression/browser test suite; responsive checks were manual plus
  screenshots in `screenshots/`.

---

## 11. Security notes

- CSRF is enforced on every state-changing form; tests verify missing-token rejection.
- Passwords use Django hashing and validators; login-gated account/wishlist/order views.
- Order and address lookups are scoped to `request.user` (foreign orders return 404).
- Cart/checkout never trust client prices or totals. Stock is decremented with a
  conditional `UPDATE … WHERE stock >= quantity` inside `transaction.atomic()`; variant
  rows are also locked with `select_for_update()` on databases that support it.
- Coupon validation and usage limits are rechecked under transaction on order placement.
- Razorpay signatures are verified with `hmac.compare_digest`; the gateway is queried for
  order/amount/currency/status before marking paid. Browser callbacks cannot set payment
  state directly.
- Uploads are validated for size and real image content with Pillow.
- Razorpay secrets come from environment variables only; the public key alone is rendered.
- Cancelling an order restores stock once (`stock_restored` flag).

---

## 12. Useful commands

```powershell
python manage.py check
python manage.py migrate
python manage.py seed_products
python manage.py seed_products --skip-demo-reviews
python manage.py test
python manage.py test orders.tests
python manage.py createsuperuser
python manage.py runserver
```

For a production-style settings check (after configuring real private values in the host environment):

```powershell
$env:DJANGO_DEBUG="False"
$env:DJANGO_SECRET_KEY="<generated secret, at least 50 characters>"
$env:DJANGO_SECURE_SSL_REDIRECT="True"
python manage.py check --deploy
```

A warning for missing HSTS is expected until you verify HTTPS and intentionally set
`DJANGO_HSTS_SECONDS`; do not silence that warning by enabling HSTS before the domain and
all relevant subdomains are confirmed HTTPS-only.

## Render free-plan test deployment

This repository includes a Render Blueprint (`render.yaml`) for a **test deployment only**.
It provisions a free web service and a free PostgreSQL database where the plan is available;
free services may sleep when idle, and free database retention/availability is not appropriate
for live customer orders. Verify current Render pricing and database expiry/backup policy
before creating resources. Do not enter real customer data or treat this deployment as a
live store.

The free test intentionally uses the included static demo product photos only. Do not upload
or change product photos via admin: uploaded media uses local ephemeral storage on this test
plan and can disappear on restart/redeploy. The blueprint configures the Django console email
backend (emails appear only in service logs), leaves Razorpay credentials blank, and turns on
secure production cookie/HTTPS settings. No domain or Brevo credentials are required yet.

To create the test deployment:

1. Push the latest project commit to the private GitHub repository.
2. In Render, create a **Blueprint** from `Vishnu-Anilkumar-Git/loom-leaf-store`, approve the
   web service and database resources described by `render.yaml`, and wait for the build and
   deploy to finish. Do not create a separate database unless you update the blueprint too.
3. Render generates the Django secret and links `DATABASE_URL` to the managed test database.
   The build script installs requirements, runs `collectstatic`, and applies migrations;
   the start command runs Gunicorn. Confirm the service URL and `/` health check.
4. Create the admin account using Render's **One-Off Jobs** feature (if available on your
   plan) with command `python manage.py createsuperuser`; if one-off jobs are unavailable,
   pause here rather than putting a password in source code. The build automatically runs
   the idempotent `seed_products --skip-demo-reviews` command, so the sample catalog appears
   after the next deploy. Validate homepage, static assets, catalog, and a COD test order.
   Treat test orders and database contents as disposable.
5. To stop using the test, delete the test Blueprint resources in Render. Before any real
   store deployment, choose paid/reliable database and persistent media options, configure
   SMTP and the verified domain, rotate any credentials that were ever exposed, and test
   backups/restores. Never rely on this free test database for important data.

This blueprint prepares but does not deploy or connect accounts on your behalf.
