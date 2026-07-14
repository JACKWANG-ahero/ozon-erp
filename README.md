# Ozon ERP — 俄罗斯电商管理系统

面向 Ozon 跨境卖家的全栈 ERP 系统。从中国供应商采购到 Ozon 平台上架的全链路管理。

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    Ozon ERP v1.0                        │
├───────────────┬───────────────────────┬─────────────────┤
│  供应商端      │      ERP 后台         │    Ozon 平台     │
│  (1688采购)   │  FastAPI + SQLite     │  Seller API     │
├───────────────┴───────────────────────┴─────────────────┤
│  📦 商品管理  │  💰 定价计算  │  🌐 AI翻译  │  🚀 上架  │
└─────────────────────────────────────────────────────────┘
```

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11+ · FastAPI (async) · SQLAlchemy 2.0 |
| 数据库 | SQLite (开发) / PostgreSQL (生产) |
| 前端 | Jinja2 · HTMX · Alpine.js · Tailwind CSS |
| AI | 豆包 Doubao (多模态) · DeepSeek (文本翻译) |
| 集成 | Ozon Seller API v3 · GitHub CDN · RETS 物流 |
| 工具 | Playwright · uvicorn · httpx · Pillow |

## 核心功能

### 📦 商品管理
- 双栏表单：🟠供应商端 + 🔵Ozon 输出端
- 类目联想搜索（中/俄双语，Ozon API + 本地 DB 双路）
- 本地图片 → GitHub CDN → Ozon 公网 URL
- 批量操作（多选推送/归档/删除）
- 软删除 + 回收站恢复
- 标签式筛选（草稿/已上架/失败/归档/已删除）

### 🌐 AI 翻译
- **豆包 Doubao**：图片+中文 → 俄语标题/描述/关键词（多模态）
- **DeepSeek**：纯文本翻译（豆包失效时兜底）
- 自动过滤：批发/货源/相框/半成品等 C 端禁用词（中+俄 20+词）
- 俄语规范：`набор для вышивки` 开头 · `рисунок с X` · `пяльцы` 绣绷

### 💰 定价计算器
- RETS 俄通收 **48 条**真实物流渠道（俄/白俄/哈）
- 迭代求解：`售价 = (采购成本 + 运费 + 货损) / (1 - 佣金率 - 利润率)`
- 多渠道路线对比表（运费/佣金/利润/货损/售价/电池/赔付）
- 展开式明细 · 点击行填入售价 · 原价 = 售价 ÷ 60%
- 计费公式：`运费 = 单价(CNY/kg) × 重量 + 挂号费(CNY/票)`

### 🚀 Ozon 推送
- V3 API 完整字段映射（14 必填字段）
- 异步导入 → `task_id` 轮询 `/v1/product/import/info`
- 分段限流器（15s 间隔 + 零重试 + 持久化冷却）
- 推送结果详情展示 · 错误码友好提示

## 项目结构

```
ozon-erp/
├── app/
│   ├── main.py               # FastAPI 入口 (lifespan/static/middleware)
│   ├── config.py              # Pydantic Settings (60+ 配置项)
│   ├── database.py            # 异步 SQLAlchemy 引擎
│   ├── dependencies.py        # get_db / get_ozon_client / templates
│   ├── api/                   # 路由层 (10 模块)
│   │   ├── products.py        # 商品 CRUD + 推送 + 翻译/描述/定价 API
│   │   ├── categories.py      # 类目树 + 联想搜索 JSON API
│   │   ├── orders.py          # FBS/FBO 订单
│   │   ├── sourcing.py        # 1688 采购管理
│   │   ├── pricing.py         # 价格管理
│   │   ├── inventory.py       # 库存管理
│   │   ├── finance.py         # 财务管理
│   │   ├── returns.py         # 退货管理
│   │   ├── dashboard.py       # 仪表盘
│   │   ├── sync.py            # 同步管理
│   │   └── router.py          # 路由汇总
│   ├── services/              # 业务逻辑层 (12 模块)
│   │   ├── product_service.py     # 商品 CRUD + Ozon 推送 (482 行)
│   │   ├── category_service.py    # 类目同步 + 55 种子类目
│   │   ├── pricing_calculator.py  # RETS 迭代定价算法
│   │   ├── translation.py         # DeepSeek 翻译 (中→俄)
│   │   ├── doubao_service.py      # 豆包多模态 (图片+文字)
│   │   ├── image_handler.py       # GitHub CDN 上传 + 1688 图片下载
│   │   ├── order_service.py       # 订单处理 (FBS/FBO)
│   │   ├── finance_service.py     # 财务交易
│   │   ├── price_service.py       # 价格管理
│   │   ├── inventory_service.py   # 库存管理
│   │   ├── sync_service.py        # 同步编排
│   │   └── analytics_service.py   # 数据分析
│   ├── models/               # ORM 模型 (17 张表)
│   │   ├── product.py            # 商品 / 属性 / 图片
│   │   ├── category.py           # 类目 / 属性 / 字典值
│   │   ├── shipping_channel.py   # RETS 48 渠道
│   │   ├── price.py              # 价格 / 历史
│   │   ├── order.py              # 订单 / 明细 / 状态
│   │   ├── finance.py            # 财务交易
│   │   ├── stock.py              # 库存
│   │   ├── warehouse.py          # 仓库
│   │   ├── return_model.py       # 退货
│   │   ├── chat.py               # 聊天 / 消息
│   │   ├── sync_log.py           # 同步日志
│   │   └── sourcing.py           # 1688 采购 / SKU
│   ├── integrations/         # Ozon API 客户端
│   │   ├── client.py             # HTTP 客户端 (认证/限流/异常)
│   │   ├── rate_limiter.py       # 分段限流 + 持久冷却
│   │   ├── endpoints/            # 12 个 API 端点封装
│   │   │   ├── products.py       # /v3/product/* (14 方法)
│   │   │   ├── categories.py     # /v1/description-category/*
│   │   │   ├── orders_fbs.py     # /v3/posting/fbs/*
│   │   │   ├── orders_fbo.py     # /v2/posting/fbo/*
│   │   │   ├── prices.py         # /v1/*/prices
│   │   │   ├── stocks.py         # /v2/*/stocks
│   │   │   ├── finance.py        # /v3/finance/*
│   │   │   ├── warehouse.py      # /v1/warehouse/*
│   │   │   ├── chat.py           # /v1/chat/*
│   │   │   └── ...               # returns/reports/base
│   │   └── schemas/              # Ozon API 请求/响应模型
│   ├── templates/            # Jinja2 模板 (14 页面)
│   │   ├── base.html             # 基础布局 (白色导航栏)
│   │   ├── products/             # 列表/表单/详情
│   │   ├── orders/               # 列表/详情
│   │   ├── categories/           # 类目列表
│   │   ├── returns/              # 退货列表
│   │   └── ...
│   └── static/               # CSS / JS / 图片上传目录
├── scripts/
│   └── inspect_1688_cart.py  # 1688 进货单 API 探测
├── .env                      # 环境变量 (API 密钥)
├── .gitignore
├── CHANGELOG.md              # 详细更新日志
├── requirements.txt          # Python 依赖
└── README.md
```

## 数据库 (17 张表)

```
categories              → Ozon 类目树 (55 种子 + 实时同步)
category_attributes     → 类目属性定义
attribute_dictionaries  → 属性字典值
products                → 商品 (含 keywords/status/sync_status)
product_attributes      → 商品属性值
product_images          → 商品图片 (URL + 主图标记)
prices                  → 价格 (CNY, 含 vat)
price_history           → 价格变动历史
orders                  → FBS/FBO 订单
order_items             → 订单明细
order_status_history    → 订单状态流转
stocks                  → 库存 (仓库维度)
warehouses              → 仓库信息
finance_transactions    → 财务交易
returns                 → 退货记录
chats / chat_messages   → 买家聊天
sync_log                → 同步审计日志
sourcing_records        → 1688 采购记录
sourcing_skus           → 采购 SKU
shipping_channels       → RETS 48 条物流渠道
```

## 环境变量

```env
# ── Ozon Seller API ──
OZON_CLIENT_ID=4512621
OZON_API_KEY=315490ba-7a37-4249-bb40-3c09a187b1ad
OZON_BASE_URL=https://api-seller.ozon.ru

# ── AI 翻译 ──
DOUBAO_API_KEY=ark-bee81bda-...       # 豆包多模态 (火山引擎 ARK)
DEEPSEEK_API_KEY=sk-d00ca10e...       # DeepSeek 文本翻译

# ── GitHub CDN (图片公网访问) ──
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_OWNER=JACKWANG-ahero

# ── 数据库 ──
DATABASE_URL=sqlite+aiosqlite:///./ozon_erp.db
```

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 .env

# 3. 启动服务器
cd ozon-erp
python -m uvicorn app.main:app --host 127.0.0.1 --port 8081 --reload

# 4. 打开浏览器
http://127.0.0.1:8081/products/
```

## Ozon API 覆盖 (50+ 端点)

| 类别 | 端点 | 说明 |
|------|------|------|
| 商品创建 | `/v3/product/import` | 批量创建/更新 |
| 导入状态 | `/v1/product/import/info` | 异步结果轮询 |
| 商品列表 | `/v3/product/list` | 游标翻页 |
| 商品详情 | `/v3/product/info/list` | 批量查询 |
| 商品属性 | `/v4/product/info/attributes` | 完整属性 |
| 图片上传 | `/v1/product/import/pictures` | 产品图片 |
| 属性更新 | `/v1/product/update/attributes` | 更新属性值 |
| 类目树 | `/v1/description-category/tree` | 类目+type_id |
| 类目属性 | `/v1/description-category/attribute` | 属性定义 |
| 属性字典 | `/v1/description-category/attribute/values` | 字典值 |
| 属性搜索 | `/v1/description-category/attribute/values/search` | 搜索匹配 |
| 订单 FBS | `/v3/posting/fbs/*` | 列表/详情/发货 |
| 订单 FBO | `/v2/posting/fbo/*` | 列表/详情 |
| 价格 | `/v1/product/import/prices` `/v5/product/info/prices` | 更新/查询 |
| 库存 | `/v2/products/stocks` `/v4/product/info/stocks` | 更新/查询 |
| 财务 | `/v3/finance/transaction/*` | 交易列表/汇总 |
| 仓库 | `/v1/warehouse/list` `/v1/delivery-method/list` | 仓库/物流 |
| 聊天 | `/v1/chat/*` | 列表/发送/历史/已读 |
| 退货 | `/v1/returns/*` | 列表/详情 |
| 报告 | `/v1/report/*` | 生成/列表/详情 |

## 工作流

```
  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ 供应商端  │ →  │ 图片CDN  │ →  │ AI翻译   │ →  │ Ozon上架 │
  │ 中文+图片 │    │ GitHub   │    │ 豆包+DS  │    │ /v3/推送 │
  └──────────┘    └──────────┘    └──────────┘    └──────────┘
       │               │               │               │
  采购成本+重量    raw URL        俄语标题+描述     task_id→上架
       │               │               │               │
       └───────────────┴───────┬───────┴───────────────┘
                               │
                     ┌─────────▼─────────┐
                     │   💰 定价计算器    │
                     │   RETS 48 渠道    │
                     │   迭代求解售价     │
                     └───────────────────┘
```

## RETS 物流渠道 (48 条)

| 类别 | 重量 | 时效 | 单价/kg |
|------|------|------|---------|
| Extra Small | 0.001-0.5kg | 4-20天 | ¥26-47 |
| Small | 0.001-2kg | 4-20天 | ¥26-47 |
| Budget | 0.5-30kg | 10-20天 | ¥18-26 |
| Premium Small | 0.001-5kg | 4-20天 | ¥26-47 |
| Big | 2-35kg | 10-30天 | ¥17-29 |

覆盖：🇷🇺俄罗斯(28条) · 🇧🇾白俄罗斯(10条) · 🇰🇿哈萨克斯坦(10条)

## 统计

| 指标 | 值 |
|------|-----|
| 源文件 | 102 |
| 代码行数 | ~11,500 |
| 数据库表 | 17 |
| Ozon API 端点 | 50+ |
| 物流渠道 | 48 |
| 种子类目 | 55 |
| API 路由 | 30+ |
| HTML 模板 | 14 |

## 版本

**v1.0.0** · 2026-07

GitHub: https://github.com/JACKWANG-ahero/ozon-erp

更新日志: [CHANGELOG.md](CHANGELOG.md)
