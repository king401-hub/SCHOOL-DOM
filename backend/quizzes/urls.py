from django.urls import path

from . import views

urlpatterns = [
    path("teacher/", views.TeacherQuizListCreate.as_view(), name="quiz_teacher_list"),
    path("teacher/<int:quiz_id>/", views.TeacherQuizDetail.as_view(), name="quiz_teacher_detail"),
    path("teacher/<int:quiz_id>/submissions/", views.TeacherQuizSubmissions.as_view(), name="quiz_teacher_submissions"),
    path("personal/resource-folder/", views.PersonalQuizResourceFolder.as_view(), name="personal_quiz_resource_folder"),
    path("personal/resource-folder/<int:folder_id>/", views.PersonalQuizResourceFolderDetail.as_view(), name="personal_quiz_resource_folder_detail"),
    path("personal/resource-folder/<int:folder_id>/questions/", views.PersonalQuizResourceQuestion.as_view(), name="personal_quiz_resource_question"),
    path("personal/resource-folder/<int:folder_id>/questions/<int:question_id>/", views.PersonalQuizResourceQuestion.as_view(), name="personal_quiz_resource_question_detail"),
    path("student/", views.StudentQuizList.as_view(), name="quiz_student_list"),
    path("student/<int:quiz_id>/", views.StudentQuizDetail.as_view(), name="quiz_student_detail"),
    path("student/<int:quiz_id>/submit/", views.StudentQuizSubmit.as_view(), name="quiz_student_submit"),
    path("student/<int:quiz_id>/flag-question/", views.StudentQuizFlagQuestion.as_view(), name="quiz_student_flag_question"),
    path("student/<int:quiz_id>/result/", views.StudentQuizResult.as_view(), name="quiz_student_result"),
    path("personal/options/", views.PersonalQuizOptions.as_view(), name="personal_quiz_options"),
    path("personal/generate/", views.PersonalQuizGenerate.as_view(), name="personal_quiz_generate"),
    path("personal/<int:attempt_id>/submit/", views.PersonalQuizSubmit.as_view(), name="personal_quiz_submit"),
    path("personal/<int:attempt_id>/flag-question/", views.PersonalQuizFlagQuestion.as_view(), name="personal_quiz_flag_question"),
    path("personal/history/", views.PersonalQuizHistory.as_view(), name="personal_quiz_history"),
]
