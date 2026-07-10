import { useState } from 'react';
import { HashRouter, Routes, Route } from 'react-router-dom';
import { AuroraBackground, ParticleField, CursorSpotlight, ScrollProgress } from './components/Background';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import Features from './components/Features';
import CBTSection from './components/CBTSection';
import Demo from './components/Demo';
import Testimonials from './components/Testimonials';
import Pricing from './components/Pricing';
import Footer from './components/Footer';
import OnboardingWizard from './components/OnboardingWizard';
import FAQPage from './pages/FAQ';
import ContactPage from './pages/Contact';

function HomePage({ onOpenWizard }: { onOpenWizard: () => void }) {
  const handleSignIn = () => { window.location.href = '/app/sign-in'; };
  const handleDemo = () => { document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' }); };

  return (
    <>
      <Hero onGetStarted={onOpenWizard} onSignIn={handleSignIn} onDemo={handleDemo} />
      <Features />
      <CBTSection />
      <Demo />
      <Testimonials />
      <Pricing onGetStarted={onOpenWizard} />
    </>
  );
}

export default function App() {
  const [wizardOpen, setWizardOpen] = useState(false);
  const openWizard = () => setWizardOpen(true);
  const handleSignIn = () => { window.location.href = '/app/sign-in'; };

  return (
    <HashRouter>
      <div style={{ background: '#030712', color: '#f8fafc', minHeight: '100vh' }}>
        <AuroraBackground />
        <ParticleField count={50} />
        <CursorSpotlight />
        <ScrollProgress />

        <Navbar onSignIn={handleSignIn} onSignUp={openWizard} />

        <main>
          <Routes>
            <Route path="/" element={<HomePage onOpenWizard={openWizard} />} />
            <Route path="/faq" element={<FAQPage />} />
            <Route path="/contact" element={<ContactPage />} />
          </Routes>
        </main>

        <Footer onGetStarted={openWizard} />

        <OnboardingWizard isOpen={wizardOpen} onClose={() => setWizardOpen(false)} />
      </div>
    </HashRouter>
  );
}
