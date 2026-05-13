# exams/views.py - Add these endpoints

from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Exam, ExamAttempt
import json

@login_required
def exam_list_for_upload(request):
    """HTMX endpoint for exam list in upload form"""
    exams = Exam.objects.filter(
        teacher=request.user.teacher_profile,
        status='published'
    ).order_by('-created_at')[:20]
    
    return render(request, 'exams/partials/exam_list_items.html', {'exams': exams})

@login_required
def search_exams_for_upload(request):
    """HTMX endpoint for searching exams"""
    query = request.GET.get('q', '')
    exams = Exam.objects.filter(
        teacher=request.user.teacher_profile,
        title__icontains=query,
        status='published'
    )[:10]
    
    return render(request, 'exams/partials/exam_list_items.html', {'exams': exams})

@login_required
def recent_uploads(request):
    """HTMX endpoint for recent uploads"""
    search = request.GET.get('search', '')
    attempts = ExamAttempt.objects.filter(
        exam__teacher=request.user.teacher_profile
    ).order_by('-created_at')
    
    if search:
        attempts = attempts.filter(
            student__user__first_name__icontains=search
        ) | attempts.filter(
            student__user__last_name__icontains=search
        )
    
    attempts = attempts[:10]
    
    return render(request, 'exams/partials/recent_uploads.html', {'attempts': attempts})

@login_required
@require_POST
def upload_results(request):
    """Handle exam results upload"""
    try:
        exam_id = request.POST.get('exam_id')
        file = request.FILES.get('file')
        
        # Process the file and save results
        # This is where you'd implement your file processing logic
        
        return JsonResponse({
            'success': True,
            'count': 10,  # Return actual count
            'message': 'Results uploaded successfully'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)