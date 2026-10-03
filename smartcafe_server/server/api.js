const express = require('express');
const router = express.Router();
const { findByIP, getConfig, recordConnection, getWhitelist } = require('./storage');
const { getHaTokens } = require('./ha_auth');

router.get('/terminal/pull', async (req, res) => {
  const clientIP = req.ip.replace('::ffff:', '');
  console.log(`[API] 终端请求: ${clientIP}`);

  const entry = findByIP(clientIP);

  if (!entry) {
    console.log(`[API] 未授权: ${clientIP}`);
    return res.status(403).json({ error: 'unauthorized' });
  }

  // 检查客户端功能是否开启
  if (entry.client_enabled === false) {
    console.log(`[API] 客户端功能未开启: ${clientIP}`);
    return res.status(403).json({ error: 'client_disabled' });
  }

  try {
    const config = getConfig();
    const baseURL = config.ha_base_url.replace(/\/$/, '');
    const viewPath = entry.view_path || '';
    const width = entry.width || 0;
    const height = entry.height || 0;

    const url = `${baseURL}${viewPath}?kiosk=true`;

    let ha_tokens = null;
    if (config.ha_username && config.ha_password) {
      try {
        ha_tokens = await getHaTokens(config.ha_username, config.ha_password);
        console.log(`[API] HA tokens 获取成功: ${clientIP}`);
      } catch (e) {
        console.log(`[API] HA tokens 获取失败: ${e.message}`);
      }
    }

    await recordConnection(clientIP);

    console.log(`[API] 下发配置: ${clientIP} -> ${viewPath} (${width}x${height})`);

    res.json({
      url,
      width,
      height,
      ha_tokens: ha_tokens ? {
        access_token: ha_tokens.access_token,
        refresh_token: ha_tokens.refresh_token
      } : null
    });
  } catch (err) {
    console.error(`[API] 内部错误:`, err.message);
    res.status(500).json({ error: 'internal' });
  }
});

// 公共设备列表接口（供HA集成config_flow使用，无需ingress header）
router.get('/devices', (req, res) => {
  const whitelist = getWhitelist();
  const devices = whitelist
    .filter(item => item.ip)
    .map(item => ({
      ip: item.ip,
      mac: item.mac || '',
      name: item.name || item.ip,
      category: item.category || ''
    }));
  res.json(devices);
});

module.exports = router;
