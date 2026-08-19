import { useEffect, useMemo, useRef, useState } from "react";
import { Search, X } from "lucide-react";

/**
 * Reusable "jump to page" search box for a role's sidebar.
 *
 * `items` must already be filtered down to exactly what that role/session is
 * allowed to see (the same list used to render the sidebar's own buttons) -
 * this component does no permission filtering of its own, it only searches
 * whatever list it's handed.
 *
 * Item shape: { id, label, section, group?, keywords?: string[], icon?: Component }
 */
export default function SidebarSearch({ items, onSelect, placeholder = "Search pages...", renderIcon }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState(0);
  const containerRef = useRef(null);
  const inputRef = useRef(null);

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    const matched = (items || []).filter((item) => {
      const haystack = [item.label, item.section, item.group, ...(item.keywords || [])]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
    const bySection = new Map();
    const ordered = [];
    for (const item of matched) {
      const key = item.section || "Pages";
      if (!bySection.has(key)) {
        const group = { section: key, items: [] };
        bySection.set(key, group);
        ordered.push(group);
      }
      bySection.get(key).items.push(item);
    }
    return ordered;
  }, [items, query]);

  const flatResults = useMemo(() => groups.flatMap((group) => group.items), [groups]);
  const showDropdown = open && query.trim().length > 0;

  useEffect(() => {
    setHighlightIndex(0);
  }, [query]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const selectItem = (item) => {
    onSelect?.(item);
    setQuery("");
    setOpen(false);
  };

  const handleKeyDown = (event) => {
    if (event.key === "Escape") {
      setOpen(false);
      inputRef.current?.blur();
      return;
    }
    if (!showDropdown) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlightIndex((index) => Math.min(index + 1, flatResults.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const item = flatResults[highlightIndex];
      if (item) selectItem(item);
    }
  };

  return (
    <div className="sidebar-search" ref={containerRef}>
      <div className="sidebar-search-input-wrap">
        <Search size={15} className="sidebar-search-icon" aria-hidden="true" />
        <input
          ref={inputRef}
          type="search"
          className="sidebar-search-input"
          placeholder={placeholder}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          aria-label={placeholder}
        />
        {query ? (
          <button
            type="button"
            className="sidebar-search-clear"
            onClick={() => {
              setQuery("");
              inputRef.current?.focus();
            }}
            aria-label="Clear search"
          >
            <X size={13} />
          </button>
        ) : null}
      </div>
      {showDropdown ? (
        <div className="sidebar-search-results" role="listbox">
          {flatResults.length === 0 ? (
            <p className="sidebar-search-empty">No matching pages for &quot;{query.trim()}&quot;.</p>
          ) : (
            groups.map((group) => (
              <div key={group.section} className="sidebar-search-group">
                <p className="sidebar-search-group-label">{group.section}</p>
                {group.items.map((item) => {
                  const flatIndex = flatResults.indexOf(item);
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      role="option"
                      aria-selected={flatIndex === highlightIndex}
                      className={`sidebar-search-result ${flatIndex === highlightIndex ? "highlighted" : ""}`}
                      onMouseEnter={() => setHighlightIndex(flatIndex)}
                      onClick={() => selectItem(item)}
                    >
                      {renderIcon ? (
                        renderIcon(item)
                      ) : Icon ? (
                        <Icon size={15} strokeWidth={1.8} className="sidebar-search-result-icon" />
                      ) : null}
                      <span className="sidebar-search-result-label">{item.label}</span>
                      {item.group ? <span className="sidebar-search-result-group">{item.group}</span> : null}
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
