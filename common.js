/* 行程小程序 - 共用工具 (支持无服务器模式) */
(function (root) {
  const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];
  const GH_OWNER = 'adillojesus310-create';
  const GH_REPO = 'xingcheng';
  const GH_BRANCH = 'master';
  const GH_RAW = 'https://raw.githubusercontent.com/' + GH_OWNER + '/' + GH_REPO + '/' + GH_BRANCH + '/data.json';
  const GH_API = 'https://api.github.com/repos/' + GH_OWNER + '/' + GH_REPO + '/contents/data.json';

  function pad(n) { return String(n).padStart(2, '0'); }

  function formatTime(d) {
    return pad(d.getHours()) + ':' + pad(d.getMinutes());
  }

  function todayStr() {
    const d = new Date();
    return d.getFullYear() + '年' + (d.getMonth() + 1) + '月' + d.getDate() + '日 星期' + WEEKDAYS[d.getDay()];
  }

  const LUNAR_DAYS = ['','初一','初二','初三','初四','初五','初六','初七','初八','初九','初十',
    '十一','十二','十三','十四','十五','十六','十七','十八','十九','二十',
    '廿一','廿二','廿三','廿四','廿五','廿六','廿七','廿八','廿九','三十'];

  function lunarStr() {
    try {
      const fmt = new Intl.DateTimeFormat('zh-CN-u-ca-chinese', { month: 'long', day: 'numeric' });
      const raw = fmt.format(new Date());
      const m = raw.match(/^(.+?月)\s*(\d+)/);
      if (m) {
        const day = parseInt(m[2]);
        return '农历' + m[1] + (LUNAR_DAYS[day] || day);
      }
      return '农历' + raw.replace(/日$/, '');
    } catch (e) { return ''; }
  }

  function parseScheduleText(text) {
    const lines = text.split('\n');
    const items = [];
    let note = '', inNote = false;
    for (const line of lines) {
      const t = line.trim();
      if (!t) continue;
      if (t === '===') { inNote = true; continue; }
      if (inNote) { note = note ? note + '\n' + t : t; continue; }
      const m = t.match(/^(\d{1,2}:\d{2})(?:\s*[-~]\s*\d{1,2}:\d{2})?\s+(.+)/);
      if (m) {
        const rest = m[2];
        const atIdx = rest.indexOf(' @');
        const title = atIdx >= 0 ? rest.slice(0, atIdx).trim() : rest.trim();
        const desc = atIdx >= 0 ? '@' + rest.slice(atIdx + 2).trim() : '';
        items.push({ time: m[1], title, desc, done: false });
        continue;
      }
      const hm = t.match(/预计到家\s*(\d{1,2}:\d{2})/);
      if (hm) items.push({ time: hm[1], title: '预计到家', desc: '', done: false });
    }
    items.sort((a, b) => a.time.localeCompare(b.time));
    return { items, note };
  }

  function stringifySchedule(data) {
    if (!data || !data.items) return '';
    const lines = data.items.map(i => i.time + ' ' + i.title + (i.desc ? ' ' + i.desc : ''));
    if (data.note) { lines.push('', '==='); lines.push(data.note); }
    return lines.join('\n');
  }

  function itemStatus(item, now) {
    if (item.done) return 'done';
    const [h, m] = item.time.split(':').map(Number);
    const im = h * 60 + m;
    const cur = now.getHours() * 60 + now.getMinutes();
    if (im + 60 < cur) return 'done';
    if (Math.abs(im - cur) <= 30) return 'current';
    return '';
  }

  function renderTimeline(container, items, opts) {
    opts = opts || {};
    if (!items || items.length === 0) {
      container.innerHTML = '<div class="empty-state"><div class="emoji">📅</div><div class="text">' + (opts.emptyText || '今天暂无安排') + '</div></div>';
      return;
    }
    const now = new Date();
    const html = items.map((item, i) => {
      const status = itemStatus(item, now);
      const dot = 'timeline-dot' + (status ? ' ' + status : '');
      const del = opts.deletable ? '<div class="timeline-del" data-idx="' + i + '">✕</div>' : '';
      const desc = item.desc ? '<div class="timeline-desc">' + escapeHtml(item.desc) + '</div>' : '';
      return '<div class="timeline-item"><div class="' + dot + '"></div>'
        + '<div class="timeline-content">'
        + '<div class="timeline-time">' + escapeHtml(item.time) + '</div>'
        + '<div class="timeline-title">' + escapeHtml(item.title) + '</div>'
        + desc
        + '</div>' + del + '</div>';
    }).join('');
    container.innerHTML = html;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  // ===== 数据同步 (支持本地服务器 / GitHub Pages 双模式) =====
  let _etag = null;
  let _mode = 'auto'; // 'server' | 'github' | 'auto'

  // 获取 GitHub Token (admin页面会加载 config.js)
  function getToken() {
    return (typeof GITHUB_TOKEN_FROM_CONFIG !== 'undefined') ? GITHUB_TOKEN_FROM_CONFIG : '';
  }

  // 检测是否有本地服务器
  async function checkServer() {
    if (_mode !== 'auto') return _mode === 'server';
    try {
      const r = await fetch('/data', { method: 'GET', cache: 'no-store', signal: AbortSignal.timeout(2000) });
      _mode = r.ok ? 'server' : 'github';
    } catch (e) {
      _mode = 'github';
    }
    return _mode === 'server';
  }

  async function fetchData() {
    // 优先本地服务器
    if (await checkServer()) {
      try {
        const headers = {};
        if (_etag) headers['If-None-Match'] = _etag;
        const resp = await fetch('/data', { headers, cache: 'no-store' });
        if (resp.status === 304) return { unchanged: true };
        if (resp.ok) {
          const tag = resp.headers.get('ETag');
          if (tag) _etag = tag;
          return { unchanged: false, data: await resp.json() };
        }
      } catch (e) { /* fall through */ }
    }

    // GitHub Raw 模式
    try {
      const url = GH_RAW + '?t=' + Date.now();
      const resp = await fetch(url, { cache: 'no-store' });
      if (resp.ok) {
        return { unchanged: false, data: await resp.json() };
      }
    } catch (e) { /* ignore */ }
    return null;
  }

  async function postData(data) {
    // 优先本地服务器
    if (await checkServer()) {
      try {
        const resp = await fetch('/data', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
        return resp.ok;
      } catch (e) { /* fall through */ }
    }

    // GitHub API 模式 (需要 token)
    const token = getToken();
    if (!token) {
      console.warn('未配置 GitHub Token，无法保存');
      return false;
    }

    try {
      const bodyStr = JSON.stringify(data, null, 2);

      // 先获取当前 SHA
      let sha = '';
      try {
        const r = await fetch(GH_API + '?ref=' + GH_BRANCH, {
          headers: { 'Authorization': 'token ' + token, 'User-Agent': 'xingcheng' }
        });
        if (r.ok) {
          const info = await r.json();
          sha = info.sha || '';
        }
      } catch (e) { /* 文件可能不存在 */ }

      // base64 编码
      const b64 = btoa(unescape(encodeURIComponent(bodyStr)));

      const body = {
        message: 'update via admin',
        content: b64,
        branch: GH_BRANCH
      };
      if (sha) body.sha = sha;

      const resp = await fetch(GH_API, {
        method: 'PUT',
        headers: {
          'Authorization': 'token ' + token,
          'Content-Type': 'application/json',
          'User-Agent': 'xingcheng'
        },
        body: JSON.stringify(body)
      });
      return resp.ok;
    } catch (e) {
      console.error('GitHub 保存失败:', e);
      return false;
    }
  }

  // 地图
  function osmEmbedUrl(loc) {
    const d = 0.008;
    return 'https://www.openstreetmap.org/export/embed.html?bbox='
      + (loc.lng - d) + ',' + (loc.lat - d) + ',' + (loc.lng + d) + ',' + (loc.lat + d)
      + '&layer=mapnik&marker=' + loc.lat + ',' + loc.lng;
  }

  function amapUrl(loc, name) {
    return 'https://uri.amap.com/marker?position=' + loc.lng + ',' + loc.lat
      + '&name=' + encodeURIComponent(name || '位置') + '&callnative=1';
  }

  root.HermesUtil = {
    pad, formatTime, todayStr, lunarStr,
    parseScheduleText, stringifySchedule,
    itemStatus, renderTimeline, escapeHtml,
    fetchData, postData,
    osmEmbedUrl, amapUrl
  };
})(window);
