import { useEffect, useRef, useState, Suspense } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import {
  PerformanceMonitor, AdaptiveDpr, RoundedBox, ContactShadows,
  Environment, Lightformer,
} from '@react-three/drei';
import type { Group } from 'three';

type Quality = 'low' | 'high';

/** Procedural studio lighting baked into an environment map so the glass
 * materials below have something to actually reflect/refract. Without this,
 * transmissive/PBR materials render flat and near-black regardless of their
 * base color - this was the root cause of the muddy-looking first attempt.
 * Pure virtual light panels (Lightformer), so there is no texture to fetch. */
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

/** A tight cluster of rounded, intersecting acrylic-glass panels at varied
 * sizes/depths/rotations, plus one smooth sphere nested among them - a
 * distinct abstract form rather than the generic "two cubes and a ball"
 * primitive layout. Deliberately overlapping and obliquely angled (not one
 * shape sitting cleanly "on top of" another) so it reads as abstract art,
 * not an accidental camera/device silhouette. Idles in a slow rotation with
 * a gentle mouse-parallax tilt on top.
 *
 * Uses reflective frosted-acrylic materials (clearcoat + environment
 * reflections), not true refractive transmission: the canvas is transparent
 * over the page (alpha: true, no scene background), so a transmissive
 * material has nothing real behind it to refract and renders as a near-
 * black void regardless of lighting - the actual cause of the first
 * attempt's "poor quality" look, not just the missing environment map.
 * Reflection-based frosted glass doesn't have that failure mode and still
 * reads as premium glass/acrylic. */
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
    g.rotation.y += delta * 0.16;
    g.rotation.x += (-pointer.current.y * 0.2 - g.rotation.x) * 0.045;
    g.rotation.z += (pointer.current.x * 0.09 - g.rotation.z) * 0.045;
  });

  const smoothness = quality === 'high' ? 8 : 5;
  const sphereSegments = quality === 'high' ? 48 : 24;

  const glass = (color: string) => (
    <meshPhysicalMaterial
      color={color}
      roughness={0.2}
      metalness={0}
      transmission={0.15}
      thickness={0.4}
      ior={1.3}
      clearcoat={1}
      clearcoatRoughness={0.12}
      envMapIntensity={1.8}
      reflectivity={0.6}
    />
  );

  return (
    <group ref={group} scale={1.05} position={[0, 0, 0]}>
      {/* Large shard - the dominant piece, angled obliquely */}
      <RoundedBox args={[1.6, 1.0, 0.22]} radius={0.16} smoothness={smoothness} position={[-0.15, 0.1, 0]} rotation={[0.3, 0.6, -0.15]}>
        {glass('#1d6b3c')}
      </RoundedBox>
      {/* Medium shard, overlapping at a crossing angle - not stacked parallel */}
      <RoundedBox args={[1.0, 1.3, 0.2]} radius={0.15} smoothness={smoothness} position={[0.45, -0.25, 0.32]} rotation={[-0.45, -0.5, 0.4]}>
        {glass('#2f7d4f')}
      </RoundedBox>
      {/* Small shard, tucked in close */}
      <RoundedBox args={[0.55, 0.8, 0.16]} radius={0.12} smoothness={smoothness} position={[-0.55, 0.4, 0.45]} rotation={[0.6, 0.25, -0.5]}>
        {glass('#4ade80')}
      </RoundedBox>
      {/* Smooth sphere nested into the cluster, overlapping the shards rather
          than sitting isolated beneath them - avoids reading as a lens/wheel
          on a "device". Real sphere geometry at every tier, never faceted. */}
      <mesh position={[-0.25, -0.55, 0.6]}>
        <sphereGeometry args={[0.34, sphereSegments, sphereSegments]} />
        {glass('#4ade80')}
      </mesh>
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
      camera={{ position: [0, 0, 5], fov: 36 }}
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
          <GlassCluster quality={quality} />
          {quality === 'high' && (
            <ContactShadows position={[0, -1.35, 0]} opacity={0.35} scale={6} blur={2.4} far={2} color="#141310" />
          )}
        </Suspense>
      </PerformanceMonitor>
    </Canvas>
  );
}
