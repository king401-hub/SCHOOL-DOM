import { AuroraBackground, ParticleField, CursorSpotlight, ScrollProgress } from './components/Background';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import Features from './components/Features';
import Demo from './components/Demo';
import Testimonials from './components/Testimonials';
import Pricing from './components/Pricing';
import Footer from './components/Footer';

function handleSignIn() {
  window.location.href = '/app/sign-in';
}

function handleSignUp() {
  window.location.href = '/onboarding/wizard/';
}

function handleDemo() {
  document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' });
}

export default function App() {
  return (
    <div style={{ background: '#020817', color: '#fff', minHeight: '100vh' }}>
      <AuroraBackground />
      <ParticleField count={50} />
      <CursorSpotlight />
      <ScrollProgress />

      <Navbar onSignIn={handleSignIn} onSignUp={handleSignUp} />

      <main>
        <Hero onGetStarted={handleSignUp} onSignIn={handleSignIn} onDemo={handleDemo} />
        <Features />
        <Demo />
        <Testimonials />
        <Pricing />
      </main>

      <Footer />
    </div>
  );
}
