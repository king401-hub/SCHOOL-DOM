package com.schooldom.cardassign

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.widget.EditText
import android.widget.ListView
import android.widget.ProgressBar
import android.widget.TextView
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.Executors

/** Search-as-you-type picker for the student who's getting a card. Only
 * students are offered here - the app's whole purpose is "tap a card, give
 * it to a student" (see MainActivity's routing and the user's own framing
 * of this app), so there's no role switcher like the web wizard has. */
class StudentPickerActivity : Activity() {
    private val bgExecutor = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())
    private val searchDebounce = Handler(Looper.getMainLooper())
    private var searchRunnable: Runnable? = null
    private var searchGeneration = 0

    private lateinit var schoolNameText: TextView
    private lateinit var changeSchoolButton: TextView
    private lateinit var signOutButton: TextView
    private lateinit var searchInput: EditText
    private lateinit var errorText: TextView
    private lateinit var emptyText: TextView
    private lateinit var progressBar: ProgressBar
    private lateinit var studentList: ListView
    private lateinit var adapter: TwoLineAdapter

    private var students: List<JSONObject> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_student_picker)

        schoolNameText = findViewById(R.id.schoolNameText)
        changeSchoolButton = findViewById(R.id.changeSchoolButton)
        signOutButton = findViewById(R.id.signOutButton)
        searchInput = findViewById(R.id.searchInput)
        errorText = findViewById(R.id.errorText)
        emptyText = findViewById(R.id.emptyText)
        progressBar = findViewById(R.id.progressBar)
        studentList = findViewById(R.id.studentList)

        adapter = TwoLineAdapter(this, emptyList())
        studentList.adapter = adapter
        studentList.setOnItemClickListener { _, _, position, _ ->
            val student = students[position]
            val intent = Intent(this, TapAssignActivity::class.java).apply {
                putExtra("person_id", student.optString("id"))
                putExtra("person_name", student.optString("name"))
                putExtra("class_name", student.optString("class_name"))
                putExtra("has_active_card", student.optBoolean("has_active_card"))
            }
            startActivity(intent)
        }

        if (CardAssignStore.needsSchoolPicker(this)) {
            schoolNameText.text = CardAssignStore.schoolName(this)
            changeSchoolButton.visibility = View.VISIBLE
            changeSchoolButton.setOnClickListener {
                CardAssignStore.clearSchool(this)
                startActivity(Intent(this, SchoolPickerActivity::class.java))
                finish()
            }
        } else {
            schoolNameText.text = CardAssignStore.userEmail(this)
        }

        signOutButton.setOnClickListener {
            SessionStore.clearSession(this)
            CardAssignStore.clearAll(this)
            startActivity(Intent(this, LoginActivity::class.java))
            finish()
        }

        searchInput.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
            override fun afterTextChanged(s: Editable?) {
                searchRunnable?.let { searchDebounce.removeCallbacks(it) }
                val runnable = Runnable { loadStudents(searchInput.text.toString().trim()) }
                searchRunnable = runnable
                searchDebounce.postDelayed(runnable, 350)
            }
        })
    }

    override fun onResume() {
        super.onResume()
        loadStudents(searchInput.text.toString().trim())
    }

    private fun loadStudents(search: String) {
        val generation = ++searchGeneration
        errorText.visibility = View.GONE
        emptyText.visibility = View.GONE
        progressBar.visibility = View.VISIBLE
        bgExecutor.execute {
            try {
                val schoolCode = CardAssignStore.schoolCode(this)
                var endpoint = "/api/rfid/people/?roles=student"
                if (schoolCode.isNotEmpty()) endpoint += "&school_code=${Uri.encode(schoolCode)}"
                if (search.isNotEmpty()) endpoint += "&search=${Uri.encode(search)}"
                val data = ApiClient.getJson(this, endpoint)
                val rows = data.optJSONArray("data") ?: JSONArray()
                val list = mutableListOf<JSONObject>()
                for (i in 0 until rows.length()) list.add(rows.getJSONObject(i))
                mainHandler.post {
                    if (generation != searchGeneration) return@post
                    progressBar.visibility = View.GONE
                    students = list
                    emptyText.visibility = if (list.isEmpty()) View.VISIBLE else View.GONE
                    adapter.update(list.map { student ->
                        val className = student.optString("class_name")
                        val hasCard = student.optBoolean("has_active_card")
                        val subtitleParts = mutableListOf<String>()
                        if (className.isNotEmpty()) subtitleParts.add(className)
                        if (hasCard) subtitleParts.add("Has a card")
                        student.optString("name") to subtitleParts.joinToString(" · ")
                    })
                }
            } catch (e: SessionExpiredException) {
                mainHandler.post { goToLogin() }
            } catch (e: Exception) {
                mainHandler.post {
                    if (generation != searchGeneration) return@post
                    progressBar.visibility = View.GONE
                    errorText.text = e.message ?: "Could not load students."
                    errorText.visibility = View.VISIBLE
                }
            }
        }
    }

    private fun goToLogin() {
        CardAssignStore.clearAll(this)
        startActivity(Intent(this, LoginActivity::class.java))
        finish()
    }
}
