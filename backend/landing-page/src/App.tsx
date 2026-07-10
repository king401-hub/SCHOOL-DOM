import { useState } from 'react';
import { AuroraBackground, ParticleField, CursorSpotlight, ScrollProgress } from './components/Background';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import Features from './components/Features';
import Demo from './components/Demo';
import Testimonials from './components/Testimonials';
import Pricing from './components/Pricing';
import Footer from './components/Footer';
import OnboardingWizard from './components/OnboardingWizard';

export default function App() {
  const [wizardOpen, setWizardOpen] = useState(false);

  const openWizard = () => setWizardOpen(true);

  const handleSignIn = () => {
    window.location.href = '/app/sign-in';
  };

  const handleDemo = () => {
    document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div style={{ background: '#020817', color: '#fff', minHeight: '100vh' }}>
      <AuroraBackground />
      <ParticleField count={50} />
      <CursorSpotlight />
      <ScrollProgress />

      <Navbar onSignIn={handleSignIn} onSignUp={openWizard} />

      <main>
        <Hero onGetStarted={openWizard} onSignIn={handleSignIn} onDemo={handleDemo} />
        <Features />
        <Demo />
        <Testimonials />
        <Pricing onGetStarted={openWizard} />
      </main>

      <Footer onGetStarted={openWizard} />

      <OnboardingWizard isOpen={wizardOpen} onClose={() => setWizardOpen(false)} />
    </div>
  );
}
