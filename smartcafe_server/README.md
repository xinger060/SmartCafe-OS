# 智咖网吧智能管理系统

网吧智能管理系统服务端 - Home Assistant Add-on

局域网终端与 HA 安全对接，服务端集中管控终端白名单，自动获取并刷新 HA Token，终端设备零凭证接入。

## 功能

- **设备白名单** — 按 IP 授权终端，支持分类管理
- **客户端开关** — 控制设备是否允许终端连接
- **分类管理** — 创建、重命名、删除分类，按分类筛选设备
- **批量添加** — IP段模式 + 文本导入模式
- **复制设备** — 基于已有设备快速复制并修改
- **Token 自动管理** — 通过 HA Auth API 自动获取 access_token / refresh_token
- **定时刷新** — 可配置每日定时刷新，避免 Token 过期
- **自动登录** — 终端通过 localStorage 注入 Token 实现免登录
- **窗口控制** — 按设备设置窗口宽高，支持全屏 Kiosk 模式
- **Apple 风格 UI** — 管理面板采用 Apple Design Language

## 安装

1. 在 HA 中添加自定义 Add-on 仓库：
   ```
   https://github.com/zhutianlei/SmartCafe-OS
   ```
2. 安装「智咖系统」
3. 在配置中填写 HA 地址和凭据
4. 启动后通过 HA 侧边栏访问管理面板

## 配置

| 配置项 | 说明 | 默认值 |
|---|---|---|
| `ha_base_url` | Home Assistant 地址 | `http://homeassistant.local:8123` |
| `ha_username` | HA 登录用户名 | — |
| `ha_password` | HA 登录密码 | — |
| `token_refresh_time` | 定时刷新时间 `HH:MM`，留空禁用 | — |
| `port` | 服务端口 | `8765` |

## API

```
GET /api/terminal/pull
```

服务端通过 Socket 提取客户端 IP，查询白名单后返回配置。

| 状态码 | 响应 | 条件 |
|---|---|---|
| 200 | `{"url":"...","width":1920,"height":1080,"ha_tokens":{...}}` | IP 在白名单且客户端已开启 |
| 403 | `{"error":"unauthorized"}` | IP 未授权 |
| 403 | `{"error":"client_disabled"}` | 客户端功能未开启 |
| 500 | `{"error":"internal"}` | 服务端异常 |

## 管理面板

默认账号：`admin` / `admin`（首次启动自动创建）

功能：
- **设备管理** — 增删改查终端设备，支持分类、批量添加、复制
- **分类管理** — 创建和管理设备分类，支持重命名和删除
- **搜索筛选** — 按名称/IP/MAC搜索，按状态/分类筛选
- **排序功能** — 按名称、IP、状态排序

## 数据持久化

所有配置和白名单存储在 `/data/smartcafe-server/`，Add-on 更新不会丢失数据。

## License

MIT
