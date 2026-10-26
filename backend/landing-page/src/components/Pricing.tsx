import { useRef, useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { CheckCircle, ArrowRight, Star, Zap, Shield, Users, Eye, ScanLine } from 'lucide-react';

const K12_COLOR = '#c9a24e';
const NONK12_COLOR = '#8a7246';
const GATE_COLOR = '#a86a4a';

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

export default function Pricing() {
  const { t } = useTranslation();
  const { ref, visible } = useVisible(0.1);
  const [kidMonitor, setKidMonitor] = useState(false);
  const [gatePlan, setGatePlan] = useState<'basic' | 'premium'>('basic');

  const K12_FEATURES = t('pricing.k12.features', { returnObjects: true }) as string[];
  const NON_K12_FEATURES = t('pricing.nonK12.features', { returnObjects: true }) as string[];
  const SCHOOLGATE_FEATURES: Record<'basic' | 'premium', string[]> = {
    basic: t('pricing.schoolgate.featuresBasic', { returnObjects: true }) as string[],
    premium: t('pricing.schoolgate.featuresPremium', { returnObjects: true }) as string[],
  };

  return (
    <section id="pricing" ref={ref} className="py-28 px-4 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(201,162,78,0.04) 0%, transparent 60%)' }} />

      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-14"
          style={{ opacity: visible ? 1 : 0, transform: visible ? 'none' : 'translateY(20px)', transition: 'all 0.7s ease' }}>
          <span className="badge mb-4">{t('pricing.badge')}</span>
          <h2 className="font-display font-semibold text-4xl sm:text-5xl text-white mb-4">
            {t('pricing.title')} <span className="gradient-text">{t('pricing.titleHighlight')}</span>
          </h2>
          <p className="text-slate-400 max-w-lg mx-auto">{t('pricing.subtitle')}</p>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* K-12 Card */}
          <div className="relative rounded-3xl p-8 overflow-hidden sd-card"
            style={{
              border: `1px solid ${K12_COLOR}40`,
              opacity: visible ? 1 : 0,
              transform: visible ? 'none' : 'translateY(24px)',
              transition: 'all 0.7s ease 0.1s',
            }}>
            <div className="absolute top-4 right-4">
              <span className="flex items-center gap-1 badge text-[9px]">
                <Star className="h-2.5 w-2.5 fill-current" /> {t('pricing.mostPopular')}
              </span>
            </div>

            <div className="relative">
              <div className="flex items-center gap-3 mb-6">
                <div className="h-11 w-11 rounded-2xl flex items-center justify-center"
                  style={{ background: `${K12_COLOR}22`, border: `1px solid ${K12_COLOR}50` }}>
                  <Users className="h-5 w-5" style={{ color: K12_COLOR }} />
                </div>
                <div>
                  <h3 className="font-display font-semibold text-white text-xl">{t('pricing.k12.name')}</h3>
                  <p className="text-slate-500 text-xs">{t('pricing.k12.tagline')}</p>
                </div>
              </div>

              <div className="mb-6">
                <div className="flex items-end gap-2">
                  <span className="font-display font-semibold text-5xl" style={{ color: K12_COLOR }}>₦500</span>
                  <div className="mb-2">
                    <p className="text-white text-sm font-semibold">{t('pricing.k12.perTerm')}</p>
                    <p className="text-slate-500 text-xs">{t('pricing.k12.termLength')}</p>
                  </div>
                </div>
                <p className="text-slate-500 text-xs mt-2">{t('pricing.k12.flatRate')}</p>
              </div>

              {/* Child Monitor Toggle */}
              <div className="rounded-2xl p-4 mb-6 transition-all sd-card"
                style={{
                  background: kidMonitor ? `${K12_COLOR}10` : undefined,
                  borderColor: kidMonitor ? `${K12_COLOR}50` : undefined,
                }}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Eye className="h-4 w-4 shrink-0" style={{ color: kidMonitor ? K12_COLOR : '#5a554d' }} />
                    <div>
                      <p className="text-white text-sm font-semibold">{t('pricing.childMonitor.title')}</p>
                      <p className="text-slate-500 text-[10px]">{t('pricing.childMonitor.desc')}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono font-bold" style={{ color: K12_COLOR }}>{t('pricing.childMonitor.price')}</span>
                    <button onClick={() => setKidMonitor(k => !k)}
                      className="relative h-6 w-11 rounded-full transition-all cursor-pointer shrink-0"
                      style={{ background: kidMonitor ? K12_COLOR : 'rgba(255,255,255,0.12)' }}>
                      <div className="absolute top-1 h-4 w-4 rounded-full bg-white shadow-sm transition-all duration-200"
                        style={{ left: kidMonitor ? 24 : 4 }} />
                    </button>
                  </div>
                </div>
                {kidMonitor && (
                  <div className="mt-3 pt-3 border-t border-white/5 flex items-center justify-between">
                    <span className="text-slate-400 text-xs">{t('pricing.childMonitor.totalPerTerm')}</span>
                    <span className="font-display font-semibold text-lg" style={{ color: K12_COLOR }}>₦1,500</span>
                  </div>
                )}
              </div>

              <ul className="space-y-2.5 mb-8">
                {K12_FEATURES.map(f => (
                  <li key={f} className="flex items-center gap-3 text-slate-300 text-sm">
                    <CheckCircle className="h-4 w-4 shrink-0" style={{ color: K12_COLOR }} />
                    {f}
                  </li>
                ))}
              </ul>

              <a href="/#/signup?tier=k12" className="w-full btn-primary justify-center py-4 text-base">
                {t('pricing.k12.cta')} <ArrowRight className="h-4 w-4" />
              </a>
            </div>
          </div>

          {/* Non-K12 Card */}
          <div className="relative rounded-3xl p-8 overflow-hidden sd-card"
            style={{
              border: `1px solid ${NONK12_COLOR}40`,
              opacity: visible ? 1 : 0,
              transform: visible ? 'none' : 'translateY(24px)',
              transition: 'all 0.7s ease 0.25s',
            }}>
            <div className="relative">
              <div className="flex items-center gap-3 mb-6">
                <div className="h-11 w-11 rounded-2xl flex items-center justify-center"
                  style={{ background: `${NONK12_COLOR}22`, border: `1px solid ${NONK12_COLOR}50` }}>
                  <Zap className="h-5 w-5" style={{ color: NONK12_COLOR }} />
                </div>
                <div>
                  <h3 className="font-display font-semibold text-white text-xl">{t('pricing.nonK12.name')}</h3>
                  <p className="text-slate-500 text-xs">{t('pricing.nonK12.tagline')}</p>
                </div>
              </div>

              <div className="mb-6">
                <div className="flex items-end gap-2">
                  <span className="font-display font-semibold text-5xl" style={{ color: NONK12_COLOR }}>₦200</span>
                  <div className="mb-2">
                    <p className="text-white text-sm font-semibold">{t('pricing.nonK12.perMonth')}</p>
                    <p className="text-slate-500 text-xs">{t('pricing.nonK12.billedMonthly')}</p>
                  </div>
                </div>
                <p className="text-slate-500 text-xs mt-2">{t('pricing.nonK12.flatRate')}</p>
              </div>

              <div className="h-[120px] mb-6 rounded-2xl flex items-center px-4 sd-card">
                <div className="flex items-center gap-3">
                  <Shield className="h-5 w-5 text-slate-500" />
                  <div>
                    <p className="text-white text-sm font-semibold">{t('pricing.nonK12.fullAccess')}</p>
                    <p className="text-slate-500 text-xs mt-1">{t('pricing.nonK12.fullAccessDesc')}</p>
                  </div>
                </div>
              </div>

              <ul className="space-y-2.5 mb-8">
                {NON_K12_FEATURES.map(f => (
                  <li key={f} className="flex items-center gap-3 text-slate-300 text-sm">
                    <CheckCircle className="h-4 w-4 shrink-0" style={{ color: NONK12_COLOR }} />
                    {f}
                  </li>
                ))}
              </ul>

              <a href="/#/signup?tier=non_k12"
                className="w-full py-4 rounded-2xl font-semibold text-base text-white cursor-pointer hover:opacity-90 transition-all flex items-center justify-center"
                style={{ background: `${NONK12_COLOR}22`, border: `1px solid ${NONK12_COLOR}55` }}>
                {t('pricing.nonK12.cta')} <ArrowRight className="h-4 w-4 inline ml-2" />
              </a>
            </div>
          </div>

          {/* SchoolGate Card */}
          <div className="relative rounded-3xl p-8 overflow-hidden sd-card"
            style={{
              border: `1px solid ${GATE_COLOR}40`,
              opacity: visible ? 1 : 0,
              transform: visible ? 'none' : 'translateY(24px)',
              transition: 'all 0.7s ease 0.4s',
            }}>
            <div className="absolute top-4 right-4">
              <span className="badge text-[9px]" style={{ background: `${GATE_COLOR}22`, border: `1px solid ${GATE_COLOR}50`, color: GATE_COLOR }}>
                {t('pricing.new')}
              </span>
            </div>

            <div className="relative">
              <div className="flex items-center gap-3 mb-6">
                <div className="h-11 w-11 rounded-2xl flex items-center justify-center"
                  style={{ background: `${GATE_COLOR}22`, border: `1px solid ${GATE_COLOR}50` }}>
                  <ScanLine className="h-5 w-5" style={{ color: GATE_COLOR }} />
                </div>
                <div>
                  <h3 className="font-display font-semibold text-white text-xl">{t('pricing.schoolgate.name')}</h3>
                  <p className="text-slate-500 text-xs">{t('pricing.schoolgate.tagline')}</p>
                </div>
              </div>

              {/* Basic / Premium toggle */}
              <div className="flex rounded-xl p-1 mb-6 sd-card" style={{ gap: 4 }}>
                {(['basic', 'premium'] as const).map(plan => (
                  <button key={plan} onClick={() => setGatePlan(plan)}
                    className="flex-1 py-2 rounded-lg text-xs font-bold capitalize transition-all cursor-pointer"
                    style={{
                      background: gatePlan === plan ? `${GATE_COLOR}28` : 'transparent',
                      color: gatePlan === plan ? GATE_COLOR : '#6b645b',
                    }}>
                    {plan === 'basic' ? t('pricing.schoolgate.basic') : t('pricing.schoolgate.premium')}
                  </button>
                ))}
              </div>

              <div className="mb-6">
                <div className="flex items-end gap-2">
                  <span className="font-display font-semibold text-5xl" style={{ color: GATE_COLOR }}>
                    ₦{gatePlan === 'premium' ? '1,500' : '700'}
                  </span>
                  <div className="mb-2">
                    <p className="text-white text-sm font-semibold">{t('pricing.schoolgate.perStudentTerm')}</p>
                  </div>
                </div>
                <p className="text-slate-500 text-xs mt-2">{t('pricing.schoolgate.deviceFee')}</p>
              </div>

              <ul className="space-y-2.5 mb-8">
                {SCHOOLGATE_FEATURES[gatePlan].map(f => (
                  <li key={f} className="flex items-center gap-3 text-slate-300 text-sm">
                    <CheckCircle className="h-4 w-4 shrink-0" style={{ color: GATE_COLOR }} />
                    {f}
                  </li>
                ))}
              </ul>

              <a href={`/#/signup?product=schoolgate&plan=${gatePlan}`}
                className="w-full py-4 rounded-2xl font-semibold text-base text-white cursor-pointer hover:opacity-90 transition-all flex items-center justify-center"
                style={{ background: `${GATE_COLOR}22`, border: `1px solid ${GATE_COLOR}55` }}>
                {t('pricing.schoolgate.cta')} <ArrowRight className="h-4 w-4 inline ml-2" />
              </a>
            </div>
          </div>
        </div>

        {/* Guarantees row */}
        <div className="mt-10 grid grid-cols-2 sm:grid-cols-4 gap-4"
          style={{ opacity: visible ? 1 : 0, transition: 'opacity 0.7s ease 0.5s' }}>
          {[
            { icon: Shield, label: t('pricing.guarantees.noSetupFee') },
            { icon: Zap, label: t('pricing.guarantees.startIn4Min') },
            { icon: Users, label: t('pricing.guarantees.unlimitedUsers') },
            { icon: Star, label: t('pricing.guarantees.cancelAnytime') },
          ].map(g => {
            const Icon = g.icon;
            return (
              <div key={g.label} className="flex items-center gap-2 justify-center px-4 py-3 rounded-xl sd-card">
                <Icon className="h-4 w-4 shrink-0" style={{ color: '#c9a24e' }} />
                <span className="text-slate-400 text-xs">{g.label}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
