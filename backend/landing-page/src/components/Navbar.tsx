import { useState, useEffect, useRef } from 'react';
import { Menu, X, ArrowRight, ChevronDown, Sun, Moon } from 'lucide-react';

function ThemeToggle() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() =>
    (localStorage.getItem('sd-theme') as 'dark' | 'light') || 'dark'
  );
  useEffect(() => {
    document.documentElement.classList.toggle('light', theme === 'light');
    localStorage.setItem('sd-theme', theme);
  }, [theme]);
  return (
    <button
      onClick={() => setTheme(t => (t === 'dark' ? 'light' : 'dark'))}
      aria-label="Toggle theme"
      className="h-9 w-9 rounded-xl border border-white/8 flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/5 transition-all cursor-pointer shrink-0"
    >
      {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" style={{ color: '#475569' }} />}
    </button>
  );
}

interface NavbarProps {
  onSignIn: () => void;
  onSignUp: () => void;
}

const NAV_LINKS = [
  { label: 'Features', href: '#features' },
  { label: 'CBT App', href: '#cbt' },
  { label: 'Pricing', href: '#pricing' },
  { label: 'Testimonials', href: '#testimonials' },
  {
    label: 'More', href: '#', children: [
      { label: 'FAQ', href: '/#/faq' },
      { label: 'Contact', href: '/#/contact' },
      { label: 'About', href: '#' },
    ]
  },
];

export default function Navbar({ onSignIn, onSignUp }: NavbarProps) {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);
  const [activeLink, setActiveLink] = useState('');
  const btnRef = useRef<HTMLButtonElement>(null);

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

  const handleMagnet = (e: React.MouseEvent<HTMLButtonElement>) => {
    const btn = btnRef.current;
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width - 0.5) * 8;
    const y = ((e.clientY - rect.top) / rect.height - 0.5) * 8;
    btn.style.transform = `translate(${x}px, ${y}px)`;
  };
  const resetMagnet = () => { if (btnRef.current) btnRef.current.style.transform = ''; };

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
        className="fixed top-0 left-0 right-0 z-[100] transition-all duration-500"
        style={{
          background: scrolled ? 'rgba(3,7,18,0.85)' : 'transparent',
          backdropFilter: scrolled ? 'blur(24px)' : 'none',
          WebkitBackdropFilter: scrolled ? 'blur(24px)' : 'none',
          borderBottom: scrolled ? '1px solid rgba(255,255,255,0.04)' : '1px solid transparent',
          boxShadow: scrolled ? '0 4px 30px rgba(0,0,0,0.3)' : 'none',
          padding: scrolled ? '0.625rem 0' : '1.25rem 0',
        }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex items-center justify-between">
          <a href="/" className="flex items-center gap-3 group">
            <div className="h-9 w-9 rounded-xl overflow-hidden border border-white/10 group-hover:border-green-500/30 transition-all"
              style={{ boxShadow: '0 0 12px rgba(34,197,94,0.15)' }}>
              <img src="/schooldom-favicon.jpeg" alt="Schooldom" className="w-full h-full object-cover" />
            </div>
            <div className="flex flex-col leading-none">
              <span className="font-display font-black text-white text-lg tracking-tight">Schooldom</span>
              <span className="text-[9px] font-bold uppercase tracking-[0.15em]" style={{ color: '#22c55e' }}>Academy</span>
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
                      className="flex items-center gap-1 px-4 py-2 rounded-xl text-sm font-medium transition-all cursor-pointer text-slate-400 hover:text-white"
                    >
                      {link.label} <ChevronDown className="h-3.5 w-3.5" />
                    </button>
                    {openDropdown === link.label && (
                      <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-44 rounded-2xl overflow-hidden border border-white/8 shadow-2xl z-50"
                        style={{ background: 'rgba(10,15,30,0.98)', backdropFilter: 'blur(24px)' }}>
                        {link.children.map(c => (
                          <a key={c.label} href={c.href}
                            className="block px-4 py-3 text-sm text-slate-400 hover:text-white hover:bg-white/5 transition-all">
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
                      color: activeLink === link.href.slice(1) ? '#22c55e' : '#94a3b8',
                      background: activeLink === link.href.slice(1) ? 'rgba(34,197,94,0.06)' : 'transparent',
                    }}
                  >
                    {link.label}
                    {activeLink === link.href.slice(1) && (
                      <span className="absolute bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-green-500" />
                    )}
                  </button>
                )}
              </div>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-3">
            <ThemeToggle />
            <button onClick={onSignIn} className="btn-ghost text-sm px-5 py-2">Sign In</button>
            <button
              ref={btnRef}
              onClick={onSignUp}
              onMouseMove={handleMagnet}
              onMouseLeave={resetMagnet}
              className="btn-primary text-sm px-5 py-2"
              style={{ transition: 'transform 0.15s ease, opacity 0.2s, box-shadow 0.2s' }}
            >
              Get Started Free <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="md:hidden flex items-center gap-2">
            <ThemeToggle />
            <button
              className="p-2 rounded-xl border border-white/8 text-slate-400 hover:text-white hover:bg-white/5 transition-all cursor-pointer"
              onClick={() => setMobileOpen(o => !o)}
            >
              {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>
      </nav>

      {mobileOpen && (
        <div className="fixed inset-0 z-[99] md:hidden" onClick={() => setMobileOpen(false)}>
          <div className="absolute inset-0" style={{ background: 'rgba(3,7,18,0.6)', backdropFilter: 'blur(8px)' }} />
          <div
            className="absolute top-[70px] left-4 right-4 rounded-2xl overflow-hidden border border-white/8 shadow-2xl"
            style={{ background: 'rgba(10,15,30,0.98)', backdropFilter: 'blur(30px)' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="p-4 space-y-1">
              {NAV_LINKS.filter(l => !l.children).map(link => (
                <button key={link.label} onClick={() => scrollTo(link.href)}
                  className="w-full text-left px-4 py-3 rounded-xl text-sm font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-all cursor-pointer">
                  {link.label}
                </button>
              ))}
              <a href="/#/faq" className="block px-4 py-3 rounded-xl text-sm font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-all">FAQ</a>
              <a href="/#/contact" className="block px-4 py-3 rounded-xl text-sm font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-all">Contact</a>
            </div>
            <div className="p-4 border-t border-white/5 flex gap-3">
              <button onClick={onSignIn} className="flex-1 btn-ghost text-sm py-2.5">Sign In</button>
              <button onClick={onSignUp} className="flex-1 btn-primary text-sm py-2.5 justify-center">Get Started</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
