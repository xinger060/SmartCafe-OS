#!/command/with-contenv bashio
# shellcheck shell=bash

# ===========================================================================
# 把 add-on「配置」页里的选项写进 /data/smartcafe-server/config.json
#
# ⚠️ 原版是每次启动都用 `cat > config.json` 把整个文件覆盖掉，
#    而那个模板里【没有 ha_long_lived_token】。后果是一条完整的故障链：
#
#      在管理界面/API 里设好 HA 长期令牌
#        → 容器一重启（比如 HA 重启），run.sh 把 config.json 重写
#        → 令牌没了
#        → 智咖拿空令牌去调 HA 的 /api/pc_manager/status
#        → 被 401 挡回来（HA 日志里会刷 "invalid authentication"）
#        → 后台「PC状态」列永远显示「离线」
#
#    现在改成【合并】：选项有值的才覆盖对应的键，其它键原样保留。
#    这样令牌不会再被冲掉，顺带也解决了"在管理界面改的配置一重启就丢"的老毛病。
# ===========================================================================

mkdir -p /data/smartcafe-server

# 先把选项读进环境变量。用环境变量而不是直接拼进 JSON，
# 是为了避免密码/令牌里的特殊字符把 shell 或 JSON 搞坏。
export HA_BASE_URL="$(bashio::config 'ha_base_url')"
export HA_USERNAME="$(bashio::config 'ha_username')"
export HA_PASSWORD="$(bashio::config 'ha_password')"
export HA_TOKEN_REFRESH_TIME="$(bashio::config 'token_refresh_time')"
export HA_LONG_LIVED_TOKEN="$(bashio::config 'ha_long_lived_token')"

node -e '
const fs = require("fs");
const p = "/data/smartcafe-server/config.json";
let c = {};
try { c = JSON.parse(fs.readFileSync(p, "utf-8")); } catch (e) { c = {}; }

// 只在这些选项【有值】时才覆盖 —— 避免选项留空时把已经设好的值抹掉
const set = (k, v) => { if (v) c[k] = v; };
set("ha_base_url",         process.env.HA_BASE_URL);
set("ha_username",         process.env.HA_USERNAME);
set("ha_password",         process.env.HA_PASSWORD);
set("ha_long_lived_token", process.env.HA_LONG_LIVED_TOKEN);

// 这两项即使为空也要写：token_refresh_time 为空 = 关闭定时刷新
c.token_refresh_time = process.env.HA_TOKEN_REFRESH_TIME || "";
c.port = 8766;
if (c.password_hash === undefined) { c.password_hash = ""; }
if (c.password_salt === undefined) { c.password_salt = ""; }

fs.writeFileSync(p, JSON.stringify(c, null, 2));
'

# 兜底：万一 node 不可用、config.json 还是没生成，就用模板建一个。
# 少了这个的话，端口会退回默认 8080，而 add-on 的 ingress_port 是 8766，
# 管理后台会直接打不开。
if [ ! -f /data/smartcafe-server/config.json ]; then
  bashio::log.warning "node 合并失败，使用兜底模板生成 config.json"
  cat > /data/smartcafe-server/config.json << EOF
{
  "ha_base_url": "${HA_BASE_URL}",
  "ha_username": "${HA_USERNAME}",
  "ha_password": "${HA_PASSWORD}",
  "token_refresh_time": "${HA_TOKEN_REFRESH_TIME}",
  "ha_long_lived_token": "${HA_LONG_LIVED_TOKEN}",
  "port": 8766,
  "password_hash": "",
  "password_salt": ""
}
EOF
fi

# Create empty data files if they don't exist
if [ ! -f /data/smartcafe-server/whitelist.json ]; then
  echo "[]" > /data/smartcafe-server/whitelist.json
fi

if [ ! -f /data/smartcafe-server/audit.json ]; then
  echo "[]" > /data/smartcafe-server/audit.json
fi

# Start the server
cd /opt/server
exec node server.js
