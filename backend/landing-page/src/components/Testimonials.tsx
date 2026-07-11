import { useRef, useState, useEffect } from 'react';
import { Star, Quote } from 'lucide-react';

const TESTIMONIALS = [
  { name: 'Mr. Adewale Ogundimu', role: 'Principal, Greenfield Academy, Ibadan', quote: "Schooldom transformed how we run exams. Our CBT pass rate jumped from 71% to 89% in one term because we eliminated paper leakages. The offline mode is a lifesaver during NEPA outages.", school: 'K-12 School', students: '1,240 students', initials: 'AO', color: '#22c55e' },
  { name: 'Mrs. Chidinma Eze', role: 'Bursar, Royal Heights Group of Schools, Enugu', quote: "Before Schooldom, collecting fees was a nightmare — parents came with handwritten receipts and we could never reconcile. Now we track every kobo, and parents pay via bank transfer directly.", school: 'Group of 4 Schools', students: '3,800 students', initials: 'CE', color: '#0ea5e9' },
  { name: 'Mr. Ibrahim Al-Hassan', role: "ICT Coordinator, Al-Noor International Academy, Kano", quote: "The offline CBT app is exactly what we needed. We have 12 Windows 7 machines and Schooldom works perfectly. Students get results instantly after submission.", school: 'Islamic Secondary', students: '680 students', initials: 'IH', color: '#8b5cf6' },
  { name: 'Mrs. Funmilayo Adesanya', role: 'Head Mistress, Sunrise Nursery & Primary, Lagos', quote: "The Child Monitor feature gives our parents peace of mind. They see when children arrive safely. Attendance SMS alerts have reduced late pickups by 60%.", school: 'K-12 School', students: '420 students', initials: 'FA', color: '#f59e0b' },
  { name: 'Dr. Emeka Okonkwo', role: 'Registrar, Covenant Vocational College, Owerri', quote: "As a non-K12 institution, we needed flexible management. Schooldom's Non-K12 plan at ₦200/month is extraordinary value. We manage 600 diploma students with full academic records.", school: 'Vocational College', students: '600 students', initials: 'EO', color: '#10b981' },
  { name: 'Mrs. Ngozi Okeke', role: 'Director, Prestige Group of Schools, Abuja', quote: "Managing 5 campuses used to require 3 finance officers. Now one bursar handles all collections centrally. Monthly reconciliation dropped from 3 days to 2 hours.", school: 'Group of 5 Schools', students: '2,100 students', initials: 'NO', color: '#ec4899' },
  { name: 'Mr. Tunde Adeyemi', role: "Vice Principal, Bishop's Crown Secondary, Abeokuta", quote: "Report card generation used to take 2 weeks every term. With Schooldom, it takes 30 minutes. It computes positions, fills remarks, and exports PDFs automatically.", school: 'Secondary School', students: '890 students', initials: 'TA', color: '#06b6d4' },
  { name: 'Mrs. Halima Yusuf', role: 'Proprietress, New Horizon International, Kaduna', quote: "The parent portal changed our school community. Parents see exam scores, attendance, and fee receipts on their phones without calling. Our parent satisfaction surveys are at an all-time high.", school: 'K-12 School', students: '560 students', initials: 'HY', color: '#a855f7' },
];

function TestimonialCard({ t }: { t: typeof TESTIMONIALS[0] }) {
  return (
    <div className="shrink-0 w-80 rounded-2xl p-6 mx-2 hover:border-white/10 transition-all sd-card">
      <div className="flex items-start justify-between mb-4">
        <div className="flex">{[...Array(5)].map((_, i) => <Star key={i} className="h-3.5 w-3.5 fill-yellow-400 text-yellow-400" />)}</div>
        <Quote className="h-5 w-5 opacity-15 text-white" />
      </div>
      <p className="text-slate-300 text-sm leading-relaxed mb-5">"{t.quote}"</p>
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-full flex items-center justify-center text-sm font-bold shrink-0"
          style={{ background: `${t.color}18`, border: `1px solid ${t.color}35`, color: t.color }}>{t.initials}</div>
        <div>
          <p className="text-white text-sm font-semibold">{t.name}</p>
          <p className="text-slate-500 text-[10px]">{t.role}</p>
        </div>
      </div>
      <div className="mt-4 flex gap-2 flex-wrap">
        <span className="text-[9px] px-2 py-1 rounded-full border" style={{ color: t.color, background: `${t.color}08`, borderColor: `${t.color}25` }}>{t.school}</span>
        <span className="text-[9px] px-2 py-1 rounded-full border border-white/8 text-slate-500">{t.students}</span>
      </div>
    </div>
  );
}

function useVisible(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setVisible(true); }, { threshold });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, visible };
}

export default function Testimonials() {
  const { ref, visible } = useVisible(0.1);
  const row1 = TESTIMONIALS.slice(0, 4);
  const row2 = TESTIMONIALS.slice(4);

  return (
    <section id="testimonials" ref={ref} className="py-28 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 100%, rgba(34,197,94,0.04) 0%, transparent 60%)' }} />

      <div className="mb-14 px-4"
        style={{ opacity: visible ? 1 : 0, transform: visible ? 'none' : 'translateY(24px)', transition: 'all 0.7s ease' }}>
        <div className="text-center max-w-3xl mx-auto">
          <span className="badge badge-green mb-4"><Star className="h-3 w-3 fill-current" /> Testimonials</span>
          <h2 className="font-display font-black text-4xl sm:text-5xl text-white mb-4">
            Schools love <span className="gradient-text">what we've built</span>
          </h2>
          <p className="text-slate-400">Real stories from real school administrators across Nigeria.</p>
        </div>
      </div>

      <div className="overflow-hidden mb-4"
        style={{ maskImage: 'linear-gradient(90deg, transparent, black 8%, black 92%, transparent)', opacity: visible ? 1 : 0, transition: 'opacity 0.7s ease 0.3s' }}>
        <div className="flex animate-marquee-left" style={{ width: 'max-content' }}>
          {[...row1, ...row1].map((t, i) => <TestimonialCard key={i} t={t} />)}
        </div>
      </div>

      <div className="overflow-hidden"
        style={{ maskImage: 'linear-gradient(90deg, transparent, black 8%, black 92%, transparent)', opacity: visible ? 1 : 0, transition: 'opacity 0.7s ease 0.5s' }}>
        <div className="flex animate-marquee-right" style={{ width: 'max-content' }}>
          {[...row2, ...row2].map((t, i) => <TestimonialCard key={i} t={t} />)}
        </div>
      </div>

      <div className="text-center mt-12 px-4"
        style={{ opacity: visible ? 1 : 0, transition: 'opacity 0.7s ease 0.7s' }}>
        <div className="inline-flex items-center gap-3 px-6 py-3 rounded-2xl sd-card">
          <div className="flex">{[...Array(5)].map((_, i) => <Star key={i} className="h-4 w-4 fill-yellow-400 text-yellow-400" />)}</div>
          <span className="text-white font-bold text-lg">4.9 / 5</span>
          <span className="text-slate-500 text-sm">from 300+ school reviews</span>
        </div>
      </div>
    </section>
  );
}
