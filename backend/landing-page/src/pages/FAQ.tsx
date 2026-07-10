import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ChevronDown, Search, ArrowLeft } from 'lucide-react';

const CAT_KEYS: Record<string, string> = {
  pricing: 'Pricing',
  cbt: 'CBT & Exams',
  finance: 'Finance & Fees',
  setup: 'Setup & Support',
  security: 'Security & Compliance',
};

const FAQS = [
  {
    category: 'Pricing',
    color: '#22c55e',
    items: [
      { q: 'How much does Schooldom cost?', a: 'K-12 schools pay ₦500 per term (3 months 15 days). Non-K12 institutions pay ₦200 per month. Both plans are flat rates — no per-student charges, no hidden fees.' },
      { q: 'What is the Child Monitor add-on?', a: 'Child Monitor is an optional add-on for K-12 schools at ₦1,000 per term. It provides real-time location tracking, screen activity monitoring, and safety alerts for students.' },
      { q: 'Is there a free trial?', a: 'Yes! New schools get a 30-day free trial with full access to all features. No credit card required to start.' },
      { q: 'Are there setup fees or per-student charges?', a: 'No. Our pricing is completely flat. You pay one rate for the entire school regardless of how many students or staff members you add.' },
    ]
  },
  {
    category: 'CBT & Exams',
    color: '#0ea5e9',
    items: [
      { q: 'Can students take exams without internet?', a: 'Yes. Our Desktop CBT app is 100% offline-capable. Students take exams on local machines; results automatically sync to the cloud when internet is restored.' },
      { q: 'What Windows versions does the desktop CBT app support?', a: 'The Schooldom Desktop CBT app works on Windows 7, 8, 10, and 11. No upgrade required — we designed it specifically for schools with older hardware.' },
      { q: 'How does anti-cheat work?', a: 'The CBT app locks the computer into exam mode — preventing tab switching, copy-paste, screenshots, and external applications. All session activity is logged.' },
      { q: 'Can I upload past questions as a question bank?', a: 'Yes. You can import questions via Excel/CSV or type them directly. Questions support images, equations, and multiple choice or theory formats.' },
    ]
  },
  {
    category: 'Finance & Fees',
    color: '#8b5cf6',
    items: [
      { q: 'How do parents pay school fees?', a: "Parents can pay via Paystack (card/bank transfer/USSD), direct bank transfer with automated reconciliation, or in-person cash (recorded by the bursary). All payments generate instant digital receipts sent via SMS." },
      { q: 'Can Schooldom send invoice SMS to parents?', a: 'Yes. When a new term begins or a payment is due, Schooldom automatically sends invoice SMS messages to parents with payment links.' },
      { q: 'What happens to unpaid fees?', a: 'The system tracks outstanding balances per student, generates aging reports, and can automatically restrict portal access for students with unpaid fees — configurable by the school.' },
      { q: 'Does Schooldom support multi-term or full-year invoicing?', a: "Yes. You can create invoices for individual terms, the full academic year, or any custom period. Split-payment installments are also supported." },
    ]
  },
  {
    category: 'Setup & Support',
    color: '#f59e0b',
    items: [
      { q: 'How long does it take to set up?', a: 'Most schools are fully operational within 4 minutes of registering. Our onboarding wizard guides you through school setup, and your dashboard is live immediately.' },
      { q: 'Do you offer training for staff?', a: 'Yes. Every new school gets a complimentary onboarding session. We also provide video tutorials, documentation, and a dedicated support channel.' },
      { q: 'Can I migrate data from another school management system?', a: "Yes. We have import tools for student records, fee history, and exam data from Excel, CSV, and common formats. Our team can also assist with custom migrations." },
      { q: 'What support channels are available?', a: 'Email, WhatsApp, and phone support during business hours. K-12 plans include priority support with faster response times.' },
    ]
  },
  {
    category: 'Security & Compliance',
    color: '#10b981',
    items: [
      { q: 'Is Schooldom NDPA compliant?', a: 'Yes. All student data is processed in compliance with the Nigeria Data Protection Act (NDPA). We maintain data processing agreements with all schools and conduct regular audits.' },
      { q: 'Where is my school data stored?', a: 'Your data is stored on AWS infrastructure in the West Africa region, ensuring low latency and compliance with Nigerian data residency requirements.' },
      { q: 'Can I export or delete my data?', a: 'Yes. You can export all school data at any time in standard formats (CSV, PDF, JSON). Data deletion requests are processed within 30 days of school termination.' },
    ]
  },
];

function AccordionItem({ q, a, color }: { q: string; a: string; color: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-white/5 last:border-0">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between py-4 text-left cursor-pointer gap-4"
      >
        <span className="text-white text-sm font-medium leading-relaxed">{q}</span>
        <ChevronDown
          className="h-4 w-4 shrink-0 transition-transform duration-200"
          style={{ color, transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}
        />
      </button>
      <div className="overflow-hidden transition-all duration-300" style={{ maxHeight: open ? 400 : 0 }}>
        <p className="text-slate-400 text-sm leading-relaxed pb-5">{a}</p>
      </div>
    </div>
  );
}

export default function FAQPage() {
  const [searchParams] = useSearchParams();
  const initialCat = CAT_KEYS[searchParams.get('cat') ?? ''] ?? 'All';
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState(initialCat);

  const filtered = FAQS.map(cat => ({
    ...cat,
    items: cat.items.filter(item =>
      !search || item.q.toLowerCase().includes(search.toLowerCase()) || item.a.toLowerCase().includes(search.toLowerCase())
    )
  })).filter(cat => (activeCategory === 'All' || cat.category === activeCategory) && cat.items.length > 0);

  return (
    <div className="min-h-screen pt-24 pb-20 px-4 relative">
      <div className="absolute top-0 inset-x-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(34,197,94,0.05) 0%, transparent 50%)' }} />

      <div className="max-w-3xl mx-auto">
        {/* Back */}
        <a href="/" className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-300 text-sm mb-8 transition-colors">
          <ArrowLeft className="h-4 w-4" /> Back to home
        </a>

        {/* Header */}
        <div className="text-center mb-12">
          <span className="badge badge-green mb-4">FAQ</span>
          <h1 className="font-display font-black text-4xl sm:text-5xl text-white mb-4">
            Frequently asked <span className="gradient-text">questions</span>
          </h1>
          <p className="text-slate-400">Everything you need to know about Schooldom. Can't find an answer? <a href="/#/contact" className="text-green-400 hover:underline">Contact us.</a></p>
        </div>

        {/* Search */}
        <div className="relative mb-6">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search questions..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-11 pr-4 py-3.5 rounded-2xl text-sm sd-input placeholder-slate-600"
          />
        </div>

        {/* Category filters */}
        <div className="flex flex-wrap gap-2 mb-10">
          {['All', ...FAQS.map(c => c.category)].map(cat => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className="px-4 py-2 rounded-xl text-sm font-medium transition-all cursor-pointer sd-card-2"
              style={{
                background: activeCategory === cat ? 'rgba(34,197,94,0.1)' : undefined,
                borderColor: activeCategory === cat ? 'rgba(34,197,94,0.3)' : undefined,
                color: activeCategory === cat ? '#22c55e' : undefined,
              }}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* FAQ sections */}
        <div className="space-y-8">
          {filtered.map(cat => (
            <div key={cat.category} className="rounded-2xl p-6 sd-card">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-2 h-2 rounded-full" style={{ background: cat.color }} />
                <h2 className="font-bold text-sm" style={{ color: cat.color }}>{cat.category}</h2>
              </div>
              {cat.items.map(item => <AccordionItem key={item.q} q={item.q} a={item.a} color={cat.color} />)}
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="text-center py-16">
              <p className="text-slate-500">No questions match your search. <a href="/#/contact" className="text-green-400 hover:underline">Ask us directly.</a></p>
            </div>
          )}
        </div>

        {/* Still have questions */}
        <div className="mt-14 rounded-2xl p-8 text-center"
          style={{ background: 'linear-gradient(135deg, rgba(34,197,94,0.07), rgba(14,165,233,0.07))', border: '1px solid rgba(34,197,94,0.15)' }}>
          <h3 className="font-display font-black text-white text-xl mb-2">Still have questions?</h3>
          <p className="text-slate-400 text-sm mb-5">Our team responds within 2 hours during business hours.</p>
          <a href="/#/contact" className="btn-primary inline-flex">
            Contact Support <ArrowLeft className="h-4 w-4 rotate-180" />
          </a>
        </div>
      </div>
    </div>
  );
}
