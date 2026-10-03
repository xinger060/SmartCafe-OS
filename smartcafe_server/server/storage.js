const fs = require('fs').promises;
const fsSync = require('fs');
const path = require('path');
const crypto = require('crypto');

// Support both standalone and HA add-on modes
const isAddon = process.env.HA_ADDON === 'true' || fsSync.existsSync('/data/smartcafe-server');
const DATA_DIR = isAddon ? '/data/smartcafe-server' : path.join(__dirname, 'data');
const CONFIG_FILE = path.join(DATA_DIR, 'config.json');
const WHITELIST_FILE = path.join(DATA_DIR, 'whitelist.json');
const AUDIT_FILE = path.join(DATA_DIR, 'audit.json');
const CATEGORIES_FILE = path.join(DATA_DIR, 'categories.json');

let config = { port: 8080, ha_base_url: 'http://192.168.1.100:8123', username: 'admin', password_hash: '', password_salt: '' };
let whitelist = [];
let audit = [];
let categories = [];

async function ensureDir(dir) {
  try {
    await fs.access(dir);
  } catch {
    await fs.mkdir(dir, { recursive: true });
  }
}

async function readJSON(filePath, defaultValue) {
  try {
    const data = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(data);
  } catch {
    return defaultValue;
  }
}

async function writeJSON(filePath, data) {
  await fs.writeFile(filePath, JSON.stringify(data, null, 2), 'utf-8');
}

function hashPassword(password, salt) {
  return crypto.pbkdf2Sync(password, salt, 10000, 64, 'sha512').toString('hex');
}

function verifyPassword(password) {
  if (!config.password_hash || !config.password_salt) return false;
  const hash = hashPassword(password, config.password_salt);
  return hash === config.password_hash;
}

async function changePassword(newPassword) {
  const salt = crypto.randomBytes(16).toString('hex');
  config.password_salt = salt;
  config.password_hash = hashPassword(newPassword, salt);
  await saveConfig();
}

function getUsername() {
  return config.username || 'admin';
}

function readPortSync() {
  try {
    const data = require('fs').readFileSync(CONFIG_FILE, 'utf-8');
    const parsed = JSON.parse(data);
    return parsed.port || 8080;
  } catch {
    return 8080;
  }
}

async function initStorage() {
  await ensureDir(DATA_DIR);
  config = await readJSON(CONFIG_FILE, config);
  whitelist = await readJSON(WHITELIST_FILE, whitelist);
  audit = await readJSON(AUDIT_FILE, audit);
  categories = await readJSON(CATEGORIES_FILE, categories);
  if (!config.password_hash) {
    await changePassword('admin');
    console.log(`[Storage] 默认账号: admin / admin (请立即修改密码)`);
  }
  if (!config.port) {
    config.port = 8080;
  }
  await saveConfig();
  await saveWhitelist();
  await saveAudit();
  await saveCategories();
  console.log(`[Storage] 数据目录: ${DATA_DIR}`);
  console.log(`[Storage] 白名单记录: ${whitelist.length} 条`);
}

async function saveConfig() {
  await writeJSON(CONFIG_FILE, config);
}

async function saveWhitelist() {
  await writeJSON(WHITELIST_FILE, whitelist);
}

async function saveAudit() {
  await writeJSON(AUDIT_FILE, audit);
}

async function saveCategories() {
  await writeJSON(CATEGORIES_FILE, categories);
}

function getConfig() {
  return config;
}

async function updateConfig(newConfig) {
  let needRestart = false;
  if (newConfig.ha_base_url !== undefined) {
    config.ha_base_url = newConfig.ha_base_url;
  }
  if (newConfig.ha_username !== undefined) {
    config.ha_username = newConfig.ha_username;
  }
  if (newConfig.ha_password !== undefined) {
    config.ha_password = newConfig.ha_password;
  }
  if (newConfig.token_refresh_time !== undefined) {
    config.token_refresh_time = newConfig.token_refresh_time;
  }
  if (newConfig.ha_long_lived_token !== undefined) {
    config.ha_long_lived_token = newConfig.ha_long_lived_token;
  }
  if (newConfig.port !== undefined && newConfig.port !== config.port) {
    config.port = newConfig.port;
    needRestart = true;
  }
  await saveConfig();
  return { config, needRestart };
}

function getWhitelist() {
  return whitelist;
}

function findByIP(ip) {
  return whitelist.find(item => item.ip === ip);
}

async function addWhitelistItem(item) {
  const existing = findByIP(item.ip);
  if (existing) {
    Object.assign(existing, item);
  } else {
    whitelist.push(item);
  }
  await saveWhitelist();
  return item;
}

async function updateWhitelistItem(ip, updates) {
  const index = whitelist.findIndex(item => item.ip === ip);
  if (index === -1) return null;
  Object.assign(whitelist[index], updates);
  await saveWhitelist();
  return whitelist[index];
}

async function deleteWhitelistItem(ip) {
  const index = whitelist.findIndex(item => item.ip === ip);
  if (index === -1) return false;
  whitelist.splice(index, 1);
  await saveWhitelist();
  return true;
}

async function batchImport(items) {
  let imported = 0;
  let updated = 0;
  for (const item of items) {
    const existing = findByIP(item.ip);
    if (existing) {
      Object.assign(existing, item);
      updated++;
    } else {
      whitelist.push(item);
      imported++;
    }
  }
  await saveWhitelist();
  return { imported, updated };
}

function getAuditLog() {
  return audit;
}

async function addAuditEntry(entry) {
  audit.push({
    timestamp: new Date().toISOString(),
    ...entry
  });
  await saveAudit();
}

function getConnectionStats() {
  const stats = {};
  for (const item of whitelist) {
    stats[item.ip] = {
      lastPull: item.lastPull || null,
      pullCount: item.pullCount || 0
    };
  }
  return stats;
}

async function recordConnection(ip) {
  const item = findByIP(ip);
  if (item) {
    item.lastPull = new Date().toISOString();
    item.pullCount = (item.pullCount || 0) + 1;
    await saveWhitelist();
  }
}

function getCategories() {
  return categories;
}

async function addCategory(name) {
  if (!name || categories.includes(name)) return false;
  categories.push(name);
  await saveCategories();
  return true;
}

async function renameCategory(oldName, newName) {
  if (!oldName || !newName || oldName === newName) return false;
  const idx = categories.indexOf(oldName);
  if (idx === -1) return false;
  if (categories.includes(newName)) return false;
  categories[idx] = newName;
  for (const item of whitelist) {
    if (item.category === oldName) item.category = newName;
  }
  await saveCategories();
  await saveWhitelist();
  return true;
}

async function deleteCategory(name) {
  const idx = categories.indexOf(name);
  if (idx === -1) return false;
  categories.splice(idx, 1);
  for (const item of whitelist) {
    if (item.category === name) item.category = '';
  }
  await saveCategories();
  await saveWhitelist();
  return true;
}

async function reorderCategories(order) {
  categories = order.filter(c => categories.includes(c));
  await saveCategories();
}

module.exports = {
  initStorage,
  readPortSync,
  getConfig,
  updateConfig,
  getWhitelist,
  findByIP,
  addWhitelistItem,
  updateWhitelistItem,
  deleteWhitelistItem,
  batchImport,
  getAuditLog,
  addAuditEntry,
  getConnectionStats,
  recordConnection,
  verifyPassword,
  changePassword,
  getUsername,
  getCategories,
  addCategory,
  renameCategory,
  deleteCategory,
  reorderCategories
};
