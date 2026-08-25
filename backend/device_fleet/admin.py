from django.contrib import admin

from .models import Device, DeviceAuditLog, ProvisioningKey


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['device_id', 'name', 'status', 'tenant', 'authorized', 'battery_percentage', 'last_seen_at']
    list_filter = ['status', 'authorized', 'battery_health']
    search_fields = ['device_id', 'name', 'tenant__name']
    readonly_fields = ['id', 'device_id', 'auth_token', 'created_at', 'updated_at']


@admin.register(ProvisioningKey)
class ProvisioningKeyAdmin(admin.ModelAdmin):
    list_display = ['key', 'status', 'created_by', 'created_at', 'used_at']
    list_filter = ['status', 'single_use']
    search_fields = ['key']
    readonly_fields = ['id', 'key', 'created_at']


@admin.register(DeviceAuditLog)
class DeviceAuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'device', 'actor', 'result', 'created_at']
    list_filter = ['action', 'result']
    search_fields = ['device__device_id', 'actor__email']
    readonly_fields = ['id', 'created_at']

    def has_add_permission(self, request):
        return False
