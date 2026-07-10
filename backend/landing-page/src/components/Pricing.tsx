import { useState, useEffect, useRef } from 'react';
import { Check, Zap, School, Eye } from 'lucide-react';

interface PricingProps {
  onGetStarted: () => void;
}

export default function Pricing({ onGetStarted }: PricingProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [kidMonitor, setKidMonitor] = useState(false);

  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setVisible(true); }, { threshold: 0.15 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);

  const plans = [
    {
      icon: School,
      name: 'K-12 Schools',
      badge: 'Nursery · Primary · Secondary',
      price: '₦500',
      cycle: '/ term  (3 months 15 days)',
      desc: 'Full platform access per term for structured K-12 institutions.',
      color: '#0ea5e9',
      popular: true,
      features: [
        'Unlimited staff & teacher accounts',
        'Full CBT exam engine (hybrid offline)',
        'Fee collection & Paystack gateway',
        'Auto report card generation',
        'QR / biometric attendance',
        'Parent portal & SMS alerts',
        'Student enrollment & profiles',
        'Academic calendar & timetable',
      ],
      addon: {
        name: 'Kid Monitor',
        icon: Eye,
        price: '₦1,000',
        cycle: '/ term',
        desc: "Real-time location, screen & activity monitoring for students' devices. Parents get a live dashboard.",
        optional: true,
      },
      cta: 'Onboard Your School',
    },
    {
      icon: Zap,
      name: 'Non-K12 Institutions',
      badge: 'Vocational · Tertiary · Training',
      price: '₦200',
      cycle: '/ month',
      desc: 'Flexible monthly billing for vocational centres, tutoring hubs, and continuing education.',
      color: '#10b981',
      popular: false,
      features: [
        'Unlimited staff accounts',
        'CBT exam engine (online)',
        'Fee & payment tracking',
        'Student enrollment & profiles',
        'Attendance tracking',
        'Basic report generation',
        'Email & chat support',
      ],
      addon: null,
      cta: 'Get Started',
    },
  ];

  return (
    <section id="pricing" className="py-28 px-4 relative" ref={ref}>
      <div className="max-w-5xl mx-auto">
        <div
          className="text-center mb-16 transition-all duration-700"
          style={{ opacity: visible ? 1 : 0, transform: visible ? 'translateY(0)' : 'translateY(30px)' }}
        >
          <span
            className="text-xs font-bold uppercase tracking-widest px-4 py-1.5 rounded-full border mb-4 inline-block"
            style={{ color: '#f59e0b', background: 'rgba(245,158,11,0.08)', borderColor: 'rgba(245,158,11,0.2)' }}
          >
            Transparent Pricing
          </span>
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Flat rates, zero surprises,{' '}
            <span style={{ background: 'linear-gradient(90deg, #f59e0b, #ef4444)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
              pay per cycle
            </span>
          </h2>
          <p className="text-slate-400 max-w-lg mx-auto">No setup fees. No per-student charges. One flat rate covers your entire school.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
          {plans.map((plan, pi) => {
            const Icon = plan.icon;
            return (
              <div
                key={plan.name}
                className="relative rounded-2xl border flex flex-col transition-all duration-500"
                style={{
                  border: plan.popular ? `1px solid ${plan.color}40` : '1px solid rgba(255,255,255,0.06)',
                  background: plan.popular ? `rgba(14,165,233,0.05)` : 'rgba(255,255,255,0.02)',
                  opacity: visible ? 1 : 0,
                  transform: visible ? 'translateY(0)' : 'translateY(40px)',
                  transitionDelay: `${pi * 150}ms`,
                }}
              >
                {plan.popular && (
                  <div
                    className="absolute -top-3 left-1/2 -translate-x-1/2 text-white text-[10px] font-bold px-4 py-1 rounded-full whitespace-nowrap"
                    style={{ background: `linear-gradient(90deg, ${plan.color}, #6366f1)` }}
                  >
                    MOST COMMON
                  </div>
                )}

                <div className="p-7">
                  <div className="flex items-start justify-between mb-5">
                    <div
                      className="h-11 w-11 rounded-xl flex items-center justify-center"
                      style={{ background: `${plan.color}18`, border: `1px solid ${plan.color}30` }}
                    >
                      <Icon className="h-5 w-5" style={{ color: plan.color }} />
                    </div>
                    <span
                      className="text-[10px] font-bold px-3 py-1 rounded-full border"
                      style={{ color: plan.color, background: `${plan.color}10`, borderColor: `${plan.color}30` }}
                    >
                      {plan.badge}
                    </span>
                  </div>

                  <h3 className="text-white font-bold text-xl mb-1">{plan.name}</h3>
                  <p className="text-slate-500 text-sm mb-6">{plan.desc}</p>

                  <div className="flex items-end gap-2 mb-2">
                    <span className="text-white text-5xl font-bold">{plan.price}</span>
                    <span className="text-slate-400 text-sm mb-2">{plan.cycle}</span>
                  </div>

                  <div className="space-y-3 mt-6 mb-6">
                    {plan.features.map(f => (
                      <div key={f} className="flex items-start gap-3">
                        <div
                          className="h-5 w-5 rounded-full flex items-center justify-center shrink-0 mt-px"
                          style={{ background: `${plan.color}20` }}
                        >
                          <Check className="h-3 w-3" style={{ color: plan.color }} />
                        </div>
                        <span className="text-slate-300 text-sm">{f}</span>
                      </div>
                    ))}
                  </div>

                  {plan.addon && (
                    <div
                      className="rounded-xl p-4 mb-6 border"
                      style={{ background: 'rgba(255,255,255,0.03)', borderColor: kidMonitor ? 'rgba(168,85,247,0.4)' : 'rgba(255,255,255,0.07)' }}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Eye className="h-4 w-4 text-violet-400" />
                          <span className="text-white text-sm font-semibold">{plan.addon.name}</span>
                          <span className="text-[10px] font-bold text-violet-400 bg-violet-500/10 border border-violet-500/20 px-2 py-0.5 rounded-full">OPTIONAL</span>
                        </div>
                        <button
                          onClick={() => setKidMonitor(k => !k)}
                          className="relative h-6 w-11 rounded-full transition-all cursor-pointer shrink-0"
                          style={{ background: kidMonitor ? '#8b5cf6' : 'rgba(255,255,255,0.1)' }}
                        >
                          <div
                            className="absolute top-1 h-4 w-4 rounded-full bg-white transition-all duration-200"
                            style={{ left: kidMonitor ? '24px' : '4px' }}
                          />
                        </button>
                      </div>
                      <p className="text-slate-500 text-xs leading-relaxed mb-2">{plan.addon.desc}</p>
                      <div className="flex items-center gap-1.5">
                        <span className="text-violet-400 text-lg font-bold">{plan.addon.price}</span>
                        <span className="text-slate-500 text-xs">{plan.addon.cycle}</span>
                        {kidMonitor && <span className="text-emerald-400 text-xs ml-1 font-semibold">✓ Added</span>}
                      </div>
                    </div>
                  )}

                  {plan.addon && kidMonitor && (
                    <div
                      className="rounded-xl p-3 mb-4 flex items-center justify-between"
                      style={{ background: 'rgba(14,165,233,0.06)', border: '1px solid rgba(14,165,233,0.15)' }}
                    >
                      <span className="text-slate-400 text-sm">Total per term</span>
                      <span className="text-white font-bold text-lg">₦1,500</span>
                    </div>
                  )}

                  <button
                    onClick={onGetStarted}
                    className="w-full py-3.5 rounded-xl font-semibold text-sm transition-all cursor-pointer hover:opacity-90 active:scale-[0.98]"
                    style={
                      plan.popular
                        ? { background: `linear-gradient(135deg, ${plan.color}, #6366f1)`, color: '#fff' }
                        : { border: `1px solid ${plan.color}40`, color: plan.color, background: `${plan.color}08` }
                    }
                  >
                    {plan.cta}
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        <p
          className="text-center text-slate-600 text-xs mt-8 transition-all duration-700 delay-300"
          style={{ opacity: visible ? 1 : 0 }}
        >
          All plans include SSL, 99.9% uptime, daily automated backups, and unlimited admin & teacher accounts.
        </p>
      </div>
    </section>
  );
}
