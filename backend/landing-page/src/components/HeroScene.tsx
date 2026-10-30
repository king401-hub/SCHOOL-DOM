import FeatureOrbit from './FeatureOrbit';

/**
 * Hero visual wrapper. Used to lazy-load a Three.js/WebGL scene behind a
 * device-capability gate with a static CSS fallback - that whole apparatus
 * (HeroScene3D.tsx, HeroSceneFallback.tsx, HeroSceneErrorBoundary.tsx,
 * lib/deviceCapability.ts) existed only to manage WebGL's risk profile:
 * download cost, GPU capability, context-creation failures, load races.
 * FeatureOrbit is plain SVG/CSS/motion - none of those risks exist, so none
 * of that machinery is needed anymore; it was deleted along with this file's
 * previous contents rather than kept around unused.
 */
export default function HeroScene() {
  return (
    <div className="absolute inset-0">
      <FeatureOrbit />
    </div>
  );
}
