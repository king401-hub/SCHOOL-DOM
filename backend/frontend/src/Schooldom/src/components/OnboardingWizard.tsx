import React, { useMemo, useState } from 'react';
import { 
  X, Check, ChevronRight, School, Sparkles, User, Mail, Phone, 
  MapPin, Sliders, ShieldCheck, Cpu, RefreshCw, Layers, Award, Eye, EyeOff
} from 'lucide-react';

interface OnboardingWizardProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthenticated?: (session: any) => void;
}

const SESSION_KEY = "schooldom.session";
const LEGACY_SESSION_KEY = "educonnect.session";
const TERMS_OPENED_KEY = "schooldom.terms_opened";
const DEFAULT_SIGNUP_ROLE = "school_admin";
const ADMIN_SIGNUP_ROLES = [
  { value: "school_admin", title: "School Admin", label: "School Admin" },
  { value: "principal", title: "School Principal", label: "School Principal" },
  { value: "school_superadmin", title: "Proprietor/Director", label: "Proprietor/Director" },
];

const API_BASE_URL = (() => {
  const raw = (import.meta as any).env?.VITE_API_BASE_URL ?? "";
  if (!raw) return "";
  const trimmed = raw.replace(/\/+$/, "");
  const withoutApi = trimmed.endsWith("/api") ? trimmed.slice(0, -4) : trimmed;
  if (withoutApi.startsWith("http://") || withoutApi.startsWith("https://")) {
    return withoutApi;
  }
  return `${window.location.protocol}//${window.location.host}${withoutApi.startsWith("/") ? withoutApi : `/${withoutApi}`}`;
})();

function parseErrorMessage(payload: any, fallback: string): string {
  if (!payload) return fallback;
  if (typeof payload.message === "string" && payload.message.trim()) return payload.message;
  if (typeof payload.error === "string" && payload.error.trim()) return payload.error;
  if (payload.errors && typeof payload.errors === "object") {
    const entries = Object.entries(payload.errors);
    if (entries.length) {
      const [field, value] = entries[0];
      if (Array.isArray(value) && value.length) return `${field}: ${String(value[0])}`;
      if (typeof value === "string") return `${field}: ${value}`;
    }
  }
  if (payload.non_field_errors?.length) return payload.non_field_errors.join(" ");
  return fallback;
}

async function postAuth(path: string, payload: any) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error(`Unable to reach the server at ${API_BASE_URL || "this host"}.`);
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    throw new Error(parseErrorMessage(data, "Request failed. Please try again."));
  }

  return data;
}

function splitFullName(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return { firstName: "", lastName: "" };
  if (parts.length === 1) return { firstName: parts[0], lastName: "" };
  return { firstName: parts[0], lastName: parts.slice(1).join(" ") };
}

export default function OnboardingWizard({ isOpen, onClose, onAuthenticated }: OnboardingWizardProps) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState('');
  const [onboardSuccess, setOnboardSuccess] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [createdSchoolCode, setCreatedSchoolCode] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpEmail, setOtpEmail] = useState("");
  const [otpChallenge, setOtpChallenge] = useState("");
  const [otpPurpose, setOtpPurpose] = useState("");
  const [otpExpiresIn, setOtpExpiresIn] = useState(0);
  const [otpDebugCode, setOtpDebugCode] = useState("");
  const [isResendingOtp, setIsResendingOtp] = useState(false);

  // Form State
  const [schoolName, setSchoolName] = useState('');
  const [schoolType, setSchoolType] = useState<'k12' | 'non_k12'>('k12');
  const [preferredSchoolCode, setPreferredSchoolCode] = useState('');
  const [schoolEmail, setSchoolEmail] = useState('');
  const [isGroup, setIsGroup] = useState(false);
  const [locationState, setLocationState] = useState('Lagos State');
  const [authName, setAuthName] = useState('');
  const [authEmail, setAuthEmail] = useState('');
  const [authPhone, setAuthPhone] = useState('');
  const [adminRoleTitle, setAdminRoleTitle] = useState("School Admin");
  const [schoolGroupName, setSchoolGroupName] = useState('');
  const [signupPassword, setSignupPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showSignupPassword, setShowSignupPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [studentSize, setStudentSize] = useState(350);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [termsOpened, setTermsOpened] = useState(() => window.localStorage.getItem(TERMS_OPENED_KEY) === "true");
  const [showTermsModal, setShowTermsModal] = useState(false);
  const [legalConsent, setLegalConsent] = useState(false);
  
  // Integrations preferences
  const [modulesSelected, setModulesSelected] = useState({
    cbtOffline: true,
    financeGate: true,
    reportCards: true,
    biometrics: false,
    idBuilder: true
  });

  const selectedSignupRole = useMemo(
    () => ADMIN_SIGNUP_ROLES.find((item) => item.title === adminRoleTitle) || ADMIN_SIGNUP_ROLES[0],
    [adminRoleTitle]
  );
  const isSchoolSuperadminSignup = selectedSignupRole.value === "school_superadmin";
  const { firstName, lastName } = useMemo(() => splitFullName(authName), [authName]);
  const canContinueStep1 = schoolName.trim().length >= 3 && (
    isSchoolSuperadminSignup
      ? schoolGroupName.trim().length >= 3
      : preferredSchoolCode.trim().length >= 3
  );
  const canContinueStep2 =
    firstName.trim().length > 0 &&
    lastName.trim().length > 0 &&
    authEmail.trim().length > 0 &&
    authPhone.trim().length > 0 &&
    signupPassword.length >= 8 &&
    confirmPassword.length > 0 &&
    signupPassword === confirmPassword;
  const canSubmit = legalConsent && termsAccepted && canContinueStep1 && canContinueStep2 && !loading;

  if (!isOpen) return null;

  const toggleModule = (key: keyof typeof modulesSelected) => {
    setModulesSelected({
      ...modulesSelected,
      [key]: !modulesSelected[key]
    });
  };

  const handleNextStep = () => {
    setError("");
    if (step === 1 && !canContinueStep1) {
      setError(isSchoolSuperadminSignup ? "Enter a valid school group name." : "Enter school name and preferred school code.");
      return;
    }
    if (step === 2 && !canContinueStep2) {
      setError("Complete the account details. Passwords must match and the full name must include first and last name.");
      return;
    }
    setStep(prev => prev + 1);
  };

  const handlePrevStep = () => {
    setStep(prev => prev - 1);
  };

  const clearSession = () => {
    window.localStorage.removeItem(SESSION_KEY);
    window.sessionStorage.removeItem(SESSION_KEY);
    window.localStorage.removeItem(LEGACY_SESSION_KEY);
    window.sessionStorage.removeItem(LEGACY_SESSION_KEY);
    window.localStorage.removeItem("access_token");
    window.localStorage.removeItem("refresh_token");
  };

  const completeSession = (data: any) => {
    const session = {
      user: data.user,
      access: data.access,
      refresh: data.refresh,
      school: data.school || null,
      school_code: data.school_code || createdSchoolCode || "",
      redirectUrl: data.redirect_url || "/settings",
      requiresVerification: false,
      signedInAt: new Date().toISOString(),
    };
    clearSession();
    window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    if (typeof onAuthenticated === "function") {
      onAuthenticated(session);
    }
  };

  const resetWizard = () => {
    setOnboardSuccess(false);
    setStep(1);
    setSchoolName('');
    setPreferredSchoolCode('');
    setSchoolEmail('');
    setAuthName('');
    setAuthEmail('');
    setAuthPhone('');
    setSignupPassword('');
    setConfirmPassword('');
    setSchoolGroupName('');
    setCreatedSchoolCode('');
    setOtpCode('');
    setOtpEmail('');
    setOtpChallenge('');
    setOtpPurpose('');
    setOtpDebugCode('');
    setTermsAccepted(false);
    setLegalConsent(false);
    setError("");
    setSuccessMessage("");
  };

  const handleFinalSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) {
      setError(!termsAccepted ? "Read and accept the SchoolDom terms and conditions before signing up." : "Complete every required field before provisioning.");
      return;
    }

    setError("");
    setSuccessMessage("");
    setLoading(true);

    const stages = [
      "Creating school tenant and code...",
      "Registering administrative account...",
      "Linking account to Schooldom backend...",
      "Preparing verification workflow..."
    ];

    try {
      stages.forEach((msg, index) => {
        setTimeout(() => setLoadingStage(msg), index * 220);
      });

      let schoolCode = "";
      if (!isSchoolSuperadminSignup) {
        const schoolData = await postAuth("/api/auth/create-school/", {
          school_name: schoolName.trim(),
          school_code: preferredSchoolCode.trim(),
          email: schoolEmail.trim() || authEmail.trim(),
          phone: authPhone.trim(),
          address: locationState,
          school_type: schoolType,
        });

        if (!schoolData.success || !schoolData.school) {
          throw new Error(parseErrorMessage(schoolData, "School creation failed."));
        }

        schoolCode = schoolData.school.school_code || "";
        setCreatedSchoolCode(schoolCode);
      }

      const registerData = await postAuth("/api/auth/register/", {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: authEmail.trim(),
        password: signupPassword,
        confirm_password: confirmPassword,
        role: selectedSignupRole.value || DEFAULT_SIGNUP_ROLE,
        admin_title: adminRoleTitle,
        phone: authPhone.trim(),
        school_code: isSchoolSuperadminSignup ? "" : schoolCode,
        school_group_name: isSchoolSuperadminSignup ? schoolGroupName.trim() : "",
        terms_accepted: termsAccepted,
      });

      if (!registerData.success) {
        throw new Error(parseErrorMessage(registerData, "Sign up failed."));
      }

      localStorage.setItem('schooldom_onboarding_school_name', schoolName);
      window.dispatchEvent(new CustomEvent('schooldom_school_name_changed'));

      if (registerData.requires_otp) {
        setOtpEmail(authEmail.trim());
        setOtpChallenge(registerData.otp_challenge);
        setOtpPurpose(registerData.otp_purpose || "signup");
        setOtpExpiresIn(registerData.otp_expires_in || 600);
        setOtpDebugCode(registerData.debug_otp || "");
        setOtpCode("");
        setStep(4);
        setSuccessMessage(registerData.message || "Enter the OTP sent to your email.");
      } else {
        completeSession(registerData);
      }
    } catch (requestError: any) {
      setError(requestError.message || "School onboarding failed.");
    } finally {
      setLoading(false);
      setLoadingStage("");
    }
  };

  const handleVerifyOtp = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccessMessage("");
    setLoading(true);
    setLoadingStage("Verifying administrative OTP...");
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
      setOnboardSuccess(true);
      completeSession(data);
    } catch (requestError: any) {
      setError(requestError.message || "OTP verification failed.");
    } finally {
      setLoading(false);
      setLoadingStage("");
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

  const generatedRegId = `SD-SCH-${Math.floor(1000 + Math.random() * 9000)}`;

  return (<>
    <div className="fixed inset-0 z-100 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs text-left">
      <div className="relative w-full max-w-2xl bg-white text-slate-800 rounded-3xl overflow-hidden shadow-2xl border border-gray-100 flex flex-col max-h-[90vh]">
        
        {/* Header Ribbon Indicator */}
        <div className="bg-brand-600 text-white px-6 py-4 flex items-center justify-between relative">
          <div className="flex items-center gap-2.5">
            <School className="h-5.5 w-5.5 text-teal-brand-500" />
            <div>
              <h3 className="font-display font-bold text-base">Schooldom Enterprise Onboarding</h3>
              <p className="text-[10px] text-brand-100 font-mono">STEP {Math.min(step, 3)} OF 3 - REGISTRATION PROFILE</p>
            </div>
          </div>
          <button
            id="wizard-btn-close"
            onClick={onClose}
            className="p-1.5 hover:bg-white/10 rounded-lg cursor-pointer transition-colors text-white"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content body layout container */}
        <div className="p-6 sm:p-8 overflow-y-auto flex-1">
          {loading ? (
            /* Intermediary Installation progress loop */
            <div className="py-12 flex flex-col items-center justify-center text-center space-y-6">
              <RefreshCw className="h-12 w-12 text-brand-600 animate-spin" />
              <div className="space-y-2">
                <h4 className="font-display font-bold text-lg text-brand-950">Provisioning Schooldom</h4>
                <p className="text-xs text-gray-500 max-w-xs mx-auto">Please wait while we organize databases for your institution.</p>
              </div>
              <div className="px-5 py-2.5 rounded-xl bg-slate-50 border border-gray-150 inline-block text-xs font-semibold text-slate-600 font-mono animate-pulse">
                {loadingStage || "Connecting to core cloud routers..."}
              </div>
            </div>
          ) : onboardSuccess ? (
            /* Successful digitizing certificate of authenticity */
            <div className="space-y-6 animate-in zoom-in-95 duration-300">
              
              <div className="text-center space-y-2">
                <div className="h-12 w-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto text-xl font-bold">✓</div>
                <h4 className="font-display font-extrabold text-xl text-brand-950">Institution Successfully Onboarded!</h4>
                <p className="text-xs text-gray-500">Your school operations have been compiled on the Schooldom cluster.</p>
              </div>

              {/* Dynamic physical Certificate layout */}
              <div className="border border-brand-200/80 rounded-2xl p-6 bg-slate-50 relative overflow-hidden max-w-lg mx-auto shadow-sm">
                
                {/* Visual watermark */}
                <div className="absolute top-[30%] left-[50%] -translate-x-1/2 -translate-y-1/2 opacity-5 pointer-events-none">
                  <Award className="h-44 w-44 text-brand-950" />
                </div>

                <div className="text-center border-b border-brand-100 pb-4">
                  <span className="text-[9px] font-bold text-brand-600 bg-brand-50 border border-brand-200 px-2.5 py-0.5 rounded-full uppercase">
                    Certification of Digital Migration
                  </span>
                  <h5 className="font-display font-extrabold text-sm text-brand-950 uppercase mt-2">{schoolName || "ROYAL CLASSIC MODEL SCHOOL"}</h5>
                  <p className="text-[10px] text-gray-400 font-mono tracking-wider mt-0.5">REGISTERED CLOUD IDENTITY: {createdSchoolCode || generatedRegId}</p>
                </div>

                <div className="py-4 space-y-2.5 text-xs text-gray-600 border-b border-gray-100">
                  <div className="flex justify-between">
                    <span>Administrative Campus:</span>
                    <strong className="text-slate-800">{locationState}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span>Authorized Registrar:</span>
                    <strong className="text-slate-800">{authName} ({authEmail})</strong>
                  </div>
                  <div className="flex justify-between">
                    <span>Subscription Category:</span>
                    <strong className="text-sky-950 font-bold">{schoolType === 'k12' ? 'K12 Termly Contract' : 'Non-K12 Monthly Flex'}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span>Assigned Student Seats:</span>
                    <strong className="text-sky-950 font-mono font-bold">{studentSize} Enrolled</strong>
                  </div>
                </div>

                {/* Schooldom Credit Hub Prequalification Access */}
                <div className="mt-3 p-3 bg-emerald-50 border border-emerald-150 rounded-xl space-y-1">
                  <div className="flex items-center gap-1.5 text-emerald-800 font-bold">
                    <Sparkles className="h-4 w-4 text-emerald-600 animate-pulse shrink-0" />
                    <span>Special Credit Hub Offer (Prequalified)</span>
                  </div>
                  <p className="text-[10px] text-emerald-700 leading-normal">
                    Based on your onboarding scale of <strong className="text-emerald-950">{studentSize} student seats</strong>, your institution is provisionally prequalified for up to <strong className="text-emerald-950">₦{(studentSize * 7500).toLocaleString()}</strong> in school development &amp; hardware facilities loans from our verified financial partners (including EdFin MFB).
                  </p>
                  <p className="text-[8px] text-emerald-500/80 italic font-mono uppercase tracking-wide">
                    *Terms and Conditions Apply. subject to final portfolio risk review.
                  </p>
                </div>

                <div className="pt-3 text-[10px] text-slate-400 text-center leading-relaxed font-medium">
                  Approved by NUC & WAEC Digital Operations Registry. Welcome to the future of organized education.
                </div>

              </div>

              <div className="flex gap-3 justify-center">
                <button
                  id="btn-succ-close"
                  onClick={() => {
                    resetWizard();
                    onClose();
                  }}
                  className="px-6 py-2.5 rounded-xl text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 cursor-pointer"
                >
                  Conclude Setup Workspace
                </button>
              </div>

            </div>
          ) : (
            <form onSubmit={handleFinalSubmit} className="space-y-6">
              {step === 4 && (
                <div className="space-y-5 text-xs text-gray-600 animate-in fade-in duration-250">
                  <div>
                    <h4 className="font-display font-bold text-base text-brand-950 mb-1">Verify admin access</h4>
                    <p className="text-gray-400">We sent a 6-digit admin verification code to <strong>{otpEmail}</strong>.</p>
                  </div>

                  <div>
                    <label htmlFor="wizard-admin-otp" className="block font-bold mb-1.5 text-slate-700">Verification code</label>
                    <input
                      id="wizard-admin-otp"
                      type="text"
                      inputMode="numeric"
                      pattern="[0-9]{6}"
                      maxLength={6}
                      value={otpCode}
                      onChange={(event) => setOtpCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                      placeholder="000000"
                      autoComplete="one-time-code"
                      required
                      className="w-full border border-gray-200 rounded-xl px-4.5 py-3 text-sm focus:border-brand-500 bg-white"
                    />
                    <p className="text-[10px] text-gray-400 mt-2">
                      Code expires in about {Math.max(Math.ceil(Number(otpExpiresIn || 0) / 60), 1)} minutes.
                    </p>
                  </div>

                  {otpDebugCode ? <p className="text-[10px] text-emerald-600 font-bold">Local development OTP: {otpDebugCode}</p> : null}
                  {error ? <p className="text-[10px] text-rose-500 font-bold">{error}</p> : null}
                  {successMessage ? <p className="text-[10px] text-emerald-600 font-bold">{successMessage}</p> : null}

                  <div className="border-t border-gray-100 pt-5 flex items-center justify-between">
                    <button
                      type="button"
                      onClick={handleResendOtp}
                      disabled={isResendingOtp}
                      className="px-5 py-3 rounded-xl border border-gray-200 text-gray-700 hover:bg-slate-50 font-semibold cursor-pointer disabled:opacity-50"
                    >
                      {isResendingOtp ? "Sending..." : "Resend OTP"}
                    </button>
                    <button
                      type="button"
                      onClick={handleVerifyOtp}
                      disabled={otpCode.length !== 6 || loading}
                      className="px-7 py-3 rounded-xl font-bold text-white bg-brand-600 hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed shadow-md transition-all cursor-pointer"
                    >
                      {loading ? "Verifying..." : otpPurpose === "signup" ? "Verify and activate" : "Verify and sign in"}
                    </button>
                  </div>
                </div>
              )}
              
              {/* STEP 1: school characteristics */}
              {step === 1 && (
                <div className="space-y-5 text-xs text-gray-600 animate-in fade-in duration-200">
                  <div>
                    <h4 className="font-display font-bold text-base text-brand-950 mb-1">Tell us about your Institution</h4>
                    <p className="text-gray-400">Please provide verified physical parameters of the campus.</p>
                  </div>

                  <div className="space-y-4">
                    {/* Role selector — determines whether school code or group name is required */}
                    <div>
                      <label htmlFor="select-wizard-role" className="block font-bold mb-1.5 text-slate-700">Your Role:</label>
                      <select
                        id="select-wizard-role"
                        value={adminRoleTitle}
                        onChange={(e) => {
                          setAdminRoleTitle(e.target.value);
                          setPreferredSchoolCode('');
                          setSchoolGroupName('');
                          setError('');
                        }}
                        className="w-full border border-gray-200 rounded-xl px-4.5 py-3 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20 bg-white"
                      >
                        {ADMIN_SIGNUP_ROLES.map((r) => (
                          <option key={r.value} value={r.title}>{r.label}</option>
                        ))}
                      </select>
                      {isSchoolSuperadminSignup && (
                        <p className="text-[10px] text-brand-600 mt-1 font-medium">
                          Proprietor/Director manages multiple schools. You'll create individual school branches after signup.
                        </p>
                      )}
                    </div>

                    <div>
                      <label htmlFor="input-wizard-sch" className="block font-bold mb-1.5 text-slate-700">
                        {isSchoolSuperadminSignup ? 'School Group / Brand Name:' : 'School Name:'}
                      </label>
                      <input
                        id="input-wizard-sch"
                        type="text"
                        required
                        placeholder={isSchoolSuperadminSignup ? 'e.g. Xcel Group of Schools' : 'e.g. Royal Heights Academy'}
                        value={schoolName}
                        onChange={(e) => setSchoolName(e.target.value)}
                        className="w-full border border-gray-200 rounded-xl px-4.5 py-3 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20 bg-white"
                      />
                    </div>

                    {/* Superadmin: school group name. Others: preferred school code */}
                    {isSchoolSuperadminSignup ? (
                      <div>
                        <label htmlFor="input-wizard-group" className="block font-bold mb-1.5 text-slate-700">Group Display Name (for dashboard):</label>
                        <input
                          id="input-wizard-group"
                          type="text"
                          required
                          placeholder="e.g. Xcel Schools Group"
                          value={schoolGroupName}
                          onChange={(e) => setSchoolGroupName(e.target.value)}
                          className="w-full border border-gray-200 rounded-xl px-4.5 py-3 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20 bg-white"
                        />
                      </div>
                    ) : (
                      <div>
                        <label htmlFor="input-wizard-code" className="block font-bold mb-1.5 text-slate-700">Preferred School Code:</label>
                        <input
                          id="input-wizard-code"
                          type="text"
                          required
                          placeholder="e.g. royal_heights (no spaces)"
                          value={preferredSchoolCode}
                          onChange={(e) => setPreferredSchoolCode(e.target.value.toLowerCase().replace(/\s+/g, '_'))}
                          className="w-full border border-gray-200 rounded-xl px-4.5 py-3 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20 bg-white font-mono"
                        />
                        <p className="text-[10px] text-gray-400 mt-1">This becomes your school's unique identifier. Use lowercase letters and underscores only.</p>
                      </div>
                    )}

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label htmlFor="select-wizard-type" className="block font-bold mb-1.5 text-slate-700">Academic Structure:</label>
                        <select
                          id="select-wizard-type"
                          value={schoolType}
                          onChange={(e) => setSchoolType(e.target.value as any)}
                          className="w-full border border-gray-200 rounded-xl px-4.5 py-3 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20 bg-white focus:outline-hidden"
                        >
                          <option value="k12">K12 (Nursery / Primary / Secondary)</option>
                          <option value="non_k12">Non-K12 (Vocational / Continuing)</option>
                        </select>
                      </div>
                      <div>
                        <label htmlFor="select-wizard-loc" className="block font-bold mb-1.5 text-slate-700">Location Territory:</label>
                        <select
                          id="select-wizard-loc"
                          value={locationState}
                          onChange={(e) => setLocationState(e.target.value)}
                          className="w-full border border-gray-200 rounded-xl px-4.5 py-3 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20 bg-white"
                        >
                          <option value="Lagos State">Lagos State</option>
                          <option value="Oyo State">Oyo State</option>
                          <option value="Kaduna State">Kaduna State</option>
                          <option value="Rivers State">Rivers State</option>
                          <option value="Abuja FCT">Abuja FCT</option>
                          <option value="Kano State">Kano State</option>
                          <option value="Delta State">Delta State</option>
                          <option value="Enugu State">Enugu State</option>
                          <option value="Anambra State">Anambra State</option>
                          <option value="Cross River State">Cross River State</option>
                          <option value="Other State">Other State</option>
                        </select>
                      </div>
                    </div>

                    <div>
                      <label htmlFor="input-wizard-schemail" className="block font-bold mb-1.5 text-slate-700">School Official Email (optional):</label>
                      <input
                        id="input-wizard-schemail"
                        type="email"
                        placeholder="admin@royalheights.edu.ng"
                        value={schoolEmail}
                        onChange={(e) => setSchoolEmail(e.target.value)}
                        className="w-full border border-gray-200 rounded-xl px-4.5 py-3 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20 bg-white"
                      />
                    </div>

                    {/* Group of schools Toggle */}
                    <div className="p-4 bg-slate-50 rounded-2xl border border-gray-100 flex items-center justify-between">
                      <div className="space-y-1">
                        <span className="font-bold text-slate-700 block">Multi-campus group brand?</span>
                        <span className="text-[10px] text-gray-400">Enable to provision a central executive reporting dashboard.</span>
                      </div>
                      <input
                        id="checkbox-wizard-group"
                        type="checkbox"
                        checked={isGroup}
                        onChange={(e) => setIsGroup(e.target.checked)}
                        className="h-5 w-5 rounded border-gray-300 text-brand-600 focus:ring-brand-500 cursor-pointer"
                      />
                    </div>
                  </div>

                  {error && <p className="text-[10px] text-rose-500 font-bold">{error}</p>}

                  <div className="border-t border-gray-100 pt-5 flex justify-end">
                    <button
                      id="wizard-btn-next1"
                      type="button"
                      disabled={!canContinueStep1}
                      onClick={handleNextStep}
                      className="inline-flex items-center gap-1.5 px-6 py-3 rounded-xl font-bold bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50 cursor-pointer"
                    >
                      Continue to Registrar Details
                      <ChevronRight className="h-4.5 w-4.5" />
                    </button>
                  </div>
                </div>
              )}

              {/* STEP 2: administrator data */}
              {step === 2 && (
                <div className="space-y-5 text-xs text-gray-600 animate-in fade-in duration-250">
                  <div>
                    <h4 className="font-display font-bold text-base text-brand-950 mb-1">Registrar Contact Dossier</h4>
                    <p className="text-gray-400">Create your administrator login. These credentials will be used to access the school dashboard.</p>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label htmlFor="input-wizard-name" className="block font-bold mb-1.5 text-slate-700">Full Name:</label>
                      <input
                        id="input-wizard-name"
                        type="text"
                        required
                        placeholder="e.g. Florence Adebayo"
                        value={authName}
                        onChange={(e) => setAuthName(e.target.value)}
                        className="w-full border border-gray-200 rounded-xl px-4.5 py-3 text-sm focus:border-brand-500 bg-white"
                      />
                      <p className="text-[10px] text-gray-400 mt-1">Enter both first and last name separated by a space.</p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label htmlFor="input-wizard-email" className="block font-bold mb-1.5 text-slate-700">Your Email Address:</label>
                        <input
                          id="input-wizard-email"
                          type="email"
                          required
                          placeholder="principal@school.com"
                          value={authEmail}
                          onChange={(e) => setAuthEmail(e.target.value)}
                          className="w-full border border-gray-200 rounded-xl px-4.5 py-3 text-sm focus:border-brand-500 bg-white"
                        />
                      </div>
                      <div>
                        <label htmlFor="input-wizard-phone" className="block font-bold mb-1.5 text-slate-700">Mobile Phone Number:</label>
                        <input
                          id="input-wizard-phone"
                          type="tel"
                          required
                          placeholder="+234 80xxxxxxxx"
                          value={authPhone}
                          onChange={(e) => setAuthPhone(e.target.value)}
                          className="w-full border border-gray-200 rounded-xl px-4.5 py-3 text-sm focus:border-brand-500 bg-white"
                        />
                      </div>
                    </div>

                    {/* Password fields */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label htmlFor="input-wizard-pwd" className="block font-bold mb-1.5 text-slate-700">Password:</label>
                        <div className="relative">
                          <input
                            id="input-wizard-pwd"
                            type={showSignupPassword ? 'text' : 'password'}
                            required
                            placeholder="Minimum 8 characters"
                            value={signupPassword}
                            onChange={(e) => setSignupPassword(e.target.value)}
                            autoComplete="new-password"
                            className="w-full border border-gray-200 rounded-xl px-4.5 py-3 pr-12 text-sm focus:border-brand-500 bg-white"
                          />
                          <button
                            type="button"
                            onClick={() => setShowSignupPassword(p => !p)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 cursor-pointer p-1"
                            aria-label={showSignupPassword ? 'Hide password' : 'Show password'}
                          >
                            {showSignupPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                          </button>
                        </div>
                      </div>
                      <div>
                        <label htmlFor="input-wizard-cpwd" className="block font-bold mb-1.5 text-slate-700">Confirm Password:</label>
                        <div className="relative">
                          <input
                            id="input-wizard-cpwd"
                            type={showConfirmPassword ? 'text' : 'password'}
                            required
                            placeholder="Re-enter password"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            autoComplete="new-password"
                            className={`w-full border rounded-xl px-4.5 py-3 pr-12 text-sm focus:border-brand-500 bg-white ${
                              confirmPassword && signupPassword !== confirmPassword
                                ? 'border-rose-300 focus:border-rose-500'
                                : 'border-gray-200'
                            }`}
                          />
                          <button
                            type="button"
                            onClick={() => setShowConfirmPassword(p => !p)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 cursor-pointer p-1"
                            aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                          >
                            {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                          </button>
                        </div>
                        {confirmPassword && signupPassword !== confirmPassword && (
                          <p className="text-[10px] text-rose-500 mt-1">Passwords do not match.</p>
                        )}
                      </div>
                    </div>

                    {/* Student count estimates slider */}
                    <div className="p-4 bg-brand-50 rounded-2xl border border-brand-100 space-y-3">
                      <div className="flex justify-between font-bold text-brand-900">
                        <label htmlFor="wizard-slider-size">Estimated Student Enrollment:</label>
                        <span className="font-mono text-brand-650">{studentSize} SEATS</span>
                      </div>
                      <input
                        id="wizard-slider-size"
                        type="range"
                        min="50"
                        max="3000"
                        step="50"
                        value={studentSize}
                        onChange={(e) => setStudentSize(parseInt(e.target.value))}
                        className="w-full h-2 bg-brand-200 rounded-lg appearance-none cursor-pointer accent-brand-600"
                      />
                      <p className="text-[10px] text-gray-400 italic">Admins &amp; Teachers are 100% free. Paying the activation fee unlocks student portals and CBT tools.</p>
                    </div>
                  </div>

                  {error && <p className="text-[10px] text-rose-500 font-bold">{error}</p>}

                  <div className="border-t border-gray-100 pt-5 flex items-center justify-between">
                    <button
                      id="wizard-btn-prev2"
                      type="button"
                      onClick={handlePrevStep}
                      className="px-5 py-3 rounded-xl border border-gray-200 text-gray-700 hover:bg-slate-50 font-semibold cursor-pointer"
                    >
                      Back
                    </button>
                    <button
                      id="wizard-btn-next2"
                      type="button"
                      disabled={!canContinueStep2}
                      onClick={handleNextStep}
                      className="inline-flex items-center gap-1.5 px-6 py-3 rounded-xl font-bold bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50 cursor-pointer"
                    >
                      Select Digital Modules
                      <ChevronRight className="h-4.5 w-4.5" />
                    </button>
                  </div>
                </div>
              )}

              {/* STEP 3: modules integrations validation */}
              {step === 3 && (
                <div className="space-y-5 text-xs text-gray-600 animate-in fade-in duration-250">
                  <div>
                    <h4 className="font-display font-bold text-base text-brand-950 mb-1">Tailor Schooldom Modules</h4>
                    <p className="text-gray-400">Select which digital solutions components to provision on your initial profile workspace.</p>
                  </div>

                  <div className="space-y-2.5 max-h-[260px] overflow-y-auto pr-1">
                    
                    <div 
                      onClick={() => toggleModule('cbtOffline')}
                      className={`p-3 border rounded-xl flex items-center justify-between cursor-pointer transition-colors ${
                        modulesSelected.cbtOffline ? 'bg-brand-50 border-brand-500' : 'bg-white border-gray-200 hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center gap-3 text-left">
                        <Cpu className={`h-5 w-5 ${modulesSelected.cbtOffline ? 'text-brand-600' : 'text-gray-400'}`} />
                        <div>
                          <p className="font-bold text-slate-800">Hybrid Offline CBT system</p>
                          <p className="text-[10px] text-gray-400">Required local area server package sync.</p>
                        </div>
                      </div>
                      <div className={`h-5 w-5 rounded flex items-center justify-center border ${modulesSelected.cbtOffline ? 'bg-brand-600 border-brand-700 text-white' : 'border-gray-300'}`}>
                        {modulesSelected.cbtOffline && <Check className="h-3 w-3" />}
                      </div>
                    </div>

                    <div 
                      onClick={() => toggleModule('financeGate')}
                      className={`p-3 border rounded-xl flex items-center justify-between cursor-pointer transition-colors ${
                        modulesSelected.financeGate ? 'bg-brand-50 border-brand-500' : 'bg-white border-gray-200 hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center gap-3 text-left">
                        <Sliders className={`h-5 w-5 ${modulesSelected.financeGate ? 'text-brand-600' : 'text-gray-400'}`} />
                        <div>
                          <p className="font-bold text-slate-800">Finance & Integrated payment gateways</p>
                          <p className="text-[10px] text-gray-400">SMS, WhatsApp invoices & auto receipts.</p>
                        </div>
                      </div>
                      <div className={`h-5 w-5 rounded flex items-center justify-center border ${modulesSelected.financeGate ? 'bg-brand-600 border-brand-700 text-white' : 'border-gray-300'}`}>
                        {modulesSelected.financeGate && <Check className="h-3 w-3" />}
                      </div>
                    </div>

                    <div 
                      onClick={() => toggleModule('reportCards')}
                      className={`p-3 border rounded-xl flex items-center justify-between cursor-pointer transition-colors ${
                        modulesSelected.reportCards ? 'bg-brand-50 border-brand-500' : 'bg-white border-gray-200 hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center gap-3 text-left">
                        <Award className={`h-5 w-5 ${modulesSelected.reportCards ? 'text-brand-600' : 'text-gray-400'}`} />
                        <div>
                          <p className="font-bold text-slate-800">Academic Report Sheet generation</p>
                          <p className="text-[10px] text-gray-400">Compute position ranks & termly averages.</p>
                        </div>
                      </div>
                      <div className={`h-5 w-5 rounded flex items-center justify-center border ${modulesSelected.reportCards ? 'bg-brand-600 border-brand-700 text-white' : 'border-gray-300'}`}>
                        {modulesSelected.reportCards && <Check className="h-3 w-3" />}
                      </div>
                    </div>

                    <div 
                      onClick={() => toggleModule('idBuilder')}
                      className={`p-3 border rounded-xl flex items-center justify-between cursor-pointer transition-colors ${
                        modulesSelected.idBuilder ? 'bg-brand-50 border-brand-500' : 'bg-white border-gray-200 hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center gap-3 text-left">
                        <Layers className={`h-5 w-5 ${modulesSelected.idBuilder ? 'text-brand-600' : 'text-gray-400'}`} />
                        <div>
                          <p className="font-bold text-slate-800">Bulk ID PVC card generator</p>
                          <p className="text-[10px] text-gray-400">Print modern card sizes featuring unique QR codes.</p>
                        </div>
                      </div>
                      <div className={`h-5 w-5 rounded flex items-center justify-center border ${modulesSelected.idBuilder ? 'bg-brand-600 border-brand-700 text-white' : 'border-gray-300'}`}>
                        {modulesSelected.idBuilder && <Check className="h-3 w-3" />}
                      </div>
                    </div>

                  </div>

                  <div className="space-y-3">
                    <div className="p-3 bg-teal-brand-50 border border-teal-brand-500/15 rounded-xl flex gap-2.5 text-[11px] text-teal-brand-600 font-medium">
                      <ShieldCheck className="h-4.5 w-4.5 text-teal-brand-500 shrink-0 mt-0.5" />
                      <span>
                        <strong>Workspace SLA: </strong> No subscription fees are charged until term 1 classes resume! Confirming will provision your secure cloud sandbox.
                      </span>
                    </div>

                    {/* Terms & Conditions */}
                    <div className="p-3 bg-slate-50 border border-slate-200/60 rounded-xl flex items-start gap-2.5">
                      <input
                        id="checkbox-terms-accepted"
                        type="checkbox"
                        required
                        checked={termsAccepted}
                        onChange={(e) => {
                          if (e.target.checked && !termsOpened) {
                            setError("Please read the Terms and Conditions before accepting.");
                            return;
                          }
                          setError("");
                          setTermsAccepted(e.target.checked);
                        }}
                        className="mt-0.5 h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500 cursor-pointer"
                      />
                      <label htmlFor="checkbox-terms-accepted" className="text-[10px] sm:text-[11px] text-slate-600 font-semibold cursor-pointer select-none leading-relaxed">
                        I have read and accept the Schooldom{' '}
                        <a
                          href="#terms"
                          className="text-brand-600 underline hover:text-brand-700"
                          onClick={(e) => {
                            e.preventDefault();
                            setShowTermsModal(true);
                            setTermsOpened(true);
                            window.localStorage.setItem(TERMS_OPENED_KEY, "true");
                          }}
                        >
                          Terms &amp; Conditions
                        </a>.
                      </label>
                    </div>

                    {/* NDPC Consent */}
                    <div className="p-3 bg-slate-50 border border-slate-200/60 rounded-xl flex items-start gap-2.5">
                      <input
                        id="checkbox-legal-consent"
                        type="checkbox"
                        required
                        checked={legalConsent}
                        onChange={(e) => setLegalConsent(e.target.checked)}
                        className="mt-0.5 h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500 cursor-pointer"
                      />
                      <label htmlFor="checkbox-legal-consent" className="text-[10px] sm:text-[11px] text-slate-500 font-semibold cursor-pointer select-none leading-relaxed">
                        Our institution consents to secure student record processing in full compliance with the <strong>Nigeria Data Protection Act (NDPR/NDPA)</strong> and Schooldom's Privacy Charter.
                      </label>
                    </div>
                  </div>

                  {error && <p className="text-[10px] text-rose-500 font-bold">{error}</p>}

                  <div className="border-t border-gray-100 pt-5 flex items-center justify-between">
                    <button
                      id="wizard-btn-prev3"
                      type="button"
                      onClick={handlePrevStep}
                      className="px-5 py-3 rounded-xl border border-gray-200 text-gray-700 hover:bg-slate-50 font-semibold cursor-pointer"
                    >
                      Back
                    </button>
                    <button
                      id="wizard-btn-submit"
                      type="submit"
                      disabled={!canSubmit}
                      className="px-7 py-3 rounded-xl font-bold text-white bg-brand-600 hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed shadow-md transition-all cursor-pointer"
                    >
                      Provision Workspace &amp; Deploy
                    </button>
                  </div>
                </div>
              )}

            </form>
          )}
        </div>

      </div>
    </div>

    {showTermsModal && (
      <div
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem', backdropFilter: 'blur(3px)' }}
        onClick={(e) => { if (e.target === e.currentTarget) setShowTermsModal(false); }}
        role="dialog"
        aria-modal="true"
        aria-label="Terms and Conditions"
      >
        <div style={{ background: '#fff', borderRadius: '14px', width: '100%', maxWidth: '660px', maxHeight: '88vh', display: 'flex', flexDirection: 'column', boxShadow: '0 28px 64px rgba(0,0,0,0.2)' }}>
          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.2rem 1.5rem 1rem', borderBottom: '1px solid #e2e8f0', flexShrink: 0 }}>
            <h2 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: '#1e293b' }}>Terms &amp; Conditions</h2>
            <button type="button" onClick={() => setShowTermsModal(false)} style={{ background: 'none', border: 'none', fontSize: '1.6rem', lineHeight: 1, cursor: 'pointer', color: '#64748b', padding: '0.2rem 0.5rem', borderRadius: '6px' }} aria-label="Close">×</button>
          </div>

          {/* Body */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', fontSize: '0.875rem', lineHeight: 1.7, color: '#475569' }}>
            <p style={{ color: '#94a3b8', fontSize: '0.78rem', marginBottom: '1rem' }}>Effective Date: 2026 · Xcel Technologies Ltd</p>

            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', margin: '0 0 0.4rem' }}>1. Introduction &amp; Agreement</h3>
            <p>These Terms govern your access to and use of the SchoolDom platform, including the website, web application, and mobile applications. By creating an account, you confirm you have read, understood, and agree to these Terms.</p>

            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', margin: '1.2rem 0 0.4rem' }}>2. Definitions</h3>
            <p><strong>Platform:</strong> SchoolDom website, web app, and mobile apps.</p>
            <p><strong>User:</strong> Any individual authorized to use the Platform — School Owner, Administrator, Teacher, Parent/Guardian, or Student.</p>
            <p><strong>Content:</strong> All data, files, results, documents, and information uploaded or stored by Users.</p>

            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', margin: '1.2rem 0 0.4rem' }}>3. Accounts &amp; Eligibility</h3>
            <p>School Owners must be legal representatives with authority to contract. Administrators, Teachers, and Parents must be 18+. Students may use the Platform only under supervision and with consent from the School Owner.</p>
            <p>You must provide accurate information and keep it updated. You are responsible for all activities under your account. Notify us at <a href="mailto:enquiry@schooldom.academy" style={{ color: '#4f46e5' }}>enquiry@schooldom.academy</a> immediately if you suspect unauthorized access.</p>
            <p>You must not: violate any Nigerian law or NDPR; impersonate any person or school; upload malware; attempt unauthorized access or data scraping; upload content that is defamatory, obscene, or harmful to minors.</p>

            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', margin: '1.2rem 0 0.4rem' }}>4. Content &amp; Data Ownership</h3>
            <p>You own the Content you upload and are solely responsible for it. You grant Xcel Technologies a non-exclusive license to host, process, and backup your Content solely to provide SchoolDom. The School Owner is the Data Controller for NDPR/GDPR purposes; Xcel Technologies is the Data Processor.</p>

            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', margin: '1.2rem 0 0.4rem' }}>5. Intellectual Property</h3>
            <p>SchoolDom, including all code, design, logos, and features, is owned by Xcel Technologies Ltd. We grant you a limited, non-exclusive, non-transferable license for your school's internal use only. You may not copy, modify, reverse engineer, or resell the Platform without written consent.</p>

            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', margin: '1.2rem 0 0.4rem' }}>6. Fees, Payment &amp; Refunds</h3>
            <p>Subscription fees are billed annually/termly in advance. After the free trial ends, fees are non-refundable except if we fail to provide core services for 7+ consecutive days due to our fault. Parents paying school fees via SchoolDom pay gateway charges set by payment partners — Xcel Technologies does not receive these.</p>

            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', margin: '1.2rem 0 0.4rem' }}>7. Service Availability &amp; Support</h3>
            <p>We aim for 99.5% monthly uptime, excluding scheduled maintenance (48-hour notice given). Support: <a href="mailto:enquiry@schooldom.academy" style={{ color: '#4f46e5' }}>enquiry@schooldom.academy</a>, 9am–5pm WAT Mon–Fri. Critical issues: 4-hour response.</p>

            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', margin: '1.2rem 0 0.4rem' }}>8. Suspension &amp; Termination</h3>
            <p>School Owners may terminate by emailing us; access ends at the paid period. We may suspend accounts for breach of Terms, non-payment, fraud, or illegal use. You have 30 days after termination to export your data.</p>

            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', margin: '1.2rem 0 0.4rem' }}>9. Limitation of Liability</h3>
            <p>Xcel Technologies is not liable for indirect, incidental, or consequential damages. Our total liability is limited to amounts you paid us in the 12 months before the claim.</p>

            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', margin: '1.2rem 0 0.4rem' }}>10. Disclaimer of Warranties</h3>
            <p>SchoolDom is provided "AS IS" and "AS AVAILABLE". We do not guarantee the Platform will be error-free or uninterrupted, and are not responsible for internet outages or third-party service failures.</p>

            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', margin: '1.2rem 0 0.4rem' }}>11. Changes to Terms</h3>
            <p>We may update these Terms to reflect new features or legal changes. We'll post the updated version with a new Effective Date and notify School Administrators by email for material changes.</p>

            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', margin: '1.2rem 0 0.4rem' }}>12. Governing Law &amp; Disputes</h3>
            <p>These Terms are governed by the laws of the Federal Republic of Nigeria. Disputes will first attempt amicable resolution for 30 days, then proceed to arbitration in Lagos under the Arbitration and Conciliation Act.</p>

            <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', margin: '1.2rem 0 0.4rem' }}>13. Contact Us</h3>
            <p>Xcel Technologies Ltd · <a href="mailto:enquiry@schooldom.academy" style={{ color: '#4f46e5' }}>enquiry@schooldom.academy</a> · 256 Ikotun Road, Lagos.</p>
          </div>

          {/* Footer */}
          <div style={{ padding: '1rem 1.5rem', borderTop: '1px solid #e2e8f0', display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', flexShrink: 0 }}>
            <button
              type="button"
              onClick={() => { setTermsAccepted(false); setShowTermsModal(false); }}
              style={{ padding: '0.6rem 1.25rem', borderRadius: '8px', border: '1px solid #e2e8f0', background: 'transparent', color: '#64748b', fontSize: '0.875rem', cursor: 'pointer' }}
            >
              Decline
            </button>
            <button
              type="button"
              onClick={() => {
                setTermsAccepted(true);
                setTermsOpened(true);
                window.localStorage.setItem(TERMS_OPENED_KEY, "true");
                setShowTermsModal(false);
                setError("");
              }}
              style={{ padding: '0.6rem 1.5rem', borderRadius: '8px', border: 'none', background: '#4f46e5', color: '#fff', fontSize: '0.875rem', fontWeight: 600, cursor: 'pointer' }}
            >
              Accept &amp; Continue
            </button>
          </div>
        </div>
      </div>
    )}
  </>);
}

