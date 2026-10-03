const http = require('http');
const net = require('net');
const { getConfig, getWhitelist } = require('./storage');
const { getHaTokens } = require('./ha_auth');

const LIST_SENSOR = 'sensor.smartcafe_devices';
let heartbeatTimer = null;

function httpRequest(urlStr, data, token) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlStr);
    const postData = data ? JSON.stringify(data) : null;
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const req = http.request({
      hostname: url.hostname,
      port: url.port || 80,
      path: url.pathname,
      method: 'POST',
      headers
    }, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        try { resolve({ status: res.statusCode, data: JSON.parse(body) }); }
        catch { resolve({ status: res.statusCode, data: body }); }
      });
    });
    req.on('error', reject);
    if (postData) req.write(postData);
    req.end();
  });
}

function checkPort(ip, port = 445, timeoutMs = 2000) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    let done = false;
    const finish = (val) => {
      if (done) return;
      done = true;
      socket.destroy();
      resolve(val);
    };
    socket.setTimeout(timeoutMs);
    socket.on('connect', () => finish(true));
    socket.on('timeout', () => finish(false));
    socket.on('error', () => finish(false));
    socket.connect(port, ip);
  });
}

function sanitizeName(name) {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, '_')
    .replace(/^_|_$/g, '');
}

async function pushDeviceList() {
  const config = getConfig();
  if (!config.ha_username || !config.ha_password) {
    console.log('[Heartbeat] 未配置HA凭据，跳过心跳');
    return;
  }

  const haBase = config.ha_base_url.replace(/\/$/, '');
  let token;
  try {
    const tokens = await getHaTokens(config.ha_username, config.ha_password);
    token = tokens.access_token;
  } catch (e) {
    console.error('[Heartbeat] 获取Token失败:', e.message);
    return;
  }

  const whitelist = getWhitelist();
  const devices = whitelist
    .filter(item => item.ip)
    .map(item => ({
      ip: item.ip,
      mac: item.mac || '',
      name: item.name || item.ip,
      category: item.category || ''
    }));

  // 检测每台设备在线状态
  const checkResults = await Promise.all(
    devices.map(d => checkPort(d.ip).then(online => ({ ...d, online })))
  );

  // 创建/更新每台设备的独立 sensor
  for (const device of checkResults) {
    const sensorId = `sensor.smartcafe_${sanitizeName(device.name)}`;
    const state = device.online ? 'online' : 'offline';
    const attributes = {
      ip: device.ip,
      mac: device.mac,
      category: device.category,
      friendly_name: `智咖 ${device.name}`
    };

    try {
      await httpRequest(
        `${haBase}/api/states/${sensorId}`,
        { state, attributes, icon: device.online ? 'mdi:monitor' : 'mdi:monitor-off' },
        token
      );
    } catch (e) {
      console.error(`[Heartbeat] 更新 ${sensorId} 失败:`, e.message);
    }
  }

  // 更新设备列表汇总 sensor
  const listState = devices.length > 0 ? 'online' : 'offline';
  const listAttrs = {
    devices: checkResults.map(d => ({
      ip: d.ip, mac: d.mac, name: d.name,
      category: d.category, online: d.online
    })),
    device_count: devices.length,
    online_count: checkResults.filter(d => d.online).length,
    friendly_name: '智咖系统设备列表'
  };

  try {
    await httpRequest(
      `${haBase}/api/states/${LIST_SENSOR}`,
      { state: listState, attributes: listAttrs, icon: 'mdi:monitor-dashboard' },
      token
    );
    const onlineCount = checkResults.filter(d => d.online).length;
    console.log(`[Heartbeat] 同步完成: ${devices.length} 台设备, ${onlineCount} 台在线`);
  } catch (e) {
    console.error('[Heartbeat] 同步失败:', e.message);
  }
}

function startHeartbeat(intervalMs = 30000) {
  if (heartbeatTimer) clearInterval(heartbeatTimer);
  console.log(`[Heartbeat] 启动心跳，间隔 ${intervalMs / 1000}s`);
  pushDeviceList();
  heartbeatTimer = setInterval(pushDeviceList, intervalMs);
}

function stopHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
}

module.exports = { startHeartbeat, stopHeartbeat, pushDeviceList };
