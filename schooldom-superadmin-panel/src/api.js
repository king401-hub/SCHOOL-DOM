// Thin fetch wrapper against the SchoolDom API. Session (JWT access token)
// persists in localStorage, which is per-origin and private to this
// Electron app's own renderer - not shared with any other app or website.
// Different SchoolDom endpoints shape their error bodies differently -
// {message}/{detail} (most DRF views here), {errors: {error: [...]}} (the
// login endpoint specifically), or generic DRF field-validation errors
// ({errors: {field: [...]}}). Try each rather than falling back to a bare
// status code, which is what a real login failure surfaced as before this.
function extractErrorMessage(data) {
  if (!data) return null;
  if (data.message) return data.message;
  if (data.detail) return data.detail;
  if (data.errors && typeof data.errors === 'object') {
    for (const key of Object.keys(data.errors)) {
      const value = data.errors[key];
      if (Array.isArray(value) && value.length) return value[0];
      if (typeof value === 'string') return value;
    }
  }
  return null;
}

const API = (() => {
  const BASE_URL = 'https://schooldom.academy';
  const STORAGE_KEY = 'schooldom_superadmin_session';

  function loadSession() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  function saveSession(session) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  }

  function clearSession() {
    localStorage.removeItem(STORAGE_KEY);
  }

  async function request(method, path, body) {
    const session = loadSession();
    const headers = { 'Content-Type': 'application/json' };
    if (session && session.access) headers['Authorization'] = 'Bearer ' + session.access;

    let response;
    try {
      response = await fetch(BASE_URL + path, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (err) {
      throw new Error('Network error: could not reach the SchoolDom server.');
    }

    let data = null;
    try { data = await response.json(); } catch { /* empty body */ }

    if (response.status === 401) {
      clearSession();
      throw new Error('AUTH_EXPIRED');
    }
    if (!response.ok) {
      throw new Error(extractErrorMessage(data) || `Request failed (${response.status}).`);
    }
    return data;
  }

  return {
    get: (path) => request('GET', path),
    post: (path, body) => request('POST', path, body),

    async login(email, password) {
      const data = await request('POST', '/api/auth/login/', { email, password });
      if (!data || !data.access) throw new Error('Sign-in succeeded but no access token was returned.');
      saveSession({
        access: data.access,
        userName: data.user ? `${data.user.first_name || ''} ${data.user.last_name || ''}`.trim() : email,
        userEmail: email,
        userRole: data.user ? data.user.role : null,
      });
      return loadSession();
    },

    signOut() { clearSession(); },
    currentSession: loadSession,
  };
})();
