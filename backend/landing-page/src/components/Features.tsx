import { type ReactElement } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'motion/react';
import {
  BookOpen, DollarSign, Users, FileText, MessageSquare,
  Briefcase, Monitor, ArrowRight, CheckCircle, QrCode
} from 'lucide-react';
import { Reveal, RevealGroup, revealItem, EASE } from '../lib/reveal';
import { smoothScrollTo } from '../lib/smoothScroll';
import { useTilt } from '../lib/tilt';

const GREEN = 'var(--c-green)';
// Brighter variant for text/icons inside the dark dashboard-mockup previews,
// where the deep brand green wouldn't read against a near-black surface.
const GREEN_BRIGHT = '#4ade80';

// Indices of the feature-grid tiles rendered wide (2 cols) in the bento layout.
const WIDE_TILES = new Set([0, 4]);

function goTo(link: string) {
  if (link.startsWith('#')) {
    smoothScrollTo(link);
  } else {
    window.location.href = link;
  }
}

type IconType = typeof BookOpen;

interface FeatureGridItem { icon: IconType; title: string; desc: string; link: string }

function buildFeaturesGrid(t: (key: string) => string): FeatureGridItem[] {
  return [
    { icon: BookOpen, title: t('features.grid.cbtEngine.title'), desc: t('features.grid.cbtEngine.desc'), link: '#cbt' },
    { icon: DollarSign, title: t('features.grid.finance.title'), desc: t('features.grid.finance.desc'), link: '/#/faq?cat=finance' },
    { icon: Users, title: t('features.grid.students.title'), desc: t('features.grid.students.desc'), link: '/#/faq?cat=setup' },
    { icon: QrCode, title: t('features.grid.attendance.title'), desc: t('features.grid.attendance.desc'), link: '/#/faq' },
    { icon: FileText, title: t('features.grid.reportCards.title'), desc: t('features.grid.reportCards.desc'), link: '/#/faq' },
    { icon: MessageSquare, title: t('features.grid.parentPortal.title'), desc: t('features.grid.parentPortal.desc'), link: '/#/faq' },
    { icon: Briefcase, title: t('features.grid.hr.title'), desc: t('features.grid.hr.desc'), link: '/#/faq' },
    { icon: Monitor, title: t('features.grid.desktopCbt.title'), desc: t('features.grid.desktopCbt.desc'), link: '#cbt' },
  ];
}

interface ShowcaseSectionData { badge: string; link: string; title: string; desc: string; points: string[]; preview: ReactElement }

function buildShowcaseSections(t: (key: string, options?: Record<string, unknown>) => any): ShowcaseSectionData[] {
  return [
  {
    badge: t('features.showcase.finance.badge'),
    link: '/#/faq?cat=finance',
    title: t('features.showcase.finance.title'),
    desc: t('features.showcase.finance.desc'),
    points: t('features.showcase.finance.points', { returnObjects: true }) as string[],
    preview: (
      <div className="rounded-2xl overflow-hidden border border-white/10 keep-dark" style={{ background: 'rgba(15,13,11,0.97)' }}>
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <span className="text-white text-sm font-semibold">Fee Collection Dashboard</span>
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-[9px] font-semibold uppercase tracking-[0.08em]"
            style={{ color: GREEN_BRIGHT, background: 'rgba(74,222,128,0.1)', border: '1px solid rgba(74,222,128,0.25)' }}>Live</span>
        </div>
        <div className="p-4 space-y-3">
          {[
            { name: 'Adaugo Obi', amount: '₦75,000', status: 'Paid', color: '#34d399' },
            { name: 'Emeka Nwachukwu', amount: '₦75,000', status: 'Partial', color: '#fbbf24' },
            { name: 'Halima Abdullahi', amount: '₦75,000', status: 'Pending', color: '#f87171' },
            { name: 'Tunde Adeyemi', amount: '₦75,000', status: 'Paid', color: '#34d399' },
          ].map((r, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-white/4 last:border-0">
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold"
                  style={{ background: 'rgba(74,222,128,0.15)', color: GREEN_BRIGHT }}>{r.name[0]}</div>
                <div>
                  <p className="text-white text-xs font-medium">{r.name}</p>
                  <p className="text-slate-500 text-[10px]">Term 2 · SS3</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-white text-xs font-mono">{r.amount}</p>
                <span className="text-[9px] font-semibold" style={{ color: r.color }}>{r.status}</span>
              </div>
            </div>
          ))}
          <div className="grid grid-cols-3 gap-2 mt-2">
            {[
              { label: 'Collected', val: '₦6.2M' },
              { label: 'Pending', val: '₦1.8M' },
              { label: 'Students', val: '842' },
            ].map(s => (
              <div key={s.label} className="rounded-xl p-2.5 text-center" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}>
                <p className="font-bold font-mono text-sm" style={{ color: GREEN_BRIGHT }}>{s.val}</p>
                <p className="text-slate-500 text-[9px]">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    ),
  },
  {
    badge: t('features.showcase.cbt.badge'),
    link: '#cbt',
    title: t('features.showcase.cbt.title'),
    desc: t('features.showcase.cbt.desc'),
    points: t('features.showcase.cbt.points', { returnObjects: true }) as string[],
    preview: (
      <div className="rounded-2xl overflow-hidden border border-white/10 keep-dark" style={{ background: 'rgba(15,13,11,0.97)' }}>
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <span className="text-white text-sm font-semibold">CBT — English SS3 (Term 2)</span>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs" style={{ color: GREEN_BRIGHT }}>01:24:33</span>
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-[9px] font-semibold uppercase tracking-[0.08em]"
              style={{ color: GREEN_BRIGHT, background: 'rgba(74,222,128,0.1)', border: '1px solid rgba(74,222,128,0.25)' }}>LIVE</span>
          </div>
        </div>
        <div className="p-4">
          <div className="grid grid-cols-2 gap-3 mb-4">
            {[{ l: 'Active', v: '127' }, { l: 'Submitted', v: '43' }, { l: 'Avg Progress', v: '68%' }, { l: 'Offline', v: '12' }].map(s => (
              <div key={s.l} className="rounded-xl p-3" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}>
                <p className="text-slate-500 text-[9px]">{s.l}</p>
                <p className="font-bold text-lg font-mono" style={{ color: GREEN_BRIGHT }}>{s.v}</p>
              </div>
            ))}
          </div>
          <div className="space-y-2">
            <p className="text-slate-500 text-[9px] uppercase tracking-wider mb-2">Student Progress</p>
            {['Bello Fatima', 'Chidi Okonkwo', 'Ngozi Eze', 'Tunde A.'].map((name, i) => (
              <div key={name} className="flex items-center gap-3">
                <span className="text-slate-500 text-[9px] w-20 truncate">{name}</span>
                <div className="flex-1 h-1.5 rounded-full" style={{ background: 'rgba(255,255,255,0.08)' }}>
                  <div className="h-full rounded-full transition-all" style={{ width: `${[78, 95, 62, 88][i]}%`, background: GREEN_BRIGHT }} />
                </div>
                <span className="text-[9px] font-mono w-8 text-right" style={{ color: GREEN_BRIGHT }}>{[78, 95, 62, 88][i]}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    ),
  },
  {
    badge: t('features.showcase.attendance.badge'),
    link: '/#/faq',
    title: t('features.showcase.attendance.title'),
    desc: t('features.showcase.attendance.desc'),
    points: t('features.showcase.attendance.points', { returnObjects: true }) as string[],
    preview: (
      <div className="rounded-2xl overflow-hidden border border-white/10 keep-dark" style={{ background: 'rgba(15,13,11,0.97)' }}>
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <span className="text-white text-sm font-semibold">Attendance — JSS2A</span>
          <div className="flex items-center gap-1.5">
            <QrCode className="h-3.5 w-3.5" style={{ color: GREEN_BRIGHT }} />
            <span className="text-[9px]" style={{ color: GREEN_BRIGHT }}>Scanning</span>
          </div>
        </div>
        <div className="p-4">
          <div className="grid grid-cols-4 gap-2 mb-4">
            {[{ l: 'Present', v: '38', c: '#34d399' }, { l: 'Late', v: '3', c: '#fbbf24' }, { l: 'Absent', v: '4', c: '#f87171' }, { l: 'Rate', v: '93%', c: GREEN_BRIGHT }].map(s => (
              <div key={s.l} className="rounded-xl p-2 text-center" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}>
                <p className="font-bold text-base font-mono" style={{ color: s.c }}>{s.v}</p>
                <p className="text-slate-500 text-[8px]">{s.l}</p>
              </div>
            ))}
          </div>
          <div className="space-y-2">
            {[
              { name: 'Adunola Okafor', time: '07:58 AM', status: 'Present', color: '#34d399' },
              { name: 'Emeka Obi', time: '08:22 AM', status: 'Late', color: '#fbbf24' },
              { name: 'Fatima Bello', time: '07:55 AM', status: 'Present', color: '#34d399' },
              { name: 'Gbenga Adeyemi', time: '--:--', status: 'Absent', color: '#f87171' },
            ].map((r, i) => (
              <div key={i} className="flex items-center gap-3 py-1.5 border-b border-white/4 last:border-0">
                <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: r.color }} />
                <span className="text-white text-[10px] flex-1">{r.name}</span>
                <span className="text-slate-500 text-[9px] font-mono">{r.time}</span>
                <span className="text-[9px] font-semibold" style={{ color: r.color }}>{r.status}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    ),
  },
  ];
}

function ShowcaseSection({ section, idx }: { section: ShowcaseSectionData; idx: number }) {
  const { t } = useTranslation();
  const isEven = idx % 2 === 0;

  return (
    <div className={`grid lg:grid-cols-2 gap-12 items-center ${idx > 0 ? 'mt-24' : ''}`}>
      <Reveal x={isEven ? -28 : 28} y={0} className={isEven ? 'order-1' : 'order-1 lg:order-2'}>
        <span className="badge mb-4">{section.badge}</span>
        <h3 className="font-display font-semibold text-3xl lg:text-4xl text-[var(--c-ink)] mb-4 leading-tight">{section.title}</h3>
        <p className="text-[var(--c-muted)] text-base leading-relaxed mb-6">{section.desc}</p>
        <ul className="space-y-2.5 mb-8">
          {section.points.map(p => (
            <li key={p} className="flex items-center gap-3 text-[var(--c-ink)] text-sm">
              <CheckCircle className="h-4 w-4 shrink-0" style={{ color: GREEN }} />
              {p}
            </li>
          ))}
        </ul>
        <button className="btn-ghost" onClick={() => goTo(section.link)}>
          {t('common.learnMore')} <ArrowRight className="h-4 w-4" />
        </button>
      </Reveal>

      <Reveal x={isEven ? 28 : -28} y={0} delay={0.15} className={isEven ? 'order-2' : 'order-2 lg:order-1'}>
        {section.preview}
      </Reveal>
    </div>
  );
}

function FeatureCard({ feature, wide }: { feature: FeatureGridItem; wide: boolean }) {
  const { t } = useTranslation();
  const { icon: Icon, title, desc, link } = feature;
  const tilt = useTilt<HTMLDivElement>(6);

  return (
    <motion.div
      ref={tilt.ref}
      onClick={() => goTo(link)}
      onMouseMove={tilt.onMouseMove}
      onMouseLeave={tilt.onMouseLeave}
      variants={revealItem}
      whileHover={{ y: -6, scale: 1.01 }}
      transition={{ type: 'spring', stiffness: 300, damping: 22 }}
      style={tilt.style}
      className={`group relative rounded-2xl p-6 cursor-pointer sd-card-glass ${wide ? 'lg:col-span-2 flex items-start gap-5' : ''}`}
    >
      <div className={`rounded-xl flex items-center justify-center shrink-0 ${wide ? 'h-14 w-14' : 'h-12 w-12 mb-4'}`}
        style={{ background: 'rgba(var(--c-green-rgb),0.08)', border: '1px solid rgba(var(--c-green-rgb),0.22)' }}>
        <Icon className={wide ? 'h-6 w-6' : 'h-5 w-5'} style={{ color: GREEN }} />
      </div>
      <div className="min-w-0">
        <h3 className={`text-[var(--c-ink)] font-semibold mb-2 ${wide ? 'text-lg' : 'text-base'}`}>{title}</h3>
        <p className="text-[var(--c-muted)] text-sm leading-relaxed">{desc}</p>
        <div className="mt-4 flex items-center gap-1 text-xs font-medium opacity-0 group-hover:opacity-100 transition-opacity" style={{ color: GREEN }}>
          {t('common.learnMore')} <ArrowRight className="h-3 w-3" />
        </div>
      </div>
    </motion.div>
  );
}

export default function Features() {
  const { t } = useTranslation();
  const showcaseSections = buildShowcaseSections(t);
  const featuresGrid = buildFeaturesGrid(t);

  return (
    <section id="features" className="py-28 px-4 relative">
      <div className="max-w-7xl mx-auto">
        {/* Showcase sections */}
        {showcaseSections.map((s, i) => <ShowcaseSection key={s.badge} section={s} idx={i} />)}

        {/* Section divider */}
        <div className="section-divider my-24" />

        {/* Feature grid — asymmetric bento layout, not a uniform 3-up */}
        <div>
          <Reveal className="text-center mb-14">
            <span className="badge mb-4">{t('features.badge')}</span>
            <h2 className="font-display font-bold text-4xl sm:text-5xl text-[var(--c-ink)] mb-4 tracking-tight">
              {t('features.title')}{' '}
              <span className="gradient-text">{t('features.titleHighlight')}</span>
            </h2>
            <p className="text-[var(--c-muted)] max-w-xl mx-auto">{t('features.subtitle')}</p>
          </Reveal>
          <RevealGroup className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" stagger={0.07} amount={0.05}>
            {featuresGrid.map((f, i) => <FeatureCard key={f.title} feature={f} wide={WIDE_TILES.has(i)} />)}
          </RevealGroup>
        </div>
      </div>
    </section>
  );
}
