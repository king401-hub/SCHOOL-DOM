import { useState, useEffect } from 'react';
import { ArrowRight, Sparkles, CheckCircle2, ShieldAlert, Cpu } from 'lucide-react';

const SLIDING_PHRASES = [
  "Admission to Graduation",
  "Offline CBT to Cloud Results",
  "Fee Ledger to Settlement",
  "Lesson Plans to Report Cards"
];

interface AnimatedCounterProps {
  target: number;
  suffix?: string;
  prefix?: string;
}

function AnimatedCounter({ target, suffix = "", prefix = "" }: AnimatedCounterProps) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let active = true;
    const duration = 1800; // ms
    const frames = 60;
    const stepTime = duration / frames;
    let frame = 0;

    const interval = setInterval(() => {
      frame++;
      const progress = frame / frames;
      // easeOutExpo
      const ease = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      const current = Math.floor(ease * target);
      
      if (active) {
        setCount(current);
      }

      if (frame >= frames) {
        clearInterval(interval);
      }
    }, stepTime);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [target]);

  const formatValue = (val: number) => {
    if (val >= 1000000) {
      return (val / 1000000).toFixed(1) + "M";
    }
    return val.toLocaleString();
  };

  return <span>{prefix}{formatValue(count)}{suffix}</span>;
}

interface HeroProps {
  onOpenOnboarding: () => void;
  scrollToSection: (id: string) => void;
  onSignUp?: () => void;  // Add this
}

export default function Hero({ onOpenOnboarding, scrollToSection, onSignUp }: HeroProps) {
  // Typewriter effect: type a phrase out, hold, delete, then move to the next.
  const [phraseIdx, setPhraseIdx] = useState(0);
  const [displayText, setDisplayText] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const fullPhrase = SLIDING_PHRASES[phraseIdx];
    let timeout: ReturnType<typeof setTimeout>;

    if (!isDeleting && displayText === fullPhrase) {
      // Finished typing — hold the full phrase, then start deleting.
      timeout = setTimeout(() => setIsDeleting(true), 1800);
    } else if (isDeleting && displayText === '') {
      // Finished deleting — advance to the next phrase.
      setIsDeleting(false);
      setPhraseIdx((prev) => (prev + 1) % SLIDING_PHRASES.length);
    } else {
      const nextText = isDeleting
        ? fullPhrase.substring(0, displayText.length - 1)
        : fullPhrase.substring(0, displayText.length + 1);
      timeout = setTimeout(() => setDisplayText(nextText), isDeleting ? 45 : 85);
    }

    return () => clearTimeout(timeout);
  }, [displayText, isDeleting, phraseIdx]);

  const handleSignUp = () => {
    if (onSignUp) {
      onSignUp();
    }
  };

  return (
    <section 
      id="hero-section"
      className="relative pt-32 pb-20 md:pt-40 md:pb-28 overflow-hidden bg-radial from-brand-50/40 via-white to-white dark:from-slate-900/40 dark:via-slate-950 dark:to-slate-950 transition-colors duration-300"
    >
      {/* Visual background accents with premium drift animations */}
      <div className="absolute top-[-10%] right-[-10%] w-[50%] h-[50%] bg-brand-200/20 rounded-full filter blur-[100px] pointer-events-none animate-blob" />
      <div className="absolute bottom-[5%] left-[-10%] w-[40%] h-[40%] bg-teal-brand-50/30 rounded-full filter blur-[80px] pointer-events-none animate-blob-delayed" />
      <div className="absolute top-[40%] left-[20%] w-[300px] h-[300px] bg-brand-100/15 rounded-full filter blur-[90px] pointer-events-none animate-blob-slow" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="text-center max-w-4xl mx-auto">
          {/* Tagline Badge */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-brand-50 dark:bg-brand-950/40 border border-brand-200/60 dark:border-brand-900/60 shadow-xs mb-6 sm:mb-8 animate-fade-in hover:scale-105 transition-transform duration-300">
            <Sparkles className="h-4 w-4 text-brand-500 animate-pulse" />
            <span className="text-xs sm:text-sm font-semibold tracking-wide text-brand-900 dark:text-brand-200 uppercase font-display">
              Enterprise Resource Platform & Complete School Manager
            </span>
          </div>

          {/* Large display typography */}
          <h1 className="font-display font-extrabold text-4xl sm:text-5xl md:text-6xl text-brand-950 dark:text-white tracking-tight leading-[1.15] mb-6 block select-none">
            <span className="block opacity-95">Digitize Your School Operations from</span>
            <span className="block mt-2 min-h-[2.5em] sm:min-h-[1.3em] w-full flex items-center justify-center px-2">
              <span className="gradient-text text-center" aria-live="polite">
                {displayText}
              </span>
              <span className="typing-caret" aria-hidden="true" />
            </span>
          </h1>

          <p className="font-sans text-base sm:text-lg md:text-xl text-gray-600 dark:text-slate-300 font-normal leading-relaxed mb-10 max-w-3xl mx-auto animate-fade-in-delayed">
            Schooldom Academy is the unified school manager built to run and scale African schools. 
            Experience an avalanche of digital systems: Hybrid offline/online CBT, automated report cards, biometric 
            attendance, parent fees gateways, lesson planners, WAEC/JAMB exam prep, and much more.
          </p>

          {/* Strong action CTA buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-14 animate-fade-in-delayed">
            {/* Get Started - Now goes to Sign Up */}
            {/* Onboard Your School - Opens Onboarding Wizard */}
            <button
              id="hero-btn-onboard"
              onClick={onOpenOnboarding}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-8 py-4 rounded-2xl text-base font-bold text-white bg-teal-brand-500 hover:bg-teal-brand-600 active:bg-teal-brand-700 shadow-lg shadow-teal-brand-500/20 hover:shadow-teal-brand-500/35 transition-all hover:translate-y-[-1px] cursor-pointer"
            >
               Get started for free           
              <ArrowRight className="h-5 w-5" />
            </button>
            
            <button
              id="hero-btn-demo"
              onClick={() => scrollToSection('demo-center')}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-8 py-4 rounded-2xl text-base font-bold text-gray-700 dark:text-slate-200 bg-white dark:bg-slate-900 hover:bg-gray-50 dark:hover:bg-slate-800 border border-gray-200/80 dark:border-slate-800 hover:border-gray-300 dark:hover:border-slate-700 shadow-xs transition-all active:translate-y-0 cursor-pointer"
            >
              Explore Interactive Demo
            </button>
          </div>

          {/* Business Model / Support Model Clarification */}
          <p className="text-xs font-semibold text-brand-700 dark:text-brand-350 bg-brand-50/45 dark:bg-slate-900/60 border border-brand-100 dark:border-slate-800/80 max-w-xl mx-auto rounded-xl px-4.5 py-2.5 mb-14 -mt-8 animate-fade-in-delayed shadow-xs">
            ✨ <strong className="text-brand-900 dark:text-brand-200">100% Free for Admins &amp; Teachers:</strong> Manage modules, layout CBTs, track attendance and print ID badges free. Student logins are restricted until active seats are activated.
          </p>

          {/* Social Proof Stats Counter Panel */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-5xl mx-auto bg-white dark:bg-slate-900 p-6 sm:p-8 rounded-3xl glow-card dark:border-slate-800 animate-fade-in-delayed shadow-xl shadow-brand-100/30 dark:shadow-none">
            <div className="text-center p-3 border-r border-gray-100/80 dark:border-slate-800 last:border-0 max-md:even:border-0 hover:scale-[1.03] transition-transform duration-300">
              <p className="font-display font-extrabold text-3xl sm:text-4xl text-brand-950 dark:text-white tracking-tight">
                <AnimatedCounter target={250} suffix="+" />
              </p>
              <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider mt-1.5">Registered Schools</p>
            </div>
            <div className="text-center p-3 md:border-r border-gray-100/80 dark:border-slate-800 last:border-0 max-md:border-none hover:scale-[1.03] transition-transform duration-300">
              <p className="font-display font-extrabold text-3xl sm:text-4xl text-brand-950 dark:text-white tracking-tight">
                <AnimatedCounter target={85000} suffix="+" />
              </p>
              <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider mt-1.5">Active Students</p>
            </div>
            <div className="text-center p-3 border-r border-gray-100/80 dark:border-slate-800 last:border-0 max-md:even:border-0 hover:scale-[1.03] transition-transform duration-300">
              <p className="font-display font-extrabold text-3xl sm:text-4xl text-brand-950 dark:text-white tracking-tight">
                <AnimatedCounter target={1200000} suffix="+" />
              </p>
              <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider mt-1.5">Quizzes & Exams Written</p>
            </div>
            <div className="text-center p-3 last:border-0 hover:scale-[1.03] transition-transform duration-300">
              <p className="font-display font-extrabold text-3xl sm:text-4xl text-teal-brand-500 tracking-tight">
                <AnimatedCounter target={450000000} prefix="₦" suffix="+" />
              </p>
              <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider mt-1.5">Tuition Reconciled</p>
            </div>
          </div>
        </div>

        {/* Highlighted trust banner items */}
        <div className="mt-12 flex flex-wrap justify-center items-center gap-x-8 gap-y-4 text-sm text-gray-500 dark:text-slate-400 font-medium">
          <div className="flex items-center gap-1.5">
            <CheckCircle2 className="h-4.5 w-4.5 text-teal-brand-500" />
            <span>Parent portal app download included</span>
          </div>
          <div className="hidden sm:block text-gray-300 dark:text-slate-800">•</div>
          <div className="flex items-center gap-1.5">
            <Cpu className="h-4.5 w-4.5 text-brand-500" />
            <span>Hybrid Local Server - 100% Offline CBT</span>
          </div>
          <div className="hidden sm:block text-gray-300 dark:text-slate-800">•</div>
          <div className="flex items-center gap-1.5">
            <CheckCircle2 className="h-4.5 w-4.5 text-teal-brand-500" />
            <span>Free White-glove Data Migration</span>
          </div>
        </div>
      </div>
    </section>
  );
}