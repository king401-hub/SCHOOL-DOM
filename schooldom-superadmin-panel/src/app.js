// Single-page app logic - no framework/build step, just DOM + fetch via API
// (api.js) and a shared inline-SVG icon set (icons.js). Views are plain
// <div id="view-...">, toggled by data-view nav clicks; each view's data is
// (re)loaded when it becomes active.

let currentDevices = [];
let selectedDeviceId = null;
let schoolsCache = [];

function $(sel) { return document.querySelector(sel); }
function $all(sel) { return Array.from(document.querySelectorAll(sel)); }

function showToast(message, isError) {
  const el = $('#toast');
  el.textContent = message;
  el.style.background = isError ? 'var(--coral)' : 'var(--navy)';
  el.style.display = 'block';
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => { el.style.display = 'none'; }, 3500);
}

function timeAgo(iso) {
  if (!iso) return 'Never';
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins} min${mins === 1 ? '' : 's'} ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hr${hrs === 1 ? '' : 's'} ago`;
  const days = Math.floor(hrs / 24);
  return `${days} day${days === 1 ? '' : 's'} ago`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ---------------------------------------------------------------- Static icon injection
// Everything that's part of the static page shell (sidebar nav, sign-out
// button, modal close buttons, search fields) gets its icon filled in once
// at load, from the shared ICONS set - keeps every icon in the app visually
// consistent instead of mixing in emoji glyphs.

const NAV_ICON_MAP = {
  dashboard: 'dashboard', devices: 'devices', schools: 'school', students: 'students',
  cards: 'card', attendance: 'attendance', alerts: 'bell', reports: 'reports',
  settings: 'settings', users: 'user', audit: 'audit',
};

function injectStaticIcons() {
  $all('.nav-item').forEach(item => {
    const icon = NAV_ICON_MAP[item.dataset.view];
    const slot = item.querySelector('.nav-icon');
    if (icon && slot) slot.innerHTML = ICONS[icon];
  });
  $('#sign-out-btn').innerHTML = ICONS.logout + '<span>Sign Out</span>';
  $('#dash-view-all-devices').innerHTML = 'View all devices' + ICONS.chevronRight;
  renderThemeToggleIcon();
  $('#topbar-bell').innerHTML = (ICONS.bell || '') + '<span class="dot" id="topbar-bell-dot" style="display:none;"></span>';
  $('#key-modal-close').innerHTML = ICONS.x;
  $('#signout-modal-close').innerHTML = ICONS.x;
  $('#reassign-modal-close').innerHTML = ICONS.x;
  $('#signout-modal-icon').innerHTML = ICONS.logout;
  const searchIcons = ['device-search-icon', 'audit-search-icon', 'cards-search-icon', 'schools-search-icon'];
  searchIcons.forEach(id => { const el = $('#' + id); if (el) el.outerHTML = ICONS.search; });
}

// ---------------------------------------------------------------- Theme

const THEME_KEY = 'schooldom_superadmin_theme';

function renderThemeToggleIcon() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  // Icon + label describe the mode a click switches TO, not the current mode.
  $('#theme-toggle-btn').innerHTML = (isDark ? ICONS.sun : ICONS.moon) + `<span>${isDark ? 'Light Mode' : 'Dark Mode'}</span>`;
}

$('#theme-toggle-btn').addEventListener('click', () => {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  if (isDark) {
    document.documentElement.removeAttribute('data-theme');
    localStorage.removeItem(THEME_KEY);
  } else {
    document.documentElement.setAttribute('data-theme', 'dark');
    localStorage.setItem(THEME_KEY, 'dark');
  }
  renderThemeToggleIcon();
});

// ---------------------------------------------------------------- Auth

function boot() {
  injectStaticIcons();
  const session = API.currentSession();
  if (session && session.access) {
    enterApp(session);
  } else {
    $('#login-screen').style.display = 'flex';
    $('#app-shell').classList.remove('active');
  }
}

function enterApp(session) {
  $('#login-screen').style.display = 'none';
  $('#app-shell').classList.add('active');
  $('#user-name').textContent = session.userName || 'Superadmin';
  $('#user-email').textContent = session.userEmail || '';
  const initials = (session.userName || 'SA').split(' ').map(p => p[0]).slice(0, 2).join('').toUpperCase() || 'SA';
  $('#user-avatar').textContent = initials;
  $('#topbar-avatar').textContent = initials;
  loadDashboard();
}

let _pendingOtp = null; // { email, challenge } while the OTP card is showing

// Decorative particles drifting up through the login background - purely
// visual, generated once at load since hand-writing dozens of divs isn't
// practical. Positions/timings are randomized so each launch looks alive.
function generateLoginParticles() {
  const container = $('#login-particles');
  if (!container) return;
  for (let i = 0; i < 26; i++) {
    const el = document.createElement('div');
    el.className = 'login-particle';
    const size = (2 + Math.random() * 3).toFixed(1);
    const left = (Math.random() * 100).toFixed(1);
    const top = (Math.random() * 100).toFixed(1);
    const duration = (6 + Math.random() * 9).toFixed(1);
    const delay = (Math.random() * duration).toFixed(1);
    const opacity = (0.25 + Math.random() * 0.45).toFixed(2);
    const hue = Math.random() > 0.5 ? 'var(--login-green)' : 'var(--login-blue)';
    el.style.cssText = `width:${size}px;height:${size}px;left:${left}%;top:${top}%;` +
      `animation-duration:${duration}s;animation-delay:-${delay}s;--op:${opacity};` +
      `color:${hue};background:${hue};`;
    container.appendChild(el);
  }
}
generateLoginParticles();

const REMEMBER_EMAIL_KEY = 'schooldom_superadmin_remember_email';
const rememberedEmail = localStorage.getItem(REMEMBER_EMAIL_KEY);
if (rememberedEmail) {
  $('#login-email').value = rememberedEmail;
  $('#login-remember').checked = true;
}

$('#login-password-toggle').addEventListener('click', () => {
  const input = $('#login-password');
  input.type = input.type === 'password' ? 'text' : 'password';
});

$('#login-forgot').addEventListener('click', () => {
  showToast('Contact your SchoolDom administrator to reset your password.');
});

$('#login-submit').addEventListener('click', async () => {
  const email = $('#login-email').value.trim();
  const password = $('#login-password').value;
  const errorBox = $('#login-error');
  errorBox.style.display = 'none';
  if (!email || !password) {
    errorBox.textContent = 'Enter your email and password.';
    errorBox.style.display = 'block';
    return;
  }
  if ($('#login-remember').checked) localStorage.setItem(REMEMBER_EMAIL_KEY, email);
  else localStorage.removeItem(REMEMBER_EMAIL_KEY);
  const btn = $('#login-submit');
  btn.disabled = true;
  $('#login-submit-label').textContent = 'Signing in...';
  try {
    const result = await API.login(email, password);

    if (result.status === 'otp_required') {
      if (result.userRole && result.userRole !== 'super_admin') {
        throw new Error('This account is not a SchoolDom super administrator.');
      }
      _pendingOtp = { email, challenge: result.challenge };
      $('#login-card-main').style.display = 'none';
      $('#otp-card').style.display = 'block';
      $('#otp-code').value = '';
      $('#otp-error').style.display = 'none';
      $('#otp-code').focus();
      return;
    }

    const session = result.session;
    if (session.userRole && session.userRole !== 'super_admin') {
      API.signOut();
      throw new Error('This account is not a SchoolDom super administrator.');
    }
    enterApp(session);
  } catch (err) {
    errorBox.textContent = err.message === 'AUTH_EXPIRED' ? 'Sign-in failed.' : err.message;
    errorBox.style.display = 'block';
  } finally {
    btn.disabled = false;
    $('#login-submit-label').textContent = 'Sign In';
  }
});

$('#login-password').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') $('#login-submit').click();
});

$('#otp-submit').addEventListener('click', async () => {
  const code = $('#otp-code').value.trim();
  const errorBox = $('#otp-error');
  errorBox.style.display = 'none';
  if (!/^\d{6}$/.test(code)) {
    errorBox.textContent = 'Enter the 6-digit code.';
    errorBox.style.display = 'block';
    return;
  }
  const btn = $('#otp-submit');
  btn.disabled = true;
  $('#otp-submit-label').textContent = 'Verifying...';
  try {
    const session = await API.verifyOtp(_pendingOtp.email, code, _pendingOtp.challenge);
    if (session.userRole && session.userRole !== 'super_admin') {
      API.signOut();
      throw new Error('This account is not a SchoolDom super administrator.');
    }
    enterApp(session);
  } catch (err) {
    errorBox.textContent = err.message;
    errorBox.style.display = 'block';
  } finally {
    btn.disabled = false;
    $('#otp-submit-label').textContent = 'Verify';
  }
});

$('#otp-code').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') $('#otp-submit').click();
});

$('#otp-resend').addEventListener('click', async () => {
  const btn = $('#otp-resend');
  btn.disabled = true;
  try {
    const data = await API.resendOtp(_pendingOtp.email, _pendingOtp.challenge);
    if (data && data.otp_challenge) _pendingOtp.challenge = data.otp_challenge;
    showToast('A new code has been sent.');
  } catch (err) {
    $('#otp-error').textContent = err.message;
    $('#otp-error').style.display = 'block';
  } finally {
    btn.disabled = false;
  }
});

// Sign-out now goes through a confirmation modal (spec: no accidental
// sign-outs) instead of acting immediately on click.
$('#sign-out-btn').addEventListener('click', () => $('#signout-modal').classList.add('active'));
$('#signout-modal-close').addEventListener('click', () => $('#signout-modal').classList.remove('active'));
$('#signout-modal-cancel').addEventListener('click', () => $('#signout-modal').classList.remove('active'));
$('#signout-modal-confirm').addEventListener('click', () => {
  API.signOut();
  location.reload();
});

function handleApiError(err) {
  if (err.message === 'AUTH_EXPIRED') {
    showToast('Your sign-in has expired. Please sign in again.', true);
    setTimeout(() => location.reload(), 1200);
    return;
  }
  showToast(err.message, true);
}

// ---------------------------------------------------------------- Nav

$all('.nav-item').forEach(item => {
  item.addEventListener('click', () => switchView(item.dataset.view));
});
$all('[data-view-link]').forEach(link => {
  link.addEventListener('click', () => switchView(link.dataset.viewLink));
});

const PLACEHOLDER_COPY = {
  students: ['students', 'Students', 'A cross-school student directory is next on the list.'],
  attendance: ['attendance', 'Attendance Logs', 'A merged attendance log across every device is next on the list.'],
  alerts: ['bell', 'Alerts', 'Alerts show live on the Dashboard for now - a dedicated history and resolution view is next.'],
  reports: ['reports', 'Reports', 'Usage, attendance, and device analytics reporting is next on the list.'],
  settings: ['settings', 'Settings', 'Global platform, security, and device-default settings are next on the list.'],
  users: ['user', 'Users', 'Superadmin account management is next on the list.'],
};

function switchView(name) {
  $all('.nav-item').forEach(i => i.classList.toggle('active', i.dataset.view === name));
  $all('.view').forEach(v => v.style.display = 'none');

  const view = $('#view-' + name);
  if (!view) return;
  view.style.display = 'block';

  if (view.classList.contains('placeholder-view') && !view.dataset.rendered) {
    const [icon, title, copy] = PLACEHOLDER_COPY[name] || ['settings', title, 'Coming soon.'];
    view.innerHTML = `
      <div class="placeholder">
        <div class="placeholder-icon">${ICONS[icon] || ICONS.settings}</div>
        <h3>${title}</h3>
        <p>${copy}</p>
        <div class="placeholder-badge">${ICONS.clock}In active development</div>
      </div>`;
    view.dataset.rendered = '1';
  }

  if (name === 'dashboard') loadDashboard();
  if (name === 'devices') loadDevicesView();
  if (name === 'audit') loadAuditView();
  if (name === 'cards') loadCardsView();
  if (name === 'schools') loadSchoolsView();
}

// ---------------------------------------------------------------- Dashboard

function skeletonRows(n, cols) {
  return Array.from({ length: n }).map(() => `
    <tr class="skel-row">${Array.from({ length: cols }).map(() => `<td><div class="skel skel-text" style="width:${40 + Math.random() * 40}%;"></div></td>`).join('')}</tr>
  `).join('');
}

async function loadDashboard() {
  $('#device-table-body').innerHTML = skeletonRows(5, 5);
  renderDeviceDetail(null);
  renderBatteryPanel(null);
  try {
    const [devicesRes, auditRes] = await Promise.all([
      API.get('/api/device-fleet/devices/'),
      API.get('/api/device-fleet/audit-logs/'),
    ]);
    currentDevices = devicesRes.data;
    renderStats(devicesRes.stats);
    renderDonut(devicesRes.stats);
    renderDeviceTable('#device-table-body', currentDevices.slice(0, 6), false);
    renderActivity(auditRes.data.slice(0, 6));
    renderAlerts(currentDevices);
    renderQuickActions();
    loadWizardSchools();
  } catch (err) {
    handleApiError(err);
  }
}

// Animates each stat number counting up from its previous value - runs once
// per render, driven by requestAnimationFrame rather than setInterval so it
// stays smooth and self-terminating.
function countUp(el, to) {
  const from = parseInt(el.textContent, 10) || 0;
  if (from === to) { el.textContent = to; return; }
  const duration = 600;
  const start = performance.now();
  function tick(now) {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = Math.round(from + (to - from) * eased);
    if (t < 1) requestAnimationFrame(tick);
    else el.textContent = to;
  }
  requestAnimationFrame(tick);
}

function renderStats(stats) {
  $('#stat-grid').querySelectorAll('.stat-icon')[0].innerHTML = ICONS.devices;
  $('#stat-grid').querySelectorAll('.stat-icon')[1].innerHTML = ICONS.wifi;
  $('#stat-grid').querySelectorAll('.stat-icon')[2].innerHTML = ICONS.wifiOff;
  $('#stat-grid').querySelectorAll('.stat-icon')[3].innerHTML = ICONS.school;
  $('#stat-grid').querySelectorAll('.stat-icon')[4].innerHTML = ICONS.alertTriangle;
  countUp($('#stat-total'), stats.total);
  countUp($('#stat-online'), stats.online);
  countUp($('#stat-offline'), stats.offline);
  countUp($('#stat-schools'), stats.total_schools);
  countUp($('#stat-attention'), stats.needs_attention);
  $('#stat-online-pct').textContent = stats.total ? `${Math.round(100 * stats.online / stats.total)}% of fleet` : '';
  $('#stat-offline-pct').textContent = stats.total ? `${Math.round(100 * stats.offline / stats.total)}% of fleet` : '';
  $('#topbar-bell-dot').style.display = stats.needs_attention > 0 ? 'block' : 'none';
}

// ---------------------------------------------------------------- Donut chart

function renderDonut(stats) {
  const suspended = currentDevices.filter(d => d.status === 'suspended').length;
  const unassigned = currentDevices.filter(d => !d.school_name).length;
  const online = stats.online;
  const offlineAssigned = Math.max(0, stats.offline - suspended - unassigned);
  const total = stats.total || 1;
  const segments = [
    { label: 'Online', value: online, color: 'var(--green)' },
    { label: 'Offline', value: offlineAssigned, color: 'var(--coral)' },
    { label: 'Suspended', value: suspended, color: 'var(--gold)' },
    { label: 'Unassigned', value: unassigned, color: 'var(--muted)' },
  ];
  const r = 52, circ = 2 * Math.PI * r;
  let offset = 0;
  const circles = segments.map(s => {
    const frac = s.value / total;
    const dash = frac * circ;
    const el = `<circle cx="60" cy="60" r="${r}" fill="none" stroke="${s.color}" stroke-width="14"
      stroke-dasharray="${dash} ${circ - dash}" stroke-dashoffset="${-offset}" stroke-linecap="round" />`;
    offset += dash;
    return el;
  }).join('');

  $('#donut-body').innerHTML = `
    <div class="donut-wrap">
      <svg class="donut-svg" width="120" height="120" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="${r}" fill="none" stroke="var(--light-button)" stroke-width="14" />
        ${circles}
        <g transform="rotate(90 60 60)">
          <text x="60" y="56" class="donut-center" font-size="22" font-weight="800" fill="var(--text)">${stats.total}</text>
          <text x="60" y="72" class="donut-center" font-size="10" font-weight="700" fill="var(--muted)">DEVICES</text>
        </g>
      </svg>
      <div class="donut-legend">
        ${segments.map(s => `
          <div class="donut-legend-item">
            <span class="donut-legend-left"><span class="donut-legend-dot" style="background:${s.color}"></span>${s.label}</span>
            <span class="donut-legend-value">${s.value}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function statusPill(device) {
  if (device.status === 'suspended') return `<span class="pill pill-gold"><span class="pill-dot" style="background:var(--gold)"></span>Suspended</span>`;
  if (device.status === 'revoked') return `<span class="pill pill-red"><span class="pill-dot" style="background:var(--coral)"></span>Revoked</span>`;
  if (!device.school_name) return `<span class="pill pill-muted"><span class="pill-dot" style="background:var(--muted)"></span>Unassigned</span>`;
  if (device.is_online) return `<span class="pill pill-green"><span class="pill-dot pulse" style="background:var(--green)"></span>Online</span>`;
  return `<span class="pill pill-red"><span class="pill-dot" style="background:var(--coral)"></span>Offline</span>`;
}

function batteryColor(pct) {
  if (pct === null || pct === undefined) return 'var(--muted)';
  if (pct <= 20) return 'var(--coral)';
  if (pct <= 50) return 'var(--gold)';
  return 'var(--green)';
}

function batteryHtml(device) {
  if (device.battery_percentage === null || device.battery_percentage === undefined) {
    return '<span style="color:var(--muted);font-size:12px;">Not reported</span>';
  }
  const color = batteryColor(device.battery_percentage);
  return `<span class="battery-bar" style="color:${color}">
    <span class="battery-shell"><span class="battery-fill" style="width:${Math.max(6, device.battery_percentage)}%;background:${color}"></span></span>
    ${device.battery_percentage}%${device.battery_charging ? `<span class="battery-bolt">${ICONS.bolt}</span>` : ''}
  </span>`;
}

function deviceRowIcon(d) {
  if (d.status === 'suspended' || d.status === 'revoked') return ICONS.alertTriangle;
  return ICONS.devices;
}

function renderDeviceTable(bodySelector, devices, full) {
  const body = $(bodySelector);
  if (!devices.length) {
    const cols = full ? 8 : 5;
    body.innerHTML = `<tr><td colspan="${cols}" style="padding:0;">
      <div class="empty-state">
        <div class="empty-state-icon">${ICONS.devices}</div>
        <div class="empty-state-title">No devices registered yet</div>
        <div class="empty-state-desc">Register your first SchoolDom scanner to begin monitoring devices.</div>
        <button class="btn-gradient" style="width:auto;padding:9px 16px;" id="empty-register-device">${ICONS.plusCircle}Register Device</button>
      </div>
    </td></tr>`;
    $('#empty-register-device')?.addEventListener('click', () => $('#qa-generate-key')?.click());
    return;
  }
  body.innerHTML = devices.map(d => `
    <tr class="device-row ${d.id === selectedDeviceId ? 'selected' : ''}" data-id="${d.id}">
      <td>
        <div class="cell-with-icon">
          <span class="table-row-icon">${deviceRowIcon(d)}</span>
          <div>
            <div class="dev-name">${d.device_id}</div>
            ${d.name ? `<div class="dev-name-sub">${escapeHtml(d.name)}</div>` : ''}
          </div>
        </div>
      </td>
      ${full ? `<td class="mono">${d.license_key || '&mdash;'}</td>` : ''}
      <td>${d.school_name || '<span style="color:var(--muted)">Unassigned</span>'}</td>
      <td>${statusPill(d)}</td>
      <td>${batteryHtml(d)}</td>
      ${full ? `<td>${healthPill(d.battery_health)}</td>` : ''}
      <td style="color:var(--muted);font-size:12px;">${timeAgo(d.last_seen_at)}</td>
      ${full ? `<td><span class="card-link" data-open-detail="${d.id}">Manage${ICONS.chevronRight}</span></td>` : ''}
    </tr>
  `).join('');

  $all(`${bodySelector} tr.device-row`).forEach(row => {
    row.addEventListener('click', () => selectDevice(row.dataset.id));
  });
  $all(`${bodySelector} [data-open-detail]`).forEach(link => {
    link.addEventListener('click', (e) => { e.stopPropagation(); switchView('dashboard'); selectDevice(link.dataset.openDetail); });
  });
}

function healthPill(health) {
  const labels = { good: 'Good', normal: 'Normal', fair: 'Fair', poor: 'Poor', unknown: 'Unknown', not_supported: 'Not Supported' };
  if (!health) return '<span style="color:var(--muted);font-size:12px;">Not reported</span>';
  const cls = health === 'good' ? 'pill-green' : health === 'poor' ? 'pill-red' : health === 'fair' ? 'pill-gold' : 'pill-muted';
  return `<span class="pill ${cls}">${labels[health] || health}</span>`;
}

function selectDevice(id) {
  selectedDeviceId = id;
  $all('.device-row').forEach(r => r.classList.toggle('selected', r.dataset.id === id));
  const device = currentDevices.find(d => d.id === id);
  if (!device) return;
  renderDeviceDetail(device);
  renderBatteryPanel(device);
}

function renderDeviceDetail(d) {
  if (!d) {
    $('#device-detail-body').innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">${ICONS.devices}</div>
        <div class="empty-state-title">Select a device</div>
        <div class="empty-state-desc">Choose a scanner from the device list to view battery, health, school assignment, and device controls.</div>
      </div>`;
    return;
  }
  $('#device-detail-body').innerHTML = `
    <div class="detail-row"><span class="detail-label">${ICONS.devices}Device</span><span class="detail-value">${d.device_id}</span></div>
    <div class="detail-row"><span class="detail-label">${ICONS.checkCircle}Status</span><span class="detail-value">${statusPill(d)}</span></div>
    <div class="detail-row"><span class="detail-label">${ICONS.school}School</span><span class="detail-value">${d.school_name || 'Unassigned'}</span></div>
    <div class="detail-row"><span class="detail-label">${ICONS.key}License Key</span><span class="detail-value mono">${d.license_key || '&mdash;'}</span></div>
    <div class="detail-row"><span class="detail-label">${ICONS.laptop}App Version</span><span class="detail-value">${d.app_version || 'Not supported'}</span></div>
    <div class="detail-row"><span class="detail-label">${ICONS.devices}Device Model</span><span class="detail-value">${d.device_model || 'Not supported'}</span></div>
    <div class="detail-row"><span class="detail-label">${ICONS.clock}Last Seen</span><span class="detail-value">${timeAgo(d.last_seen_at)}</span></div>
    <div class="detail-row"><span class="detail-label">${ICONS.refresh}Last Sync</span><span class="detail-value">${timeAgo(d.last_sync_at)}</span></div>
    <div class="detail-actions">
      <button class="btn btn-danger" data-action="revoke">Log Out Device</button>
      ${d.status === 'suspended'
        ? '<button class="btn btn-secondary" data-action="reactivate">Reactivate</button>'
        : '<button class="btn btn-secondary" data-action="suspend">Deactivate</button>'}
      <button class="btn btn-secondary" data-action="reassign">Reassign School</button>
    </div>
  `;
  $('[data-action="revoke"]').addEventListener('click', () => deviceAction(d.id, 'revoke', 'Log out this device? It will need to be re-authorized before scanning again.'));
  $('[data-action="suspend"]')?.addEventListener('click', () => deviceAction(d.id, 'suspend'));
  $('[data-action="reactivate"]')?.addEventListener('click', () => deviceAction(d.id, 'reactivate'));
  $('[data-action="reassign"]').addEventListener('click', () => openReassignPrompt(d));
}

function renderBatteryPanel(d) {
  if (!d) {
    $('#battery-panel-body').innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">${ICONS.battery}</div>
        <div class="empty-state-title">No device selected</div>
        <div class="empty-state-desc">Battery level, charging status, and health appear here once you pick a device.</div>
      </div>`;
    return;
  }
  const pct = d.battery_percentage;
  const color = batteryColor(pct);
  const deg = pct === null || pct === undefined ? 0 : Math.round(pct * 3.6);
  $('#battery-panel-body').innerHTML = `
    <div class="gauge-wrap">
      <div style="width:120px;height:120px;border-radius:50%;
        background:conic-gradient(${color} ${deg}deg, var(--light-button) ${deg}deg);
        display:flex;align-items:center;justify-content:center;">
        <div style="width:92px;height:92px;border-radius:50%;background:var(--surface);
          display:flex;align-items:center;justify-content:center;flex-direction:column;">
          <div class="gauge-value" style="margin-top:0;color:${color}">${pct !== null && pct !== undefined ? pct + '%' : '&mdash;'}</div>
        </div>
      </div>
      <div class="gauge-caption">Battery Level</div>
    </div>
    <div class="health-list">
      <div class="health-item"><span class="detail-label">Battery Health</span>${healthPill(d.battery_health)}</div>
      <div class="health-item"><span class="detail-label">Charging Status</span><span class="detail-value">${d.battery_charging === null ? 'Not supported' : (d.battery_charging ? 'Charging' : 'Not charging')}</span></div>
      <div class="health-item"><span class="detail-label">Temperature</span><span class="detail-value">${d.battery_temperature_c !== null && d.battery_temperature_c !== undefined ? d.battery_temperature_c + '&deg;C' : 'Not supported'}</span></div>
      <div class="health-item"><span class="detail-label">Last Update</span><span class="detail-value">${timeAgo(d.last_seen_at)}</span></div>
    </div>
  `;
}

async function deviceAction(id, action, confirmMsg) {
  if (confirmMsg && !confirm(confirmMsg)) return;
  try {
    const res = await API.post(`/api/device-fleet/devices/${id}/${action}/`, {});
    showToast('Done.');
    const idx = currentDevices.findIndex(d => d.id === id);
    if (idx >= 0) currentDevices[idx] = res.data;
    renderDeviceTable('#device-table-body', currentDevices.slice(0, 6), false);
    if (document.querySelector('#view-devices').style.display !== 'none') {
      renderDeviceTable('#device-table-body-full', currentDevices, true);
    }
    selectDevice(id);
  } catch (err) {
    handleApiError(err);
  }
}

// window.prompt() isn't implemented in Electron's renderer at all (throws
// "prompt() is not supported") - use the app's own modal instead of the
// native dialog, and a dropdown of real school names rather than asking
// the admin to type an exact schema code from memory.
let _reassignDevice = null;

async function openReassignPrompt(device) {
  _reassignDevice = device;
  await loadWizardSchools();
  $('#reassign-device-name').textContent = device.device_id;
  $('#reassign-school-select').innerHTML = schoolsCache
    .map(s => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('');
  $('#reassign-error').style.display = 'none';
  $('#reassign-modal').classList.add('active');
}

function closeReassignModal() { $('#reassign-modal').classList.remove('active'); }
$('#reassign-modal-close').addEventListener('click', closeReassignModal);
$('#reassign-modal-cancel').addEventListener('click', closeReassignModal);

$('#reassign-modal-confirm').addEventListener('click', async () => {
  const device = _reassignDevice;
  const schoolId = $('#reassign-school-select').value;
  const school = schoolsCache.find(s => s.id === schoolId);
  if (!device || !school) return;
  try {
    const res = await API.post(`/api/device-fleet/devices/${device.id}/assign-school/`, { school_id: school.id });
    showToast(`${device.device_id} assigned to ${school.name}.`);
    const idx = currentDevices.findIndex(d => d.id === device.id);
    if (idx >= 0) currentDevices[idx] = res.data;
    selectDevice(device.id);
    renderDeviceTable('#device-table-body', currentDevices.slice(0, 6), false);
    closeReassignModal();
  } catch (err) {
    $('#reassign-error').textContent = err.message;
    $('#reassign-error').style.display = 'block';
  }
});

// ---------------------------------------------------------------- Recent Activity (timeline)

const ACTION_ICON = {
  device_registered: ['devices', 'i-green'], device_provisioned: ['devices', 'i-green'],
  card_assigned: ['card', 'i-blue'], card_revoked: ['card', 'i-gold'],
  device_suspended: ['alertTriangle', 'i-gold'], device_reactivated: ['checkCircle', 'i-green'],
  device_revoked: ['xCircle', 'i-red'], school_assigned: ['school', 'i-blue'], school_unassigned: ['school', 'i-gold'],
};

function renderActivity(logs) {
  const el = $('#activity-list');
  if (!logs.length) {
    el.innerHTML = `<div class="empty-state">
      <div class="empty-state-icon">${ICONS.audit}</div>
      <div class="empty-state-title">No recent activity</div>
      <div class="empty-state-desc">Device and card management actions will show up here.</div>
    </div>`;
    return;
  }
  el.innerHTML = `<div class="timeline">${logs.map(l => {
    const [iconKey, cls] = ACTION_ICON[l.action] || ['audit', 'i-blue'];
    return `
    <div class="timeline-item">
      <span class="timeline-icon ${cls}">${ICONS[iconKey]}</span>
      <div class="timeline-body">
        <div class="activity-text">${formatAction(l.action)}</div>
        ${l.device_id ? `<div class="activity-sub">${l.device_id}</div>` : ''}
        <div class="activity-time">${l.actor_name} &bull; ${timeAgo(l.created_at)}</div>
      </div>
    </div>`;
  }).join('')}</div>`;
}

function formatAction(action) {
  return (action || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// ---------------------------------------------------------------- Alerts

function renderAlerts(devices) {
  const el = $('#alerts-list');
  const alerts = [];
  devices.forEach(d => {
    if (d.is_low_battery) alerts.push({ icon: 'battery', cls: 'i-red', text: `${d.device_id} battery is at ${d.battery_percentage}%.` });
    if (!d.is_online && d.last_seen_at) alerts.push({ icon: 'wifiOff', cls: 'i-red', text: `${d.device_id} has been offline since ${timeAgo(d.last_seen_at)}.` });
    if (d.battery_health === 'poor') alerts.push({ icon: 'battery', cls: 'i-gold', text: `${d.device_id} reports poor battery health.` });
    if (d.status === 'suspended') alerts.push({ icon: 'alertTriangle', cls: 'i-gold', text: `${d.device_id} is suspended.` });
  });
  if (!alerts.length) {
    el.innerHTML = `<div class="empty-state empty-state-good">
      <div class="empty-state-icon">${ICONS.checkCircle}</div>
      <div class="empty-state-title">Everything looks good</div>
      <div class="empty-state-desc">No device alerts require your attention.</div>
    </div>`;
    return;
  }
  el.innerHTML = alerts.slice(0, 8).map(a => `
    <div class="alert-item">
      <span class="alert-icon ${a.cls}">${ICONS[a.icon]}</span>
      <div><div class="alert-text">${a.text}</div></div>
    </div>
  `).join('');
}

// ---------------------------------------------------------------- Quick actions

function renderQuickActions() {
  $('#quick-actions-body').innerHTML = `
    <button class="qa-btn" id="qa-register-device"><span class="qa-icon">${ICONS.plusCircle}</span>Register New Device</button>
    <button class="qa-btn" id="qa-generate-key"><span class="qa-icon">${ICONS.key}</span>Generate License Key</button>
    <button class="qa-btn" id="qa-assign-card" data-view-link-inline="cards"><span class="qa-icon">${ICONS.card}</span>Assign Card</button>
    <button class="qa-btn" id="qa-view-devices" data-view-link-inline="devices"><span class="qa-icon">${ICONS.devices}</span>View Devices</button>
    <button class="qa-btn" id="qa-refresh"><span class="qa-icon">${ICONS.refresh}</span>Refresh Data</button>
  `;
  $('#qa-refresh').addEventListener('click', loadDashboard);
  $('#qa-generate-key').addEventListener('click', generateLicenseKey);
  $('#qa-register-device').addEventListener('click', generateLicenseKey);
  $all('[data-view-link-inline]').forEach(btn => btn.addEventListener('click', () => switchView(btn.dataset.viewLinkInline)));
}

async function generateLicenseKey() {
  try {
    const res = await API.post('/api/device-fleet/provisioning-keys/', {});
    $('#key-modal-value').textContent = res.data.key;
    $('#key-modal').classList.add('active');
  } catch (err) {
    handleApiError(err);
  }
}

$('#key-modal-close').addEventListener('click', () => $('#key-modal').classList.remove('active'));
$('#key-modal-done').addEventListener('click', () => $('#key-modal').classList.remove('active'));
$('#key-modal-copy').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText($('#key-modal-value').textContent);
    showToast('Copied to clipboard.');
  } catch {
    showToast('Could not copy - select and copy manually.', true);
  }
});

// ---------------------------------------------------------------- Devices view

async function loadDevicesView(filterKey) {
  $('#device-table-body-full').innerHTML = skeletonRows(6, 8);
  try {
    const path = '/api/device-fleet/devices/' + (filterKey && filterKey !== 'all' ? `?filter=${filterKey}` : '');
    const res = await API.get(path);
    currentDevices = filterKey ? currentDevices : res.data;
    let rows = res.data;
    const search = ($('#device-search').value || '').trim().toLowerCase();
    if (search) {
      rows = rows.filter(d => d.device_id.toLowerCase().includes(search) || (d.school_name || '').toLowerCase().includes(search) || (d.name || '').toLowerCase().includes(search));
    }
    renderDeviceTable('#device-table-body-full', rows, true);
    renderDeviceFilterBar(filterKey || 'all');
  } catch (err) {
    handleApiError(err);
  }
}

$('#device-search').addEventListener('input', debounce(() => loadDevicesView(), 300));
$('#devices-register-btn').addEventListener('click', generateLicenseKey);

function renderDeviceFilterBar(active) {
  const filters = ['all', 'online', 'offline', 'low_battery', 'charging', 'unassigned', 'suspended', 'needs_attention'];
  $('#device-filter-bar').innerHTML = filters.map(f => `
    <button class="filter-chip ${f === active ? 'active' : ''}" data-filter="${f}">
      ${f.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
    </button>
  `).join('');
  $all('[data-filter]').forEach(btn => btn.addEventListener('click', () => loadDevicesView(btn.dataset.filter)));
}

// ---------------------------------------------------------------- Audit view

let auditCache = [];

async function loadAuditView() {
  $('#audit-table-body').innerHTML = skeletonRows(6, 5);
  try {
    const res = await API.get('/api/device-fleet/audit-logs/');
    auditCache = res.data;
    renderAuditTable(auditCache);
  } catch (err) {
    handleApiError(err);
  }
}

function renderAuditTable(logs) {
  const body = $('#audit-table-body');
  if (!logs.length) {
    body.innerHTML = `<tr><td colspan="5" style="padding:0;">
      <div class="empty-state">
        <div class="empty-state-icon">${ICONS.audit}</div>
        <div class="empty-state-title">No audit events yet</div>
        <div class="empty-state-desc">Every device-management action will be recorded here.</div>
      </div>
    </td></tr>`;
    return;
  }
  body.innerHTML = logs.map(l => `
    <tr>
      <td style="color:var(--muted);font-size:12px;">${new Date(l.created_at).toLocaleString()}</td>
      <td style="font-weight:700;">${formatAction(l.action)}</td>
      <td class="mono">${l.device_id || '&mdash;'}</td>
      <td>${l.actor_name}</td>
      <td>${l.result === 'success' ? `<span class="pill pill-green">${ICONS.check}Success</span>` : `<span class="pill pill-red">${ICONS.x}${l.result}</span>`}</td>
    </tr>
  `).join('');
}

$('#audit-search').addEventListener('input', debounce(() => {
  const search = $('#audit-search').value.trim().toLowerCase();
  const filtered = search
    ? auditCache.filter(l => formatAction(l.action).toLowerCase().includes(search) || (l.device_id || '').toLowerCase().includes(search) || (l.actor_name || '').toLowerCase().includes(search))
    : auditCache;
  renderAuditTable(filtered);
}, 250));

// ---------------------------------------------------------------- Card management

let cardsCache = [];

async function loadCardsView() {
  $('#cards-table-body').innerHTML = skeletonRows(5, 5);
  try {
    await loadWizardSchools();
    const school = $('#wiz-school').value;
    if (!school) {
      cardsCache = [];
      renderCardsStats([]);
      $('#cards-table-body').innerHTML = `<tr><td colspan="5" style="padding:0;">
        <div class="empty-state">
          <div class="empty-state-icon">${ICONS.card}</div>
          <div class="empty-state-title">Select a school</div>
          <div class="empty-state-desc">Pick a school in the Assign Card wizard on the Dashboard to see its card assignments.</div>
        </div>
      </td></tr>`;
      return;
    }
    const res = await API.get(`/api/rfid/card-assignments/?school_code=${encodeURIComponent(school)}`);
    cardsCache = res.data;
    renderCardsStats(cardsCache);
    renderCardsTable(cardsCache, school);
  } catch (err) {
    handleApiError(err);
  }
}

function renderCardsStats(cards) {
  ['total', 'assigned', 'unassigned', 'recent'].forEach(k => { const el = $('#cards-stat-icon-' + k); if (el) el.innerHTML = ''; });
  $('#cards-stat-icon-total').innerHTML = ICONS.card;
  $('#cards-stat-icon-assigned').innerHTML = ICONS.checkCircle;
  $('#cards-stat-icon-unassigned').innerHTML = ICONS.xCircle;
  $('#cards-stat-icon-recent').innerHTML = ICONS.clock;
  const recent = cards.filter(c => c.assigned_at && (Date.now() - new Date(c.assigned_at).getTime()) < 7 * 86400000).length;
  countUp($('#cards-stat-total'), cards.length);
  countUp($('#cards-stat-assigned'), cards.length);
  countUp($('#cards-stat-unassigned'), 0);
  countUp($('#cards-stat-recent'), recent);
}

function renderCardsTable(cards, school) {
  const body = $('#cards-table-body');
  if (!cards.length) {
    body.innerHTML = `<tr><td colspan="5" style="padding:0;">
      <div class="empty-state">
        <div class="empty-state-icon">${ICONS.card}</div>
        <div class="empty-state-title">No active card assignments</div>
        <div class="empty-state-desc">Assign a card to a student from the wizard on the Dashboard.</div>
      </div>
    </td></tr>`;
    return;
  }
  body.innerHTML = cards.map(c => `
    <tr>
      <td>
        <div class="cell-with-icon">
          <span class="table-row-icon">${ICONS.user}</span>
          <div style="font-weight:700;">${escapeHtml(c.person_name)}</div>
        </div>
      </td>
      <td class="mono">${c.student_id || '&mdash;'}</td>
      <td><span class="pill pill-blue">${escapeHtml(c.role)}</span></td>
      <td style="color:var(--muted);font-size:12px;">${timeAgo(c.assigned_at)}</td>
      <td><span class="card-link" data-unassign="${c.card_uid}">Unassign</span></td>
    </tr>
  `).join('');
  $all('[data-unassign]').forEach(link => link.addEventListener('click', () => unassignCard(link.dataset.unassign, school)));
}

$('#cards-search').addEventListener('input', debounce(() => {
  const search = $('#cards-search').value.trim().toLowerCase();
  const school = $('#wiz-school').value;
  const filtered = search
    ? cardsCache.filter(c => c.person_name.toLowerCase().includes(search) || (c.student_id || '').toLowerCase().includes(search))
    : cardsCache;
  renderCardsTable(filtered, school);
}, 250));

async function unassignCard(cardUid, schoolCode) {
  if (!confirm(`Unassign this card?`)) return;
  try {
    await API.post('/api/rfid/card-assignments/revoke/', { card_uid: cardUid, school_code: schoolCode });
    showToast('Card unassigned.');
    loadCardsView();
  } catch (err) {
    handleApiError(err);
  }
}

// ---------------------------------------------------------------- Schools view

async function loadSchoolsView() {
  $('#schools-body').innerHTML = `<div class="schools-grid">${Array.from({ length: 3 }).map(() => `
    <div class="school-card"><div class="skel" style="height:110px;"></div></div>
  `).join('')}</div>`;
  try {
    const [schoolsRes, devicesRes] = await Promise.all([
      API.get('/api/device-fleet/schools/'),
      API.get('/api/device-fleet/devices/'),
    ]);
    schoolsCache = schoolsRes.data;
    currentDevices = devicesRes.data;
    renderSchools(schoolsCache);
  } catch (err) {
    handleApiError(err);
  }
}

function renderSchools(schools) {
  const el = $('#schools-body');
  if (!schools.length) {
    el.innerHTML = `<div class="card"><div class="empty-state">
      <div class="empty-state-icon">${ICONS.school}</div>
      <div class="empty-state-title">No schools connected yet</div>
      <div class="empty-state-desc">Schools appear here once they're set up on the SchoolDom platform.</div>
    </div></div>`;
    return;
  }
  el.innerHTML = `<div class="schools-grid">${schools.map(s => {
    const devices = currentDevices.filter(d => d.school_name === s.name);
    const online = devices.filter(d => d.is_online).length;
    const lastSeen = devices.reduce((max, d) => {
      if (!d.last_seen_at) return max;
      const t = new Date(d.last_seen_at).getTime();
      return t > max ? t : max;
    }, 0);
    return `
    <div class="school-card" data-school="${s.schema_name}">
      <div class="school-card-top">
        <span class="school-icon">${ICONS.school}</span>
        <div>
          <div class="school-name">${escapeHtml(s.name)}</div>
          <div class="school-code">${s.schema_name}</div>
        </div>
      </div>
      <div class="school-stats">
        <div><div class="school-stat-value">${devices.length}</div><div class="school-stat-label">Devices</div></div>
        <div><div class="school-stat-value">${online}</div><div class="school-stat-label">Online</div></div>
        <div><div class="school-stat-value">${s.student_count ?? '&mdash;'}</div><div class="school-stat-label">Students</div></div>
      </div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-top:12px;padding-top:12px;border-top:1px solid var(--border);">
        <span class="pill pill-green">${ICONS.check}Active</span>
        <span style="font-size:11px;color:var(--muted);font-weight:600;">${lastSeen ? timeAgo(new Date(lastSeen).toISOString()) : 'No activity yet'}</span>
      </div>
    </div>`;
  }).join('')}</div>`;

  $all('[data-school]').forEach(card => card.addEventListener('click', () => {
    switchView('devices');
    $('#device-search').value = card.dataset.school;
    loadDevicesView();
  }));
}

$('#schools-search').addEventListener('input', debounce(() => {
  const search = $('#schools-search').value.trim().toLowerCase();
  const filtered = search ? schoolsCache.filter(s => s.name.toLowerCase().includes(search) || s.schema_name.toLowerCase().includes(search)) : schoolsCache;
  renderSchools(filtered);
}, 250));

// ---------------------------------------------------------------- Assign Card wizard

async function loadWizardSchools() {
  if (!schoolsCache.length) {
    const res = await API.get('/api/device-fleet/schools/');
    schoolsCache = res.data;
  }
  const select = $('#wiz-school');
  if (select.options.length <= 1) {
    select.innerHTML = '<option value="">Select a school...</option>' +
      schoolsCache.map(s => `<option value="${s.schema_name}">${escapeHtml(s.name)}</option>`).join('');
  }
}

function updateWizardStepState() {
  const steps = $all('#wizard-steps .wizard-step');
  steps[0]?.classList.toggle('done', !!$('#wiz-school').value);
  steps[1]?.classList.toggle('done', !!$('#wiz-student').value);
  steps[2]?.classList.toggle('done', !!$('#wiz-card-uid').value.trim());
}

$('#wiz-school').addEventListener('change', () => { loadWizardStudents(); updateWizardStepState(); });
$('#wiz-student-search').addEventListener('input', debounce(loadWizardStudents, 350));
$('#wiz-student').addEventListener('change', updateWizardStepState);
$('#wiz-card-uid').addEventListener('input', updateWizardStepState);

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

async function loadWizardStudents() {
  const school = $('#wiz-school').value;
  const select = $('#wiz-student');
  if (!school) { select.innerHTML = ''; return; }
  try {
    const search = $('#wiz-student-search').value.trim();
    const res = await API.get(`/api/rfid/people/?school_code=${encodeURIComponent(school)}&roles=student&search=${encodeURIComponent(search)}`);
    select.innerHTML = res.data.map(p => `<option value="${p.id}" data-name="${escapeHtml(p.name)}">${escapeHtml(p.name)}${p.student_id ? ' (' + p.student_id + ')' : ''}</option>`).join('')
      || '<option value="">No students found</option>';
  } catch (err) {
    handleApiError(err);
  }
}

$('#wiz-assign-btn').addEventListener('click', async () => {
  const school = $('#wiz-school').value;
  const studentSelect = $('#wiz-student');
  const studentId = studentSelect.value;
  const studentName = studentSelect.selectedOptions[0]?.dataset.name;
  const cardUid = $('#wiz-card-uid').value.trim();

  if (!school || !studentId || !cardUid) {
    showToast('Select a school, a student, and enter a card ID.', true);
    return;
  }
  try {
    await API.post('/api/rfid/card-assignments/assign/', {
      school_code: school, person_id: studentId, card_uid: cardUid,
    });
    showToast(`Card assigned to ${studentName}.`);
    $('#wiz-card-uid').value = '';
    updateWizardStepState();
  } catch (err) {
    if (err.message && err.message.includes('already')) {
      if (confirm(err.message + '\n\nReassign anyway?')) {
        try {
          await API.post('/api/rfid/card-assignments/assign/', {
            school_code: school, person_id: studentId, card_uid: cardUid, force: true,
          });
          showToast(`Card reassigned to ${studentName}.`);
          $('#wiz-card-uid').value = '';
          updateWizardStepState();
          return;
        } catch (err2) { handleApiError(err2); return; }
      }
      return;
    }
    handleApiError(err);
  }
});

// ---------------------------------------------------------------- Boot + auto-refresh

boot();
setInterval(() => {
  if (document.querySelector('#view-dashboard').style.display !== 'none' && $('#app-shell').classList.contains('active')) {
    loadDashboard();
  }
}, 30000);
