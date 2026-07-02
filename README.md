# Ozon ERP — Ozon Seller API ERP System

A production-grade ERP for Ozon marketplace sellers. Manage products, inventory, orders (FBS/FBO), pricing, finance, returns, and customer chat — all through the Ozon Seller API.

## Features

- **📦 Product Management** — local catalog with Ozon sync, category tree, attribute mapping (RU↔ZH), image management, bulk import/export
- **🏭 Inventory Management** — multi-warehouse stock tracking, low-stock alerts, stock sync with Ozon
- **📋 Order Management** — FBS/FBO order processing, status workflow, shipping labels, tracking numbers
- **💰 Pricing** — price management with history, bulk updates, push/pull sync
- **💳 Finance** — transaction tracking, per-order P&L, commission analysis, reconciliation
- **📊 Dashboard** — KPI cards, sales trends, top products, margin analysis
- **↩️ Returns** — return tracking and status management
- **⚙️ Sync Engine** — pull-primary bidirectional sync with audit logging

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env — add your OZON_CLIENT_ID and OZON_API_KEY
```

### 3. Run the app

```bash
uvicorn app.main:app --reload
```

### 4. Open in browser

```
http://localhost:8000
```

## Ozon API Coverage

| Domain | Endpoints Used | Description |
|--------|---------------|-------------|
| Products | `/v2/product/import`, `/v3/product/info/list`, `/v3/product/list`, `/v4/product/info/attributes`, `/v1/product/info/description`, `/v1/product/classify`, `/v1/product/archive`, `/v1/product/unarchive` | Full product lifecycle |
| Categories | `/v1/category/tree`, `/v1/category/attribute`, `/v1/category/attribute/value` | Category tree and attribute dictionary |
| Prices | `/v1/product/import/prices`, `/v5/product/info/prices` | Price get/set |
| Stocks | `/v2/products/stocks`, `/v4/product/info/stocks` | Stock get/set |
| Warehouses | `/v1/warehouse/list` | Warehouse list |
| Orders (FBS) | `/v3/posting/fbs/list`, `/get`, `/ship`, `/delivering`, `/last-mile`, `/delivered`, `/tracking-number/set`, `/package-label` | Full FBS workflow |
| Orders (FBO) | `/v2/posting/fbo/list`, `/get` | FBO visibility |
| Finance | `/v3/finance/transaction/list`, `/totals` | Financial operations |
| Returns | `/v1/returns/list`, `/get` | Return management |
| Reports | `/v1/report/list`, `/info`, `/create` | Report center |
| Chat | `/v1/chat/list`, `/send` | Customer chat |

## Architecture

```
ozon-erp/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Pydantic settings
│   ├── database.py          # Async SQLAlchemy
│   ├── dependencies.py      # DI
│   ├── models/              # SQLAlchemy ORM (16 tables)
│   ├── schemas/             # Pydantic API schemas
│   ├── api/                 # Route handlers
│   ├── services/            # Business logic
│   ├── integrations/        # Ozon API client
│   │   ├── client.py        # HTTP client (auth, retry, rate-limit)
│   │   ├── rate_limiter.py  # Token bucket
│   │   └── endpoints/       # Per-domain endpoint wrappers (12 modules)
│   ├── templates/           # Jinja2 + HTMX
│   └── static/              # CSS, JS
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python FastAPI (async) |
| ORM | SQLAlchemy 2.0 (async) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Frontend | Jinja2 + HTMX + Alpine.js |
| HTTP Client | httpx (async) |
| Task Queue | APScheduler |

## Rate Limiting

The Ozon API has a limit of 80 requests per minute per client. The built-in `TokenBucketRateLimiter` automatically:
- Acquires tokens before every API call
- Inserts 0.6s delay between batch calls
- Auto-chunks requests to 100 items per call

## Sync Strategy

**Pull-primary**: Ozon is the source of truth for orders, finance, and prices. Only products and manual price/stock adjustments push from local to Ozon.

- Categories: daily full sync
- Products: 15-min incremental pull + on-demand push
- Prices/Stocks: 5-min cursor-paginated pull
- FBS Orders: 2-min delta pull
- Finance: 30-min rolling sync

## License

MIT
