import { useTranslation } from 'react-i18next';
import { Mail, MapPin, Twitter, Youtube, Facebook, ArrowRight, Phone } from 'lucide-react';

const LINK_GROUPS = ['product', 'company', 'support'] as const;

export default function Footer() {
  const { t } = useTranslation();
  const year = new Date().getFullYear();
  const LINKS: Record<(typeof LINK_GROUPS)[number], { heading: string; items: string[] }> = {
    product: t('footer.columns.product', { returnObjects: true }) as { heading: string; items: string[] },
    company: t('footer.columns.company', { returnObjects: true }) as { heading: string; items: string[] },
    support: t('footer.columns.support', { returnObjects: true }) as { heading: string; items: string[] },
  };

  return (
    <footer className="relative border-t border-black/8 pt-20 pb-8 px-4 overflow-hidden">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[1px]"
        style={{ background: 'linear-gradient(90deg, transparent, rgba(20,83,45,0.4), transparent)' }} />

      <div className="max-w-7xl mx-auto">
        {/* Main grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-10 mb-14">
          {/* Brand col */}
          <div className="lg:col-span-2">
            <div className="flex items-center gap-3 mb-5">
              <div className="h-10 w-10 rounded-xl overflow-hidden border border-black/10">
                <img src="/schooldom-favicon.jpeg" alt="Schooldom" className="w-full h-full object-cover" />
              </div>
              <div>
                <span className="font-display font-semibold text-[#141310] text-xl tracking-tight">Schooldom</span>
                <span className="text-[9px] font-bold ml-2 px-1.5 py-0.5 rounded border" style={{ color: '#14532d', background: 'rgba(20,83,45,0.07)', borderColor: 'rgba(20,83,45,0.22)' }}>ACADEMY</span>
              </div>
            </div>
            <p className="text-[#8a8378] text-sm leading-relaxed max-w-xs mb-6">
              {t('footer.tagline')}
            </p>

            <div className="space-y-2.5 mb-6">
              <a href="mailto:support@schooldom.academy" className="flex items-center gap-2.5 text-[#5b5750] hover:text-[#141310] text-sm transition-colors">
                <Mail className="h-4 w-4 shrink-0" style={{ color: '#14532d' }} />
                support@schooldom.academy
              </a>
              <a href="tel:+2349076821365" className="flex items-center gap-2.5 text-[#5b5750] hover:text-[#141310] text-sm transition-colors">
                <Phone className="h-4 w-4 shrink-0" style={{ color: '#14532d' }} />
                +234 907 682 1365
              </a>
              <div className="flex items-center gap-2.5 text-[#5b5750] text-sm">
                <MapPin className="h-4 w-4 shrink-0" style={{ color: '#14532d' }} />
                {t('footer.location')}
              </div>
            </div>

            <div className="flex gap-3">
              {[Twitter, Youtube, Facebook].map((Icon, i) => (
                <button key={i}
                  className="h-9 w-9 rounded-xl border border-black/8 flex items-center justify-center text-[#5b5750] hover:text-[#141310] hover:border-black/15 hover:bg-black/5 transition-all cursor-pointer">
                  <Icon className="h-4 w-4" />
                </button>
              ))}
            </div>
          </div>

          {/* Link cols */}
          {LINK_GROUPS.map(group => {
            const { heading, items } = LINKS[group];
            return (
              <div key={group}>
                <h4 className="text-[#141310] font-bold text-sm mb-4">{heading}</h4>
                <ul className="space-y-2.5">
                  {items.map((item, i) => {
                    const href = group === 'support' && i === 3 ? '/#/contact' : group === 'company' && i === 3 ? '/#/privacy' : '#';
                    return (
                      <li key={item}>
                        <a href={href} className="text-[#5b5750] hover:text-[#141310] text-sm transition-colors">
                          {item}
                        </a>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </div>

        {/* CTA block */}
        <div className="rounded-3xl p-10 mb-10 text-center relative overflow-hidden"
          style={{ background: 'rgba(20,83,45,0.06)', border: '1px solid rgba(20,83,45,0.18)' }}>
          <div className="relative">
            <h3 className="font-display font-bold text-[#141310] text-2xl sm:text-3xl mb-3 tracking-tight">
              {t('footer.ctaTitle')}
            </h3>
            <p className="text-[#5b5750] text-sm mb-6">{t('footer.ctaSubtitle')}</p>
            <a href="/#/signup" className="btn-primary text-base px-8 py-4">
              {t('footer.ctaButton')} <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="border-t border-black/8 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-[#8a8378] text-xs">
            {t('footer.copyright', { year })}
          </p>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-600 animate-pulse" />
            <span className="text-[#8a8378] text-xs">{t('footer.systemsOperational')}</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
