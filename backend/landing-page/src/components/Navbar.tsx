import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { motion, AnimatePresence } from 'motion/react';
import { Menu, X, ChevronDown, Sun, Moon } from 'lucide-react';
import LanguageSwitcher from './LanguageSwitcher';
import { smoothScrollTo } from '../lib/smoothScroll';
import { useTheme } from '../lib/theme';

function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button
      type="button"
      onClick={toggle}
      className="theme-toggle"
      aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
      title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={theme}
          initial={{ opacity: 0, rotate: -90, scale: 0.6 }}
          animate={{ opacity: 1, rotate: 0, scale: 1 }}
          exit={{ opacity: 0, rotate: 90, scale: 0.6 }}
          transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          style={{ display: 'inline-flex' }}
        >
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </motion.span>
      </AnimatePresence>
    </button>
  );
}

interface NavbarProps {
  onSignIn: () => void;
}

export default function Navbar({ onSignIn }: NavbarProps) {
  const { t } = useTranslation();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);
  const [activeLink, setActiveLink] = useState('');
  const navRowRef = useRef<HTMLDivElement>(null);
  const linkRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [indicator, setIndicator] = useState<{ x: number; width: number } | null>(null);

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
      smoothScrollTo(href);
    } else {
      window.location.href = href;
    }
  };

  const measureIndicator = useCallback(() => {
    const row = navRowRef.current;
    const btn = activeLink && linkRefs.current[activeLink];
    if (!row || !btn) { setIndicator(null); return; }
    const rowRect = row.getBoundingClientRect();
    const btnRect = btn.getBoundingClientRect();
    setIndicator({ x: btnRect.left - rowRect.left, width: btnRect.width });
  }, [activeLink]);

  useEffect(() => { measureIndicator(); }, [measureIndicator]);
  useEffect(() => {
    window.addEventListener('resize', measureIndicator);
    return () => window.removeEventListener('resize', measureIndicator);
  }, [measureIndicator]);

  return (
    <>
      <nav
        className={`fixed top-0 left-0 right-0 z-[100] transition-all duration-500 ${scrolled ? 'nav-scrolled' : ''}`}
        style={{ padding: scrolled ? '0.625rem 0' : '1.25rem 0' }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex items-center justify-between">
          <a href="/" className="flex items-center gap-3 group">
            <div className="h-9 w-9 rounded-xl overflow-hidden border border-[var(--c-ink)]/10 group-hover:border-[var(--c-green)]/40 transition-all">
              <img src="/schooldom-favicon.jpeg" alt="Schooldom" className="w-full h-full object-cover" />
            </div>
            <div className="flex flex-col leading-none">
              <span className="font-display font-bold text-[var(--c-ink)] text-lg tracking-tight">Schooldom</span>
              <span className="text-[9px] font-semibold uppercase tracking-[0.15em]" style={{ color: 'var(--c-green)' }}>Academy</span>
            </div>
          </a>

          <div ref={navRowRef} className="hidden md:flex items-center gap-1 relative">
            {indicator && (
              <motion.div
                className="absolute top-0 h-full rounded-xl pointer-events-none"
                style={{ background: 'rgba(var(--c-green-rgb),0.08)', border: '1px solid rgba(var(--c-green-rgb),0.18)' }}
                animate={{ x: indicator.x, width: indicator.width }}
                transition={{ type: 'spring', stiffness: 420, damping: 34 }}
              />
            )}
            {NAV_LINKS.map(link => (
              <div key={link.label} className="relative"
                onMouseEnter={() => link.children && setOpenDropdown(link.label)}
                onMouseLeave={() => setOpenDropdown(null)}>
                {link.children ? (
                  <>
                    <button
                      className="relative flex items-center gap-1 px-4 py-2 rounded-xl text-sm font-medium transition-all cursor-pointer text-[var(--c-muted)] hover:text-[var(--c-ink)]"
                      aria-haspopup="true"
                      aria-expanded={openDropdown === link.label}
                    >
                      {link.label} <ChevronDown className="h-3.5 w-3.5" />
                    </button>
                    <AnimatePresence>
                      {openDropdown === link.label && (
                        <motion.div
                          initial={{ opacity: 0, y: -6, scale: 0.98 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: -6, scale: 0.98 }}
                          transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
                          className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-44 rounded-2xl overflow-hidden shadow-xl z-50 sd-panel"
                        >
                          {link.children.map(c => (
                            <a key={c.label} href={c.href}
                              className="block px-4 py-3 text-sm text-[var(--c-muted)] hover:text-[var(--c-ink)] hover:bg-[var(--c-ink)]/5 transition-all">
                              {c.label}
                            </a>
                          ))}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </>
                ) : (
                  <button
                    ref={el => { linkRefs.current[link.href.slice(1)] = el; }}
                    onClick={() => scrollTo(link.href)}
                    className="relative px-4 py-2 rounded-xl text-sm font-medium transition-colors cursor-pointer"
                    style={{ color: activeLink === link.href.slice(1) ? 'var(--c-green)' : 'var(--c-muted)' }}
                  >
                    {link.label}
                  </button>
                )}
              </div>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-3">
            <ThemeToggle />
            <LanguageSwitcher />
            <button onClick={onSignIn} className="btn-ghost text-sm px-5 py-2">{t('nav.signIn')}</button>
            <a href="/#/signup" className="btn-primary text-sm px-5 py-2">{t('nav.getStarted')}</a>
          </div>

          <div className="md:hidden flex items-center gap-2">
            <ThemeToggle />
            <LanguageSwitcher />
            <button
              className="p-2 rounded-xl border border-[var(--c-ink)]/10 text-[var(--c-muted)] hover:text-[var(--c-ink)] hover:bg-[var(--c-ink)]/5 transition-all cursor-pointer"
              onClick={() => setMobileOpen(o => !o)}
              aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={mobileOpen}
            >
              {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>
      </nav>

      <AnimatePresence>
      {mobileOpen && (
        <motion.div
          className="fixed inset-0 z-[99] md:hidden"
          onClick={() => setMobileOpen(false)}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          <div className="absolute inset-0" style={{ background: 'rgba(var(--c-ink-rgb),0.4)', backdropFilter: 'blur(8px)' }} />
          <motion.div
            className="absolute top-[70px] left-4 right-4 rounded-2xl overflow-hidden shadow-xl sd-panel"
            onClick={e => e.stopPropagation()}
            initial={{ opacity: 0, y: -12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -12, scale: 0.98 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="p-4 space-y-1">
              {NAV_LINKS.filter(l => !l.children).map(link => (
                <button key={link.label} onClick={() => scrollTo(link.href)}
                  className="w-full text-left px-4 py-3 rounded-xl text-sm font-medium text-[var(--c-muted)] hover:text-[var(--c-ink)] hover:bg-[var(--c-ink)]/5 transition-all cursor-pointer">
                  {link.label}
                </button>
              ))}
              <a href="/#/faq" className="block px-4 py-3 rounded-xl text-sm font-medium text-[var(--c-muted)] hover:text-[var(--c-ink)] hover:bg-[var(--c-ink)]/5 transition-all">{t('nav.faq')}</a>
              <a href="/#/contact" className="block px-4 py-3 rounded-xl text-sm font-medium text-[var(--c-muted)] hover:text-[var(--c-ink)] hover:bg-[var(--c-ink)]/5 transition-all">{t('nav.contact')}</a>
            </div>
            <div className="p-4 border-t border-[var(--c-ink)]/8 space-y-2">
              <a href="/#/signup" className="w-full btn-primary text-sm py-2.5 justify-center">{t('nav.getStarted')}</a>
              <button onClick={onSignIn} className="w-full btn-ghost text-sm py-2.5 justify-center">{t('nav.signIn')}</button>
            </div>
          </motion.div>
        </motion.div>
      )}
      </AnimatePresence>
    </>
  );
}
