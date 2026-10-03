/**
 * PC Manager API Client
 * 用于与Home Assistant中的pc_manager集成通信
 */

const http = require('http');
const https = require('https');

class PCManagerClient {
  constructor(haBaseUrl) {
    this.haBaseUrl = haBaseUrl;
    this.apiUrl = '/api/pc_manager';
  }

  /**
   * 发送HTTP请求到HA
   */
  async _request(method, path, data = null) {
    return new Promise((resolve, reject) => {
      const url = new URL(path, this.haBaseUrl);
      const isHttps = url.protocol === 'https:';
      const client = isHttps ? https : http;

      const options = {
        hostname: url.hostname,
        port: url.port || (isHttps ? 443 : 80),
        path: url.pathname + url.search,
        method: method,
        headers: {
          'Content-Type': 'application/json',
        },
      };

      // 如果有长期访问令牌，添加到请求头
      if (this.longLivedToken) {
        options.headers['Authorization'] = `Bearer ${this.longLivedToken}`;
      }

      const req = client.request(options, (res) => {
        let body = '';
        res.on('data', (chunk) => {
          body += chunk;
        });
        res.on('end', () => {
          try {
            const json = JSON.parse(body);
            if (res.statusCode >= 200 && res.statusCode < 300) {
              resolve(json);
            } else {
              reject(new Error(`HTTP ${res.statusCode}: ${json.error || body}`));
            }
          } catch (e) {
            reject(new Error(`Invalid JSON response: ${body}`));
          }
        });
      });

      req.on('error', (error) => {
        reject(error);
      });

      if (data) {
        req.write(JSON.stringify(data));
      }

      req.end();
    });
  }

  /**
   * 设置长期访问令牌
   */
  setLongLivedToken(token) {
    this.longLivedToken = token;
  }

  /**
   * 获取所有设备
   */
  async getDevices() {
    return this._request('GET', `${this.apiUrl}/devices`);
  }

  /**
   * 获取单个设备
   */
  async getDevice(deviceId) {
    return this._request('GET', `${this.apiUrl}/devices/${deviceId}`);
  }

  /**
   * 唤醒设备（WOL）
   */
  async wakeDevice(ip) {
    return this._request('POST', `${this.apiUrl}/devices/${ip}/wake`);
  }

  /**
   * 获取所有设备状态
   */
  async getStatus() {
    return this._request('GET', `${this.apiUrl}/status`);
  }
}

module.exports = PCManagerClient;
