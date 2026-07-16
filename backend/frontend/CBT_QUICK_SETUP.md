# CBT Exam System - Quick Setup Guide

## Prerequisites

Before setting up exams, ensure:
1. Django migrations are run: `python manage.py migrate`
2. Admin user is created: `python manage.py createsuperuser`
3. Backend is running: `python manage.py runserver`
4. Frontend is running in development mode

## Step 1: Access Django Admin

1. Go to `http://localhost:8000/admin/`
2. Login with your admin credentials

## Step 2: Create Exam Type

1. Go to **Exams → Exam Types**
2. Click **Add Exam Type** 
3. Enter name: "MCQ" (for Multiple Choice)
4. Click **Save**

## Step 3: Create Question Bank

1. Go to **Exams → Question Banks**
2. Click **Add Question Bank**
3. Fill in:
   - **Name**: "General Knowledge Bank"
   - **Subject**: Select a subject
   - **Teacher**: Select a teacher
   - **Is Shared**: Check if you want to share
4. Click **Save**

## Step 4: Create Questions

1. Go to **Exams → Questions**
2. Click **Add Question**
3. Fill in the following for each question:
   - **Question Type**: "mcq" (Multiple Choice)
   - **Text**: "Which of the following is the capital of France?"
   - **Points**: 1
   - **Options**: Enter as JSON:
     ```json
     ["Berlin", "Madrid", "Paris", "Rome"]
     ```
   - **Correct Answer**: "Paris" (or index: 2)
   - **Explanation**: "Paris is the capital of France..."
4. Click **Save**

### Create Multiple Questions

Repeat Step 4 to create at least 10-50 questions. For example:

**Question 2:**
- Text: "What is 2 + 2?"
- Options: `["2", "3", "4", "5"]`
- Correct Answer: "4"

**Question 3:**
- Text: "Which planet is known as the Red Planet?"
- Options: `["Venus", "Mars", "Jupiter", "Saturn"]`
- Correct Answer: "Mars"

## Step 5: Create Exam

1. Go to **Exams → Exams**
2. Click **Add Exam**
3. Fill in:
   - **Title**: "General Knowledge Mock Exam"
   - **Subject**: Select from dropdown
   - **Class Group**: Select class (optional)
   - **Teacher**: Select teacher
   - **Exam Type**: "MCQ"
   - **Start Date**: Set to now or past date
   - **End Date**: Set to future date
   - **Duration Minutes**: 60
   - **Shuffle Questions**: Check if you want random order
   - **Show Results Immediately**: Check to show results after submit
   - **Allow Retake**: Check to allow multiple attempts
   - **Max Attempts**: 1 or 2
   - **Is Published**: ✓ Check this!
4. Click **Save**

## Step 6: Add Questions to Exam

1. After creating the exam, scroll down to the questions section
2. Select the question bank you created in Step 3
3. Click **Add**
4. Select all questions you want to include
5. Click **Save**

## Step 7: Test the Exam Interface

### As Admin
1. Create a test user account
2. Go to `http://localhost:3000` (frontend)
3. Sign in as the test user

### As Student
1. Navigate to `/exams` in the frontend
2. Should see "General Knowledge Mock Exam" in the list
3. Click "Start Exam"
4. Test the exam interface:
   - Answer questions
   - Navigate between questions
   - Use the question grid navigator
   - Submit the exam
   - View results

## Troubleshooting

### Exam Not Showing

Check:
- [ ] Exam is published (Is Published = checked)
- [ ] Start date is today or earlier
- [ ] End date is today or later
- [ ] Exam has questions assigned
- [ ] Questions have options set

### Questions Not Loading

Check:
- [ ] Questions are added to the exam
- [ ] Questions have `question_type` set to "mcq"
- [ ] Questions have `options` in JSON format
- [ ] Questions have `correct_answer` set

### Answers Not Saving

Check:
- [ ] API endpoint `/api/exams/attempt/<id>/answer/` is accessible
- [ ] User is authenticated
- [ ] Browser console for error messages

## Sample Exam Data

### SQL to Create Sample Questions

If you want to use Django shell to create questions quickly:

```python
from exams.models import Question, QuestionBank

# Get question bank
qb = QuestionBank.objects.first()

# Create questions
questions_data = [
    {
        "text": "What is the capital of France?",
        "options": ["Berlin", "Madrid", "Paris", "Rome"],
        "correct_answer": "Paris",
        "points": 1
    },
    {
        "text": "What is 2 + 2?",
        "options": ["2", "3", "4", "5"],
        "correct_answer": "4",
        "points": 1
    },
    {
        "text": "Which planet is closest to the sun?",
        "options": ["Venus", "Mercury", "Earth", "Mars"],
        "correct_answer": "Mercury",
        "points": 1
    }
]

for data in questions_data:
    q = Question.objects.create(
        question_type="mcq",
        text=data["text"],
        options=data["options"],
        correct_answer=data["correct_answer"],
        points=data["points"]
    )
    qb.questions.add(q)
```

## Next Steps

1. **Create More Exams**: Follow steps 1-6 to create different exams
2. **Test Different Scenarios**:
   - Multiple choice questions
   - Different time limits
   - Multiple attempts
3. **Customize Styling**: Edit `ExamCBT.css` to match your branding
4. **Add More Question Types**: Extend to support True/False, Short Answer, etc.
5. **Monitor Results**: View student results and analytics

## Features to Test

- [ ] Timer countdown
- [ ] Question navigation
- [ ] Answer saving
- [ ] Clear response button
- [ ] Submit confirmation modal
- [ ] Results page
- [ ] Score calculation
- [ ] Grade assignment
- [ ] Answer review with explanations
- [ ] Responsive design on mobile

## Admin Tips

1. **Batch Create Questions**: Use Django admin's "Add another" feature
2. **Import Questions**: Write a management command for bulk import
3. **Group Related Exams**: Use naming conventions (e.g., "Math_Final_2024")
4. **Set Realistic Timings**: Consider difficulty when setting duration
5. **Review Before Publishing**: Always test exams before publishing

## Common Mistakes to Avoid

❌ Forgetting to publish the exam
❌ Not setting proper date ranges
❌ Missing options in JSON format
❌ Not assigning questions to the exam
❌ Setting incorrect correct_answer values
❌ Not checking "Show Results Immediately" for feedback

## Support

For issues:
1. Check Django logs: `python manage.py runserver`
2. Check browser console for frontend errors
3. Verify all required fields are filled
4. Test API endpoints directly with Postman
