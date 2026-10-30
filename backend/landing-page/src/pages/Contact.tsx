import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Mail, Phone, MapPin, Send, CheckCircle, ArrowLeft, Clock, MessageSquare } from 'lucide-react';
import Spinner from '../components/Spinner';
import { usePageMeta } from '../lib/usePageMeta';

export default function ContactPage() {
  const { t } = useTranslation();
  usePageMeta(`${t('contact.title')} ${t('contact.titleHighlight')}`, t('contact.subtitle'), '/contact');
  const [form, setForm] = useState({ name: '', email: '', phone: '', school: '', message: '' });
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const notProvided = t('contact.form.notProvided');
      const res = await fetch('/api/auth/contact/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name,
          email: form.email,
          message: `${form.message}\n\n—\nPhone: ${form.phone || notProvided}\nSchool: ${form.school || notProvided}`,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.success === false) {
        throw new Error(data.message || t('contact.form.genericError'));
      }
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('contact.form.genericErrorFallback'));
    } finally {
      setSubmitting(false);
    }
  };

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  const inputCls = 'w-full px-4 py-3 text-sm rounded-xl sd-input';

  return (
    <div className="min-h-screen pt-24 pb-20 px-4 relative">
      <div className="absolute top-0 inset-x-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(var(--c-green-rgb),0.06) 0%, transparent 50%)' }} />

      <div className="max-w-5xl mx-auto">
        <a href="/" className="inline-flex items-center gap-2 text-[var(--c-muted)] hover:text-[var(--c-ink)] text-sm mb-8 transition-colors">
          <ArrowLeft className="h-4 w-4" /> {t('common.backToHome')}
        </a>

        <div className="text-center mb-12">
          <span className="badge badge-blue mb-4">{t('contact.badge')}</span>
          <h1 className="font-display font-bold text-4xl sm:text-5xl text-[var(--c-ink)] mb-4 tracking-tight">
            {t('contact.title')} <span className="gradient-text-reverse">{t('contact.titleHighlight')}</span>
          </h1>
          <p className="text-[var(--c-muted)] max-w-xl mx-auto">{t('contact.subtitle')}</p>
        </div>

        <div className="grid lg:grid-cols-5 gap-10">
          {/* Left: Contact info */}
          <div className="lg:col-span-2 space-y-5">
            {[
              { icon: Mail, label: t('contact.info.email'), value: 'support@schooldom.academy', href: 'mailto:support@schooldom.academy', color: 'var(--c-green)' },
              { icon: Phone, label: t('contact.info.phone'), value: '+234 907 682 1365', href: 'tel:+2349076821365', color: 'var(--c-green)' },
              { icon: MapPin, label: t('contact.info.location'), value: t('contact.info.locationValue'), href: '#', color: 'var(--c-green)' },
              { icon: Clock, label: t('contact.info.supportHours'), value: t('contact.info.supportHoursValue'), href: '#', color: 'var(--c-green)' },
              { icon: MessageSquare, label: t('contact.info.whatsapp'), value: '+234 907 682 1365', href: 'https://wa.me/2349076821365', color: 'var(--c-green)' },
            ].map(c => {
              const Icon = c.icon;
              return (
                <a key={c.label} href={c.href}
                  className="flex items-center gap-4 p-4 rounded-2xl hover:border-[var(--c-green)]/25 transition-all sd-card">
                  <div className="h-10 w-10 rounded-xl flex items-center justify-center shrink-0"
                    style={{ background: `${c.color}10`, border: `1px solid ${c.color}22` }}>
                    <Icon className="h-4.5 w-4.5" style={{ color: c.color }} />
                  </div>
                  <div>
                    <p className="text-[var(--c-subtle)] text-[10px] uppercase tracking-wider">{c.label}</p>
                    <p className="text-[var(--c-ink)] text-sm font-medium">{c.value}</p>
                  </div>
                </a>
              );
            })}

            <div className="rounded-2xl p-5 mt-4"
              style={{ background: 'rgba(var(--c-green-rgb),0.06)', border: '1px solid rgba(var(--c-green-rgb),0.16)' }}>
              <p className="text-[var(--c-ink)] text-sm font-semibold mb-1">{t('contact.avgResponseTitle')}</p>
              <p className="text-[var(--c-muted)] text-xs">{t('contact.avgResponseDesc')}</p>
              <div className="mt-3 flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                <span className="text-green-400 text-xs font-semibold">{t('contact.supportOnline')}</span>
              </div>
            </div>
          </div>

          {/* Right: Form */}
          <div className="lg:col-span-3">
            <div className="rounded-3xl p-8 sd-card">
              {submitted ? (
                <div className="py-12 text-center space-y-4">
                  <div className="h-16 w-16 rounded-full flex items-center justify-center mx-auto"
                    style={{ background: 'rgba(var(--c-green-rgb),0.12)', border: '1px solid rgba(var(--c-green-rgb),0.3)' }}>
                    <CheckCircle className="h-8 w-8" style={{ color: 'var(--c-green)' }} />
                  </div>
                  <h3 className="font-display font-black text-[var(--c-ink)] text-2xl">{t('contact.success.title')}</h3>
                  <p className="text-[var(--c-muted)] text-sm max-w-xs mx-auto">
                    {t('contact.success.desc', { name: form.name.split(' ')[0], email: form.email })}
                  </p>
                  <button
                    onClick={() => { setForm({ name: '', email: '', phone: '', school: '', message: '' }); setSubmitted(false); }}
                    className="btn-ghost text-sm mt-4"
                  >
                    {t('contact.success.another')}
                  </button>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-5">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="contact-name" className="block text-[var(--c-subtle)] text-xs mb-1.5">{t('contact.form.fullName')}</label>
                      <input id="contact-name" required type="text" value={form.name} onChange={set('name')}
                        placeholder={t('contact.form.fullNamePlaceholder')}
                        className={inputCls} />
                    </div>
                    <div>
                      <label htmlFor="contact-email" className="block text-[var(--c-subtle)] text-xs mb-1.5">{t('contact.form.email')}</label>
                      <input id="contact-email" required type="email" value={form.email} onChange={set('email')}
                        placeholder={t('contact.form.emailPlaceholder')}
                        className={inputCls} />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="contact-phone" className="block text-[var(--c-subtle)] text-xs mb-1.5">{t('contact.form.phone')}</label>
                      <input id="contact-phone" type="tel" value={form.phone} onChange={set('phone')}
                        placeholder={t('contact.form.phonePlaceholder')}
                        className={inputCls} />
                    </div>
                    <div>
                      <label htmlFor="contact-school" className="block text-[var(--c-subtle)] text-xs mb-1.5">{t('contact.form.school')}</label>
                      <input id="contact-school" type="text" value={form.school} onChange={set('school')}
                        placeholder={t('contact.form.schoolPlaceholder')}
                        className={inputCls} />
                    </div>
                  </div>
                  <div>
                    <label htmlFor="contact-message" className="block text-[var(--c-subtle)] text-xs mb-1.5">{t('contact.form.message')}</label>
                    <textarea id="contact-message" required value={form.message} onChange={set('message')}
                      placeholder={t('contact.form.messagePlaceholder')}
                      rows={5}
                      className={`${inputCls} resize-none`} />
                  </div>
                  {error && (
                    <div className="p-3.5 rounded-xl text-sm"
                      style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)', color: '#f87171' }}>
                      {error}
                    </div>
                  )}
                  <button type="submit" disabled={submitting} className="w-full btn-primary justify-center py-4 text-base">
                    {submitting ? (
                      <span className="flex items-center gap-2">
                        <Spinner /> {t('contact.form.sending')}
                      </span>
                    ) : (
                      <span className="flex items-center gap-2">
                        {t('contact.form.send')} <Send className="h-4 w-4" />
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
