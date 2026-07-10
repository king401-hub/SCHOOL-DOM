import { useState, useEffect, useRef } from 'react';
import { Menu, X, ChevronRight } from 'lucide-react';

interface NavbarProps {
  onSignIn: () => void;
  onSignUp: () => void;
}

function MagneticButton({ children, className, onClick }: { children: React.ReactNode; className?: string; onClick?: () => void }) {
  const ref = useRef<HTMLButtonElement>(null);
  const handleMove = (e: React.MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = (e.clientX - rect.left - rect.width / 2) * 0.3;
    const y = (e.clientY - rect.top - rect.height / 2) * 0.3;
    el.style.transform = `translate(${x}px, ${y}px)`;
  };
  const handleLeave = () => {
    if (ref.current) ref.current.style.transform = '';
  };
  return (
    <button
      ref={ref}
      className={className}
      onClick={onClick}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
      style={{ transition: 'transform 0.2s cubic-bezier(0.23,1,0.32,1)' }}
    >
      {children}
    </button>
  );
}

export default function Navbar({ onSignIn, onSignUp }: NavbarProps) {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
    setMenuOpen(false);
  };

  return (
    <nav
      className="fixed top-0 left-0 right-0 z-50 transition-all duration-500"
      style={{
        background: scrolled ? 'rgba(2,8,23,0.85)' : 'transparent',
        backdropFilter: scrolled ? 'blur(20px)' : 'none',
        borderBottom: scrolled ? '1px solid rgba(255,255,255,0.06)' : 'none',
        padding: scrolled ? '12px 0' : '20px 0',
      }}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
          <div className="h-9 w-9 rounded-xl overflow-hidden border border-white/10 shadow-lg shadow-cyan-500/10">
            <img src="/schooldom-favicon.jpeg" alt="Schooldom" className="w-full h-full object-cover" />
          </div>
          <div>
            <span className="font-bold text-white text-lg tracking-tight">Schooldom</span>
            <span className="text-cyan-400 text-[10px] font-bold ml-1.5 bg-cyan-500/10 px-1.5 py-0.5 rounded border border-cyan-500/20">ACADEMY</span>
          </div>
        </div>

        <div className="hidden md:flex items-center gap-8">
          {['features', 'demo', 'pricing', 'testimonials'].map(id => (
            <button
              key={id}
              onClick={() => scrollTo(id)}
              className="text-sm text-slate-400 hover:text-white transition-colors capitalize cursor-pointer"
            >
              {id === 'demo' ? 'Live Demo' : id.charAt(0).toUpperCase() + id.slice(1)}
            </button>
          ))}
        </div>

        <div className="hidden md:flex items-center gap-3">
          <MagneticButton
            onClick={onSignIn}
            className="text-sm font-medium text-slate-300 hover:text-white px-4 py-2 rounded-xl hover:bg-white/5 transition-all border border-transparent hover:border-white/10 cursor-pointer"
          >
            Sign In
          </MagneticButton>
          <MagneticButton
            onClick={onSignUp}
            className="text-sm font-semibold text-white px-5 py-2 rounded-xl cursor-pointer relative overflow-hidden group"
            style={{ background: 'linear-gradient(135deg, #0ea5e9, #6366f1)' }}
          >
            <span className="relative z-10 flex items-center gap-1.5">Get Started <ChevronRight className="h-3.5 w-3.5" /></span>
            <div className="absolute inset-0 bg-white/20 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-500 skew-x-12" />
          </MagneticButton>
        </div>

        <button className="md:hidden text-slate-300 hover:text-white" onClick={() => setMenuOpen(!menuOpen)}>
          {menuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </div>

      {menuOpen && (
        <div className="md:hidden border-t border-white/5 bg-[#020817]/95 backdrop-blur-xl px-4 py-4 flex flex-col gap-3">
          {['features', 'demo', 'pricing', 'testimonials'].map(id => (
            <button key={id} onClick={() => scrollTo(id)} className="text-left py-2 text-slate-300 capitalize cursor-pointer hover:text-white">
              {id === 'demo' ? 'Live Demo' : id.charAt(0).toUpperCase() + id.slice(1)}
            </button>
          ))}
          <div className="flex gap-2 pt-2 border-t border-white/5">
            <button onClick={onSignIn} className="flex-1 py-2.5 text-sm font-medium text-white border border-white/10 rounded-xl hover:bg-white/5 cursor-pointer">Sign In</button>
            <button onClick={onSignUp} className="flex-1 py-2.5 text-sm font-semibold text-white rounded-xl cursor-pointer" style={{ background: 'linear-gradient(135deg, #0ea5e9, #6366f1)' }}>Get Started</button>
          </div>
        </div>
      )}
    </nav>
  );
}
