from django.contrib import admin

from .models import CardAssignment


@admin.register(CardAssignment)
class CardAssignmentAdmin(admin.ModelAdmin):
    list_display = ['card_uid', 'holder', 'status', 'tenant', 'assigned_at', 'revoked_at']
    list_filter = ['status', 'tenant']
    search_fields = ['card_uid', 'holder__email', 'holder__first_name', 'holder__last_name']
    readonly_fields = ['id', 'assigned_at', 'created_at', 'updated_at']
    # A plain <select> would list every user platform-wide. This opens a
    # popup onto UserAdmin's own changelist instead - its existing
    # role/tenant list_filter and tenant-name search already let the admin
    # narrow it down to one school before picking a holder, with no new
    # cascading-dropdown code needed.
    raw_id_fields = ['holder']
