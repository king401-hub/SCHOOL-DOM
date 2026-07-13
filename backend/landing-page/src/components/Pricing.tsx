import { useRef, useState, useEffect } from 'react';
import { CheckCircle, Star, Zap, Shield, Users, Eye } from 'lucide-react';

function useVisible(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setVisible(true); }, { threshold });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, visible };
}

const K12_FEATURES = [
  'Full student management & admissions',
  'Hybrid CBT exam engine (online + offline)',
  'Fee collection with secure payment processors',
  'QR attendance tracking',
  'Auto-generated report cards & transcripts',
  'Parent portal (mobile-friendly)',
  'HR & staff payroll management',
  'Bulk ID / PVC card generator',
  'Multi-campus central dashboard',
  'NDPA compliant data handling',
  'Priority support & onboarding',
];

const NON_K12_FEATURES = [
  'Student enrollment management',
  'Hybrid CBT exam engine',
  'Fee collection & digital receipts',
  'Attendance tracking',
  'Course results & transcripts',
  'Staff management',
  'Analytics dashboard',
  'NDPA compliant storage',
];

export default function Pricing() {
  const { ref, visible } = useVisible(0.1);
  const [kidMonitor, setKidMonitor] = useState(false);

  return (
    <section id="pricing" ref={ref} className="py-28 px-4 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(34,197,94,0.05) 0%, transparent 60%)' }} />

      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-14"
          style={{ opacity: visible ? 1 : 0, transform: visible ? 'none' : 'translateY(24px)', transition: 'all 0.7s ease' }}>
          <span className="badge badge-green mb-4">Simple Pricing</span>
          <h2 className="font-display font-black text-4xl sm:text-5xl text-white mb-4">
            Fair pricing, <span className="gradient-text">full power</span>
          </h2>
          <p className="text-slate-400 max-w-lg mx-auto">No setup fees. No per-student charges. No surprises. Just a flat rate that keeps every school covered.</p>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* K-12 Card */}
          <div className="relative rounded-3xl p-8 overflow-hidden sd-card"
            style={{
              border: '1px solid rgba(34,197,94,0.25)',
              boxShadow: '0 0 60px rgba(34,197,94,0.08), inset 0 1px 0 rgba(34,197,94,0.08)',
              opacity: visible ? 1 : 0,
              transform: visible ? 'none' : 'translateY(30px)',
              transition: 'all 0.7s ease 0.1s',
            }}>
            <div className="absolute top-4 right-4">
              <span className="flex items-center gap-1 badge badge-green text-[9px]">
                <Star className="h-2.5 w-2.5 fill-current" /> Most Popular
              </span>
            </div>
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-64 h-32 pointer-events-none"
              style={{ background: 'radial-gradient(ellipse, rgba(34,197,94,0.1) 0%, transparent 70%)', filter: 'blur(20px)' }} />

            <div className="relative">
              <div className="flex items-center gap-3 mb-6">
                <div className="h-11 w-11 rounded-2xl flex items-center justify-center"
                  style={{ background: 'rgba(34,197,94,0.15)', border: '1px solid rgba(34,197,94,0.3)' }}>
                  <Users className="h-5 w-5" style={{ color: '#22c55e' }} />
                </div>
                <div>
                  <h3 className="font-display font-black text-white text-xl">K-12 Schools</h3>
                  <p className="text-slate-500 text-xs">Nursery · Primary · Secondary</p>
                </div>
              </div>

              <div className="mb-6">
                <div className="flex items-end gap-2">
                  <span className="font-display font-black text-5xl" style={{ color: '#22c55e' }}>₦500</span>
                  <div className="mb-2">
                    <p className="text-white text-sm font-semibold">/ term</p>
                    <p className="text-slate-500 text-xs">(3 months 15 days)</p>
                  </div>
                </div>
                <p className="text-slate-500 text-xs mt-2">Flat rate — unlimited students & staff</p>
              </div>

              {/* Child Monitor Toggle */}
              <div className="rounded-2xl p-4 mb-6 transition-all sd-card"
                style={{
                  background: kidMonitor ? 'rgba(34,197,94,0.06)' : undefined,
                  borderColor: kidMonitor ? 'rgba(34,197,94,0.3)' : undefined,
                }}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Eye className="h-4 w-4 shrink-0" style={{ color: kidMonitor ? '#22c55e' : '#475569' }} />
                    <div>
                      <p className="text-white text-sm font-semibold">Child Monitor</p>
                      <p className="text-slate-500 text-[10px]">Real-time location + activity tracking</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono font-bold" style={{ color: '#22c55e' }}>+₦1,000/term</span>
                    <button onClick={() => setKidMonitor(k => !k)}
                      className="relative h-6 w-11 rounded-full transition-all cursor-pointer shrink-0"
                      style={{ background: kidMonitor ? '#22c55e' : 'rgba(255,255,255,0.1)' }}>
                      <div className="absolute top-1 h-4 w-4 rounded-full bg-white shadow-sm transition-all duration-200"
                        style={{ left: kidMonitor ? 24 : 4 }} />
                    </button>
                  </div>
                </div>
                {kidMonitor && (
                  <div className="mt-3 pt-3 border-t border-white/5 flex items-center justify-between">
                    <span className="text-slate-400 text-xs">Total per term</span>
                    <span className="font-display font-black text-lg" style={{ color: '#22c55e' }}>₦1,500</span>
                  </div>
                )}
              </div>

              <ul className="space-y-2.5 mb-8">
                {K12_FEATURES.map(f => (
                  <li key={f} className="flex items-center gap-3 text-slate-300 text-sm">
                    <CheckCircle className="h-4 w-4 shrink-0" style={{ color: '#22c55e' }} />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Non-K12 Card */}
          <div className="relative rounded-3xl p-8 overflow-hidden sd-card"
            style={{
              border: '1px solid rgba(14,165,233,0.2)',
              boxShadow: '0 0 40px rgba(14,165,233,0.05)',
              opacity: visible ? 1 : 0,
              transform: visible ? 'none' : 'translateY(30px)',
              transition: 'all 0.7s ease 0.25s',
            }}>
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-64 h-32 pointer-events-none"
              style={{ background: 'radial-gradient(ellipse, rgba(14,165,233,0.07) 0%, transparent 70%)', filter: 'blur(20px)' }} />

            <div className="relative">
              <div className="flex items-center gap-3 mb-6">
                <div className="h-11 w-11 rounded-2xl flex items-center justify-center"
                  style={{ background: 'rgba(14,165,233,0.12)', border: '1px solid rgba(14,165,233,0.25)' }}>
                  <Zap className="h-5 w-5" style={{ color: '#0ea5e9' }} />
                </div>
                <div>
                  <h3 className="font-display font-black text-white text-xl">Non-K12</h3>
                  <p className="text-slate-500 text-xs">Vocational · Tertiary · Academies</p>
                </div>
              </div>

              <div className="mb-6">
                <div className="flex items-end gap-2">
                  <span className="font-display font-black text-5xl" style={{ color: '#0ea5e9' }}>₦200</span>
                  <div className="mb-2">
                    <p className="text-white text-sm font-semibold">/ month</p>
                    <p className="text-slate-500 text-xs">billed monthly</p>
                  </div>
                </div>
                <p className="text-slate-500 text-xs mt-2">Flat rate — unlimited students & staff</p>
              </div>

              <div className="h-[120px] mb-6 rounded-2xl flex items-center px-4 sd-card">
                <div className="flex items-center gap-3">
                  <Shield className="h-5 w-5 text-slate-500" />
                  <div>
                    <p className="text-white text-sm font-semibold">Full Platform Access</p>
                    <p className="text-slate-500 text-xs mt-1">All modules included, no add-ons required</p>
                  </div>
                </div>
              </div>

              <ul className="space-y-2.5 mb-8">
                {NON_K12_FEATURES.map(f => (
                  <li key={f} className="flex items-center gap-3 text-slate-300 text-sm">
                    <CheckCircle className="h-4 w-4 shrink-0" style={{ color: '#0ea5e9' }} />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Guarantees row */}
        <div className="mt-10 grid grid-cols-2 sm:grid-cols-4 gap-4"
          style={{ opacity: visible ? 1 : 0, transition: 'opacity 0.7s ease 0.5s' }}>
          {[
            { icon: Shield, label: 'No setup fee', color: '#22c55e' },
            { icon: Zap, label: 'Start in 4 minutes', color: '#0ea5e9' },
            { icon: Users, label: 'Unlimited users', color: '#8b5cf6' },
            { icon: Star, label: 'Cancel anytime', color: '#f59e0b' },
          ].map(g => {
            const Icon = g.icon;
            return (
              <div key={g.label} className="flex items-center gap-2 justify-center px-4 py-3 rounded-xl sd-card">
                <Icon className="h-4 w-4 shrink-0" style={{ color: g.color }} />
                <span className="text-slate-400 text-xs">{g.label}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
