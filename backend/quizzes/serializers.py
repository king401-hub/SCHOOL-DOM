from django.contrib.auth import get_user_model
from rest_framework import serializers

from users.models import resolve_legacy_tenant_for_school
from .models import Answer, Choice, Question, Quiz, Submission

User = get_user_model()


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ["id", "text", "is_correct"]
        read_only_fields = ["id"]


class PublicChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ["id", "text"]
        read_only_fields = ["id", "text"]


class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True)

    class Meta:
        model = Question
        fields = ["id", "text", "explanation", "order", "points", "choices"]
        read_only_fields = ["id"]

    def validate_choices(self, value):
        if not value:
            raise serializers.ValidationError("Add at least one choice.")
        if not any(item.get("is_correct") for item in value):
            raise serializers.ValidationError("Mark at least one option as correct.")
        return value


class PublicQuestionSerializer(serializers.ModelSerializer):
    choices = PublicChoiceSerializer(many=True)

    class Meta:
        model = Question
        fields = ["id", "text", "explanation", "order", "points", "choices"]
        read_only_fields = ["id", "text", "explanation", "order", "points", "choices"]


class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True)

    class Meta:
        model = Quiz
        fields = [
            "id",
            "title",
            "description",
            "is_published",
            "allow_multiple_attempts",
            "time_limit_minutes",
            "questions",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        request = self.context.get("request")
        teacher = getattr(request, "user", None)
        tenant = resolve_legacy_tenant_for_school(getattr(teacher, "tenant", None))

        questions_data = validated_data.pop("questions", [])
        quiz = Quiz.objects.create(teacher=teacher, tenant=tenant, **validated_data)

        for index, question_data in enumerate(questions_data):
            choices_data = question_data.pop("choices", [])
            order_value = question_data.pop("order", None) or index + 1
            question = Question.objects.create(
                quiz=quiz,
                tenant=quiz.tenant,
                order=order_value,
                **question_data,
            )
            for choice_data in choices_data:
                Choice.objects.create(question=question, **choice_data)

        return quiz

    def update(self, instance, validated_data):
        questions_data = validated_data.pop("questions", [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Replace questions/choices with provided payload
        if questions_data:
            instance.questions.all().delete()
            for index, question_data in enumerate(questions_data):
                choices_data = question_data.pop("choices", [])
                order_value = question_data.pop("order", None) or index + 1
                question = Question.objects.create(
                    quiz=instance,
                    tenant=instance.tenant,
                    order=order_value,
                    **question_data,
                )
                for choice_data in choices_data:
                    Choice.objects.create(question=question, **choice_data)

        return instance


class QuizListSerializer(serializers.ModelSerializer):
    question_count = serializers.SerializerMethodField()
    submission_count = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = [
            "id",
            "title",
            "description",
            "is_published",
            "allow_multiple_attempts",
            "time_limit_minutes",
            "question_count",
            "submission_count",
            "created_at",
            "updated_at",
        ]

    def get_question_count(self, obj):
        return obj.questions.count()

    def get_submission_count(self, obj):
        return obj.submissions.count()


class StudentQuizSerializer(serializers.ModelSerializer):
    questions = PublicQuestionSerializer(many=True)

    class Meta:
        model = Quiz
        fields = [
            "id",
            "title",
            "description",
            "time_limit_minutes",
            "allow_multiple_attempts",
            "questions",
        ]


class AnswerPayloadSerializer(serializers.Serializer):
    question = serializers.IntegerField()
    choice = serializers.IntegerField()


class SubmissionSerializer(serializers.Serializer):
    answers = AnswerPayloadSerializer(many=True)

    def validate(self, attrs):
        request = self.context["request"]
        quiz = self.context["quiz"]
        student = request.user

        # Validate that answers contain valid questions and choices
        answers_payload = attrs.get("answers", [])
        
        # Get fresh question and choice data from database
        question_map = {}
        choice_map = {}
        
        for question in quiz.questions.all():
            question_map[question.id] = question
            choice_map[question.id] = {choice.id: choice for choice in question.choices.all()}
        
        # Only validate answers that were submitted (not all questions)
        for idx, item in enumerate(answers_payload):
            question_id = item.get("question")
            choice_id = item.get("choice")
            
            if not question_id or not choice_id:
                raise serializers.ValidationError(f"Answer {idx}: missing question or choice.")
            
            if question_id not in question_map:
                raise serializers.ValidationError(f"Question {question_id} not found in quiz {quiz.id}.")
            
            if question_id not in choice_map or choice_id not in choice_map[question_id]:
                raise serializers.ValidationError(f"Choice {choice_id} not found for question {question_id}.")
        
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        quiz = self.context["quiz"]
        student = request.user
        tenant = resolve_legacy_tenant_for_school(getattr(student, "tenant", None)) or quiz.tenant

        answers_payload = validated_data.get("answers", [])
        question_map = {q.id: q for q in quiz.questions.prefetch_related("choices")}

        if not quiz.allow_multiple_attempts:
            Submission.objects.filter(quiz=quiz, student=student).delete()

        submission = Submission.objects.create(
            quiz=quiz,
            student=student,
            tenant=tenant,
            total_points=sum(q.points for q in question_map.values()),
        )

        score = 0
        answer_records = []
        for item in answers_payload:
            question = question_map.get(item["question"])
            if not question:
                continue
            selected_choice = next((c for c in question.choices.all() if c.id == item["choice"]), None)
            is_correct = bool(selected_choice and selected_choice.is_correct)
            earned = question.points if is_correct else 0
            score += earned
            answer_records.append(
                Answer(
                    submission=submission,
                    question=question,
                    choice=selected_choice,
                    is_correct=is_correct,
                    earned_points=earned,
                )
            )

        Answer.objects.bulk_create(answer_records)
        submission.score = score
        submission.save(update_fields=["score"])
        return submission


class SubmissionDetailSerializer(serializers.ModelSerializer):
    answers = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = ["id", "score", "total_points", "submitted_at", "answers"]

    def get_answers(self, obj):
        from django.db.models import Prefetch
        
        data = []
        # Prefetch all answers with their questions and choices efficiently
        answers = obj.answers.select_related("question", "choice").prefetch_related("question__choices")
        
        for answer in answers:
            # Use the prefetched choices from the question
            correct_choices = [c for c in answer.question.choices.all() if c.is_correct]
            data.append(
                {
                    "question_id": answer.question_id,
                    "question": answer.question.text,
                    "explanation": answer.question.explanation,
                    "selected_choice_id": answer.choice_id,
                    "selected_choice": answer.choice.text if answer.choice else None,
                    "is_correct": answer.is_correct,
                    "earned_points": answer.earned_points,
                    "correct_choice_ids": [c.id for c in correct_choices],
                    "correct_choices": [{"id": c.id, "text": c.text} for c in correct_choices],
                }
            )
        return data
