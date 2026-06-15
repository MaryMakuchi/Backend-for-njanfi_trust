# Nkap API

Django REST Framework backend for the **Nkap** mobile application — Cameroon's circle of money and trust.

## Stack

- Django 5 + Django REST Framework
- JWT authentication (`djangorestframework-simplejwt`)
- PostgreSQL (production) / SQLite (local dev)
- OpenAPI docs via `drf-spectacular`

## Quick Start

```bash
cd njangi_trust_api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_data
python manage.py createsuperuser   # optional, for admin panel
python manage.py runserver 0.0.0.0:8000
```

API base URL: `http://127.0.0.1:8000/api/v1/`  
Swagger docs: `http://127.0.0.1:8000/api/docs/`  
Admin panel: `http://127.0.0.1:8000/admin/`

## Demo Account

After running `seed_demo_data`:

| Field | Value |
|-------|-------|
| Email | `makuchi@example.com` |
| Password | `password123` |
| Join code | `NJA2025` |

## API Endpoints

### Authentication
| Method | Endpoint | Auth |
|--------|----------|------|
| POST | `/api/v1/auth/register/` | No |
| POST | `/api/v1/auth/login/` | No |
| POST | `/api/v1/auth/login/phone/` | No |
| POST | `/api/v1/auth/verify-phone/` | Yes |
| POST | `/api/v1/auth/verify-email/` | Yes |
| POST | `/api/v1/auth/forgot-password/` | No |
| POST | `/api/v1/auth/logout/` | Yes |
| GET | `/api/v1/auth/me/` | Yes |
| POST | `/api/v1/auth/token/refresh/` | No |

### Core Features
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/dashboard/` | Dashboard summary |
| GET/POST | `/api/v1/groups/` | List / create groups |
| GET | `/api/v1/groups/{id}/` | Group details |
| POST | `/api/v1/groups/join/` | Join via invite code |
| GET | `/api/v1/contributions/` | Contribution history |
| POST | `/api/v1/contributions/pay/` | Make payment |
| GET | `/api/v1/loans/` | Loan list |
| GET | `/api/v1/loans/eligibility/` | Max loan amount |
| POST | `/api/v1/loans/request/` | Request loan |
| GET | `/api/v1/transactions/` | Blockchain ledger |
| GET | `/api/v1/notifications/` | Notifications |
| PATCH | `/api/v1/notifications/{id}/read/` | Mark read |

## Example: Login

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"makuchi@example.com","password":"password123"}'
```

Response includes `user` and `tokens.access` / `tokens.refresh`.

## Example: Authenticated Request

```bash
curl http://127.0.0.1:8000/api/v1/dashboard/ \
  -H "Authorization: Bearer <access_token>"
```

## PostgreSQL (Production)

```bash
# .env
DATABASE_URL=postgres://user:password@localhost:5432/njangi_trust
SECRET_KEY=your-production-secret
DEBUG=False
ALLOWED_HOSTS=api.njangitrust.com
```

## Project Structure

```
njangi_trust_api/
├── config/           # Django settings & URLs
├── accounts/         # User model, auth, dashboard
├── groups/           # Njangi groups & memberships
├── contributions/    # Payments & contributions
├── loans/            # Loan management
├── ledger/           # Transaction ledger
└── notifications/    # Push-ready notifications
```

## Connect Flutter App

In `njangi_trust/lib/core/constants/app_constants.dart`:

```dart
// Android emulator → host machine:
static const String apiBaseUrl = 'http://10.0.2.2:8000/api/v1';

// Linux / iOS simulator:
static const String apiBaseUrl = 'http://127.0.0.1:8000/api/v1';
```

Then replace mock repository implementations with API calls via `ApiService`.

## Next Steps

- [ ] Wire Flutter repositories to live API
- [ ] Firebase token verification endpoint
- [ ] MTN MoMo / Orange Money webhooks
- [ ] Celery payment reminders
- [ ] KYC document upload (Firebase Storage → Django)
