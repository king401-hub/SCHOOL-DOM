from django.contrib import admin

from .models import (
    Announcement,
    AnnouncementRead,
    BroadcastMessage,
    InAppMessage,
    Notification,
    NotificationPreference,
    NotificationTemplate,
)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "event_type", "tenant", "default_priority", "is_active")
    list_filter = ("tenant", "event_type", "is_active", "default_priority")
    search_fields = ("name", "code")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "tenant", "notification_type", "priority", "channel", "is_read", "created_at")
    list_filter = ("tenant", "notification_type", "priority", "channel", "is_read", "is_delivered")
    search_fields = ("title", "message", "user__email")
    readonly_fields = ("created_at", "updated_at", "read_at", "delivered_at")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "tenant", "disable_all", "allow_email", "allow_push", "allow_in_app")
    list_filter = ("tenant", "disable_all", "allow_email", "allow_push", "allow_in_app")
    search_fields = ("user__email",)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "tenant", "author", "audience_type", "priority", "is_published", "publish_from")
    list_filter = ("tenant", "audience_type", "priority", "is_published", "is_pinned")
    search_fields = ("title", "slug", "author__email", "content")
    readonly_fields = ("view_count", "unique_views", "click_count")


@admin.register(AnnouncementRead)
class AnnouncementReadAdmin(admin.ModelAdmin):
    list_display = ("announcement", "user", "tenant", "read_at")
    list_filter = ("tenant", "read_at")
    search_fields = ("announcement__title", "user__email")


@admin.register(BroadcastMessage)
class BroadcastMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "tenant", "sender", "status", "scheduled_for", "sent_at")
    list_filter = ("tenant", "status", "send_email", "send_sms", "send_push", "send_in_app")
    search_fields = ("subject", "message", "sender__email")


@admin.register(InAppMessage)
class InAppMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "sender", "recipient", "tenant", "is_read", "created_at")
    list_filter = ("tenant", "is_read", "deleted_by_sender", "deleted_by_recipient")
    search_fields = ("subject", "body", "sender__email", "recipient__email")
