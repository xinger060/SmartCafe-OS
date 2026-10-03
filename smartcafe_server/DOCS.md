# 智咖网吧智能管理系统

局域网终端与 Home Assistant 安全对接系统。服务端集中管控，客户端零信任。

## 功能特性

- 终端设备白名单管理
- 电脑名称、IP、MAC地址管理
- 客户端功能开关控制
- 分类管理（创建、重命名、删除、拖拽排序）
- 批量添加（IP段模式 + 文本导入模式）
- 搜索、排序、筛选功能
- 自动获取 HA 访问令牌
- 定时刷新令牌（可选）
- 终端自动登录 HA 仪表板
- 与pc_manager集成同步设备
- WOL远程唤醒功能
- 在线状态检测
- Apple 风格管理界面

## 配置说明

### HA Base URL
Home Assistant 的访问地址，例如：`http://homeassistant.local:8123`

### HA Username / Password
用于自动获取访问令牌的 HA 账号凭据。令牌会缓存在内存中，过期自动刷新。

### Token Refresh Time
定时刷新令牌的时间，格式为 HH:MM（例如：03:30）。留空禁用。

### Port
服务端口，默认 8765。

## 使用方法

1. 安装应用后，在配置中填写 HA 地址和凭据
2. 保存配置，服务端会自动获取令牌
3. 在「设备管理」中添加终端设备：
   - 电脑名称：自定义设备名称
   - IP地址：终端设备的IP
   - MAC地址：用于WOL唤醒（可选）
   - 客户端：控制是否允许终端连接
4. 终端设备访问 `http://服务端IP:8765/api/terminal/pull` 获取配置

## API 接口

### GET /api/terminal/pull
终端设备调用，获取HA访问配置。

响应：
```json
{
  "url": "http://ha:8123/lovelace?kiosk=true",
  "width": 1920,
  "height": 1080,
  "ha_tokens": {
    "access_token": "...",
    "refresh_token": "..."
  }
}
```

## 端口说明

- 8765：终端 API 端口（通过 Ingress 映射）

## 数据持久化

所有配置和白名单数据存储在 `/data/smartcafe-server/` 目录中，应用更新不会丢失数据。
