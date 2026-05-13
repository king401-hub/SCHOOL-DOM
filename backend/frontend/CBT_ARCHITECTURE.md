# CBT Exam System - Architecture & Component Map

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  App.jsx - Route Handler                                  │ │
│  │  - /exams → ExamsList                                     │ │
│  │  - /exam/:id → ExamCBT                                    │ │
│  │  - /exam-result/:id → ExamResult                          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                           ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                 ExamCBT.jsx (Main Container)              ││
│  │  - Manages exam state and timing                          ││
│  │  - Handles answer saving and submission                   ││
│  │  - Implements auto-submit on timeout                      ││
│  └─────────────────────────────────────────────────────────────┘│
│         ↑                    ↑                    ↑              │
│    ┌────────┐         ┌──────────┐        ┌───────────┐         │
│    │ Header │         │ Sidebar  │        │QuestionDis││         │
│    │        │         │          │        │play      ││         │
│    └────────┘         └──────────┘        └───────────┘         │
│    - Timer            - Nav Tabs          - Questions            │
│    - Submit Btn       - Progress          - Options              │
│                       - Instructions      - Clear Btn            │
│                                           - Previous/Next        │
│                                           └──────────────┘       │
│                              ↑                                    │
│                        ┌──────────────┐                          │
│                        │ StudentInfo  │                          │
│                        │              │                          │
│                        │ - Profile    │                          │
│                        │ - Navigator  │                          │
│                        │   Grid       │                          │
│                        └──────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
                           ↓ API Calls ↓
┌─────────────────────────────────────────────────────────────────┐
│               BACKEND API (Django Rest Framework)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  /api/exams/list/                   → ExamListView             │
│  /api/exams/<id>/start/             → StartExamView            │
│  /api/exams/attempt/<id>/           → ExamAttemptDetailView    │
│  /api/exams/attempt/<id>/answer/    → SaveExamAnswerView       │
│  /api/exams/attempt/<id>/submit/    → SubmitExamView           │
│  /api/exams/attempt/<id>/timer-sync/→ exam_timer_sync()        │
│  /api/exams/result/<id>/            → ExamResultView           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                           ↓ Database ↓
┌─────────────────────────────────────────────────────────────────┐
│                    DATABASE (SQLite/PostgreSQL)                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │    Exam      │  │  ExamAttempt │  │  Question    │          │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤          │
│  │ id           │  │ id           │  │ id           │          │
│  │ title        │  │ exam_id      │  │ text         │          │
│  │ duration     │  │ student_id   │  │ options      │          │
│  │ max_attempts │  │ start_time   │  │ correct_ans  │          │
│  │ is_published │  │ is_submitted │  │ points       │          │
│  │ ...          │  │ ...          │  │ ...          │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         ↑                  ↑                  ↑                 │
│         └──────────────────┴──────────────────┘                 │
│                                                                 │
│  ┌──────────────────────────────────┐                           │
│  │      StudentAnswer               │                           │
│  ├──────────────────────────────────┤                           │
│  │ id                               │                           │
│  │ attempt_id (FK: ExamAttempt)     │                           │
│  │ question_id (FK: Question)       │                           │
│  │ selected_options (JSON)          │                           │
│  │ is_correct (Boolean)             │                           │
│  │ score (Float)                    │                           │
│  └──────────────────────────────────┘                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Component Communication Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ User Navigation                                                 │
├─────────────────────────────────────────────────────────────────┤

1. USER NAVIGATES TO /exams
   ↓
   App.jsx → ExamsList
   ↓
   Fetch: GET /api/exams/list/
   ↓
   Display: List of available exams
   ↓
   User clicks: "Start Exam"

2. USER STARTS EXAM
   ↓
   ExamsList → API: POST /api/exams/<id>/start/
   ↓
   Response: { attempt_id: 1, ... }
   ↓
   Navigate to: /exam/1
   ↓
   App.jsx → ExamCBT (with attemptId)

3. EXAM LOADS
   ↓
   ExamCBT Component Mounts
   ↓
   useEffect: Fetch GET /api/exams/attempt/1/
   ↓
   Response includes:
      - Exam metadata
      - All questions
      - Previous answers (if any)
      - Time remaining
   ↓
   Set state and render:
      ├─ ExamHeader (shows timer)
      ├─ ExamSidebar (navigation tabs)
      ├─ QuestionDisplay (question #1)
      └─ StudentInfo (profile & navigator)

4. USER ANSWERS QUESTION
   ↓
   QuestionDisplay → onChange event
   ↓
   setLocalAnswer state
   ↓
   handleSaveAnswer called
   ↓
   POST /api/exams/attempt/1/answer/
   {
      question_id: 1,
      selected_options: 2
   }
   ↓
   Answer saved to database
   ↓
   StudentInfo grid updates status

5. USER NAVIGATES
   ↓
   Option A: Click "Save & Next" button
      ↓
      setCurrentQuestionIndex++
      ↓
      QuestionDisplay re-renders with new question
   
   Option B: Click question number in navigator
      ↓
      setCurrentQuestionIndex = clicked index
      ↓
      QuestionDisplay re-renders

6. TIMER COUNTDOWN
   ↓
   useEffect timer: setInterval every 1 second
   ↓
   setTimeRemaining(prev - 1)
   ↓
   ExamHeader re-renders with new time
   ↓
   When time reaches 0:
      ↓
      handleAutoSubmit()
      ↓
      Exam submitted automatically

7. USER SUBMITS EXAM
   ↓
   User clicks: "Submit Test" button
   ↓
   SubmitModal displayed
   ↓
   User confirms
   ↓
   POST /api/exams/attempt/1/submit/
   ↓
   Backend:
      - Marks attempt as submitted
      - Calculates score
      - Records correct/incorrect
   ↓
   Response: { success: true, score: 45, ... }
   ↓
   Navigate to: /exam-result/1

8. VIEW RESULTS
   ↓
   ExamResult component mounts
   ↓
   useEffect: Fetch GET /api/exams/result/1/
   ↓
   Response includes:
      - Score & percentage
      - Grade
      - Detailed answer review
      - Explanations
   ↓
   Render:
      - Score gauge
      - Performance summary
      - Answer review with expand/collapse
      - Download button

└─────────────────────────────────────────────────────────────────┘
```

## State Management

### ExamCBT Main State

```javascript
const [examData, setExamData] = useState(null)           // Exam metadata
const [attemptData, setAttemptData] = useState(null)     // Attempt info
const [questions, setQuestions] = useState([])           // All questions
const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0)  // Current Q
const [answers, setAnswers] = useState({})               // {questionId: answer}
const [timeRemaining, setTimeRemaining] = useState(0)    // Seconds left
const [loading, setLoading] = useState(true)             // Loading state
const [showSubmitModal, setShowSubmitModal] = useState(false)  // Modal toggle
const [navSection, setNavSection] = useState("questions") // Tab: instructions/questions/submit
const [studentInfo, setStudentInfo] = useState(null)     // Student data
```

## Data Flow Diagram

```
ExamCBT (Parent)
    ├─ examData ────────────→ ExamHeader (title, duration)
    ├─ timeRemaining ──────→ ExamHeader (timer display)
    ├─ questions ──────────→ QuestionDisplay (current question)
    ├─ currentQuestionIndex→ QuestionDisplay (which question)
    ├─ studentInfo ────────→ StudentInfo (profile)
    ├─ answers ────────────→ StudentInfo (status for navigator)
    ├─ answers ────────────→ QuestionDisplay (current answer)
    └─ navSection ─────────→ ExamSidebar (active tab)

Event Handlers:
    ├─ handleSaveAnswer() ─→ API: POST answer
    ├─ handleClearResponse()→ API: POST answer(null)
    ├─ handleNavigateToQuestion() → setCurrentQuestionIndex
    ├─ handleSaveAndNext() → setCurrentQuestionIndex++
    ├─ handlePrevious() → setCurrentQuestionIndex--
    ├─ handleSubmitExam() → API: POST submit
    └─ useEffect(timer) → setTimeRemaining-- or autoSubmit()
```

## API Request/Response Cycle

```
REQUEST: POST /api/exams/attempt/1/answer/
{
    "question_id": 1,
    "selected_options": 2
}
           ↓
     BACKEND PROCESSING
           ↓
     - Verify attempt exists
     - Verify student owns attempt
     - Create/Update StudentAnswer
           ↓
RESPONSE: 200 OK
{
    "success": true,
    "answer_id": 5
}
           ↓
FRONTEND UPDATE
     - setAnswers (merge new answer)
     - Disable save button
     - Update question navigator status
```

## File Organization

```
backend/
├── exams/
│   ├── __init__.py
│   ├── models.py (Exam, Question, ExamAttempt, StudentAnswer)
│   ├── admin.py
│   ├── views.py
│   ├── serializers.py (7 serializers)
│   ├── exam_views.py (7 view classes)
│   ├── urls.py (7 routes)
│   ├── tests.py
│   ├── migrations/
│   └── management/
│
└── frontend/
    ├── src/
    │   ├── App.jsx (Updated with exam routes)
    │   ├── App.jsx.css
    │   └── components/
    │       └── ExamCBT/
    │           ├── ExamCBT.jsx
    │           ├── ExamHeader.jsx
    │           ├── ExamSidebar.jsx
    │           ├── QuestionDisplay.jsx
    │           ├── StudentInfo.jsx
    │           ├── SubmitModal.jsx
    │           ├── ExamsList.jsx
    │           ├── ExamResult.jsx
    │           ├── ExamCBT.css
    │           ├── ExamResult.css
    │           ├── ExamsList.css
    │           └── index.js
    │
    ├── CBT_IMPLEMENTATION_GUIDE.md
    ├── CBT_QUICK_SETUP.md
    └── CBT_ARCHITECTURE.md (this file)
```

## Styling Hierarchy

```
App.jsx
└── ExamCBT.jsx
    ├── ExamHeader.jsx
    │   └── .exam-header (flexbox layout)
    │       ├── .exam-header-left (logo)
    │       ├── .exam-header-center (title)
    │       └── .exam-header-right (timer + button)
    │
    ├── ExamSidebar.jsx
    │   └── .exam-sidebar (fixed width)
    │       ├── .sidebar-header
    │       └── .sidebar-menu
    │           ├── .sidebar-item.instructions
    │           ├── .sidebar-item.questions (active)
    │           └── .sidebar-item.submit
    │
    ├── QuestionDisplay.jsx
    │   └── .question-display (flex 1, scrollable)
    │       ├── .question-header
    │       ├── .question-content
    │       │   ├── .question-text
    │       │   ├── .question-options
    │       │   │   └── .option-label (radio)
    │       │   └── .btn-clear-response
    │       └── .question-navigation
    │           ├── .btn-previous
    │           └── .btn-save-next
    │
    └── StudentInfo.jsx
        └── .student-info (fixed width, scrollable)
            ├── .student-profile
            ├── .question-navigator
            │   ├── .navigator-header
            │   ├── .question-grid
            │   │   └── .question-number (5 per row)
            │   │       ├── .answered (green)
            │   │       ├── .current (blue)
            │   │       └── .unanswered (gray)
            │   └── .navigator-legend
            └── .navigator-stats
```

## Browser API Usage

```
Fetches:
- GET /api/exams/list/
- POST /api/exams/{id}/start/
- GET /api/exams/attempt/{id}/
- POST /api/exams/attempt/{id}/answer/
- POST /api/exams/attempt/{id}/submit/
- GET /api/exams/attempt/{id}/timer-sync/
- GET /api/exams/result/{id}/

Authentication:
- Bearer token in Authorization header
- From localStorage (access token)

State Persistence:
- answers: stored in component state
- session: stored in localStorage

LocalStorage Keys:
- schooldom.session (user session)
- schooldom.ui_theme (dark/light mode)
```

## Performance Considerations

```
Optimizations:
- Questions lazy loaded on mount
- useCallback for event handlers
- useMemo for calculations
- useEffect cleanup for timer
- CSS Grid for question navigator

Potential Bottlenecks:
- 100+ questions: Consider pagination
- Timer sync: Every 1 second
- Auto-save: Debounce if needed
- Large images: Compress question images
```

## Security Flow

```
1. USER LOGIN
   ↓
   Session created with JWT tokens
   ↓
   Access token stored in localStorage

2. EXAM ATTEMPT
   ↓
   Each API request includes Authorization header
   ↓
   Backend verifies JWT token
   ↓
   Backend verifies attempt ownership

3. ANSWER SAVE
   ↓
   API validates attempt belongs to user
   ↓
   API validates question is in exam
   ↓
   Answer saved with validation

4. SUBMIT EXAM
   ↓
   API verifies exam not already submitted
   ↓
   API calculates score server-side
   ↓
   Time verified on server

5. VIEW RESULTS
   ↓
   API verifies exam submitted
   ↓
   API verifies result belongs to user
   ↓
   Results sent with all details
```

## Error Handling

```
Frontend Error Handlers:
- try/catch in useEffect
- API error responses
- Missing data validation
- Network error handling

Backend Validation:
- Exam publish status
- Attempt exists
- Attempt belongs to user
- Exam availability dates
- Attempt not submitted
- Time limits respected

User Feedback:
- Loading states
- Error messages
- Toast notifications (future)
- Form validation
```

---

This architecture ensures:
✓ Clean separation of concerns
✓ Scalable component structure
✓ Secure API communication
✓ Responsive design
✓ State management best practices
