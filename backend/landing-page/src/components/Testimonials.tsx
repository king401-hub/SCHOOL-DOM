import { useState, useEffect, useRef } from 'react';
import { Star, ChevronLeft, ChevronRight, Quote } from 'lucide-react';

const TESTIMONIALS = [
  {
    name: 'Mr. Adewale Ogundimu',
    role: 'Principal, Bright Future Academy, Lagos',
    avatar: 'AO',
    color: '#0ea5e9',
    stars: 5,
    text: "Schooldom completely transformed how we run our school. Fee collection used to take weeks of manual reconciliation. Now bursary staff settle everything in a day. The Paystack integration alone has been life-changing.",
  },
  {
    name: 'Mrs. Chidinma Eze',
    role: 'Director, Excellence Model School, Enugu',
    avatar: 'CE',
    color: '#10b981',
    stars: 5,
    text: "Our report card generation used to take three staff members an entire week. With Schooldom, we generate all 800 report cards in under 10 minutes with a single click. Parents are amazed at how professional they look.",
  },
  {
    name: 'Alhaji Musa Abdullahi',
    role: 'Proprietor, Crown Heights Academy, Abuja',
    avatar: 'MA',
    color: '#8b5cf6',
    stars: 5,
    text: "The offline CBT system is exactly what we needed. Our exam hall has poor internet and the old system kept failing during exams. Now exams run perfectly offline and sync when connectivity is restored. No more panicking.",
  },
  {
    name: 'Mrs. Folake Adeyemi',
    role: 'Admin Officer, Heritage International School, Ibadan',
    avatar: 'FA',
    color: '#f59e0b',
    stars: 5,
    text: "Parents now pay school fees from their phones at midnight if they want to. We get the alert instantly. The debt tracking means we never lose track of who owes what. Our outstanding balance dropped by 60% in one term.",
  },
  {
    name: 'Mr. Emmanuel Okeke',
    role: "ICT Coordinator, St. Andrew's Secondary, Port Harcourt",
    avatar: 'EO',
    color: '#ec4899',
    stars: 5,
    text: "The Win7 desktop CBT app is a god-send. Some of our student machines are old Dell systems that can't run modern browsers well. The desktop app handles 200 concurrent students without breaking a sweat.",
  },
];

function StarRating({ count }: { count: number }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: count }).map((_, i) => (
        <Star key={i} className="h-4 w-4 fill-amber-400 text-amber-400" />
      ))}
    </div>
  );
}

export default function Testimonials() {
  const [active, setActive] = useState(0);
  const [animating, setAnimating] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const go = (idx: number) => {
    if (animating) return;
    setAnimating(true);
    setTimeout(() => {
      setActive((idx + TESTIMONIALS.length) % TESTIMONIALS.length);
      setAnimating(false);
    }, 200);
  };

  useEffect(() => {
    intervalRef.current = setInterval(() => go(active + 1), 5000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [active]);

  const t = TESTIMONIALS[active];

  return (
    <section id="testimonials" className="py-28 px-4 relative">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <span
            className="text-xs font-bold uppercase tracking-widest px-4 py-1.5 rounded-full border mb-4 inline-block"
            style={{ color: '#10b981', background: 'rgba(16,185,129,0.08)', borderColor: 'rgba(16,185,129,0.2)' }}
          >
            What Schools Say
          </span>
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Trusted by schools{' '}
            <span style={{ background: 'linear-gradient(90deg, #10b981, #0ea5e9)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
              across Nigeria
            </span>
          </h2>
        </div>

        <div className="relative">
          <div
            className="rounded-3xl border border-white/5 p-8 sm:p-12 transition-all duration-200"
            style={{
              background: 'rgba(255,255,255,0.02)',
              opacity: animating ? 0 : 1,
              transform: animating ? 'translateY(8px)' : 'translateY(0)',
            }}
          >
            <Quote className="h-10 w-10 mb-6" style={{ color: t.color, opacity: 0.6 }} />
            <p className="text-white text-lg sm:text-xl leading-relaxed mb-8 font-light">
              "{t.text}"
            </p>
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div className="flex items-center gap-4">
                <div
                  className="h-12 w-12 rounded-2xl flex items-center justify-center text-white font-bold text-sm shrink-0"
                  style={{ background: `linear-gradient(135deg, ${t.color}80, ${t.color}40)`, border: `1px solid ${t.color}30` }}
                >
                  {t.avatar}
                </div>
                <div>
                  <p className="text-white font-semibold">{t.name}</p>
                  <p className="text-slate-500 text-sm">{t.role}</p>
                </div>
              </div>
              <StarRating count={t.stars} />
            </div>
          </div>

          <div className="flex items-center justify-between mt-8">
            <div className="flex gap-2">
              {TESTIMONIALS.map((_, i) => (
                <button
                  key={i}
                  onClick={() => go(i)}
                  className="rounded-full transition-all duration-300 cursor-pointer"
                  style={{
                    width: active === i ? '24px' : '8px',
                    height: '8px',
                    background: active === i ? '#0ea5e9' : 'rgba(255,255,255,0.15)',
                  }}
                />
              ))}
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => go(active - 1)}
                className="h-10 w-10 rounded-xl flex items-center justify-center border border-white/10 text-slate-400 hover:text-white hover:border-white/20 hover:bg-white/5 transition-all cursor-pointer"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                onClick={() => go(active + 1)}
                className="h-10 w-10 rounded-xl flex items-center justify-center border border-white/10 text-slate-400 hover:text-white hover:border-white/20 hover:bg-white/5 transition-all cursor-pointer"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 sm:grid-cols-5 gap-4 mt-16">
          {TESTIMONIALS.map((item, i) => (
            <button
              key={i}
              onClick={() => go(i)}
              className="flex flex-col items-center gap-2 p-3 rounded-xl border transition-all cursor-pointer"
              style={{
                border: active === i ? `1px solid ${item.color}40` : '1px solid rgba(255,255,255,0.05)',
                background: active === i ? `${item.color}08` : 'transparent',
              }}
            >
              <div
                className="h-8 w-8 rounded-lg flex items-center justify-center text-white text-xs font-bold"
                style={{ background: `${item.color}30` }}
              >
                {item.avatar}
              </div>
              <span className="text-[10px] text-slate-500 text-center leading-tight hidden sm:block">{item.name.split(' ')[0]}</span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
