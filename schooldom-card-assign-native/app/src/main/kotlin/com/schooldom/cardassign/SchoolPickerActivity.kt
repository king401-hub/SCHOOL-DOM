package com.schooldom.cardassign

import android.app.Activity
import android.content.Intent
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
import java.util.concurrent.Executors

/** super_admin only (see CardAssignStore.needsSchoolPicker) - every other
 * role's own tenant is implicit, so they never reach this screen. */
class SchoolPickerActivity : Activity() {
    private val bgExecutor = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())

    private lateinit var searchInput: EditText
    private lateinit var errorText: TextView
    private lateinit var progressBar: ProgressBar
    private lateinit var schoolList: ListView
    private lateinit var adapter: TwoLineAdapter

    /** schema_name, name, student_count for each school. */
    private var schools: List<Triple<String, String, Int>> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_school_picker)

        searchInput = findViewById(R.id.searchInput)
        errorText = findViewById(R.id.errorText)
        progressBar = findViewById(R.id.progressBar)
        schoolList = findViewById(R.id.schoolList)

        adapter = TwoLineAdapter(this, emptyList())
        schoolList.adapter = adapter
        schoolList.setOnItemClickListener { _, _, position, _ ->
            val filtered = filteredSchools()
            val (schemaName, name, _) = filtered[position]
            CardAssignStore.setSchool(this, schemaName, name)
            startActivity(Intent(this, StudentPickerActivity::class.java))
            finish()
        }

        searchInput.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
            override fun afterTextChanged(s: Editable?) {
                render()
            }
        })

        loadSchools()
    }

    private fun filteredSchools(): List<Triple<String, String, Int>> {
        val query = searchInput.text.toString().trim().lowercase()
        if (query.isEmpty()) return schools
        return schools.filter { it.second.lowercase().contains(query) }
    }

    private fun render() {
        val filtered = filteredSchools()
        adapter.update(filtered.map { (_, name, count) -> name to "$count student${if (count == 1) "" else "s"}" })
    }

    private fun loadSchools() {
        errorText.visibility = View.GONE
        progressBar.visibility = View.VISIBLE
        bgExecutor.execute {
            try {
                val data = ApiClient.getJson(this, "/api/device-fleet/schools/")
                val list = mutableListOf<Triple<String, String, Int>>()
                val rows = data.optJSONArray("data") ?: JSONArray()
                for (i in 0 until rows.length()) {
                    val row = rows.getJSONObject(i)
                    list.add(Triple(row.optString("schema_name"), row.optString("name"), row.optInt("student_count")))
                }
                list.sortBy { it.second.lowercase() }
                mainHandler.post {
                    progressBar.visibility = View.GONE
                    schools = list
                    render()
                }
            } catch (e: SessionExpiredException) {
                mainHandler.post { goToLogin() }
            } catch (e: Exception) {
                mainHandler.post {
                    progressBar.visibility = View.GONE
                    errorText.text = e.message ?: "Could not load schools."
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
