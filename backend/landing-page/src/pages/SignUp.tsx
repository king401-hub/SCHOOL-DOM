import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import {
  ArrowLeft, ArrowRight, ShieldCheck, GraduationCap, Users, CheckCircle2,
  Eye, EyeOff, Copy, Check,
} from 'lucide-react';

const stepMotion = {
  initial: { opacity: 0, x: 28 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -28 },
  transition: { duration: 0.35, ease: 'easeOut' },
};

function Spinner() {
  return <span className="sd-spinner" aria-hidden="true" />;
}

type Role = 'school_admin' | 'principal' | 'school_superadmin';
type SchoolType = 'k12' | 'non_k12';

const SESSION_KEY = 'schooldom.session';
const ADMIN_APP_URL = (import.meta as any).env?.VITE_ADMIN_APP_URL || ((import.meta as any).env?.PROD ? '/app/' : 'http://localhost:5173/');

const ROLES: { value: Role; title: string; desc: string; icon: typeof ShieldCheck }[] = [
  { value: 'school_admin', title: 'School Admin', desc: 'Direct management of single school operations, staff, and configurations.', icon: ShieldCheck },
  { value: 'principal', title: 'School Principal', desc: 'Educational head oversight, curriculum planning, and staff assignment keys.', icon: GraduationCap },
  { value: 'school_superadmin', title: 'Proprietor', desc: 'Group management overseeing multiple campuses and administrative keys.', icon: Users },
];

const STEP_LABELS = ['Account & Onboarding Role', 'Configure Institutional Profile', 'Verify & Activate'];

function parseErrorMessage(data: any, fallback: string): string {
  if (!data) return fallback;
  if (typeof data.message === 'string' && data.message.trim().length > 0) return data.message;
  if (data.errors && typeof data.errors === 'object') {
    const entries = Object.entries(data.errors);
    if (entries.length > 0) {
      const [field, value] = entries[0];
      const val = Array.isArray(value) ? value[0] : value;
      return `${field}: ${val}`;
    }
  }
  return fallback;
}

async function postJson(path: string, body: any) {
  let res: Response;
  try {
    res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error('Unable to reach the server. Check your connection and try again.');
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data?.success === false) {
    throw new Error(parseErrorMessage(data, 'Request failed. Please try again.'));
  }
  return data;
}

function Stepper({ step }: { step: number }) {
  return (
    <div className="mb-8">
      <div className="flex items-center gap-3 mb-3">
        <div className="h-8 w-8 rounded-lg flex items-center justify-center font-display font-black text-sm text-white shrink-0"
          style={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)' }}>
          {step}
        </div>
        <div>
          <p className="text-slate-500 text-[10px] uppercase tracking-wider font-semibold">Onboarding Progress</p>
          <p className="text-white text-sm font-bold">{STEP_LABELS[step - 1]}</p>
        </div>
      </div>
      <div className="flex gap-1.5">
        {STEP_LABELS.map((_, i) => (
          <div key={i} className="h-1.5 flex-1 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
            <div className="h-full rounded-full transition-all duration-500"
              style={{ width: i <= step - 1 ? '100%' : '0%', background: 'linear-gradient(90deg,#22c55e,#0ea5e9)' }} />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function SignUpPage() {
  const [searchParams] = useSearchParams();
  const initialTier = searchParams.get('tier') === 'non_k12' ? 'non_k12' : 'k12';

  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const [role, setRole] = useState<Role>('school_admin');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const [schoolName, setSchoolName] = useState('');
  const [schoolType, setSchoolType] = useState<SchoolType>(initialTier as SchoolType);
  const [address, setAddress] = useState('');
  const [schoolGroupName, setSchoolGroupName] = useState('');
  const [certified, setCertified] = useState(false);

  // useState's initializer only runs on mount, so if this page is ever reached
  // twice without a full remount (e.g. browser back/forward between
  // ?tier=k12 and ?tier=non_k12), the dropdown could silently keep showing
  // the stale tier. Resync whenever the URL's tier param actually changes.
  useEffect(() => {
    const tierParam = searchParams.get('tier');
    if (tierParam === 'k12' || tierParam === 'non_k12') {
      setSchoolType(tierParam);
    }
  }, [searchParams]);

  const [schoolCode, setSchoolCode] = useState('');
  const [otpChallenge, setOtpChallenge] = useState('');
  const [otpExpiresIn, setOtpExpiresIn] = useState(600);
  const [otpCode, setOtpCode] = useState('');
  const [isResending, setIsResending] = useState(false);
  const [activated, setActivated] = useState(false);
  const [codeCopied, setCodeCopied] = useState(false);

  const isProprietor = role === 'school_superadmin';

  const canStep1 = useMemo(() => (
    fullName.trim().length > 1 &&
    /\S+@\S+\.\S+/.test(email.trim()) &&
    phone.trim().length >= 7 &&
    password.length >= 8 &&
    password === confirmPassword
  ), [fullName, email, phone, password, confirmPassword]);

  const canStep2 = useMemo(() => {
    if (!certified) return false;
    return isProprietor ? schoolGroupName.trim().length >= 3 : schoolName.trim().length >= 3;
  }, [isProprietor, schoolGroupName, schoolName, certified]);

  const inputCls = 'w-full px-4 py-3 text-sm rounded-xl sd-input placeholder-slate-600';
  const errorBox = (msg: string) => (
    <div className="p-3.5 rounded-xl text-sm" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)', color: '#f87171' }}>
      {msg}
    </div>
  );

  const finalizeSession = (data: any, code: string) => {
    const session = {
      user: data.user,
      access: data.access,
      refresh: data.refresh,
      school: data.school || null,
      school_code: data.school_code || code || '',
      redirectUrl: data.redirect_url || '/dashboard',
      requiresVerification: false,
      signedInAt: new Date().toISOString(),
    };
    window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    setActivated(true);
  };

  const handleGenerateCode = async () => {
    if (!canStep2 || submitting) return;
    setSubmitting(true);
    setError('');
    try {
      let code = '';
      if (!isProprietor) {
        const schoolData = await postJson('/api/auth/create-school/', {
          school_name: schoolName.trim(),
          school_code: '',
          email: email.trim(),
          school_type: schoolType,
          address: address.trim(),
        });
        code = schoolData?.school?.school_code || '';
        setSchoolCode(code);
      }

      const parts = fullName.trim().split(/\s+/);
      const firstName = parts[0] || '';
      const lastName = parts.slice(1).join(' ') || parts[0] || '';
      const roleMeta = ROLES.find(r => r.value === role);

      const regData = await postJson('/api/auth/register/', {
        first_name: firstName,
        last_name: lastName,
        email: email.trim(),
        password,
        confirm_password: confirmPassword,
        role,
        admin_title: roleMeta?.title || '',
        phone: phone.trim(),
        school_code: isProprietor ? '' : code,
        school_group_name: isProprietor ? schoolGroupName.trim() : '',
        terms_accepted: certified,
      });

      if (regData.requires_otp) {
        setOtpChallenge(regData.otp_challenge);
        setOtpExpiresIn(regData.otp_expires_in || 600);
        setStep(3);
      } else {
        finalizeSession(regData, code);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleVerifyOtp = async (event: React.FormEvent) => {
    event.preventDefault();
    if (otpCode.trim().length !== 6 || submitting) return;
    setSubmitting(true);
    setError('');
    try {
      const data = await postJson('/api/auth/admin/verify-otp/', {
        email: email.trim(),
        code: otpCode.trim(),
        challenge: otpChallenge,
      });
      if (!data.success || !data.access) throw new Error(parseErrorMessage(data, 'Verification failed.'));
      finalizeSession(data, schoolCode);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleResendOtp = async () => {
    if (isResending) return;
    setIsResending(true);
    setError('');
    try {
      const data = await postJson('/api/auth/admin/resend-otp/', { email: email.trim(), challenge: otpChallenge });
      setOtpChallenge(data.otp_challenge || otpChallenge);
      setOtpExpiresIn(data.otp_expires_in || 600);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not resend code.');
    } finally {
      setIsResending(false);
    }
  };

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(schoolCode);
      setCodeCopied(true);
      setTimeout(() => setCodeCopied(false), 2000);
    } catch {
      // clipboard unavailable — ignore
    }
  };

  if (activated) {
    return (
      <div className="signup-shell min-h-screen pt-24 pb-20 px-4 flex items-center justify-center">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
          className="max-w-md w-full rounded-3xl p-8 text-center sd-card">
          <motion.div
            initial={{ scale: 0 }} animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 400, damping: 14, delay: 0.1 }}
            className="h-16 w-16 rounded-full flex items-center justify-center mx-auto mb-5"
            style={{ background: 'rgba(34,197,94,0.15)', border: '1px solid rgba(34,197,94,0.3)' }}>
            <CheckCircle2 className="h-8 w-8" style={{ color: '#22c55e' }} />
          </motion.div>
          <h1 className="font-display font-black text-white text-2xl mb-2">Your school is live!</h1>
          <p className="text-slate-400 text-sm mb-6">
            {schoolCode
              ? <>Your unique school code is <strong className="text-white">{schoolCode}</strong> — keep it safe, you'll need it to sign in.</>
              : 'You can create your first school from the dashboard.'}
          </p>
          <a href={ADMIN_APP_URL} className="btn-primary w-full justify-center py-3.5 text-base">
            Go to Dashboard <ArrowRight className="h-4 w-4" />
          </a>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="signup-shell min-h-screen pt-24 pb-20 px-4 relative">
      <div className="absolute top-0 inset-x-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(34,197,94,0.05) 0%, transparent 50%)' }} />

      <div className="max-w-3xl mx-auto" style={{ animation: 'fadeInUp 0.6s ease' }}>
        <a href="/" className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-300 text-sm mb-8 transition-colors">
          <ArrowLeft className="h-4 w-4" /> Back to home
        </a>

        <div className="rounded-3xl p-8 sm:p-10 sd-card overflow-hidden">
          <Stepper step={step} />

          <AnimatePresence mode="wait">
          {step === 1 && (
            <motion.div key="step1" {...stepMotion} className="space-y-6">
              <div>
                <h1 className="font-display font-black text-white text-2xl mb-1">Onboard your School Platform</h1>
                <p className="text-slate-400 text-sm">Begin by choosing your structural role and entering your representative contact details.</p>
              </div>

              <div>
                <p className="text-slate-500 text-[10px] uppercase tracking-wider font-semibold mb-3">Choose your primary role</p>
                <div className="grid sm:grid-cols-3 gap-3">
                  {ROLES.map(r => {
                    const Icon = r.icon;
                    const active = role === r.value;
                    return (
                      <button key={r.value} type="button" onClick={() => setRole(r.value)}
                        className="relative w-full text-left flex items-start gap-3 p-4 rounded-2xl transition-all sd-card cursor-pointer"
                        style={{ borderColor: active ? 'rgba(34,197,94,0.4)' : undefined, background: active ? 'rgba(34,197,94,0.06)' : undefined }}>
                        <div className="h-9 w-9 rounded-xl flex items-center justify-center shrink-0"
                          style={{ background: active ? 'rgba(34,197,94,0.15)' : 'rgba(255,255,255,0.04)', border: active ? '1px solid rgba(34,197,94,0.3)' : '1px solid rgba(255,255,255,0.06)' }}>
                          <Icon className="h-4 w-4" style={{ color: active ? '#22c55e' : '#64748b' }} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-white text-sm font-semibold">{r.title}</p>
                          <p className="text-slate-500 text-xs mt-0.5">{r.desc}</p>
                        </div>
                        {active && (
                          <motion.span
                            initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                            transition={{ type: 'spring', stiffness: 500, damping: 15 }}
                            className="absolute top-3 right-3">
                            <CheckCircle2 className="h-5 w-5 shrink-0" style={{ color: '#22c55e' }} />
                          </motion.span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <p className="text-slate-500 text-[10px] uppercase tracking-wider font-semibold mb-3">Representative contact details</p>
                <div className="space-y-4">
                  <div>
                    <label className="block text-slate-500 text-xs mb-1.5">Full Name</label>
                    <input type="text" value={fullName} onChange={e => setFullName(e.target.value)}
                      placeholder="Dr. Eleanor Vance" autoComplete="name" className={inputCls} />
                  </div>
                  <div className="grid sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-slate-500 text-xs mb-1.5">Professional Email Address</label>
                      <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                        placeholder="vance.e@academy.edu" autoComplete="email" className={inputCls} />
                    </div>
                    <div>
                      <label className="block text-slate-500 text-xs mb-1.5">Direct Contact Phone</label>
                      <input type="tel" value={phone} onChange={e => setPhone(e.target.value)}
                        placeholder="+234 80x xxx xxxx" autoComplete="tel" className={inputCls} />
                    </div>
                  </div>
                  <div className="grid sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-slate-500 text-xs mb-1.5">Password</label>
                      <div className="relative">
                        <input type={showPassword ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)}
                          placeholder="Minimum 8 characters" autoComplete="new-password" className={inputCls} />
                        <button type="button" onClick={() => setShowPassword(s => !s)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 cursor-pointer"
                          aria-label={showPassword ? 'Hide password' : 'Show password'}>
                          {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>
                    <div>
                      <label className="block text-slate-500 text-xs mb-1.5">Confirm Password</label>
                      <input type={showPassword ? 'text' : 'password'} value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)}
                        placeholder="Re-enter password" autoComplete="new-password" className={inputCls} />
                    </div>
                  </div>
                  {password && confirmPassword && password !== confirmPassword && (
                    <p className="text-xs" style={{ color: '#f87171' }}>Passwords do not match.</p>
                  )}
                </div>
              </div>

              {error && errorBox(error)}

              <button type="button" disabled={!canStep1} onClick={() => { setError(''); setStep(2); }}
                className="w-full btn-primary justify-center py-3.5 text-base">
                Continue to School Profile <ArrowRight className="h-4 w-4" />
              </button>
            </motion.div>
          )}

          {step === 2 && (
            <motion.div key="step2" {...stepMotion} className="space-y-6">
              <div>
                <h1 className="font-display font-black text-white text-2xl mb-1">
                  {isProprietor ? 'Configure Group Profile' : 'Configure Institutional Details'}
                </h1>
                <p className="text-slate-400 text-sm">
                  {isProprietor
                    ? 'Set up your organization name. You will create and manage individual schools from your dashboard.'
                    : "Provide information regarding your school, including the Schooldom tier."}
                </p>
              </div>

              {isProprietor ? (
                <div>
                  <label className="block text-slate-500 text-xs mb-1.5">Official Group / Organization Name</label>
                  <input type="text" value={schoolGroupName} onChange={e => setSchoolGroupName(e.target.value)}
                    placeholder="Pinecrest Education Group" className={inputCls} />
                </div>
              ) : (
                <div className="space-y-4">
                  <div>
                    <label className="block text-slate-500 text-xs mb-1.5">Official School Name</label>
                    <input type="text" value={schoolName} onChange={e => setSchoolName(e.target.value)}
                      placeholder="Pinecrest Academy High" className={inputCls} />
                  </div>
                  <div>
                    <label className="block text-slate-500 text-xs mb-1.5">Schooldom Tier</label>
                    <select value={schoolType} onChange={e => setSchoolType(e.target.value as SchoolType)} className={inputCls}>
                      <option value="k12">K-12 Education</option>
                      <option value="non_k12">Non-K12 (Vocational, Tertiary, Academies)</option>
                    </select>
                    <p className="text-slate-500 text-xs mt-1.5">Select 'K-12' for foundational schools, or 'Non-K12' for higher/vocational education.</p>
                  </div>
                  <div>
                    <label className="block text-slate-500 text-xs mb-1.5">Institutional Physical Address (Optional)</label>
                    <input type="text" value={address} onChange={e => setAddress(e.target.value)}
                      placeholder="402 Academic Circle, Suite 100" className={inputCls} />
                  </div>
                </div>
              )}

              <label className="flex items-start gap-3 text-slate-400 text-xs cursor-pointer">
                <input type="checkbox" checked={certified} onChange={e => setCertified(e.target.checked)} className="mt-0.5" />
                <span>I certify that I am authorized to onboard this {isProprietor ? 'organization' : 'school'} and I agree to the Institutional Onboarding Charter and Data Protection Agreement.</span>
              </label>

              {error && errorBox(error)}

              <div className="flex gap-3">
                <button type="button" onClick={() => { setError(''); setStep(1); }} className="btn-ghost py-3.5 px-6 text-sm">
                  <ArrowLeft className="h-4 w-4" /> Back
                </button>
                <button type="button" disabled={!canStep2 || submitting} onClick={handleGenerateCode}
                  className="flex-1 btn-primary justify-center py-3.5 text-base">
                  {submitting
                    ? <span className="flex items-center gap-2"><Spinner /> Generating...</span>
                    : <>Generate Verification Code <ArrowRight className="h-4 w-4" /></>}
                </button>
              </div>
            </motion.div>
          )}

          {step === 3 && (
            <motion.form key="step3" {...stepMotion} onSubmit={handleVerifyOtp} className="space-y-6">
              <div>
                <h1 className="font-display font-black text-white text-2xl mb-1">Verify Your Account</h1>
                <p className="text-slate-400 text-sm">We sent a 6-digit verification code to <strong className="text-white">{email}</strong>.</p>
              </div>

              {schoolCode && (
                <div className="rounded-2xl p-4 flex items-center justify-between gap-3"
                  style={{ background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.2)' }}>
                  <div>
                    <p className="text-slate-500 text-[10px] uppercase tracking-wider">Your unique school code</p>
                    <p className="font-display font-black text-lg" style={{ color: '#22c55e' }}>{schoolCode}</p>
                  </div>
                  <button type="button" onClick={copyCode} className="btn-ghost text-xs py-2 px-3">
                    {codeCopied ? <><Check className="h-3.5 w-3.5" /> Copied</> : <><Copy className="h-3.5 w-3.5" /> Copy</>}
                  </button>
                </div>
              )}

              <div>
                <label className="block text-slate-500 text-xs mb-1.5">Verification Code</label>
                <input type="text" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={otpCode}
                  onChange={e => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="000000" autoComplete="one-time-code"
                  className={`${inputCls} text-center tracking-[0.5em] font-mono text-lg`} />
                <p className="text-slate-500 text-xs mt-1.5">Code expires in about {Math.max(Math.ceil(otpExpiresIn / 60), 1)} minutes.</p>
              </div>

              {error && errorBox(error)}

              <button type="submit" disabled={otpCode.length !== 6 || submitting} className="w-full btn-primary justify-center py-3.5 text-base">
                {submitting
                  ? <span className="flex items-center gap-2"><Spinner /> Verifying...</span>
                  : 'Activate Account'}
              </button>
              <button type="button" disabled={isResending} onClick={handleResendOtp} className="w-full btn-ghost justify-center py-2.5 text-sm">
                {isResending ? <span className="flex items-center gap-2"><Spinner /> Sending...</span> : 'Resend code'}
              </button>
            </motion.form>
          )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
