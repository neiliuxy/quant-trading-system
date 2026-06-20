# Data Management Page 设计

## Goal

在现有 Web dashboard 内新增一个偏运维的数据管理页，把已经就绪的 DataHub 后端能力直接暴露给
用户使用。v1 聚焦三件事：

- 查看有哪些数据集可用
- 查看当前缓存条目及其过滤结果
- 发起数据刷新并跟踪刷新状态

页面面向运维式使用场景，要求将个股数据与大盘数据明确分开显示，并让刷新队列在操作过程中始终可见。

## Background

后端接口已经具备完整的数据管理基础能力，定义在 `server/api.py`：

- `GET /api/data/datasets`
- `GET /api/data/cache`
- `POST /api/data/refresh`
- `GET /api/data/refresh/{refresh_id}`

最近的数据层工作集中在 DataHub v1 收尾与测试补强，后端已可稳定提供数据集列表、缓存查询、刷新创建和
单任务状态查询。当前缺口在前端：`web/` 仍只有回测 dashboard，尚无数据层可视化入口。相比继续扩展底层
能力，这一页可以最快把 DataHub 能力变成用户可见、可操作的产品表面。

## Scope

In scope:

- 在现有 React/Vite dashboard 内新增 `Data Management` 视图，而不是另起一套页面壳。
- 提供 `个股` / `大盘` 两个分段视图，分别承载对应数据集与缓存查询。
- 展示数据集目录，包括 `label`、`dataset_type`、`source_name`、`ttl_seconds`、
  `historical_ttl_seconds`、`symbol_required`。
- 查询并展示缓存条目，支持按 `dataset_type`、`symbol`、`start/end` 过滤。
- 发起单个数据集刷新，并轮询刷新状态直到结束。
- 在右侧常驻显示刷新队列和最近已知 refresh 状态。
- 补充对应前端 API 包装、类型定义、组件测试。

Out of scope:

- 新增后端接口或修改 DataHub 领域逻辑。
- 批量 refresh、定时 refresh、TTL 配置编辑、数据源配置编辑。
- 全局缓存统计图、历史趋势图、管理后台级别权限控制。
- e2e 测试。
- 独立数据服务进程、跨进程文件锁、golden 兼容录制测试等已被上游 spec 明确推迟的方向。

## Information Architecture

页面放在现有 dashboard 内部，作为一个新的顶层视图 `Data Management`。其内部结构固定为三栏：

1. 左栏 `Dataset Catalog`
2. 中栏 `Cache Workspace`
3. 右栏 `Refresh Queue`

顶层使用分段切换，仅保留两个 segment：

- `个股`
- `大盘`

分类规则不新增后端字段，直接复用已有 `symbol_required`：

- `symbol_required = true` 归入 `个股`
- `symbol_required = false` 归入 `大盘`

这样可直接消费现有 `GET /api/data/datasets` 返回结构，不需要调整 DataHub spec 或 registry。

## Layout Decision

已确认采用：

- **B. Segmented operations view**
- **Q2. Queue as persistent right rail**

原因如下：

- 这是偏运维页面，主工作流是筛选、查看缓存、发起刷新、盯队列状态；队列常驻比单独切页更顺手。
- 个股与大盘需要明确分开，但不要求在同一时刻并排比较；用 segment 切换比双表并列更稳。
- 与现有 dashboard 的信息密度和组件风格更一致，不需要重造新的导航层级。

## Main User Flow

### 1. 进入页面

进入 `Data Management` 后默认落在 `个股` 分段。页面并行加载：

- `GET /api/data/datasets`
- `GET /api/data/cache`（使用当前分段的默认过滤）

右侧 `Refresh Queue` 在 v1 只显示“当前前端会话中创建过的 refresh”以及“用户主动查询过详情的
refresh”。当前后端没有 refresh 列表接口，因此 v1 不伪造“全局最近刷新记录”。

### 2. 切换分段

用户可在 `个股` / `大盘` 之间切换。

- 切换分段只影响展示与默认过滤，不重新拉取 datasets。
- 当前选中的 dataset 若不属于目标分段，则清空选中状态并回到该分段默认首项。
- 中栏 cache 查询条件同步切到该分段上下文。

### 3. 选择数据集

左栏展示当前分段下的数据集目录。用户点击某一项后：

- 高亮所选 dataset
- 中栏 cache 过滤自动绑定该 `dataset_type`
- 下方 refresh form 自动填入该 `dataset_type`
- 若是个股数据集，则保留 symbol 输入；若是大盘数据集，则 symbol 默认为空且不展示输入框

### 4. 查询缓存

中栏提供 cache 过滤表单：

- `dataset_type`：由选中 dataset 驱动
- `symbol`：仅在 `symbol_required = true` 时显示
- `start`
- `end`

点击查询后请求 `GET /api/data/cache`。结果表格展示后端返回的缓存条目原始字段，按“运维排查”优先级排布，
至少包括：数据集类型、symbol、时间范围、缓存路径或标识、更新时间、行数/命中信息（以接口实际返回为准）。

### 5. 发起刷新

中栏底部提供 refresh form。字段直接对齐当前后端接口：

- `dataset_type`
- `symbol`（条件出现）
- `start`
- `end`
- `frequency`
- `force_refresh`

提交 `POST /api/data/refresh` 后：

- 成功时，把新 refresh 插入右侧队列顶部
- 自动开始轮询 `GET /api/data/refresh/{refresh_id}`
- 若当前中栏展示的正是该数据集范围，则在 refresh 完成后自动重新查询 cache

### 6. 观察刷新状态

右栏 `Refresh Queue` 始终可见，展示：

- 运行中 / 排队中 refresh
- 最近已结束的 refresh
- 选中 refresh 的详情

状态至少覆盖：

- `queued`
- `running`
- `completed`
- `failed`

## Components

建议从当前过大的 [web/src/App.tsx](/Users/neiliuxy/Workspace/quntx/quant-trading-system/web/src/App.tsx)
中拆出数据管理相关单元，避免继续堆叠到单文件中。

### `DataManagementView`

顶层容器，负责：

- 当前 segment
- datasets 加载与分类
- 当前选中 dataset
- cache filters
- cache 查询结果
- 本地 refresh 队列与轮询

### `DatasetCatalog`

左栏目录组件，负责：

- 展示当前 segment 可用 datasets
- 高亮当前选中项
- 展示 TTL / source / symbol_required 等摘要

只做展示和选择，不承担数据请求。

### `CacheTable`

中栏缓存结果区，负责：

- 展示过滤表单
- 展示加载、空状态、错误状态
- 渲染缓存条目表格

### `RefreshQueue`

右栏队列组件，负责：

- 展示 refresh 列表及状态 badge
- 展示选中 refresh 的细节
- 标记轮询中状态

## API and Types

在 `web/src/api.ts` 中新增前端包装：

- `listDatasets()`
- `listCache(params)`
- `createRefresh(payload)`
- `getRefresh(refreshId)`

在 `web/src/types.ts` 中新增或扩展：

- `DatasetSpec`
- `CacheEntry`
- `DataRefresh`
- `DataSegment = 'stock' | 'index'`

这些类型必须尽量贴近现有后端返回，避免前端自行发明字段语义。

## State and Error Handling

### Loading

- 初始进入页面时，datasets 与初始 cache 并行加载。
- cache 查询与 refresh 提交分别维护独立 loading 状态。
- refresh 轮询期间，队列中对应项目显示进行中状态。

### Empty States

- 当前分段无可用 dataset：显示明确空状态，不展示无效 form。
- cache 查询无结果：显示“没有匹配的缓存条目”，不是空白表格。
- 队列为空：显示“当前会话尚未发起刷新任务”。

### Errors

- `400`：直接展示接口返回 detail，定位为用户输入或参数问题。
- `409 refresh_in_progress`：单独映射为“该数据范围已有刷新任务在运行”，不使用泛化错误文案。
- refresh 轮询失败：保留最后一次已知状态，并允许用户手动继续查询。
- datasets 或 cache 初始加载失败：局部报错，不拖垮整个 dashboard 其余部分。

## Visual Direction

视觉上沿用现有 dashboard 样式语言，不引入新设计系统：

- 浅色背景
- 紧凑表格
- 轻量 panel 边框
- 与现有 `status-*` 体系一致的状态 badge

布局要求：

- 桌面端三列：catalog / cache / queue
- 笔记本宽度下仍以三列为主，但压缩侧栏宽度
- 窄屏时改为纵向堆叠，`Refresh Queue` 移到底部

不做 marketing 风格卡片，不做装饰性 hero，不做花哨概览图。

## Testing

测试聚焦前端组件与逻辑层，延续仓库现有测试风格。

新增测试至少覆盖：

- `api.ts` 的 4 个新请求包装
- `DataManagementView` 的分段切换
- dataset 选择后驱动 cache 过滤与 refresh 默认值
- refresh 创建成功后进入队列并触发轮询
- refresh 完成后自动重新拉取当前 cache
- `RefreshQueue` 对 `queued/running/completed/failed` 的渲染
- `409 refresh_in_progress` 的专门错误提示

不做 e2e。v1 的风险主要是状态编排，不是浏览器自动化流程。

## Acceptance Criteria

- dashboard 内出现新的 `Data Management` 视图，不影响现有回测页面工作流。
- 数据集按 `个股` / `大盘` 明确分段显示，分类规则基于 `symbol_required`。
- 用户可查看数据集目录、查询缓存、发起 refresh，并在同一视图中跟踪 refresh 状态。
- 右侧 refresh 队列在操作过程中始终可见，不需要切换到独立页面才能看状态。
- refresh 完成后，当前相关 cache 视图会自动刷新。
- 不新增后端接口即可完成 v1。
- 前端新增测试覆盖核心状态流，现有前端测试风格保持一致。

## Non-goals

- **全局 refresh 历史列表**：后端没有 refresh list API，v1 不假装自己有全局观测能力，只展示当前会话
  已知任务。
- **批量刷新**：会迅速引入排队策略、并发语义、失败恢复等额外问题，不符合 v1 收敛目标。
- **底层并发/锁语义增强**：跨进程文件锁已被上游明确推迟，单进程原型阶段不在这个页面解决。
- **扩展新数据集**：页面设计应兼容未来扩展，但本次不包含新增 dataset adapter 或 registry 变更。
