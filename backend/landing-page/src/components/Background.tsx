import { useEffect, useRef } from 'react';

export function AuroraBackground() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
      <div className="absolute inset-0 bg-[#020817]" />
      <div
        className="absolute -top-40 -left-40 w-[700px] h-[700px] rounded-full opacity-30"
        style={{
          background: 'radial-gradient(circle, #0ea5e9 0%, #6366f1 50%, transparent 70%)',
          animation: 'aurora1 12s ease-in-out infinite',
          filter: 'blur(60px)',
        }}
      />
      <div
        className="absolute top-1/3 -right-40 w-[600px] h-[600px] rounded-full opacity-25"
        style={{
          background: 'radial-gradient(circle, #10b981 0%, #0ea5e9 50%, transparent 70%)',
          animation: 'aurora2 15s ease-in-out infinite',
          filter: 'blur(60px)',
        }}
      />
      <div
        className="absolute -bottom-40 left-1/3 w-[500px] h-[500px] rounded-full opacity-20"
        style={{
          background: 'radial-gradient(circle, #8b5cf6 0%, #ec4899 50%, transparent 70%)',
          animation: 'aurora3 18s ease-in-out infinite',
          filter: 'blur(60px)',
        }}
      />
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
          backgroundSize: '60px 60px',
        }}
      />
      <style>{`
        @keyframes aurora1 {
          0%,100% { transform: translate(0,0) scale(1); }
          33% { transform: translate(80px,-60px) scale(1.2); }
          66% { transform: translate(-40px,80px) scale(0.9); }
        }
        @keyframes aurora2 {
          0%,100% { transform: translate(0,0) scale(1); }
          33% { transform: translate(-70px,50px) scale(1.1); }
          66% { transform: translate(60px,-70px) scale(1.3); }
        }
        @keyframes aurora3 {
          0%,100% { transform: translate(0,0) scale(1); }
          50% { transform: translate(50px,-50px) scale(1.2); }
        }
      `}</style>
    </div>
  );
}

export function ParticleField({ count = 60 }: { count?: number }) {
  return (
    <div className="fixed inset-0 -z-10 pointer-events-none overflow-hidden">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="absolute rounded-full"
          style={{
            width: `${Math.random() * 3 + 1}px`,
            height: `${Math.random() * 3 + 1}px`,
            left: `${Math.random() * 100}%`,
            top: `${Math.random() * 100}%`,
            background: ['#0ea5e9', '#10b981', '#8b5cf6', '#f59e0b', '#ec4899'][Math.floor(Math.random() * 5)],
            animation: `particleFloat ${Math.random() * 20 + 10}s linear infinite`,
            animationDelay: `${Math.random() * 10}s`,
            opacity: Math.random() * 0.6 + 0.2,
          }}
        />
      ))}
      <style>{`
        @keyframes particleFloat {
          0% { transform: translateY(0) translateX(0); opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { transform: translateY(-100vh) translateX(${Math.random() > 0.5 ? '' : '-'}${Math.floor(Math.random() * 200)}px); opacity: 0; }
        }
      `}</style>
    </div>
  );
}

export function CursorSpotlight() {
  const spotRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const move = (e: MouseEvent) => {
      if (spotRef.current) {
        spotRef.current.style.left = `${e.clientX}px`;
        spotRef.current.style.top = `${e.clientY}px`;
      }
    };
    window.addEventListener('mousemove', move);
    return () => window.removeEventListener('mousemove', move);
  }, []);
  return (
    <div
      ref={spotRef}
      className="fixed pointer-events-none -z-10 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full"
      style={{
        background: 'radial-gradient(circle, rgba(14,165,233,0.06) 0%, transparent 70%)',
        transition: 'left 0.08s ease-out, top 0.08s ease-out',
      }}
    />
  );
}

export function ScrollProgress() {
  const barRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const update = () => {
      const pct = (window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100;
      if (barRef.current) barRef.current.style.width = `${pct}%`;
    };
    window.addEventListener('scroll', update, { passive: true });
    return () => window.removeEventListener('scroll', update);
  }, []);
  return (
    <div className="fixed top-0 left-0 right-0 z-[100] h-[2px] bg-white/5">
      <div ref={barRef} className="h-full bg-gradient-to-r from-cyan-400 via-violet-500 to-emerald-400 w-0 transition-none" />
    </div>
  );
}
