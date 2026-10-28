import { Suspense, lazy, useEffect, useState } from 'react';
import { HashRouter, Routes, Route, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import { useTranslation } from 'react-i18next';
import Lenis from 'lenis';
import { setLenisInstance, smoothScrollTo } from './lib/smoothScroll';
import AmbientField from './components/AmbientField';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import Features from './components/Features';
import CBTSection from './components/CBTSection';
import Demo from './components/Demo';
import Testimonials from './components/Testimonials';
import Pricing from './components/Pricing';
import Footer from './components/Footer';
import FAQPage from './pages/FAQ';
import ContactPage from './pages/Contact';
import PrivacyPage from './pages/Privacy';

const PAGE_EASE = [0.16, 1, 0.3, 1] as const;
const pageMotion = {
  initial: { opacity: 0, x: 28 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -28 },
  transition: { duration: 0.4, ease: PAGE_EASE },
};

const SignUpPage = lazy(() => import('./pages/SignUp'));

const ADMIN_APP_URL =
  (import.meta as any).env?.VITE_ADMIN_APP_URL ||
  (import.meta.env.DEV ? 'http://localhost:5173/app/' : '/app/');

function WhatsAppButton() {
  const { t } = useTranslation();
  return (
    <a
      href="https://wa.me/2349076821365"
      target="_blank"
      rel="noopener noreferrer"
      aria-label={t('nav.whatsapp')}
      className="fixed bottom-6 right-6 z-[150] h-14 w-14 rounded-full flex items-center justify-center hover:scale-105 transition-transform"
      style={{ background: '#25D366', boxShadow: '0 8px 24px rgba(0,0,0,0.3)' }}
    >
      <svg viewBox="0 0 24 24" className="h-7 w-7 relative" fill="#fff" aria-hidden="true">
        <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.297-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
      </svg>
    </a>
  );
}

function HomePage() {
  const handleDemo = () => { smoothScrollTo('#demo'); };

  return (
    <>
      <Hero onDemo={handleDemo} />
      <Features />
      <CBTSection />
      <Demo />
      <Testimonials />
      <Pricing />
    </>
  );
}

/** Animates between routes - exit finishes before the next page enters
 * (mode="wait"), so navigating (e.g. into Sign Up) is a real transition
 * instead of an instant swap. `location` is captured once per render and
 * handed to <Routes> explicitly so the outgoing route's content is what
 * actually plays the exit animation, not whatever the URL has already
 * become - the standard react-router + AnimatePresence pairing. */
function AnimatedMain() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait">
      <motion.main key={location.pathname} {...pageMotion}>
        <Routes location={location}>
          <Route path="/" element={<HomePage />} />
          <Route path="/faq" element={<FAQPage />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/signup" element={<Suspense fallback={null}><SignUpPage /></Suspense>} />
        </Routes>
      </motion.main>
    </AnimatePresence>
  );
}

export default function App() {
  const [exiting, setExiting] = useState(false);

  // Sign In leaves this app entirely (a separate deployed app at
  // ADMIN_APP_URL, not a client-side route) - a hard window.location nav has
  // no transition of its own, so play a brief exit animation on this page
  // first and only fire the redirect once it's finished. Reduced-motion
  // visitors get the plain instant redirect, matching how Lenis is skipped
  // for them below.
  const handleSignIn = () => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      window.location.href = `${ADMIN_APP_URL}signin`;
      return;
    }
    setExiting(true);
    setTimeout(() => { window.location.href = `${ADMIN_APP_URL}signin`; }, 420);
  };

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const lenis = new Lenis({ duration: 1.1, easing: t => 1 - Math.pow(1 - t, 3) });
    setLenisInstance(lenis);
    let rafId = requestAnimationFrame(function raf(time) {
      lenis.raf(time);
      rafId = requestAnimationFrame(raf);
    });
    return () => {
      cancelAnimationFrame(rafId);
      lenis.destroy();
      setLenisInstance(null);
    };
  }, []);

  return (
    <HashRouter>
      <motion.div
        className="app-root"
        animate={exiting ? { opacity: 0, y: -16, filter: 'blur(6px)' } : { opacity: 1, y: 0, filter: 'blur(0px)' }}
        transition={{ duration: 0.4, ease: [0.4, 0, 1, 1] }}
      >
        <AmbientField />
        <Navbar onSignIn={handleSignIn} />

        <AnimatedMain />

        <Footer />

        <WhatsAppButton />
      </motion.div>
    </HashRouter>
  );
}
