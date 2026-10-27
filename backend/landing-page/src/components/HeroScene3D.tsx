import { useEffect, useRef, useState, Suspense } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { PerformanceMonitor, AdaptiveDpr, RoundedBox, ContactShadows } from '@react-three/drei';
import type { Group } from 'three';

type Quality = 'low' | 'high';

/** A small cluster of rounded glass-like forms in ink/green/mint, idling in
 * a slow rotation with a gentle mouse-parallax tilt on top. Deliberately
 * restrained - three shapes, not a particle field. */
function GlassCluster({ quality }: { quality: Quality }) {
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

  useFrame((_, delta) => {
    const g = group.current;
    if (!g) return;
    g.rotation.y += delta * 0.18;
    g.rotation.x += (-pointer.current.y * 0.22 - g.rotation.x) * 0.045;
    g.rotation.z += (pointer.current.x * 0.1 - g.rotation.z) * 0.045;
  });

  const smoothness = quality === 'high' ? 6 : 3;
  const icoDetail = quality === 'high' ? 2 : 0;

  const glass = (color: string, metalness = 0) =>
    quality === 'high' ? (
      <meshPhysicalMaterial
        color={color}
        transmission={0.85}
        roughness={0.12}
        thickness={0.6}
        ior={1.35}
        clearcoat={1}
        clearcoatRoughness={0.15}
        metalness={metalness}
        attenuationColor={color}
        attenuationDistance={1.5}
      />
    ) : (
      <meshStandardMaterial color={color} transparent opacity={0.6} roughness={0.25} metalness={metalness} />
    );

  return (
    <group ref={group} scale={0.62} position={[0.35, 0.1, 0]}>
      <RoundedBox args={[1.5, 1.5, 1.5]} radius={0.22} smoothness={smoothness} position={[0, 0, 0]}>
        {glass('#2a4a3a')}
      </RoundedBox>
      <RoundedBox args={[0.8, 0.8, 0.8]} radius={0.16} smoothness={smoothness} position={[1.2, 0.55, 0.5]}>
        {glass('#14532d')}
      </RoundedBox>
      <mesh position={[-1.05, -0.5, 0.35]}>
        <icosahedronGeometry args={[0.52, icoDetail]} />
        {glass('#4ade80', 0.1)}
      </mesh>
    </group>
  );
}

function Lights({ quality }: { quality: Quality }) {
  return (
    <>
      <ambientLight intensity={0.55} />
      <directionalLight position={[4, 6, 5]} intensity={1.15} color="#ffffff" />
      <directionalLight position={[-5, -2, -3]} intensity={0.3} color="#4ade80" />
      {quality === 'high' && <pointLight position={[0, 2, 3]} intensity={0.35} color="#f5f4f1" />}
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
      gl={{ antialias: quality === 'high', alpha: true, powerPreference: quality === 'high' ? 'high-performance' : 'low-power' }}
      camera={{ position: [0, 0, 5.5], fov: 38 }}
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
        <Lights quality={quality} />
        <Suspense fallback={null}>
          <GlassCluster quality={quality} />
          {quality === 'high' && (
            <ContactShadows position={[0, -1.35, 0]} opacity={0.35} scale={6} blur={2.4} far={2} color="#141310" />
          )}
        </Suspense>
      </PerformanceMonitor>
    </Canvas>
  );
}
