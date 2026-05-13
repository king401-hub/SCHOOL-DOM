# CBT Exam System - Implementation Guide

This document provides a comprehensive guide for the Computer-Based Testing (CBT) exam system that has been integrated into the Virtual School Platform.

## Overview

The CBT system provides a complete exam taking experience with:
- Real-time countdown timer
- Question navigation grid
- Automatic answer saving
- Exam submission with results review
- Student information display
- Instruction management

## Project Structure

### Frontend Components (`backend/frontend/src/components/ExamCBT/`)

1. **ExamCBT.jsx** - Main exam container component
   - Manages exam state and timing
   - Handles question navigation
   - Manages answer saving and submission
   - Implements auto-submit on time expiration

2. **ExamHeader.jsx** - Top header component
   - Displays exam title and CBT logo
   - Shows countdown timer
   - Contains submit button

3. **ExamSidebar.jsx** - Left navigation sidebar
   - Navigation tabs (Instructions, Questions, Submit)
   - Displays answer statistics
   - Question progress indicator

4. **QuestionDisplay.jsx** - Main question area
   - Displays question text and image
   - Radio button options
   - Clear response button
   - Previous/Next navigation

5. **StudentInfo.jsx** - Right sidebar with student info
   - Student profile section
   - Question navigator grid
   - Answered/Unanswered status indicators
   - Quick navigation to any question

6. **SubmitModal.jsx** - Submission confirmation modal
   - Summary of answered questions
   - Warning for unanswered questions
   - Submit confirmation dialog

7. **ExamsList.jsx** - Exams listing page
   - Shows available exams
   - Start exam button
   - Exam details

8. **ExamResult.jsx** - Results page
   - Score display with gauge
   - Performance summary
   - Detailed answer review
   - Download results option

9. **ExamCBT.css** - Main stylesheet
   - All styling for exam interface
   - Responsive design

10. **ExamResult.css** - Results page styling
    - Score card styling
    - Review section styling
    - Responsive layout

11. **ExamsList.css** - Exams list styling
    - Card-based layout
    - Responsive grid

### Backend API Endpoints (`backend/exams/`)

#### URLs Configuration (`exams/urls.py`)
```
GET    /api/exams/list/                    - Get available exams
POST   /api/exams/<exam_id>/start/         - Start new exam attempt
GET    /api/exams/attempt/<attempt_id>/    - Get exam attempt details
POST   /api/exams/attempt/<attempt_id>/answer/     - Save answer
POST   /api/exams/attempt/<attempt_id>/submit/     - Submit exam
GET    /api/exams/attempt/<attempt_id>/timer-sync/ - Sync timer
GET    /api/exams/result/<attempt_id>/    - Get exam results
```

#### Views (`exams/exam_views.py`)

1. **ExamListView** - List available exams
   - Filters by publication status
   - Checks exam availability dates
   - Tenant-aware

2. **StartExamView** - Start new exam attempt
   - Validates exam availability
   - Checks attempt limits
   - Creates ExamAttempt record
   - Fetches questions

3. **ExamAttemptDetailView** - Get exam details with questions
   - Returns exam metadata
   - Returns all questions
   - Returns student's existing answers
   - Calculates remaining time

4. **SaveExamAnswerView** - Save single answer
   - Creates/updates StudentAnswer
   - Saves selected options or text
   - Async operation

5. **SubmitExamView** - Submit exam
   - Marks attempt as submitted
   - Calculates score
   - Records correct/incorrect for each answer

6. **ExamResultView** - Get exam results
   - Returns score breakdown
   - Includes detailed answer review
   - Shows correct answers and explanations
   - Calculates grade

7. **exam_timer_sync** - Sync timer with server
   - Handles auto-submit on timeout
   - Prevents time cheating

#### Serializers (`exams/serializers.py`)

- **QuestionSerializer** - Serializes exam questions
- **ExamSerializer** - Serializes exam metadata
- **StudentAnswerSerializer** - Serializes student answers
- **ExamAttemptSerializer** - Serializes exam attempt
- **ExamAttemptDetailSerializer** - Complete exam attempt with questions
- **ExamResultSerializer** - Exam results with review

## Integration Steps

### 1. Database Setup

Run Django migrations to create necessary tables:

```bash
python manage.py makemigrations exams
python manage.py migrate exams
```

Ensure these models exist in `exams/models.py`:
- `Exam` - Exam definitions
- `ExamAttempt` - Student exam attempts
- `Question` - Individual questions
- `StudentAnswer` - Student responses
- `ExamType` - Exam type categories
- `QuestionBank` - Question collections

### 2. URL Configuration

The exam URLs have been added to `config/urls.py`:
```python
path('api/exams/', include('exams.urls')),
```

### 3. Frontend Routing

The App.jsx has been updated with:
- Route matching for `/exams` - Exam list page
- Route matching for `/exam/:attemptId` - Active exam
- Route matching for `/exam-result/:attemptId` - Results page

Routes are added to STUDENT_ROUTES for navigation menu.

### 4. Admin Setup

1. Add exams to your admin panel
2. Create exam questions with options
3. Set exam timing and availability
4. Publish exams

## Usage Flow

### For Students

1. **View Available Exams**
   - Navigate to `/exams`
   - See list of available exams
   - Click "Start Exam" to begin

2. **Take Exam**
   - Answers are auto-saved
   - Use question navigator to jump between questions
   - View instructions before starting
   - Monitor remaining time

3. **Submit Exam**
   - Click "Submit Test" when ready
   - Confirm submission in modal
   - Auto-submit when time expires

4. **View Results**
   - Redirected to results page after submission
   - See score and grade
   - Review all questions with explanations
   - Download results

### Question Types Supported

Currently supports:
- Multiple Choice (MCQ) with A/B/C/D/E options
- Expandable to: True/False, Short Answer, Essay

## API Response Examples

### Start Exam Response
```json
{
  "attempt_id": 1,
  "exam_id": 5,
  "start_time": "2024-05-05T10:30:00Z",
  "duration_minutes": 60,
  "question_count": 50
}
```

### Get Exam Attempt Response
```json
{
  "attempt": {
    "id": 1,
    "start_time": "2024-05-05T10:30:00Z",
    "is_completed": false
  },
  "exam": {
    "id": 5,
    "title": "General Knowledge",
    "duration_minutes": 60,
    "instructions": "<p>Read all questions carefully...</p>"
  },
  "questions": [
    {
      "id": 1,
      "text": "Which of the following is the capital of France?",
      "image": null,
      "options": ["Berlin", "Madrid", "Paris", "Rome"],
      "question_type": "mcq",
      "points": 1
    }
  ],
  "student": {
    "id": "STU000001",
    "name": "John Doe",
    "avatar": null
  },
  "answers": {
    "1": 2
  },
  "time_remaining_seconds": 3600
}
```

### Submit Exam Response
```json
{
  "success": true,
  "attempt_id": 1,
  "score": 45,
  "total_points": 50,
  "percentage": 90
}
```

### Get Results Response
```json
{
  "attempt_id": 1,
  "exam_title": "General Knowledge",
  "score": 45,
  "total_points": 50,
  "percentage": 90,
  "grade": "A",
  "is_passed": true,
  "submitted_at": "2024-05-05T11:35:00Z",
  "answers_review": [
    {
      "question_number": 1,
      "question_text": "Which of the following is the capital of France?",
      "user_answer": 2,
      "correct_answer": 2,
      "is_correct": true,
      "points_earned": 1,
      "total_points": 1,
      "explanation": "Paris is the capital of France."
    }
  ]
}
```

## Configuration

### Model Settings (in Exam)

- `duration_minutes` - Exam time limit
- `shuffle_questions` - Randomize question order
- `show_results_immediately` - Show results right after submission
- `allow_retake` - Allow multiple attempts
- `max_attempts` - Maximum number of attempts
- `is_published` - Make exam visible to students

### Passing Grade

Default passing grade is set to 40% in `ExamResultView._calculate_grade()`

To modify:
1. Edit `backend/exams/exam_views.py`
2. Change the `is_passed` calculation in `ExamResultView.get()`

## Features

### Timer Management
- Real-time countdown display
- Server-side time validation
- Automatic submission on timeout
- Client-side timer sync with server

### Answer Management
- Automatic saving of answers
- Clear response option
- Support for multiple answer types
- Review before submission

### Navigation
- Question grid with status indicators
- Direct jump to any question
- Next/Previous buttons
- Section-based organization

### Results
- Score calculation with points
- Grade assignment (A/B/C/D/F)
- Pass/Fail determination
- Detailed answer review with explanations

## Customization

### Adding Question Images

Questions support image display. To add:

```json
{
  "id": 1,
  "text": "Based on the image below...",
  "image": "/media/question_images/image.jpg",
  "options": ["Option A", "Option B"],
  "question_type": "mcq"
}
```

### Custom Styling

Edit `ExamCBT.css` to customize:
- Colors and gradients
- Font sizes and styles
- Layout and spacing
- Responsive breakpoints

### Theme Support

Supports dark/light theme switching. Update CSS variables to theme the interface.

## Troubleshooting

### Exam Not Loading
1. Check if exam is published
2. Verify exam dates are correct
3. Check user permissions
4. Review browser console for errors

### Timer Issues
1. Verify server time is correct
2. Check timer-sync endpoint
3. Review browser console

### Answers Not Saving
1. Check network connectivity
2. Verify API endpoint is working
3. Check user authentication
4. Review browser console errors

## Performance Considerations

1. **Lazy Load Questions** - Consider pagination for 100+ questions
2. **Timer Updates** - Currently every 1 second (adjustable)
3. **Auto-save Debouncing** - Avoid excessive API calls
4. **Image Optimization** - Compress question images
5. **Caching** - Consider caching exam metadata

## Security

1. **Server-Side Timer** - Timer is validated on server
2. **Token Validation** - All requests require authentication
3. **Attempt Verification** - Verify student owns attempt
4. **Anti-Cheat** - Timer sync prevents time manipulation
5. **Data Validation** - All inputs are validated

## Future Enhancements

1. Offline mode with sync
2. Question randomization
3. Adaptive testing
4. Proctoring integration
5. Advanced reporting
6. AI-powered grading for essays
7. Practice mode
8. Detailed analytics
9. Mobile app support
10. Real-time class monitoring

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review browser console errors
3. Check Django logs
4. Verify API endpoints are working
5. Test with sample data

## License

This component is part of the Virtual School Platform and follows the same license terms.
