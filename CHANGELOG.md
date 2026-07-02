# Changelog

## 2026-07-02 (UPDATE 4)

### Changed
- 原价自动计算：`原价 = 售价 ÷ 60%`（Ozon 要求原价≥售价）
- 售价输入框实时联动原价

---

## 2026-07-02 (UPDATE 3 — Final)

### Added
- 定价计算器渠道对比表 — 展开式明细（采购/运费/佣金/利润/货损/计费/赔付）
- 每个渠道独立显示佣金、利润、货损金额
- 渠道表免弹窗 — 点击行展开/收起成本拆解
- 售价/原价标签标注 ¥CNY，填入价格统一为人民币
- 目的地选择（🇷🇺俄罗斯/🇧🇾白俄罗斯/🇰🇿哈萨克斯坦）
- 全部渠道可选 — 移除自动最佳渠道，用户显式点击选择
- 代码上传 GitHub: [JACKWANG-ahero/ozon-erp](https://github.com/JACKWANG-ahero/ozon-erp)

### Fixed
- 运费统一为 CNY — 移除汇率换算（RETE 渠道定价本身就是人民币）
- `¥undefined` 修复 — 嵌套 `<tbody>` 导致 Alpine.js 渲染失败
- 服务器冷启动目录问题

### Changed
- 定价计算器从弹出式 → 展开式明细
- 渠道表重构：运费(¥) / 佣金(¥) / 利润(¥) / 货损(¥) / 售价(¥) 全部展示

---

## 2026-07-02 (UPDATE 2)

### Added
- RET 俄通收 48 条真实物流渠道（俄罗斯/白俄罗斯/哈萨克斯坦）
  - 定价公式：`运费 = 单价/kg × 重量 + 挂号费`
  - 支持按重量+货值+目的地+带电筛选
  - 时效标签：特快4-9天 / 标准10-15天 / 经济15-30天
  - 电池提示：❌禁带电 / ✅可带电 + 赔付上限
- 定价计算器全面升级 — 渠道对比表
  - 目的地选择（🇷🇺/🇧🇾/🇰🇿）
  - 遍历所有匹配渠道，展示运费+售价+时效+电池+赔付
  - 点击任意渠道行填入对应售价
  - 迭代收敛 + 验算验证
- ERP 币种全部统一为 CNY (人民币)

### Fixed
- `product_builder.py` else 分支 v2 → v3 格式（22 字段完整迁移）
- `rate_limiter.py` 竞态条件 — `report_429/success` 加 `threading.Lock()`
- `base.py` 移除死代码 `_batch_with_delay` + `_chunked`
- `order.py` 类型注解 `date` → `datetime`，清理未用 import

### Changed
- 定价计算器从单一结果 → 多渠道路线对比
- 表单币种选项加 ¥/₽ 图标

---

## 2026-07-02 (UPDATE 1)

### Added
- GitHub CDN 图片公网访问 — 本地上传自动同步到 `JACKWANG-ahero/ozon-cdn`，Ozon 可下载
- 商品管理多选批量操作（批量推送/归档/删除）
- 列表标签式筛选（草稿/已上架/失败/归档/已删除）
- 商品列表显示创建日期、价格列
- 类目联想搜索（中/俄双语，Ozon classify + 本地 DB 双路）
- 图片上传改为一框多选（最多30张，点击放大，第一张自动主图）
- 商品编辑页 — 表单预填所有字段
- 归档/软删除/恢复功能
- 新增端点：`/v1/product/import/info`、`/v1/product/import/pictures`、`/v1/product/import/by_sku`、`/v1/product/update/attributes`、`/v1/product/update/offer_id`、`/v2/products/delete`、`/v1/description-category/attribute/values/search`、`/v1/delivery-method/list`
- 聊天 API 扩展：`/v1/chat/send/file`、`/v1/chat/create`、`/v1/chat/history`、`/v1/chat/read`
- 分类列表模板、退货列表模板、变更日志

### Fixed
- `/v3/product/import` 请求体完全对齐官方 Schema（`description_category_id`、`type_id`、`dimension_unit`、`weight_unit`、`currency_code`、`attributes` 格式等14字段）
- `/v1/description-category/attribute` + `/values` 参数对齐官方（`description_category_id`、`type_id`、`language: "DEFAULT"`）
- `/v1/description-category/tree` 请求体加入 `language: "DEFAULT"`
- 产品导入改为异步 task_id 轮询流程
- 限流器分段退避 + 持久化冷却状态
- `order.py:54-55` `mapped_column` 缺少 `()` 调用
- `category_service.py:176` `category_id` 未定义变量（应为 `description_category_id`）
- `database.py` 移除重复的 `get_db()`
- `client.py` 移除死代码 `_backoff()`
- `prices.py:58` / `stocks.py:58` 响应解析缺少 `result` 层级
- `order_service.py:157-164` 订单财务只取第一个商品 → 改为 `sum()` 累加
- `product_service.py:272` `promotions` 移除可疑的 `REVIEWS_PROMO` 硬编码
- `product_service.py:104` 默认货币 `CNY` → `RUB`
- `product_builder.py` v2 格式 → v3 完整迁移
- `sync_service.py:59` `_finish_log` commit 加 try/except 保护
- `categories.py:23` 分类页渲染错误模板（`products/list.html` → `categories/list.html`）
- `product_service.py:394` `offer_id` 空字符串 fallback 不生效（`dict.get()` → `or`）
- `returns.py` 渲染 `finance/list.html` + `total=len(items)` 虚假分页 → 修复模板 + SQL COUNT
- `sourcing.py:430` `func.now()` → `datetime.now()`
- `product_service.py` 搜索补上 `name_zh` 中文名

### Changed
- 导航栏白色主题
- 商品名称中文优先、俄语必填
- 图片上传改为30张上限、点击放大
- 类目选择从树改为联想搜索
- 筛选从下拉改为标签式
- 默认显示草稿列表

