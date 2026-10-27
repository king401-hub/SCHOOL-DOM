import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'motion/react';
import { CheckCircle, ArrowRight, Star, Zap, Shield, Users, Eye, ScanLine } from 'lucide-react';
import { Reveal } from '../lib/reveal';
import { useTilt } from '../lib/tilt';

const K12_COLOR = '#14532d';
const NONK12_COLOR = '#0d9488';
const GATE_COLOR = '#4d7c0f';
const EASE = [0.16, 1, 0.3, 1] as const;

export default function Pricing() {
  const { t } = useTranslation();
  const [kidMonitor, setKidMonitor] = useState(false);
  const [gatePlan, setGatePlan] = useState<'basic' | 'premium'>('basic');

  const K12_FEATURES = t('pricing.k12.features', { returnObjects: true }) as string[];
  const NON_K12_FEATURES = t('pricing.nonK12.features', { returnObjects: true }) as string[];
  const SCHOOLGATE_FEATURES: Record<'basic' | 'premium', string[]> = {
    basic: t('pricing.schoolgate.featuresBasic', { returnObjects: true }) as string[],
    premium: t('pricing.schoolgate.featuresPremium', { returnObjects: true }) as string[],
  };

  const tiltK12 = useTilt<HTMLDivElement>(5);
  const tiltNonK12 = useTilt<HTMLDivElement>(5);
  const tiltGate = useTilt<HTMLDivElement>(5);

  return (
    <section id="pricing" className="py-28 px-4 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(20,83,45,0.05) 0%, transparent 60%)' }} />

      <div className="max-w-5xl mx-auto">
        <Reveal className="text-center mb-14">
          <span className="badge mb-4">{t('pricing.badge')}</span>
          <h2 className="font-display font-bold text-4xl sm:text-5xl text-[#141310] mb-4 tracking-tight">
            {t('pricing.title')} <span className="gradient-text">{t('pricing.titleHighlight')}</span>
          </h2>
          <p className="text-[#5b5750] max-w-lg mx-auto">{t('pricing.subtitle')}</p>
        </Reveal>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* K-12 Card */}
          <motion.div
            ref={tiltK12.ref}
            onMouseMove={tiltK12.onMouseMove}
            onMouseLeave={tiltK12.onMouseLeave}
            className="relative rounded-3xl p-8 overflow-hidden sd-card-glass"
            style={{ border: `1px solid ${K12_COLOR}40`, ...tiltK12.style }}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, amount: 0.15 }}
            variants={{ hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0, transition: { duration: 0.7, delay: 0.05, ease: EASE } } }}
            whileHover={{ y: -6, scale: 1.01 }}
            transition={{ type: 'spring', stiffness: 280, damping: 22 }}
          >
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
                  <h3 className="font-display font-semibold text-[#141310] text-xl">{t('pricing.k12.name')}</h3>
                  <p className="text-[#8a8378] text-xs">{t('pricing.k12.tagline')}</p>
                </div>
              </div>

              <div className="mb-6">
                <div className="flex items-end gap-2">
                  <span className="font-display font-semibold text-5xl" style={{ color: K12_COLOR }}>₦500</span>
                  <div className="mb-2">
                    <p className="text-[#141310] text-sm font-semibold">{t('pricing.k12.perTerm')}</p>
                    <p className="text-[#8a8378] text-xs">{t('pricing.k12.termLength')}</p>
                  </div>
                </div>
                <p className="text-[#8a8378] text-xs mt-2">{t('pricing.k12.flatRate')}</p>
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
                      <p className="text-[#141310] text-sm font-semibold">{t('pricing.childMonitor.title')}</p>
                      <p className="text-[#8a8378] text-[10px]">{t('pricing.childMonitor.desc')}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono font-bold" style={{ color: K12_COLOR }}>{t('pricing.childMonitor.price')}</span>
                    <button onClick={() => setKidMonitor(k => !k)}
                      className="relative h-6 w-11 rounded-full transition-all cursor-pointer shrink-0"
                      style={{ background: kidMonitor ? K12_COLOR : 'rgba(20,19,16,0.14)' }}>
                      <div className="absolute top-1 h-4 w-4 rounded-full bg-white shadow-sm transition-all duration-200"
                        style={{ left: kidMonitor ? 24 : 4 }} />
                    </button>
                  </div>
                </div>
                {kidMonitor && (
                  <div className="mt-3 pt-3 border-t border-black/8 flex items-center justify-between">
                    <span className="text-[#8a8378] text-xs">{t('pricing.childMonitor.totalPerTerm')}</span>
                    <span className="font-display font-semibold text-lg" style={{ color: K12_COLOR }}>₦1,500</span>
                  </div>
                )}
              </div>

              <ul className="space-y-2.5 mb-8">
                {K12_FEATURES.map(f => (
                  <li key={f} className="flex items-center gap-3 text-[#3a362f] text-sm">
                    <CheckCircle className="h-4 w-4 shrink-0" style={{ color: K12_COLOR }} />
                    {f}
                  </li>
                ))}
              </ul>

              <a href="/#/signup?tier=k12" className="w-full btn-primary justify-center py-4 text-base">
                {t('pricing.k12.cta')} <ArrowRight className="h-4 w-4" />
              </a>
            </div>
          </motion.div>

          {/* Non-K12 Card */}
          <motion.div
            ref={tiltNonK12.ref}
            onMouseMove={tiltNonK12.onMouseMove}
            onMouseLeave={tiltNonK12.onMouseLeave}
            className="relative rounded-3xl p-8 overflow-hidden sd-card-glass"
            style={{ border: `1px solid ${NONK12_COLOR}40`, ...tiltNonK12.style }}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, amount: 0.15 }}
            variants={{ hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0, transition: { duration: 0.7, delay: 0.15, ease: EASE } } }}
            whileHover={{ y: -6, scale: 1.01 }}
            transition={{ type: 'spring', stiffness: 280, damping: 22 }}
          >
            <div className="relative">
              <div className="flex items-center gap-3 mb-6">
                <div className="h-11 w-11 rounded-2xl flex items-center justify-center"
                  style={{ background: `${NONK12_COLOR}22`, border: `1px solid ${NONK12_COLOR}50` }}>
                  <Zap className="h-5 w-5" style={{ color: NONK12_COLOR }} />
                </div>
                <div>
                  <h3 className="font-display font-semibold text-[#141310] text-xl">{t('pricing.nonK12.name')}</h3>
                  <p className="text-[#8a8378] text-xs">{t('pricing.nonK12.tagline')}</p>
                </div>
              </div>

              <div className="mb-6">
                <div className="flex items-end gap-2">
                  <span className="font-display font-semibold text-5xl" style={{ color: NONK12_COLOR }}>₦200</span>
                  <div className="mb-2">
                    <p className="text-[#141310] text-sm font-semibold">{t('pricing.nonK12.perMonth')}</p>
                    <p className="text-[#8a8378] text-xs">{t('pricing.nonK12.billedMonthly')}</p>
                  </div>
                </div>
                <p className="text-[#8a8378] text-xs mt-2">{t('pricing.nonK12.flatRate')}</p>
              </div>

              <div className="h-[120px] mb-6 rounded-2xl flex items-center px-4 sd-card">
                <div className="flex items-center gap-3">
                  <Shield className="h-5 w-5 text-[#8a8378]" />
                  <div>
                    <p className="text-[#141310] text-sm font-semibold">{t('pricing.nonK12.fullAccess')}</p>
                    <p className="text-[#8a8378] text-xs mt-1">{t('pricing.nonK12.fullAccessDesc')}</p>
                  </div>
                </div>
              </div>

              <ul className="space-y-2.5 mb-8">
                {NON_K12_FEATURES.map(f => (
                  <li key={f} className="flex items-center gap-3 text-[#3a362f] text-sm">
                    <CheckCircle className="h-4 w-4 shrink-0" style={{ color: NONK12_COLOR }} />
                    {f}
                  </li>
                ))}
              </ul>

              <a href="/#/signup?tier=non_k12"
                className="w-full py-4 rounded-2xl font-semibold text-base text-[#141310] cursor-pointer hover:opacity-90 transition-all flex items-center justify-center"
                style={{ background: `${NONK12_COLOR}22`, border: `1px solid ${NONK12_COLOR}55` }}>
                {t('pricing.nonK12.cta')} <ArrowRight className="h-4 w-4 inline ml-2" />
              </a>
            </div>
          </motion.div>

          {/* SchoolGate Card */}
          <motion.div
            ref={tiltGate.ref}
            onMouseMove={tiltGate.onMouseMove}
            onMouseLeave={tiltGate.onMouseLeave}
            className="relative rounded-3xl p-8 overflow-hidden sd-card-glass"
            style={{ border: `1px solid ${GATE_COLOR}40`, ...tiltGate.style }}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, amount: 0.15 }}
            variants={{ hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0, transition: { duration: 0.7, delay: 0.25, ease: EASE } } }}
            whileHover={{ y: -6, scale: 1.01 }}
            transition={{ type: 'spring', stiffness: 280, damping: 22 }}
          >
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
                  <h3 className="font-display font-semibold text-[#141310] text-xl">{t('pricing.schoolgate.name')}</h3>
                  <p className="text-[#8a8378] text-xs">{t('pricing.schoolgate.tagline')}</p>
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
                    <p className="text-[#141310] text-sm font-semibold">{t('pricing.schoolgate.perStudentTerm')}</p>
                  </div>
                </div>
                <p className="text-[#8a8378] text-xs mt-2">{t('pricing.schoolgate.deviceFee')}</p>
              </div>

              <ul className="space-y-2.5 mb-8">
                {SCHOOLGATE_FEATURES[gatePlan].map(f => (
                  <li key={f} className="flex items-center gap-3 text-[#3a362f] text-sm">
                    <CheckCircle className="h-4 w-4 shrink-0" style={{ color: GATE_COLOR }} />
                    {f}
                  </li>
                ))}
              </ul>

              <a href={`/#/signup?product=schoolgate&plan=${gatePlan}`}
                className="w-full py-4 rounded-2xl font-semibold text-base text-[#141310] cursor-pointer hover:opacity-90 transition-all flex items-center justify-center"
                style={{ background: `${GATE_COLOR}22`, border: `1px solid ${GATE_COLOR}55` }}>
                {t('pricing.schoolgate.cta')} <ArrowRight className="h-4 w-4 inline ml-2" />
              </a>
            </div>
          </motion.div>
        </div>

        {/* Guarantees row */}
        <Reveal className="mt-10 grid grid-cols-2 sm:grid-cols-4 gap-4" y={0} delay={0.3}>
          {[
            { icon: Shield, label: t('pricing.guarantees.noSetupFee') },
            { icon: Zap, label: t('pricing.guarantees.startIn4Min') },
            { icon: Users, label: t('pricing.guarantees.unlimitedUsers') },
            { icon: Star, label: t('pricing.guarantees.cancelAnytime') },
          ].map(g => {
            const Icon = g.icon;
            return (
              <div key={g.label} className="flex items-center gap-2 justify-center px-4 py-3 rounded-xl sd-card">
                <Icon className="h-4 w-4 shrink-0" style={{ color: '#14532d' }} />
                <span className="text-[#8a8378] text-xs">{g.label}</span>
              </div>
            );
          })}
        </Reveal>
      </div>
    </section>
  );
}
