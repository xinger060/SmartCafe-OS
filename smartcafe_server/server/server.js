const express = require('express');
const path = require('path');
const fs = require('fs');
const { initStorage, readPortSync } = require('./storage');
const { scheduleRefresh } = require('./ha_auth');
const { startHeartbeat } = require('./heartbeat');
const apiRoutes = require('./api');
const adminRoutes = require('./admin');

const app = express();
const PORT = readPortSync();

app.use((req, res, next) => {
  req.url = req.url.replace(/\/+/g, '/');
  next();
});

app.use(express.json());

// API routes - accessible externally for terminal devices
app.use('/api', apiRoutes);

// Admin routes - only accessible via HA ingress
app.use('/admin', (req, res, next) => {
  if (!req.headers['x-ingress-path']) {
    return res.status(404).send('页面不存在');
  }
  next();
}, adminRoutes);

app.use('/static', (req, res, next) => {
  if (!req.headers['x-ingress-path']) {
    return res.status(404).send('页面不存在');
  }
  next();
}, express.static(path.join(__dirname, 'public')));

app.get('/', (req, res) => {
  if (!req.headers['x-ingress-path']) {
    return res.status(404).send('页面不存在');
  }
  const ingressPath = req.headers['x-ingress-path'] || '';
  let html = fs.readFileSync(path.join(__dirname, 'public', 'index.html'), 'utf-8');
  html = html.replace('__INGRESS_PATH__', ingressPath);
  res.type('html').send(html);
});

async function start() {
  try {
    await initStorage();
    scheduleRefresh();
    startHeartbeat(30000);
    app.listen(PORT, '0.0.0.0', () => {
      console.log(`[Server] HaAssistant 服务端已启动`);
      console.log(`[Server] 监听端口: ${PORT}`);
    });
  } catch (err) {
    console.error('[Server] 启动失败:', err.message);
    process.exit(1);
  }
}

start();
