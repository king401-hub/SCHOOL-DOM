import { useState } from 'react';
import { TESTIMONIALS } from './data';
import { Quote, ChevronLeft, ChevronRight, Award, UserCheck, ShieldCheck } from 'lucide-react';

export default function Testimonials() {
  const [currentIndex, setCurrentIndex] = useState(0);

  const prevSlide = () => {
    setCurrentIndex((prev) => (prev === 0 ? TESTIMONIALS.length - 1 : prev - 1));
  };

  const nextSlide = () => {
    setCurrentIndex((prev) => (prev === TESTIMONIALS.length - 1 ? 0 : prev + 1));
  };

  const curTest = TESTIMONIALS[currentIndex];

  return (
    <section id="testimonials" className="py-20 bg-gray-50 dark:bg-slate-950 border-y border-gray-100/60 dark:border-slate-900 transition-colors duration-300">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

        {/* Title sections */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-bold uppercase tracking-widest text-brand-600 dark:text-brand-400 bg-brand-50 dark:bg-brand-950/40 px-3.5 py-1.5 rounded-full border border-brand-200/50 dark:border-brand-900/50">
            Social Proof & Trust Indicators
          </span>
          <h2 className="font-display font-bold text-3xl sm:text-4xl text-brand-950 dark:text-white mt-4 tracking-tight">
            Loved By Proprietors and School Administrators
          </h2>
          <p className="text-gray-600 dark:text-slate-400 mt-3 text-base">
            See how schools across Ibadan, Lekki, Kaduna, and Port Harcourt successfully transition physically to modern digitized management systems.
          </p>
        </div>

        {/* Big visual carousel and stats card display grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center justify-center max-w-6xl mx-auto">

          {/* Left testimonial card */}
          <div className="lg:col-span-7 bg-white dark:bg-slate-900 p-6 sm:p-10 rounded-3xl glow-card text-left relative min-h-[350px] flex flex-col justify-between">
            <div className="absolute top-6 right-6 text-brand-100 dark:text-brand-900/60 pointer-events-none">
              <Quote className="h-16 w-16" />
            </div>

            <div>
              {/* Star Rating decoration */}
              <div className="flex gap-1 text-amber-400 mb-6">
                {[...Array(5)].map((_, i) => (
                  <span key={i} className="text-sm">★</span>
                ))}
                <span className="text-xs text-gray-400 dark:text-slate-500 font-semibold ml-2 font-mono">5.0 OUTSTANDING</span>
              </div>

              <blockquote className="text-base sm:text-lg text-brand-950 dark:text-white leading-relaxed font-normal italic">
                "{curTest.quote}"
              </blockquote>
            </div>

            {/* Principal signature profile */}
            <div className="border-t border-gray-100 dark:border-slate-800 pt-6 mt-8 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <p className="font-display font-extrabold text-base text-brand-950 dark:text-white">{curTest.principalName}</p>
                <p className="text-xs font-semibold text-gray-500 dark:text-slate-400">{curTest.role} • {curTest.schoolName}</p>
                <p className="text-xs text-brand-500 dark:text-brand-400 font-medium mt-0.5">{curTest.location}</p>
              </div>

              {/* Slider arrow controls */}
              <div className="flex gap-2 shrink-0">
                <button
                  id="btn-prev-test"
                  onClick={prevSlide}
                  className="p-2 border border-gray-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 active:bg-slate-100 dark:active:bg-slate-700 rounded-xl cursor-pointer"
                >
                  <ChevronLeft className="h-5 w-5 text-gray-600 dark:text-slate-300" />
                </button>
                <button
                  id="btn-next-test"
                  onClick={nextSlide}
                  className="p-2 border border-brand-100 dark:border-brand-900/50 text-brand-600 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-950/40 rounded-xl cursor-pointer"
                >
                  <ChevronRight className="h-5 w-5" />
                </button>
              </div>
            </div>

          </div>

          {/* Right Metrics summary visual block */}
          <div className="lg:col-span-5 bg-slate-900 text-white rounded-3xl p-6 sm:p-8 flex flex-col justify-between h-full min-h-[350px] text-left border border-slate-800 relative overflow-hidden">
            {/* Design glow background */}
            <div className="absolute top-[-10%] right-[-10%] w-32 h-32 bg-teal-brand-500/10 rounded-full filter blur-xl pointer-events-none" />

            <div className="space-y-6">
              <div className="flex items-center gap-2 text-teal-brand-500">
                <ShieldCheck className="h-5 w-5" />
                <span className="text-xs font-bold uppercase tracking-wider font-mono">Verified Integration Metrics</span>
              </div>

              <div>
                <h4 className="font-display font-bold text-lg text-white">Trust Ecosystem Scale</h4>
                <p className="text-xs text-slate-400 mt-1">Real-time statistics updated directly from registered African educational institutes.</p>
              </div>

              <div className="space-y-5">
                <div className="flex items-center gap-4">
                  <div className="h-10 w-10 rounded-xl bg-slate-800 text-teal-brand-500 flex items-center justify-center shrink-0">
                    <Award className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-slate-300">250+ Schools Onboarded</p>
                    <p className="text-xs text-slate-500">Includes multi-school groups and vocational centres.</p>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div className="h-10 w-10 rounded-xl bg-slate-800 text-teal-brand-500 flex items-center justify-center shrink-0">
                    <UserCheck className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-slate-300">85,000+ Enrolled Students</p>
                    <p className="text-xs text-slate-500">Each student earns profile credentials and quiz XP daily.</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="border-t border-slate-800 pt-6 mt-8 grid grid-cols-2 gap-4 text-xs font-medium text-slate-400">
              <div>
                <p className="text-white font-extrabold text-lg leading-none">99.8%</p>
                <p className="text-[10px] uppercase text-slate-500 font-bold mt-1.5">Server Uptime API</p>
              </div>
              <div>
                <p className="text-white font-extrabold text-lg leading-none">₦450M+</p>
                <p className="text-[10px] uppercase text-slate-500 font-bold mt-1.5">Tuition Collections Reconciled</p>
              </div>
            </div>

          </div>

        </div>

      </div>
    </section>
  );
}
