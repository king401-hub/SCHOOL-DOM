import React, { useState } from 'react';
import { 
  X, Check, ChevronRight, School, Sparkles, User, Mail, Phone, 
  MapPin, Sliders, ShieldCheck, Cpu, RefreshCw, Layers, Award
} from 'lucide-react';

interface OnboardingWizardProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function OnboardingWizard({ isOpen, onClose }: OnboardingWizardProps) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState('');
  const [onboardSuccess, setOnboardSuccess] = useState(false);

  // Form State
  const [schoolName, setSchoolName] = useState('');
  const [schoolType, setSchoolType] = useState<'K12' | 'Non-K12'>('K12');
  const [isGroup, setIsGroup] = useState(false);
  const [locationState, setLocationState] = useState('Lagos State');
  const [authName, setAuthName] = useState('');
  const [authEmail, setAuthEmail] = useState('');
  const [authPhone, setAuthPhone] = useState('');
  const [studentSize, setStudentSize] = useState(350);
  const [legalConsent, setLegalConsent] = useState(false);
  
  // Integrations preferences
  const [modulesSelected, setModulesSelected] = useState({
    cbtOffline: true,
    financeGate: true,
    reportCards: true,
    biometrics: false,
    idBuilder: true
  });

  if (!isOpen) return null;

  const toggleModule = (key: keyof typeof modulesSelected) => {
    setModulesSelected({
      ...modulesSelected,
      [key]: !modulesSelected[key]
    });
  };

  const handleNextStep = () => {
    if (step === 1 && schoolName.trim() === '') {
      return; // validate basic
    }
    if (step === 2 && (authName.trim() === '' || authEmail.trim() === '' || authPhone.trim() === '')) {
      return; // validate basic
    }
    setStep(prev => prev + 1);
  };

  const handlePrevStep = () => {
    setStep(prev => prev - 1);
  };

  const handleFinalSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    const stages = [
      "Securing administrative endpoint cluster...",
      "Mapping physical database shards...",
      "Configuring Schooldom Hybrid CBT credentials...",
      "Generating terminal certificate seals..."
    ];

    stages.forEach((msg, index) => {
      setTimeout(() => {
        setLoadingStage(msg);
        if (index === stages.length - 1) {
          setTimeout(() => {
            setLoading(false);
            setOnboardSuccess(true);
            localStorage.setItem('schooldom_onboarding_school_name', schoolName);
            window.dispatchEvent(new CustomEvent('schooldom_school_name_changed'));
          }, 800);
        }
      }, index * 400);
    });
  };

  const generatedRegId = `SD-SCH-${Math.floor(1000 + Math.random() * 9000)}`;

  return (
    <div className="fixed inset-0 z-100 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs text-left">
      <div className="relative w-full max-w-2xl bg-white rounded-3xl overflow-hidden shadow-2xl border border-gray-100 flex flex-col max-h-[90vh]">
        
        {/* Header Ribbon Indicator */}
        <div className="bg-brand-600 text-white px-6 py-4 flex items-center justify-between relative">
          <div className="flex items-center gap-2.5">
            <School className="h-5.5 w-5.5 text-teal-brand-500" />
            <div>
              <h3 className="font-display font-bold text-base">Schooldom Enterprise Onboarding</h3>
              <p className="text-[10px] text-brand-100 font-mono">STEP {step} OF 3 • REGISTRATION PROFILE</p>
            </div>
          </div>
          <button
            id="wizard-btn-close"
            onClick={onClose}
            className="p-1.5 hover:bg-white/10 rounded-lg cursor-pointer transition-colors text-white"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content body layout container */}
        <div className="p-6 sm:p-8 overflow-y-auto flex-1">
          {loading ? (
            /* Intermediary Installation progress loop */
            <div className="py-12 flex flex-col items-center justify-center text-center space-y-6">
              <RefreshCw className="h-12 w-12 text-brand-600 animate-spin" />
              <div className="space-y-2">
                <h4 className="font-display font-bold text-lg text-brand-950">Provisioning Schooldom Sandbox Shards</h4>
                <p className="text-xs text-gray-500 max-w-xs mx-auto">Please wait while our West African server nodes organize databases for your institution.</p>
              </div>
              <div className="px-5 py-2.5 rounded-xl bg-slate-50 border border-gray-150 inline-block text-xs font-semibold text-slate-600 font-mono animate-pulse">
                {loadingStage || "Connecting to core cloud routers..."}
              </div>
            </div>
          ) : onboardSuccess ? (
            /* Successful digitizing certificate of authenticity */
            <div className="space-y-6 animate-in zoom-in-95 duration-300">
              
              <div className="text-center space-y-2">
                <div className="h-12 w-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto text-xl font-bold">✓</div>
                <h4 className="font-display font-extrabold text-xl text-brand-950">Institution Successfully Onboarded!</h4>
                <p className="text-xs text-gray-500">Your school operations have been compiled on the Schooldom cluster.</p>
              </div>

              {/* Dynamic physical Certificate layout */}
              <div className="border border-brand-200/80 rounded-2xl p-6 bg-slate-50 relative overflow-hidden max-w-lg mx-auto shadow-sm">
                
                {/* Visual watermark */}
                <div className="absolute top-[30%] left-[50%] -translate-x-1/2 -translate-y-1/2 opacity-5 pointer-events-none">
                  <Award className="h-44 w-44 text-brand-950" />
                </div>

                <div className="text-center border-b border-brand-100 pb-4">
                  <span className="text-[9px] font-bold text-brand-600 bg-brand-50 border border-brand-200 px-2.5 py-0.5 rounded-full uppercase">
                    Certification of Digital Migration
                  </span>
                  <h5 className="font-display font-extrabold text-sm text-brand-950 uppercase mt-2">{schoolName || "ROYAL CLASSIC MODEL SCHOOL"}</h5>
                  <p className="text-[10px] text-gray-400 font-mono tracking-wider mt-0.5">REGISTERED CLOUD IDENTITY: {generatedRegId}</p>
                </div>

                <div className="py-4 space-y-2.5 text-xs text-gray-600 border-b border-gray-100">
                  <div className="flex justify-between">
                    <span>Administrative Campus:</span>
                    <strong className="text-slate-800">{locationState}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span>Authorized Registrar:</span>
                    <strong className="text-slate-800">{authName} ({authEmail})</strong>
                  </div>
                  <div className="flex justify-between">
                    <span>Subscription Category:</span>
                    <strong className="text-sky-950 font-bold">{schoolType === 'K12' ? 'K12 Termly Contract' : 'Non-K12 Monthly Flex'}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span>Assigned Student Seats:</span>
                    <strong className="text-sky-950 font-mono font-bold">{studentSize} Enrolled</strong>
                  </div>
                </div>

                {/* Schooldom Credit Hub Prequalification Access */}
                <div className="mt-3 p-3 bg-emerald-50 border border-emerald-150 rounded-xl space-y-1">
                  <div className="flex items-center gap-1.5 text-emerald-800 font-bold">
                    <Sparkles className="h-4 w-4 text-emerald-600 animate-pulse shrink-0" />
                    <span>Special Credit Hub Offer (Prequalified)</span>
                  </div>
                  <p className="text-[10px] text-emerald-700 leading-normal">
                    Based on your onboarding scale of <strong className="text-emerald-950">{studentSize} student seats</strong>, your institution is provisionally prequalified for up to <strong className="text-emerald-950">₦{(studentSize * 7500).toLocaleString()}</strong> in school development &amp; hardware facilities loans from our verified financial partners (including EdFin MFB).
                  </p>
                  <p className="text-[8px] text-emerald-500/80 italic font-mono uppercase tracking-wide">
                    *Terms and Conditions Apply. subject to final portfolio risk review.
                  </p>
                </div>

                <div className="pt-3 text-[10px] text-slate-400 text-center leading-relaxed font-medium">
                  Approved by NUC & WAEC Digital Operations Registry. Welcome to the future of organized education.
                </div>

              </div>

              <div className="flex gap-3 justify-center">
                <button
                  id="btn-succ-close"
                  onClick={() => {
                    setOnboardSuccess(false);
                    setStep(1);
                    setSchoolName('');
                    setAuthName('');
                    setAuthEmail('');
                    setAuthPhone('');
                    onClose();
                  }}
                  className="px-6 py-2.5 rounded-xl text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 cursor-pointer"
                >
                  Conclude Setup Workspace
                </button>
              </div>

            </div>
          ) : (
            <form onSubmit={handleFinalSubmit} className="space-y-6">
              
              {/* STEP 1: school characteristics */}
              {step === 1 && (
                <div className="space-y-5 text-xs text-gray-600 animate-in fade-in duration-200">
                  <div>
                    <h4 className="font-display font-bold text-base text-brand-950 mb-1">Tell us about your Institution</h4>
                    <p className="text-gray-400">Please provide verified physical parameters of the campus.</p>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label htmlFor="input-wizard-sch" className="block font-bold mb-1.5 text-slate-700">School Name / Group Name:</label>
                      <input
                        id="input-wizard-sch"
                        type="text"
                        required
                        placeholder="e.g. Royal Heights Group of Schools"
                        value={schoolName}
                        onChange={(e) => setSchoolName(e.target.value)}
                        className="w-full border border-gray-200 rounded-xl px-4.5 py-3 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20 bg-white"
                      />
                      {schoolName.trim() === '' && (
                        <p className="text-[10px] text-rose-500 mt-1">Institutional title is mandatory to continue.</p>
                      )}
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label htmlFor="select-wizard-type" className="block font-bold mb-1.5 text-slate-700">Academic Structure:</label>
                        <select
                          id="select-wizard-type"
                          value={schoolType}
                          onChange={(e) => setSchoolType(e.target.value as any)}
                          className="w-full border border-gray-200 rounded-xl px-4.5 py-3 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20 bg-white focus:outline-hidden"
                        >
                          <option value="K12">K12 (Nursery/Primary/Secondary)</option>
                          <option value="Non-K12">Non-K12 (Vocational/Continuing)</option>
                        </select>
                      </div>
                      <div>
                        <label htmlFor="select-wizard-loc" className="block font-bold mb-1.5 text-slate-700">Location Territory:</label>
                        <select
                          id="select-wizard-loc"
                          value={locationState}
                          onChange={(e) => setLocationState(e.target.value)}
                          className="w-full border border-gray-200 rounded-xl px-4.5 py-3 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20 bg-white"
                        >
                          <option value="Lagos State">Lagos State</option>
                          <option value="Oyo State">Oyo State</option>
                          <option value="Kaduna State">Kaduna State</option>
                          <option value="Rivers State">Rivers State</option>
                          <option value="Abuja FCT">Abuja FCT</option>
                        </select>
                      </div>
                    </div>

                    {/* Group of schools Toggle */}
                    <div className="p-4 bg-slate-50 rounded-2xl border border-gray-100 flex items-center justify-between">
                      <div className="space-y-1">
                        <span className="font-bold text-slate-700 block">Is this a group or multi-school brand?</span>
                        <span className="text-[10px] text-gray-400">Select to provision centralized executive dashboard reporting.</span>
                      </div>
                      <input
                        id="checkbox-wizard-group"
                        type="checkbox"
                        checked={isGroup}
                        onChange={(e) => setIsGroup(e.target.checked)}
                        className="h-5 w-5 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
                      />
                    </div>
                  </div>

                  <div className="border-t border-gray-100 pt-5 flex justify-end">
                    <button
                      id="wizard-btn-next1"
                      type="button"
                      disabled={schoolName.trim() === ''}
                      onClick={handleNextStep}
                      className="inline-flex items-center gap-1.5 px-6 py-3 rounded-xl font-bold bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50 cursor-pointer"
                    >
                      Continue to Registrar Details
                      <ChevronRight className="h-4.5 w-4.5" />
                    </button>
                  </div>
                </div>
              )}

              {/* STEP 2: administrator data */}
              {step === 2 && (
                <div className="space-y-5 text-xs text-gray-600 animate-in fade-in duration-250">
                  <div>
                    <h4 className="font-display font-bold text-base text-brand-950 mb-1">Registrar Contact Dossier</h4>
                    <p className="text-gray-400">Input primary administrative representative details below.</p>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label htmlFor="input-wizard-name" className="block font-bold mb-1.5 text-slate-700">Full Name:</label>
                      <input
                        id="input-wizard-name"
                        type="text"
                        required
                        placeholder="e.g. Proprietress Florence Adebayo"
                        value={authName}
                        onChange={(e) => setAuthName(e.target.value)}
                        className="w-full border border-gray-200 rounded-xl px-4.5 py-3 text-sm focus:border-brand-500 bg-white"
                      />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label htmlFor="input-wizard-email" className="block font-bold mb-1.5 text-slate-700">Official Email Address:</label>
                        <input
                          id="input-wizard-email"
                          type="email"
                          required
                          placeholder="principal@school.com"
                          value={authEmail}
                          onChange={(e) => setAuthEmail(e.target.value)}
                          className="w-full border border-gray-200 rounded-xl px-4.5 py-3 text-sm focus:border-brand-500 bg-white"
                        />
                      </div>
                      <div>
                        <label htmlFor="input-wizard-phone" className="block font-bold mb-1.5 text-slate-700">Mobile Phone Number:</label>
                        <input
                          id="input-wizard-phone"
                          type="tel"
                          required
                          placeholder="+234 80xxxxxxxx"
                          value={authPhone}
                          onChange={(e) => setAuthPhone(e.target.value)}
                          className="w-full border border-gray-200 rounded-xl px-4.5 py-3 text-sm focus:border-brand-500 bg-white"
                        />
                      </div>
                    </div>

                    {/* Student count estimates slide */}
                    <div className="p-4 bg-brand-50 rounded-2xl border border-brand-100 space-y-3">
                      <div className="flex justify-between font-bold text-brand-900">
                        <label htmlFor="wizard-slider-size">Students to Activate (Backend is Free):</label>
                        <span className="font-mono text-brand-650">{studentSize} SEATS BINDING</span>
                      </div>
                      <input
                        id="wizard-slider-size"
                        type="range"
                        min="50"
                        max="3000"
                        step="50"
                        value={studentSize}
                        onChange={(e) => setStudentSize(parseInt(e.target.value))}
                        className="w-full h-2 bg-brand-200 rounded-lg appearance-none cursor-pointer accent-brand-600"
                      />
                      <p className="text-[10px] text-gray-400 italic">Admins &amp; Teachers are 100% free! Paying the activation fee unlocks portals and dynamic CBT tools for students.</p>
                    </div>
                  </div>

                  <div className="border-t border-gray-100 pt-5 flex items-center justify-between">
                    <button
                      id="wizard-btn-prev2"
                      type="button"
                      onClick={handlePrevStep}
                      className="px-5 py-3 rounded-xl border border-gray-200 text-gray-700 hover:bg-slate-50 font-semibold cursor-pointer"
                    >
                      Back
                    </button>
                    <button
                      id="wizard-btn-next2"
                      type="button"
                      disabled={authName.trim() === '' || authEmail.trim() === '' || authPhone.trim() === ''}
                      onClick={handleNextStep}
                      className="inline-flex items-center gap-1.5 px-6 py-3 rounded-xl font-bold bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50 cursor-pointer"
                    >
                      Select Digital Modules
                      <ChevronRight className="h-4.5 w-4.5" />
                    </button>
                  </div>
                </div>
              )}

              {/* STEP 3: modules integrations validation */}
              {step === 3 && (
                <div className="space-y-5 text-xs text-gray-600 animate-in fade-in duration-250">
                  <div>
                    <h4 className="font-display font-bold text-base text-brand-950 mb-1">Tailor Schooldom Modules</h4>
                    <p className="text-gray-400">Select which digital solutions components to provision on your initial profile workspace.</p>
                  </div>

                  <div className="space-y-2.5 max-h-[260px] overflow-y-auto pr-1">
                    
                    <div 
                      onClick={() => toggleModule('cbtOffline')}
                      className={`p-3 border rounded-xl flex items-center justify-between cursor-pointer transition-colors ${
                        modulesSelected.cbtOffline ? 'bg-brand-50 border-brand-500' : 'bg-white border-gray-200 hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center gap-3 text-left">
                        <Cpu className={`h-5 w-5 ${modulesSelected.cbtOffline ? 'text-brand-600' : 'text-gray-400'}`} />
                        <div>
                          <p className="font-bold text-slate-800">Hybrid Offline CBT system</p>
                          <p className="text-[10px] text-gray-400">Required local area server package sync.</p>
                        </div>
                      </div>
                      <div className={`h-5 w-5 rounded flex items-center justify-center border ${modulesSelected.cbtOffline ? 'bg-brand-600 border-brand-700 text-white' : 'border-gray-300'}`}>
                        {modulesSelected.cbtOffline && <Check className="h-3 w-3" />}
                      </div>
                    </div>

                    <div 
                      onClick={() => toggleModule('financeGate')}
                      className={`p-3 border rounded-xl flex items-center justify-between cursor-pointer transition-colors ${
                        modulesSelected.financeGate ? 'bg-brand-50 border-brand-500' : 'bg-white border-gray-200 hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center gap-3 text-left">
                        <Sliders className={`h-5 w-5 ${modulesSelected.financeGate ? 'text-brand-600' : 'text-gray-400'}`} />
                        <div>
                          <p className="font-bold text-slate-800">Finance & Integrated payment gateways</p>
                          <p className="text-[10px] text-gray-400">SMS, WhatsApp invoices & auto receipts.</p>
                        </div>
                      </div>
                      <div className={`h-5 w-5 rounded flex items-center justify-center border ${modulesSelected.financeGate ? 'bg-brand-600 border-brand-700 text-white' : 'border-gray-300'}`}>
                        {modulesSelected.financeGate && <Check className="h-3 w-3" />}
                      </div>
                    </div>

                    <div 
                      onClick={() => toggleModule('reportCards')}
                      className={`p-3 border rounded-xl flex items-center justify-between cursor-pointer transition-colors ${
                        modulesSelected.reportCards ? 'bg-brand-50 border-brand-500' : 'bg-white border-gray-200 hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center gap-3 text-left">
                        <Award className={`h-5 w-5 ${modulesSelected.reportCards ? 'text-brand-600' : 'text-gray-400'}`} />
                        <div>
                          <p className="font-bold text-slate-800">Academic Report Sheet generation</p>
                          <p className="text-[10px] text-gray-400">Compute position ranks & termly averages.</p>
                        </div>
                      </div>
                      <div className={`h-5 w-5 rounded flex items-center justify-center border ${modulesSelected.reportCards ? 'bg-brand-600 border-brand-700 text-white' : 'border-gray-300'}`}>
                        {modulesSelected.reportCards && <Check className="h-3 w-3" />}
                      </div>
                    </div>

                    <div 
                      onClick={() => toggleModule('idBuilder')}
                      className={`p-3 border rounded-xl flex items-center justify-between cursor-pointer transition-colors ${
                        modulesSelected.idBuilder ? 'bg-brand-50 border-brand-500' : 'bg-white border-gray-200 hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center gap-3 text-left">
                        <Layers className={`h-5 w-5 ${modulesSelected.idBuilder ? 'text-brand-600' : 'text-gray-400'}`} />
                        <div>
                          <p className="font-bold text-slate-800">Bulk ID PVC card generator</p>
                          <p className="text-[10px] text-gray-400">Print modern card sizes featuring unique QR codes.</p>
                        </div>
                      </div>
                      <div className={`h-5 w-5 rounded flex items-center justify-center border ${modulesSelected.idBuilder ? 'bg-brand-600 border-brand-700 text-white' : 'border-gray-300'}`}>
                        {modulesSelected.idBuilder && <Check className="h-3 w-3" />}
                      </div>
                    </div>

                  </div>

                  <div className="space-y-3">
                    <div className="p-3 bg-teal-brand-50 border border-teal-brand-500/15 rounded-xl flex gap-2.5 text-[11px] text-teal-brand-600 font-medium">
                      <ShieldCheck className="h-4.5 w-4.5 text-teal-brand-500 shrink-0 mt-0.5" />
                      <span>
                        <strong>Workspace SLA: </strong> No subscription fees are charged until term 1 classes resume! Confirming will provision your secure cloud sandbox.
                      </span>
                    </div>

                    {/* NDPC Consent Choice */}
                    <div className="p-3 bg-slate-50 border border-slate-200/60 rounded-xl flex items-start gap-2.5">
                      <input 
                        id="checkbox-legal-consent"
                        type="checkbox"
                        required
                        checked={legalConsent}
                        onChange={(e) => setLegalConsent(e.target.checked)}
                        className="mt-0.5 h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500 cursor-pointer"
                      />
                      <label htmlFor="checkbox-legal-consent" className="text-[10px] sm:text-[11px] text-slate-500 font-semibold cursor-pointer select-none leading-relaxed">
                        I confirm that our institution consents to secure student record processing in absolute compliance with the **Nigeria Data Protection Act (NDPR/NDPA)** and Schooldom's Privacy Charter &amp; Terms of Service.
                      </label>
                    </div>
                  </div>

                  <div className="border-t border-gray-100 pt-5 flex items-center justify-between">
                    <button
                      id="wizard-btn-prev3"
                      type="button"
                      onClick={handlePrevStep}
                      className="px-5 py-3 rounded-xl border border-gray-200 text-gray-700 hover:bg-slate-50 font-semibold cursor-pointer"
                    >
                      Back
                    </button>
                    <button
                      id="wizard-btn-submit"
                      type="submit"
                      disabled={!legalConsent}
                      className="px-7 py-3 rounded-xl font-bold text-white bg-brand-600 hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed shadow-md transition-all cursor-pointer"
                    >
                      Provision Workspace &amp; Deploy
                    </button>
                  </div>
                </div>
              )}

            </form>
          )}
        </div>

      </div>
    </div>
  );
}
