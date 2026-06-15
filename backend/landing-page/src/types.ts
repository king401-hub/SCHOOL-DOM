export interface SolutionFeature {
  id: string;
  title: string;
  shortDescription: string;
  description: string;
  category: 'academic' | 'operations' | 'finance' | 'students';
  icon: string;
  benefits: string[];
  specs?: string;
  demoComponent?: string;
}

export interface Testimonial {
  id: string;
  schoolName: string;
  type: 'K12' | 'Higher Ed' | 'Vocational' | 'Multi-School Group';
  principalName: string;
  role: string;
  location: string;
  quote: string;
  activeStudents: number;
}

export interface InteractiveFeature {
  id: string;
  name: string;
  badge: string;
}

export interface OnboardingForm {
  schoolName: string;
  primaryContact: string;
  phone: string;
  email: string;
  schoolType: 'K12' | 'Non-K12';
  estimatedStudents: number;
  isGroupOfSchools: boolean;
  notes?: string;
}
