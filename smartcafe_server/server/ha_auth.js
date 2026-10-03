const http = require('http');
const { getConfig } = require('./storage');

const tokenCache = {};
let refreshTimer = null;

function parseBody(res) {
  return new Promise((resolve, reject) => {
    let body = '';
    res.on('data', chunk => body += chunk);
    res.on('end', () => {
      try { resolve(JSON.parse(body)); }
      catch { resolve(body); }
    });
    res.on('error', reject);
  });
}

function httpPost(urlStr, data, contentType = 'application/json') {
  return new Promise((resolve, reject) => {
    const url = new URL(urlStr);
    const postData = contentType === 'application/json' ? JSON.stringify(data) : data;
    const options = {
      hostname: url.hostname,
      port: url.port || 80,
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': contentType,
        'Content-Length': Buffer.byteLength(postData)
      }
    };
    const req = http.request(options, (res) => {
      parseBody(res).then(body => resolve({ status: res.statusCode, data: body }));
    });
    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

async function getHaTokens(username, password) {
  const config = getConfig();
  const haBase = config.ha_base_url.replace(/\/$/, '');
  const cacheKey = username;

  // Check cache
  if (tokenCache[cacheKey] && tokenCache[cacheKey].expires_at > Date.now()) {
    return tokenCache[cacheKey];
  }

  // Refresh if we have a refresh_token
  if (tokenCache[cacheKey] && tokenCache[cacheKey].refresh_token) {
    try {
      const refreshRes = await httpPost(
        `${haBase}/auth/token`,
        `grant_type=refresh_token&refresh_token=${tokenCache[cacheKey].refresh_token}&client_id=${haBase}`,
        'application/x-www-form-urlencoded'
      );
      if (refreshRes.status === 200 && refreshRes.data.access_token) {
        const tokens = refreshRes.data;
        tokenCache[cacheKey] = {
          access_token: tokens.access_token,
          refresh_token: tokens.refresh_token || tokenCache[cacheKey].refresh_token,
          expires_at: Date.now() + (tokens.expires_in - 60) * 1000
        };
        return tokenCache[cacheKey];
      }
    } catch (e) {
      // Refresh failed, get new tokens
    }
  }

  // Get new tokens via login flow
  const flowRes = await httpPost(`${haBase}/auth/login_flow`, {
    client_id: haBase,
    handler: ['homeassistant', null],
    redirect_uri: haBase
  });

  if (flowRes.status !== 200 || !flowRes.data.flow_id) {
    throw new Error('Failed to start login flow');
  }

  const codeRes = await httpPost(`${haBase}/auth/login_flow/${flowRes.data.flow_id}`, {
    username,
    password,
    client_id: haBase
  });

  if (codeRes.status !== 200 || !codeRes.data.result) {
    throw new Error('Login failed: invalid credentials');
  }

  const tokenRes = await httpPost(
    `${haBase}/auth/token`,
    `grant_type=authorization_code&code=${codeRes.data.result}&client_id=${haBase}`,
    'application/x-www-form-urlencoded'
  );

  if (tokenRes.status !== 200 || !tokenRes.data.access_token) {
    throw new Error('Failed to get tokens');
  }

  const tokens = tokenRes.data;
  tokenCache[cacheKey] = {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
    expires_at: Date.now() + (tokens.expires_in - 60) * 1000
  };

  return tokenCache[cacheKey];
}

async function forceRefreshTokens() {
  const config = getConfig();
  if (!config.ha_username || !config.ha_password) {
    console.log('[TokenRefresh] 未配置 HA 凭据，跳过刷新');
    return;
  }
  try {
    // Clear cache to force new login
    delete tokenCache[config.ha_username];
    await getHaTokens(config.ha_username, config.ha_password);
    console.log('[TokenRefresh] 定时刷新成功');
  } catch (e) {
    console.error('[TokenRefresh] 定时刷新失败:', e.message);
  }
}

function scheduleRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }

  const config = getConfig();
  const time = (config.token_refresh_time || '').trim();

  if (!time || !/^\d{1,2}:\d{2}$/.test(time)) {
    console.log('[TokenRefresh] 定时刷新未启用');
    return;
  }

  const [hour, minute] = time.split(':').map(Number);
  console.log(`[TokenRefresh] 定时刷新已启用，每日 ${String(hour).padStart(2,'0')}:${String(minute).padStart(2,'0')} 执行`);

  refreshTimer = setInterval(() => {
    const now = new Date();
    if (now.getHours() === hour && now.getMinutes() === minute) {
      forceRefreshTokens();
    }
  }, 60 * 1000);
}

module.exports = { getHaTokens, scheduleRefresh, forceRefreshTokens };
