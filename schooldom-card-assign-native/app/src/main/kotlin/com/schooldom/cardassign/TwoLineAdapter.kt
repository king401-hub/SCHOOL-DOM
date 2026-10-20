package com.schooldom.cardassign

import android.content.Context
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.BaseAdapter
import android.widget.TextView

/** One shared row renderer for the school and student lists - both are just
 * a bold title plus a muted subtitle, so there's no reason for two adapters. */
class TwoLineAdapter(
    private val context: Context,
    private var items: List<Pair<String, String>>,
) : BaseAdapter() {
    fun update(newItems: List<Pair<String, String>>) {
        items = newItems
        notifyDataSetChanged()
    }

    override fun getCount(): Int = items.size
    override fun getItem(position: Int): Pair<String, String> = items[position]
    override fun getItemId(position: Int): Long = position.toLong()

    override fun getView(position: Int, convertView: View?, parent: ViewGroup?): View {
        val view = convertView ?: LayoutInflater.from(context).inflate(R.layout.list_item_two_line, parent, false)
        val (title, subtitle) = items[position]
        view.findViewById<TextView>(R.id.itemTitle).text = title
        val subtitleView = view.findViewById<TextView>(R.id.itemSubtitle)
        subtitleView.text = subtitle
        subtitleView.visibility = if (subtitle.isEmpty()) View.GONE else View.VISIBLE
        return view
    }
}
