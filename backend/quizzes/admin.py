from django.contrib import admin

from .models import PersonalQuizFolder, PersonalQuizFolderQuestion


class PersonalQuizFolderQuestionInline(admin.TabularInline):
    model = PersonalQuizFolderQuestion
    extra = 1
    fields = ("question_type", "prompt", "options", "correct_answer", "explanation", "order", "points", "is_active")
    readonly_fields = ()
    show_change_link = True


@admin.register(PersonalQuizFolder)
class PersonalQuizFolderAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "subject", "subject_code", "subject_name", "class_group", "is_active", "question_count")
    list_filter = ("is_active", "tenant", "subject", "class_group")
    search_fields = ("name", "subject_code", "subject_name")
    inlines = [PersonalQuizFolderQuestionInline]

    @admin.display(description="Questions")
    def question_count(self, obj):
        return obj.folder_questions.filter(is_active=True).count()


@admin.register(PersonalQuizFolderQuestion)
class PersonalQuizFolderQuestionAdmin(admin.ModelAdmin):
    list_display = ("folder", "question_type", "prompt_preview", "correct_answer", "order", "is_active")
    list_filter = ("question_type", "is_active", "folder__tenant", "folder__subject")
    search_fields = ("prompt", "correct_answer", "folder__name")
    list_select_related = ("folder",)

    @admin.display(description="Prompt")
    def prompt_preview(self, obj):
        return (obj.prompt or "")[:80]
