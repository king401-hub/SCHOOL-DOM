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
  // Separate from the session (which login/OTP-verify wipe and recreate) -
  // this survives across logins for the same account on this machine so a
  // returning superadmin skips OTP (login_view's own
  // device_trust_token_valid check), rather than needing a 6-digit code
  // every single time they open the app.
  const TRUST_KEY = 'schooldom_superadmin_device_trust';

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

  function loadTrustToken() {
    return localStorage.getItem(TRUST_KEY);
  }

  function saveTrustToken(token) {
    if (token) localStorage.setItem(TRUST_KEY, token);
  }

  function sessionFromTokens(data, email) {
    return {
      access: data.access,
      refresh: data.refresh,
      userName: data.user ? `${data.user.first_name || ''} ${data.user.last_name || ''}`.trim() : email,
      userEmail: email,
      userRole: data.user ? data.user.role : null,
    };
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

    // Every real superadmin account requires OTP (users.views.ADMIN_OTP_ROLES
    // includes super_admin) unless this device already holds a valid trust
    // token from a previous verification - login_view returns a plain
    // {success, requires_otp, otp_challenge, ...} with NO access/refresh at
    // all in that case, not an error. Callers must check result.status.
    async login(email, password) {
      const data = await request('POST', '/api/auth/login/', {
        email,
        password,
        device_trust_token: loadTrustToken() || undefined,
      });

      if (data && data.requires_otp) {
        return {
          status: 'otp_required',
          email,
          challenge: data.otp_challenge,
          userRole: data.user ? data.user.role : null,
        };
      }
      if (!data || !data.access) {
        throw new Error('Sign-in succeeded but no access token was returned.');
      }
      if (data.device_trust_token) saveTrustToken(data.device_trust_token);
      saveSession(sessionFromTokens(data, email));
      return { status: 'ok', session: loadSession() };
    },

    async verifyOtp(email, code, challenge) {
      const data = await request('POST', '/api/auth/admin/verify-otp/', { email, code, challenge });
      if (!data || !data.access) throw new Error('Verification succeeded but no access token was returned.');
      if (data.device_trust_token) saveTrustToken(data.device_trust_token);
      saveSession(sessionFromTokens(data, email));
      return loadSession();
    },

    async resendOtp(email, challenge) {
      return request('POST', '/api/auth/admin/resend-otp/', { email, challenge });
    },

    signOut() { clearSession(); },
    currentSession: loadSession,
  };
})();
