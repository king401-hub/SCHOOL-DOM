"""
Tool implementations for the Schooldom Secretary AI agent.

Each method is called by the agent loop after the LLM requests a tool.
The `tenant` and `requesting_user` are injected from the authenticated request
server-side — the LLM never sees or supplies tenant identifiers.
"""
import json
import logging
import secrets
from datetime import date, datetime, timedelta, timezone

from django.conf import settings
from django.utils import timezone as dj_timezone

logger = logging.getLogger(__name__)

# Keep these labels aligned with frontend/src/appConstants.js. The assistant
# receives natural-language page names, while the React app needs exact routes.
NAVIGATION_ROUTES = {
    "dashboard": "/dashboard", "home": "/dashboard", "student": "/students",
    "attendance register": "/attendance", "school settings": "/settings",
    "dashboard page": "/dashboard", "performance analytics": "/performance-heatmap",
    "analytics": "/performance-heatmap", "performance heatmap": "/performance-heatmap",
    "students": "/students", "student management": "/students", "alumni": "/alumni",
    "parents": "/parents", "parent directory": "/parents", "teachers": "/teachers",
    "non teaching staff": "/non-teaching-staff", "non-teaching staff": "/non-teaching-staff",
    "staff": "/non-teaching-staff", "classes": "/classes", "subjects": "/classes",
    "attendance": "/attendance", "cbt": "/exams", "cbt exams": "/exams", "exams": "/exams",
    "timetable": "/timetables", "timetables": "/timetables", "results": "/results",
    "report cards": "/results", "reports": "/results", "finance": "/finance",
    "fee management": "/finance", "fees": "/finance", "expenses": "/expenses",
    "sms wallet": "/sms-wallet", "hr": "/hr/activity", "human resources": "/hr/activity",
    "hr management": "/hr/activity", "payroll": "/hr-self-service",
    "loan application": "/loan-application", "id cards": "/id-cards", "documents": "/documents",
    "transcripts": "/documents", "testimonials": "/documents",
    "document customization": "/document-customization", "inventory": "/inventory",
    "database import": "/database-import", "messages": "/messages", "settings": "/settings",
    "license": "/license", "compliance": "/compliance", "service agreement": "/service-agreement",
}


def resolve_navigation_page(page: str) -> tuple[str, str]:
    """Resolve a page label or natural-language navigation request to a route."""
    page_key = " ".join(str(page or "").lower().replace("_", " ").split())
    if page_key in NAVIGATION_ROUTES:
        return page_key, NAVIGATION_ROUTES[page_key]
    for label, route in NAVIGATION_ROUTES.items():
        if page_key == route:
            return label, route
    for label in sorted(NAVIGATION_ROUTES, key=len, reverse=True):
        if label in page_key:
            return label, NAVIGATION_ROUTES[label]
    return "dashboard", NAVIGATION_ROUTES["dashboard"]

# ── Tool schema definitions (fed to Ollama as the `tools` list) ──────────────
# tenant_id is intentionally omitted — it is injected server-side for security.

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "create_student",
            "description": "Register a new student with their guardian's contact info, so they immediately show up correctly in rosters, fee records, and bulk messages. Need: name, class_name (a real one - call list_classes first if unsure), guardian_name, phone (the guardian's phone). guardian_relation and email are optional.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Student full name"},
                    "phone": {"type": "string", "description": "Guardian/parent phone E.164 e.g. +2348012345678 - this is what fee reminders and bulk messages go to"},
                    "class_name": {"type": "string", "description": "Class e.g. JSS1, SS2A - must be a real class name"},
                    "guardian_name": {"type": "string", "description": "Parent or guardian's full name"},
                    "guardian_relation": {"type": "string", "description": "Guardian's relation to the student, e.g. Mother, Father, Uncle (optional, defaults to 'Guardian')"},
                    "email": {"type": "string", "description": "Student's own email (optional - a placeholder is generated if omitted)"},
                },
                "required": ["name", "phone", "class_name", "guardian_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_teacher",
            "description": "Register a new teacher. Only name, phone, and email are needed - everything else (qualification, specialization, emergency contact) is filled with a placeholder the admin can complete later from the Staff page, same as the admin \"Add Teacher\" form already does when those fields are left blank.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Teacher full name"},
                    "phone": {"type": "string", "description": "Teacher's phone E.164 e.g. +2348012345678"},
                    "email": {"type": "string", "description": "Teacher's email - used to sign in"},
                },
                "required": ["name", "phone", "email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_timetable",
            "description": "Auto-generate a timetable draft for the selected class and term.",
            "parameters": {
                "type": "object",
                "properties": {
                    "class_name": {"type": "string", "description": "Class like SS2A or JSS3"},
                    "term": {"type": "string", "description": "Term name such as First Term"},
                },
                "required": ["class_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report_cards",
            "description": "Generate a report card pack for a class or whole school for a selected term.",
            "parameters": {
                "type": "object",
                "properties": {
                    "class_name": {"type": "string", "description": "Class name or all"},
                    "term": {"type": "string", "description": "Academic term"},
                },
                "required": ["class_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fee_status",
            "description": "Check fee collection status for the whole school or a selected class.",
            "parameters": {
                "type": "object",
                "properties": {
                    "class_name": {"type": "string", "description": "Optional class filter"},
                    "scope": {"type": "string", "description": "school or class"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_cbt_exam",
            "description": "Create a CBT exam by pulling real questions from the question bank for that subject - a real, existing Subject name (call list_classes-style lookups or ask the admin if unsure). Fails with NOT_FOUND if the subject doesn't exist, or NO_QUESTIONS if the bank has nothing for it yet - never fabricates questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "A real subject name that already exists, e.g. Mathematics, Biology"},
                    "class_name": {"type": "string", "description": "Class target like SS2 or JSS3"},
                    "question_count": {"type": "integer", "description": "Number of questions wanted - fewer may be used if the bank has less than this available"},
                    "time_limit_minutes": {"type": "integer", "description": "Exam duration in minutes"},
                },
                "required": ["subject", "class_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_class",
            "description": "Create a new class in the school, e.g. SS2A or JSS1B.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Class name, e.g. SS2, JSS1, Grade 9"},
                    "section": {"type": "string", "description": "Optional arm/section, e.g. A, B (omit if the school doesn't use arms)"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "navigate_to_page",
            "description": "Open a target SchoolDom page or section for the admin user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {"type": "string", "description": "Page label like fee management, timetable, reports, cbt"},
                },
                "required": ["page"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_attendance",
            "description": "Mark one student's attendance. Call get_student_list first for bulk class marking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "string", "description": "Student unique ID"},
                    "date": {"type": "string", "description": "Date YYYY-MM-DD, default today"},
                    "status": {"type": "string", "enum": ["present", "absent", "late", "excused"]},
                },
                "required": ["student_id", "date", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_exam",
            "description": "Create and schedule an exam. Returns exam_id for publish_cbt_exam.",
            "parameters": {
                "type": "object",
                "properties": {
                    "exam_name": {"type": "string", "description": "Exam title"},
                    "class_name": {"type": "string", "description": "Target class e.g. SS2"},
                    "date": {"type": "string", "description": "Exam date YYYY-MM-DD"},
                    "duration_minutes": {"type": "integer", "description": "Duration in minutes, default 60"},
                    "subject": {"type": "string", "description": "Subject name (optional)"},
                },
                "required": ["exam_name", "class_name", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp_message",
            "description": "Send WhatsApp to one phone. Try this before send_sms. Max 500 chars.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_phone": {"type": "string", "description": "Phone E.164 e.g. +2348023456789"},
                    "message_body": {"type": "string", "description": "Message text, max 500 chars"},
                },
                "required": ["to_phone", "message_body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_sms",
            "description": "Send SMS fallback. message_body must be 160 chars or less. No emojis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_phone": {"type": "string", "description": "Phone E.164"},
                    "message_body": {"type": "string", "description": "SMS text, strictly ≤160 chars"},
                },
                "required": ["to_phone", "message_body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_student_list",
            "description": "Get students in a class. Returns student IDs and parent phones.",
            "parameters": {
                "type": "object",
                "properties": {
                    "class_name": {"type": "string", "description": "Class e.g. SS1A. Use ALL for whole school."},
                    "include_inactive": {"type": "boolean", "description": "Include withdrawn students, default false"},
                },
                "required": ["class_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "publish_cbt_exam",
            "description": "Publish an exam as live CBT. Returns a link to send to parents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "exam_id": {"type": "string", "description": "Exam ID from schedule_exam"},
                    "access_window_hours": {"type": "integer", "description": "Hours link stays active, default 24"},
                },
                "required": ["exam_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "count_students",
            "description": "Get the total number of students in the school, or count by specific class.",
            "parameters": {
                "type": "object",
                "properties": {
                    "class_name": {"type": "string", "description": "Optional: specific class name like SS2A. If omitted, counts all students."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "count_classes",
            "description": "Get the total number of classes in the school.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_classes",
            "description": "List every class in the school by its exact name (e.g. SS2A, JSS1B), with each class's current student count. Call this whenever you need a real class name before calling a class-specific tool (roster, fee status, bulk message) and the admin didn't spell one out exactly, or asked to see the classes themselves.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_student_details",
            "description": "Get complete student profile including personal info, class, and contact details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "string", "description": "Student ID or name to search"}
                },
                "required": ["student_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_class_roster",
            "description": "Get complete class roster with student names, IDs, and contact info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "class_name": {"type": "string", "description": "Class name like SS2A"}
                },
                "required": ["class_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_student_fee_balance",
            "description": "Get fee balance for a student, including total due, paid, and outstanding amount.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "string", "description": "Student ID or name"}
                },
                "required": ["student_id"]
            }
        }
    },
]


# ── Tool executor class ───────────────────────────────────────────────────────

class SecretaryTools:
    """
    All tool implementations, pre-bound to the authenticated tenant and user.
    Called by the agent loop — never exposed directly to the LLM.
    """

    def __init__(self, tenant, requesting_user):
        self.tenant = tenant
        self.requesting_user = requesting_user
        # Lazy import to avoid circular imports at module load time
        self._User = None
        self._Class = None
        self._Exam = None
        self._StudentAttendance = None
        self._Subject = None

    # ── Model accessors ──────────────────────────────────────────────────────

    @property
    def User(self):
        if self._User is None:
            from django.contrib.auth import get_user_model
            self._User = get_user_model()
        return self._User

    @property
    def Class(self):
        if self._Class is None:
            from academic.models import Class
            self._Class = Class
        return self._Class

    @property
    def Exam(self):
        if self._Exam is None:
            from exams.models import Exam
            self._Exam = Exam
        return self._Exam

    @property
    def StudentAttendance(self):
        if self._StudentAttendance is None:
            from ai_secretary.models import StudentAttendance
            self._StudentAttendance = StudentAttendance
        return self._StudentAttendance

    @property
    def Subject(self):
        if self._Subject is None:
            from academic.models import Subject
            self._Subject = Subject
        return self._Subject

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _normalize_phone(self, phone: str) -> str:
        """Convert 0801... → +2348... E.164 format."""
        phone = phone.strip().replace(" ", "").replace("-", "")
        if phone.startswith("0") and len(phone) == 11:
            phone = "+234" + phone[1:]
        elif phone.startswith("234") and not phone.startswith("+"):
            phone = "+" + phone
        return phone

    def _get_school_name(self) -> str:
        return getattr(self.tenant, "name", "Schooldom School")

    def _get_class(self, class_name: str):
        """Return Class object or None; tenant-aware.

        academic.Class is keyed to the LEGACY tenants.Tenant, not
        core.SchoolTenant (self.tenant) - filtering on self.tenant directly
        compares two different ID spaces and silently returns nothing for
        real production data. Must resolve via _get_legacy_tenant() first,
        same bridge create_cbt_exam already uses correctly."""
        try:
            legacy_tenant = self._get_legacy_tenant()
            if legacy_tenant is None:
                return None
            return self.Class.objects.filter(
                tenant=legacy_tenant,
                name__iexact=class_name.strip(),
            ).first()
        except Exception:
            return None

    def _get_subject(self, subject_name: str):
        """Same legacy-tenant bridge _get_class uses - academic.Subject is
        also keyed to tenants.Tenant, not core.SchoolTenant."""
        try:
            legacy_tenant = self._get_legacy_tenant()
            if legacy_tenant is None:
                return None
            return self.Subject.objects.filter(
                tenant=legacy_tenant,
                name__iexact=subject_name.strip(),
            ).first()
        except Exception:
            return None

    def _active_term_and_year(self):
        """Whichever Term/AcademicYear is currently active for the requesting
        user's school - same source of truth exams created from the admin
        Exam Builder are tagged with, so a Phoenix-created exam is filterable
        by term exactly like a manually-built one."""
        try:
            from users.app_views import _active_term, _active_academic_year
            return _active_term(self.requesting_user), _active_academic_year(self.requesting_user)
        except Exception:
            logger.debug("Active term/year lookup failed for user %s", getattr(self.requesting_user, 'id', None), exc_info=True)
            return None, None

    def _get_legacy_tenant(self):
        """Resolve the older tenants.Tenant object expected by legacy academic/exam models."""
        try:
            from users.models import resolve_legacy_tenant_for_school
            legacy_tenant = resolve_legacy_tenant_for_school(self.tenant)
            if legacy_tenant is not None:
                return legacy_tenant
        except Exception:
            logger.debug("Legacy tenant lookup failed for school %s", getattr(self.tenant, 'id', None), exc_info=True)
        return None

    # ── Tool 1: create_student ───────────────────────────────────────────────

    def create_student(
        self, name: str, phone: str, class_name: str, guardian_name: str,
        guardian_relation: str = "Guardian", email: str = "",
    ) -> dict:
        """Creates both the User AND a StudentProfile - an earlier draft of
        this tool only created a bare User (role="student") with no profile
        at all, which silently excluded every AI-registered student from
        rosters, fee records, and bulk parent messages (StudentProfile is
        what those actually query - see get_class_roster/get_fee_status/
        send_bulk_parent_message). Follows the same student_id/admission_number
        convention the real "Add Student" admin form uses (users/app_views.py)
        so these students are indistinguishable from ones added there."""
        try:
            from users.models import StudentProfile, generate_short_student_id

            guardian_name = (guardian_name or "").strip()
            if not guardian_name:
                return {"status": "error", "error_code": "BAD_ARGS", "message": "A guardian name is required to register a student."}

            guardian_phone = self._normalize_phone(phone)
            name_parts = name.strip().split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            class_obj = self._get_class(class_name)
            if class_obj is None:
                return {"status": "error", "error_code": "NOT_FOUND", "message": f"Class '{class_name}' not found."}

            base_email = email.strip() if email else f"{first_name.lower()}.{last_name.lower()}.{secrets.token_hex(3)}@student.{self.tenant.schema_name}.schooldom.local"

            user = self.User(
                email=base_email,
                first_name=first_name,
                last_name=last_name,
                role="student",
                tenant=self.tenant,
                is_active=True,
                is_verified=False,
            )
            user.set_unusable_password()
            user.save()

            student_code = generate_short_student_id(user.id.hex, self.tenant)
            admission_number = f"ADM{dj_timezone.now().strftime('%Y%m%d')}{user.id.hex[:4].upper()}"
            StudentProfile.objects.create(
                user=user,
                student_id=student_code,
                admission_number=admission_number,
                admission_date=dj_timezone.localdate(),
                current_class=class_obj,
                guardian_name=guardian_name,
                guardian_phone=guardian_phone,
                guardian_relation=(guardian_relation or "Guardian").strip(),
            )

            return {
                "status": "success",
                "student_id": str(user.id),
                "name": user.get_full_name(),
                "class": class_name,
                "guardian_phone": guardian_phone,
                "message": f"{user.get_full_name()} registered successfully in {class_name}.",
            }
        except Exception as exc:
            logger.exception("create_student failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    def create_teacher(self, name: str, phone: str, email: str) -> dict:
        """Only name/phone/email are asked for - everything else TeacherProfile
        requires (qualification, specialization, emergency contact) gets the
        same "Not specified"/"Not provided" placeholder the real admin "Add
        Teacher" form already falls back to when those fields are left blank
        (users/app_views.py) - the admin can fill them in properly later from
        the Staff page. Not in TOOL_SCHEMAS' create_student mould of requiring
        full data; this one is deliberately minimal per how it's actually used."""
        try:
            from users.models import TeacherProfile, generate_short_teacher_id

            email = (email or "").strip()
            if not email:
                return {"status": "error", "error_code": "BAD_ARGS", "message": "An email is required to register a teacher."}
            if self.User.objects.filter(email__iexact=email).exists():
                return {"status": "error", "error_code": "DUPLICATE", "message": f"A user with email {email} already exists."}

            phone = self._normalize_phone(phone)
            name_parts = name.strip().split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            user = self.User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                role="teacher",
                tenant=self.tenant,
                is_active=True,
                is_verified=False,
            )
            user.set_unusable_password()
            user.save()

            employee_id = generate_short_teacher_id(user.id.hex, self.tenant)
            TeacherProfile.objects.create(
                user=user,
                employee_id=employee_id,
                qualification="Not specified",
                specialization="Not specified",
                hire_date=dj_timezone.localdate(),
                emergency_contact_name="Not provided",
                emergency_contact_phone="Not provided",
                emergency_contact_relation="Not provided",
            )

            return {
                "status": "success",
                "teacher_id": str(user.id),
                "name": user.get_full_name(),
                "employee_id": employee_id,
                "message": f"{user.get_full_name()} registered as a teacher (employee ID {employee_id}). Qualification and emergency contact can be filled in later from the Staff page.",
            }
        except Exception as exc:
            logger.exception("create_teacher failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    # ── Tool 2: mark_attendance ──────────────────────────────────────────────

    def mark_attendance(self, student_id: str, date: str, status: str) -> dict:
        try:
            try:
                attendance_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                return {"status": "error", "error_code": "BAD_DATE", "message": "Date must be YYYY-MM-DD."}

            try:
                student = self.User.objects.get(id=student_id, tenant=self.tenant, role="student")
            except self.User.DoesNotExist:
                return {"status": "error", "error_code": "NOT_FOUND", "message": "Student not found."}

            obj, created = self.StudentAttendance.objects.update_or_create(
                student=student,
                date=attendance_date,
                tenant=self.tenant,
                defaults={"status": status, "marked_by": self.requesting_user},
            )
            return {
                "status": "success",
                "record_id": str(obj.id),
                "student_id": student_id,
                "student_name": student.get_full_name(),
                "date": str(attendance_date),
                "status_marked": status,
                "created": created,
            }
        except Exception as exc:
            logger.exception("mark_attendance failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    # ── Phase 1 tool 1: generate_timetable ───────────────────────────────────

    def generate_timetable(self, class_name: str, term: str = "First Term") -> dict:
        """Delegates to the same slot-filling core the admin "Generate"
        button uses (users/app_views.py::_generate_timetable_core) - one
        implementation, not a second guess at what "generated" means. An
        earlier draft of this tool always claimed "10 entries created"
        without touching the database."""
        try:
            class_label = (class_name or "").strip()
            if not class_label:
                return {"status": "error", "error_code": "BAD_ARGS", "message": "A class name is required to generate a timetable."}
            class_obj = self._get_class(class_label)
            if class_obj is None:
                return {"status": "error", "error_code": "NOT_FOUND", "message": f"Class '{class_label}' not found."}

            from users.app_views import _generate_timetable_core
            result = _generate_timetable_core(self.requesting_user, class_ids=[class_obj.id])
            if not result.get("success"):
                return {"status": "error", "error_code": "NOT_CONFIGURED", "message": result.get("message") or "Could not generate a timetable."}

            return {
                "status": "success",
                "message": result.get("message", ""),
                "class_name": class_label,
                "term": term,
                "entries_created": result.get("created_count", 0),
                "skipped_existing_count": result.get("skipped_existing_count", 0),
                "route": "/timetables",
            }
        except Exception as exc:
            logger.exception("generate_timetable failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    # ── Phase 1 tool 2: generate_report_cards ────────────────────────────────

    def generate_report_cards(self, class_name: str = "all", term: str = "First Term") -> dict:
        """There is no batch "report card pack" feature to trigger, so the
        honest version of this tool is a readiness check: how many students
        in the class already have published results for the active term,
        reusing the same _class_broadsheet the Results page's broadsheet
        export already relies on - not a fabricated "1 record ready"."""
        try:
            target = (class_name or "").strip()
            if not target or target.lower() == "all":
                return {
                    "status": "error",
                    "error_code": "BAD_ARGS",
                    "message": "A specific class name is required to check report card readiness, e.g. 'SS2A'.",
                }
            class_obj = self._get_class(target)
            if class_obj is None:
                return {"status": "error", "error_code": "NOT_FOUND", "message": f"Class '{target}' not found."}

            active_term, _active_year = self._active_term_and_year()
            if active_term is None:
                return {"status": "error", "error_code": "NOT_CONFIGURED", "message": "No active term is configured yet."}

            from users.app_views import _class_broadsheet
            broadsheet = _class_broadsheet(class_obj, active_term, self.requesting_user)
            rows = broadsheet.get("rows", [])
            class_size = broadsheet.get("class_size", 0)
            ready_count = sum(1 for row in rows if row.get("scores"))
            pending_count = class_size - ready_count

            if class_size == 0:
                message = f"{target} has no students yet, so there is nothing to report on."
            elif ready_count == class_size:
                message = f"All {class_size} students in {target} have published results for {active_term.name} - report cards are ready."
            else:
                message = (
                    f"{ready_count} of {class_size} students in {target} have published results for "
                    f"{active_term.name}; {pending_count} still need results published first."
                )

            return {
                "status": "success",
                "message": message,
                "class_name": target,
                "term": active_term.name,
                "class_size": class_size,
                "ready_count": ready_count,
                "pending_count": pending_count,
                "route": "/results",
            }
        except Exception as exc:
            logger.exception("generate_report_cards failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    # ── Phase 1 tool 3: get_fee_status ────────────────────────────────────────

    def get_fee_status(self, class_name: str = None, scope: str = "school") -> dict:
        """Real fee collection numbers from finance.SchoolFee - an earlier
        draft of this tool always reported "82% collected, 18% pending"
        regardless of scope or actual data, same shape of bug
        get_student_fee_balance was already fixed for."""
        try:
            from django.db.models import Sum

            from finance.models import SchoolFee
            from users.models import StudentProfile

            qs = StudentProfile.objects.filter(user__tenant=self.tenant, user__role="student", user__is_active=True)
            class_label = (class_name or "").strip()
            if class_label:
                class_obj = self._get_class(class_label)
                if class_obj is None:
                    return {"status": "error", "error_code": "NOT_FOUND", "message": f"Class '{class_label}' not found."}
                qs = qs.filter(current_class=class_obj)

            fees = SchoolFee.objects.filter(student__in=qs)
            total_due = fees.aggregate(total=Sum("amount"))["total"] or 0
            total_paid = fees.filter(status=SchoolFee.STATUS_PAID).aggregate(total=Sum("amount"))["total"] or 0
            collected_percent = round(float(total_paid) / float(total_due) * 100, 1) if total_due else 0.0
            pending_percent = round(100 - collected_percent, 1) if total_due else 0.0
            target = class_label or "the school"

            summary = (
                f"{target.title()} fee collection: {collected_percent}% collected "
                f"(₦{float(total_paid):,.0f} of ₦{float(total_due):,.0f})."
                if total_due
                else f"No fee records found for {target} yet."
            )
            return {
                "status": "success",
                "summary": summary,
                "scope": "class" if class_label else "school",
                "class_name": class_label or None,
                "collected_percent": collected_percent,
                "pending_percent": pending_percent,
                "total_due": float(total_due),
                "total_paid": float(total_paid),
                "route": "/finance",
            }
        except Exception as exc:
            logger.exception("get_fee_status failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    # ── Phase 1 tool 4: create_cbt_exam ──────────────────────────────────────

    def create_cbt_exam(
        self,
        subject: str,
        class_name: str,
        question_count: int = 50,
        time_limit_minutes: int = 60,
    ) -> dict:
        """Pulls real questions from the question bank (exams.QuestionBank/
        Question) and attaches them to the exam - an earlier draft created
        an empty exam shell and just claimed "{question_count} questions" in
        its message regardless of whether any existed, same shape of bug
        create_student had for StudentProfile."""
        try:
            from django.db.models import Q

            from exams.models import Question, QuestionBank

            subject_name = (subject or "").strip()
            class_label = (class_name or "SS2").strip()
            if not subject_name:
                return {"status": "error", "error_code": "BAD_ARGS", "message": "A subject is required to create a CBT exam."}
            if question_count <= 0:
                return {"status": "error", "error_code": "BAD_ARGS", "message": "Question count must be greater than zero."}

            legacy_tenant = self._get_legacy_tenant()
            subject_obj = self._get_subject(subject_name)
            if subject_obj is None:
                return {
                    "status": "error", "error_code": "NOT_FOUND",
                    "message": f"Subject '{subject_name}' not found. Add it first, or check the spelling.",
                }

            banks = QuestionBank.objects.filter(subject=subject_obj).filter(
                Q(tenant=legacy_tenant) | Q(is_shared=True) | ~Q(board="")
            )
            pool = Question.objects.filter(question_banks__in=banks).distinct()
            available = pool.count()
            if available == 0:
                return {
                    "status": "error", "error_code": "NO_QUESTIONS",
                    "message": f"No questions found for {subject_name} in the question bank. Add some to a question bank first, then try again.",
                }

            selected_count = min(question_count, available)
            selected = list(pool.order_by("?")[:selected_count])
            objective_types = set(Question.OBJECTIVE_TYPES)
            theory_types = set(Question.THEORY_TYPES)
            picked_types = {q.question_type for q in selected}
            if picked_types <= objective_types:
                exam_format = "objective"
            elif picked_types <= theory_types:
                exam_format = "theory"
            else:
                exam_format = "mixed"

            now = dj_timezone.now()
            active_term, active_academic_year = self._active_term_and_year()
            exam = self.Exam.objects.create(
                tenant=legacy_tenant,
                title=f"{subject_name} CBT - {class_label}",
                subject=subject_obj,
                class_group=self._get_class(class_label),
                start_date=now,
                end_date=now + timedelta(minutes=time_limit_minutes or 60),
                duration_minutes=time_limit_minutes or 60,
                exam_format=exam_format,
                is_published=False,
                term=active_term,
                academic_year=active_academic_year,
            )
            exam.questions.set(selected)

            shortfall_note = (
                f" Only {available} question(s) were available, so all of them were used." if selected_count < question_count else ""
            )
            return {
                "status": "success",
                "message": f"CBT exam created for {subject_name} in {class_label} with {selected_count} question(s) from the question bank.{shortfall_note}",
                "exam_id": str(exam.id),
                "subject": subject_name,
                "class_name": class_label,
                "question_count": selected_count,
                "requested_question_count": question_count,
                "time_limit_minutes": time_limit_minutes or 60,
                "route": "/exams",
            }
        except Exception as exc:
            logger.exception("create_cbt_exam failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    # ── Phase 1 tool 5: navigate_to_page ──────────────────────────────────────

    def navigate_to_page(self, page: str) -> dict:
        try:
            page_key, route = resolve_navigation_page(page)
            return {
                "status": "success",
                "message": f"Opening the {page_key} page.",
                "page": page_key,
                "route": route,
            }
        except Exception as exc:
            logger.exception("navigate_to_page failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    # ── Tool 3: schedule_exam ────────────────────────────────────────────────

    def schedule_exam(
        self,
        exam_name: str,
        class_name: str,
        date: str,
        duration_minutes: int = 60,
        subject: str = "",
    ) -> dict:
        try:
            try:
                exam_date = datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                return {"status": "error", "error_code": "BAD_DATE", "message": "Date must be YYYY-MM-DD."}

            class_obj = self._get_class(class_name)
            start_dt = dj_timezone.make_aware(exam_date)
            end_dt = start_dt + timedelta(minutes=duration_minutes)
            active_term, active_academic_year = self._active_term_and_year()

            exam = self.Exam.objects.create(
                tenant=self._get_legacy_tenant(),
                title=exam_name.strip(),
                class_group=class_obj,
                start_date=start_dt,
                end_date=end_dt,
                duration_minutes=duration_minutes,
                is_published=False,
                term=active_term,
                academic_year=active_academic_year,
            )
            return {
                "status": "success",
                "exam_id": str(exam.id),
                "exam_name": exam.title,
                "class": class_name,
                "date": date,
                "duration_minutes": duration_minutes,
                "message": "Exam scheduled successfully.",
            }
        except Exception as exc:
            logger.exception("schedule_exam failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    # ── Tool 4: send_whatsapp_message ────────────────────────────────────────

    def send_whatsapp_message(self, to_phone: str, message_body: str) -> dict:
        try:
            from finance.services import send_termii_whatsapp
        except ImportError:
            return {"status": "error", "error_code": "NOT_CONFIGURED", "message": "WhatsApp service not available."}
        try:
            to_phone = self._normalize_phone(to_phone)
            result = send_termii_whatsapp(to_phone, message_body)
            ok = result.get("status") == "success"
            if ok:
                return {
                    "status": "success",
                    "delivered_to": to_phone,
                    "message_id": result.get("data", {}).get("id", ""),
                }
            return {
                "status": "error",
                "error_code": "WHATSAPP_DELIVERY_FAILED",
                "message": result.get("message", "Delivery failed."),
            }
        except Exception as exc:
            logger.exception("send_whatsapp_message failed: %s", exc)
            return {"status": "error", "error_code": "NETWORK", "message": str(exc)}

    # ── Tool 5: send_sms ─────────────────────────────────────────────────────

    def send_sms(self, to_phone: str, message_body: str) -> dict:
        try:
            from finance.models import SmsMessageLog
            from finance.services import InsufficientSmsCreditsError, SmsWalletLockedError, send_wallet_sms, sms_failure_reason
        except ImportError:
            return {"status": "error", "error_code": "NOT_CONFIGURED", "message": "SMS service not available."}
        try:
            if len(message_body) > 160:
                return {
                    "status": "error",
                    "error_code": "MESSAGE_TOO_LONG",
                    "message": f"SMS is {len(message_body)} chars — must be ≤160. Please shorten it.",
                }
            to_phone = self._normalize_phone(to_phone)
            try:
                log = send_wallet_sms(
                    self.tenant,
                    to_phone,
                    message_body,
                    category=SmsMessageLog.OTHER,
                    actor=self.requesting_user,
                    narration="AI Secretary",
                )
            except (InsufficientSmsCreditsError, SmsWalletLockedError) as exc:
                return {"status": "error", "error_code": "INSUFFICIENT_CREDITS", "message": str(exc)}
            if log.delivery_status in (SmsMessageLog.SENT, SmsMessageLog.DELIVERED):
                return {
                    "status": "success",
                    "delivered_to": to_phone,
                    "sms_id": str(log.id),
                    "units_used": log.credits_charged,
                }
            return {
                "status": "error",
                "error_code": "SMS_DELIVERY_FAILED",
                "message": sms_failure_reason(log),
            }
        except Exception as exc:
            logger.exception("send_sms failed: %s", exc)
            return {"status": "error", "error_code": "NETWORK", "message": str(exc)}

    # ── Tool 6: get_student_list ─────────────────────────────────────────────

    def get_student_list(self, class_name: str, include_inactive: bool = False) -> dict:
        try:
            # current_class lives on StudentProfile, not User directly - see
            # list_classes' docstring note on this same field confusion.
            qs = self.User.objects.filter(tenant=self.tenant, role="student")
            if not include_inactive:
                qs = qs.filter(is_active=True)
            if class_name.strip().upper() != "ALL":
                class_obj = self._get_class(class_name)
                if class_obj is None:
                    return {
                        "status": "error",
                        "error_code": "NOT_FOUND",
                        "message": f"Class '{class_name}' not found. Check the class name and try again.",
                    }
                qs = qs.filter(student_profile__current_class=class_obj)

            students = []
            for s in qs.select_related("student_profile__current_class").order_by("last_name", "first_name"):
                profile = getattr(s, "student_profile", None)
                student_class = profile.current_class if profile and profile.current_class else None
                students.append({
                    "student_id": str(s.id),
                    "name": s.get_full_name() or s.email,
                    "phone": s.phone or "",
                    "class": str(student_class) if student_class else class_name,
                    "is_active": s.is_active,
                })

            return {
                "status": "success",
                "class": class_name,
                "total": len(students),
                "students": students,
            }
        except Exception as exc:
            logger.exception("get_student_list failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    # ── Tool 7: publish_cbt_exam ─────────────────────────────────────────────

    def publish_cbt_exam(self, exam_id: str, access_window_hours: int = 24) -> dict:
        try:
            try:
                exam = self.Exam.objects.get(id=exam_id, tenant=self._get_legacy_tenant())
            except self.Exam.DoesNotExist:
                return {
                    "status": "error",
                    "error_code": "NOT_FOUND",
                    "message": f"Exam with ID '{exam_id}' not found.",
                }

            exam.is_published = True
            exam.save(update_fields=["is_published"])

            app_url = getattr(settings, "FRONTEND_BASE_URL", "https://app.schooldom.ng").rstrip("/")
            cbt_link = f"{app_url}/cbt/{exam_id}"
            expires_at = dj_timezone.now() + timedelta(hours=access_window_hours)

            return {
                "status": "success",
                "exam_id": exam_id,
                "exam_name": exam.title,
                "cbt_link": cbt_link,
                "expires_at": expires_at.strftime("%Y-%m-%d %H:%M UTC"),
                "access_window_hours": access_window_hours,
                "message": "Exam published as CBT.",
            }
        except Exception as exc:
            logger.exception("publish_cbt_exam failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    # ── Dispatcher ───────────────────────────────────────────────────────────

    TOOL_MAP = {
        "create_student": "create_student",
        "create_teacher": "create_teacher",
        "mark_attendance": "mark_attendance",
        "generate_timetable": "generate_timetable",
        "generate_report_cards": "generate_report_cards",
        "get_fee_status": "get_fee_status",
        "create_cbt_exam": "create_cbt_exam",
        "navigate_to_page": "navigate_to_page",
        "schedule_exam": "schedule_exam",
        "send_whatsapp_message": "send_whatsapp_message",
        "send_sms": "send_sms",
        "get_student_list": "get_student_list",
        "publish_cbt_exam": "publish_cbt_exam",
        "send_bulk_parent_message": "send_bulk_parent_message",
        "count_students": "count_students",
        "count_classes": "count_classes",
        "list_classes": "list_classes",
        "create_class": "create_class",
        "get_student_details": "get_student_details",
        "get_class_roster": "get_class_roster",
        "get_student_fee_balance": "get_student_fee_balance",
    }

    def send_bulk_parent_message(self, class_name: str, message_type: str, message: str) -> dict:
        """Actually sends the message (WhatsApp first, SMS fallback per
        SECRETARY_SYSTEM_PROMPT's rule) to every guardian in the class - an
        earlier draft of this tool sent nothing at all and returned a
        hardcoded delivered_count regardless of what was asked, which is why
        this is deliberately kept OUT of TOOL_SCHEMAS (see agent.py's bulk
        confirm-gate, the only path that can reach this)."""
        try:
            class_label = (class_name or "").strip()
            if not class_label:
                return {"status": "error", "error_code": "BAD_ARGS", "message": "A class name is required."}
            body = (message or "").strip()
            if not body:
                return {"status": "error", "error_code": "BAD_ARGS", "message": "Message content is required."}

            from users.models import StudentProfile

            class_obj = self._get_class(class_label)
            if class_obj is None:
                return {"status": "error", "error_code": "NOT_FOUND", "message": f"Class '{class_label}' not found."}

            roster = (
                StudentProfile.objects.select_related("user")
                .filter(user__tenant=self.tenant, user__is_active=True, current_class=class_obj)
                .exclude(guardian_phone="")
            )
            if not roster.exists():
                return {
                    "status": "error",
                    "error_code": "NO_RECIPIENTS",
                    "message": f"No parent phone numbers on file for {class_label}.",
                }

            sent, failed, errors = 0, 0, []
            for student in roster:
                guardian_label = student.guardian_name or student.user.get_full_name()
                wa_result = self.send_whatsapp_message(student.guardian_phone, body[:1000])
                if wa_result.get("status") == "success":
                    sent += 1
                    continue
                if len(body) > 160:
                    failed += 1
                    errors.append(f"{guardian_label}: message too long for SMS fallback")
                    continue
                sms_result = self.send_sms(student.guardian_phone, body)
                if sms_result.get("status") == "success":
                    sent += 1
                else:
                    failed += 1
                    errors.append(f"{guardian_label}: {sms_result.get('message', 'delivery failed')}")

            total = sent + failed
            return {
                "status": "success" if sent else "error",
                "class_name": class_label,
                "message_type": message_type,
                "delivered_count": sent,
                "failed_count": failed,
                "message": (
                    f"Bulk {message_type} sent to {sent} of {total} {class_label} parent(s)."
                    + (f" {failed} failed." if failed else "")
                ),
                "errors": errors[:10],
            }
        except Exception as exc:
            logger.exception("send_bulk_parent_message failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    def dispatch(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool by name. Returns a JSON-serialisable result dict."""
        method_name = self.TOOL_MAP.get(tool_name)
        if not method_name:
            return {"status": "error", "error_code": "UNKNOWN_TOOL", "message": f"Unknown tool: {tool_name}"}
        method = getattr(self, method_name)
        try:
            return method(**arguments)
        except TypeError as exc:
            return {"status": "error", "error_code": "BAD_ARGS", "message": f"Invalid arguments: {exc}"}

    def count_students(self, class_name: str = None) -> dict:
        """Count students in the school, optionally filtered by class."""
        try:
            qs = self.User.objects.filter(tenant=self.tenant, role="student", is_active=True)
            if class_name:
                class_obj = self._get_class(class_name)
                if class_obj is None:
                    return {
                        "status": "error",
                        "error_code": "NOT_FOUND",
                        "message": f"Class '{class_name}' not found.",
                    }
                count = qs.filter(student_profile__current_class=class_obj).count()
                return {
                    "status": "success",
                    "class_name": class_name,
                    "total": count,
                    "message": f"There are {count} active students in {class_name}.",
                }
            count = qs.count()
            return {
                "status": "success",
                "total": count,
                "message": f"There are {count} active students in the school.",
            }
        except Exception as exc:
            logger.exception("count_students failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    def count_classes(self) -> dict:
        """Count classes in the school."""
        try:
            legacy_tenant = self._get_legacy_tenant()
            count = self.Class.objects.filter(tenant=legacy_tenant).count() if legacy_tenant else self.Class.objects.count()
            return {
                "status": "success",
                "total": count,
                "message": f"There are {count} classes in the school.",
            }
        except Exception as exc:
            logger.exception("count_classes failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    def create_class(self, name: str, section: str = "") -> dict:
        try:
            from django.db.models import Q

            legacy_tenant = self._get_legacy_tenant()
            if legacy_tenant is None:
                return {"status": "error", "error_code": "NO_TENANT", "message": "Could not resolve this school's academic records."}

            name = (name or "").strip()
            if not name:
                return {"status": "error", "error_code": "BAD_ARGS", "message": "A class name is required."}
            section = (section or "").strip()

            existing_qs = self.Class.objects.filter(tenant=legacy_tenant, name__iexact=name)
            existing_qs = existing_qs.filter(section__iexact=section) if section else existing_qs.filter(Q(section__isnull=True) | Q(section=""))
            label = f"{name} {section}".strip() if section else name
            if existing_qs.exists():
                return {"status": "error", "error_code": "DUPLICATE", "message": f"A class named '{label}' already exists."}

            self.Class.objects.create(tenant=legacy_tenant, name=name, section=section)
            return {
                "status": "success",
                "class_name": name,
                "section": section,
                "message": f"Class '{label}' created.",
                "route": "/classes",
            }
        except Exception as exc:
            logger.exception("create_class failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    def list_classes(self) -> dict:
        """List every class by its real name, with a live student count each -
        the thing a model needs before it can correctly call a class-specific
        tool (roster, fee status, bulk message) instead of guessing a name
        that doesn't exist and getting NOT_FOUND."""
        try:
            legacy_tenant = self._get_legacy_tenant()
            classes = (
                self.Class.objects.filter(tenant=legacy_tenant).order_by("name")
                if legacy_tenant else self.Class.objects.none()
            )
            items = []
            for class_obj in classes:
                label = f"{class_obj.name} {class_obj.section}".strip() if class_obj.section else class_obj.name
                student_count = self.User.objects.filter(
                    tenant=self.tenant, role="student", is_active=True, student_profile__current_class=class_obj,
                ).count()
                items.append({
                    "name": class_obj.name,
                    "section": class_obj.section or "",
                    "label": label,
                    "student_count": student_count,
                })
            summary = ", ".join(f"{i['label']} ({i['student_count']})" for i in items) if items else "none yet"
            return {
                "status": "success",
                "total": len(items),
                "classes": items,
                "message": f"This school has {len(items)} class(es): {summary}.",
            }
        except Exception as exc:
            logger.exception("list_classes failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    def get_student_details(self, student_id: str) -> dict:
        """Get a student's full profile - by id first, falling back to a name search.
        Searches email rather than username: this User model has no username
        field at all (USERNAME_FIELD is email), so a username__icontains
        lookup would raise FieldError on every call - a bug in an earlier
        draft of this tool, fixed here rather than reintroduced."""
        try:
            from django.db.models import Q

            user = self.User.objects.filter(id=student_id, tenant=self.tenant, role="student").first()
            if not user:
                user = self.User.objects.filter(
                    Q(first_name__icontains=student_id) | Q(last_name__icontains=student_id) | Q(email__icontains=student_id),
                    tenant=self.tenant,
                    role="student",
                ).first()
            if not user:
                return {"status": "error", "error_code": "NOT_FOUND", "message": f"Student '{student_id}' not found."}
            profile = getattr(user, "student_profile", None)  # current_class lives here, not on User
            user_class = profile.current_class if profile and profile.current_class else None
            return {
                "status": "success",
                "student_id": str(user.id),
                "name": user.get_full_name(),
                "email": user.email or "N/A",
                "phone": user.phone or "N/A",
                "class": str(user_class) if user_class else "Not assigned",
                "is_active": user.is_active,
                "date_joined": user.date_joined.strftime("%Y-%m-%d") if user.date_joined else "N/A",
                "message": f"Found student: {user.get_full_name()}",
            }
        except Exception as exc:
            logger.exception("get_student_details failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    def get_class_roster(self, class_name: str) -> dict:
        """Get the full class roster - names, ids, and contact info."""
        try:
            class_obj = self._get_class(class_name)
            if not class_obj:
                return {"status": "error", "error_code": "NOT_FOUND", "message": f"Class '{class_name}' not found."}
            students = self.User.objects.filter(
                tenant=self.tenant,
                role="student",
                student_profile__current_class=class_obj,
                is_active=True,
            ).order_by("last_name", "first_name")
            roster = [
                {
                    "student_id": str(s.id),
                    "name": s.get_full_name(),
                    "email": s.email or "N/A",
                    "phone": s.phone or "N/A",
                }
                for s in students
            ]
            return {
                "status": "success",
                "class_name": class_name,
                "total_students": len(roster),
                "roster": roster,
                "message": f"Found {len(roster)} students in {class_name}.",
            }
        except Exception as exc:
            logger.exception("get_class_roster failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    def get_student_fee_balance(self, student_id: str) -> dict:
        """Get a student's real fee balance from SchoolFee records - an
        earlier draft of this tool returned hardcoded mock numbers
        (₦75,000 due / ₦50,000 paid for every student); this queries the
        actual finance.SchoolFee ledger instead, same total/paid pattern
        finance.services._student_paid_ratio already uses elsewhere."""
        try:
            from django.db.models import Q, Sum

            from finance.models import SchoolFee
            from users.models import StudentProfile

            user = self.User.objects.filter(id=student_id, tenant=self.tenant, role="student").first()
            if not user:
                user = self.User.objects.filter(
                    Q(first_name__icontains=student_id) | Q(last_name__icontains=student_id) | Q(email__icontains=student_id),
                    tenant=self.tenant,
                    role="student",
                ).first()
            if not user:
                return {"status": "error", "error_code": "NOT_FOUND", "message": f"Student '{student_id}' not found."}

            student_profile = StudentProfile.objects.filter(user=user).first()
            if not student_profile:
                return {"status": "error", "error_code": "NOT_FOUND", "message": f"No student profile found for {user.get_full_name()}."}

            fees = SchoolFee.objects.filter(student=student_profile)
            total_due = fees.aggregate(total=Sum("amount"))["total"] or 0
            total_paid = fees.filter(status=SchoolFee.STATUS_PAID).aggregate(total=Sum("amount"))["total"] or 0
            outstanding = total_due - total_paid

            return {
                "status": "success",
                "student_id": str(user.id),
                "name": user.get_full_name(),
                "class": str(student_profile.current_class) if student_profile.current_class else "Not assigned",
                "total_due": float(total_due),
                "total_paid": float(total_paid),
                "outstanding_balance": float(outstanding),
                "message": (
                    f"Fee balance for {user.get_full_name()}: ₦{outstanding:,.0f} outstanding"
                    if outstanding > 0
                    else f"{user.get_full_name()} has no outstanding fees."
                ),
            }
        except Exception as exc:
            logger.exception("get_student_fee_balance failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}

    def get_daily_briefing(self) -> dict:
        """Deterministic, zero-AI-cost snapshot for the admin login briefing:
        top fee defaulters and yesterday's successful fee payments. Pure DB
        queries, no AI call involved - deliberately NOT in TOOL_SCHEMAS (not
        meant to be something the model decides whether to call; the
        dashboard calls this tool method directly), same reasoning as
        send_bulk_parent_message being kept out of TOOL_SCHEMAS."""
        try:
            from django.db.models import Sum

            from finance.models import AdminWallet, SchoolFee, Transaction

            yesterday = dj_timezone.localdate() - timedelta(days=1)

            defaulters_qs = (
                SchoolFee.objects.filter(student__user__tenant=self.tenant)
                .exclude(status=SchoolFee.STATUS_PAID)
                .values("student_id", "student__user__first_name", "student__user__last_name")
                .annotate(outstanding=Sum("amount"))
                .order_by("-outstanding")[:10]
            )
            defaulters = [
                {
                    "student_id": str(row["student_id"]),
                    "name": f"{row['student__user__first_name']} {row['student__user__last_name']}".strip(),
                    "outstanding": float(row["outstanding"] or 0),
                }
                for row in defaulters_qs
            ]
            total_outstanding = float(
                SchoolFee.objects.filter(student__user__tenant=self.tenant)
                .exclude(status=SchoolFee.STATUS_PAID)
                .aggregate(total=Sum("amount"))["total"] or 0
            )

            admin_wallet = AdminWallet.objects.filter(tenant=self.tenant).first()
            yesterday_qs = (
                Transaction.objects.filter(
                    admin_wallet=admin_wallet, status=Transaction.STATUS_SUCCESS, created_at__date=yesterday,
                )
                if admin_wallet else Transaction.objects.none()
            )
            yesterday_total = float(yesterday_qs.aggregate(total=Sum("amount"))["total"] or 0)
            yesterday_count = yesterday_qs.count()

            return {
                "status": "success",
                "date": yesterday.isoformat(),
                "defaulters": defaulters,
                "total_outstanding": total_outstanding,
                "yesterday_total": yesterday_total,
                "yesterday_count": yesterday_count,
            }
        except Exception as exc:
            logger.exception("get_daily_briefing failed: %s", exc)
            return {"status": "error", "error_code": "UNKNOWN", "message": str(exc)}
