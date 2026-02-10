# exams/models.py
from django.db import models
from core.models import TimeStampedModel, TenantAwareModel

class ExamType(models.Model):
    name = models.CharField(max_length=100)  # MCQ, Essay, Mixed
    tenant = models.ForeignKey('core.SchoolTenant', on_delete=models.CASCADE)

class QuestionBank(TenantAwareModel, TimeStampedModel):
    name = models.CharField(max_length=200)
    subject = models.ForeignKey('academic.Subject', on_delete=models.CASCADE)
    teacher = models.ForeignKey('users.Teacher', on_delete=models.CASCADE)
    questions = models.ManyToManyField('Question', related_name='question_banks')
    is_shared = models.BooleanField(default=False)

class Question(TenantAwareModel, TimeStampedModel):
    QUESTION_TYPES = [
        ('mcq', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('short_answer', 'Short Answer'),
        ('essay', 'Essay'),
    ]
    
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    text = models.TextField()
    image = models.ImageField(upload_to='question_images/', null=True, blank=True)
    points = models.IntegerField(default=1)
    options = models.JSONField(null=True, blank=True)  # For MCQ
    correct_answer = models.TextField(null=True, blank=True)
    explanation = models.TextField(null=True, blank=True)

class Exam(TenantAwareModel, TimeStampedModel):
    title = models.CharField(max_length=200)
    subject = models.ForeignKey('academic.Subject', on_delete=models.CASCADE)
    class_group = models.ForeignKey('academic.Class', on_delete=models.CASCADE)
    teacher = models.ForeignKey('users.Teacher', on_delete=models.CASCADE)
    exam_type = models.ForeignKey(ExamType, on_delete=models.CASCADE)
    
    # Scheduling
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    duration_minutes = models.IntegerField()
    
    # Settings
    shuffle_questions = models.BooleanField(default=False)
    show_results_immediately = models.BooleanField(default=False)
    allow_retake = models.BooleanField(default=False)
    max_attempts = models.IntegerField(default=1)
    
    # Offline support
    offline_package_id = models.UUIDField(null=True, blank=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=False)

class ExamAttempt(TenantAwareModel, TimeStampedModel):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    student = models.ForeignKey('users.Student', on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    is_submitted = models.BooleanField(default=False)
    
    # Sync fields
    device_id = models.CharField(max_length=255, null=True, blank=True)
    is_offline = models.BooleanField(default=False)
    sync_status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('synced', 'Synced'), ('failed', 'Failed')],
        default='pending'
    )

class StudentAnswer(TenantAwareModel, TimeStampedModel):
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer_text = models.TextField(null=True, blank=True)
    selected_options = models.JSONField(null=True, blank=True)  # For MCQ
    is_correct = models.BooleanField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    teacher_feedback = models.TextField(null=True, blank=True)