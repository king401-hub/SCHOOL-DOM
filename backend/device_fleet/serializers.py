from rest_framework import serializers

from .models import Device, DeviceAuditLog, ProvisioningKey


class DeviceSerializer(serializers.ModelSerializer):
    school_name = serializers.SerializerMethodField()
    is_online = serializers.BooleanField(read_only=True)
    is_low_battery = serializers.BooleanField(read_only=True)
    needs_attention = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = [
            'id', 'device_id', 'name', 'license_key', 'status', 'school_name', 'authorized',
            'is_online', 'is_low_battery', 'needs_attention',
            'app_version', 'device_model', 'os_version',
            'battery_percentage', 'battery_charging', 'battery_health', 'battery_temperature_c',
            'last_seen_at', 'last_sync_at', 'first_activated_at', 'created_at',
        ]

    def get_school_name(self, obj):
        return obj.tenant.name if obj.tenant else None

    def get_needs_attention(self, obj):
        return obj.needs_attention()


class ProvisioningKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProvisioningKey
        fields = ['id', 'key', 'status', 'single_use', 'expires_at', 'created_at', 'used_at', 'notes']


class DeviceAuditLogSerializer(serializers.ModelSerializer):
    device_id = serializers.CharField(source='device.device_id', read_only=True, default=None)
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = DeviceAuditLog
        fields = ['id', 'device_id', 'actor_name', 'action', 'details', 'result', 'created_at']

    def get_actor_name(self, obj):
        return obj.actor.get_full_name() if obj.actor else 'System'
