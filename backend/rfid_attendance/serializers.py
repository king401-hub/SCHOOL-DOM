from rest_framework import serializers

from .models import CardAssignment


class CardAssignmentSerializer(serializers.ModelSerializer):
    person_id = serializers.CharField(source='holder.id', read_only=True)
    person_name = serializers.SerializerMethodField()
    role = serializers.CharField(source='holder.role', read_only=True)
    assigned_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CardAssignment
        fields = [
            'id', 'person_id', 'person_name', 'role', 'card_uid', 'status',
            'assigned_at', 'revoked_at', 'assigned_by_name',
        ]

    def get_person_name(self, obj):
        return obj.holder.get_full_name() or obj.holder.email

    def get_assigned_by_name(self, obj):
        return obj.assigned_by.get_full_name() if obj.assigned_by else None
