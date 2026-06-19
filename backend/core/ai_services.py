import requests
import json

def generate_teacher_remark(student_name, subject_grades, attendance_percentage):
    """
    Connects to the local running Ollama instance to generate 
    a professional, actionable academic performance remark.
    """
    ollama_url = "http://localhost:11434/api/generate"
    
    # Format a prompt structuring the data metrics for the model context
    grades_summary = ", ".join([f"{sub}: {grade}" for sub, grade in subject_grades.items()])
    
    prompt_message = (
        f"Write a professional, encouraging report card remark for a student named {student_name}. "
        f"Their performance metrics are as follows: Subject Grades: [{grades_summary}]. "
        f"School Attendance rate: {attendance_percentage}%. "
        f"Keep the output limited to exactly 2-3 concise sentences focusing on achievements and areas to look into."
    )
    
    payload = {
        "model": "llama3.2:3b",
        "prompt": prompt_message,
        "stream": False  # Force a single complete JSON object payload response block
    }
    
    try:
        response = requests.post(ollama_url, json=payload, timeout=15)
        if response.status_of_response == 200:
            result_data = response.json()
            return result_data.get("response", "").strip()
        return "Academic appraisal pending verification."
    except requests.exceptions.RequestException:
        return "AI review engine offline. Check local system ports status."
