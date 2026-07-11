import { useState } from 'react';
import {
  X, Check, ChevronRight, Eye, ShieldCheck, RefreshCw, Award, Sparkles
} from 'lucide-react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

const NIG_STATES = [
  'Abia','Adamawa','Akwa Ibom','Anambra','Bauchi','Bayelsa','Benue','Borno',
  'Cross River','Delta','Ebonyi','Edo','Ekiti','Enugu','Gombe','Imo','Jigawa',
  'Kaduna','Kano','Katsina','Kebbi','Kogi','Kwara','Lagos','Nasarawa','Niger',
  'Ogun','Ondo','Osun','Oyo','Plateau','Rivers','Sokoto','Taraba','Yobe','Zamfara','FCT Abuja',
];

export default function OnboardingWizard({ isOpen, onClose }: Props) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState('');
  const [success, setSuccess] = useState(false);

  const [schoolName, setSchoolName] = useState('');
  const [schoolType, setSchoolType] = useState<'K12' | 'Non-K12'>('K12');
  const [locationState, setLocationState] = useState('Lagos');
  const [isGroup, setIsGroup] = useState(false);

  const [authName, setAuthName] = useState('');
  const [authEmail, setAuthEmail] = useState('');
  const [authPhone, setAuthPhone] = useState('');
  const [studentSize, setStudentSize] = useState(300);

  const [kidMonitor, setKidMonitor] = useState(false);
  const [consent, setConsent] = useState(false);

  const [schoolCode] = useState(() => `SD-SCH-${Math.floor(1000 + Math.random() * 9000)}`);

  if (!isOpen) return null;

  const canStep1 = schoolName.trim() !== '';
  const canStep2 = authName.trim() !== '' && authEmail.trim() !== '' && authPhone.trim() !== '';

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const stages = [
      'Securing administrative endpoint cluster...',
      'Mapping regional database shards...',
      'Configuring Schooldom CBT credentials...',
      'Generating terminal certificate seal...',
    ];
    stages.forEach((msg, i) => {
      setTimeout(() => {
        setLoadingStage(msg);
        if (i === stages.length - 1) {
          setTimeout(() => {
            setLoading(false);
            setSuccess(true);
            localStorage.setItem('schooldom_school_name', schoolName);
          }, 800);
        }
      }, i * 500);
    });
  };

  const reset = () => {
    setStep(1); setLoading(false); setSuccess(false);
    setSchoolName(''); setSchoolType('K12'); setLocationState('Lagos');
    setIsGroup(false); setAuthName(''); setAuthEmail(''); setAuthPhone('');
    setStudentSize(300); setConsent(false); setKidMonitor(false);
    onClose();
  };

  const pricing = schoolType === 'K12'
    ? `₦500 / term (3 months 15 days)${kidMonitor ? ' + ₦1,000 Child Monitor = ₦1,500/term' : ''}`
    : '₦200 / month';

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4"
      style={{ background: 'rgba(2,8,23,0.88)', backdropFilter: 'blur(12px)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="relative w-full max-w-xl rounded-3xl overflow-hidden flex flex-col max-h-[92vh] sd-modal"
        style={{ boxShadow: '0 40px 80px rgba(0,0,0,0.6)' }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-6 py-5"
          style={{ background: 'linear-gradient(135deg, rgba(34,197,94,0.12), rgba(14,165,233,0.08))', borderBottom: '1px solid rgba(255,255,255,0.06)' }}
        >
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl overflow-hidden border border-white/10 shrink-0"
              style={{ boxShadow: '0 0 12px rgba(34,197,94,0.15)' }}>
              <img src="/schooldom-favicon.jpeg" alt="Schooldom" className="w-full h-full object-cover" />
            </div>
            <div>
              <p className="text-white font-bold text-sm">Schooldom Onboarding</p>
              {!success && !loading && (
                <p className="text-slate-500 text-[10px] font-mono">STEP {step} OF 3 — REGISTRATION</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden sm:block text-right px-3 py-1.5 rounded-xl"
              style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.25)' }}>
              <p className="text-slate-500 text-[8px] uppercase tracking-widest">School Code</p>
              <p className="font-mono font-bold text-xs" style={{ color: '#22c55e' }}>{schoolCode}</p>
            </div>
            <button onClick={onClose} className="p-1.5 rounded-xl hover:bg-white/5 text-slate-500 hover:text-white transition-colors cursor-pointer">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Step indicators */}
        {!loading && !success && (
          <div className="flex px-6 py-3 gap-2" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
            {[1, 2, 3].map(s => (
              <div
                key={s}
                className={`flex-1 h-1 rounded-full transition-all duration-300 ${s <= step ? '' : 'sd-track'}`}
                style={{ background: s <= step ? '#22c55e' : undefined }}
              />
            ))}
          </div>
        )}

        {/* Body */}
        <div className="p-6 overflow-y-auto flex-1 text-left">

          {loading && (
            <div className="py-14 flex flex-col items-center justify-center text-center space-y-5">
              <RefreshCw className="h-12 w-12 text-green-400 animate-spin" />
              <div>
                <h4 className="text-white font-bold text-lg mb-1">Provisioning Your Workspace</h4>
                <p className="text-slate-500 text-xs max-w-xs mx-auto">West African server nodes are organizing your institution's database cluster.</p>
              </div>
              <div className="px-4 py-2 rounded-xl text-xs font-mono text-green-400 animate-pulse" style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.15)' }}>
                {loadingStage || 'Connecting to core cloud router...'}
              </div>
            </div>
          )}

          {success && (
            <div className="space-y-5">
              <div className="text-center space-y-2">
                <div className="h-14 w-14 rounded-full flex items-center justify-center mx-auto mb-3" style={{ background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)' }}>
                  <Check className="h-7 w-7 text-emerald-400" />
                </div>
                <h4 className="text-white font-bold text-xl">Institution Onboarded!</h4>
                <p className="text-slate-500 text-sm">Your school has been compiled on the Schooldom cluster.</p>
              </div>

              <div className="rounded-2xl p-5 relative overflow-hidden sd-card">
                <div className="absolute top-4 right-4 opacity-5 pointer-events-none">
                  <Award className="h-24 w-24 text-white" />
                </div>
                <p className="text-[9px] font-bold text-green-400 tracking-[0.2em] uppercase mb-3">Certification of Digital Migration</p>
                <h5 className="text-white font-bold text-sm mb-1">{schoolName}</h5>
                <p className="text-slate-500 text-[10px] font-mono tracking-wider mb-3">SCHOOL CODE: <span className="text-green-400 font-bold">{schoolCode}</span></p>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between"><span className="text-slate-500">Location</span><span className="text-slate-300">{locationState}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Registrar</span><span className="text-slate-300">{authName}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Type</span><span className="text-green-400 font-semibold">{schoolType === 'K12' ? 'K-12 Termly' : 'Non-K12 Monthly'}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Pricing</span><span className="text-emerald-400 font-semibold">{pricing}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Student Seats</span><span className="text-slate-300 font-mono">{studentSize}</span></div>
                </div>
                <div className="mt-4 p-3 rounded-xl space-y-1.5" style={{ background: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.15)' }}>
                  <div className="flex items-start gap-2.5">
                    <Sparkles className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5 animate-pulse" />
                    <p className="text-emerald-400 text-[11px] leading-relaxed">
                      Based on {studentSize} student seats, your institution is pre-qualified for up to <strong>₦{(studentSize * 5000).toLocaleString()}</strong> in school development facilities from our verified financial partners.
                    </p>
                  </div>
                  <p className="text-emerald-500/70 text-[8px] italic font-mono uppercase tracking-wide pl-6">
                    *Terms and Conditions apply. Subject to final portfolio risk review.
                  </p>
                </div>
              </div>

              <div className="flex gap-3">
                <button onClick={reset} className="flex-1 py-3 rounded-xl border border-white/10 text-slate-300 text-sm font-medium hover:bg-white/5 transition-all cursor-pointer">
                  Close
                </button>
                <a
                  href="/register/"
                  className="flex-1 py-3 rounded-xl text-white text-sm font-bold text-center transition-all cursor-pointer"
                  style={{ background: 'linear-gradient(135deg, #22c55e, #0ea5e9)' }}
                >
                  Continue Setup →
                </a>
              </div>
            </div>
          )}

          {!loading && !success && (
            <form onSubmit={handleSubmit} className="space-y-5">

              {/* STEP 1 */}
              {step === 1 && (
                <div className="space-y-5">
                  <div>
                    <h4 className="text-white font-bold text-base mb-0.5">About Your Institution</h4>
                    <p className="text-slate-500 text-xs">Provide the verified details of your school or group.</p>
                  </div>

                  <Field label="School / Group Name" id="wiz-name">
                    <input
                      id="wiz-name"
                      type="text"
                      required
                      placeholder="e.g. Royal Heights Group of Schools"
                      value={schoolName}
                      onChange={e => setSchoolName(e.target.value)}
                      className="w-full px-4 py-3 rounded-xl text-sm sd-input placeholder-slate-600 outline-none"
                    />
                  </Field>

                  <div className="grid grid-cols-2 gap-4">
                    <Field label="Academic Structure" id="wiz-type">
                      <select
                        id="wiz-type"
                        value={schoolType}
                        onChange={e => setSchoolType(e.target.value as 'K12' | 'Non-K12')}
                        className="w-full px-4 py-3 rounded-xl text-sm sd-input outline-none appearance-none"
                      >
                        <option value="K12">K-12 (Nursery / Primary / Secondary)</option>
                        <option value="Non-K12">Non-K12 (Vocational / Tertiary)</option>
                      </select>
                    </Field>
                    <Field label="State" id="wiz-state">
                      <select
                        id="wiz-state"
                        value={locationState}
                        onChange={e => setLocationState(e.target.value)}
                        className="w-full px-4 py-3 rounded-xl text-sm sd-input outline-none appearance-none"
                      >
                        {NIG_STATES.map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </Field>
                  </div>

                  <div className="flex items-center justify-between p-4 rounded-xl sd-card-2">
                    <div>
                      <p className="text-white text-sm font-medium">Multi-campus / Group of Schools?</p>
                      <p className="text-slate-500 text-xs mt-0.5">Enables centralized executive reporting across all campuses.</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setIsGroup(g => !g)}
                      className="relative h-6 w-11 rounded-full transition-all cursor-pointer shrink-0"
                      style={{ background: isGroup ? '#22c55e' : 'rgba(148,163,184,0.4)' }}
                    >
                      <div className="absolute top-1 h-4 w-4 rounded-full bg-white transition-all duration-200" style={{ left: isGroup ? '24px' : '4px' }} />
                    </button>
                  </div>

                  <div className="pt-2 flex justify-end">
                    <button
                      type="button"
                      disabled={!canStep1}
                      onClick={() => setStep(2)}
                      className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-sm text-white transition-all cursor-pointer disabled:opacity-40"
                      style={{ background: 'linear-gradient(135deg, #22c55e, #0ea5e9)' }}
                    >
                      Registrar Details <ChevronRight className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              )}

              {/* STEP 2 */}
              {step === 2 && (
                <div className="space-y-5">
                  <div>
                    <h4 className="text-white font-bold text-base mb-0.5">Registrar Contact</h4>
                    <p className="text-slate-500 text-xs">Administrative representative details for your institution.</p>
                  </div>

                  <Field label="Full Name" id="wiz-auth-name">
                    <input id="wiz-auth-name" type="text" required placeholder="e.g. Mrs. Adunola Okafor"
                      value={authName} onChange={e => setAuthName(e.target.value)}
                      className="w-full px-4 py-3 rounded-xl text-sm sd-input placeholder-slate-600 outline-none" />
                  </Field>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Field label="Email Address" id="wiz-auth-email">
                      <input id="wiz-auth-email" type="email" required placeholder="principal@school.com"
                        value={authEmail} onChange={e => setAuthEmail(e.target.value)}
                        className="w-full px-4 py-3 rounded-xl text-sm sd-input placeholder-slate-600 outline-none" />
                    </Field>
                    <Field label="Phone Number" id="wiz-auth-phone">
                      <input id="wiz-auth-phone" type="tel" required placeholder="+234 80x xxx xxxx"
                        value={authPhone} onChange={e => setAuthPhone(e.target.value)}
                        className="w-full px-4 py-3 rounded-xl text-sm sd-input placeholder-slate-600 outline-none" />
                    </Field>
                  </div>

                  <div className="p-4 rounded-xl space-y-3" style={{ background: 'rgba(34,197,94,0.05)', border: '1px solid rgba(34,197,94,0.15)' }}>
                    <div className="flex justify-between items-center">
                      <label className="text-white text-sm font-medium">Estimated Student Count</label>
                      <span className="text-green-400 font-mono font-bold text-sm">{studentSize}</span>
                    </div>
                    <input type="range" min="50" max="3000" step="50" value={studentSize}
                      onChange={e => setStudentSize(parseInt(e.target.value))}
                      className="w-full h-2 rounded-lg appearance-none cursor-pointer accent-green-500"
                      style={{ background: 'rgba(34,197,94,0.2)' }} />
                    <p className="text-slate-500 text-[10px]">Staff and teachers are always free. This only estimates platform provisioning scale.</p>
                  </div>

                  <div className="flex items-center justify-between pt-2">
                    <button type="button" onClick={() => setStep(1)} className="px-5 py-3 rounded-xl border border-white/10 text-slate-300 text-sm font-medium hover:bg-white/5 transition-all cursor-pointer">
                      Back
                    </button>
                    <button type="button" disabled={!canStep2} onClick={() => setStep(3)}
                      className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-sm text-white transition-all cursor-pointer disabled:opacity-40"
                      style={{ background: 'linear-gradient(135deg, #22c55e, #0ea5e9)' }}>
                      Review & Confirm <ChevronRight className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              )}

              {/* STEP 3 */}
              {step === 3 && (
                <div className="space-y-5">
                  <div>
                    <h4 className="text-white font-bold text-base mb-0.5">Review & Confirm</h4>
                    <p className="text-slate-500 text-xs">Confirm your plan details before provisioning your workspace.</p>
                  </div>

                  {/* Plan summary */}
                  <div className="rounded-xl p-4 space-y-2.5 sd-card">
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500">School Code</span>
                      <span className="font-mono font-bold" style={{ color: '#22c55e' }}>{schoolCode}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500">Institution</span>
                      <span className="text-white font-medium">{schoolName}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500">Type</span>
                      <span className="text-white font-medium">{schoolType === 'K12' ? 'K-12 (Termly)' : 'Non-K12 (Monthly)'}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500">State</span>
                      <span className="text-white font-medium">{locationState}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500">Student Seats</span>
                      <span className="text-white font-mono font-medium">{studentSize}</span>
                    </div>
                  </div>

                  {/* Child Monitor add-on (K-12 only) */}
                  {schoolType === 'K12' && (
                    <div className="flex items-center justify-between p-4 rounded-xl transition-all sd-card-2"
                      style={{
                        background: kidMonitor ? 'rgba(34,197,94,0.06)' : undefined,
                        borderColor: kidMonitor ? 'rgba(34,197,94,0.3)' : undefined,
                      }}>
                      <div className="flex items-center gap-3">
                        <Eye className="h-4 w-4 shrink-0" style={{ color: kidMonitor ? '#22c55e' : '#475569' }} />
                        <div>
                          <p className="text-white text-sm font-medium">Child Monitor <span className="text-green-400 text-xs font-mono">+₦1,000/term</span></p>
                          <p className="text-slate-500 text-[10px] mt-0.5">Optional — real-time location, screen & activity tracking.</p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setKidMonitor(k => !k)}
                        className="relative h-6 w-11 rounded-full transition-all cursor-pointer shrink-0"
                        style={{ background: kidMonitor ? '#22c55e' : 'rgba(148,163,184,0.4)' }}
                      >
                        <div className="absolute top-1 h-4 w-4 rounded-full bg-white transition-all duration-200" style={{ left: kidMonitor ? '24px' : '4px' }} />
                      </button>
                    </div>
                  )}

                  {/* Pricing line */}
                  <div className="p-3.5 rounded-xl" style={{ background: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.2)' }}>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400 text-xs">Your pricing plan</span>
                      <span className="text-emerald-400 font-bold text-sm">{pricing}</span>
                    </div>
                  </div>

                  {/* Terms & Conditions consent */}
                  <div className="p-3.5 rounded-xl flex items-start gap-3 sd-card">
                    <input id="wiz-consent" type="checkbox" required checked={consent}
                      onChange={e => setConsent(e.target.checked)}
                      className="mt-0.5 h-4 w-4 rounded cursor-pointer accent-green-500 shrink-0" />
                    <label htmlFor="wiz-consent" className="text-slate-400 text-[11px] leading-relaxed cursor-pointer">
                      I agree to Schooldom's <strong className="text-slate-300">Terms &amp; Conditions</strong> and Privacy Charter, and confirm this institution consents to student record processing in compliance with the <strong className="text-slate-300">Nigeria Data Protection Act (NDPA)</strong>.
                    </label>
                  </div>

                  <div className="p-3 rounded-xl flex items-start gap-2.5" style={{ background: 'rgba(34,197,94,0.05)', border: '1px solid rgba(34,197,94,0.12)' }}>
                    <ShieldCheck className="h-4 w-4 text-green-400 shrink-0 mt-0.5" />
                    <p className="text-slate-400 text-[11px] leading-relaxed">
                      No subscription fees are charged until Term 1 classes resume. Confirming provisions your secure cloud sandbox.
                    </p>
                  </div>

                  <div className="flex items-center justify-between pt-2">
                    <button type="button" onClick={() => setStep(2)} className="px-5 py-3 rounded-xl border border-white/10 text-slate-300 text-sm font-medium hover:bg-white/5 transition-all cursor-pointer">
                      Back
                    </button>
                    <button type="submit" disabled={!consent}
                      className="px-7 py-3 rounded-xl font-bold text-sm text-white transition-all cursor-pointer disabled:opacity-40"
                      style={{ background: 'linear-gradient(135deg, #22c55e, #0ea5e9)' }}>
                      Provision & Deploy →
                    </button>
                  </div>
                </div>
              )}
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="block text-slate-400 text-xs font-medium mb-1.5">{label}</label>
      {children}
    </div>
  );
}
