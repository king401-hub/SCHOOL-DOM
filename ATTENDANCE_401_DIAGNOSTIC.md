# Attendance QR Code 401 Unauthorized - Diagnostic Guide

## Problem
`POST /api/attendance/qr-code/generate/ HTTP/1.1" 401 172` - Unauthorized error when generating QR codes.

## Root Cause
The frontend is not sending a valid JWT authentication token in the request. Django requires the `Authorization: Bearer <token>` header, but the request is being sent without it.

## How It Should Work
1. **User logs in** → Backend returns `{access: "jwt_token", refresh: "...", user: {...}}`
2. **Session stored** → Browser localStorage/sessionStorage holds the session object
3. **API requests** → Frontend checks `session.access` and adds `Authorization: Bearer {token}` header
4. **Backend validates** → Uses JWT to authenticate the user
5. **Request succeeds** → Returns 201/200 response

## How It's Currently Failing
1. Session might be **null** or missing `access` property
2. **No** `Authorization` header is being sent
3. Backend returns **401 Unauthorized**

## Diagnostics

### Step 1: Check Browser Console
Open DevTools (F12) and check the browser console. You should see a message like:
```
Attendance Request Error: Missing session.access token
```

### Step 2: Verify Session Storage
In the browser console, run:
```javascript
// Check localStorage
const session = JSON.parse(localStorage.getItem('schooldom.session') || '{}');
console.log('Session:', session);
console.log('Has access token:', !!session.access);
```

Expected output:
```
Session: {user: {...}, access: "eyJ0eXAi...", refresh: "...", ...}
Has access token: true
```

### Step 3: Check Network Tab
1. Try to generate a QR code
2. Open DevTools → Network tab
3. Find the POST request to `/api/attendance/qr-code/generate/`
4. **Request Headers** should include:
   ```
   Authorization: Bearer eyJ0eXAi...
   ```

If this header is missing, the session.access token is the issue.

## Solutions

### Solution 1: Sign In Again (Most Common)
1. Click **Sign Out** in the app
2. Sign in again with your credentials
3. Try generating the QR code again

This refreshes the session with a new, valid JWT token.

### Solution 2: Clear Storage and Refresh
1. Open DevTools → Application tab
2. Clear **localStorage** and **sessionStorage** under schooldom.session
3. Refresh the page
4. Sign in again

### Solution 3: Check Token Expiration
JWT tokens have an expiration time. If your token has expired:
```javascript
const token = JSON.parse(localStorage.getItem('schooldom.session') || '{}').access;
if (token) {
  const payload = JSON.parse(atob(token.split('.')[1]));
  console.log('Token expires at:', new Date(payload.exp * 1000));
}
```

If the token is expired, sign out and sign in again.

### Solution 4: Backend Token Refresh Issue
If the problem persists after signing in:
1. Check backend logs: `python manage.py runserver --verbosity 3`
2. Verify JWT settings in `backend/config/settings.py`
3. Ensure the login endpoint is returning `access` and `refresh` tokens

## Files Modified
- `backend/frontend/src/components/Attendance.jsx`
  - Added debug logging for missing session.access
  - Added session validation in QRCodeManagement component

## Next Steps
1. Check browser console for the diagnostic message
2. Verify session in localStorage (see Step 2 above)
3. Sign out and sign in again
4. Try generating the QR code

If the 401 error persists after these steps, check the Django logs for auth-related errors.
