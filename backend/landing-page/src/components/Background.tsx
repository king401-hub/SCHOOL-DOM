import { useEffect, useRef, useState } from 'react';

export function AuroraBackground() {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      <div className="absolute -top-96 -left-60 w-[700px] h-[700px] rounded-full animate-aurora"
        style={{ background: 'radial-gradient(circle, rgba(34,197,94,0.08) 0%, transparent 70%)', filter: 'blur(90px)' }} />
      <div className="absolute top-1/4 -right-72 w-[600px] h-[600px] rounded-full animate-aurora-delayed"
        style={{ background: 'radial-gradient(circle, rgba(14,165,233,0.07) 0%, transparent 70%)', filter: 'blur(90px)' }} />
      <div className="absolute bottom-0 left-1/3 w-[500px] h-[500px] rounded-full animate-aurora-slow"
        style={{ background: 'radial-gradient(circle, rgba(139,92,246,0.05) 0%, transparent 70%)', filter: 'blur(90px)' }} />
      <div className="absolute inset-0 perspective-grid opacity-25"
        style={{ maskImage: 'radial-gradient(ellipse at 50% 0%, black 0%, transparent 70%)' }} />
    </div>
  );
}

export function ParticleField({ count = 40 }: { count?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    const colors = ['rgba(34,197,94,', 'rgba(14,165,233,', 'rgba(139,92,246,', 'rgba(16,185,129,'];
    const particles = Array.from({ length: count }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 1.5 + 0.5,
      vx: (Math.random() - 0.5) * 0.3,
      vy: -Math.random() * 0.4 - 0.1,
      color: colors[Math.floor(Math.random() * colors.length)],
      opacity: Math.random() * 0.4 + 0.1,
    }));
    let frame: number;
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        if (p.y < -5) { p.y = canvas.height + 5; p.x = Math.random() * canvas.width; }
        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `${p.color}${p.opacity})`;
        ctx.fill();
      });
      frame = requestAnimationFrame(draw);
    };
    draw();
    const resize = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight; };
    window.addEventListener('resize', resize);
    return () => { cancelAnimationFrame(frame); window.removeEventListener('resize', resize); };
  }, [count]);
  return <canvas ref={canvasRef} className="fixed inset-0 pointer-events-none z-0 opacity-60" />;
}

const SCHOOL_GLYPHS = ['🎓', '📚', '✏️', '🧮', '🌍', '🔬', '📐', '🖥️', '🏫', '📝', '⚗️', '🎨', '📊', '🔔'];

export function IconConstellation({ count = 14 }: { count?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const nodes = Array.from({ length: count }, (_, i) => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.35,
      vy: (Math.random() - 0.5) * 0.35,
      glyph: SCHOOL_GLYPHS[i % SCHOOL_GLYPHS.length],
      size: 18 + Math.random() * 10,
      phase: Math.random() * Math.PI * 2,
    }));

    const LINK_DIST = 240;
    let frame: number;
    let t = 0;

    const draw = () => {
      t += 0.008;
      const light = document.documentElement.classList.contains('light');
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Connection lines
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const dist = Math.hypot(dx, dy);
          if (dist < LINK_DIST) {
            const alpha = (1 - dist / LINK_DIST) * (light ? 0.14 : 0.12);
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.strokeStyle = light ? `rgba(15,23,42,${alpha})` : `rgba(148,163,184,${alpha})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        }
      }

      // Icon nodes with gentle bob
      nodes.forEach(n => {
        n.x += n.vx;
        n.y += n.vy + Math.sin(t * 2 + n.phase) * 0.08;
        if (n.x < -30) n.x = canvas.width + 30;
        if (n.x > canvas.width + 30) n.x = -30;
        if (n.y < -30) n.y = canvas.height + 30;
        if (n.y > canvas.height + 30) n.y = -30;

        ctx.globalAlpha = light ? 0.38 : 0.32;
        ctx.font = `${n.size}px serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(n.glyph, n.x, n.y);
        ctx.globalAlpha = 1;
      });

      frame = requestAnimationFrame(draw);
    };
    draw();

    const resize = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight; };
    window.addEventListener('resize', resize);
    return () => { cancelAnimationFrame(frame); window.removeEventListener('resize', resize); };
  }, [count]);

  return <canvas ref={canvasRef} className="fixed inset-0 pointer-events-none z-0" />;
}

export function CursorSpotlight() {
  const [pos, setPos] = useState({ x: -200, y: -200 });
  useEffect(() => {
    const move = (e: MouseEvent) => setPos({ x: e.clientX, y: e.clientY });
    window.addEventListener('mousemove', move);
    return () => window.removeEventListener('mousemove', move);
  }, []);
  return (
    <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden"
      style={{
        background: `radial-gradient(400px circle at ${pos.x}px ${pos.y}px, rgba(34,197,94,0.04) 0%, transparent 60%)`,
        transition: 'background 0.1s ease',
      }}
    />
  );
}

export function ScrollProgress() {
  const [pct, setPct] = useState(0);
  useEffect(() => {
    const update = () => {
      const el = document.documentElement;
      setPct((el.scrollTop / (el.scrollHeight - el.clientHeight)) * 100);
    };
    window.addEventListener('scroll', update, { passive: true });
    return () => window.removeEventListener('scroll', update);
  }, []);
  return (
    <div className="fixed top-0 left-0 right-0 z-[999] h-[2px]">
      <div
        className="h-full transition-all duration-100"
        style={{ width: `${pct}%`, background: 'linear-gradient(90deg, #22c55e, #0ea5e9, #8b5cf6)' }}
      />
    </div>
  );
}
