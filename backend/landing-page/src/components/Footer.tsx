import { Mail, Phone, MapPin, Twitter, Youtube, Facebook } from 'lucide-react';

const LINKS = {
  Product: ['Features', 'Pricing', 'CBT Engine', 'Finance Ledger', 'Parent Portal'],
  Company: ['About Us', 'Contact', 'Privacy Policy', 'Terms of Service'],
  Support: ['Documentation', 'API Reference', 'Status Page', 'Help Center'],
};

export default function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="relative border-t border-white/5 pt-20 pb-8 px-4">
      <div
        className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[1px]"
        style={{ background: 'linear-gradient(90deg, transparent, rgba(14,165,233,0.5), transparent)' }}
      />

      <div className="max-w-7xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-10 mb-14">
          <div className="lg:col-span-2">
            <div className="flex items-center gap-3 mb-5">
              <div className="h-9 w-9 rounded-xl overflow-hidden border border-white/10">
                <img src="/schooldom-favicon.jpeg" alt="Schooldom" className="w-full h-full object-cover" />
              </div>
              <div>
                <span className="font-bold text-white text-lg tracking-tight">Schooldom</span>
                <span className="text-cyan-400 text-[10px] font-bold ml-1.5 bg-cyan-500/10 px-1.5 py-0.5 rounded border border-cyan-500/20">ACADEMY</span>
              </div>
            </div>
            <p className="text-slate-500 text-sm leading-relaxed max-w-xs mb-6">
              The complete school management platform built for African schools. From admission to graduation, fees to CBT — all in one place.
            </p>

            <div className="space-y-2.5">
              <a href="mailto:solomonomotayo96@gmail.com" className="flex items-center gap-2.5 text-slate-500 hover:text-slate-300 text-sm transition-colors">
                <Mail className="h-4 w-4 shrink-0" />
                solomonomotayo96@gmail.com
              </a>
              <div className="flex items-center gap-2.5 text-slate-500 text-sm">
                <MapPin className="h-4 w-4 shrink-0" />
                Lagos, Nigeria
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              {[Twitter, Youtube, Facebook].map((Icon, i) => (
                <button
                  key={i}
                  className="h-9 w-9 rounded-xl border border-white/5 flex items-center justify-center text-slate-500 hover:text-white hover:border-white/15 hover:bg-white/5 transition-all cursor-pointer"
                >
                  <Icon className="h-4 w-4" />
                </button>
              ))}
            </div>
          </div>

          {Object.entries(LINKS).map(([heading, items]) => (
            <div key={heading}>
              <h4 className="text-white font-semibold text-sm mb-4">{heading}</h4>
              <ul className="space-y-2.5">
                {items.map(item => (
                  <li key={item}>
                    <a href="#" className="text-slate-500 hover:text-slate-300 text-sm transition-colors">
                      {item}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="border-t border-white/5 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-slate-600 text-xs">
            © {year} Schooldom Academy. All rights reserved.
          </p>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-slate-600 text-xs">All systems operational</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
