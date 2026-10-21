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

/**
 * Search-as-you-type picker for who's getting a card. Defaults to students
 * (the common case) but a role switcher covers everyone the backend will
 * actually let an admin link a card to - teachers, staff, and admins/
 * principals too (see ASSIGNABLE_ROLES in rfid_attendance/views.py; "Admin"
 * here covers school_admin, principal, super_admin and school_superadmin in
 * one tab since the result list already shows each person's exact title).
 */
class StudentPickerActivity : Activity() {
    private val bgExecutor = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())
    private val searchDebounce = Handler(Looper.getMainLooper())
    private var searchRunnable: Runnable? = null
    private var searchGeneration = 0

    private lateinit var screenTitleText: TextView
    private lateinit var schoolNameText: TextView
    private lateinit var changeSchoolButton: TextView
    private lateinit var signOutButton: TextView
    private lateinit var roleTabStudent: TextView
    private lateinit var roleTabTeacher: TextView
    private lateinit var roleTabStaff: TextView
    private lateinit var roleTabAdmin: TextView
    private lateinit var searchInput: EditText
    private lateinit var errorText: TextView
    private lateinit var emptyText: TextView
    private lateinit var progressBar: ProgressBar
    private lateinit var studentList: ListView
    private lateinit var adapter: TwoLineAdapter

    private var people: List<JSONObject> = emptyList()
    private var selectedRole = "student"
    private lateinit var roleTabs: Map<String, TextView>

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_student_picker)

        screenTitleText = findViewById(R.id.screenTitleText)
        schoolNameText = findViewById(R.id.schoolNameText)
        changeSchoolButton = findViewById(R.id.changeSchoolButton)
        signOutButton = findViewById(R.id.signOutButton)
        roleTabStudent = findViewById(R.id.roleTabStudent)
        roleTabTeacher = findViewById(R.id.roleTabTeacher)
        roleTabStaff = findViewById(R.id.roleTabStaff)
        roleTabAdmin = findViewById(R.id.roleTabAdmin)
        searchInput = findViewById(R.id.searchInput)
        errorText = findViewById(R.id.errorText)
        emptyText = findViewById(R.id.emptyText)
        progressBar = findViewById(R.id.progressBar)
        studentList = findViewById(R.id.studentList)

        roleTabs = mapOf(
            "student" to roleTabStudent,
            "teacher" to roleTabTeacher,
            "staff" to roleTabStaff,
            "admin" to roleTabAdmin,
        )
        roleTabs.forEach { (role, tab) -> tab.setOnClickListener { selectRole(role) } }

        adapter = TwoLineAdapter(this, emptyList())
        studentList.adapter = adapter
        studentList.setOnItemClickListener { _, _, position, _ ->
            val person = people[position]
            val intent = Intent(this, TapAssignActivity::class.java).apply {
                putExtra("person_id", person.optString("id"))
                putExtra("person_name", person.optString("name"))
                putExtra("class_name", person.optString("class_name"))
                putExtra("role_label", person.optString("role_label"))
                putExtra("has_active_card", person.optBoolean("has_active_card"))
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
                val runnable = Runnable { loadPeople(searchInput.text.toString().trim()) }
                searchRunnable = runnable
                searchDebounce.postDelayed(runnable, 350)
            }
        })

        renderRoleTabs()
    }

    override fun onResume() {
        super.onResume()
        loadPeople(searchInput.text.toString().trim())
    }

    private fun selectRole(role: String) {
        if (role == selectedRole) return
        selectedRole = role
        renderRoleTabs()
        loadPeople(searchInput.text.toString().trim())
    }

    private fun renderRoleTabs() {
        roleTabs.forEach { (role, tab) ->
            val selected = role == selectedRole
            tab.setBackgroundColor(resources.getColor(if (selected) R.color.primary else R.color.card_bg, theme))
            tab.setTextColor(if (selected) 0xFFFFFFFF.toInt() else resources.getColor(R.color.text_muted, theme))
        }
        val label = when (selectedRole) {
            "teacher" -> "Teacher"
            "staff" -> "Staff"
            "admin" -> "Admin"
            else -> "Student"
        }
        screenTitleText.text = "Select $label"
        searchInput.hint = "Search ${label.lowercase()}s by name"
        emptyText.text = "No ${label.lowercase()}s found."
    }

    private fun rolesQueryValue(): String = when (selectedRole) {
        "teacher" -> "teacher"
        "staff" -> "staff"
        "admin" -> "school_admin,principal,super_admin,school_superadmin"
        else -> "student"
    }

    private fun loadPeople(search: String) {
        val generation = ++searchGeneration
        val role = selectedRole
        errorText.visibility = View.GONE
        emptyText.visibility = View.GONE
        progressBar.visibility = View.VISIBLE
        bgExecutor.execute {
            try {
                val schoolCode = CardAssignStore.schoolCode(this)
                var endpoint = "/api/rfid/people/?roles=${Uri.encode(rolesQueryValue())}"
                if (schoolCode.isNotEmpty()) endpoint += "&school_code=${Uri.encode(schoolCode)}"
                if (search.isNotEmpty()) endpoint += "&search=${Uri.encode(search)}"
                val data = ApiClient.getJson(this, endpoint)
                val rows = data.optJSONArray("data") ?: JSONArray()
                val list = mutableListOf<JSONObject>()
                for (i in 0 until rows.length()) list.add(rows.getJSONObject(i))
                mainHandler.post {
                    if (generation != searchGeneration || role != selectedRole) return@post
                    progressBar.visibility = View.GONE
                    people = list
                    emptyText.visibility = if (list.isEmpty()) View.VISIBLE else View.GONE
                    adapter.update(list.map { person ->
                        val hasCard = person.optBoolean("has_active_card")
                        val subtitleParts = mutableListOf<String>()
                        if (role == "student") {
                            val className = person.optString("class_name")
                            if (className.isNotEmpty()) subtitleParts.add(className)
                        } else {
                            val roleLabel = person.optString("role_label")
                            if (roleLabel.isNotEmpty()) subtitleParts.add(roleLabel)
                        }
                        if (hasCard) subtitleParts.add("Has a card")
                        person.optString("name") to subtitleParts.joinToString(" · ")
                    })
                }
            } catch (e: SessionExpiredException) {
                mainHandler.post { goToLogin() }
            } catch (e: Exception) {
                mainHandler.post {
                    if (generation != searchGeneration || role != selectedRole) return@post
                    progressBar.visibility = View.GONE
                    errorText.text = e.message ?: "Could not load the list."
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
