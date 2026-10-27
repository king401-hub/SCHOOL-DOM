import { Component, type ReactNode } from 'react';

interface Props { children: ReactNode; fallback: ReactNode }
interface State { hasError: boolean }

/**
 * Catches a WebGL/Three.js mount failure - e.g. a driver-blocklisted GPU that
 * still reports WebGL2 support at feature-detection time - and drops to the
 * static fallback instead of crashing the hero section.
 */
export default class HeroSceneErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  componentDidCatch(error: unknown) { console.warn('[HeroScene] falling back to static visual:', error); }
  render() {
    return this.state.hasError ? this.props.fallback : this.props.children;
  }
}
