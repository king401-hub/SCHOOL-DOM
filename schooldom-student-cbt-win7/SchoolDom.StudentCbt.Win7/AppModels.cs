using System;
using System.Collections.Generic;

namespace SchoolDom.StudentCbt.Win7
{
    /// <summary>
    /// Student record from the server
    /// </summary>
    public class StudentRecord
    {
        // Primary fields (snake_case from server)
        public string id { get; set; }
        public string student_id { get; set; }
        public string full_name { get; set; }
        public string first_name { get; set; }
        public string last_name { get; set; }
        public string class_name { get; set; }
        public string class_label { get; set; }
        public string profile_picture { get; set; }
        public string profile_picture_data { get; set; }
        public string photo_data { get; set; }
        public string photo_url { get; set; }
        public string email { get; set; }
        
        // Helper properties for consistent access (PascalCase)
        public string Id => id ?? "";
        public string StudentId => student_id ?? "";
        public string FullName => full_name ?? "";
        public string FirstName => first_name ?? "";
        public string LastName => last_name ?? "";
        public string ClassName => class_name ?? "";
        public string ClassLabel => class_label ?? "";
        public string ProfilePicture => profile_picture ?? "";
        public string ProfilePictureData => profile_picture_data ?? "";
        public string PhotoData => photo_data ?? "";
        public string PhotoUrl => photo_url ?? "";
        public string Email => email ?? "";
        
        // Display name (prioritize full_name, then first+last, then student_id)
        public string DisplayName
        {
            get
            {
                if (!string.IsNullOrWhiteSpace(FullName)) return FullName;
                if (!string.IsNullOrWhiteSpace(FirstName) || !string.IsNullOrWhiteSpace(LastName))
                {
                    return $"{FirstName} {LastName}".Trim();
                }
                return StudentId;
            }
        }
        
        // Initials for avatar
        public string Initials
        {
            get
            {
                var parts = DisplayName.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length == 0) return "SD";
                if (parts.Length == 1) return parts[0].Substring(0, Math.Min(2, parts[0].Length)).ToUpperInvariant();
                return (parts[0][0].ToString() + parts[1][0].ToString()).ToUpperInvariant();
            }
        }
    }

    /// <summary>
    /// Exam information from the server
    /// </summary>
    public class ExamInfo
    {
        // Primary fields (snake_case from server)
        public string id { get; set; }
        public string title { get; set; }
        public string subject { get; set; }
        public int duration_seconds { get; set; }
        public string instructions { get; set; }
        public List<QuestionRecord> questions { get; set; }
        
        // Helper properties (PascalCase)
        public string Id => id ?? "";
        public string Title => title ?? "";
        public string Subject => subject ?? "";
        public int DurationSeconds => duration_seconds;
        public string Instructions => instructions ?? "";
        public List<QuestionRecord> Questions => questions ?? new List<QuestionRecord>();
        
        // Helper for duration in minutes
        public int DurationMinutes => Math.Max(1, duration_seconds / 60);
        
        // Helper for question count
        public int QuestionCount => Questions.Count;
    }

    /// <summary>
    /// Question record from the server
    /// </summary>
    public class QuestionRecord
    {
        private string _id;
        
        // Primary fields (supports both PascalCase and snake_case)
        public string Id 
        { 
            get => _id ?? "";
            set => _id = value; 
        }
        
        public string id 
        { 
            get => Id;
            set => Id = value;
        }
        
        public string text { get; set; }
        public string type { get; set; }
        public double points { get; set; }
        public List<string> options { get; set; }
        
        // Helper properties (PascalCase)
        public string Text => text ?? "";
        public string Type => type?.ToLowerInvariant() ?? "multiple_choice";
        public double Points => points;
        public List<string> Options => options ?? new List<string>();
        
        // Question type checks
        public bool IsMultipleChoice => Type == "multiple_choice" || Type == "mcq" || Type == "objective";
        public bool IsEssay => Type == "essay" || Type == "theory" || Type == "written";
        public bool IsFillBlank => Type == "fill_blank" || Type == "fill_in_the_blank" || Type == "fill";
        public bool IsTrueFalse => Type == "true_false" || Type == "boolean";
        
        // Check if question has options
        public bool HasOptions => Options.Count > 0;
        
        // Constructor
        public QuestionRecord()
        {
            options = new List<string>();
            text = "";
            type = "multiple_choice";
        }
        
        // Clone for deep copying
        public QuestionRecord Clone()
        {
            return new QuestionRecord
            {
                Id = this.Id,
                text = this.text,
                type = this.type,
                points = this.points,
                options = new List<string>(this.options)
            };
        }
    }

    /// <summary>
    /// Session record from the server
    /// </summary>
    public class SessionRecord
    {
        // Primary fields (snake_case from server)
        public string id { get; set; }
        public string exam_id { get; set; }
        public string student_id { get; set; }
        public string status { get; set; }
        public string started_at { get; set; }
        public string ends_at { get; set; }
        public Dictionary<string, object> answers { get; set; }
        public int focus_loss_count { get; set; }
        
        // Helper properties (PascalCase)
        public string Id => id ?? "";
        public string ExamId => exam_id ?? "";
        public string StudentId => student_id ?? "";
        public string Status => status ?? "active";
        public string StartedAt => started_at ?? "";
        public string EndsAt => ends_at ?? "";
        public int FocusLossCount => focus_loss_count;
        
        // DateTime helpers
        public DateTime? StartedAtDateTime
        {
            get
            {
                if (DateTime.TryParse(StartedAt, out var dt)) return dt;
                return null;
            }
        }
        
        public DateTime? EndsAtDateTime
        {
            get
            {
                if (DateTime.TryParse(EndsAt, out var dt)) return dt.ToUniversalTime();
                return null;
            }
        }
        
        public TimeSpan? TimeRemaining
        {
            get
            {
                if (!EndsAtDateTime.HasValue) return null;
                var remaining = EndsAtDateTime.Value - DateTime.UtcNow;
                return remaining.TotalSeconds > 0 ? remaining : TimeSpan.Zero;
            }
        }
        
        // Helper for time remaining string
        public string TimeRemainingString
        {
            get
            {
                if (!TimeRemaining.HasValue) return "N/A";
                var ts = TimeRemaining.Value;
                return $"{(int)ts.TotalHours:D2}:{ts.Minutes:D2}:{ts.Seconds:D2}";
            }
        }
        
        // Check if session is expired
        public bool IsExpired
        {
            get
            {
                if (!EndsAtDateTime.HasValue) return false;
                return DateTime.UtcNow >= EndsAtDateTime.Value;
            }
        }
        
        // Check if session is submitted
        public bool IsSubmitted => Status?.ToLowerInvariant() == "submitted";
        
        // Check if session is active
        public bool IsActive => Status?.ToLowerInvariant() == "active" && !IsExpired;
        
        // Constructor
        public SessionRecord()
        {
            answers = new Dictionary<string, object>();
            status = "active";
        }
        
        // Get answer for a question
        public object GetAnswer(string questionId)
        {
            if (answers == null || string.IsNullOrEmpty(questionId)) return null;
            answers.TryGetValue(questionId, out var value);
            return value;
        }
        
        // Set answer for a question
        public void SetAnswer(string questionId, object value)
        {
            if (answers == null) answers = new Dictionary<string, object>();
            if (string.IsNullOrEmpty(questionId)) return;
            
            if (value == null || (value is string str && string.IsNullOrWhiteSpace(str)))
            {
                answers.Remove(questionId);
            }
            else
            {
                answers[questionId] = value;
            }
        }
        
        // Get answer as string
        public string GetAnswerString(string questionId)
        {
            var answer = GetAnswer(questionId);
            return JsonUtil.Text(answer);
        }
        
        // Get answer as int
        public int GetAnswerInt(string questionId, int fallback = -1)
        {
            var answer = GetAnswer(questionId);
            return JsonUtil.Int(answer, fallback);
        }
        
        // Get all answered question IDs
        public List<string> GetAnsweredQuestionIds()
        {
            if (answers == null) return new List<string>();
            return new List<string>(answers.Keys);
        }
        
        // Get number of answered questions
        public int AnsweredCount => answers?.Count ?? 0;
    }

    /// <summary>
    /// API Response wrapper
    /// </summary>
    public class ApiResponse
    {
        public bool success { get; set; }
        public string message { get; set; }
        public object data { get; set; }
        
        // Helper properties
        public bool Success => success;
        public string Message => message ?? "";
        public object Data => data;
        
        // Helper methods
        public Dictionary<string, object> DataAsDictionary()
        {
            return data as Dictionary<string, object> ?? new Dictionary<string, object>();
        }
        
        public List<object> DataAsList()
        {
            return data as List<object> ?? new List<object>();
        }
        
        public T DataAs<T>() where T : class
        {
            try
            {
                return data as T;
            }
            catch
            {
                return null;
            }
        }
        
        // Check if response is successful
        public bool IsSuccess => success;
        
        // Check if response has data
        public bool HasData => data != null;
        
        // Constructor
        public ApiResponse()
        {
            success = false;
            message = "";
        }
    }

    /// <summary>
    /// Login response (server sends this)
    /// </summary>
    public class LoginResponse
    {
        public bool success { get; set; }
        public string message { get; set; }
        public StudentRecord student { get; set; }
        public List<ExamInfo> exams { get; set; }
        public ExamInfo exam { get; set; }
        public SessionRecord session { get; set; }
        
        // Helper properties
        public bool Success => success;
        public string Message => message ?? "";
        public StudentRecord Student => student;
        public List<ExamInfo> Exams => exams ?? new List<ExamInfo>();
        public ExamInfo Exam => exam;
        public SessionRecord Session => session;
        
        // Check if has multiple exams
        public bool HasMultipleExams => Exams.Count > 1;
        
        // Check if has single exam
        public bool HasSingleExam => Exams.Count == 1 || Exam != null;
    }

    /// <summary>
    /// Start session response
    /// </summary>
    public class StartSessionResponse
    {
        public bool success { get; set; }
        public string message { get; set; }
        public ExamInfo exam { get; set; }
        public SessionRecord session { get; set; }
        
        // Helper properties
        public bool Success => success;
        public string Message => message ?? "";
        public ExamInfo Exam => exam;
        public SessionRecord Session => session;
    }

    /// <summary>
    /// Save answers response
    /// </summary>
    public class SaveAnswersResponse
    {
        public bool success { get; set; }
        public string message { get; set; }
        public SessionRecord session { get; set; }
        
        // Helper properties
        public bool Success => success;
        public string Message => message ?? "";
        public SessionRecord Session => session;
    }

    /// <summary>
    /// Submit response
    /// </summary>
    public class SubmitResponse
    {
        public bool success { get; set; }
        public string message { get; set; }
        public string result { get; set; }
        public int score { get; set; }
        
        // Helper properties
        public bool Success => success;
        public string Message => message ?? "";
        public string Result => result ?? "";
        public int Score => score;
    }
}