import React, { useState } from 'react';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialMode: 'login' | 'register';
}

export default function AuthModal({ isOpen, onClose, initialMode }: AuthModalProps) {
  const [mode, setMode] = useState<'login' | 'register'>(initialMode);
  
  // Helper to read the Django CSRF cookie value for form submission safety
  const getCsrfToken = () => {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; csrftoken=`);
    if (parts.length === 2) return parts.pop()?.split(';').shift();
    return '';
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md antialiased text-slate-100">
      {/* Modal Card Box Container */}
      <div className="relative w-full max-w-md p-6 overflow-hidden bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl shadow-black/50 transition-all">
        
        {/* Close Button */}
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white transition-colors text-xl font-medium focus:outline-none"
        >
          ✕
        </button>

        {/* Modal Branding Header */}
        <div className="text-center mb-6">
          <div className="mx-auto h-12 w-12 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/10">
            <span className="text-xl font-black text-white tracking-tighter">SD</span>
          </div>
          <h3 className="mt-4 text-2xl font-bold tracking-tight text-white">
            {mode === 'register' ? 'Onboard Your School' : 'Access Admin Dashboard'}
          </h3>
          <p className="mt-1.5 text-sm text-slate-400">
            {mode === 'register' ? 'Already managing a system portal? ' : 'New institution administrator? '}
            <button 
              onClick={() => setMode(mode === 'register' ? 'login' : 'register')}
              className="font-semibold text-blue-400 hover:text-blue-300 transition-colors focus:outline-none"
            >
              {mode === 'register' ? 'Sign In' : 'Register Here'}
            </button>
          </p>
        </div>

        {/* Unified Standard Post Form matching your Django structure views */}
        <form className="space-y-4" method="POST" action={mode === 'register' ? '/register/' : '/login/'}>
          {/* Hidden input supplying the vital secure Django validation check token */}
          <input type="hidden" name="csrfmiddlewaretoken" value={getCsrfToken()} />

          {mode === 'register' && (
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider">Proprietor / Full Name</label>
              <input 
                name="full_name" 
                type="text" 
                required 
                placeholder="e.g. Dr. John Doe"
                className="mt-1 block w-full px-3.5 py-2.5 bg-slate-950/60 border border-slate-800 rounded-xl text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-all sm:text-sm"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider">
              {mode === 'register' ? 'Email Address' : 'Username or Email'}
            </label>
            <input 
              name="username" 
              type={mode === 'register' ? 'email' : 'text'} 
              required 
              placeholder={mode === 'register' ? 'admin@school.com' : 'Enter account credentials'}
              className="mt-1 block w-full px-3.5 py-2.5 bg-slate-950/60 border border-slate-800 rounded-xl text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-all sm:text-sm"
            />
            {mode === 'register' && (
              <input type="hidden" name="email" value="" ref={(el) => { if (el) el.value = (el.previousSibling as HTMLInputElement)?.value || ''; }} />
            )}
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider">Account Password</label>
            <input 
              name="password" 
              type="password" 
              required 
              placeholder="••••••••"
              className="mt-1 block w-full px-3.5 py-2.5 bg-slate-950/60 border border-slate-800 rounded-xl text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-all sm:text-sm"
            />
          </div>

          {mode === 'register' && (
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider">Administrative Access Level</label>
              <select 
                name="role" 
                required
                className="mt-1 block w-full px-3.5 py-2.5 bg-slate-950/60 border border-slate-800 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-all sm:text-sm appearance-none"
              >
                <option value="school_superadmin">School Superadmin (Proprietor / Owner)</option>
                <option value="school_admin">School Admin (Principal / Registrar)</option>
              </select>
            </div>
          )}

          <div>
            <button 
              type="submit" 
              className="w-full flex justify-center py-3 px-4 border border-transparent rounded-xl shadow-lg shadow-blue-600/10 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-500 active:bg-blue-700 focus:outline-none transition-all cursor-pointer"
            >
              {mode === 'register' ? 'Complete Onboarding setup' : 'Establish Session'}
            </button>
          </div>
        </form>

      </div>
    </div>
  );
}
