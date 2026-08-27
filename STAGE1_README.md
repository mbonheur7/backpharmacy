# VI-PHARMACY — Stage 1: Database Layer

## What this stage is, and isn't

This stage delivers the PostgreSQL schema, SQLAlchemy models, Alembic
migrations, environment-based configuration, and the initial Admin seed
script. There is **no Flask app, no API routes, and no frontend change**
in this stage — those are Stage 2 and Stage 3.

**Important caveat on testing:** this sandbox has no network access, so I
could not `pip install` SQLAlchemy/Alembic/psycopg2 or connect to a real
PostgreSQL instance to actually run these migrations. What I *did* verify:

- Every `.py` file compiles with no syntax errors (`py_compile`, shown
  below — this catches typos, bad indentation, mismatched parens, etc.)
- A structural cross-check confirming every table and every column defined
  in the SQLAlchemy models matches, name-for-name, what the hand-written
  migration creates — so the migration and the models can't drift apart
  silently.

I have **not** run `alembic upgrade head` against a live database, and I'm
not claiming that I have. The commands below are exact and should work,
but you're the first one to run them for real — treat Stage 1 as "ready
for you to test," not "already tested."

---

## Complete Stage 1 file structure

```
backend/
├── .env.example
├── alembic.ini
├── config.py
├── db.py
├── requirements.txt
├── seed_admin.py
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
└── models/
    ├── __init__.py
    ├── user.py          -- User, LoginHistory
    ├── medicine.py       -- Medicine, StockMovement
    ├── sale.py             -- Sale, SaleItem
    └── activity_log.py       -- ActivityLog
```

## What each table is for

| Table | Purpose |
|---|---|
| `users` | Admin + 3 pharmacist accounts. `role` is `Admin` or `Pharmacist`. `is_active`, `failed_logins`, `locked_until` support the disable/lockout requirements. |
| `login_history` | Every login attempt, success or failure, even for usernames that don't exist (`user_id` is nullable). |
| `medicines` | Inventory, extended with `batch_number`, `supplier`, `date_received`, `notes`, `status` (Active/Discontinued), and `critical_stock` (a second, lower threshold than `minimum_stock`). |
| `stock_movements` | Every quantity change — sale, stock-in, adjustment, damaged, expired, correction — with who did it and when. `medicines.quantity` is a running total; this table is the history behind it. `change_qty` can never be `0` (a movement that changes nothing isn't a movement). |
| `sales` | One row per completed checkout. `sold_by` references the cashier. Receipt-number generation strategy is deferred to the Stage 2 sales service, not stored as generated-column logic here. |
| `sale_items` | Line items per sale. Prices are **snapshotted** at sale time, so a receipt stays accurate even if a medicine's price changes later. `quantity` must be greater than `0`. |
| `activity_logs` | Admin-viewable audit trail for everything else worth recording (medicine edits, user management, etc.). |

The `requests` table from your original prototype is **not** in this
schema, per your decision to drop it from v1.

### Scope decisions carried into this revision

- **`supplier`** stays a plain text column on `medicines` for v1 — no
  separate `suppliers` table yet.
- **No `settings` table** yet.
- **Receipt-number generation** is not schema/database logic — it will be
  implemented in the Stage 2 sales service. The `receipt_number` column
  here is just a unique string slot for whatever that service produces.
- **User deactivation is soft-delete only.** `users.is_active` is how an
  account is disabled; there is no destructive user-delete path planned
  for the backend. `login_history` and `activity_logs` both use a
  nullable `user_id` specifically so a disabled (never deleted) user's
  historical rows are never orphaned.

---

## CHECK constraints in this schema

| Table | Constraint name | Rule |
|---|---|---|
| `users` | `ck_users_role` | `role IN ('Admin','Pharmacist')` |
| `medicines` | `ck_medicines_status` | `status IN ('Active','Discontinued')` |
| `medicines` | `ck_medicines_quantity_nonnegative` | `quantity >= 0` |
| `medicines` | `ck_medicines_purchase_price_nonnegative` | `purchase_price >= 0` |
| `medicines` | `ck_medicines_selling_price_nonnegative` | `selling_price >= 0` |
| `medicines` | `ck_medicines_minimum_stock_nonnegative` | `minimum_stock >= 0` |
| `medicines` | `ck_medicines_critical_stock_nonnegative` | `critical_stock >= 0` |
| `stock_movements` | `ck_stock_movements_reason` | `reason IN ('received','sale','adjustment','damaged','expired','correction','other')` |
| `stock_movements` | `ck_stock_movements_change_qty_nonzero` | `change_qty <> 0` |
| `sale_items` | `ck_sale_items_quantity_positive` | `quantity > 0` |

The last four rows (`purchase_price`, `selling_price`, `minimum_stock`,
`critical_stock` nonnegative, `sale_items.quantity` positive,
`stock_movements.change_qty` nonzero) were added in this hardening pass
and are folded into migration `0001` rather than a separate `0002`, since
this migration has not yet been applied to any live database.

---

## Exact dependencies (`requirements.txt`)

```
SQLAlchemy==2.0.35
alembic==1.13.3
psycopg2-binary==2.9.9
bcrypt==4.2.0
python-dotenv==1.0.1
```

## `.env.example` variables

```
DATABASE_URL=postgresql+psycopg2://vipharmacy:vipharmacy@localhost:5432/vipharmacy
SECRET_KEY=change-me-before-deploying
SEED_ADMIN_USERNAME=admin
SEED_ADMIN_PASSWORD=change-this-before-seeding
SEED_ADMIN_FULLNAME=System Administrator
LOCKOUT_MAX_FAILED_ATTEMPTS=5
LOCKOUT_DURATION_MINUTES=15
```

`SECRET_KEY` isn't used until Stage 3 (Flask sessions) — it's defined now
so there's one config file for the whole backend, not one per stage.

---

## Commands you will run on your own machine

### 1. Install dependencies

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create and configure the PostgreSQL database

If you don't already have PostgreSQL running locally, install it first
(e.g. `brew install postgresql` on macOS, or use Postgres.app / Docker).
Then, from a `psql` shell as a superuser (often just `psql postgres`):

```sql
CREATE USER vipharmacy WITH PASSWORD 'vipharmacy';
CREATE DATABASE vipharmacy OWNER vipharmacy;
GRANT ALL PRIVILEGES ON DATABASE vipharmacy TO vipharmacy;
```

(Change the username/password before using this anywhere but your own
local machine — and definitely before deploying.)

Then set up your `.env`:

```bash
cp .env.example .env
# edit .env — at minimum confirm DATABASE_URL matches what you just created
```

### 3. Run the Alembic migration

```bash
alembic upgrade head
```

This creates all seven tables in one migration (`0001_initial_schema`).
Expected output ends with something like:

```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, initial schema — ...
```

### 4. Seed the initial Admin account

Either set `SEED_ADMIN_USERNAME` / `SEED_ADMIN_PASSWORD` in `.env` first,
or just run it and answer the prompts:

```bash
python seed_admin.py
```

It refuses to run with a password under 8 characters, and refuses to
create a duplicate if that username already exists.

---

## Verification checklist

Run these against your database (`psql vipharmacy` or any GUI client)
after step 3, then again after step 4.

**After the migration (step 3):**

```sql
-- Should list exactly these 7 tables
\dt

-- Expected: users, login_history, medicines, stock_movements,
--           sales, sale_items, activity_logs
```

```sql
-- Spot-check the medicines table has the new fields
\d medicines
-- Confirm batch_number, supplier, date_received, notes, status,
-- critical_stock are present alongside the original prototype fields.
```

```sql
-- Confirm the status check constraint is active
INSERT INTO medicines (generic_name, brand_name, purchase_price, selling_price, expiry_date, status)
VALUES ('Test Medicine', 'TestBrand', 1.00, 2.00, '2030-01-01', 'InvalidStatus');
-- Expected: ERROR — violates check constraint "ck_medicines_status"
```

```sql
-- Clean up the constraint test (only if you ran a variant that succeeded)
DELETE FROM medicines WHERE generic_name = 'Test Medicine';
```

**Hardening constraints — each of these should fail with the named constraint:**

```sql
-- ck_medicines_purchase_price_nonnegative
INSERT INTO medicines (generic_name, brand_name, purchase_price, selling_price, expiry_date)
VALUES ('Neg Purchase', 'TestBrand', -1.00, 2.00, '2030-01-01');
-- Expected: ERROR — ck_medicines_purchase_price_nonnegative

-- ck_medicines_selling_price_nonnegative
INSERT INTO medicines (generic_name, brand_name, purchase_price, selling_price, expiry_date)
VALUES ('Neg Selling', 'TestBrand', 1.00, -2.00, '2030-01-01');
-- Expected: ERROR — ck_medicines_selling_price_nonnegative

-- ck_medicines_minimum_stock_nonnegative
INSERT INTO medicines (generic_name, brand_name, purchase_price, selling_price, expiry_date, minimum_stock)
VALUES ('Neg MinStock', 'TestBrand', 1.00, 2.00, '2030-01-01', -5);
-- Expected: ERROR — ck_medicines_minimum_stock_nonnegative

-- ck_medicines_critical_stock_nonnegative
INSERT INTO medicines (generic_name, brand_name, purchase_price, selling_price, expiry_date, critical_stock)
VALUES ('Neg CritStock', 'TestBrand', 1.00, 2.00, '2030-01-01', -1);
-- Expected: ERROR — ck_medicines_critical_stock_nonnegative

-- ck_stock_movements_change_qty_nonzero
-- (requires an existing medicine id and user id — substitute real ones)
INSERT INTO stock_movements (medicine_id, change_qty, reason, performed_by)
VALUES (1, 0, 'adjustment', 1);
-- Expected: ERROR — ck_stock_movements_change_qty_nonzero

-- ck_sale_items_quantity_positive
-- (requires an existing sale_id and medicine_id — substitute real ones)
INSERT INTO sale_items (sale_id, medicine_id, quantity, purchase_price, selling_price, subtotal, profit)
VALUES (1, 1, 0, 1.00, 2.00, 0.00, 0.00);
-- Expected: ERROR — ck_sale_items_quantity_positive
```

**After seeding the admin (step 4):**

```sql
SELECT id, username, fullname, role, is_active, failed_logins
FROM users;
-- Expected: exactly one row — your seeded admin, role='Admin', is_active=true, failed_logins=0
```

```sql
-- Confirm the password is actually hashed, not plaintext
SELECT password_hash FROM users WHERE username = 'admin';
-- Expected: a bcrypt hash starting with $2b$ — NOT your actual password
```

```sql
-- Confirm re-running the seed script refuses to duplicate
-- (run `python seed_admin.py` again with the same username, then:)
SELECT COUNT(*) FROM users WHERE username = 'admin';
-- Expected: still 1, not 2
```

**Rollback check (optional but recommended once):**

```bash
alembic downgrade base
\dt   # should show no VI-PHARMACY tables
alembic upgrade head
\dt   # tables back
```

This confirms the `downgrade()` function is correct and safe to rely on,
not just the `upgrade()` path.

---

## What to report back

Once you've run this for real, let me know:
1. Did `alembic upgrade head` succeed cleanly, or did anything error?
2. Did all 7 tables and the check constraints show up as expected?
3. Did `seed_admin.py` create the admin correctly, with a bcrypt hash (not plaintext)?

If anything fails, paste the exact error — I'd rather fix a real error
against your actual Postgres than guess at one in a sandbox that can't
run it.
