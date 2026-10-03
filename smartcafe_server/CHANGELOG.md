# Changelog

## 1.0.6

### 修复：后台「PC状态」列永远显示「离线」

**根因链**（三处凑在一起才发作，前两处是原版的疏漏）：

1. `run.sh` 每次容器启动都用 `cat >` 把 `config.json` **整个覆盖**，
   而模板里没有 `ha_long_lived_token` —— 于是**令牌设了也活不过一次重启**。
2. `ha_long_lived_token` 不在 add-on 的 `options` / `schema` 里，
   所以界面和 Supervisor 配置页都填不了，只能靠 API 设。
3. 智咖拿空令牌去调 HA 的 `/api/pc_manager/status` → 401 →
   前端拿不到数据 → 一律显示「离线」。
   （HA 日志里会刷 `Login attempt or request with invalid authentication
   from ...smartcafe-server...`）

**改动**：

- `config.yaml`：新增 `ha_long_lived_token`（`password` 类型，界面打码），
  版本 1.0.5 → 1.0.6
- `config.yaml`：`breaking_versions` 清空。
  ⚠️ 原版写的是 `["1.0.4", "1.0.5"]`，含义是"从这两个版本升级必须卸载重装（数据全丢）"。
  1.0.6 修的就是 1.0.5 的问题，清空后 1.0.5 才能直接升上来。
- `run.sh`：`cat >` 整体覆盖改成**按选项合并**，只覆盖有值的键。
  令牌不再被冲掉；顺带修好了"在管理界面改的配置一重启就丢"的老毛病。
- `run.sh`：加了兜底，万一 node 合并失败也会生成带正确端口的 config.json。

> 配套：HA 端 `smartcafe_control/__init__.py` 补上了 `async_register_api()` 的调用。
> 原版定义了那三个 REST 视图（`/api/pc_manager/devices|status|wake`）却从来没注册，
> 所以那个接口一直是 404。两处都修好，「PC状态」列才会显示真实状态。

## 1.0.0

- 使用HA基础镜像构建，确保bashio正常运行
- 项目重构为SmartCafe-OS
- 新增电脑名称字段
- 新增客户端功能开关
- 新增批量添加文本导入模式（支持名称,IP,MAC格式）
- 新增搜索功能（按名称、IP、MAC搜索）
- 新增排序功能（按名称、IP、状态排序）
- 新增状态筛选功能
- 新增pc_manager集成设备同步API
- 新增WOL远程唤醒API
- 新增在线状态查询API
- 新增中文翻译文件
- 数据目录改为/data/smartcafe-server
