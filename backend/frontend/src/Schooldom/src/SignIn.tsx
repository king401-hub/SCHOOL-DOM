import { useEffect, useMemo, useState } from "react";

// ============================================
// TYPES
// ============================================
interface SigninProps {
  onAuthenticated?: (session: any) => void;
  onBack?: () => void;
  initialMode?: "signin" | "signup";
}

interface SessionData {
  user: any;
  access: any;
  refresh: any;
  school: any;
  school_code: string;
  redirectUrl: string;
  requiresVerification: boolean;
  signedInAt: string;
}

interface OtpResponse {
  requiresOtp: boolean;
  email: string;
  challenge: string;
  purpose: string;
  expiresIn: number;
  debugCode: string;
  message: string;
  user: any;
}

type LoginResponse = SessionData | OtpResponse;

// ============================================
// CONSTANTS
// ============================================
const SESSION_KEY = "schooldom.session";
const LEGACY_SESSION_KEY = "educonnect.session";
const DEFAULT_SIGNUP_ROLE = "school_admin";
const TERMS_OPENED_KEY = "schooldom.terms_opened";
const SIGNUP_ROLES = [
  { value: "school_admin", title: "School Admin", label: "School Admin" },
  { value: "school_superadmin", title: "Proprietor/Director", label: "Proprietor/Director" },
  { value: "student", title: "Student", label: "Student (Non-K12 schools only)" },
];

// Fix for import.meta.env - use Vite's import.meta.env with type assertion
const API_BASE_URL = (() => {
  const raw = (import.meta as any).env?.VITE_API_BASE_URL ?? "";
  if (!raw) return ""; // use relative /api/... calls
  const trimmed = raw.replace(/\/+$/, "");
  const withoutApi = trimmed.endsWith("/api") ? trimmed.slice(0, -4) : trimmed;
  if (withoutApi.startsWith("http://") || withoutApi.startsWith("https://")) {
    return withoutApi;
  }
  return `${window.location.protocol}//${window.location.host}${withoutApi.startsWith("/") ? withoutApi : `/${withoutApi}`}`;
})();

// ============================================
// ICON COMPONENTS
// ============================================
function ThemeIcon({ theme }: { theme: string }) {
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

// ============================================
// UTILITY FUNCTIONS
// ============================================
function parseErrorMessage(payload: any, fallback: string): string {
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

async function postAuth(path: string, payload: any) {
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

// Type guard to check if response is OtpResponse
function isOtpResponse(response: LoginResponse): response is OtpResponse {
  return (response as OtpResponse).requiresOtp === true;
}

// ============================================
// MAIN SIGNIN COMPONENT
// ============================================
export default function Signin({ onAuthenticated, onBack, initialMode = "signin" }: SigninProps) {
  const [theme, setTheme] = useState("light");
  const [mode, setMode] = useState(() => {
    const path = window.location.pathname;
    const query = new URLSearchParams(window.location.search);
    if (path === "/forgot-password") return "forgot";
    if (query.get("mode") === "signup") return "signup";
    return initialMode || "signin";
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
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [termsOpened, setTermsOpened] = useState(() => window.localStorage.getItem(TERMS_OPENED_KEY) === "true");
  const [adminRoleTitle, setAdminRoleTitle] = useState("School Admin");
  const [phone, setPhone] = useState("");
  const [schoolCode, setSchoolCode] = useState("");
  const [guardianName, setGuardianName] = useState("");
  const [guardianPhone, setGuardianPhone] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpEmail, setOtpEmail] = useState("");
  const [otpChallenge, setOtpChallenge] = useState("");
  const [otpPurpose, setOtpPurpose] = useState("");
  const [otpExpiresIn, setOtpExpiresIn] = useState(0);
  const [otpDebugCode, setOtpDebugCode] = useState("");
  const [isResendingOtp, setIsResendingOtp] = useState(false);
  const [forgotEmail, setForgotEmail] = useState("");
  const [resetOtpCode, setResetOtpCode] = useState("");
  const [resetPassword, setResetPassword] = useState("");
  const [resetConfirmPassword, setResetConfirmPassword] = useState("");
  const [showResetPassword, setShowResetPassword] = useState(false);
  const [showResetConfirmPassword, setShowResetConfirmPassword] = useState(false);
  const [isResendingReset, setIsResendingReset] = useState(false);

  const [showTermsModal, setShowTermsModal] = useState(false);
  const [showCreateSchool, setShowCreateSchool] = useState(false);
  const [schoolName, setSchoolName] = useState("");
  const [preferredSchoolCode, setPreferredSchoolCode] = useState("");
  const [schoolEmail, setSchoolEmail] = useState("");
  const [schoolType, setSchoolType] = useState("k12");
  const [isCreatingSchool, setIsCreatingSchool] = useState(false);
  const [schoolError, setSchoolError] = useState("");
  const [schoolSuccess, setSchoolSuccess] = useState("");

  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [signedInUser, setSignedInUser] = useState<any>(null);
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
  const selectedSignupRole = useMemo(
    () => SIGNUP_ROLES.find((item) => item.title === adminRoleTitle) || SIGNUP_ROLES[0],
    [adminRoleTitle]
  );
  const isStudentSignup = selectedSignupRole.value === "student";

  const canSignUp = useMemo(() => {
    if (
      firstName.trim().length === 0 ||
      lastName.trim().length === 0 ||
      signupEmail.trim().length === 0 ||
      signupPassword.length === 0 ||
      confirmPassword.length === 0 ||
      !termsAccepted
    ) {
      return false;
    }

    if (schoolCode.trim().length === 0) {
      return false;
    }

    if (isStudentSignup && guardianName.trim().length === 0) {
      return false;
    }

    if (signupPassword !== confirmPassword) {
      return false;
    }

    return true;
  }, [
    confirmPassword,
    firstName,
    guardianName,
    isStudentSignup,
    lastName,
    schoolCode,
    signupEmail,
    signupPassword,
    termsAccepted,
  ]);

  const canCreateSchool = useMemo(() => schoolName.trim().length >= 3, [schoolName]);
  const canRequestReset = useMemo(() => forgotEmail.trim().length > 0, [forgotEmail]);
  const canResetPassword = useMemo(
    () => resetOtpCode.trim().length === 6 && resetPassword.length >= 8 && resetPassword === resetConfirmPassword,
    [resetConfirmPassword, resetOtpCode, resetPassword]
  );

  const clearSession = () => {
    window.localStorage.removeItem(SESSION_KEY);
    window.sessionStorage.removeItem(SESSION_KEY);
    window.localStorage.removeItem(LEGACY_SESSION_KEY);
    window.sessionStorage.removeItem(LEGACY_SESSION_KEY);
    window.localStorage.removeItem("access_token");
    window.localStorage.removeItem("refresh_token");
  };

  const switchMode = (nextMode: string) => {
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
        school_type: schoolType,
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
      setSchoolType("k12");
      setShowCreateSchool(false);
    } catch (requestError: any) {
      setSchoolError(requestError.message || "School creation failed.");
    } finally {
      setIsCreatingSchool(false);
    }
  };

  const handleLogin = async (credentials: { email: string; password: string; school_code?: string }): Promise<LoginResponse> => {
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
        debugCode: data.debug_otp || "",
        message: data.message || "Enter the OTP sent to your email.",
        user: data.user,
      };
    }

    const session: SessionData = {
      user: data.user,
      access: data.access,
      refresh: data.refresh,
      school: data.school || null,
      school_code: data.school_code || payload.school_code || "",
      redirectUrl: data.redirect_url || "/dashboard/",
      requiresVerification: Boolean(data.requires_verification),
      signedInAt: new Date().toISOString(),
    };

    return session;
  };

  const handleSignIn = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccessMessage("");
    setSchoolError("");
    setIsSubmitting(true);

    try {
      const response = await handleLogin({
        email: email.trim(),
        password,
        school_code: schoolCode.trim(),
      });

      if (isOtpResponse(response)) {
        setOtpEmail(response.email);
        setOtpChallenge(response.challenge);
        setOtpPurpose(response.purpose);
        setOtpExpiresIn(response.expiresIn);
        setOtpDebugCode(response.debugCode || "");
        setOtpCode("");
        setMode("otp");
        setSuccessMessage(response.message);
        return;
      }

      // It's a SessionData
      const session = response as SessionData;
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
    } catch (requestError: any) {
      setSignedInUser(null);
      setError(requestError.message || "Sign in failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSignUp = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccessMessage("");
    setSchoolError("");
    setIsSubmitting(true);

    try {
      if (!termsAccepted) {
        throw new Error("Accept the terms and conditions before signing up.");
      }

      const payload = {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: signupEmail.trim(),
        password: signupPassword,
        confirm_password: confirmPassword,
        role: selectedSignupRole.value || DEFAULT_SIGNUP_ROLE,
        admin_title: isStudentSignup ? "" : adminRoleTitle,
        phone: phone.trim(),
        school_code: schoolCode.trim(),
        guardian_name: isStudentSignup ? guardianName.trim() : "",
        guardian_phone: isStudentSignup ? guardianPhone.trim() : "",
        terms_accepted: termsAccepted,
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
        setOtpDebugCode(data.debug_otp || "");
        setOtpCode("");
        setMode("otp");
        setSuccessMessage(data.message || "Enter the OTP sent to your email.");
      } else {
        completeSession(data);
      }
      setEmail(signupEmail.trim());
      setPassword("");
      setShowPassword(false);
      setShowSignupPassword(false);
      setShowConfirmPassword(false);
      setSignupPassword("");
      setConfirmPassword("");
      setTermsAccepted(false);
      setTermsOpened(false);
      window.localStorage.removeItem(TERMS_OPENED_KEY);
    } catch (requestError: any) {
      setError(requestError.message || "Sign up failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const completeSession = (data: any) => {
    const session: SessionData = {
      user: data.user,
      access: data.access,
      refresh: data.refresh,
      school: data.school || null,
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

  const handleVerifyOtp = async (event: React.FormEvent) => {
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
    } catch (requestError: any) {
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
      setOtpDebugCode(data.debug_otp || "");
      setOtpCode("");
      setSuccessMessage(data.message || "A new OTP code has been sent.");
    } catch (requestError: any) {
      setError(requestError.message || "Could not resend OTP.");
    } finally {
      setIsResendingOtp(false);
    }
  };

  const handleForgotPassword = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccessMessage("");
    setIsSubmitting(true);
    try {
      const data = await postAuth("/api/auth/password-reset/", {
        email: forgotEmail.trim(),
      });
      if (data.requires_otp) {
        setOtpChallenge(data.otp_challenge);
        setOtpExpiresIn(data.otp_expires_in || 600);
        setOtpDebugCode(data.debug_otp || "");
        setResetOtpCode("");
        setMode("reset");
      }
      setSuccessMessage(data.message || "If that account exists, a 6-digit code has been sent.");
    } catch (requestError: any) {
      setError(requestError.message || "Could not send the reset code.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResendResetOtp = async () => {
    if (!forgotEmail || isResendingReset) return;
    setError("");
    setSuccessMessage("");
    setIsResendingReset(true);
    try {
      const data = await postAuth("/api/auth/password-reset/resend/", {
        email: forgotEmail.trim(),
        challenge: otpChallenge,
      });
      setOtpChallenge(data.otp_challenge || otpChallenge);
      setOtpExpiresIn(data.otp_expires_in || 600);
      setOtpDebugCode(data.debug_otp || "");
      setResetOtpCode("");
      setSuccessMessage(data.message || "A new code has been sent.");
    } catch (requestError: any) {
      setError(requestError.message || "Could not resend the code.");
    } finally {
      setIsResendingReset(false);
    }
  };

  const handleResetPassword = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccessMessage("");
    setIsSubmitting(true);
    try {
      const data = await postAuth("/api/auth/password-reset/confirm/", {
        email: forgotEmail.trim(),
        code: resetOtpCode.trim(),
        challenge: otpChallenge,
        password: resetPassword,
        confirm_password: resetConfirmPassword,
      });
      setResetOtpCode("");
      setResetPassword("");
      setResetConfirmPassword("");
      setPassword("");
      setMode("signin");
      setShowCreateSchool(false);
      setSchoolError("");
      setSchoolSuccess("");
      setSuccessMessage(data.message || "Password reset successful. You can sign in now.");
    } catch (requestError: any) {
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

      <label htmlFor="preferred-school-code">Preferred code</label>
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

      <label htmlFor="school-email">School email</label>
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

      <label htmlFor="school-type">School term</label>
      <div className="input-wrap">
        <span className="input-icon">T</span>
        <select
          id="school-type"
          value={schoolType}
          onChange={(event) => setSchoolType(event.target.value)}
        >
          <option value="k12">K-12 school</option>
          <option value="non_k12">Non K-12 school (tutorials, colleges, polytechnics)</option>
        </select>
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
                </div>
                {mode === "forgot" ? (
                  <form className="signup-form" onSubmit={handleForgotPassword} noValidate>
                    <p className="help-text">Enter your account email and we will send a 6-digit code to reset your password.</p>
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
                      {isSubmitting ? "Sending code..." : "Send reset code"}
                    </button>
                    <button type="button" className="create-school-trigger" onClick={() => switchMode("signin")}>
                      Back to sign in
                    </button>
                  </form>
                ) : mode === "reset" ? (
                  <form className="signup-form" onSubmit={handleResetPassword} noValidate>
                    <p className="help-text">
                      We sent a 6-digit code to <strong>{forgotEmail}</strong>. Enter it below with your new password.
                    </p>
                    <label htmlFor="reset-otp-code">Verification code</label>
                    <div className="input-wrap">
                      <span className="input-icon">#</span>
                      <input
                        id="reset-otp-code"
                        type="text"
                        inputMode="numeric"
                        pattern="[0-9]{6}"
                        maxLength={6}
                        value={resetOtpCode}
                        onChange={(event) => setResetOtpCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                        placeholder="000000"
                        autoComplete="one-time-code"
                        required
                      />
                    </div>
                    <p className="help-text">
                      Code expires in about {Math.max(Math.ceil(Number(otpExpiresIn || 0) / 60), 1)} minutes.
                    </p>
                    {otpDebugCode ? (
                      <p className="success-text">
                        Local development code: <strong>{otpDebugCode}</strong>
                      </p>
                    ) : null}
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
                    <button type="button" className="create-school-trigger" disabled={isResendingReset} onClick={handleResendResetOtp}>
                      {isResendingReset ? "Sending..." : "Resend code"}
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
                    {otpDebugCode ? (
                      <p className="success-text">
                        Local development OTP: <strong>{otpDebugCode}</strong>
                      </p>
                    ) : null}
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
                        setOtpDebugCode("");
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

                    <label htmlFor="signin-school-code">School code</label>
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

                    <button type="button" className="create-school-trigger" onClick={() => {
                      setAdminRoleTitle("Student");
                      switchMode("signup");
                    }}>
                      New student? Create an account with your school code
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

                    <label htmlFor="signup-phone">Phone</label>
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

                    {isStudentSignup ? (
                      <>
                        <label htmlFor="admin-role-title">Role</label>
                        <div className="input-wrap" aria-live="polite">
                          <span className="input-icon">R</span>
                          <span id="admin-role-title" style={{ padding: "0.75rem 0" }}>
                            {selectedSignupRole.label}
                          </span>
                        </div>

                        <p className="success-text">
                          Student self-registration is only available for Non-K12 schools (vocational,
                          tertiary, and academy institutions). Enter your school's unique code below —
                          ask your school administrator if you don't have it.
                        </p>
                        <label htmlFor="student-school-code">School code</label>
                        <div className="input-wrap">
                          <span className="input-icon">S</span>
                          <input
                            id="student-school-code"
                            type="text"
                            value={schoolCode}
                            onChange={(event) => setSchoolCode(event.target.value)}
                            placeholder="school schema code"
                            required
                          />
                        </div>

                        <label htmlFor="guardian-name">Guardian name</label>
                        <div className="input-wrap">
                          <span className="input-icon">G</span>
                          <input
                            id="guardian-name"
                            type="text"
                            value={guardianName}
                            onChange={(event) => setGuardianName(event.target.value)}
                            placeholder="Parent or guardian's full name"
                            required
                          />
                        </div>

                        <label htmlFor="guardian-phone">Guardian phone (optional)</label>
                        <div className="input-wrap">
                          <span className="input-icon">P</span>
                          <input
                            id="guardian-phone"
                            type="text"
                            value={guardianPhone}
                            onChange={(event) => setGuardianPhone(event.target.value)}
                            placeholder="+1234567890"
                          />
                        </div>
                      </>
                    ) : (
                      <>
                        <p className="success-text">
                          School Admin accounts are for one school. Create or enter that school's code to continue.
                        </p>
                        <label htmlFor="signup-school-code">School code</label>
                        <div className="input-wrap">
                          <span className="input-icon">S</span>
                          <input
                            id="signup-school-code"
                            type="text"
                            value={schoolCode}
                            onChange={(event) => setSchoolCode(event.target.value)}
                            placeholder="school schema code"
                            required
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
                      </>
                    )}

                    <label className="terms-checkbox" htmlFor="terms-accepted">
                      <input
                        id="terms-accepted"
                        type="checkbox"
                        checked={termsAccepted}
                        onChange={(event) => {
                          if (event.target.checked && !termsOpened) {
                            setTermsAccepted(false);
                            setError("Read and accept.");
                            return;
                          }
                          setError("");
                          setTermsAccepted(event.target.checked);
                        }}
                        required
                      />
                      <span>
                        I have read and accept the SchoolDom{" "}
                        <a
                          href="#terms"
                          onClick={(e) => {
                            e.preventDefault();
                            setShowTermsModal(true);
                            setTermsOpened(true);
                            window.localStorage.setItem(TERMS_OPENED_KEY, "true");
                          }}
                        >
                          terms and conditions
                        </a>.
                      </span>
                    </label>

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
                <h2>Welcome, {signedInUser?.user?.full_name || signedInUser?.user?.email || "User"}</h2>
                <p>
                  Signed in as <strong>{signedInUser?.user?.role || "User"}</strong>.
                </p>
                <p>{signedInUser?.user?.email || ""}</p>
                {signedInUser?.requiresVerification ? (
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

      {showTermsModal && (
        <div
          className="terms-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="Terms and Conditions"
          onClick={(e) => { if (e.target === e.currentTarget) setShowTermsModal(false); }}
        >
          <div className="terms-modal">
            <div className="terms-modal-header">
              <h2>Terms &amp; Conditions</h2>
              <button
                type="button"
                className="terms-modal-close"
                onClick={() => setShowTermsModal(false)}
                aria-label="Close"
              >
                ×
              </button>
            </div>

            <div className="terms-modal-body">
              <p style={{ color: "#94a3b8", fontSize: "0.8rem", marginBottom: "1rem" }}>Effective Date: 2026 · Xcel Technologies Ltd</p>

              <h3>1. Introduction &amp; Agreement</h3>
              <p>These Terms govern your access to and use of the SchoolDom platform ("Platform"), including the website, web application, and mobile applications for school administrators, teachers, students, and parents. By creating an account or using the Platform, you confirm that you have read, understood, and agree to these Terms.</p>

              <h3>2. Definitions</h3>
              <p><strong>Platform:</strong> SchoolDom website, web app, and mobile apps.</p>
              <p><strong>User:</strong> Any individual or entity authorized to use the Platform — School Owner, Administrator, Teacher, Parent/Guardian, or Student.</p>
              <p><strong>Content:</strong> All data, files, results, documents, and information uploaded or stored on the Platform by Users.</p>

              <h3>3. Accounts &amp; Eligibility</h3>
              <p><strong>3.1 Eligibility</strong></p>
              <ul>
                <li>School Owners must be legal representatives with authority to contract.</li>
                <li>Administrators, Teachers, and Parents must be 18+ years old.</li>
                <li>Students may use the Platform only under supervision and with consent from the School Owner.</li>
              </ul>
              <p><strong>3.2 Account Security</strong></p>
              <p>You must provide accurate, current information and keep it updated. You are responsible for all activities under your account. Notify us immediately at <a href="mailto:enquiry@schooldom.academy">enquiry@schooldom.academy</a> if you suspect unauthorized access.</p>
              <p><strong>3.3 Acceptable Use</strong></p>
              <p>You must not: violate any Nigerian law or NDPR; impersonate any person or school; upload malware; attempt unauthorized access or data scraping; use bots without written permission; upload content that is defamatory, obscene, or harmful to minors. We may suspend or terminate accounts that violate this section.</p>

              <h3>4. Content &amp; Data Ownership</h3>
              <p>You own the Content you upload and are solely responsible for it. You grant Xcel Technologies a non-exclusive license to host, process, display, and backup your Content solely to provide and maintain SchoolDom. For NDPR/GDPR purposes, the School Owner is the Data Controller and Xcel Technologies is the Data Processor.</p>

              <h3>5. Intellectual Property</h3>
              <p>SchoolDom, including all code, design, logos, and features, is owned by Xcel Technologies Ltd. All rights reserved. We grant you a limited, non-exclusive, non-transferable license for your school's internal use only. You may not copy, modify, reverse engineer, or resell the Platform without written consent.</p>

              <h3>6. Fees, Payment &amp; Refunds</h3>
              <p><strong>6.1 Subscription:</strong> School Owners pay subscription fees billed annually/termly in advance. Current pricing is at schooldom.academy/pricing.</p>
              <p><strong>6.2 Payment Fees:</strong> Parents paying school fees through SchoolDom pay gateway charges set by our payment partners. Xcel Technologies does not receive these charges.</p>
              <p><strong>6.3 Refunds:</strong> We offer a free trial for new schools. After trial ends, all subscription fees are non-refundable except if we fail to provide core services for 7+ consecutive days due to our fault.</p>

              <h3>7. Service Availability &amp; Support</h3>
              <p>We aim for 99.5% monthly uptime, excluding scheduled maintenance. We'll notify School Administrators 48 hours before planned maintenance. Support via <a href="mailto:enquiry@schooldom.academy">enquiry@schooldom.academy</a>, 9am–5pm WAT Mon–Fri.</p>

              <h3>8. Suspension &amp; Termination</h3>
              <p><strong>By You:</strong> School Owners may terminate by emailing us. Access ends at the end of the paid period. You have 30 days to export your data.</p>
              <p><strong>By Us:</strong> We may suspend or terminate accounts for breach of Terms, non-payment, fraud, or illegal use.</p>

              <h3>9. Limitation of Liability</h3>
              <p>To the maximum extent allowed by Nigerian law, Xcel Technologies is not liable for indirect, incidental, or consequential damages. Our total liability for any claim is limited to amounts you paid us in the 12 months before the claim.</p>

              <h3>10. Disclaimer of Warranties</h3>
              <p>SchoolDom is provided "AS IS" and "AS AVAILABLE". We do not guarantee the Platform will be error-free or uninterrupted. We are not responsible for internet outages or third-party service failures.</p>

              <h3>11. Changes to Terms</h3>
              <p>We may update these Terms to reflect new features or legal changes. We'll post the updated version with a new Effective Date and notify School Administrators by email for material changes.</p>

              <h3>12. Governing Law &amp; Disputes</h3>
              <p>These Terms are governed by the laws of the Federal Republic of Nigeria. Disputes will first attempt amicable resolution for 30 days, then proceed to arbitration in Lagos under the Arbitration and Conciliation Act.</p>

              <h3>13. Contact Us</h3>
              <p>Xcel Technologies Ltd · <a href="mailto:enquiry@schooldom.academy">enquiry@schooldom.academy</a> · 256 Ikotun Road, Lagos.</p>
            </div>

            <div className="terms-modal-footer">
              <button
                type="button"
                className="terms-modal-decline"
                onClick={() => {
                  setTermsAccepted(false);
                  setShowTermsModal(false);
                }}
              >
                Decline
              </button>
              <button
                type="button"
                className="terms-modal-accept"
                onClick={() => {
                  setTermsAccepted(true);
                  setTermsOpened(true);
                  window.localStorage.setItem(TERMS_OPENED_KEY, "true");
                  setShowTermsModal(false);
                  setError("");
                }}
              >
                Accept &amp; Continue
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}