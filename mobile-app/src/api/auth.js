import { API_BASE_URL } from "./config";

export async function login({ email, password, schoolCode }) {
  const response = await fetch(`${API_BASE_URL}/api/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: email.trim(),
      password,
      school_code: schoolCode?.trim() || "",
    }),
  });

  const data = await response.json().catch(() => null);
  if (!response.ok || !data?.success) {
    throw new Error(data?.error || data?.message || "Login failed.");
  }

  if (data.requires_otp) {
    return {
      requiresOtp: true,
      email,
      challenge: data.otp_challenge,
      purpose: data.otp_purpose || "login",
      expiresIn: data.otp_expires_in || 600,
      message: data.message || "Enter the OTP sent to your email.",
      user: data.user,
    };
  }

  return {
    user: data.user,
    access: data.access,
    refresh: data.refresh,
    school_code: data.school_code || schoolCode || "",
    signedInAt: new Date().toISOString(),
  };
}

export async function verifyAdminOtp({ email, code, challenge }) {
  const response = await fetch(`${API_BASE_URL}/api/auth/admin/verify-otp/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, code, challenge }),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || !data?.success || !data?.access) {
    throw new Error(data?.message || data?.error || "OTP verification failed.");
  }
  return {
    user: data.user,
    access: data.access,
    refresh: data.refresh,
    school_code: data.school_code || "",
    signedInAt: new Date().toISOString(),
  };
}
