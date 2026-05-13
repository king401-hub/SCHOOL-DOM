from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from academic.models import Class
from core.models import SchoolTenant
from exams.models import Exam
from .models import (
    LoginHistory,
    ParentProfile,
    StudentEnrollment,
    StudentProfile,
    TeacherProfile,
    User,
    resolve_legacy_tenant_for_school,
)


class StudentEnrollmentAdminForm(forms.ModelForm):
    class Meta:
        model = StudentEnrollment
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_class"].queryset = Class.objects.none()
        self.fields["exams"].queryset = Exam.objects.none()
        self.fields["student"].queryset = StudentProfile.objects.select_related("user").order_by("user__email")
        self.fields["school"].queryset = SchoolTenant.objects.order_by("name")

        school = self._resolve_school()
        legacy_tenant = resolve_legacy_tenant_for_school(school)
        if legacy_tenant:
            self.fields["assigned_class"].queryset = Class.objects.filter(tenant=legacy_tenant).order_by("name", "section")
            self.fields["exams"].queryset = Exam.objects.filter(tenant=legacy_tenant).order_by("-start_date", "title")

    def _resolve_school(self):
        if self.instance.pk and self.instance.school_id:
            return self.instance.school

        raw_school = self.data.get("school") if self.data else None
        if raw_school:
            try:
                return SchoolTenant.objects.get(pk=raw_school)
            except SchoolTenant.DoesNotExist:
                return None

        initial_school = self.initial.get("school")
        if isinstance(initial_school, SchoolTenant):
            return initial_school
        if initial_school:
            try:
                return SchoolTenant.objects.get(pk=initial_school)
            except SchoolTenant.DoesNotExist:
                return None
        return None

    def clean(self):
        cleaned = super().clean()
        student = cleaned.get("student")
        school = cleaned.get("school")
        assigned_class = cleaned.get("assigned_class")
        exams = cleaned.get("exams")

        if student and not school:
            school = student.user.tenant
            cleaned["school"] = school

        if student and school and student.user.tenant_id != school.id:
            self.add_error("student", "Selected student does not belong to selected school.")

        legacy_tenant = resolve_legacy_tenant_for_school(school)

        if assigned_class and (not legacy_tenant or assigned_class.tenant_id != legacy_tenant.id):
            self.add_error("assigned_class", "Selected class does not belong to selected school.")

        if exams and not legacy_tenant:
            self.add_error("exams", "Could not map selected school to legacy exam tenant.")
        elif exams and legacy_tenant:
            invalid_exams = [exam.title for exam in exams if exam.tenant_id != legacy_tenant.id]
            if invalid_exams:
                self.add_error("exams", f"Exams outside selected school: {', '.join(invalid_exams[:3])}")

        return cleaned


class StudentEnrollmentInline(admin.TabularInline):
    model = StudentEnrollment
    extra = 0
    fields = ("school", "assigned_class", "created_by", "created_at")
    readonly_fields = ("school", "assigned_class", "created_by", "created_at")
    can_delete = False
    show_change_link = True


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "first_name", "last_name", "role", "tenant", "is_staff", "is_active")
    list_filter = ("role", "tenant", "is_staff", "is_active", "is_verified")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "phone", "profile_picture", "date_of_birth", "gender", "tenant")}),
        ("Security", {"fields": ("is_verified", "is_locked", "last_login_ip", "login_attempts", "last_password_change")}),
        ("Permissions", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "first_name", "last_name", "role", "tenant"),
            },
        ),
    )
    search_fields = ("email", "first_name", "last_name", "tenant__name", "tenant__schema_name")
    ordering = ("email",)
    filter_horizontal = ("groups", "user_permissions")
    readonly_fields = ("created_at", "updated_at", "last_login")


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = (
        "student_id",
        "student_name",
        "student_email",
        "school",
        "current_class",
        "guardian_name",
        "guardian_phone",
        "admission_date",
    )
    list_filter = ("user__tenant", "current_class", "current_term", "admission_date")
    search_fields = ("student_id", "admission_number", "user__email", "user__first_name", "user__last_name", "guardian_name")
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [StudentEnrollmentInline]

    @admin.display(description="Name")
    def student_name(self, obj):
        return obj.user.get_full_name()

    @admin.display(description="Email")
    def student_email(self, obj):
        return obj.user.email

    @admin.display(description="School")
    def school(self, obj):
        return obj.user.tenant


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "teacher_name", "teacher_email", "specialization", "hire_date", "employment_type")
    list_filter = ("employment_type", "hire_date", "user__tenant")
    search_fields = ("employee_id", "user__email", "user__first_name", "user__last_name", "specialization")
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Name")
    def teacher_name(self, obj):
        return obj.user.get_full_name()

    @admin.display(description="Email")
    def teacher_email(self, obj):
        return obj.user.email


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ("parent_name", "parent_email", "occupation", "preferred_contact", "children_count")
    list_filter = ("preferred_contact", "user__tenant")
    search_fields = ("user__email", "user__first_name", "user__last_name", "occupation", "company")
    filter_horizontal = ("children",)
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Name")
    def parent_name(self, obj):
        return obj.user.get_full_name()

    @admin.display(description="Email")
    def parent_email(self, obj):
        return obj.user.email

    @admin.display(description="Children")
    def children_count(self, obj):
        return obj.children.count()


@admin.register(StudentEnrollment)
class StudentEnrollmentAdmin(admin.ModelAdmin):
    form = StudentEnrollmentAdminForm
    list_display = (
        "student_name",
        "school",
        "assigned_class",
        "linked_exam_count",
        "has_message",
        "created_by",
        "created_at",
    )
    list_filter = ("school", "created_at")
    search_fields = (
        "student__student_id",
        "student__admission_number",
        "student__user__email",
        "student__user__first_name",
        "student__user__last_name",
        "school__name",
    )
    filter_horizontal = ("exams",)
    raw_id_fields = ("student", "created_by", "enrollment_message")
    readonly_fields = ("created_at", "updated_at", "enrollment_message")
    fieldsets = (
        ("Enrollment", {"fields": ("school", "student", "assigned_class", "exams", "created_by")}),
        ("Message", {"fields": ("welcome_subject", "welcome_message", "enrollment_message")}),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Student")
    def student_name(self, obj):
        return obj.student.user.get_full_name()

    @admin.display(description="Linked Exams")
    def linked_exam_count(self, obj):
        return obj.exams.count()

    @admin.display(boolean=True, description="Message Sent")
    def has_message(self, obj):
        return bool(obj.enrollment_message_id)

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        if obj.student_id and not obj.school_id:
            obj.school = obj.student.user.tenant
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.apply_links()


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "login_time", "logout_time", "ip_address", "device_type", "browser", "os")
    list_filter = ("status", "login_time", "device_type", "browser", "os")
    search_fields = ("user__email", "user__first_name", "user__last_name", "ip_address", "location")
    readonly_fields = (
        "user",
        "status",
        "login_time",
        "logout_time",
        "ip_address",
        "user_agent",
        "device_type",
        "browser",
        "os",
        "location",
    )

    def has_add_permission(self, request):
        return False
