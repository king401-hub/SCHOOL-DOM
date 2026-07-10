import { useState } from 'react';
import { Mail, Phone, MapPin, Send, CheckCircle, ArrowLeft, Clock, MessageSquare } from 'lucide-react';

export default function ContactPage() {
  const [form, setForm] = useState({ name: '', email: '', phone: '', school: '', message: '' });
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setTimeout(() => { setSubmitting(false); setSubmitted(true); }, 1800);
  };

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  const inputStyle = {
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: '0.875rem',
    color: '#f8fafc',
  };

  return (
    <div className="min-h-screen pt-24 pb-20 px-4 relative">
      <div className="absolute top-0 inset-x-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(14,165,233,0.05) 0%, transparent 50%)' }} />

      <div className="max-w-5xl mx-auto">
        <a href="/" className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-300 text-sm mb-8 transition-colors">
          <ArrowLeft className="h-4 w-4" /> Back to home
        </a>

        <div className="text-center mb-12">
          <span className="badge badge-blue mb-4">Contact Us</span>
          <h1 className="font-display font-black text-4xl sm:text-5xl text-white mb-4">
            Let's <span className="gradient-text-reverse">talk</span>
          </h1>
          <p className="text-slate-400 max-w-xl mx-auto">Have questions? Want a demo? Ready to onboard? We'd love to hear from you.</p>
        </div>

        <div className="grid lg:grid-cols-5 gap-10">
          {/* Left: Contact info */}
          <div className="lg:col-span-2 space-y-5">
            {[
              { icon: Mail, label: 'Email', value: 'solomonomotayo96@gmail.com', href: 'mailto:solomonomotayo96@gmail.com', color: '#22c55e' },
              { icon: Phone, label: 'Phone', value: '+234 800 000 0000', href: 'tel:+2348000000000', color: '#0ea5e9' },
              { icon: MapPin, label: 'Location', value: 'Lagos, Nigeria', href: '#', color: '#8b5cf6' },
              { icon: Clock, label: 'Support Hours', value: 'Mon–Fri, 8am–6pm WAT', href: '#', color: '#f59e0b' },
              { icon: MessageSquare, label: 'WhatsApp', value: '+234 800 000 0000', href: 'https://wa.me/2348000000000', color: '#10b981' },
            ].map(c => {
              const Icon = c.icon;
              return (
                <a key={c.label} href={c.href}
                  className="flex items-center gap-4 p-4 rounded-2xl border border-white/5 hover:border-white/10 transition-all"
                  style={{ background: 'rgba(255,255,255,0.02)' }}>
                  <div className="h-10 w-10 rounded-xl flex items-center justify-center shrink-0"
                    style={{ background: `${c.color}12`, border: `1px solid ${c.color}25` }}>
                    <Icon className="h-4.5 w-4.5" style={{ color: c.color }} />
                  </div>
                  <div>
                    <p className="text-slate-500 text-[10px] uppercase tracking-wider">{c.label}</p>
                    <p className="text-white text-sm font-medium">{c.value}</p>
                  </div>
                </a>
              );
            })}

            <div className="rounded-2xl p-5 mt-4"
              style={{ background: 'linear-gradient(135deg, rgba(34,197,94,0.07), rgba(14,165,233,0.07))', border: '1px solid rgba(34,197,94,0.15)' }}>
              <p className="text-white text-sm font-semibold mb-1">Average response time</p>
              <p className="text-slate-400 text-xs">We respond to all inquiries within 2 hours during business hours (Mon–Fri, 8am–6pm WAT).</p>
              <div className="mt-3 flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                <span className="text-green-400 text-xs font-semibold">Support is online now</span>
              </div>
            </div>
          </div>

          {/* Right: Form */}
          <div className="lg:col-span-3">
            <div className="rounded-3xl p-8 border border-white/6" style={{ background: 'rgba(255,255,255,0.02)' }}>
              {submitted ? (
                <div className="py-12 text-center space-y-4">
                  <div className="h-16 w-16 rounded-full flex items-center justify-center mx-auto"
                    style={{ background: 'rgba(34,197,94,0.15)', border: '1px solid rgba(34,197,94,0.3)' }}>
                    <CheckCircle className="h-8 w-8" style={{ color: '#22c55e' }} />
                  </div>
                  <h3 className="font-display font-black text-white text-2xl">Message sent!</h3>
                  <p className="text-slate-400 text-sm max-w-xs mx-auto">
                    Thank you, {form.name.split(' ')[0]}. We'll get back to you at {form.email} within 2 hours.
                  </p>
                  <button
                    onClick={() => { setForm({ name: '', email: '', phone: '', school: '', message: '' }); setSubmitted(false); }}
                    className="btn-ghost text-sm mt-4"
                  >
                    Send another message
                  </button>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-5">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-slate-500 text-xs mb-1.5">Full Name *</label>
                      <input required type="text" value={form.name} onChange={set('name')}
                        placeholder="Mrs. Adunola Okafor"
                        className="w-full px-4 py-3 text-sm placeholder-slate-600"
                        style={inputStyle} />
                    </div>
                    <div>
                      <label className="block text-slate-500 text-xs mb-1.5">Email Address *</label>
                      <input required type="email" value={form.email} onChange={set('email')}
                        placeholder="principal@school.com"
                        className="w-full px-4 py-3 text-sm placeholder-slate-600"
                        style={inputStyle} />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-slate-500 text-xs mb-1.5">Phone Number</label>
                      <input type="tel" value={form.phone} onChange={set('phone')}
                        placeholder="+234 80x xxx xxxx"
                        className="w-full px-4 py-3 text-sm placeholder-slate-600"
                        style={inputStyle} />
                    </div>
                    <div>
                      <label className="block text-slate-500 text-xs mb-1.5">School Name</label>
                      <input type="text" value={form.school} onChange={set('school')}
                        placeholder="Royal Heights Academy"
                        className="w-full px-4 py-3 text-sm placeholder-slate-600"
                        style={inputStyle} />
                    </div>
                  </div>
                  <div>
                    <label className="block text-slate-500 text-xs mb-1.5">How can we help? *</label>
                    <textarea required value={form.message} onChange={set('message')}
                      placeholder="Tell us about your school and what you're looking for..."
                      rows={5}
                      className="w-full px-4 py-3 text-sm placeholder-slate-600 resize-none"
                      style={inputStyle} />
                  </div>
                  <button type="submit" disabled={submitting} className="w-full btn-primary justify-center py-4 text-base">
                    {submitting ? (
                      <span className="flex items-center gap-2">
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Sending...
                      </span>
                    ) : (
                      <span className="flex items-center gap-2">
                        Send Message <Send className="h-4 w-4" />
                      </span>
                    )}
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
