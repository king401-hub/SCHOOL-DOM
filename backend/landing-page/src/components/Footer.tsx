import { Mail, MapPin, Twitter, Youtube, Facebook, ArrowRight, Phone } from 'lucide-react';

const LINKS = {
  Product: ['Features', 'CBT Engine', 'Finance Ledger', 'Parent Portal', 'Kid Monitor'],
  Company: ['About Us', 'Blog', 'Careers', 'Privacy Policy', 'Terms of Service'],
  Support: ['Documentation', 'Help Center', 'Status Page', 'Contact Us', 'API Reference'],
};

interface FooterProps {
  onGetStarted: () => void;
}

export default function Footer({ onGetStarted }: FooterProps) {
  const year = new Date().getFullYear();

  return (
    <footer className="relative border-t border-white/5 pt-20 pb-8 px-4">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[1px]"
        style={{ background: 'linear-gradient(90deg, transparent, rgba(34,197,94,0.4), rgba(14,165,233,0.4), transparent)' }} />
      <div className="absolute top-0 inset-x-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(34,197,94,0.03) 0%, transparent 50%)' }} />

      <div className="max-w-7xl mx-auto">
        {/* Main grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-10 mb-14">
          {/* Brand col */}
          <div className="lg:col-span-2">
            <div className="flex items-center gap-3 mb-5">
              <div className="h-10 w-10 rounded-xl overflow-hidden border border-white/10"
                style={{ boxShadow: '0 0 16px rgba(34,197,94,0.15)' }}>
                <img src="/schooldom-favicon.jpeg" alt="Schooldom" className="w-full h-full object-cover" />
              </div>
              <div>
                <span className="font-display font-black text-white text-xl tracking-tight">Schooldom</span>
                <span className="text-[9px] font-bold ml-2 px-1.5 py-0.5 rounded border" style={{ color: '#22c55e', background: 'rgba(34,197,94,0.08)', borderColor: 'rgba(34,197,94,0.2)' }}>ACADEMY</span>
              </div>
            </div>
            <p className="text-slate-500 text-sm leading-relaxed max-w-xs mb-6">
              The complete school management platform built for African educational institutions. From admission to graduation, fees to CBT.
            </p>

            <div className="space-y-2.5 mb-6">
              <a href="mailto:solomonomotayo96@gmail.com" className="flex items-center gap-2.5 text-slate-500 hover:text-slate-300 text-sm transition-colors">
                <Mail className="h-4 w-4 shrink-0" style={{ color: '#22c55e' }} />
                solomonomotayo96@gmail.com
              </a>
              <a href="tel:+2348000000000" className="flex items-center gap-2.5 text-slate-500 hover:text-slate-300 text-sm transition-colors">
                <Phone className="h-4 w-4 shrink-0" style={{ color: '#0ea5e9' }} />
                +234 800 000 0000
              </a>
              <div className="flex items-center gap-2.5 text-slate-500 text-sm">
                <MapPin className="h-4 w-4 shrink-0" style={{ color: '#8b5cf6' }} />
                Lagos, Nigeria
              </div>
            </div>

            <div className="flex gap-3">
              {[Twitter, Youtube, Facebook].map((Icon, i) => (
                <button key={i}
                  className="h-9 w-9 rounded-xl border border-white/6 flex items-center justify-center text-slate-500 hover:text-white hover:border-white/15 hover:bg-white/5 transition-all cursor-pointer">
                  <Icon className="h-4 w-4" />
                </button>
              ))}
            </div>
          </div>

          {/* Link cols */}
          {Object.entries(LINKS).map(([heading, items]) => (
            <div key={heading}>
              <h4 className="text-white font-bold text-sm mb-4">{heading}</h4>
              <ul className="space-y-2.5">
                {items.map(item => {
                  const href = item === 'Contact Us' ? '/#/contact' : '#';
                  return (
                    <li key={item}>
                      <a href={href} className="text-slate-500 hover:text-slate-300 text-sm transition-colors">
                        {item}
                      </a>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>

        {/* CTA block */}
        <div className="rounded-3xl p-10 mb-10 text-center relative overflow-hidden"
          style={{ background: 'linear-gradient(135deg, rgba(34,197,94,0.08), rgba(14,165,233,0.08))', border: '1px solid rgba(34,197,94,0.15)' }}>
          <div className="absolute inset-0 pointer-events-none"
            style={{ background: 'radial-gradient(ellipse at 50% 100%, rgba(34,197,94,0.06) 0%, transparent 60%)' }} />
          <div className="relative">
            <h3 className="font-display font-black text-white text-2xl sm:text-3xl mb-3">
              Ready to digitize your school?
            </h3>
            <p className="text-slate-400 text-sm mb-6">Join 300+ Nigerian schools running on Schooldom. Set up in under 4 minutes.</p>
            <button onClick={onGetStarted} className="btn-primary text-base px-8 py-4">
              Onboard Your School <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="border-t border-white/5 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-slate-600 text-xs">
            © {year} Schooldom Academy. All rights reserved. Built with love for African schools.
          </p>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-slate-600 text-xs">All systems operational</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
