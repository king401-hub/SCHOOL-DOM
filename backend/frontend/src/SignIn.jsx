import { useEffect, useMemo, useState } from "react";

const SESSION_KEY = "schooldom.session";
const LEGACY_SESSION_KEY = "educonnect.session";
const DEFAULT_SIGNUP_ROLE = "school_admin";
const API_BASE_URL = (() => {
  const raw = import.meta.env.VITE_API_BASE_URL ?? "";
  if (!raw) return ""; // use relative /api/... calls
  const trimmed = raw.replace(/\/+$/, "");
  const withoutApi = trimmed.endsWith("/api") ? trimmed.slice(0, -4) : trimmed;
  if (withoutApi.startsWith("http://") || withoutApi.startsWith("https://")) {
    return withoutApi;
  }
  return `${window.location.protocol}//${window.location.host}${withoutApi.startsWith("/") ? withoutApi : `/${withoutApi}`}`;
})();

function ThemeIcon({ theme }) {
  if (theme === "light") {
    return (
      <svg className="theme-glyph" viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="4.5" />
        <path d="M12 2v3" />
        <path d="M12 19v3" />
        <path d="M2 12h3" />
        <path d="M19 12h3" />
        <path d="M4.9 4.9l2.1 2.1" />
        <path d="M17 17l2.1 2.1" />
        <path d="M19.1 4.9L17 7" />
        <path d="M7 17l-2.1 2.1" />
      </svg>
    );
  }

  return (
    <svg className="theme-glyph" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20.4 15.4A8.5 8.5 0 0 1 8.6 3.6a8.5 8.5 0 1 0 11.8 11.8Z" />
    </svg>
  );
}

function SchoolIcon() {
  return (
    <svg className="school-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 9.5L12 5l9 4.5L12 14 3 9.5Z" />
      <path d="M6 11.2v4.2c0 1.7 2.7 3.1 6 3.1s6-1.4 6-3.1v-4.2" />
    </svg>
  );
}

function CreateSchoolIcon() {
  return (
    <svg className="create-school-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 20h16" />
      <path d="M7 20V8l5-3 5 3v12" />
      <path d="M12 11v6" />
      <path d="M9 14h6" />
    </svg>
  );
}

function parseErrorMessage(payload, fallback) {
  if (!payload) {
    return fallback;
  }

  if (typeof payload.message === "string" && payload.message.trim().length > 0) {
    return payload.message;
  }

  if (payload.errors && typeof payload.errors === "object") {
    const entries = Object.entries(payload.errors);
    if (entries.length > 0) {
      const [field, value] = entries[0];
      if (Array.isArray(value) && value.length > 0) {
        return `${field}: ${String(value[0])}`;
      }
      if (typeof value === "string") {
        return `${field}: ${value}`;
      }
    }
  }

  return fallback;
}

async function postAuth(path, payload) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    throw new Error(`Unable to reach the server at ${API_BASE_URL}. Check network access and backend host settings.`);
  }

  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }

  if (!response.ok) {
    throw new Error(parseErrorMessage(data, "Request failed. Please try again."));
  }

  return data;
}

function Signin({ onAuthenticated, onBack }) {
  const [theme, setTheme] = useState("dark");
  const [mode, setMode] = useState(() => {
    const path = window.location.pathname;
    const token = new URLSearchParams(window.location.search).get("token");
    if (path === "/reset-password" || token) return "reset";
    if (path === "/forgot-password") return "forgot";
    return "signin";
  });

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [showPassword, setShowPassword] = useState(false);

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [signupEmail, setSignupEmail] = useState("");
  const [signupPassword, setSignupPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showSignupPassword, setShowSignupPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [phone, setPhone] = useState("");
  const [schoolCode, setSchoolCode] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpEmail, setOtpEmail] = useState("");
  const [otpChallenge, setOtpChallenge] = useState("");
  const [otpPurpose, setOtpPurpose] = useState("");
  const [otpExpiresIn, setOtpExpiresIn] = useState(0);
  const [isResendingOtp, setIsResendingOtp] = useState(false);
  const [forgotEmail, setForgotEmail] = useState("");
  const [resetToken, setResetToken] = useState(() => new URLSearchParams(window.location.search).get("token") || "");
  const [resetPassword, setResetPassword] = useState("");
  const [resetConfirmPassword, setResetConfirmPassword] = useState("");
  const [showResetPassword, setShowResetPassword] = useState(false);
  const [showResetConfirmPassword, setShowResetConfirmPassword] = useState(false);

  const [showCreateSchool, setShowCreateSchool] = useState(false);
  const [schoolName, setSchoolName] = useState("");
  const [preferredSchoolCode, setPreferredSchoolCode] = useState("");
  const [schoolEmail, setSchoolEmail] = useState("");
  const [isCreatingSchool, setIsCreatingSchool] = useState(false);
  const [schoolError, setSchoolError] = useState("");
  const [schoolSuccess, setSchoolSuccess] = useState("");

  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [signedInUser, setSignedInUser] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [typedTitle, setTypedTitle] = useState("");

  const titleText =
    mode === "otp"
      ? "Verify admin access."
      : mode === "forgot"
        ? "Reset your password."
        : mode === "reset"
          ? "Choose a new password."
          : mode === "signin"
            ? "Sign in to SchoolDom."
            : "Create your SchoolDom account.";

  useEffect(() => {
    document.body.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    const fromLocalStorage = window.localStorage.getItem(SESSION_KEY) || window.localStorage.getItem(LEGACY_SESSION_KEY);
    const fromSessionStorage =
      window.sessionStorage.getItem(SESSION_KEY) || window.sessionStorage.getItem(LEGACY_SESSION_KEY);
    const raw = fromLocalStorage || fromSessionStorage;

    if (!raw) {
      return;
    }

    try {
      setSignedInUser(JSON.parse(raw));
    } catch (storageError) {
      window.localStorage.removeItem(SESSION_KEY);
      window.sessionStorage.removeItem(SESSION_KEY);
      window.localStorage.removeItem(LEGACY_SESSION_KEY);
      window.sessionStorage.removeItem(LEGACY_SESSION_KEY);
    }
  }, []);

  useEffect(() => {
    let index = 0;
    setTypedTitle("");

    const timer = setInterval(() => {
      index += 1;
      setTypedTitle(titleText.slice(0, index));
      if (index >= titleText.length) {
        clearInterval(timer);
      }
    }, 35);

    return () => clearInterval(timer);
  }, [titleText]);

  const canSignIn = useMemo(() => email.trim().length > 0 && password.length > 0, [email, password]);

  const canSignUp = useMemo(() => {
    if (
      firstName.trim().length === 0 ||
      lastName.trim().length === 0 ||
      signupEmail.trim().length === 0 ||
      signupPassword.length === 0 ||
      confirmPassword.length === 0
    ) {
      return false;
    }

    if (signupPassword !== confirmPassword) {
      return false;
    }

    return true;
  }, [confirmPassword, firstName, lastName, signupEmail, signupPassword]);

  const canCreateSchool = useMemo(() => schoolName.trim().length >= 3, [schoolName]);
  const canRequestReset = useMemo(() => forgotEmail.trim().length > 0, [forgotEmail]);
  const canResetPassword = useMemo(
    () => resetToken.trim().length > 0 && resetPassword.length >= 8 && resetPassword === resetConfirmPassword,
    [resetConfirmPassword, resetPassword, resetToken]
  );

  const clearSession = () => {
    window.localStorage.removeItem(SESSION_KEY);
    window.sessionStorage.removeItem(SESSION_KEY);
    window.localStorage.removeItem(LEGACY_SESSION_KEY);
    window.sessionStorage.removeItem(LEGACY_SESSION_KEY);
    window.localStorage.removeItem("access_token");
    window.localStorage.removeItem("refresh_token");
  };

  const switchMode = (nextMode) => {
    setMode(nextMode);
    setShowCreateSchool(false);
    setError("");
    setSuccessMessage("");
    setSchoolError("");
    setSchoolSuccess("");
  };

  const handleCreateSchool = async () => {
    if (!canCreateSchool || isCreatingSchool) {
      return;
    }

    setError("");
    setSuccessMessage("");
    setSchoolError("");
    setSchoolSuccess("");
    setIsCreatingSchool(true);

    try {
      const data = await postAuth("/api/auth/create-school/", {
        school_name: schoolName.trim(),
        school_code: preferredSchoolCode.trim(),
        email: schoolEmail.trim(),
      });

      if (!data.success || !data.school) {
        throw new Error(parseErrorMessage(data, "School creation failed."));
      }

      const generatedCode = data.school.school_code || "";
      setSchoolCode(generatedCode);
      setSchoolSuccess(
        data.conflict_resolved
          ? `School created. Code adjusted to "${generatedCode}" to avoid conflict.`
          : `School created. Use "${generatedCode}" as your school code.`
      );
      setSchoolName("");
      setPreferredSchoolCode("");
      setSchoolEmail("");
      setShowCreateSchool(false);
    } catch (requestError) {
      setSchoolError(requestError.message || "School creation failed.");
    } finally {
      setIsCreatingSchool(false);
    }
  };

  const handleLogin = async (credentials) => {
    const payload = {
      email: credentials.email.trim(),
      password: credentials.password,
      school_code: credentials.school_code?.trim() || "",
    };

    let response;
    try {
      response = await fetch(`${API_BASE_URL}/api/auth/login/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } catch (networkError) {
      throw new Error("Unable to reach the server.");
    }

    let data = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }
    if (!response.ok || !data?.success) {
      const reason =
        data?.error ||
        data?.message ||
        data?.detail ||
        data?.non_field_errors?.join?.(" ") ||
        "Login failed. Check your credentials.";
      throw new Error(reason);
    }

    if (data.requires_otp) {
      return {
        requiresOtp: true,
        email: payload.email,
        challenge: data.otp_challenge,
        purpose: data.otp_purpose || "login",
        expiresIn: data.otp_expires_in || 600,
        message: data.message || "Enter the OTP sent to your email.",
        user: data.user,
      };
    }

    const session = {
      user: data.user,
      access: data.access,
      refresh: data.refresh,
      school_code: data.school_code || payload.school_code || "",
      redirectUrl: data.redirect_url || "/dashboard/",
      requiresVerification: Boolean(data.requires_verification),
      signedInAt: new Date().toISOString(),
    };

    return session;
  };

  const handleSignIn = async (event) => {
    event.preventDefault();
    setError("");
    setSuccessMessage("");
    setSchoolError("");
    setIsSubmitting(true);

    try {
      const session = await handleLogin({
        email: email.trim(),
        password,
        school_code: schoolCode.trim(),
      });

      if (session.requiresOtp) {
        setOtpEmail(session.email);
        setOtpChallenge(session.challenge);
        setOtpPurpose(session.purpose);
        setOtpExpiresIn(session.expiresIn);
        setOtpCode("");
        setMode("otp");
        setSuccessMessage(session.message);
        return;
      }

      clearSession();
      if (rememberMe) {
        window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
      } else {
        window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
      }

      if (typeof onAuthenticated === "function") {
        onAuthenticated(session);
        return;
      }

      setSignedInUser(session);
      setPassword("");
      setSuccessMessage("Sign in successful.");
    } catch (requestError) {
      setSignedInUser(null);
      setError(requestError.message || "Sign in failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSignUp = async (event) => {
    event.preventDefault();
    setError("");
    setSuccessMessage("");
    setSchoolError("");
    setIsSubmitting(true);

    try {
      const payload = {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: signupEmail.trim(),
        password: signupPassword,
        confirm_password: confirmPassword,
        role: DEFAULT_SIGNUP_ROLE,
        phone: phone.trim(),
        school_code: schoolCode.trim(),
      };

      const data = await postAuth("/api/auth/register/", payload);

      if (!data.success) {
        throw new Error(parseErrorMessage(data, "Sign up failed."));
      }

      if (data.requires_otp) {
        setOtpEmail(signupEmail.trim());
        setOtpChallenge(data.otp_challenge);
        setOtpPurpose(data.otp_purpose || "signup");
        setOtpExpiresIn(data.otp_expires_in || 600);
        setOtpCode("");
        setMode("otp");
        setSuccessMessage(data.message || "Enter the OTP sent to your email.");
      } else {
        setSuccessMessage(data.message || "Account created successfully. You can sign in now.");
        setMode("signin");
      }
      setEmail(signupEmail.trim());
      setPassword("");
      setShowPassword(false);
      setShowSignupPassword(false);
      setShowConfirmPassword(false);
      setSignupPassword("");
      setConfirmPassword("");
    } catch (requestError) {
      setError(requestError.message || "Sign up failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const completeSession = (data) => {
    const session = {
      user: data.user,
      access: data.access,
      refresh: data.refresh,
      school_code: data.school_code || schoolCode.trim() || "",
      redirectUrl: data.redirect_url || "/dashboard/",
      requiresVerification: false,
      signedInAt: new Date().toISOString(),
    };
    clearSession();
    if (rememberMe) {
      window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    } else {
      window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
    }
    if (typeof onAuthenticated === "function") {
      onAuthenticated(session);
      return;
    }
    setSignedInUser(session);
  };

  const handleVerifyOtp = async (event) => {
    event.preventDefault();
    setError("");
    setSuccessMessage("");
    setIsSubmitting(true);
    try {
      const data = await postAuth("/api/auth/admin/verify-otp/", {
        email: otpEmail,
        code: otpCode.trim(),
        challenge: otpChallenge,
      });
      if (!data.success || !data.access) {
        throw new Error(parseErrorMessage(data, "OTP verification failed."));
      }
      setOtpCode("");
      setSuccessMessage(data.message || "Admin verification successful.");
      completeSession(data);
    } catch (requestError) {
      setError(requestError.message || "OTP verification failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResendOtp = async () => {
    if (!otpEmail || isResendingOtp) return;
    setError("");
    setSuccessMessage("");
    setIsResendingOtp(true);
    try {
      const data = await postAuth("/api/auth/admin/resend-otp/", {
        email: otpEmail,
        challenge: otpChallenge,
      });
      setOtpChallenge(data.otp_challenge || otpChallenge);
      setOtpPurpose(data.otp_purpose || otpPurpose);
      setOtpExpiresIn(data.otp_expires_in || 600);
      setOtpCode("");
      setSuccessMessage(data.message || "A new OTP code has been sent.");
    } catch (requestError) {
      setError(requestError.message || "Could not resend OTP.");
    } finally {
      setIsResendingOtp(false);
    }
  };

  const handleForgotPassword = async (event) => {
    event.preventDefault();
    setError("");
    setSuccessMessage("");
    setIsSubmitting(true);
    try {
      const data = await postAuth("/api/auth/password-reset/", {
        email: forgotEmail.trim(),
      });
      setSuccessMessage(data.message || "If that account exists, a reset link has been sent.");
    } catch (requestError) {
      setError(requestError.message || "Could not send reset email.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResetPassword = async (event) => {
    event.preventDefault();
    setError("");
    setSuccessMessage("");
    setIsSubmitting(true);
    try {
      const data = await postAuth("/api/auth/password-reset/confirm/", {
        token: resetToken.trim(),
        password: resetPassword,
        confirm_password: resetConfirmPassword,
      });
      setResetPassword("");
      setResetConfirmPassword("");
      setPassword("");
      setMode("signin");
      setShowCreateSchool(false);
      setSchoolError("");
      setSchoolSuccess("");
      setSuccessMessage(data.message || "Password reset successful. You can sign in now.");
      window.history.replaceState({}, "", "/signin");
    } catch (requestError) {
      setError(requestError.message || "Password reset failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSignOut = () => {
    clearSession();
    setSignedInUser(null);
    setSuccessMessage("");
    setError("");
    setSchoolError("");
    setSchoolSuccess("");
  };

  const schoolCreationPanel = showCreateSchool ? (
    <div className="create-school-panel">
      <label htmlFor="school-name">School name</label>
      <div className="input-wrap">
        <span className="input-icon">N</span>
        <input
          id="school-name"
          type="text"
          value={schoolName}
          onChange={(event) => setSchoolName(event.target.value)}
          placeholder="Blue Ridge Academy"
        />
      </div>

      <label htmlFor="preferred-school-code">Preferred code </label>
      <div className="input-wrap">
        <span className="input-icon">C</span>
        <input
          id="preferred-school-code"
          type="text"
          value={preferredSchoolCode}
          onChange={(event) => setPreferredSchoolCode(event.target.value)}
          placeholder="blue_ridge"
        />
      </div>

      <label htmlFor="school-email">School email </label>
      <div className="input-wrap">
        <span className="input-icon">@</span>
        <input
          id="school-email"
          type="email"
          value={schoolEmail}
          onChange={(event) => setSchoolEmail(event.target.value)}
          placeholder="office@school.edu"
        />
      </div>

      {schoolError ? <p className="error-text">{schoolError}</p> : null}

      <button
        type="button"
        className="create-school-submit"
        disabled={!canCreateSchool || isCreatingSchool}
        onClick={handleCreateSchool}
      >
        {isCreatingSchool ? "Creating school..." : "Create school now"}
      </button>
    </div>
  ) : null;

  return (
    <main className={`signup-page ${theme === "light" ? "theme-light" : ""}`}>
      <section className="signup-shell">
        <aside className="art-panel" aria-hidden="true">
          <div className="disc disc-one" />
          <div className="disc disc-two" />
          <div className="disc disc-three" />
          <div className="glow glow-one" />
          <div className="glow glow-two" />
        </aside>

        <section className="form-panel">
          <div className="form-panel-controls">
            <button
              type="button"
              className="back-home-button"
              onClick={() => {
                if (typeof onBack === "function") {
                  onBack();
                } else {
                  window.location.href = "/";
                }
              }}
              aria-label="Back to home"
              title="Back to home"
            >
              ←
            </button>
            <button
              type="button"
              className="theme-button"
              onClick={() => setTheme((previous) => (previous === "dark" ? "light" : "dark"))}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
              title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            >
              <ThemeIcon theme={theme} />
            </button>
          </div>

          <div className="form-inner">
            <div className="form-icon" aria-hidden="true">
              <SchoolIcon />
            </div>

            <h1 className="typing-title">
              {typedTitle}
              <span className="caret">|</span>
            </h1>

            {!signedInUser ? (
              <>
                <div className="mode-toggle" role="tablist" aria-label="Authentication mode">
                  <button
                    type="button"
                    className={`mode-button ${mode === "signin" ? "active" : ""}`}
                    onClick={() => {
                      switchMode("signin");
                    }}
                  >
                    Sign in
                  </button>
                  <button
                    type="button"
                    className={`mode-button ${mode === "signup" ? "active" : ""}`}
                    onClick={() => {
                      switchMode("signup");
                    }}
                  >
                    Sign up
                  </button>
                </div>

                {mode === "forgot" ? (
                  <form className="signup-form" onSubmit={handleForgotPassword} noValidate>
                    <p className="help-text">Enter your account email and we will send a secure reset link.</p>
                    <label htmlFor="forgot-email">Email address</label>
                    <div className="input-wrap">
                      <span className="input-icon">@</span>
                      <input
                        id="forgot-email"
                        type="email"
                        value={forgotEmail}
                        onChange={(event) => setForgotEmail(event.target.value)}
                        placeholder="you@school.edu"
                        autoComplete="email"
                        required
                      />
                    </div>
                    {error ? <p className="error-text">{error}</p> : null}
                    {successMessage ? <p className="success-text">{successMessage}</p> : null}
                    <button type="submit" className="signup-button" disabled={!canRequestReset || isSubmitting}>
                      {isSubmitting ? "Sending reset link..." : "Send reset link"}
                    </button>
                    <button type="button" className="create-school-trigger" onClick={() => switchMode("signin")}>
                      Back to sign in
                    </button>
                  </form>
                ) : mode === "reset" ? (
                  <form className="signup-form" onSubmit={handleResetPassword} noValidate>
                    <label htmlFor="reset-token">Reset token</label>
                    <div className="input-wrap">
                      <span className="input-icon">T</span>
                      <input
                        id="reset-token"
                        type="text"
                        value={resetToken}
                        onChange={(event) => setResetToken(event.target.value)}
                        placeholder="Paste reset token"
                        autoComplete="off"
                        required
                      />
                    </div>
                    <label htmlFor="reset-password">New password</label>
                    <div className="input-wrap password-wrap">
                      <span className="input-icon">#</span>
                      <input
                        id="reset-password"
                        type={showResetPassword ? "text" : "password"}
                        value={resetPassword}
                        onChange={(event) => setResetPassword(event.target.value)}
                        placeholder="Minimum 8 characters"
                        autoComplete="new-password"
                        required
                      />
                      <button
                        type="button"
                        className="password-toggle"
                        onClick={() => setShowResetPassword((previous) => !previous)}
                        aria-label={showResetPassword ? "Hide password" : "Show password"}
                      >
                        {showResetPassword ? "Hide" : "Show"}
                      </button>
                    </div>
                    <label htmlFor="reset-confirm-password">Confirm password</label>
                    <div className="input-wrap password-wrap">
                      <span className="input-icon">#</span>
                      <input
                        id="reset-confirm-password"
                        type={showResetConfirmPassword ? "text" : "password"}
                        value={resetConfirmPassword}
                        onChange={(event) => setResetConfirmPassword(event.target.value)}
                        placeholder="Re-enter password"
                        autoComplete="new-password"
                        required
                      />
                      <button
                        type="button"
                        className="password-toggle"
                        onClick={() => setShowResetConfirmPassword((previous) => !previous)}
                        aria-label={showResetConfirmPassword ? "Hide password" : "Show password"}
                      >
                        {showResetConfirmPassword ? "Hide" : "Show"}
                      </button>
                    </div>
                    {resetPassword && resetConfirmPassword && resetPassword !== resetConfirmPassword ? (
                      <p className="error-text">Passwords do not match.</p>
                    ) : null}
                    {error ? <p className="error-text">{error}</p> : null}
                    {successMessage ? <p className="success-text">{successMessage}</p> : null}
                    <button type="submit" className="signup-button" disabled={!canResetPassword || isSubmitting}>
                      {isSubmitting ? "Updating password..." : "Update password"}
                    </button>
                    <button type="button" className="create-school-trigger" onClick={() => switchMode("signin")}>
                      Back to sign in
                    </button>
                  </form>
                ) : mode === "otp" ? (
                  <form className="signup-form otp-form" onSubmit={handleVerifyOtp} noValidate>
                    <p className="success-text">
                      We sent a 6-digit admin verification code to <strong>{otpEmail}</strong>.
                    </p>
                    <label htmlFor="admin-otp">Verification code</label>
                    <div className="input-wrap">
                      <span className="input-icon">#</span>
                      <input
                        id="admin-otp"
                        type="text"
                        inputMode="numeric"
                        pattern="[0-9]{6}"
                        maxLength={6}
                        value={otpCode}
                        onChange={(event) => setOtpCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                        placeholder="000000"
                        autoComplete="one-time-code"
                        required
                      />
                    </div>
                    <p className="help-text">
                      Code expires in about {Math.max(Math.ceil(Number(otpExpiresIn || 0) / 60), 1)} minutes. After too many wrong attempts, the account will lock.
                    </p>
                    {error ? <p className="error-text">{error}</p> : null}
                    {successMessage ? <p className="success-text">{successMessage}</p> : null}
                    <button type="submit" className="signup-button" disabled={otpCode.length !== 6 || isSubmitting}>
                      {isSubmitting ? "Verifying..." : otpPurpose === "signup" ? "Verify and activate" : "Verify and sign in"}
                    </button>
                    <button type="button" className="create-school-trigger" disabled={isResendingOtp} onClick={handleResendOtp}>
                      {isResendingOtp ? "Sending..." : "Resend OTP"}
                    </button>
                    <button
                      type="button"
                      className="create-school-trigger"
                      onClick={() => {
                        switchMode("signin");
                        setOtpCode("");
                      }}
                    >
                      Back to sign in
                    </button>
                  </form>
                ) : mode === "signin" ? (
                  <form className="signup-form" onSubmit={handleSignIn} noValidate>
                    <label htmlFor="signin-email">Email address</label>
                    <div className="input-wrap">
                      <span className="input-icon">@</span>
                      <input
                        id="signin-email"
                        type="email"
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                        placeholder="you@school.edu"
                        autoComplete="email"
                        required
                      />
                    </div>

                    <label htmlFor="signin-password">Password</label>
                    <div className="input-wrap password-wrap">
                      <span className="input-icon">#</span>
                      <input
                        id="signin-password"
                        type={showPassword ? "text" : "password"}
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                        placeholder="Enter your password"
                        autoComplete="current-password"
                        required
                      />
                      <button
                        type="button"
                        className="password-toggle"
                        onClick={() => setShowPassword((previous) => !previous)}
                        aria-label={showPassword ? "Hide password" : "Show password"}
                      >
                        {showPassword ? "Hide" : "Show"}
                      </button>
                    </div>

                    <label htmlFor="signin-school-code">School code </label>
                    <div className="input-wrap">
                      <span className="input-icon">S</span>
                      <input
                        id="signin-school-code"
                        type="text"
                        value={schoolCode}
                        onChange={(event) => setSchoolCode(event.target.value)}
                        placeholder="school schema code"
                      />
                    </div>

                    <label className="remember-row" htmlFor="remember-me">
                      <input
                        id="remember-me"
                        type="checkbox"
                        checked={rememberMe}
                        onChange={(event) => setRememberMe(event.target.checked)}
                      />
                      Keep me signed in on this device
                    </label>

                    <button type="button" className="forgot-password-link" onClick={() => {
                      setForgotEmail(email.trim());
                      switchMode("forgot");
                    }}>
                      Forgot password?
                    </button>

                    {error ? <p className="error-text">{error}</p> : null}
                    {successMessage ? <p className="success-text">{successMessage}</p> : null}

                    <button type="submit" className="signup-button" disabled={!canSignIn || isSubmitting}>
                      {isSubmitting ? "Signing in..." : "Sign in"}
                    </button>
                  </form>
                ) : (
                  <form className="signup-form" onSubmit={handleSignUp} noValidate>
                    <label htmlFor="first-name">First name</label>
                    <div className="input-wrap">
                      <span className="input-icon">F</span>
                      <input
                        id="first-name"
                        type="text"
                        value={firstName}
                        onChange={(event) => setFirstName(event.target.value)}
                        placeholder="First name"
                        required
                      />
                    </div>

                    <label htmlFor="last-name">Last name</label>
                    <div className="input-wrap">
                      <span className="input-icon">L</span>
                      <input
                        id="last-name"
                        type="text"
                        value={lastName}
                        onChange={(event) => setLastName(event.target.value)}
                        placeholder="Last name"
                        required
                      />
                    </div>

                    <label htmlFor="signup-email">Email</label>
                    <div className="input-wrap">
                      <span className="input-icon">@</span>
                      <input
                        id="signup-email"
                        type="email"
                        value={signupEmail}
                        onChange={(event) => setSignupEmail(event.target.value)}
                        placeholder="you@school.edu"
                        autoComplete="email"
                        required
                      />
                    </div>

                    <label htmlFor="signup-password">Password</label>
                    <div className="input-wrap password-wrap">
                      <span className="input-icon">#</span>
                      <input
                        id="signup-password"
                        type={showSignupPassword ? "text" : "password"}
                        value={signupPassword}
                        onChange={(event) => setSignupPassword(event.target.value)}
                        placeholder="Minimum 8 chars, mixed case + number"
                        autoComplete="new-password"
                        required
                      />
                      <button
                        type="button"
                        className="password-toggle"
                        onClick={() => setShowSignupPassword((previous) => !previous)}
                        aria-label={showSignupPassword ? "Hide password" : "Show password"}
                      >
                        {showSignupPassword ? "Hide" : "Show"}
                      </button>
                    </div>

                    <label htmlFor="confirm-password">Confirm password</label>
                    <div className="input-wrap password-wrap">
                      <span className="input-icon">#</span>
                      <input
                        id="confirm-password"
                        type={showConfirmPassword ? "text" : "password"}
                        value={confirmPassword}
                        onChange={(event) => setConfirmPassword(event.target.value)}
                        placeholder="Re-enter password"
                        autoComplete="new-password"
                        required
                      />
                      <button
                        type="button"
                        className="password-toggle"
                        onClick={() => setShowConfirmPassword((previous) => !previous)}
                        aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                      >
                        {showConfirmPassword ? "Hide" : "Show"}
                      </button>
                    </div>

                    <label htmlFor="signup-phone">Phone </label>
                    <div className="input-wrap">
                      <span className="input-icon">P</span>
                      <input
                        id="signup-phone"
                        type="text"
                        value={phone}
                        onChange={(event) => setPhone(event.target.value)}
                        placeholder="+1234567890"
                      />
                    </div>

                    <label htmlFor="signup-school-code">School code </label>
                    <div className="input-wrap">
                      <span className="input-icon">S</span>
                      <input
                        id="signup-school-code"
                        type="text"
                        value={schoolCode}
                        onChange={(event) => setSchoolCode(event.target.value)}
                        placeholder="school schema code"
                      />
                    </div>

                    <button
                      type="button"
                      className="create-school-trigger"
                      onClick={() => {
                        setShowCreateSchool((previous) => !previous);
                        setSchoolError("");
                        setSchoolSuccess("");
                      }}
                    >
                      <CreateSchoolIcon />
                      {showCreateSchool ? "Close school creator" : "Create school"}
                    </button>

                    {schoolCreationPanel}
                    {schoolSuccess ? <p className="success-text">{schoolSuccess}</p> : null}

                    {error ? <p className="error-text">{error}</p> : null}
                    {successMessage ? <p className="success-text">{successMessage}</p> : null}

                    <button type="submit" className="signup-button" disabled={!canSignUp || isSubmitting}>
                      {isSubmitting ? "Creating account..." : "Create account"}
                    </button>
                  </form>
                )}
              </>
            ) : (
              <div className="success-box">
                <h2>Welcome, {signedInUser.user?.full_name || signedInUser.user?.email}</h2>
                <p>
                  Signed in as <strong>{signedInUser.user?.role}</strong>.
                </p>
                <p>{signedInUser.user?.email}</p>
                {signedInUser.requiresVerification ? (
                  <p>Please verify your email before full access is granted.</p>
                ) : null}
                <button type="button" className="signup-button" onClick={handleSignOut}>
                  Sign out
                </button>
              </div>
            )}
          </div>
        </section>
      </section>
    </main>
  );
}

export default Signin;
