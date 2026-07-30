from django.contrib import admin

from .models import QueuedRequest, QueuedRequestEvent


class QueuedRequestEventInline(admin.TabularInline):
    model = QueuedRequestEvent
    extra = 0
    readonly_fields = ["event_type", "description", "actor", "metadata", "created_at"]
    can_delete = False
    ordering = ["created_at"]


@admin.register(QueuedRequest)
class QueuedRequestAdmin(admin.ModelAdmin):
    list_display = ["id", "request_type", "status", "requester", "tenant", "retry_count", "is_archived", "created_at"]
    list_filter = ["status", "request_type", "is_archived"]
    search_fields = ["id", "requester__email", "requester__first_name", "requester__last_name"]
    readonly_fields = ["id", "dedupe_key", "created_at", "updated_at"]
    inlines = [QueuedRequestEventInline]
