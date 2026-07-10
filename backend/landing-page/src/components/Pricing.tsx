import { Check, Zap, Building2, Crown } from 'lucide-react';

const PLANS = [
  {
    icon: Zap,
    name: 'Starter',
    price: '₦15,000',
    period: '/month',
    desc: 'Perfect for small schools just getting started.',
    color: '#0ea5e9',
    features: [
      'Up to 200 students',
      'Fee collection & receipts',
      'Basic attendance tracking',
      'Student profiles & enrollment',
      'Basic report cards',
      'Email support',
    ],
    cta: 'Get Started',
    popular: false,
  },
  {
    icon: Building2,
    name: 'Growth',
    price: '₦35,000',
    period: '/month',
    desc: 'The complete package for growing schools.',
    color: '#8b5cf6',
    features: [
      'Up to 1,000 students',
      'Everything in Starter',
      'CBT exam engine (online)',
      'Paystack payment gateway',
      'Parent portal & SMS alerts',
      'Biometric attendance (QR)',
      'Auto report card generation',
      'Priority support',
    ],
    cta: 'Start Free Trial',
    popular: true,
  },
  {
    icon: Crown,
    name: 'Enterprise',
    price: 'Custom',
    period: '',
    desc: 'For large schools and multi-campus networks.',
    color: '#10b981',
    features: [
      'Unlimited students',
      'Everything in Growth',
      'Offline desktop CBT (Win7)',
      'AI Secretary assistant',
      'HR & payroll module',
      'Multi-campus dashboard',
      'Custom domain & branding',
      'Dedicated account manager',
      'SLA & on-site training',
    ],
    cta: 'Contact Sales',
    popular: false,
  },
];

export default function Pricing() {
  const handleCta = (planName: string) => {
    if (planName === 'Enterprise') {
      window.location.href = 'mailto:solomonomotayo96@gmail.com?subject=Enterprise Enquiry';
    } else {
      window.location.href = '/onboarding/wizard/';
    }
  };

  return (
    <section id="pricing" className="py-28 px-4 relative">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <span
            className="text-xs font-bold uppercase tracking-widest px-4 py-1.5 rounded-full border mb-4 inline-block"
            style={{ color: '#f59e0b', background: 'rgba(245,158,11,0.08)', borderColor: 'rgba(245,158,11,0.2)' }}
          >
            Simple Pricing
          </span>
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Plans that scale with{' '}
            <span style={{ background: 'linear-gradient(90deg, #f59e0b, #ef4444)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
              your school
            </span>
          </h2>
          <p className="text-slate-400 max-w-lg mx-auto">No setup fees. No hidden charges. Cancel anytime.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch">
          {PLANS.map((plan) => {
            const Icon = plan.icon;
            return (
              <div
                key={plan.name}
                className="relative rounded-2xl border flex flex-col transition-all duration-300 hover:-translate-y-1"
                style={{
                  border: plan.popular ? `1px solid ${plan.color}40` : '1px solid rgba(255,255,255,0.06)',
                  background: plan.popular ? `rgba(139,92,246,0.06)` : 'rgba(255,255,255,0.02)',
                }}
              >
                {plan.popular && (
                  <div
                    className="absolute -top-3 left-1/2 -translate-x-1/2 text-white text-[10px] font-bold px-4 py-1 rounded-full"
                    style={{ background: `linear-gradient(90deg, ${plan.color}, #ec4899)` }}
                  >
                    MOST POPULAR
                  </div>
                )}

                <div className="p-7 flex-1">
                  <div
                    className="h-11 w-11 rounded-xl flex items-center justify-center mb-5"
                    style={{ background: `${plan.color}18`, border: `1px solid ${plan.color}30` }}
                  >
                    <Icon className="h-5 w-5" style={{ color: plan.color }} />
                  </div>

                  <h3 className="text-white font-bold text-xl mb-1">{plan.name}</h3>
                  <p className="text-slate-500 text-sm mb-5">{plan.desc}</p>

                  <div className="flex items-end gap-1 mb-6">
                    <span className="text-white text-4xl font-bold">{plan.price}</span>
                    {plan.period && <span className="text-slate-500 text-sm mb-1">{plan.period}</span>}
                  </div>

                  <div className="space-y-3">
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
                </div>

                <div className="p-7 pt-0">
                  <button
                    onClick={() => handleCta(plan.name)}
                    className="w-full py-3 rounded-xl font-semibold text-sm transition-all cursor-pointer"
                    style={
                      plan.popular
                        ? { background: `linear-gradient(135deg, ${plan.color}, #ec4899)`, color: '#fff' }
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

        <p className="text-center text-slate-600 text-xs mt-8">
          All plans include SSL, 99.9% uptime SLA, and automatic database backups.
        </p>
      </div>
    </section>
  );
}
