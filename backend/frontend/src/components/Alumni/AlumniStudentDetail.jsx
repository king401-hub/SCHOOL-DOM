import { useEffect, useMemo, useRef, useState } from "react";
import { openPrintableDocument, requestJson } from "../../AppShared";
import {
  AlumniPill,
  ATTENDANCE_COLORS,
  EmptySection,
  FEE_STATUS_COLORS,
  REASON_COLORS,
  Value,
  formatDay,
  formatMoney,
} from "./alumniHelpers";

function Fact({ label, children }) {
  return (
    <div className="alumni-fact">
      <span className="fact-label">{label}</span>
      <span className="fact-value">
        <Value>{children}</Value>
      </span>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section className="alumni-section">
      <h4>{title}</h4>
      {children}
    </section>
  );
}

/** A section whose builder failed server-side reports the reason instead of
 *  silently rendering as empty - an archive that quietly drops history is worse
 *  than one that says it could not read it. */
function SectionError({ error }) {
  return <p className="form-feedback error">{error}</p>;
}

function ProfileSection({ profile }) {
  if (profile?.error) return <SectionError error={profile.error} />;
  const data = profile || {};
  return (
    <div className="alumni-facts">
      <Fact label="Full name">{data.name}</Fact>
      <Fact label="Student ID">{data.student_id}</Fact>
      <Fact label="Admission number">{data.admission_number}</Fact>
      <Fact label="Email">{data.email}</Fact>
      <Fact label="Phone">{data.phone}</Fact>
      <Fact label="Gender">{data.gender}</Fact>
      <Fact label="Date of birth">{data.date_of_birth ? formatDay(data.date_of_birth) : ""}</Fact>
      <Fact label="State of origin">{data.state_of_origin}</Fact>
      <Fact label="Local government">{data.local_government}</Fact>
      <Fact label="Home address">{data.home_address}</Fact>
      <Fact label="Student type">{data.student_type}</Fact>
      <Fact label="Class">{data.current_class}</Fact>
      <Fact label="Term">{data.current_term}</Fact>
    </div>
  );
}

function AdmissionSection({ admission }) {
  if (admission?.error) return <SectionError error={admission.error} />;
  const data = admission || {};
  const enrollments = data.enrollments || [];
  return (
    <>
      <div className="alumni-facts">
        <Fact label="Admission number">{data.admission_number}</Fact>
        <Fact label="Admission date">{data.admission_date ? formatDay(data.admission_date) : ""}</Fact>
        <Fact label="Student ID">{data.student_id}</Fact>
        <Fact label="Payment reference code">{data.payment_reference}</Fact>
        <Fact label="ID card generated">{data.id_card_generated_at ? formatDay(data.id_card_generated_at) : ""}</Fact>
        <Fact label="ID card viewed">{data.id_card_viewed_at ? formatDay(data.id_card_viewed_at) : ""}</Fact>
      </div>
      {enrollments.length > 0 ? (
        <div className="alumni-table-scroll">
          <table className="data-table">
            <thead>
              <tr><th>Class assigned</th><th>Enrolled by</th><th>Date</th></tr>
            </thead>
            <tbody>
              {enrollments.map((row) => (
                <tr key={row.id}>
                  <td><Value>{row.assigned_class}</Value></td>
                  <td><Value>{row.created_by}</Value></td>
                  <td>{formatDay(row.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  );
}

function GuardianSection({ guardians }) {
  if (guardians?.error) return <SectionError error={guardians.error} />;
  const list = guardians?.guardians || [];
  const accounts = guardians?.linked_parent_accounts || [];
  if (list.length === 0 && accounts.length === 0) return <EmptySection label="guardian details" />;
  return (
    <>
      {list.map((guardian, index) => (
        <div key={`${guardian.role}-${index}`} className="alumni-facts" style={{ marginBottom: 12 }}>
          <Fact label={`${guardian.role} name`}>{guardian.name}</Fact>
          <Fact label="Relationship">{guardian.relation}</Fact>
          <Fact label="Phone">{guardian.phone}</Fact>
          <Fact label="Email">{guardian.email}</Fact>
        </div>
      ))}
      {accounts.length > 0 ? (
        <div className="alumni-table-scroll">
          <table className="data-table">
            <thead>
              <tr><th>Linked parent account</th><th>Email</th><th>Phone</th><th>Occupation</th></tr>
            </thead>
            <tbody>
              {accounts.map((account) => (
                <tr key={account.id}>
                  <td>{account.name}</td>
                  <td><Value>{account.email}</Value></td>
                  <td><Value>{account.phone}</Value></td>
                  <td><Value>{account.occupation}</Value></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  );
}

function MedicalSection({ medical }) {
  if (medical?.error) return <SectionError error={medical.error} />;
  const data = medical || {};
  const hasAny = data.blood_group || data.allergies || data.medical_conditions || (data.disability && data.disability !== "no");
  if (!hasAny) return <EmptySection label="medical records" />;
  return (
    <div className="alumni-facts">
      <Fact label="Blood group">{data.blood_group}</Fact>
      <Fact label="Disability">{data.disability}</Fact>
      <Fact label="Allergies">{data.allergies}</Fact>
      <Fact label="Medical conditions">{data.medical_conditions}</Fact>
    </div>
  );
}

function AttendanceSection({ attendance }) {
  if (attendance?.error) return <SectionError error={attendance.error} />;
  const summary = attendance?.summary || {};
  const records = attendance?.records || [];
  if (records.length === 0) return <EmptySection label="attendance history" />;
  return (
    <>
      <div className="alumni-facts" style={{ marginBottom: 12 }}>
        <Fact label="Days recorded">{summary.total_days}</Fact>
        <Fact label="Present">{summary.present}</Fact>
        <Fact label="Late">{summary.late}</Fact>
        <Fact label="Absent">{summary.absent}</Fact>
        <Fact label="Attendance rate">{`${summary.attendance_rate ?? 0}%`}</Fact>
      </div>
      <div className="alumni-table-scroll">
        <table className="data-table">
          <thead>
            <tr><th>Date</th><th>Status</th><th>Class</th><th>Recorded by</th></tr>
          </thead>
          <tbody>
            {records.map((row, index) => (
              <tr key={`${row.date}-${index}`}>
                <td>{formatDay(row.date)}</td>
                <td><AlumniPill value={row.status} colorMap={ATTENDANCE_COLORS} /></td>
                <td><Value>{row.class_name}</Value></td>
                <td><Value>{row.noted_by}</Value></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function AcademicSection({ academics }) {
  if (academics?.error) return <SectionError error={academics.error} />;
  const cards = academics?.report_cards || [];
  const promotions = academics?.promotions || [];
  const broadsheet = academics?.broadsheet || {};

  return (
    <>
      <div className="alumni-facts" style={{ marginBottom: 14 }}>
        <Fact label="Class position">
          {broadsheet.class_position ? `${broadsheet.class_position} of ${broadsheet.class_size}` : ""}
        </Fact>
        <Fact label="Total score">{broadsheet.total_score}</Fact>
        <Fact label="Average score">{broadsheet.average_score}</Fact>
        <Fact label="Report cards on file">{cards.length}</Fact>
      </div>

      <h5>Report cards</h5>
      {cards.length === 0 ? (
        <EmptySection label="report cards" />
      ) : (
        cards.map((card, index) => (
          <div key={`${card.session}-${card.term}-${index}`} className="alumni-report-card">
            <header>
              <strong>{`${card.session} • ${card.term}`}</strong>
              <span>
                {card.class_name ? `${card.class_name} • ` : ""}
                {`${card.subject_count} subject(s) • Average ${card.average}%`}
              </span>
            </header>
            <div className="alumni-table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Subject</th><th>Score</th><th>Max</th><th>%</th><th>Grade</th><th>Remark</th><th>Teacher</th>
                  </tr>
                </thead>
                <tbody>
                  {(card.subjects || []).map((subject, subjectIndex) => (
                    <tr key={`${subject.subject}-${subjectIndex}`}>
                      <td>{subject.subject}</td>
                      <td>{subject.score}</td>
                      <td>{subject.max_score}</td>
                      <td><Value>{subject.percentage}</Value></td>
                      <td><Value>{subject.grade}</Value></td>
                      <td><Value>{subject.remark}</Value></td>
                      <td><Value>{subject.teacher}</Value></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {card.principal_remark ? (
              <p style={{ margin: "6px 0 0", fontSize: "0.85rem" }}>
                <strong>Principal / review remark:</strong> {card.principal_remark}
              </p>
            ) : null}
            {(card.teacher_remarks || []).length > 0 ? (
              <p style={{ margin: "4px 0 0", fontSize: "0.85rem" }}>
                <strong>Teacher remarks:</strong> {card.teacher_remarks.join(" | ")}
              </p>
            ) : null}
          </div>
        ))
      )}

      <h5>Promotion history</h5>
      {promotions.length === 0 ? (
        <EmptySection label="promotion history" />
      ) : (
        <div className="alumni-table-scroll">
          <table className="data-table">
            <thead>
              <tr><th>From</th><th>To</th><th>Session</th><th>Promoted by</th><th>Date</th></tr>
            </thead>
            <tbody>
              {promotions.map((row, index) => (
                <tr key={index}>
                  <td><Value>{row.from_class}</Value></td>
                  <td><Value>{row.to_class}</Value></td>
                  <td><Value>{row.to_session || row.from_session}</Value></td>
                  <td><Value>{row.promoted_by}</Value></td>
                  <td>{formatDay(row.promoted_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function ExamSection({ exams }) {
  if (exams?.error) return <SectionError error={exams.error} />;
  const rows = Array.isArray(exams) ? exams : [];
  if (rows.length === 0) return <EmptySection label="CBT exam results" />;
  return (
    <div className="alumni-table-scroll">
      <table className="data-table">
        <thead>
          <tr><th>Exam</th><th>Score</th><th>Total</th><th>%</th><th>Submitted</th><th>Date</th></tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              <td><Value>{row.exam}</Value></td>
              <td>{row.score}</td>
              <td>{row.total_points}</td>
              <td>{row.percentage}</td>
              <td>{row.is_submitted ? (row.auto_submitted ? "Auto-submitted" : "Yes") : "No"}</td>
              <td>{formatDay(row.started_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FinanceSection({ finance }) {
  if (finance?.error) return <SectionError error={finance.error} />;
  const summary = finance?.summary || {};
  const invoices = finance?.invoices || [];
  const payments = finance?.payments || [];
  const discounts = finance?.discounts || [];

  return (
    <>
      <div className="alumni-facts" style={{ marginBottom: 14 }}>
        <Fact label="Total billed">{formatMoney(summary.total_billed)}</Fact>
        <Fact label="Total paid">{formatMoney(summary.total_paid)}</Fact>
        <Fact label="Outstanding balance">{formatMoney(summary.outstanding)}</Fact>
        <Fact label="Invoices">{summary.invoice_count}</Fact>
        <Fact label="Payments">{summary.payment_count}</Fact>
      </div>

      <h5>Bills &amp; invoices</h5>
      {invoices.length === 0 ? (
        <EmptySection label="bills or invoices" />
      ) : (
        <div className="alumni-table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Title</th><th>Invoice no.</th><th>Amount</th><th>Paid</th><th>Outstanding</th><th>Status</th><th>Due</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((row) => (
                <tr key={row.id}>
                  <td>{row.title}</td>
                  <td><Value>{row.invoice_number}</Value></td>
                  <td>{formatMoney(row.amount)}</td>
                  <td>{formatMoney(row.amount_paid)}</td>
                  <td>{formatMoney(row.outstanding)}</td>
                  <td><AlumniPill value={row.status} colorMap={FEE_STATUS_COLORS} /></td>
                  <td>{formatDay(row.due_date)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h5>Payments &amp; receipts</h5>
      {payments.length === 0 ? (
        <EmptySection label="payments" />
      ) : (
        <div className="alumni-table-scroll">
          <table className="data-table">
            <thead>
              <tr><th>Applied to</th><th>Amount</th><th>Reference</th><th>Channel</th><th>Status</th><th>Date</th></tr>
            </thead>
            <tbody>
              {payments.map((row) => (
                <tr key={`${row.kind}-${row.id}`}>
                  <td><Value>{row.fee_title}</Value></td>
                  <td>{formatMoney(row.amount)}</td>
                  <td><Value>{row.reference}</Value></td>
                  <td><Value>{row.channel}</Value></td>
                  <td><Value>{row.status}</Value></td>
                  <td>{formatDay(row.paid_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h5>Discounts &amp; scholarships</h5>
      {discounts.length === 0 ? (
        <EmptySection label="discounts or scholarships" />
      ) : (
        <div className="alumni-table-scroll">
          <table className="data-table">
            <thead>
              <tr><th>Source</th><th>Type</th><th>Amount</th><th>Applied</th></tr>
            </thead>
            <tbody>
              {discounts.map((row, index) => (
                <tr key={index}>
                  <td>{row.source}</td>
                  <td>{row.type}</td>
                  <td>{formatMoney(row.amount)}</td>
                  <td>{formatDay(row.applied_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function ListSection({ rows, label, columns, renderRow }) {
  if (rows?.error) return <SectionError error={rows.error} />;
  const list = Array.isArray(rows) ? rows : [];
  if (list.length === 0) return <EmptySection label={label} />;
  return (
    <div className="alumni-table-scroll">
      <table className="data-table">
        <thead>
          <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
        </thead>
        <tbody>{list.map(renderRow)}</tbody>
      </table>
    </div>
  );
}

function TranscriptSection({ transcript }) {
  if (transcript?.error) return <SectionError error={transcript.error} />;
  const terms = transcript?.term_records || [];
  const cumulative = transcript?.cumulative || {};
  if (terms.length === 0) return <EmptySection label="transcript entries" />;
  return (
    <>
      <div className="alumni-facts" style={{ marginBottom: 12 }}>
        <Fact label="Cumulative average">{`${cumulative.average ?? 0}%`}</Fact>
        <Fact label="Cumulative GPA">{cumulative.gpa}</Fact>
        <Fact label="Overall grade">{cumulative.grade}</Fact>
        <Fact label="Subject records">{cumulative.subject_records}</Fact>
        <Fact label="Sessions">{(transcript.session_history || []).join(", ")}</Fact>
        <Fact label="Classes attended">{(transcript.class_history || []).join(", ")}</Fact>
      </div>
      <div className="alumni-table-scroll">
        <table className="data-table">
          <thead>
            <tr><th>Session</th><th>Term</th><th>Class</th><th>Subjects</th><th>Average</th><th>GPA</th><th>Grade</th></tr>
          </thead>
          <tbody>
            {terms.map((row, index) => (
              <tr key={index}>
                <td>{row.session}</td>
                <td>{row.term}</td>
                <td><Value>{row.class_name}</Value></td>
                <td>{(row.subjects || []).length}</td>
                <td>{`${row.average}%`}</td>
                <td>{row.gpa}</td>
                <td><Value>{row.grade}</Value></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function TestimonialSection({ testimonial }) {
  if (testimonial?.error) return <SectionError error={testimonial.error} />;
  const data = testimonial || {};
  return (
    <div className="alumni-facts">
      <Fact label="Class of admission">{data.class_of_admission}</Fact>
      <Fact label="Class of leaving">{data.class_of_leaving}</Fact>
      <Fact label="Date of leaving">{data.date_of_leaving ? formatDay(data.date_of_leaving) : ""}</Fact>
      <Fact label="Reason for leaving">{data.reason_for_leaving}</Fact>
      <Fact label="Educational attainment">{data.educational_attainment}</Fact>
      <Fact label="Subjects offered">{data.subjects_offered}</Fact>
      <Fact label="Co-curricular activities">{data.co_curricular_activities}</Fact>
      <Fact label="Prizes and honours">{data.prizes_and_honors}</Fact>
      <Fact label="Office held">{data.office_held}</Fact>
      <Fact label="Administrator remarks">{data.administrator_remarks}</Fact>
      <Fact label="Issued">{data.issue_date ? formatDay(data.issue_date) : ""}</Fact>
      <Fact label="Principal">{data.principal_name}</Fact>
    </div>
  );
}

export default function AlumniStudentDetail({ session, studentKey, onBack }) {
  const [student, setStudent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [printError, setPrintError] = useState("");
  const printRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setLoadError("");
      try {
        const result = await requestJson(
          session,
          "GET",
          `/api/alumni/students/${encodeURIComponent(studentKey)}/`,
        );
        if (!cancelled) setStudent(result.student || null);
      } catch (err) {
        if (!cancelled) setLoadError(err.message || "Unable to load this student's history.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [session, studentKey]);

  const identity = useMemo(() => {
    const archive = student?.archive || {};
    const profile = student?.profile || {};
    return {
      name: profile.name || archive.name || "Student",
      studentId: profile.student_id || archive.student_id || "",
      admissionNumber: profile.admission_number || archive.admission_number || "",
      className: profile.current_class || archive.class_name || "",
      photo: profile.profile_picture || archive.profile_picture || "",
      status: archive.status || "",
      reason: archive.archive_reason || "",
      reasonLabel: archive.archive_reason_display || "",
      archivedAt: archive.archived_at || "",
      isLive: Boolean(student?.is_live),
    };
  }, [student]);

  const handlePrint = () => {
    setPrintError("");
    try {
      openPrintableDocument(
        "alumni-student-history-print",
        `${identity.name} - Complete Student History`,
      );
    } catch (err) {
      setPrintError(err.message || "Unable to open the print preview.");
    }
  };

  if (loading) {
    return (
      <article className="app-panel">
        <p>Loading complete student history...</p>
      </article>
    );
  }

  if (loadError) {
    return (
      <article className="app-panel">
        <p className="form-feedback error">{loadError}</p>
        <button type="button" className="table-action" onClick={onBack}>Back to archive</button>
      </article>
    );
  }

  const schoolName = student?.school?.name || "";

  return (
    <article className="app-panel" id="alumni-student-history-print" ref={printRef}>
      <div className="table-actions-inline" style={{ marginBottom: 14 }}>
        <button type="button" className="table-action" onClick={onBack}>Back to archive</button>
        <button type="button" className="table-action" onClick={handlePrint}>Print / Save as PDF</button>
      </div>
      {printError ? <p className="form-feedback error">{printError}</p> : null}

      <div className="alumni-detail-head">
        {identity.photo ? (
          <img className="alumni-detail-photo" src={identity.photo} alt={identity.name} />
        ) : (
          <div className="alumni-detail-photo" />
        )}
        <div className="alumni-detail-identity">
          <h3>{identity.name}</h3>
          <p>{[identity.studentId, identity.admissionNumber].filter(Boolean).join(" • ")}</p>
          <p>{[identity.className, schoolName].filter(Boolean).join(" • ")}</p>
          <p>
            <AlumniPill value={identity.reason} colorMap={REASON_COLORS} />
            {identity.archivedAt ? (
              <span className="alumni-muted"> {`Left ${formatDay(identity.archivedAt)}`}</span>
            ) : null}
          </p>
        </div>
      </div>

      <p className="alumni-readonly-banner">
        This is a permanent read-only archive record. Nothing on this page can be edited.
        {identity.isLive
          ? " Their underlying records are still on the system, so this history is read live and stays current."
          : " Their records have been removed from the school, so this is the sealed snapshot taken at the time — it is retained permanently."}
      </p>

      <Section title="Personal information"><ProfileSection profile={student?.profile} /></Section>
      <Section title="Admission details"><AdmissionSection admission={student?.admission} /></Section>
      <Section title="Parent / guardian details"><GuardianSection guardians={student?.guardians} /></Section>
      <Section title="Medical records"><MedicalSection medical={student?.medical} /></Section>
      <Section title="Academic records"><AcademicSection academics={student?.academics} /></Section>
      <Section title="CBT exam results"><ExamSection exams={student?.exams} /></Section>
      <Section title="Transcript"><TranscriptSection transcript={student?.transcript} /></Section>
      <Section title="Attendance history"><AttendanceSection attendance={student?.attendance} /></Section>
      <Section title="Finance history"><FinanceSection finance={student?.finance} /></Section>

      <Section title="Disciplinary records">
        <ListSection
          rows={student?.discipline}
          label="disciplinary records"
          columns={["Date", "Incident", "Action taken", "Recorded by"]}
          renderRow={(row, index) => (
            <tr key={index}>
              <td>{formatDay(row.date)}</td>
              <td><Value>{row.incident}</Value></td>
              <td><Value>{row.action_taken}</Value></td>
              <td><Value>{row.recorded_by}</Value></td>
            </tr>
          )}
        />
      </Section>

      <Section title="Awards & honours">
        <ListSection
          rows={student?.awards}
          label="awards"
          columns={["Award", "Type", "Source"]}
          renderRow={(row, index) => (
            <tr key={index}>
              <td>{row.title}</td>
              <td><Value>{row.type}</Value></td>
              <td><Value>{row.source}</Value></td>
            </tr>
          )}
        />
      </Section>

      <Section title="Extracurricular activities">
        <ListSection
          rows={student?.activities}
          label="extracurricular activities"
          columns={["Activity", "Rating", "Source"]}
          renderRow={(row, index) => (
            <tr key={index}>
              <td>{row.name}</td>
              <td><Value>{row.stars}</Value></td>
              <td><Value>{row.source}</Value></td>
            </tr>
          )}
        />
      </Section>

      <Section title="Uploaded documents">
        <ListSection
          rows={student?.documents}
          label="uploaded documents"
          columns={["Document", "File"]}
          renderRow={(row, index) => (
            <tr key={index}>
              <td>{row.label}</td>
              <td>
                <a href={row.url} target="_blank" rel="noreferrer">Open</a>
              </td>
            </tr>
          )}
        />
      </Section>

      <Section title="Testimonial"><TestimonialSection testimonial={student?.testimonial} /></Section>

      <Section title="Official correspondence">
        <ListSection
          rows={student?.correspondence}
          label="correspondence"
          columns={["Subject", "From", "Date"]}
          renderRow={(row, index) => (
            <tr key={index}>
              <td><Value>{row.subject}</Value></td>
              <td><Value>{row.sender}</Value></td>
              <td>{formatDay(row.sent_at)}</td>
            </tr>
          )}
        />
      </Section>
    </article>
  );
}
