// Single-page app logic - no framework/build step, just DOM + fetch via API
// (api.js). Views are plain <div id="view-...">, toggled by data-view nav
// clicks; each view's data is (re)loaded when it becomes active.

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

// ---------------------------------------------------------------- Auth

function boot() {
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
  $('#user-avatar').textContent = (session.userName || 'SA')
    .split(' ').map(p => p[0]).slice(0, 2).join('').toUpperCase() || 'SA';
  loadDashboard();
}

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
  const btn = $('#login-submit');
  btn.disabled = true;
  btn.textContent = 'Signing in...';
  try {
    const session = await API.login(email, password);
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
    btn.textContent = 'Sign In';
  }
});

$('#login-password').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') $('#login-submit').click();
});

$('#sign-out-btn').addEventListener('click', () => {
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
  schools: ['&#127979;', 'Schools', 'Full school directory and onboarding is next on the list.'],
  students: ['&#128101;', 'Students', 'A cross-school student directory is next on the list.'],
  attendance: ['&#128203;', 'Attendance Logs', 'A merged attendance log across every device is next on the list.'],
  alerts: ['&#9888;', 'Alerts', 'Alerts show live on the Dashboard for now - a dedicated history view is next.'],
  reports: ['&#128202;', 'Reports', 'Usage and attendance reporting is next on the list.'],
  settings: ['&#9881;', 'Settings', 'Global platform settings are next on the list.'],
  users: ['&#128100;', 'Users', 'Superadmin user management is next on the list.'],
};

function switchView(name) {
  $all('.nav-item').forEach(i => i.classList.toggle('active', i.dataset.view === name));
  $all('.view').forEach(v => v.style.display = 'none');

  const view = $('#view-' + name);
  if (!view) return;
  view.style.display = 'block';

  if (view.classList.contains('placeholder-view') && !view.dataset.rendered) {
    const [icon, title, copy] = PLACEHOLDER_COPY[name] || ['&#128736;', title, 'Coming soon.'];
    view.innerHTML = `<div class="placeholder"><div class="placeholder-icon">${icon}</div><h3>${title}</h3><p>${copy}</p></div>`;
    view.dataset.rendered = '1';
  }

  if (name === 'dashboard') loadDashboard();
  if (name === 'devices') loadDevicesView();
  if (name === 'audit') loadAuditView();
  if (name === 'cards') loadCardsView();
}

// ---------------------------------------------------------------- Dashboard

async function loadDashboard() {
  try {
    const [devicesRes, auditRes] = await Promise.all([
      API.get('/api/device-fleet/devices/'),
      API.get('/api/device-fleet/audit-logs/'),
    ]);
    currentDevices = devicesRes.data;
    renderStats(devicesRes.stats);
    renderDeviceTable('#device-table-body', currentDevices.slice(0, 6), false);
    renderActivity(auditRes.data.slice(0, 6));
    renderAlerts(currentDevices);
    loadWizardSchools();
  } catch (err) {
    handleApiError(err);
  }
}

function renderStats(stats) {
  $('#stat-total').textContent = stats.total;
  $('#stat-online').textContent = stats.online;
  $('#stat-offline').textContent = stats.offline;
  $('#stat-schools').textContent = stats.total_schools;
  $('#stat-attention').textContent = stats.needs_attention;
  $('#stat-online-pct').textContent = stats.total ? `${Math.round(100 * stats.online / stats.total)}%` : '';
  $('#stat-offline-pct').textContent = stats.total ? `${Math.round(100 * stats.offline / stats.total)}%` : '';
}

function statusPill(device) {
  if (device.status === 'suspended') return `<span class="pill pill-gold"><span class="pill-dot" style="background:var(--gold)"></span>Suspended</span>`;
  if (device.status === 'revoked') return `<span class="pill pill-red"><span class="pill-dot" style="background:var(--coral)"></span>Revoked</span>`;
  if (!device.tenant_id && !device.school_name) return `<span class="pill pill-muted"><span class="pill-dot" style="background:var(--muted)"></span>Unassigned</span>`;
  if (device.is_online) return `<span class="pill pill-green"><span class="pill-dot" style="background:var(--green)"></span>Online</span>`;
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
    <span class="battery-shell"><span class="battery-fill" style="width:${Math.max(2, device.battery_percentage * 0.2)}px;background:${color}"></span></span>
    ${device.battery_percentage}%${device.battery_charging ? ' &#9889;' : ''}
  </span>`;
}

function renderDeviceTable(bodySelector, devices, full) {
  const body = $(bodySelector);
  if (!devices.length) {
    body.innerHTML = `<tr><td colspan="8" class="empty-hint">No devices registered yet.</td></tr>`;
    return;
  }
  body.innerHTML = devices.map(d => `
    <tr class="device-row ${d.id === selectedDeviceId ? 'selected' : ''}" data-id="${d.id}">
      <td class="dev-name">${d.device_id}${d.name ? ' &middot; ' + escapeHtml(d.name) : ''}</td>
      <td class="mono">${d.license_key || '&mdash;'}</td>
      <td>${d.school_name || '<span style="color:var(--muted)">Unassigned</span>'}</td>
      <td>${statusPill(d)}</td>
      <td>${batteryHtml(d)}</td>
      ${full ? `<td>${healthPill(d.battery_health)}</td>` : ''}
      <td style="color:var(--muted);font-size:12px;">${timeAgo(d.last_seen_at)}</td>
      ${full ? `<td><span class="card-link" data-open-detail="${d.id}">Manage</span></td>` : ''}
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
  const color = health === 'good' ? 'var(--green)' : health === 'poor' ? 'var(--coral)' : health === 'fair' ? 'var(--gold)' : 'var(--muted)';
  return `<span style="color:${color};font-weight:700;">${labels[health] || health}</span>`;
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
  $('#device-detail-body').innerHTML = `
    <div class="detail-row"><span class="detail-label">Device</span><span class="detail-value">${d.device_id}</span></div>
    <div class="detail-row"><span class="detail-label">Status</span><span class="detail-value">${statusPill(d)}</span></div>
    <div class="detail-row"><span class="detail-label">School</span><span class="detail-value">${d.school_name || 'Unassigned'}</span></div>
    <div class="detail-row"><span class="detail-label">License Key</span><span class="detail-value mono">${d.license_key || '&mdash;'}</span></div>
    <div class="detail-row"><span class="detail-label">App Version</span><span class="detail-value">${d.app_version || 'Unknown'}</span></div>
    <div class="detail-row"><span class="detail-label">Device Model</span><span class="detail-value">${d.device_model || 'Unknown'}</span></div>
    <div class="detail-row"><span class="detail-label">Last Seen</span><span class="detail-value">${timeAgo(d.last_seen_at)}</span></div>
    <div class="detail-row"><span class="detail-label">Last Sync</span><span class="detail-value">${timeAgo(d.last_sync_at)}</span></div>
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
      <div class="health-item"><span class="detail-label">Charging Status</span><span class="detail-value">${d.battery_charging === null ? 'Not reported' : (d.battery_charging ? 'Charging' : 'Not charging')}</span></div>
      <div class="health-item"><span class="detail-label">Temperature</span><span class="detail-value">${d.battery_temperature_c !== null && d.battery_temperature_c !== undefined ? d.battery_temperature_c + '&deg;C' : 'Not supported'}</span></div>
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

function openReassignPrompt(device) {
  const target = prompt(`Reassign ${device.device_id} to which school? Enter the school's short code (schema name).`, '');
  if (!target) return;
  const school = schoolsCache.find(s => s.schema_name.toLowerCase() === target.trim().toLowerCase());
  if (!school) { showToast('No school found with that code.', true); return; }
  API.post(`/api/device-fleet/devices/${device.id}/assign-school/`, { school_id: school.id })
    .then(res => {
      showToast(`${device.device_id} assigned to ${school.name}.`);
      const idx = currentDevices.findIndex(d => d.id === device.id);
      if (idx >= 0) currentDevices[idx] = res.data;
      selectDevice(device.id);
      renderDeviceTable('#device-table-body', currentDevices.slice(0, 6), false);
    })
    .catch(handleApiError);
}

function renderActivity(logs) {
  const el = $('#activity-list');
  if (!logs.length) { el.innerHTML = '<div class="empty-hint">No recent activity.</div>'; return; }
  el.innerHTML = logs.map(l => `
    <div class="activity-item">
      <div class="activity-text">${formatAction(l.action)}${l.device_id ? ` &middot; ${l.device_id}` : ''}</div>
      <div class="activity-time">${l.actor_name} &bull; ${timeAgo(l.created_at)}</div>
    </div>
  `).join('');
}

function formatAction(action) {
  return (action || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function renderAlerts(devices) {
  const el = $('#alerts-list');
  const alerts = [];
  devices.forEach(d => {
    if (d.is_low_battery) alerts.push({ color: 'var(--coral)', text: `${d.device_id} battery is at ${d.battery_percentage}%.` });
    if (!d.is_online && d.last_seen_at) alerts.push({ color: 'var(--coral)', text: `${d.device_id} has been offline for ${timeAgo(d.last_seen_at)}.` });
    if (d.battery_health === 'poor') alerts.push({ color: 'var(--gold)', text: `${d.device_id} reports poor battery health.` });
    if (d.status === 'suspended') alerts.push({ color: 'var(--gold)', text: `${d.device_id} is suspended.` });
  });
  if (!alerts.length) { el.innerHTML = '<div class="empty-hint">No active alerts.</div>'; return; }
  el.innerHTML = alerts.slice(0, 8).map(a => `
    <div class="alert-item"><span class="alert-dot" style="background:${a.color}"></span><span>${a.text}</span></div>
  `).join('');
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ---------------------------------------------------------------- Devices view

async function loadDevicesView(filterKey) {
  try {
    const path = '/api/device-fleet/devices/' + (filterKey && filterKey !== 'all' ? `?filter=${filterKey}` : '');
    const res = await API.get(path);
    currentDevices = filterKey ? currentDevices : res.data;
    renderDeviceTable('#device-table-body-full', res.data, true);
    renderDeviceFilterBar(filterKey || 'all');
  } catch (err) {
    handleApiError(err);
  }
}

function renderDeviceFilterBar(active) {
  const filters = ['all', 'online', 'offline', 'low_battery', 'charging', 'unassigned', 'suspended', 'needs_attention'];
  $('#device-filter-bar').innerHTML = filters.map(f => `
    <button class="btn ${f === active ? 'btn-primary' : 'btn-secondary'}" data-filter="${f}" style="padding:7px 14px;font-size:12px;">
      ${f.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
    </button>
  `).join('');
  $all('[data-filter]').forEach(btn => btn.addEventListener('click', () => loadDevicesView(btn.dataset.filter)));
}

// ---------------------------------------------------------------- Audit view

async function loadAuditView() {
  try {
    const res = await API.get('/api/device-fleet/audit-logs/');
    const body = $('#audit-table-body');
    if (!res.data.length) { body.innerHTML = '<tr><td colspan="5" class="empty-hint">No audit events yet.</td></tr>'; return; }
    body.innerHTML = res.data.map(l => `
      <tr>
        <td style="color:var(--muted);font-size:12px;">${new Date(l.created_at).toLocaleString()}</td>
        <td style="font-weight:700;">${formatAction(l.action)}</td>
        <td>${l.device_id || '&mdash;'}</td>
        <td>${l.actor_name}</td>
        <td>${l.result === 'success' ? '<span class="pill pill-green">Success</span>' : `<span class="pill pill-red">${l.result}</span>`}</td>
      </tr>
    `).join('');
  } catch (err) {
    handleApiError(err);
  }
}

// ---------------------------------------------------------------- Card management

async function loadCardsView() {
  try {
    await loadWizardSchools();
    const school = $('#wiz-school').value;
    if (!school) {
      $('#cards-table-body').innerHTML = '<tr><td colspan="5" class="empty-hint">Select a school in the Assign Card wizard on the Dashboard first.</td></tr>';
      return;
    }
    const res = await API.get(`/api/rfid/card-assignments/?school_code=${encodeURIComponent(school)}`);
    const body = $('#cards-table-body');
    if (!res.data.length) { body.innerHTML = '<tr><td colspan="5" class="empty-hint">No active card assignments for this school.</td></tr>'; return; }
    body.innerHTML = res.data.map(c => `
      <tr>
        <td class="mono">${c.card_uid}</td>
        <td style="font-weight:700;">${c.person_name}</td>
        <td>${c.role}</td>
        <td style="color:var(--muted);font-size:12px;">${timeAgo(c.assigned_at)}</td>
        <td><span class="card-link" data-unassign="${c.card_uid}">Unassign</span></td>
      </tr>
    `).join('');
    $all('[data-unassign]').forEach(link => link.addEventListener('click', () => unassignCard(link.dataset.unassign, school)));
  } catch (err) {
    handleApiError(err);
  }
}

async function unassignCard(cardUid, schoolCode) {
  if (!confirm(`Unassign card ${cardUid}?`)) return;
  try {
    await API.post('/api/rfid/card-assignments/revoke/', { card_uid: cardUid, school_code: schoolCode });
    showToast('Card unassigned.');
    loadCardsView();
  } catch (err) {
    handleApiError(err);
  }
}

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

$('#wiz-school').addEventListener('change', loadWizardStudents);
$('#wiz-student-search').addEventListener('input', debounce(loadWizardStudents, 350));

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
  } catch (err) {
    if (err.message && err.message.includes('already')) {
      if (confirm(err.message + '\n\nReassign anyway?')) {
        try {
          await API.post('/api/rfid/card-assignments/assign/', {
            school_code: school, person_id: studentId, card_uid: cardUid, force: true,
          });
          showToast(`Card reassigned to ${studentName}.`);
          $('#wiz-card-uid').value = '';
          return;
        } catch (err2) { handleApiError(err2); return; }
      }
      return;
    }
    handleApiError(err);
  }
});

// ---------------------------------------------------------------- Quick actions

$('#qa-refresh').addEventListener('click', loadDashboard);

$('#qa-generate-key').addEventListener('click', async () => {
  try {
    const res = await API.post('/api/device-fleet/provisioning-keys/', {});
    $('#key-modal-value').textContent = res.data.key;
    $('#key-modal').classList.add('active');
  } catch (err) {
    handleApiError(err);
  }
});

$('#qa-register-device').addEventListener('click', () => $('#qa-generate-key').click());

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

// ---------------------------------------------------------------- Boot + auto-refresh

boot();
setInterval(() => {
  if (document.querySelector('#view-dashboard').style.display !== 'none' && $('#app-shell').classList.contains('active')) {
    loadDashboard();
  }
}, 30000);
