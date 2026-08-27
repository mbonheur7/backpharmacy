# VI-PHARMACY — Stage 2: Flask Backend / API

## Environment note — Python 3.14.6 on Windows

Your environment already surfaced one real compatibility issue and fixed
it yourself: `psycopg2-binary==2.9.9` has no prebuilt wheel for Python
3.14 and fails trying to compile from source on Windows. I've updated
`requirements.txt` to pin `psycopg2-binary==2.9.12`, which you confirmed
installs cleanly and works against your migrated database.

Two things worth flagging now rather than after you hit them:

- **`gunicorn` does not run on Windows** (it depends on `fcntl`, a
  Unix-only module). It's in `requirements.txt` for the eventual
  Render/Railway deployment (Linux), not for local testing. `pip install`
  will succeed on Windows since gunicorn itself is pure Python — you just
  can't *run* it locally. Use `flask run` for all local testing, exactly
  as this README does below.
- **Python 3.14 is very new**, so it's possible `bcrypt`, `Flask-Cors`,
  `SQLAlchemy`, or `alembic` hit the same "no wheel yet, tries to compile,
  fails" problem `psycopg2-binary` did. If `pip install -r requirements.txt`
  errors on any of them, tell me the exact package and error — I'll find a
  version with a 3.14 wheel and update the pin the same way, rather than
  you having to hunt for one yourself.

Nothing in Stage 1's schema or models changed — this is Stage 2 built on
top of the database you already migrated, not a replacement of it.

---

## What was actually tested, and how

This sandbox has network access disabled, so I could not `pip install`
Flask-Cors, SQLAlchemy, bcrypt, or psycopg2 here (Flask itself happened to
already be present, but that alone isn't enough to run this app — it needs
the database layer too). I did **not** start this server or send it a
single real HTTP request. Here's exactly what I did check:

1. **`py_compile` on all 27 Python files** — every route, service, model,
   and config file parses with no syntax errors. (Output was shown to you
   in-conversation; re-run it yourself any time with the command in the
   verification section below.)

2. **A structural grep/AST pass**, specifically checking:
   - `medicine.quantity` is assigned in **exactly one place** in the whole
     codebase — `services/stock_service.py` line 50. Nowhere in `routes/`
     or any other service touches it directly.
   - `allow_sale_reason=True` (the flag that permits a `'sale'`-reasoned
     stock movement) is only ever passed from `routes/sales.py` — the
     manual stock-movement endpoint used by both roles can never produce
     a `sale` movement, only `received/adjustment/damaged/expired/
     correction/other`.
   - **No `DELETE` route exists anywhere** in `routes/` — grepped for it
     directly, confirmed empty.
   - Generated a full route inventory (method, path, permission decorator)
     for all 7 route files and checked it line-by-line against your
     approved permission matrix — shown to you in-conversation.

What this **doesn't** prove: that the code actually runs correctly against
a live Flask + SQLAlchemy + PostgreSQL stack, that the bcrypt hashing
round-trips correctly, that a real HTTP request produces the JSON shape
I've documented, or that the lockout timing behaves correctly in practice.
That requires the commands below, run by you, against your already-working
Stage 1 database.

---

## Stage 2 file structure (as built)

```
backend/
├── app.py                    -- Flask application factory
├── wsgi.py                   -- entry point for `flask run` / gunicorn
├── extensions.py             -- scoped_session wired to Flask's request lifecycle
├── config.py                 -- extended with session + CORS settings
├── utils.py                  -- receipt number generation, error/date helpers
├── serializers.py            -- model -> JSON, strips profit fields for Pharmacists
├── db.py, models/, migrations/, seed_admin.py   -- unchanged from Stage 1
├── services/
│   ├── auth_service.py           -- bcrypt verify, lockout, login_history
│   ├── permission_service.py      -- login_required / require_role — the real enforcement point
│   ├── stock_service.py            -- the ONLY function allowed to change medicines.quantity
│   └── activity_log_service.py      -- one helper, used everywhere something needs auditing
└── routes/
    ├── auth.py                       -- login, logout, me
    ├── medicines.py                   -- CRUD, non-price edit, admin pricing/status/deactivate/reactivate, stock movements
    ├── sales.py                        -- checkout, receipt list/reprint
    ├── alerts.py                        -- low/critical/out-of-stock, expired/expiring, dashboard
    ├── reports.py                        -- inventory/sales-by-period/best-lowest-selling (both roles); purchase/profit (Admin only)
    ├── users.py                           -- Admin only — create, reset password, enable/disable. No delete.
    └── activity_logs.py                    -- Admin only — audit trail viewer
```

---

## Complete API reference

All endpoints are under `/api`. Session cookie is required (except
`/api/auth/login`) — send requests with credentials so the browser/client
attaches the cookie.

| Method | Path | Who | Notes |
|---|---|---|---|
| POST | `/api/auth/login` | anyone | `{username, password}` |
| POST | `/api/auth/logout` | logged in | |
| GET | `/api/auth/me` | logged in | |
| GET | `/api/medicines` | logged in | `?search=&status=&expiry_before=` |
| GET | `/api/medicines/:id` | logged in | |
| POST | `/api/medicines` | logged in | both roles can add; `initial_quantity` routed through stock service |
| PATCH | `/api/medicines/:id` | logged in | non-price fields only — rejects `purchase_price`/`selling_price`/`status`/`quantity` with 403 |
| PATCH | `/api/medicines/:id/pricing` | **Admin** | `{purchase_price?, selling_price?}` |
| PATCH | `/api/medicines/:id/status` | **Admin** | `{status: "Active"\|"Discontinued"}` |
| POST | `/api/medicines/:id/deactivate` | **Admin** | convenience wrapper |
| POST | `/api/medicines/:id/reactivate` | **Admin** | convenience wrapper |
| POST | `/api/medicines/:id/stock-movements` | logged in | `{change_qty, reason, note?}` — `reason` can't be `'sale'` here |
| GET | `/api/medicines/:id/stock-movements` | logged in | history for one medicine |
| POST | `/api/sales` | logged in | `{items: [{medicine_id, quantity}]}` — all-or-nothing checkout |
| GET | `/api/sales` | logged in | `?receipt_number=&start=&end=` — profit fields omitted for Pharmacist |
| GET | `/api/sales/:id` | logged in | reprint a receipt |
| GET | `/api/alerts/low-stock` \| `/critical-stock` \| `/out-of-stock` \| `/expired` \| `/expiring-soon` \| `/dashboard` | logged in | |
| GET | `/api/reports/inventory` | logged in | counts + selling value only, no cost/profit |
| GET | `/api/reports/purchase` | **Admin** | inventory cost |
| GET | `/api/reports/profit` | **Admin** | expected + realized profit |
| GET | `/api/reports/sales/daily` \| `/weekly` \| `/monthly` \| `/yearly` \| `/range` | logged in | revenue + transaction count, no profit |
| GET | `/api/reports/best-selling` \| `/lowest-selling` | logged in | quantity sold only |
| GET | `/api/reports/expired-medicines` | logged in | |
| GET | `/api/users` | **Admin** | |
| POST | `/api/users` | **Admin** | create pharmacist/admin account |
| PATCH | `/api/users/:id/password` | **Admin** | reset password |
| PATCH | `/api/users/:id/status` | **Admin** | `{is_active: bool}` — enable/disable, never delete |
| GET | `/api/activity-logs` | **Admin** | `?action=&user_id=&start=&end=` |

---

## Commands — Windows PowerShell

You already have Stage 1's virtual environment and PostgreSQL running.
From your `backend` folder:

### 1. Install the new Stage 2 dependencies

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

(This installs Flask, Flask-Cors, and gunicorn on top of what you already
have — `pip` will skip the packages that are already satisfied.)

### 2. Update your `.env`

Open `.env` and add (or confirm) these Stage 2 values — they weren't
needed for Stage 1:

```
SECRET_KEY=<generate one — see below>
SESSION_COOKIE_SECURE=false
SESSION_LIFETIME_HOURS=8
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

Generate a real `SECRET_KEY`:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste that output as the value of `SECRET_KEY` in `.env`. Don't reuse the
placeholder.

### 3. Start the API server

```powershell
$env:FLASK_APP = "wsgi.py"
flask run --port 5000
```

You should see Flask start and report it's running on
`http://127.0.0.1:5000`. Leave this running in its own PowerShell window
for the tests below.

### 4. Smoke-test the health endpoint (new PowerShell window)

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/health"
```

Expected: `status: ok`, `service: VI-PHARMACY API`.

---

## API verification checklist

Run these in order — several depend on state from the previous ones.
`Invoke-RestMethod` doesn't persist cookies across calls by default, so
use a `WebSession` variable to keep the login session across requests.

### 5. Log in as your seeded Admin

```powershell
$session = $null
$body = @{ username = "admin"; password = "<your seeded admin password>" } | ConvertTo-Json
$resp = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/auth/login" -Method Post -Body $body -ContentType "application/json" -SessionVariable session
$resp.user
```

Expected: JSON with your admin's `id`, `username`, `role: "Admin"`, and
**no** `password_hash` field anywhere in the response.

### 6. Confirm the session cookie is httpOnly

```powershell
$session.Cookies.GetCookies("http://127.0.0.1:5000") | Format-List Name, HttpOnly, Value
```

Expected: a `session` cookie with `HttpOnly: True`. (`Value` will be a
long signed/encrypted string, not plaintext data — that's the Flask
session mechanism working as intended.)

### 7. Try a wrong password 5 times, confirm lockout

```powershell
$body = @{ username = "admin"; password = "definitely-wrong" } | ConvertTo-Json
for ($i = 1; $i -le 5; $i++) {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/auth/login" -Method Post -Body $body -ContentType "application/json"
    } catch {
        Write-Host "Attempt $i -> $($_.Exception.Response.StatusCode.value__): $($_.ErrorDetails.Message)"
    }
}
```

Expected: attempts 1-4 return 401 "Wrong username or password.", attempt 5
returns 423 "Too many failed attempts...". A 6th attempt (even with the
correct password) should also return 423 until 15 minutes pass.

**Then verify in the database directly:**

```sql
SELECT username, failed_logins, locked_until FROM users WHERE username='admin';
SELECT username_tried, success, occurred_at FROM login_history ORDER BY occurred_at DESC LIMIT 6;
```

Expected: `failed_logins = 5`, `locked_until` set ~15 minutes in the
future, and 5 new `login_history` rows with `success=false`.

*(You'll need to wait out the lockout, or manually clear it in the DB with
`UPDATE users SET failed_logins=0, locked_until=NULL WHERE username='admin';`,
before continuing to step 8.)*

### 8. Log back in correctly, then add a medicine as Admin

```powershell
$body = @{ username = "admin"; password = "<correct password>" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/auth/login" -Method Post -Body $body -ContentType "application/json" -WebSession $session | Out-Null

$med = @{
    generic_name = "Paracetamol"
    brand_name = "Panadol"
    medicine_class = "Analgesic"
    dosage = "500mg"
    purchase_price = 0.50
    selling_price = 1.00
    expiry_date = "2027-12-31"
    initial_quantity = 100
    minimum_stock = 20
    critical_stock = 5
    supplier = "Test Supplier"
} | ConvertTo-Json
$created = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/medicines" -Method Post -Body $med -ContentType "application/json" -WebSession $session
$created.medicine
```

Expected: the medicine comes back with `quantity: 100`, `status: "Active"`.

**Verify the stock movement was actually recorded** (not just the quantity
set directly):

```sql
SELECT * FROM stock_movements WHERE medicine_id = <id from above>;
```

Expected: one row, `change_qty=100`, `reason='received'`, `note='Initial stock on creation'`.

### 9. Confirm a Pharmacist CANNOT change price (server-side enforcement)

Create a pharmacist first (as Admin):

```powershell
$pharm = @{ username="pharm1"; password="TestPass1234"; fullname="Test Pharmacist"; role="Pharmacist" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/users" -Method Post -Body $pharm -ContentType "application/json" -WebSession $session
```

Log in as that pharmacist in a **separate** session variable:

```powershell
$pharmSession = $null
$body = @{ username = "pharm1"; password = "TestPass1234" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/auth/login" -Method Post -Body $body -ContentType "application/json" -SessionVariable pharmSession | Out-Null

$priceAttempt = @{ purchase_price = 999 } | ConvertTo-Json
try {
    Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/medicines/<id>/pricing" -Method Patch -Body $priceAttempt -ContentType "application/json" -WebSession $pharmSession
} catch {
    Write-Host "$($_.Exception.Response.StatusCode.value__): $($_.ErrorDetails.Message)"
}
```

Expected: **403**, "You do not have permission to perform this action."
— confirming the rejection happens in Flask, not just hidden in a UI that
doesn't exist yet.

Also confirm the generic PATCH rejects a sneaky price change:

```powershell
$sneaky = @{ selling_price = 1 } | ConvertTo-Json
try {
    Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/medicines/<id>" -Method Patch -Body $sneaky -ContentType "application/json" -WebSession $pharmSession
} catch {
    Write-Host "$($_.Exception.Response.StatusCode.value__): $($_.ErrorDetails.Message)"
}
```

Expected: **403** even though this hit the *general* medicine-edit route
that Pharmacists otherwise can use — because `selling_price` is in
`BLOCKED_ON_GENERIC_PATCH` regardless of role.

### 10. Confirm a Pharmacist CANNOT see profit

```powershell
try {
    Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/reports/profit" -WebSession $pharmSession
} catch {
    Write-Host "$($_.Exception.Response.StatusCode.value__): $($_.ErrorDetails.Message)"
}
```

Expected: **403**.

Then make a sale as the pharmacist and confirm profit is absent from the receipt:

```powershell
$sale = @{ items = @(@{ medicine_id = <id>; quantity = 2 }) } | ConvertTo-Json
$saleResp = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/sales" -Method Post -Body $sale -ContentType "application/json" -WebSession $pharmSession
$saleResp.sale
```

Expected: `total_amount` is present; `total_profit` is **absent** from the
JSON entirely (not `null` — actually missing, since Admin re-fetching the
same sale *will* see it).

### 11. Confirm stock actually decreased and a movement was logged for the sale

```sql
SELECT quantity FROM medicines WHERE id = <id>;
SELECT * FROM stock_movements WHERE medicine_id = <id> ORDER BY occurred_at DESC LIMIT 1;
```

Expected: quantity dropped by 2 from step 8; newest movement has
`change_qty=-2`, `reason='sale'`.

### 12. Confirm there is no way to delete a user or a medicine

```powershell
# Should both fail — there is no route for either
try { Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/users/<id>" -Method Delete -WebSession $session } catch { Write-Host $_.Exception.Response.StatusCode.value__ }
try { Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/medicines/<id>" -Method Delete -WebSession $session } catch { Write-Host $_.Exception.Response.StatusCode.value__ }
```

Expected: **405** (Method Not Allowed) for both — the routes genuinely
don't exist, this isn't a permission check.

### 13. Confirm the audit trail actually captured all of the above

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/activity-logs" -WebSession $session
```

Expected: rows for `login`, `medicine_added`, `user_created`,
`medicine_pricing_updated` attempt is **not** here (it was rejected before
reaching the log — only successful actions are logged), `sale_completed`,
etc., each with the right `user_id`.

---

## What to report back

1. Did the server start cleanly with `flask run`?
2. Did the lockout in step 7 trigger at exactly 5 attempts, and does
   `login_history` show the failed attempts?
3. Did step 9 return 403 for both the dedicated pricing endpoint *and*
   the sneaky generic-PATCH attempt?
4. Did step 10 confirm profit is genuinely absent from the Pharmacist's
   view of the sale, not just zeroed out?
5. Any error at any step — paste the exact response body and status code.

If all of that checks out, that's Stage 2 confirmed against your real
database, and we can talk about Stage 3 (the React frontend) when you're
ready. I'm not moving there until you say so.
