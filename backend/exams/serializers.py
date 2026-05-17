from rest_framework import serializers
from .models import Exam, ExamAttempt, Question, StudentAnswer

class QuestionSerializer(serializers.ModelSerializer):
    group = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = ['id', 'text', 'image', 'options', 'question_type', 'points', 'group', 'group_order']

    def get_group(self, obj):
        group = getattr(obj, "group", None)
        if not group:
            return None
        return {
            "id": group.id,
            "title": group.title,
            "group_type": group.group_type,
            "passage_text": group.passage_text,
            "image": group.image.url if group.image else "",
        }

class ExamSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    class_name = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    pin_required = serializers.SerializerMethodField()
    
    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'subject', 'duration_minutes', 'questions',
            'shuffle_questions', 'show_results_immediately', 'instructions',
            'start_date', 'end_date', 'subject_name', 'class_name', 'question_count',
            'pin_required'
        ]

    def get_class_name(self, obj):
        class_group = obj.class_group
        if not class_group:
            return 'All classes'
        return getattr(class_group, 'name', None) or str(class_group)

    def get_question_count(self, obj):
        direct_count = obj.questions.count()
        if direct_count:
            return direct_count
        try:
            return Question.objects.filter(question_banks__exam=obj).distinct().count()
        except Exception:
            return 0

    def get_pin_required(self, obj):
        return obj.pins.filter(is_active=True).exists()

class StudentAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAnswer
        fields = ['id', 'question_id', 'selected_options', 'answer_text']

class ExamAttemptSerializer(serializers.ModelSerializer):
    exam = ExamSerializer(read_only=True)
    answers = StudentAnswerSerializer(many=True, read_only=True)
    
    class Meta:
        model = ExamAttempt
        fields = [
            'id', 'exam', 'start_time', 'is_completed', 'is_submitted',
            'auto_submitted', 'auto_submit_reason', 'auto_submit_reason_display',
            'auto_submit_details', 'auto_submit_warning_history',
            'auto_submit_activity_logs', 'answers'
        ]

class ExamAttemptDetailSerializer(serializers.Serializer):
    """Serializer for exam attempt detail response"""
    attempt = ExamAttemptSerializer(read_only=True)
    exam = ExamSerializer(read_only=True)
    questions = QuestionSerializer(many=True, read_only=True)
    student = serializers.SerializerMethodField()
    time_remaining_seconds = serializers.SerializerMethodField()
    answers = serializers.DictField(read_only=True)
    
    def get_student(self, obj):
        user = self.context['request'].user
        return {
            'id': f"STU{user.id:06d}",
            'name': f"{user.first_name} {user.last_name}",
            'avatar': getattr(user, 'profile_image', None)
        }
    
    def get_time_remaining_seconds(self, obj):
        from datetime import datetime, timezone
        attempt = obj
        if attempt.is_completed:
            return 0
        
        elapsed = (datetime.now(timezone.utc) - attempt.start_time).total_seconds()
        total_seconds = attempt.exam.duration_minutes * 60
        remaining = int(total_seconds - elapsed)
        return max(0, remaining)

class ExamResultSerializer(serializers.Serializer):
    """Serializer for exam results"""
    attempt_id = serializers.IntegerField()
    score = serializers.FloatField()
    total_points = serializers.FloatField()
    percentage = serializers.FloatField()
    grade = serializers.CharField()
    is_passed = serializers.BooleanField()
    answers_review = StudentAnswerSerializer(many=True)
