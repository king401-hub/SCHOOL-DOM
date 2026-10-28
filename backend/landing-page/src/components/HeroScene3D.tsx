import { useEffect, useRef, useState, Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { Canvas, useFrame } from '@react-three/fiber';
import {
  PerformanceMonitor, AdaptiveDpr, RoundedBox, ContactShadows, Html,
  Environment, Lightformer,
} from '@react-three/drei';
import { DollarSign, BookOpen, QrCode, FileText, Briefcase, MessageSquare } from 'lucide-react';
import type { Group } from 'three';

type Quality = 'low' | 'high';
type IconType = typeof DollarSign;

interface ModuleDef { icon: IconType; key: string; color: string }

const MODULES: ModuleDef[] = [
  { icon: DollarSign, key: 'features.grid.finance.title', color: '#1d6b3c' },
  { icon: BookOpen, key: 'features.grid.cbtEngine.title', color: '#2f7d4f' },
  { icon: QrCode, key: 'features.grid.attendance.title', color: '#4ade80' },
  { icon: FileText, key: 'features.grid.reportCards.title', color: '#206e3c' },
  { icon: Briefcase, key: 'features.grid.hr.title', color: '#35966a' },
  { icon: MessageSquare, key: 'features.grid.parentPortal.title', color: '#4fae7f' },
];

/** Procedural studio lighting baked into an environment map so the glass
 * materials below have something to actually reflect. Pure virtual light
 * panels (Lightformer), so there is no texture to fetch. */
function Studio({ quality }: { quality: Quality }) {
  return (
    <Environment resolution={quality === 'high' ? 256 : 64}>
      <group>
        <Lightformer form="rect" color="#ffffff" intensity={3.2} position={[0, 4, 3]} scale={[8, 2.2, 1]} rotation={[-Math.PI / 4, 0, 0]} />
        <Lightformer form="rect" color="#dff7e8" intensity={1.6} position={[-4, 0.5, 2]} scale={[3.5, 4, 1]} rotation={[0, Math.PI / 2.4, 0]} />
        <Lightformer form="rect" color="#14532d" intensity={1.3} position={[4, -0.5, -1]} scale={[4.5, 3.5, 1]} rotation={[0, -Math.PI / 2.6, 0]} />
        <Lightformer form="ring" color="#ffffff" intensity={2.2} position={[0, -1, 5]} scale={6} />
      </group>
    </Environment>
  );
}

/** Six labelled glass cards, one per SchoolDom module, arranged as spokes
 * around a central hub - a literal wheel rather than abstract decoration,
 * so the piece visibly reads as this product's own feature set in 3D form.
 * Each card carries a drei <Html> chip (icon + the real, localized module
 * name pulled from the same features.grid.* i18n keys Features.tsx uses) so
 * the connection to the product is legible, not implied. The wheel spins
 * continuously in its own plane (rotation.z) so cards stay face-on to the
 * camera throughout the turn instead of flipping away - the group carries a
 * fixed tilt so it reads as a wheel viewed at an angle, not a flat clock
 * face, with a gentle mouse-parallax wobble layered on top. */
function ModuleWheel({ quality }: { quality: Quality }) {
  const { t } = useTranslation();
  const group = useRef<Group>(null);
  const pointer = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      pointer.current.x = (e.clientX / window.innerWidth) * 2 - 1;
      pointer.current.y = (e.clientY / window.innerHeight) * 2 - 1;
    };
    window.addEventListener('pointermove', onMove);
    return () => window.removeEventListener('pointermove', onMove);
  }, []);

  const BASE_TILT_X = 0.34;
  const BASE_TILT_Y = 0.1;

  useFrame((_, delta) => {
    const g = group.current;
    if (!g) return;
    g.rotation.z += delta * 0.32;
    g.rotation.x += (BASE_TILT_X - pointer.current.y * 0.16 - g.rotation.x) * 0.045;
    g.rotation.y += (BASE_TILT_Y + pointer.current.x * 0.14 - g.rotation.y) * 0.045;
  });

  const smoothness = quality === 'high' ? 8 : 5;
  // Wide enough that adjacent labels (60deg apart, chord length == RADIUS)
  // don't crowd each other as the wheel turns through intermediate angles -
  // narrower radii visibly collided at some rotation phases.
  const RADIUS = 1.55;

  const glass = (color: string) => (
    <meshPhysicalMaterial
      color={color}
      roughness={0.22}
      metalness={0}
      transmission={0.1}
      thickness={0.3}
      ior={1.3}
      clearcoat={1}
      clearcoatRoughness={0.14}
      envMapIntensity={1.6}
      reflectivity={0.55}
    />
  );

  return (
    <group ref={group} scale={0.86} position={[0, 0, 0]} rotation={[BASE_TILT_X, BASE_TILT_Y, 0]}>
      {/* Hub */}
      <mesh>
        <sphereGeometry args={[0.26, quality === 'high' ? 32 : 16, quality === 'high' ? 32 : 16]} />
        {glass('#206e3c')}
      </mesh>
      {MODULES.map((m, i) => {
        const n = MODULES.length;
        const angle = (i / n) * Math.PI * 2;
        const x = Math.cos(angle) * RADIUS;
        const y = Math.sin(angle) * RADIUS;
        const rotZ = angle + Math.PI / 2; // tangential, like a spoke
        const Icon = m.icon;
        return (
          <group key={m.key}>
            {/* Spoke */}
            <mesh position={[x / 2, y / 2, -0.02]} rotation={[0, 0, rotZ]}>
              <boxGeometry args={[0.03, RADIUS * 0.82, 0.03]} />
              <meshStandardMaterial color="#143b26" roughness={0.4} metalness={0.2} />
            </mesh>
            <group position={[x, y, 0]} rotation={[0, 0, rotZ]}>
              <RoundedBox args={[0.62, 0.4, 0.05]} radius={0.06} smoothness={smoothness}>
                {glass(m.color)}
              </RoundedBox>
              <Html
                position={[0, 0, 0.04]}
                center
                distanceFactor={quality === 'high' ? 7.4 : 8.4}
                style={{ pointerEvents: 'none' }}
              >
                <div
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-full whitespace-nowrap"
                  style={{
                    background: 'rgba(var(--c-surface-rgb),0.92)',
                    border: '1px solid rgba(var(--c-ink-rgb),0.1)',
                    boxShadow: '0 4px 14px rgba(var(--c-ink-rgb),0.12)',
                    fontSize: 11,
                    fontWeight: 600,
                    color: 'var(--c-ink)',
                  }}
                >
                  <Icon size={12} style={{ color: m.color, flexShrink: 0 }} />
                  {t(m.key)}
                </div>
              </Html>
            </group>
          </group>
        );
      })}
    </group>
  );
}

function Lights() {
  return (
    <>
      <ambientLight intensity={0.4} />
      <directionalLight position={[4, 6, 5]} intensity={0.8} color="#ffffff" />
      <directionalLight position={[-5, -2, -3]} intensity={0.25} color="#4ade80" />
    </>
  );
}

interface HeroScene3DProps { paused: boolean }

/** The live WebGL hero scene. Only ever mounted on devices the capability
 * gate (deviceCapability.ts) has already decided can run it, and lazy-loaded
 * so Three.js never lands in the main bundle. Quality adapts live via
 * PerformanceMonitor - starts at a tier picked from core count, then scales
 * between 'low' and 'high' as measured frame time actually comes in. */
export default function HeroScene3D({ paused }: HeroScene3DProps) {
  const [quality, setQuality] = useState<Quality>(() =>
    (navigator.hardwareConcurrency || 4) <= 4 ? 'low' : 'high'
  );

  return (
    <Canvas
      dpr={[1, quality === 'high' ? 2 : 1]}
      gl={{ antialias: true, alpha: true, powerPreference: quality === 'high' ? 'high-performance' : 'low-power' }}
      camera={{ position: [0, 0, 6.2], fov: 36 }}
      frameloop={paused ? 'never' : 'always'}
      style={{ pointerEvents: 'none' }}
    >
      <PerformanceMonitor
        onDecline={() => setQuality('low')}
        onIncline={() => setQuality('high')}
        flipflops={2}
        factor={1}
      >
        <AdaptiveDpr pixelated />
        <Lights />
        <Suspense fallback={null}>
          <Studio quality={quality} />
          <ModuleWheel quality={quality} />
          {quality === 'high' && (
            <ContactShadows position={[0, -0.85, 0]} opacity={0.3} scale={5} blur={2.4} far={2} color="#141310" />
          )}
        </Suspense>
      </PerformanceMonitor>
    </Canvas>
  );
}
