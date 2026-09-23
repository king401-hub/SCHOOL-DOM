// Layout chrome for the teacher workspace: floating sidebar, sticky top bar,
// command palette and the animated page slot. Presentational only - tab state,
// data and handlers stay in TeacherWorkspace (App.jsx).
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronRight, LogOut, Menu, Moon, Search, Sun, X } from "lucide-react";
import { CurrentTermBadge } from "../AppShared";
import CommandPalette from "./CommandPalette";
import { Avatar, Kbd, useHotkey, useMeasuredElement } from "./TeacherKit";

const isPaletteShortcut = (event) => (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k";
const isSlash = (event) => event.key === "/" && !event.ctrlKey && !event.metaKey && !event.altKey;

export default function TeacherShell({
  session,
  schoolName,
  teacherName,
  teacherRole = "Teacher",
  avatarUrl = "",
  sections,
  activeTab,
  onSelectTab,
  extraNav = [],
  badges = {},
  tabTitle,
  pageKicker = "Teacher workspace",
  navOpen,
  onToggleNav,
  onCloseNav,
  themePreference,
  onThemeChange,
  onSignOut,
  onOpenProfile,
  paletteActions = [],
  children,
}) {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [markerRef, marker] = useMeasuredElement();
  const contentRef = useRef(null);
  const firstRender = useRef(true);

  const isDark = themePreference === "dark";
  const openPalette = useCallback(() => setPaletteOpen(true), []);

  useHotkey(isPaletteShortcut, (event) => {
    event.preventDefault();
    setPaletteOpen((open) => !open);
  }, { allowInInputs: true });
  useHotkey(isSlash, (event) => {
    event.preventDefault();
    setPaletteOpen(true);
  });

  // Sticky bar gains a shadow once the page has scrolled.
  useEffect(() => {
    let frame = 0;
    const onScroll = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => setScrolled(window.scrollY > 6));
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onScroll);
    };
  }, []);

  // New page: back to the top, and let assistive tech know the content changed.
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    window.scrollTo({ top: 0, behavior: "auto" });
    contentRef.current?.focus({ preventScroll: true });
  }, [activeTab]);

  const paletteItems = useMemo(() => {
    const pages = sections.flatMap((section) =>
      section.items.map((item) => ({
        id: `tab-${item.key}`,
        label: item.label,
        hint: item.hint,
        section: "Go to",
        keywords: `${section.label} ${item.keywords || ""}`,
        icon: item.icon,
        run: () => onSelectTab(item.key),
      }))
    );
    const routes = extraNav.map((item) => ({
      id: `route-${item.id}`,
      label: item.label,
      hint: item.hint,
      section: "Go to",
      keywords: item.keywords || "",
      icon: item.icon,
      run: item.onSelect,
    }));
    return [...paletteActions, ...pages, ...routes];
  }, [sections, extraNav, paletteActions, onSelectTab]);

  return (
    <section className={`teacher-workspace-shell ts ${navOpen ? "nav-open" : ""}`}>
      <a className="ts-skip" href="#ts-main">Skip to content</a>

      <aside className="ts-sidebar" id="teacher-sidebar" aria-label="Teacher navigation">
        <div className="ts-side-brand">
          <span className="ts-side-logo" aria-hidden="true">{(schoolName || "S").trim().charAt(0).toUpperCase()}</span>
          <div className="ts-side-brand__text">
            <strong title={schoolName}>{schoolName}</strong>
            <small>{pageKicker}</small>
          </div>
          <button type="button" className="ts-side-close" onClick={onCloseNav} aria-label="Close menu">
            <X size={18} />
          </button>
        </div>

        <CurrentTermBadge session={session} className="ts-side-term" />

        <button type="button" className="ts-side-search" onClick={openPalette}>
          <Search size={16} aria-hidden="true" />
          <span>Search…</span>
          <Kbd>Ctrl K</Kbd>
        </button>

        <nav className="ts-side-nav" aria-label="Teacher workspace">
          <span
            className="ts-side-marker"
            aria-hidden="true"
            style={marker ? { transform: `translate3d(0, ${marker.top}px, 0)`, height: marker.height, opacity: 1 } : { opacity: 0 }}
          />
          {sections.map((section) => (
            <div className="ts-side-group" key={section.label}>
              <p className="ts-side-heading">{section.label}</p>
              {section.items.map((item) => {
                const Icon = item.icon;
                const active = activeTab === item.key;
                const badge = badges[item.key];
                return (
                  <button
                    key={item.key}
                    ref={active ? markerRef : undefined}
                    type="button"
                    className={`ts-side-item${active ? " is-active" : ""}`}
                    aria-current={active ? "page" : undefined}
                    onClick={() => onSelectTab(item.key)}
                  >
                    <Icon size={18} strokeWidth={active ? 2.1 : 1.8} aria-hidden="true" />
                    <span>{item.label}</span>
                    {badge ? <em className="ts-side-badge">{badge > 99 ? "99+" : badge}</em> : null}
                  </button>
                );
              })}
            </div>
          ))}
          {extraNav.length ? (
            <div className="ts-side-group">
              {extraNav.map((item) => {
                const Icon = item.icon;
                return (
                  <button key={item.id} type="button" className="ts-side-item" onClick={item.onSelect}>
                    <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
                    <span>{item.label}</span>
                    <ChevronRight size={14} className="ts-side-go" aria-hidden="true" />
                  </button>
                );
              })}
            </div>
          ) : null}
        </nav>

        <div className="ts-side-footer">
          <button type="button" className="ts-side-me" onClick={onOpenProfile} aria-label="Edit my profile">
            <Avatar name={teacherName} src={avatarUrl} size={38} />
            <span>
              <strong>{teacherName}</strong>
              <small>{teacherRole}</small>
            </span>
          </button>
          <div className="ts-side-actions">
            <button
              type="button"
              className="ts-side-action"
              onClick={() => onThemeChange?.(isDark ? "light" : "dark")}
              aria-label={`Switch to ${isDark ? "light" : "dark"} theme`}
              title={`Switch to ${isDark ? "light" : "dark"} theme`}
            >
              {isDark ? <Sun size={16} aria-hidden="true" /> : <Moon size={16} aria-hidden="true" />}
              <span>{isDark ? "Light" : "Dark"}</span>
            </button>
            {onSignOut ? (
              <button type="button" className="ts-side-action is-quiet" onClick={onSignOut}>
                <LogOut size={16} aria-hidden="true" />
                <span>Sign out</span>
              </button>
            ) : null}
          </div>
        </div>
      </aside>

      <div className="ts-scrim" role="presentation" onClick={onCloseNav} />

      <div className="ts-main">
        <header className={`ts-topbar${scrolled ? " is-scrolled" : ""}`}>
          <button
            type="button"
            className="ts-menu-btn"
            aria-expanded={navOpen}
            aria-controls="teacher-sidebar"
            aria-label={`${navOpen ? "Close" : "Open"} navigation menu, current page ${tabTitle}`}
            onClick={onToggleNav}
          >
            <Menu size={20} aria-hidden="true" />
          </button>
          <nav className="ts-crumbs" aria-label="Breadcrumb">
            <span>{pageKicker}</span>
            <ChevronRight size={14} aria-hidden="true" />
            <strong aria-current="page">{tabTitle}</strong>
          </nav>
          <div className="ts-topbar__spacer" />
          <button type="button" className="ts-search-pill" onClick={openPalette} aria-label="Search or jump to a page">
            <Search size={16} aria-hidden="true" />
            <span>Search</span>
            <Kbd>Ctrl K</Kbd>
          </button>
          <button type="button" className="ts-topbar__me" onClick={onOpenProfile} aria-label="Edit my profile">
            <Avatar name={teacherName} src={avatarUrl} size={34} />
          </button>
          {/* The app's global notifications bell is position:fixed; this slot keeps the bar clear of it. */}
          <span className="ts-topbar__bell-slot" aria-hidden="true" />
        </header>

        <div id="ts-main" className="ts-content" ref={contentRef} tabIndex={-1}>
          <div key={activeTab} className="ts-page">
            {children}
          </div>
        </div>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} items={paletteItems} />
    </section>
  );
}
