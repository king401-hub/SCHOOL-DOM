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

# ── Tool schema definitions (fed to Ollama as the `tools` list) ──────────────
# tenant_id is intentionally omitted — it is injected server-side for security.

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "create_student",
            "description": "Register a new student. Need: name, phone, class_name. Email optional.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Student full name"},
                    "phone": {"type": "string", "description": "Parent phone E.164 e.g. +2348012345678"},
                    "class_name": {"type": "string", "description": "Class e.g. JSS1, SS2A"},
                    "email": {"type": "string", "description": "Parent email (optional)"},
                },
                "required": ["name", "phone", "class_name"],
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
        """Return Class object or None; tenant-aware."""
        try:
            return self.Class.objects.filter(
                tenant=self.tenant,
                name__iexact=class_name.strip(),
            ).first()
        except Exception:
            return None

    # ── Tool 1: create_student ───────────────────────────────────────────────

    def create_student(self, name: str, phone: str, class_name: str, email: str = "") -> dict:
        try:
            phone = self._normalize_phone(phone)
            name_parts = name.strip().split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            # Resolve class
            class_obj = self._get_class(class_name)

            # Build a unique username/email for the student account
            base_email = email.strip() if email else f"{first_name.lower()}.{last_name.lower()}.{secrets.token_hex(3)}@student.{self.tenant.schema_name}.schooldom.local"

            # Prevent duplicate by phone+tenant
            if self.User.objects.filter(phone=phone, tenant=self.tenant, role="student").exists():
                return {
                    "status": "error",
                    "error_code": "DUPLICATE",
                    "message": f"A student with phone {phone} already exists in this school.",
                }

            user = self.User(
                email=base_email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                role="student",
                tenant=self.tenant,
                is_active=True,
                is_verified=False,
            )
            if class_obj:
                user.current_class = class_obj
            user.set_unusable_password()
            user.save()

            return {
                "status": "success",
                "student_id": str(user.id),
                "name": user.get_full_name(),
                "class": class_name,
                "phone": phone,
                "message": "Student registered successfully.",
            }
        except Exception as exc:
            logger.exception("create_student failed: %s", exc)
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

            exam = self.Exam.objects.create(
                tenant=self.tenant,
                title=exam_name.strip(),
                class_group=class_obj,
                start_date=start_dt,
                end_date=end_dt,
                duration_minutes=duration_minutes,
                is_published=False,
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
            from finance.services import send_sendchamp_sms
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
            result = send_sendchamp_sms(to_phone, message_body)
            ok = result.get("code") in ("200", 200) or result.get("status") == "success"
            if ok:
                return {
                    "status": "success",
                    "delivered_to": to_phone,
                    "sms_id": result.get("data", {}).get("id", ""),
                    "units_used": 1,
                }
            return {
                "status": "error",
                "error_code": "SMS_DELIVERY_FAILED",
                "message": result.get("message", "Delivery failed."),
            }
        except Exception as exc:
            logger.exception("send_sms failed: %s", exc)
            return {"status": "error", "error_code": "NETWORK", "message": str(exc)}

    # ── Tool 6: get_student_list ─────────────────────────────────────────────

    def get_student_list(self, class_name: str, include_inactive: bool = False) -> dict:
        try:
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
                qs = qs.filter(current_class=class_obj)

            students = []
            for s in qs.select_related("current_class").order_by("last_name", "first_name"):
                students.append({
                    "student_id": str(s.id),
                    "name": s.get_full_name() or s.email,
                    "phone": s.phone or "",
                    "class": str(s.current_class) if s.current_class else class_name,
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
                exam = self.Exam.objects.get(id=exam_id, tenant=self.tenant)
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
        "mark_attendance": "mark_attendance",
        "schedule_exam": "schedule_exam",
        "send_whatsapp_message": "send_whatsapp_message",
        "send_sms": "send_sms",
        "get_student_list": "get_student_list",
        "publish_cbt_exam": "publish_cbt_exam",
    }

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
