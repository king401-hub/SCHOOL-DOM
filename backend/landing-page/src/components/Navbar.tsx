import { useState, useEffect } from 'react';
import { School, Menu, X, ArrowRight, ShieldCheck, Sun, Moon } from 'lucide-react';

interface NavbarProps {
  onOpenOnboarding: () => void;
  scrollToSection: (id: string) => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  signInUrl?: string;
  signUpUrl?: string;
  onLoginClick?: () => void;
  onRegisterClick?: () => void;
}

export default function Navbar({ onOpenOnboarding, scrollToSection, theme, onToggleTheme, signInUrl, signUpUrl,  onLoginClick, onRegisterClick, }: NavbarProps) {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isVisible, setIsVisible] = useState(true);
  const [isHovered, setIsHovered] = useState(false);


  useEffect(() => {
    const handleScroll = () => {
      if (window.scrollY > 20) {
        setIsScrolled(true);
      } else {
        setIsScrolled(false);
      }
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout>;

    const resetTimer = () => {
      setIsVisible(true);
      clearTimeout(timeoutId);
      
      // Auto-hide AFTER 3 seconds of inactivity,
      // but only if mobile menu is closed and user is not currently hovering over the bar
      if (!isMobileMenuOpen && !isHovered) {
        timeoutId = setTimeout(() => {
          setIsVisible(false);
        }, 3000);
      }
    };

    // Initialize/reset timer on mount or when conditions shift
    resetTimer();

    // Trigger visibility reset on user activity
    window.addEventListener('scroll', resetTimer);
    window.addEventListener('mousemove', resetTimer);
    window.addEventListener('touchstart', resetTimer);

    return () => {
      clearTimeout(timeoutId);
      window.removeEventListener('scroll', resetTimer);
      window.removeEventListener('mousemove', resetTimer);
      window.removeEventListener('touchstart', resetTimer);
    };
  }, [isMobileMenuOpen, isHovered]);

  const handleNavClick = (id: string) => {
    scrollToSection(id);
    setIsMobileMenuOpen(false);
  };

  return (
    <nav
      id="main-navbar"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ease-in-out ${
        isVisible 
          ? 'translate-y-0 opacity-100' 
          : '-translate-y-full opacity-0 pointer-events-none'
      } ${
        isScrolled
          ? 'bg-white/70 dark:bg-slate-950/70 backdrop-blur-xl shadow-md border-b border-gray-150/50 dark:border-slate-800/60 py-3'
          : 'bg-white/40 dark:bg-slate-900/30 backdrop-blur-md shadow-xs border-b border-white/20 dark:border-white/5 py-5'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <div 
            className="flex items-center gap-2.5 cursor-pointer"
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          >
            <div className="h-10 w-10 rounded-xl overflow-hidden shadow-md shadow-brand-500/10 border border-slate-900/60">
              <img src="/schooldom-favicon.jpeg" alt="Schooldom" className="h-full w-full object-cover" />
            </div>
            <div>
              <div className="flex items-baseline">
                <span className="font-display font-bold text-xl text-brand-950 dark:text-white tracking-tight animate-fade-in">Schooldom</span>
                <span className="font-display font-medium text-xs text-teal-brand-500 ml-1 bg-teal-brand-50 dark:bg-teal-brand-950/50 px-1.5 py-0.5 rounded-md border border-teal-brand-500/10 dark:border-teal-brand-500/20">ACADEMY</span>
              </div>
              <p className="text-[10px] text-gray-400 dark:text-slate-500 font-medium tracking-wider -mt-0.5">COMPLETE SCHOOL ERP</p>
            </div>
          </div>

          {/* Desktop Links */}
          <div className="hidden md:flex items-center gap-8">
            <button
              id="btn-nav-solutions"
              onClick={() => handleNavClick('solutions')}
              className="text-sm font-medium text-gray-600 dark:text-gray-300 hover:text-brand-600 dark:hover:text-brand-405 transition-colors cursor-pointer"
            >
              Enterprise Solutions
            </button>
            <button
              id="btn-nav-demo"
              onClick={() => handleNavClick('demo-center')}
              className="text-sm font-medium text-gray-600 dark:text-gray-300 hover:text-brand-600 dark:hover:text-brand-405 transition-colors cursor-pointer"
            >
              Interactive Demo
            </button>
            <button
              id="btn-nav-calculator"
              onClick={() => handleNavClick('cost-calculator')}
              className="text-sm font-medium text-gray-600 dark:text-gray-300 hover:text-brand-600 dark:hover:text-brand-405 transition-colors cursor-pointer"
            >
              Pricing Calculator
            </button>
            <button
              id="btn-nav-testimonials"
              onClick={() => handleNavClick('testimonials')}
              className="text-sm font-medium text-gray-600 dark:text-gray-300 hover:text-brand-600 dark:hover:text-brand-405 transition-colors cursor-pointer"
            >
              Social Proof
            </button>
            <button
              id="btn-nav-faq"
              onClick={() => handleNavClick('faqs')}
              className="text-sm font-medium text-gray-600 dark:text-gray-300 hover:text-brand-600 dark:hover:text-brand-405 transition-colors cursor-pointer"
            >
              FAQs
            </button>
          </div>

          {/* Desktop CTAs */}
          <div className="hidden md:flex items-center gap-3">
            <button
              id="btn-desktop-theme-toggle"
              type="button"
              onClick={onToggleTheme}
              title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
              className="p-2.5 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 hover:text-slate-900 dark:hover:text-white border border-gray-200/40 dark:border-slate-700/60 transition-all cursor-pointer active:scale-95"
            >
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>

            <div className="flex items-center gap-1.5 text-xs text-brand-700 dark:text-brand-300 bg-brand-50 dark:bg-brand-950/30 px-3 py-1.5 rounded-lg border border-brand-100 dark:border-brand-900/40">
              <ShieldCheck className="h-4 w-4 text-teal-brand-500" />
              <span>NUC & WAEC Aligned</span>
            </div>

            {onLoginClick && (
              <button
                id="btn-sign-in"
                onClick={onLoginClick}
                className="text-sm font-semibold text-gray-700 dark:text-gray-200 hover:text-brand-600 dark:hover:text-brand-400 px-4 py-2 rounded-xl hover:bg-gray-100 dark:hover:bg-slate-800 transition-all cursor-pointer"
              >
                Sign In
              </button>
            )}

            <a
              id="btn-cta-navbar-onboard"
              href="#"
              onClick={(e) => {
                e.preventDefault();
                if (onRegisterClick) onRegisterClick();
              }}
              className="inline-flex items-center justify-center gap-2 px-5 py-2 rounded-xl text-white bg-blue-600 hover:bg-blue-500 font-semibold text-sm transition-all shadow-lg shadow-blue-600/10 cursor-pointer"
            >
              Onboard Your School
              <ArrowRight className="h-4 w-4" />
             </a>
          </div>

          {/* Mobile Menu Trigger */}
          <div className="md:hidden flex items-center gap-2.5">
            <button
              id="btn-mobile-theme-toggle"
              type="button"
              onClick={onToggleTheme}
              className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-all cursor-pointer"
            >
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            
            <a
              id="btn-cta-navbar-onboard"
              href="#"
              onClick={(e) => {
                e.preventDefault();
                if (onRegisterClick) onRegisterClick();
              }}
              className="inline-flex items-center justify-center gap-2 px-5 py-2 rounded-xl text-white bg-blue-600 hover:bg-blue-500 font-semibold text-sm transition-all shadow-lg shadow-blue-600/10 cursor-pointer"
            >
              Onboard Your School
              <ArrowRight className="h-4 w-4" />
            </a>
            <button
              id="btn-toggle-mobile-menu"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="p-1.5 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-800 rounded-lg cursor-pointer"
            >
              {isMobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Drawer Menu */}
      {isMobileMenuOpen && (
        <div className="md:hidden absolute top-full left-0 right-0 bg-white dark:bg-slate-900 border-b border-gray-100 dark:border-slate-800 shadow-lg py-4 px-4 animate-in fade-in slide-in-from-top-4 duration-200">
          <div className="flex flex-col gap-3">
            <button
              id="btn-mob-solutions"
              onClick={() => handleNavClick('solutions')}
              className="text-left py-2 px-3 rounded-lg text-base font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-slate-800 text-sky-950 dark:text-white"
            >
              Enterprise Solutions
            </button>
            <button
              id="btn-mob-demo"
              onClick={() => handleNavClick('demo-center')}
              className="text-left py-2 px-3 rounded-lg text-base font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-slate-800 text-sky-950 dark:text-white"
            >
              Interactive Demo
            </button>
            <button
              id="btn-mob-calculator"
              onClick={() => handleNavClick('cost-calculator')}
              className="text-left py-2 px-3 rounded-lg text-base font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-slate-800 text-sky-950 dark:text-white"
            >
              Pricing Calculator
            </button>
            <button
              id="btn-mob-testimonials"
              onClick={() => handleNavClick('testimonials')}
              className="text-left py-2 px-3 rounded-lg text-base font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-slate-800 text-sky-950 dark:text-white"
            >
              School Success Stories
            </button>
            <button
              id="btn-mob-faq"
              onClick={() => handleNavClick('faqs')}
              className="text-left py-2 px-3 rounded-lg text-base font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-slate-00"
            >
              FAQs
            </button>
            <div className="border-t border-gray-100 dark:border-slate-800 pt-3 flex flex-col gap-2">
              <div className="flex items-center gap-1.5 text-xs text-brand-700 dark:text-brand-300 bg-brand-50 dark:bg-brand-950/40 px-3 py-2 rounded-lg justify-center">
                <ShieldCheck className="h-4 w-4 text-teal-brand-500" />
                <span>NUC & WAEC Aligned Operations</span>
              </div>
              {onLoginClick && (
                <button
                  id="btn-mob-sign-in"
                  onClick={() => { onLoginClick(); setIsMobileMenuOpen(false); }}
                  className="w-full text-center py-2.5 px-4 rounded-xl text-sm font-semibold text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-800 transition-all cursor-pointer"
                >
                  Sign In
                </button>
              )}
             <a
              id="btn-cta-navbar-onboard"
              href="#"
              onClick={(e) => {
                e.preventDefault();
                if (onRegisterClick) onRegisterClick();
              }}
              className="inline-flex items-center justify-center gap-2 px-5 py-2 rounded-xl text-white bg-blue-600 hover:bg-blue-500 font-semibold text-sm transition-all shadow-lg shadow-blue-600/10 cursor-pointer"
            >
              Onboard Your School
              <ArrowRight className="h-4 w-4" />
            </a>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
