from rest_framework import serializers

from .models import CardAssignment


class CardAssignmentSerializer(serializers.ModelSerializer):
    student_id = serializers.CharField(source='student.id', read_only=True)
    student_name = serializers.SerializerMethodField()
    assigned_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CardAssignment
        fields = [
            'id', 'student_id', 'student_name', 'card_uid', 'status',
            'assigned_at', 'revoked_at', 'assigned_by_name',
        ]

    def get_student_name(self, obj):
        return obj.student.get_full_name() or obj.student.email

    def get_assigned_by_name(self, obj):
        return obj.assigned_by.get_full_name() if obj.assigned_by else None
