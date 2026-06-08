from django.urls import path
from . import exam_views

app_name = 'exams'

urlpatterns = [
    # Exam endpoints
    path('cbt-entry/', exam_views.StudentCbtEntryView.as_view(), name='student_cbt_entry'),
    path('cbt/offline-sync/', exam_views.cbt_offline_sync_package, name='cbt_offline_sync_package'),
    path('cbt/exams/<int:exam_id>/pin/regenerate/', exam_views.cbt_regenerate_exam_pin, name='cbt_regenerate_exam_pin'),
    path('cbt/offline-results/', exam_views.cbt_offline_result_ingest, name='cbt_offline_result_ingest'),
    path('cbt/package/export/', exam_views.cbt_exam_package_export, name='cbt_exam_package_export'),
    path('cbt/package/results/import/', exam_views.cbt_results_package_import, name='cbt_results_package_import'),
    path('list/', exam_views.ExamListView.as_view(), name='exam_list'),
    path('<int:exam_id>/start/', exam_views.StartExamView.as_view(), name='start_exam'),
    
    # Exam attempt endpoints
    path('attempt/<int:attempt_id>/', exam_views.ExamAttemptDetailView.as_view(), name='attempt_detail'),
    path('attempt/<int:attempt_id>/answer/', exam_views.SaveExamAnswerView.as_view(), name='save_answer'),
    path('attempt/<int:attempt_id>/flag-question/', exam_views.FlagExamQuestionView.as_view(), name='flag_question'),
    path('attempt/<int:attempt_id>/submit/', exam_views.SubmitExamView.as_view(), name='submit_exam'),
    path('attempt/<int:attempt_id>/timer-sync/', exam_views.exam_timer_sync, name='timer_sync'),
    path('offline/sync/', exam_views.sync_offline_exam_attempt, name='sync_offline_exam_attempt'),
    
    # Results
    path('result/<int:attempt_id>/', exam_views.ExamResultView.as_view(), name='exam_result'),
]
