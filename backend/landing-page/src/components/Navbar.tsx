import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Menu, X, ChevronDown } from 'lucide-react';
import LanguageSwitcher from './LanguageSwitcher';

interface NavbarProps {
  onSignIn: () => void;
}

export default function Navbar({ onSignIn }: NavbarProps) {
  const { t } = useTranslation();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);
  const [activeLink, setActiveLink] = useState('');

  const NAV_LINKS = [
    { label: t('nav.features'), href: '#features' },
    { label: t('nav.cbt'), href: '#cbt' },
    { label: t('nav.pricing'), href: '#pricing' },
    { label: t('nav.testimonials'), href: '#testimonials' },
    {
      label: t('nav.more'), href: '#', children: [
        { label: t('nav.faq'), href: '/#/faq' },
        { label: t('nav.contact'), href: '/#/contact' },
        { label: t('nav.about'), href: '#' },
      ]
    },
  ];

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    const sections = ['features', 'cbt', 'pricing', 'testimonials'];
    const obs = new IntersectionObserver(
      entries => entries.forEach(e => { if (e.isIntersecting) setActiveLink(e.target.id); }),
      { threshold: 0.4 }
    );
    sections.forEach(id => { const el = document.getElementById(id); if (el) obs.observe(el); });
    return () => obs.disconnect();
  }, []);

  const scrollTo = (href: string) => {
    setMobileOpen(false);
    if (href.startsWith('#') && !href.startsWith('#/')) {
      const id = href.slice(1);
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
    } else {
      window.location.href = href;
    }
  };

  return (
    <>
      <nav
        className={`fixed top-0 left-0 right-0 z-[100] transition-all duration-500 ${scrolled ? 'nav-scrolled' : ''}`}
        style={{ padding: scrolled ? '0.625rem 0' : '1.25rem 0' }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex items-center justify-between">
          <a href="/" className="flex items-center gap-3 group">
            <div className="h-9 w-9 rounded-xl overflow-hidden border border-black/10 group-hover:border-[#14532d]/40 transition-all">
              <img src="/schooldom-favicon.jpeg" alt="Schooldom" className="w-full h-full object-cover" />
            </div>
            <div className="flex flex-col leading-none">
              <span className="font-display font-bold text-[#141310] text-lg tracking-tight">Schooldom</span>
              <span className="text-[9px] font-semibold uppercase tracking-[0.15em]" style={{ color: '#14532d' }}>Academy</span>
            </div>
          </a>

          <div className="hidden md:flex items-center gap-1">
            {NAV_LINKS.map(link => (
              <div key={link.label} className="relative"
                onMouseEnter={() => link.children && setOpenDropdown(link.label)}
                onMouseLeave={() => setOpenDropdown(null)}>
                {link.children ? (
                  <>
                    <button
                      className="flex items-center gap-1 px-4 py-2 rounded-xl text-sm font-medium transition-all cursor-pointer text-[#5b5750] hover:text-[#141310]"
                    >
                      {link.label} <ChevronDown className="h-3.5 w-3.5" />
                    </button>
                    {openDropdown === link.label && (
                      <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-44 rounded-2xl overflow-hidden shadow-xl z-50 sd-panel">
                        {link.children.map(c => (
                          <a key={c.label} href={c.href}
                            className="block px-4 py-3 text-sm text-[#5b5750] hover:text-[#141310] hover:bg-black/5 transition-all">
                            {c.label}
                          </a>
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  <button
                    onClick={() => scrollTo(link.href)}
                    className="px-4 py-2 rounded-xl text-sm font-medium transition-all cursor-pointer relative"
                    style={{
                      color: activeLink === link.href.slice(1) ? '#14532d' : '#5b5750',
                      background: activeLink === link.href.slice(1) ? 'rgba(20,83,45,0.08)' : 'transparent',
                    }}
                  >
                    {link.label}
                    {activeLink === link.href.slice(1) && (
                      <span className="absolute bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full" style={{ background: '#14532d' }} />
                    )}
                  </button>
                )}
              </div>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-3">
            <LanguageSwitcher />
            <button onClick={onSignIn} className="btn-ghost text-sm px-5 py-2">{t('nav.signIn')}</button>
            <a href="/#/signup" className="btn-primary text-sm px-5 py-2">{t('nav.getStarted')}</a>
          </div>

          <div className="md:hidden flex items-center gap-2">
            <LanguageSwitcher />
            <button
              className="p-2 rounded-xl border border-black/10 text-[#5b5750] hover:text-[#141310] hover:bg-black/5 transition-all cursor-pointer"
              onClick={() => setMobileOpen(o => !o)}
            >
              {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>
      </nav>

      {mobileOpen && (
        <div className="fixed inset-0 z-[99] md:hidden" onClick={() => setMobileOpen(false)}>
          <div className="absolute inset-0" style={{ background: 'rgba(20,19,16,0.4)', backdropFilter: 'blur(8px)' }} />
          <div
            className="absolute top-[70px] left-4 right-4 rounded-2xl overflow-hidden shadow-xl sd-panel"
            onClick={e => e.stopPropagation()}
          >
            <div className="p-4 space-y-1">
              {NAV_LINKS.filter(l => !l.children).map(link => (
                <button key={link.label} onClick={() => scrollTo(link.href)}
                  className="w-full text-left px-4 py-3 rounded-xl text-sm font-medium text-[#5b5750] hover:text-[#141310] hover:bg-black/5 transition-all cursor-pointer">
                  {link.label}
                </button>
              ))}
              <a href="/#/faq" className="block px-4 py-3 rounded-xl text-sm font-medium text-[#5b5750] hover:text-[#141310] hover:bg-black/5 transition-all">{t('nav.faq')}</a>
              <a href="/#/contact" className="block px-4 py-3 rounded-xl text-sm font-medium text-[#5b5750] hover:text-[#141310] hover:bg-black/5 transition-all">{t('nav.contact')}</a>
            </div>
            <div className="p-4 border-t border-black/8 space-y-2">
              <a href="/#/signup" className="w-full btn-primary text-sm py-2.5 justify-center">{t('nav.getStarted')}</a>
              <button onClick={onSignIn} className="w-full btn-ghost text-sm py-2.5 justify-center">{t('nav.signIn')}</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
