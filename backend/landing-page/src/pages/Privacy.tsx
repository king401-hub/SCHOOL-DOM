import { ArrowLeft } from 'lucide-react';

const SECTIONS: { title: string; body: JSX.Element }[] = [
  {
    title: 'Who We Are & Contact',
    body: (
      <>
        <p><strong className="text-white">Data Controller:</strong> Xcel Technologies Ltd</p>
        <p><strong className="text-white">Address:</strong> 256, Ikotun road, Lagos.</p>
        <p><strong className="text-white">Data Protection Officer/Contact:</strong> <a href="mailto:enquiry@schooldom.academy" className="text-green-400 hover:underline">enquiry@schooldom.academy</a></p>
        <p>For any privacy questions, requests, or complaints, contact us at <a href="mailto:enquiry@schooldom.academy" className="text-green-400 hover:underline">enquiry@schooldom.academy</a>.</p>
      </>
    ),
  },
  {
    title: 'Information We Collect',
    body: (
      <>
        <p>We collect only data necessary to provide SchoolDom services. Data is provided by School Owners/Administrators, Users, or collected automatically:</p>
        <ul>
          <li><strong className="text-white">School Information:</strong> School name, address, RC number, contact details, and subscription details provided by the School Owner during onboarding.</li>
          <li><strong className="text-white">User Account Information:</strong> Name, email address, phone number, role, password, and profile details provided during account creation or by the School Administrator.</li>
          <li><strong className="text-white">Student Information:</strong> Name, admission ID, date of birth, grade/class, gender, parent/guardian details, academic performance data, attendance records, and disciplinary reports. Provided by the School Administrator and processed on their behalf.</li>
          <li><strong className="text-white">Usage &amp; Device Data:</strong> IP address, device type, browser/OS, log data, pages viewed, features used, and access times. Collected automatically to improve performance and security.</li>
          <li><strong className="text-white">Communications:</strong> Messages, support tickets, and feedback you send us.</li>
          <li><strong className="text-white">Cookies &amp; Similar Tech:</strong> We use cookies for authentication, preferences, and analytics.</li>
        </ul>
      </>
    ),
  },
  {
    title: 'Lawful Basis & How We Use Your Information',
    body: (
      <>
        <p>Under GDPR/NDPR, we process data based on: contract, legitimate interest, consent, and legal obligation. We use your information to:</p>
        <ul>
          <li><strong className="text-white">Provide the Platform:</strong> Create accounts, enable features like CBT, fees, attendance, and reporting.</li>
          <li><strong className="text-white">Communicate:</strong> Send account updates, security alerts, and platform announcements. Marketing only with consent.</li>
          <li><strong className="text-white">Personalize Experience:</strong> Show relevant dashboards, content, and recommendations based on role and activity.</li>
          <li><strong className="text-white">Support Schools:</strong> Generate reports, enable parent-teacher communication, and fulfill requests from School Administrators.</li>
          <li><strong className="text-white">Improve &amp; Secure:</strong> Analyze usage, fix bugs, prevent fraud, and develop new features.</li>
          <li><strong className="text-white">Comply with Law:</strong> Respond to legal requests and meet NDPR/GDPR obligations.</li>
        </ul>
        <p>School Administrators are the "Data Controllers" for student/parent data. Xcel Technologies acts as "Data Processor" for that data.</p>
      </>
    ),
  },
  {
    title: 'Sharing & Disclosure',
    body: (
      <>
        <p>We do not sell personal data. We share data only as follows:</p>
        <ul>
          <li><strong className="text-white">School Administrators:</strong> School Owners/Admins can access User and Student data for their school only, as authorized by them.</li>
          <li><strong className="text-white">Service Providers:</strong> Trusted third parties who host data, send emails/SMS, process payments, or provide analytics. All are bound by Data Processing Agreements to protect data and only use it for our purposes.</li>
          <li><strong className="text-white">Legal Compliance:</strong> If required by Nigerian law, court order, or regulatory authority.</li>
          <li><strong className="text-white">Business Transfer:</strong> If Xcel Technologies is merged or acquired, data may transfer subject to this Policy.</li>
        </ul>
      </>
    ),
  },
  {
    title: 'Data Retention',
    body: (
      <>
        <p>We keep data only as long as needed for the purposes above, or as required by law.</p>
        <ul>
          <li>School account data: Retained while account is active + 2 years after closure for legal/audit needs.</li>
          <li>Student academic records: Retained per instructions from the School Administrator, in line with school policy and education laws.</li>
          <li>Logs &amp; analytics: Retained for 12 months, then anonymized.</li>
        </ul>
        <p>You can request deletion anytime. We will delete or anonymize data unless law requires retention.</p>
      </>
    ),
  },
  {
    title: 'Your Rights & Choices',
    body: (
      <>
        <p>Under NDPR and GDPR, you have the right to:</p>
        <ul>
          <li><strong className="text-white">Access:</strong> Request a copy of your personal data.</li>
          <li><strong className="text-white">Correction:</strong> Ask us to correct inaccurate or incomplete data.</li>
          <li><strong className="text-white">Deletion:</strong> Ask us to delete your data, subject to legal exceptions.</li>
          <li><strong className="text-white">Object/Restrict:</strong> Object to processing or request limits on how we use data.</li>
          <li><strong className="text-white">Portability:</strong> Receive your data in a structured, machine-readable format.</li>
          <li><strong className="text-white">Withdraw Consent:</strong> Where we rely on consent, you can withdraw it anytime.</li>
        </ul>
        <p>To exercise rights, email <a href="mailto:enquiry@schooldom.academy" className="text-green-400 hover:underline">enquiry@schooldom.academy</a>. We will respond within 30 days as required by NDPR.</p>
        <p>School Administrators should contact their school to access or delete student data, since schools control that data.</p>
      </>
    ),
  },
  {
    title: 'Security',
    body: (
      <>
        <p>We use encryption, access controls, firewalls, and regular audits to protect data. All data is stored on servers with SOC 2 compliant providers.</p>
        <p>No system is 100% secure. You're also responsible for keeping your password safe and not sharing login details.</p>
      </>
    ),
  },
  {
    title: "Children's Privacy",
    body: (
      <p>
        SchoolDom is designed for schools and will process personal data of children under 13 as provided by Schools. We process this data only on instruction from the School, which acts as Data Controller. Schools must ensure they have parental consent as required by law. We do not knowingly collect data directly from children.
      </p>
    ),
  },
  {
    title: 'Cookies & Tracking',
    body: (
      <p>
        We use essential cookies for login/security and optional cookies for analytics/performance. You can manage cookie preferences in your browser. Blocking essential cookies may break login.
      </p>
    ),
  },
  {
    title: 'International Data Transfers',
    body: (
      <p>
        If data is transferred outside Nigeria/EU, we ensure adequate protection via Standard Contractual Clauses or other NDPR/GDPR-approved mechanisms.
      </p>
    ),
  },
  {
    title: 'Changes to This Policy',
    body: (
      <p>
        We may update this Policy to reflect changes in law or features. We'll post the new version here with a "Last Updated" date and notify School Administrators by email for material changes. Continued use means acceptance.
      </p>
    ),
  },
  {
    title: 'Complaints',
    body: (
      <p>
        If you're unsatisfied with our response, you can lodge a complaint with the Nigeria Data Protection Commission at{' '}
        <a href="http://ndpc.gov.ng" target="_blank" rel="noreferrer" className="text-green-400 hover:underline">ndpc.gov.ng</a> or your local EU data authority.
      </p>
    ),
  },
];

export default function PrivacyPage() {
  return (
    <div className="min-h-screen pt-24 pb-20 px-4 relative">
      <div className="absolute top-0 inset-x-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(34,197,94,0.05) 0%, transparent 50%)' }} />

      <div className="max-w-3xl mx-auto">
        <a href="/" className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-300 text-sm mb-8 transition-colors">
          <ArrowLeft className="h-4 w-4" /> Back to home
        </a>

        <div className="text-center mb-12">
          <span className="badge badge-green mb-4">Legal</span>
          <h1 className="font-display font-black text-4xl sm:text-5xl text-white mb-4">
            Privacy <span className="gradient-text">Policy</span>
          </h1>
          <p className="text-slate-400">Last Updated: July 2026</p>
        </div>

        <div className="rounded-2xl p-6 sd-card mb-6">
          <p className="text-slate-400 text-sm leading-relaxed">
            This Privacy Policy ("Policy") explains how we collect, use, disclose, and protect information in connection with the SchoolDom platform ("Platform"), including the website, web application, and mobile applications for school administrators, teachers, students, and parents (collectively, "Applications"). By accessing or using the Platform, you agree to this Policy.
          </p>
        </div>

        <div className="space-y-6">
          {SECTIONS.map((section) => (
            <div key={section.title} className="rounded-2xl p-6 sd-card">
              <h2 className="font-bold text-white text-lg mb-3">{section.title}</h2>
              <div className="text-slate-400 text-sm leading-relaxed space-y-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-2 [&_li]:marker:text-green-500">
                {section.body}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-10 rounded-2xl p-8 text-center"
          style={{ background: 'linear-gradient(135deg, rgba(34,197,94,0.07), rgba(14,165,233,0.07))', border: '1px solid rgba(34,197,94,0.15)' }}>
          <h3 className="font-display font-black text-white text-xl mb-2">Questions about your data?</h3>
          <p className="text-slate-400 text-sm mb-5">Reach our Data Protection Officer at enquiry@schooldom.academy.</p>
          <a href="/#/contact" className="btn-primary inline-flex">
            Contact Us <ArrowLeft className="h-4 w-4 rotate-180" />
          </a>
        </div>
      </div>
    </div>
  );
}
