using System.Collections.Generic;

namespace SchoolDom.StudentCbt.Win7
{
    public class StudentRecord { public string id { get; set; } public string student_id { get; set; } public string full_name { get; set; } public string class_name { get; set; } }
    public class ExamInfo { public string id { get; set; } public string title { get; set; } public string subject { get; set; } public int duration_seconds { get; set; } public string instructions { get; set; } }
    public class QuestionRecord { public string Id { get; set; } public string id { get { return Id; } set { Id = value; } } public string text { get; set; } public string type { get; set; } public double points { get; set; } public List<string> options { get; set; } public QuestionRecord() { options = new List<string>(); } }
    public class SessionRecord { public string id { get; set; } public string exam_id { get; set; } public string student_id { get; set; } public string status { get; set; } public string started_at { get; set; } public string ends_at { get; set; } public Dictionary<string, object> answers { get; set; } public int focus_loss_count { get; set; } public SessionRecord() { answers = new Dictionary<string, object>(); } }
}

