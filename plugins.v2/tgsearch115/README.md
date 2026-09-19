# 拦截mp订阅（tgsearch115）

MoviePilot 插件：订阅新增或周期扫描时按 TG 频道、观影 115 中文字幕、观影磁力中文字幕、聚影顺序搜索，经 MoviePilot 原生媒体识别确认后处理资源。115 分享使用插件内置 115 转存；完整磁力只使用插件内置 115 离线，不调用或回退 CMS。未命中时按现有最终回退配置交还 MoviePilot 默认搜索。

当前版本：`v4.8.0`。自动订阅会保存脱敏处理时间线，详情页可查看最近阶段及来源健康分；诊断不包含链接、凭据、分享码或完整任务标识，且不能替代 MoviePilot 最终整理确认。手动搜索的“搜索范围”位于搜索框上方，选择后点击搜索生效；下方“结果来源”用于即时筛选已有结果。手动搜索 API 统一返回资源类型、网盘类型、画质、中文字幕、原盘、季号和年份等结构化字段，页面优先按结构化字段筛选并兼容旧会话缓存。

TG115 会固定首次通过规则与媒体身份确认的磁力 BTIH 顺序，每次只运行一个候选；明确取消、失败或无资源后自动选择下一个不同 BTIH，默认最多提交 5 个。写请求超时或查询失败进入 `unknown` 并保持 TG115 所有权，按 BTIH 对账确认旧任务不存在前不会提交下一个，也不会释放 MoviePilot。下载中、已下载和待整理状态继续阻断 MoviePilot 原生搜索；候选耗尽或达到上限后才允许最终回退。队列顺序、索引、尝试历史和所有者通过插件数据持久化；电视剧在途期间通过保持订阅 `state=P` 阻断 MoviePilot 补搜，终态后按媒体库真实缺集重新处理。

当新版 MoviePilot/PostgreSQL 返回的 `MediaInfo` 缺少目标季首播年份时，插件只读调用宿主 TMDB 季接口补齐并缓存。若 `MediaChain` 遇到游标生命周期异常，插件按订阅精确 TMDB ID 读取宿主目标元数据，并重新核验候选标题/别名；不能凭标题相似自动处理。

需要实际处理已有订阅时，可调用受鉴权保护的 `POST /subscription/process` 并明确传入 `confirm=true`。它支持 `N`/`R` 状态并在未命中时恢复原状态，只排入同一有界高优先级队列；只有全部身份与资源规则通过时才会触发真实转存或下载。

观影电视剧搜索按“订阅总年份、目标季首播年份、无年份”依次查询，并将查询年份与季号同时写入缓存键。电影仍只查询订阅年份。干跑显示每次观影年份查询的召回及详情磁力字幕/清晰度聚合，便于定位召回、规则和身份确认的实际拒绝点。

---

## 一、核心特性

- **三源搜索**：TG 公开频道、观影资源站和聚影开发者 API
- **媒体身份确认**：使用 `MetaInfo`、`TorrentHelper` 和 `MediaChain` 校验标题、年份、类型、季号及 TMDB/豆瓣 ID
- **季级订阅搜索**：S00/S02/S03 使用独立关键词、周期键和来源缓存；错误季候选在 MoviePilot/TMDB 识别前剔除
- **识别并发门控**：插件内 `SubscribeChain`/`MediaChain` 调用串行执行，`kill_cursor` 或异常空结果只重建重试一次
- **磁力规则适配**：115 服务端磁力不因未知做种数被淘汰，其它 MoviePilot 规则与中字画质门槛不变
- **来源汇总通知**：新增订阅先临时认领，TG/观影/聚影结束后统一通知，失败才恢复给 MoviePilot 后续搜索
- **任务记录清理**：详情页“磁力下载任务”可一键清理；活动任务存在时保护性拒绝
- **精准手动搜索**：TG/观影/聚影结果按规范化片名和年份过滤，并按分享码或 URL 去重
- **双客户端观影详情**：httpx/HTML 路径被 WAF 拒绝时，使用 urllib 独立 Cookie/PoW 会话降级
- **TG 服务端搜索**：用 `t.me/s/{channel}?q=片名` 让 Telegram 服务器搜频道**全部历史**（不是只看最近 200 条），解决「明明有资源却搜不到」
- **资源站 PoW 破解**：站点用 RSW 时间锁 PoW 反机器人，本插件用纯 Python `pow(x,1<<t,N)` 约 1.5 秒解出（C 层快速模幂），**无需浏览器、无新依赖**
- **115 自动转存**：命中 115 链接后用 Cookie Web API 的 `share_snap` + `share_receive` 转存到指定目录
- **115 磁力离线**：完整观影磁力经 MP 规则和媒体 ID 确认后，优先用插件内置 115 离线接口，失败才回退 CMS
- **订阅干跑**：详情页可按订阅 ID 只读运行候选评估，返回脱敏的“候选年份 x 数量”、季级年份、规则及身份确认统计，不转存、不提交任务或修改订阅
- **详情页兼容**：对 MoviePilot v2.14 返回最小详情页能力标记，避免 Vue 联邦页面被宿主误判为空页面
- **启动兼容**：分享元数据缓存使用 `TtlCache(max_entries=...)`，避免 MoviePilot 加载阶段的参数异常
- **115 直连磁力（v4.7.0）**：使用 Cookie Web 云下载接口创建/查询任务；115 任务完成后仍等待 MP 整理历史，不误发 SubscribeComplete
- **全网盘展示**：夸克/百度/阿里/迅雷等资源展示链接；115 分享继续使用插件内置 115 转存，完整磁力仅使用插件内置 115 离线
- **115 扫码登录**：直连 115 二维码接口，扫码即得含 UID/CID/SEID 的 Cookie
- **订阅完成双模式**：`auto_finish` 开关——插件直接标记完成 / 让 MP 整理 115 后自己完成
- **自定义 Vue 前端**：Module Federation 暴露 Config/Page 组件，4 个标签页（手动转存 / 手动搜索 / TG 频道 / 插件设置）

---

## 二、目录结构

```
tgsearch115/
├── __init__.py          # 插件主类：事件监听 / 流程编排 / 12 个 API / 115 扫码登录
├── tg_scraper.py        # TG 频道爬虫：httpx + BS4，?q= 服务端搜全历史
├── site_scraper.py      # 目标资源站爬虫：解 PoW + 搜索 + 全网盘资源提取
├── juying_scraper.py    # 聚影开发者 API
├── identity_matcher.py  # MoviePilot 原生媒体身份确认
├── season_support.py    # 季号解析、季级关键词与缓存键
├── recognition_control.py # MoviePilot/TMDB 识别串行门控与安全重试
├── search_relevance.py  # 手动搜索片名/年份精准过滤
├── cms_client.py        # CMS 官方 Token API / 115 磁力离线
├── p115_offline.py      # 115 Cookie Web 磁力离线、状态、取消与重试
├── offline_tasks.py     # 115/CMS 通用脱敏任务账本
├── p115_transfer.py     # 115 转存：Cookie Web API share_snap + share_receive
├── README.md
└── frontend/            # Vue 3 + Vuetify 3 + Vite 5 (Module Federation)
    ├── src/components/Config.vue   # 配置弹窗（4 Tab）
    ├── src/components/Page.vue     # 详情页
    └── dist/assets/remoteEntry.js  # 构建产物（MP 前端远程加载）
```

安装：把整个 `tgsearch115` 目录放到 MoviePilot 插件目录（`/config/plugins` 或插件市场安装），重启即可。依赖（p115client / beautifulsoup4）启动时自动静默安装。

---

## 三、业务流程

```
订阅新增 (SubscribeAdded 事件)
  → 临时设 state=P，由单一队列运行 _handle_subscribe
  → recognize_media 识别媒体
  → _build_keyword → 只用片名（不含年份）
  → 三源搜索：
      · TG 频道 scraper.search(keyword)          → 全 115 链接
      · 资源站 site_scraper.search(keyword, year) → 全网盘（115 占少数）
      · 聚影 juying_api.search(keyword, year)     → 官方 API 资源
  → _build_torrents 构造 TorrentInfo（115 链接自动补提取码）
  → _filter_resources 复用 MP 规则组 + include/exclude
  → 115 分享按 share_code 去重
  → 本地标题/别名/年份/类型/季号初筛
  → MediaChain 识别候选，TMDB/豆瓣 ID 与订阅一致
  → 完整观影磁力：115 直连（失败按策略回退 CMS）→ 任务状态 → MP 整理历史
  → 115 分享：transfer.transfer() → share_snap → share_receive → 完成订阅
  任何环节失败 → 静默 return，MP 默认搜索照常（平滑回退）
```

---

## 四、配置项

### 115 网盘登录区
| 项 | 说明 |
|----|------|
| 启用插件 | 总开关 |
| 115 Cookie | 扫码登录后自动填入（需含 UID/CID/SEID） |
| 115 转存目录 | 如 `/电影`，不存在自动创建；也可填数字 cid |

### 观影 Tab
| 项 | 说明 |
|----|------|
| 完整磁力优先离线到 115 | 启用后仅通过插件内置 115 处理已确认的完整观影磁力 |
| 检查 115 离线 | 只读检查 115 签名与任务列表能力，不创建任务 |

### 插件设置 Tab
| 项 | 说明 |
|----|------|
| 启用目标资源站 | 开启后搜索时同时查 xn--wcv59z.com |
| 资源站 app_auth | 登录站点后从浏览器 Cookie 取 `app_auth` 值 |
| 测试连通 | 解 PoW + 试搜，验证 app_auth 是否有效 |
| 插件直接标记完成 | auto_finish：True=插件标记完成；False=让 MP 整理 115 后完成 |
| MP 过滤规则组 | 复用 MoviePilot 订阅过滤规则组 |
| 周期搜索 / 汇总通知开关 | 等 |

### TG 频道模块 Tab
- 单条添加 / JSON 批量导入 / 批量删除
- 仅支持公开用户名频道（如 `@share115`），私有频道无法网页抓取
- 代理自动用 MoviePilot 的 `settings.PROXY`

---

## 五、目标资源站原理（site_scraper.py）

站点 `xn--wcv59z.com` 用 **RSW 时间锁 PoW** 做反机器人：

1. `GET /` → 设 `browser_pow` cookie，返回验证页
2. `GET /res/pow` → 挑战 `{N, x, t}`（N=2048bit, t=200000）
3. 算 `y = x^(2^t) mod N`（连续平方 t 次）
4. `POST /res/pow {y}` → 设 `browser_verified` cookie 放行

**关键**：服务器只校验 `y` 的数学正确性，不校验耗时。JS 用解释型 worker 慢算（数秒），Python 内置 `pow(x, 1<<t, N)` 走 C 层快速模幂，**1.5 秒**算出相同 `y`。

资源 API：
- `GET /res/search_suggest?q=片名` → `[{title, id, dir, year, ename, score}]`
- `GET /res/downurl/{dir}/{id}` → `panlist: {url, name, p(提取码), tname(网盘类型)}`

网盘类型**按 URL 域名判定**（`tname` 是上传者自填，常不准）：115 / quark / baidu / aliyun / xunlei / cloud189 / uc。

> 注意：该站资源**大多是夸克/百度/阿里/迅雷，115 占比很小**。插件提取全部网盘；115 分享可直接转存，完整磁力按配置优先通过插件内置 115 直连、失败再回退 CMS，其它网盘在手动搜索中展示链接与提取码。

---

## 六、后端 API（15 个，全部 `auth="bear"`）

挂载 `/api/v1/plugin/TgSearch115{path}`：

| 路径 | 作用 |
|------|------|
| `/config/get` `/config/save` | 读/存配置（即时生效） |
| `/check_channel` `/check_all` | 检查 TG 频道连通性 |
| `/qrcode/get` `/qrcode/status` | 115 扫码登录 |
| `/transfer` | 手动转存 115 分享链接 |
| `/magnet/offline` | 通过插件内置 115 创建磁力离线任务 |
| `/check_115_offline` | 只读检查 115 签名/任务列表能力，不创建任务 |
| `/search` | 手动搜索（TG + 资源站，返回带网盘类型） |
| `/dir_info` `/dirs` | 115 目录查询/浏览 |
| `/verify_cookie` | 验证 115 Cookie |
| `/check_site` | 验证资源站 PoW + app_auth |

---

## 七、首次使用

1. **115 登录**：配置页点「扫码登录」，用 115 客户端扫码，Cookie 自动填入。
2. **TG 频道**：「TG 频道模块」Tab 添加公开频道（如 `@share115`）。
3. **资源站（可选）**：「插件设置」Tab 开启资源站，填入 `app_auth`（登录站点后从浏览器 Cookie 复制），点「测试连通」。
4. 开启插件，新增一个订阅，观察日志（关键字 `【TG115】`）。
5. 更新插件后若 UI 没变，**Ctrl+F5 强制刷新**或重启 MP（`remoteEntry.js` 无 cache-buster）。

---

## 八、常见问题排查

### PanSou 搜不到资源（来源熔断 / 504）

**现象**：日志中 pansou 的 `returned_count` 始终为 0，反复出现以下两类告警之一：

```
【TG115】PanSou HTTP 504，退避 1.0 秒后重试
【TG115】pansou 来源熔断中，剩余 N 秒，本轮跳过
【TG115】pansou 请求超过 60 秒，已释放订阅队列
【TG115】pansou 上一请求仍在结束中，本轮跳过避免并发
```

**根因链**（2026-09-19 实际排查记录）：

1. PanSou 聚合服务（默认 `http://192.168.1.15:8888`）偶发上游超时，`/api/search` 返回 **504**。
2. `pansou_scraper.py` 旧版对 504 重试 3 次 + 退避，单次搜索最长占 60 秒，期间 `BoundedSourceRunner` 并发锁被占满，后续轮次报「上一请求仍在结束中，本轮跳过」。
3. 连续失败达到阈值（默认 3 次）后，`SourceCircuitBreaker`（`runtime_control.py`）将 pansou 标记为熔断，冷却 **3600 秒（1 小时）**。冷却期内每一轮搜索直接 `allow()` 返回 False、跳过、不发请求——**即使 PanSou 服务早已恢复，插件仍在干等冷却到期**。

**排查步骤**：

1. **先确认 PanSou 服务本身是否正常**（这是根因排查的第一步）：
   ```bash
   curl -w "health: HTTP %{http_code}, %{time_total}s\n" --max-time 10 "http://192.168.1.15:8888/api/health"
   curl -w "search: HTTP %{http_code}, %{time_total}s\n" --max-time 30 "http://192.168.1.15:8888/api/search?kw=test"
   ```
   - `/api/health` 返回 200 但 `/api/search` 30 秒无响应 → PanSou 上游聚合源卡死，**重启 PanSou 服务**即可。
   - `/api/search` 秒回 200 + JSON → 服务正常，问题在插件侧熔断冷却（见下）。

2. **PanSou 真实 API 对照**（PanSou 是 Vue SPA，无 openapi.json，接口写在前端 JS bundle 里）：
   - 搜索：`GET /api/search`，参数 `kw`（关键词）+ `cloud_types`（逗号分隔，如 `115,magnet`）+ 可选 `refresh=true`
   - 健康检查：`GET /api/health`
   - 认证：`GET /api/auth/verify`（若 PanSou 开启了登录鉴权，需在插件配置 `pansou_token`）
   - 插件调用方式见 `pansou_scraper.py` 的 `PanSouClient.search()`，默认 `cloud_types=115,magnet`，与 PanSou 真实接口一致。

3. **解除熔断**：熔断状态只存内存，**重启 MoviePilot / 重新加载插件 / 保存一次插件设置**（触发 `init_plugin`）即可清零。

**已实施的代码修复**（v4.8.x）：

| 改动 | 文件 | 说明 |
|------|------|------|
| 熔断自动恢复 | `__init__.py` 搜索主循环 `allow()` 跳过分支 | pansou 熔断时先做一次轻量 `health_check`（实测 0.02 秒）；服务已恢复则调 `success()` 自动解除熔断并继续本轮搜索，不再干等冷却到期。其他来源不受影响。 |
| 504 fail-fast | `pansou_scraper.py` `_request()` | 504（网关超时）从可重试集合移除，现在只在 429/500/502/503 重试。504 立即返回失败，尽快释放并发锁、尽快记入熔断器，避免长时间占锁拖累后续轮次。 |

**验证**：修复后触发搜索，预期日志出现 `PanSou 健康检查通过，已自动解除熔断，本轮恢复搜索`，随后 pansou 正常返回资源（`returned_count > 0`）。

### 隐私说明：115 Cookie 不会被上传到第三方

- 115 Cookie **只发给 `*.115.com` 官方域名**（转存 `share_snap`/`share_receive`、磁力离线 `clouddownload.115.com`），这是网盘功能必需的鉴权。
- 资源站（`site_scraper.py`）使用**独立的 urllib + http.cookiejar** 会话，只带 `app_auth` + PoW cookie，**不携带 115 Cookie**。
- CMS 客户端（`cms_client.py`）的 httpx client 不带任何 Cookie header，body 只含磁力链接。
- 本地持久化的任务记录经 `cms_tasks.py` 的 `_safe_label()` 主动脱敏（URL/cookie/token/api_key/authorization → `[已脱敏]`）。
- 配置升级迁移（`__init__.py` `init_plugin` 内 `_legacy_old_defaults`）是纯本地内存操作，只处理超时/限流配置键，**不发起网络请求、不碰 cookie 字段**。
