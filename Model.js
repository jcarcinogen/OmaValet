// Kept compatible with Qt's QV4 engine; no browser or Node-only APIs.
function parse(text) {
    try {
        var value = JSON.parse(String(text || ""));
        return value && typeof value === "object" && !Array.isArray(value) ? value : null;
    } catch (_) { return null; }
}
function snapshot(value) {
    function app(entry) { return entry && typeof entry === "object" && typeof entry.name === "string"; }
    return !!(value && Array.isArray(value.catalog) && value.catalog.every(app)
        && Array.isArray(value.valet) && value.valet.every(app)
        && value.existing && Array.isArray(value.existing.parking)
        && value.existing.parking.every(function(entry) { return entry && typeof entry === "object"; })
        && Number.isInteger(value.workspaceCount) && value.workspaceCount >= 5 && value.workspaceCount <= 10);
}
function assignments(value, workspace) {
    var owned = (value.valet || []).filter(function(app) { return Number(app.workspace) === workspace; })
        .map(function(app) { return Object.assign({}, app, {owned:true, source:"Workspace Pins"}); });
    var existing = ((value.existing || {}).parking || [])
        .filter(function(app) { return Number(app.workspace) === workspace; })
        .map(function(app) { return Object.assign({}, app, {owned:false, name:String(app.name || app.class || "Existing rule")}); });
    return owned.concat(existing);
}
function assignedWorkspace(value, id) {
    var app = (value.valet || []).find(function(entry) { return entry.desktopId === id; });
    return app ? Number(app.workspace) : 0;
}
function catalog(value, query, filter) {
    var needle = String(query || "").toLowerCase().trim();
    return (value.catalog || []).filter(function(app) {
        var assigned = assignedWorkspace(value, app.desktopId) > 0;
        return (!needle || String(app.name).toLowerCase().indexOf(needle) >= 0)
            && (filter !== "Assigned" || assigned) && (filter !== "Unassigned" || !assigned);
    });
}
function iconName(value) {
    var name = String(value || "");
    if (!name || name.indexOf("/") !== -1 || name.indexOf(":") !== -1) name = "application-x-executable";
    return name;
}
function errorText(value, fallback) {
    var text = value && typeof value.error === "string" ? value.error : fallback;
    return String(text || "The operation could not be completed.").replace(/[\u0000-\u001f]/g, " ").slice(0, 500);
}
