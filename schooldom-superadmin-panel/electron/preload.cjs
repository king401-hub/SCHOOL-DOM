// Nothing to bridge yet - the renderer talks to the SchoolDom API directly via
// fetch() (a standard Web API, unaffected by contextIsolation/sandbox) and
// persists its session with localStorage, which is available in the renderer
// without any preload exposure. Kept as an empty preload rather than removing
// it entirely so main.cjs's webPreferences.preload path stays valid if/when
// a real main-process bridge (e.g. auto-update, native notifications) is
// added later.
