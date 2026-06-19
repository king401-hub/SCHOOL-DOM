import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Signin from './SignIn';

import Hero from './components/Hero';
import DashboardPlayground from './components/DashboardPlayground';
import SolutionsGrid from './components/SolutionsGrid.tsx';
import PricingCalculator from './components/PricingCalculator';
import Testimonials from './Testimonials';
import OnboardingWizard from './components/OnboardingWizard';
import LegalDocuments from './components/LegalDocuments';
import ParticleBackground from './components/ParticleBackground';
import Bubbles from './components/Bubbles';
import Reveal from './components/Reveal';
import { FAQS } from './data';
import { 
  Plus, Minus, School, Phone, Mail, MapPin, ShieldCheck, 
  ArrowRight, Heart, Calendar, MessageSquare, CheckCircle, MessageCircle
} from 'lucide-react';

// ============================================
// PAGE VIEW TYPES
// ============================================
type PageView = 'home' | 'signin' | 'signup';

// ============================================
// SESSION KEY
// ============================================
const SESSION_KEY = "schooldom.session";

export default function App() {
  const [isOnboardingOpen, setIsOnboardingOpen] = useState(false);
  const [isLegalOpen, setIsLegalOpen] = useState(false);
  const [isContactOpen, setIsContactOpen] = useState(false);
  const [legalDefaultTab, setLegalDefaultTab] = useState<'terms' | 'privacy'>('terms');
  const [activeFaq, setActiveFaq] = useState<number | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [contactForm, setContactForm] = useState({ name: '', email: '', message: '' });
  
  const [currentPage, setCurrentPage] = useState<PageView>(() => {
    // Check URL path to determine initial page
    const path = window.location.pathname;
    if (path === '/signin') return 'signin';
    if (path === '/signup') return 'signup';
    return 'home';
  });
  
  // Theme state
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window !== 'undefined') {
      const persisted = localStorage.getItem('theme');
      if (persisted === 'light' || persisted === 'dark') {
        return persisted;
      }
      const media = window.matchMedia('(prefers-color-scheme: dark)');
      return media.matches ? 'dark' : 'light';
    }
    return 'light';
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      root.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [theme]);

  // Check if user is already authenticated
  useEffect(() => {
    const session = localStorage.getItem(SESSION_KEY) || sessionStorage.getItem(SESSION_KEY);
    if (session) {
      try {
        const parsed = JSON.parse(session);
        if (parsed.user) {
          setIsAuthenticated(true);
        }
      } catch {
        // Invalid session
      }
    }
  }, []);

  // Newsletter state
  const [newsletterEmail, setNewsletterEmail] = useState('');
  const [newsletterSubscribed, setNewsletterSubscribed] = useState(false);

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const handleSubscribeNewsletter = (e: React.FormEvent) => {
    e.preventDefault();
    if (newsletterEmail.trim() !== '') {
      setNewsletterSubscribed(true);
      setTimeout(() => {
        setNewsletterEmail('');
        setNewsletterSubscribed(false);
      }, 5000);
    }
  };

  // ============================================
  // NAVIGATION HANDLERS
  // ============================================
  const navigateToSignIn = () => {
    // If already authenticated, go home instead
    if (isAuthenticated) {
      navigateToHome();
      return;
    }
    setCurrentPage('signin');
    window.history.pushState({}, '', '/signin');
  };

  const navigateToSignUp = () => {
    // If already authenticated, go home instead
    if (isAuthenticated) {
      navigateToHome();
      return;
    }
    setCurrentPage('signup');
    window.history.pushState({}, '', '/signup');
  };

  const navigateToHome = () => {
    setCurrentPage('home');
    window.history.pushState({}, '', '/');
  };

  const handleAuthenticated = (session: any) => {
    console.log('User authenticated:', session);
    setIsAuthenticated(true);
    // Redirect to dashboard (or use server-provided redirectUrl)
    try {
      const target = (session && (session.redirectUrl || session.redirect_url)) || '/dashboard';
      window.location.href = target;
    } catch (err) {
      navigateToHome();
    }
  };

  const handleSignOut = () => {
    // Clear session
    localStorage.removeItem(SESSION_KEY);
    sessionStorage.removeItem(SESSION_KEY);
    setIsAuthenticated(false);
    navigateToHome();
  };

  // Handle browser back/forward buttons
  useEffect(() => {
    const handlePopState = () => {
      const path = window.location.pathname;
      if (path === '/signin') setCurrentPage('signin');
      else if (path === '/signup') setCurrentPage('signup');
      else setCurrentPage('home');
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleContactSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    fetch("/api/auth/contact/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(contactForm),
    })
      .then(async (response) => {
        const payload = await response.json().catch(() => null);
        if (!response.ok) {
          throw new Error(payload?.message || "Could not send your message.");
        }
        setIsContactOpen(false);
        setContactForm({ name: '', email: '', message: '' });
      })
      .catch((error) => {
        window.alert(error.message || "Could not send your message.");
      });
  };

  // ============================================
  // RENDER SIGNIN PAGE
  // ============================================
  if (currentPage === 'signin' || currentPage === 'signup') {
    return (
      <Signin 
        onAuthenticated={handleAuthenticated}
        onBack={navigateToHome}
        initialMode={currentPage === 'signup' ? 'signup' : 'signin'}
      />
    );
  }

  // ============================================
  // RENDER HOME/LANDING PAGE
  // ============================================
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 font-sans text-slate-800 dark:text-slate-100 antialiased selection:bg-brand-500 selection:text-white transition-colors duration-300 relative isolate overflow-x-hidden">
      {/* Moving Ambient Web Background Particles */}
      <ParticleBackground />

      {/* Live floating bubbles layer (CSS-only, theme-aware) */}
      <Bubbles />

      {/* Header and Navigation */}
      <Navbar 
        onOpenOnboarding={() => setIsOnboardingOpen(true)} 
        scrollToSection={scrollToSection} 
        theme={theme}
        onToggleTheme={() => setTheme(prev => prev === 'light' ? 'dark' : 'light')}
        onSignIn={navigateToSignIn}
        onSignUp={navigateToSignUp}
        isAuthenticated={isAuthenticated}
        onSignOut={handleSignOut}
      />

      {/* Main Content Layout */}
      <main>
        {/* Hero Section with core counts */}
        <Hero 
          onOpenOnboarding={() => setIsOnboardingOpen(true)} 
          scrollToSection={scrollToSection}
          onSignUp={navigateToSignUp}
        />

        {/* 9 major solutions Bento Grid */}
        <Reveal direction="up">
          <SolutionsGrid
            onOpenOnboarding={() => setIsOnboardingOpen(true)}
          />
        </Reveal>

        {/* School Digitization Admin Sandbox Playground */}
        <Reveal direction="left">
          <DashboardPlayground />
        </Reveal>

        {/* Pricing tiers and interactive slider calculator */}
        <Reveal direction="right">
          <PricingCalculator
            onOpenOnboarding={() => setIsOnboardingOpen(true)}
          />
        </Reveal>

        {/* Testimonials Carousel & Trust indicators */}
        <Reveal direction="up">
          <Testimonials />
        </Reveal>

        {/* Interactive FAQ Accordion */}
        <section id="faqs" className="py-20 bg-white dark:bg-slate-950 transition-colors duration-300">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            <Reveal direction="up" className="text-center max-w-2xl mx-auto mb-14">
              <span className="text-xs font-bold uppercase tracking-widest text-[#0d9488] dark:text-teal-brand-400 bg-teal-brand-50 dark:bg-teal-brand-950/40 px-3.5 py-1.5 rounded-full border border-teal-brand-500/20">
                Frequently Answered Questions
              </span>
              <h2 className="font-display font-bold text-3xl text-brand-950 dark:text-white mt-4 tracking-tight">
                Got Questions? We Have Answers.
              </h2>
              <p className="text-gray-500 dark:text-slate-400 mt-2 text-sm leading-relaxed">
                Learn more about how our Hybrid CBT offline bridges, data migrations, and fee ledgers facilitate African classrooms.
              </p>
            </Reveal>

            {/* Accordion List */}
            <div className="space-y-3">
              {FAQS.map((faq, idx) => {
                const isOpen = activeFaq === idx;
                return (
                  <div
                    key={idx}
                    id={`faq-item-${idx}`}
                    className="border border-gray-100 dark:border-slate-800 rounded-2xl bg-slate-50 dark:bg-slate-900 overflow-hidden text-left transition-all"
                  >
                    <button
                      id={`faq-btn-trigger-${idx}`}
                      onClick={() => setActiveFaq(isOpen ? null : idx)}
                      className="w-full flex justify-between items-center p-5 text-left font-semibold text-brand-950 dark:text-white text-sm sm:text-base hover:bg-slate-100/60 dark:hover:bg-slate-800/60 transition-colors cursor-pointer"
                    >
                      <span className="pr-4">{faq.question}</span>
                      <span className={`p-1 rounded-lg bg-white dark:bg-slate-800 border border-gray-150 dark:border-slate-700 shrink-0 text-gray-500 dark:text-slate-300 transition-transform ${isOpen ? 'rotate-180' : ''}`}>
                        {isOpen ? <Minus className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                      </span>
                    </button>

                    {isOpen && (
                      <div className="p-5 pt-0 text-xs sm:text-sm text-gray-600 dark:text-slate-300 leading-relaxed bg-white dark:bg-slate-900 border-t border-gray-100 dark:border-slate-800 animate-in fade-in slide-in-from-top-2 duration-150">
                        {faq.answer}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Support Callout Widget */}
            <div className="mt-10 p-5 bg-brand-50 dark:bg-brand-950/30 border border-brand-100/70 dark:border-brand-900/50 rounded-2xl flex flex-col sm:flex-row items-center justify-between text-left gap-4">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 text-brand-600 bg-white dark:bg-slate-800 rounded-xl flex items-center justify-center font-bold shadow-xs">☎</div>
                <div>
                  <h5 className="font-display font-semibold text-sm text-brand-950 dark:text-white">Need a custom integration or contract schedule?</h5>
                  <p className="text-xs text-brand-800 dark:text-brand-300">Our senior migration experts are ready to hop on an onboarding call.</p>
                </div>
              </div>
              <button
                id="faq-btn-custom-support"
                onClick={() => setIsContactOpen(true)}
                className="inline-flex items-center gap-1 bg-brand-600 hover:bg-brand-700 active:bg-brand-800 text-white rounded-xl px-4.5 py-2 text-xs font-bold transition-all shadow-xs cursor-pointer"
              >
                Schedule Integration Call
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </section>

        {/* Bottom Call to Action Section Banner */}
        <Reveal as="section" direction="up" className="py-20 bg-radial from-brand-900 via-brand-950 to-[#1e1b4b] text-white overflow-hidden relative text-left">
          <div className="absolute top-[-10%] right-[-10%] w-64 h-64 bg-teal-brand-500/15 rounded-full filter blur-2xl pointer-events-none" />
          
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10 space-y-6">
            <span className="text-[10px] sm:text-xs font-bold uppercase tracking-widest text-teal-brand-500 bg-teal-brand-500/10 border border-teal-500/20 px-3.5 py-1.5 rounded-full">
              SECURE DEPLOYMENT PROTOCOL
            </span>
            <h2 className="font-display font-extrabold text-3xl sm:text-4xl lg:text-5xl leading-tight">
              Ready to Completely Digitize <br />Your School Group?
            </h2>
            <p className="text-slate-300 text-sm sm:text-base max-w-2xl mx-auto leading-relaxed">
              Transition physically to Schooldom Academy today. Take advantage of our 100% free white-glove data migration tier. We setup offline CBT boxes, sync class notes, design ID PVC credentials, and map finance gates.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
              <button
                id="btn-bottom-onboard"
                onClick={() => setIsContactOpen(true)}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-xl text-sm font-bold text-slate-900 bg-teal-brand-500 hover:bg-teal-brand-600 transition-all cursor-pointer"
              >
                Start Onboarding Free
                <ArrowRight className="h-4.5 w-4.5" />
              </button>
              <button
                id="btn-bottom-calculator"
                onClick={() => scrollToSection('cost-calculator')}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-xl text-sm font-bold text-white bg-slate-850/80 hover:bg-slate-800 border border-slate-700/60 cursor-pointer"
              >
                Estimate termly cost
              </button>
            </div>

            <div className="flex flex-wrap justify-center items-center gap-x-8 gap-y-2 pt-6 text-xs text-slate-400 font-medium">
              <div className="flex items-center gap-1.5">
                <span className="text-emerald-500 text-sm">✓</span>
                <span>Active WAEC past records pre-loaded</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-emerald-500 text-sm">✓</span>
                <span>99.8% Parent fees reconciliation SLA</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-emerald-500 text-sm">✓</span>
                <span>Zero installation fees</span>
              </div>
            </div>
          </div>
        </Reveal>
      </main>

      {/* Integrated Status Bar Footer from Vibrant Palette */}
      <div className="bg-slate-900 border-b border-slate-800/80 px-4 sm:px-8 py-3.5 flex flex-col md:flex-row justify-between items-center text-white gap-4 text-xs">
        <div className="flex flex-wrap items-center justify-center gap-6">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
            <span className="text-[10px] font-bold tracking-wider uppercase text-slate-300">CBT ENGINE: ONLINE</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-teal-brand-500 rounded-full animate-pulse"></div>
            <span className="text-[10px] font-bold tracking-wider uppercase text-slate-300">NDPC COMPLIANCE: VERIFIED</span>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[10px] font-bold">
            <span className="text-slate-500">MIGRATION PARTNERS:</span>
            <span className="bg-white/5 border border-white/10 px-2 py-0.5 rounded text-brand-300">Microsoft Education</span>
            <span className="bg-white/5 border border-white/10 px-2 py-0.5 rounded text-brand-300">Google Classroom</span>
          </div>
        </div>
        <div className="flex items-center gap-4 text-[10px] font-bold">
           <span className="text-slate-500 tracking-widest uppercase">SYSTEMS INTEGRITY VERIFIED</span>
           <button 
             onClick={() => setIsOnboardingOpen(true)}
             className="flex items-center gap-1.5 bg-brand-600 hover:bg-brand-700 active:bg-brand-800 transition-colors px-3.5 py-1 rounded-full text-white cursor-pointer text-[10px]"
           >
             <span className="text-xs">⊛</span>
             <span>HELP CENTER</span>
           </button>
        </div>
      </div>

      {/* Corporate Professional Footer */}
      <footer className="bg-slate-950 text-slate-300 border-t border-slate-900 overflow-hidden relative text-left">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-10 items-start">
            
            {/* Column 1: Brand details */}
            <div className="md:col-span-5 space-y-6">
              <div className="flex items-center gap-2.5">
                <div className="h-10 w-10 rounded-xl bg-brand-600 flex items-center justify-center text-white font-bold text-lg shadow-md shadow-brand-500/10">
                  <School className="h-5.5 w-5.5" />
                </div>
                <div>
                  <div className="flex items-baseline">
                    <span className="font-display font-extrabold text-xl text-white tracking-tight">Schooldom</span>
                    <span className="font-display font-medium text-[10px] text-teal-brand-500 ml-1 bg-teal-brand-500/10 px-1.5 py-0.5 rounded-md border border-teal-brand-500/10">ACADEMY</span>
                  </div>
                  <p className="text-[10px] text-slate-500 font-medium tracking-wider -mt-0.5">COMPLETE SCHOOL ERP</p>
                </div>
              </div>

              <p className="text-xs text-slate-400 leading-relaxed max-w-sm">
                Schooldom Academy is the trusted West African Enterprise Resource Platform and comprehensive school manager. We operate secure local servers for 100% offline testing while delivering world-class digital progress logs.
              </p>

              {/* Compliance Badges */}
              <div className="space-y-2 max-w-sm">
                <div className="flex items-center gap-2.5 text-[10px] text-slate-400 bg-slate-900 border border-slate-800/80 p-2.5 rounded-xl">
                  <ShieldCheck className="h-5 w-5 text-teal-brand-500 shrink-0" />
                  <span>Regulatory verified by NUC structural directives and standard WAEC/NECO score computation rubrics.</span>
                </div>
                <div className="flex items-center gap-2.5 text-[10px] text-slate-400 bg-slate-900 border border-slate-800/80 p-2.5 rounded-xl">
                  <div className="h-5 w-5 rounded-md bg-teal-brand-500/10 text-teal-brand-500 flex items-center justify-center font-bold text-[8px] shrink-0 border border-teal-brand-500/20">🇳🇬</div>
                  <span>
                    Fully registered and in compliance with the **Nigeria Data Protection Commission (NDPC)** under the NDPA.
                  </span>
                </div>
              </div>
            </div>

            {/* Column 2: Solutions modules quick references */}
            <div className="md:col-span-3 space-y-4">
              <h5 className="font-display font-bold text-xs uppercase tracking-widest text-slate-400">Enterprise Modules</h5>
              <div className="flex flex-col gap-2.5 text-xs text-slate-400">
                <button onClick={() => scrollToSection('solutions')} className="text-left hover:text-white transition-colors cursor-pointer">Hybrid CBT Exam Suite</button>
                <button onClick={() => scrollToSection('solutions')} className="text-left hover:text-white transition-colors cursor-pointer">Bursar Finance Ledger</button>
                <button onClick={() => scrollToSection('solutions')} className="text-left hover:text-white transition-colors cursor-pointer">Biometric QR Safety Check</button>
                <button onClick={() => scrollToSection('solutions')} className="text-left hover:text-white transition-colors cursor-pointer">Digital PVC ID Generator</button>
                <button onClick={() => scrollToSection('solutions')} className="text-left hover:text-white transition-colors cursor-pointer">Lesson Planner Curriculas</button>
              </div>
            </div>

            {/* Column 3: Contact / Physical premises */}
            <div className="md:col-span-4 space-y-5">
              <h5 className="font-display font-bold text-xs uppercase tracking-widest text-slate-400">Registrar & HQ Location</h5>
              
              <div className="space-y-3.5 text-xs text-slate-400">
                <div className="flex items-start gap-2">
                  <MapPin className="h-4 w-4 text-brand-500 shrink-0 mt-0.5" />
                  <span>Executive Suites, Admiralty Way, Lekki Phase 1, Lagos, Nigeria</span>
                </div>
                <div className="flex items-center gap-2">
                  <Phone className="h-4 w-4 text-brand-500 shrink-0" />
                  <span>+234 907 682 1365 (Support helpline)</span>
                </div>
                <div className="flex items-center gap-2">
                  <Mail className="h-4 w-4 text-brand-500 shrink-0" />
                  <span>enquiry@schooldom.academy</span>
                </div>
                <div className="pt-1.5">
                  <a
                    href="https://wa.me/2349076821365?text=Hello%20Schooldom%20Academy%20Support"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-emerald-650 hover:bg-emerald-700 active:scale-[0.98] text-white font-bold text-xs transition-all shadow-xs"
                    id="whatsapp-footer-support"
                  >
                    <MessageCircle className="h-4 w-4 fill-white/10" />
                    Chat on WhatsApp
                  </a>
                </div>
              </div>

              {/* Newsletter Sub */}
              <div className="border-t border-slate-900 pt-4 space-y-2">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Subscribe for Academic Operations journals</p>
                {newsletterSubscribed ? (
                  <p className="text-xs text-teal-brand-500 font-semibold animate-pulse">✓ Thank you for subscribing to Schooldom Journals!</p>
                ) : (
                  <form onSubmit={handleSubscribeNewsletter} className="flex gap-1.5">
                    <input
                      id="input-newsletter"
                      type="email"
                      required
                      placeholder="proprietor@academy.com"
                      value={newsletterEmail}
                      onChange={(e) => setNewsletterEmail(e.target.value)}
                      className="flex-1 bg-slate-900 border border-slate-850 px-3 py-2 rounded-lg text-xs font-medium text-white placeholder-slate-500 focus:border-brand-500"
                    />
                    <button
                      id="btn-subscribe-newsletter"
                      type="submit"
                      className="px-3.5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-xs font-bold transition-all cursor-pointer"
                    >
                      Subscribe
                    </button>
                  </form>
                )}
              </div>
            </div>

          </div>

          {/* Clean bottom credit */}
          <div className="border-t border-slate-900 mt-14 pt-6 flex flex-col sm:flex-row items-center justify-between text-[11px] text-slate-500 font-medium">
            <p>© {new Date().getFullYear()} Schooldom Academy. All Rights Reserved. Complete School ERP Solutions.</p>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mt-4 sm:mt-0">
              <button 
                onClick={() => { setLegalDefaultTab('terms'); setIsLegalOpen(true); }}
                className="hover:text-slate-300 transition-colors cursor-pointer text-left"
              >
                Terms of Service
              </button>
              <span>•</span>
              <button 
                onClick={() => { setLegalDefaultTab('privacy'); setIsLegalOpen(true); }}
                className="hover:text-slate-300 transition-colors cursor-pointer text-left"
              >
                Privacy Policy &amp; NDPA Code
              </button>
              <span>•</span>
              <span className="text-teal-brand-500 bg-teal-brand-500/5 px-2 py-0.5 rounded border border-teal-brand-500/10 text-[10px]">NDPC Compliant</span>
              <span>•</span>
              <a href="#hero-section" className="hover:text-slate-400">Back to Top</a>
            </div>
          </div>
        </div>
      </footer>

      {/* Onboarding Multi-step Wizard Popup Modal */}
      <OnboardingWizard 
        isOpen={isOnboardingOpen} 
        onClose={() => setIsOnboardingOpen(false)} 
      />

      {/* Trust & Legal Portal Modal */}
      <LegalDocuments
        isOpen={isLegalOpen}
        onClose={() => setIsLegalOpen(false)}
        defaultTab={legalDefaultTab}
      />

      {isContactOpen && (
        <div
          className="fixed inset-0 z-[60] bg-slate-950/80 backdrop-blur-sm flex items-center justify-center px-4 py-8"
          role="dialog"
          aria-modal="true"
          aria-labelledby="contact-popup-title"
          onClick={() => setIsContactOpen(false)}
        >
          <div
            className="w-full max-w-xl rounded-2xl border border-white/10 bg-slate-950 text-white shadow-2xl overflow-hidden"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4 p-5 border-b border-white/10">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-teal-300">Contact Schooldom</p>
                <h3 id="contact-popup-title" className="mt-1 text-xl font-extrabold">Send an email request</h3>
                <p className="mt-1 text-sm text-slate-300">Tell us what you need and we will open your email app with the message ready to send.</p>
              </div>
              <button
                type="button"
                onClick={() => setIsContactOpen(false)}
                className="rounded-xl border border-white/10 px-3 py-2 text-sm font-bold text-slate-300 hover:text-white hover:bg-white/5"
                aria-label="Close contact form"
              >
                Close
              </button>
            </div>
            <form onSubmit={handleContactSubmit} className="p-5 space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-2 text-sm font-semibold">
                  <span>Name</span>
                  <input
                    type="text"
                    value={contactForm.name}
                    onChange={(event) => setContactForm((current) => ({ ...current, name: event.target.value }))}
                    className="w-full rounded-xl border border-white/10 bg-slate-900 px-4 py-3 text-white outline-none focus:border-teal-400"
                    placeholder="Your name"
                  />
                </label>
                <label className="space-y-2 text-sm font-semibold">
                  <span>Email</span>
                  <input
                    type="email"
                    required
                    value={contactForm.email}
                    onChange={(event) => setContactForm((current) => ({ ...current, email: event.target.value }))}
                    className="w-full rounded-xl border border-white/10 bg-slate-900 px-4 py-3 text-white outline-none focus:border-teal-400"
                    placeholder="you@example.com"
                  />
                </label>
              </div>
              <label className="space-y-2 text-sm font-semibold block">
                <span>Message</span>
                  <textarea
                    required
                  rows={5}
                  value={contactForm.message}
                  onChange={(event) => setContactForm((current) => ({ ...current, message: event.target.value }))}
                  className="w-full rounded-xl border border-white/10 bg-slate-900 px-4 py-3 text-white outline-none focus:border-teal-400 resize-none"
                  placeholder="Tell us about your integration or contract request"
                />
              </label>
              <div className="flex flex-col sm:flex-row justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsContactOpen(false)}
                  className="rounded-xl border border-white/10 px-5 py-3 text-sm font-bold text-slate-300 hover:text-white hover:bg-white/5"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-teal-500 px-5 py-3 text-sm font-bold text-slate-950 hover:bg-teal-400"
                >
                  <Mail className="h-4 w-4" />
                  Open Email Draft
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Floating Live WhatsApp Customer Support Button */}
      <a
        href="https://wa.me/2349076821365?text=Hello%20Schooldom%20Academy%20Support"
        target="_blank"
        rel="noopener noreferrer"
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 px-4 py-3.5 rounded-full bg-emerald-600 text-white font-bold text-sm shadow-2xl hover:bg-emerald-705 hover:scale-105 active:scale-95 transition-all group duration-300 border border-emerald-400/25"
        title="Chat on WhatsApp"
        id="whatsapp-floating-support"
      >
        <MessageCircle className="h-5 w-5 fill-white/10 shrink-0" />
        <span className="hidden sm:inline-block max-w-0 overflow-hidden group-hover:max-w-xs transition-all duration-550 ease-in-out whitespace-nowrap">
          Support Hotline
        </span>
        <span className="relative flex h-2.5 w-2.5 shrink-0">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-200 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-100"></span>
        </span>
      </a>
    </div>
  );
}
