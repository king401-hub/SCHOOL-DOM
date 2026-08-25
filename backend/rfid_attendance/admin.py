from django.contrib import admin

from .models import CardAssignment


@admin.register(CardAssignment)
class CardAssignmentAdmin(admin.ModelAdmin):
    list_display = ['card_uid', 'student', 'status', 'tenant', 'assigned_at', 'revoked_at']
    list_filter = ['status', 'tenant']
    search_fields = ['card_uid', 'student__email', 'student__first_name', 'student__last_name']
    readonly_fields = ['id', 'assigned_at', 'created_at', 'updated_at']

    def has_add_permission(self, request):
        # Assignments should only be created from the RFID desktop app.
        return False
