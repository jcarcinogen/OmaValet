import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import "Model.js" as Model

FocusScope {
    id: root
    objectName: "omavaletBoard"
    implicitWidth: Style.space(1100)
    implicitHeight: Style.space(740)
    property string scriptPath: String(Qt.resolvedUrl("scripts/omavalet.py")).replace("file://", "")
    property var snapshot: ({catalog:[], valet:[], existing:{parking:[]}, workspaceCount:5, settings:{}})
    property var selectedApp: null
    property var detailRow: null
    property string accessMode: "bar"
    property string filter: "All"
    property string statusText: "Choose an app, then choose its workspace."
    property bool hasError: false
    property bool retryAvailable: false
    property bool destinationMode: false
    property bool settingsOpen: false
    property int expandedLane: 0
    onExpandedLaneChanged: if (expandedLane > 0) Qt.callLater(function() { settingsClose.forceActiveFocus() })
    onRunningOpenChanged: if (runningOpen) Qt.callLater(function() { settingsClose.forceActiveFocus() })
    property bool runningOpen: false
    property var runningWindows: []
    property var chosenWindow: null
    property string actionName: ""
    property string actionLabel: ""
    property bool active: false
    property bool cameoActive: false
    readonly property bool systemReducedMotion: snapshot.systemReducedMotion === true
    property bool dragging: false
    property var dragApp: null
    property alias dragItem: ghost
    property bool pending: false
    readonly property bool busy: pending || request.running
    readonly property var settings: snapshot.settings || ({})
    readonly property var apps: Model.catalog(snapshot, search.text, filter)
    readonly property int workspaceCount: snapshot.workspaceCount
    readonly property bool modalOpen: settingsOpen || expandedLane > 0 || runningOpen
    signal dismissed()

    function open() {
        active = true
        requestAction(["snapshot"], "Loading apps…")
        Qt.callLater(function() { search.forceActiveFocus() })
    }
    function close() {
        active = false
        cameoActive = false
        settingsOpen = false
        expandedLane = 0
        runningOpen = false
        cancelDrag()
    }
    function handleEscape() {
        if (runningOpen) { runningOpen = false; chosenWindow = null; return }
        if (settingsOpen) { settingsOpen = false; return }
        if (expandedLane) { expandedLane = 0; return }
        if (search.text) { search.text = ""; return }
        if (selectedApp) { selectedApp = null; destinationMode = false; search.forceActiveFocus(); return }
        dismissed()
    }
    function applySnapshot(value) {
        if (!Model.snapshot(value)) return false
        snapshot = value
        retryAvailable = value.applyPending === true
        if (value.accessMode === "bar" || value.accessMode === "menu") accessMode = value.accessMode
        if (detailRow && detailRow.owned) {
            var found = value.valet.find(function(app) { return app.desktopId === root.detailRow.desktopId })
            detailRow = found ? Object.assign({}, found, {owned:true, source:"OmaValet"}) : null
        }
        return true
    }
    function requestAction(args, label) {
        if (busy) return false
        actionName = args[0]
        actionLabel = label || "Working…"
        hasError = false
        statusText = actionLabel
        pending = true
        request.command = ["python3", scriptPath].concat(args)
        request.running = true
        return true
    }
    function setAccessMode(mode) {
        if (mode === accessMode || busy) return
        requestAction(["access", mode], "Changing where OmaValet opens…")
    }
    function consume(text, exitCode) {
        var value = Model.parse(text)
        if (value && value.snapshot && !applySnapshot(value.snapshot)) {
            hasError = true
            statusText = "The returned board was invalid. Your last loaded board is still shown."
            return
        }
        if (exitCode !== 0 || !value || value.ok === false) {
            hasError = true
            retryAvailable = !!(value && value.saved && !value.applied)
            statusText = Model.errorText(value, "Could not complete the operation. Your last loaded board is still shown.")
            return
        }
        if (actionName === "snapshot") {
            if (!applySnapshot(value)) {
                hasError = true
                statusText = "The app catalog could not be read. Refresh to try again."
                return
            }
            hasError = retryAvailable
            statusText = retryAvailable ? "Saved assignments still need Retry before they can take effect." : "Choose an app, then choose its workspace."
        } else if (actionName === "running") {
            runningWindows = value.windows || value.running || []
            runningOpen = true
            chosenWindow = null
            statusText = "Choose a running window to identify this app. Window titles are not shown or saved."
        } else if (actionName === "access") {
            accessMode = value.accessMode || accessMode
            statusText = accessMode === "menu" ? "OmaValet now opens from Super+Space → OmaValet." : "OmaValet now opens from the bar."
        } else {
            retryAvailable = snapshot.applyPending === true
            statusText = actionLabel.replace(/…$/, ".")
            if (actionName === "park") {
                statusText += " Applies to newly opened windows."
                selectedApp = null
                destinationMode = false
                if (active) search.forceActiveFocus()
            }
            if (actionName === "identify") { runningOpen = false; chosenWindow = null }
            if (actionName === "test-launch") statusText = "Launch requested. A single-instance app may activate an existing window instead."
        }
        if (retryAvailable && !hasError) statusText += " Saved assignments still need Retry."
        if (value.celebrate === true && active) celebrate()
    }
    function chooseApp(app) {
        if (!app || busy) return
        selectedApp = app
        detailRow = null
        destinationMode = true
        lanes.currentIndex = Math.max(0, Model.assignedWorkspace(snapshot, app.desktopId) - 1)
        lanes.forceActiveFocus()
    }
    function park(app, workspace) {
        if (!app || busy || workspace < 1 || workspace > workspaceCount) return
        requestAction(["park", app.desktopId, String(workspace)], String(app.name) + " assigned to Workspace " + workspace + "…")
    }
    function inspect(row, workspace) {
        detailRow = Object.assign({}, row, {workspace:workspace})
        selectedApp = null
        destinationMode = false
        expandedLane = 0
    }
    function prepareDrag(app, x, y) {
        dragApp = app
        ghost.x = x - ghost.width / 2
        ghost.y = y - ghost.height / 2
    }
    function finishDrag() {
        if (dragging) ghost.Drag.drop()
        cancelDrag()
    }
    function cancelDrag() { dragging = false; dragApp = null }
    function celebrate() {
        if (!active || settings.celebrations === false || cameoActive) return
        cameoActive = true
    }
    function visibleAssignmentIcons() {
        var icons = []
        function visit(item) {
            if (String(item.objectName || "").indexOf("assigned-") === 0 && item.visible)
                icons.push({app:item.appData.desktopId || item.appData.class, ready:item.iconReady, fallback:item.fallbackIcon})
            var children = item.children || []
            for (var i=0; i<children.length; i++) visit(children[i])
        }
        visit(lanes.contentItem)
        return icons
    }
    function debugState() {
        return {active:active,busy:busy,appCount:apps.length,workspaceCount:workspaceCount,
            assignmentIcons:visibleAssignmentIcons(),
            assignedCount:snapshot.valet.length,selected:selectedApp ? selectedApp.desktopId : "",
            destinationMode:destinationMode,hasError:hasError,retryAvailable:retryAvailable,
            status:statusText,expandedLane:expandedLane,runningOpen:runningOpen,settingsOpen:settingsOpen,
            accessMode:accessMode,undoAvailable:!!snapshot.undoAvailable,settings:settings,
            cameoLoaded:cameo.active,frame:cameo.item ? cameo.item.frame : -1,
            frameCount:cameo.item ? cameo.item.frameCount : 0}
    }
    Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Escape) { handleEscape(); event.accepted = true }
        else if (event.modifiers === Qt.ControlModifier && event.key === Qt.Key_F && !modalOpen) {
            search.forceActiveFocus(); event.accepted = true
        }
    }
    Process {
        id: request
        objectName: "backendRequest"
        stdout: StdioCollector { id: output; waitForEnd: true }
        stderr: StdioCollector { waitForEnd: true }
        onExited: function(exitCode) { root.consume(output.text, exitCode); root.pending = false }
    }
    Rectangle { anchors.fill: parent; color: Color.menu.background; radius: Style.cornerRadius; border.width: Math.max(1,Style.space(1)); border.color: Color.menu.border }
    MouseArea { anchors.fill: parent }
    ColumnLayout {
        enabled: !root.modalOpen
        anchors.fill: parent
        anchors.margins: Style.space(20)
        spacing: Style.space(12)
        RowLayout {
            Layout.fillWidth: true
            spacing: Style.space(12)
            Item {
                Layout.preferredWidth: Style.space(44)
                Layout.preferredHeight: Style.space(44)
                Text { anchors.centerIn: parent; text: "󰐃"; color: Color.accent; font.family: Style.font.family; font.pixelSize: Style.font.display }
                MouseArea { objectName: "valetLogo"; anchors.fill: parent; onDoubleClicked: root.celebrate() }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Style.space(2)
                Text { text: "OmaValet"; color: Color.menu.text; font.family: Style.font.family; font.pixelSize: Style.font.title; font.bold: true }
                Text { text: "Your apps. Their own workspaces. No Lua."; color: Color.menu.text; font.family: Style.font.family; font.pixelSize: Style.font.caption; textFormat: Text.PlainText }
            }
            ColumnLayout {
                spacing: Style.space(2)
                Text { text: "OPEN OmaValet FROM"; color: Color.menu.text; font.family: Style.font.family; font.pixelSize: Style.font.caption }
                RowLayout {
                    spacing: Style.space(4)
                    ValetButton { objectName: "accessBar"; text: "Bar"; checked: root.accessMode === "bar"; enabled: !root.busy; onClicked: root.setAccessMode("bar") }
                    ValetButton { objectName: "accessMenu"; text: "Menu"; checked: root.accessMode === "menu"; enabled: !root.busy; onClicked: root.setAccessMode("menu") }
                }
            }
            ValetButton { objectName: "settingsButton"; text: "Settings"; onClicked: { root.settingsOpen = true; settingsClose.forceActiveFocus() } }
            ValetButton { objectName: "closeButton"; text: "×"; hint: "Close OmaValet"; Accessible.name: "Close OmaValet"; onClicked: root.dismissed() }
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Color.menu.border }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: Style.space(120)
            spacing: Style.space(16)
            ColumnLayout {
                Layout.preferredWidth: Math.min(Style.space(285), root.width * 0.29)
                Layout.fillHeight: true
                spacing: Style.space(8)
                TextField {
                    id: search
                    objectName: "appSearch"
                    Layout.fillWidth: true
                    implicitHeight: Style.space(42)
                    placeholderText: "Search apps"
                    color: Color.menu.text
                    placeholderTextColor: Qt.alpha(Color.menu.text, 0.7)
                    selectionColor: Color.accent
                    font.family: Style.font.family
                    font.pixelSize: Style.font.body
                    background: Rectangle { color: Qt.alpha(Color.menu.text, 0.06); radius: Style.cornerRadius; border.width: search.activeFocus ? 1 : 0; border.color: Color.accent }
                    onTextChanged: { root.destinationMode = false; appList.currentIndex = 0 }
                    Keys.onPressed: function(event) {
                        if (event.key === Qt.Key_Escape) { root.handleEscape(); event.accepted = true }
                        else if (event.key === Qt.Key_Down) { appList.forceActiveFocus(); event.accepted = true }
                        else if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && root.apps.length) { root.chooseApp(root.apps[0]); event.accepted = true }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Style.space(3)
                    Repeater {
                        model: ["All", "Assigned", "Unassigned"]
                        ValetButton { required property string modelData; Layout.fillWidth: true; text: modelData; checked: root.filter === modelData; onClicked: root.filter = modelData }
                    }
                }
                ListView {
                    id: appList
                    objectName: "appList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: Style.space(4)
                    model: root.apps
                    currentIndex: 0
                    keyNavigationEnabled: true
                    ScrollBar.vertical: ScrollBar {}
                    Keys.onReturnPressed: if (currentIndex >= 0 && currentIndex < root.apps.length) root.chooseApp(root.apps[currentIndex])
                    Keys.onEnterPressed: if (currentIndex >= 0 && currentIndex < root.apps.length) root.chooseApp(root.apps[currentIndex])
                    delegate: AppTile {
                        required property var modelData
                        required property int index
                        objectName: "app-" + modelData.desktopId
                        width: appList.width - Style.space(12)
                        appData: modelData
                        board: root
                        selected: (root.selectedApp && root.selectedApp.desktopId === modelData.desktopId) || (appList.activeFocus && appList.currentIndex === index)
                        badge: Model.assignedWorkspace(root.snapshot, modelData.desktopId) ? "WS " + Model.assignedWorkspace(root.snapshot, modelData.desktopId) : ""
                        enabled: !root.busy
                        onPicked: root.chooseApp(modelData)
                    }
                    Text {
                        anchors.fill: parent
                        anchors.margins: Style.space(12)
                        visible: root.apps.length === 0
                        text: root.busy ? "Loading apps…" : search.text ? "No apps match “" + search.text + "”.\nClear search to try again." : "No apps in this filter.\nTry All or refresh in Settings."
                        textFormat: Text.PlainText
                        color: Color.menu.text
                        font.family: Style.font.family
                        font.pixelSize: Style.font.body
                        wrapMode: Text.WordWrap
                    }
                }
                ValetButton { text: "Clear search"; visible: search.text.length > 0; Layout.fillWidth: true; onClicked: { search.clear(); search.forceActiveFocus() } }
            }
            Rectangle { Layout.fillHeight: true; implicitWidth: 1; color: Color.menu.border }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: Style.space(8)
                Text {
                    Layout.fillWidth: true
                    text: root.selectedApp ? "Assign " + root.selectedApp.name + " to…" : "Workspace assignments"
                    textFormat: Text.PlainText
                    color: root.selectedApp ? Color.accent : Color.menu.text
                    font.family: Style.font.family
                    font.pixelSize: Style.font.body
                    font.bold: true
                    elide: Text.ElideRight
                }
                ListView {
                    id: lanes
                    objectName: "workspaceList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: Style.space(8)
                    model: root.workspaceCount
                    currentIndex: 0
                    keyNavigationEnabled: true
                    ScrollBar.vertical: ScrollBar {}
                    Keys.onPressed: function(event) {
                        if (!root.destinationMode || !root.selectedApp || (event.modifiers !== Qt.NoModifier && event.modifiers !== Qt.KeypadModifier)) return
                        var workspace = event.key === Qt.Key_0 ? 10 : event.key - Qt.Key_0
                        if (workspace >= 1 && workspace <= root.workspaceCount) {
                            root.park(root.selectedApp, workspace); event.accepted = true
                        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                            root.park(root.selectedApp, currentIndex + 1); event.accepted = true
                        }
                    }
                    delegate: Rectangle {
                        id: lane
                        required property int index
                        readonly property int number: index + 1
                        readonly property var rows: Model.assignments(root.snapshot, number)
                        readonly property int iconSlots: Math.max(1, Math.floor((width - Style.space(136)) / Style.space(49)))
                        readonly property int shown: rows.length <= iconSlots ? iconSlots : Math.max(1, Math.floor((width - Style.space(221)) / Style.space(49)))
                        objectName: "lane-" + number
                        width: lanes.width - Style.space(12)
                        height: Style.space(68)
                        radius: Style.cornerRadius
                        color: Qt.alpha(drop.containsDrag || (lanes.activeFocus && lanes.currentIndex === index) ? Color.accent : Color.menu.text, 0.07)
                        border.width: drop.containsDrag || (lanes.activeFocus && lanes.currentIndex === index) ? 1 : 0
                        border.color: Color.accent
                        DropArea {
                            id: drop
                            anchors.fill: parent
                            keys: ["omavalet-app"]
                            onDropped: function(event) {
                                if (root.dragApp && !root.busy) { root.park(root.dragApp, lane.number); event.acceptProposedAction() }
                            }
                        }
                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: Style.space(8)
                            spacing: Style.space(5)
                            ValetButton {
                                objectName: "park-" + lane.number
                                text: "Workspace " + lane.number
                                Layout.preferredWidth: Style.space(115)
                                emphasized: !!root.selectedApp
                                hint: root.selectedApp ? "Assign selected app here" : "View every assignment"
                                enabled: !root.busy
                                onClicked: {
                                    if (root.selectedApp) root.park(root.selectedApp, lane.number)
                                    else root.expandedLane = lane.number
                                }
                            }
                            Repeater {
                                model: lane.rows.slice(0, lane.shown)
                                AppTile {
                                    required property var modelData
                                    objectName: "assigned-" + lane.number + "-" + (modelData.desktopId || modelData.class)
                                    Layout.preferredWidth: Style.space(44)
                                    compact: true
                                    appData: modelData
                                    board: root
                                    draggable: modelData.owned
                                    badge: modelData.owned ? (modelData.launchOnStart ? "⏻" : "") : "🔒"
                                    enabled: !root.busy
                                    onPicked: root.inspect(modelData, lane.number)
                                }
                            }
                            Text { visible: lane.rows.length === 0; Layout.fillWidth: true; text: "No apps assigned"; color: Color.menu.text; font.family: Style.font.family; font.pixelSize: Style.font.caption; elide: Text.ElideRight }
                            Item { visible: lane.rows.length > 0; Layout.fillWidth: true }
                            ValetButton {
                                objectName: "more-" + lane.number
                                Layout.preferredWidth: Style.space(80)
                                visible: lane.rows.length > lane.shown
                                text: "+" + (lane.rows.length - lane.shown) + " more"
                                onClicked: root.expandedLane = lane.number
                            }
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    ValetButton { text: "+ Add workspace"; visible: root.workspaceCount < 10; enabled: !root.busy; onClicked: root.requestAction(["expand"], "Workspace added…") }
                    ValetButton { text: "− Remove workspace"; visible: root.workspaceCount > 5; enabled: !root.busy && Model.assignments(root.snapshot, root.workspaceCount).length === 0; hint: "Only the last empty extra workspace can be removed"; onClicked: root.requestAction(["shrink"], "Empty workspace removed…") }
                    Item { Layout.fillWidth: true }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Style.space(12)
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Style.space(7)
                Text {
                    Layout.fillWidth: true
                    text: root.detailRow ? String(root.detailRow.name || root.detailRow.class) + " · Workspace " + root.detailRow.workspace : "Select an assignment to manage it. Drag an app to a workspace, or use search → Enter → number."
                    textFormat: Text.PlainText
                    wrapMode: Text.WordWrap
                    color: Color.menu.text
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                }
                RowLayout {
                    visible: !!root.detailRow && root.detailRow.owned === true
                    Layout.fillWidth: true
                    spacing: Style.space(6)
                    ValetButton {
                        objectName: "loginToggle"
                        text: "Start at login: " + (root.detailRow && root.detailRow.launchOnStart ? "On" : "Off")
                        checked: !!root.detailRow && root.detailRow.launchOnStart === true
                        enabled: !root.busy
                        onClicked: root.requestAction(["boot", root.detailRow.desktopId, root.detailRow.launchOnStart ? "off" : "on"], "Login preference saved…")
                    }
                    ValetButton { objectName: "testLaunch"; text: "Open to test"; enabled: !root.busy; onClicked: root.requestAction(["test-launch", root.detailRow.desktopId], "Opening app…") }
                    ValetButton { objectName: "identifyButton"; text: "Identify window"; enabled: !root.busy; onClicked: root.requestAction(["running"], "Reading running app identities…") }
                    ValetButton { objectName: "removeAssignment"; text: "Remove"; hint: "Remove this assignment, not the application"; enabled: !root.busy; onClicked: root.requestAction(["unpark", root.detailRow.desktopId], "Assignment removed…") }
                    Item { Layout.fillWidth: true }
                }
                Text {
                    visible: !!root.detailRow && root.detailRow.owned === false
                    Layout.fillWidth: true
                    text: "🔒 Managed by " + (root.detailRow ? root.detailRow.source || "Hyprland" : "") + ". OmaValet leaves this rule unchanged."
                    textFormat: Text.PlainText
                    wrapMode: Text.WordWrap
                    color: Color.menu.text
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                }
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        objectName: "statusText"
                        Layout.fillWidth: true
                        text: (root.hasError ? "Could not apply: " : "") + root.statusText
                        textFormat: Text.PlainText
                        color: root.hasError ? Color.menu.text : Color.accent
                        font.family: Style.font.family
                        font.pixelSize: Style.font.caption
                        wrapMode: Text.WordWrap
                        maximumLineCount: 3
                        elide: Text.ElideRight
                    }
                    ValetButton { objectName: "retryButton"; visible: root.retryAvailable; text: "Retry"; enabled: !root.busy; onClicked: root.requestAction(["retry"], "Saved assignments applied…") }
                    ValetButton { objectName: "undoButton"; visible: !!root.snapshot.undoAvailable; text: "Undo"; enabled: !root.busy; onClicked: root.requestAction(["undo"], "Last change undone…") }
                }
            }
            Loader {
                id: cameo
                objectName: "celebrationLoader"
                Layout.preferredWidth: active ? Style.space(190) : 0
                Layout.preferredHeight: active ? Style.space(220) : 0
                active: root.active && root.cameoActive
                visible: active
                sourceComponent: Celebration {
                    reducedMotion: root.settings.reducedMotion === true || root.systemReducedMotion
                    onFinished: root.cameoActive = false
                }
            }
        }
    }
    Rectangle {
        id: ghost
        z: 100
        visible: root.dragging
        width: Style.space(160)
        height: Style.space(44)
        radius: Style.cornerRadius
        color: Color.menu.background
        border.color: Color.accent
        border.width: 2
        Drag.active: root.dragging
        Drag.keys: ["omavalet-app"]
        Drag.hotSpot.x: width / 2
        Drag.hotSpot.y: height / 2
        Text { anchors.fill: parent; anchors.margins: Style.space(8); text: root.dragApp ? root.dragApp.name : ""; textFormat: Text.PlainText; color: Color.menu.text; elide: Text.ElideRight; font.family: Style.font.family; verticalAlignment: Text.AlignVCenter }
    }
    Rectangle {
        anchors.fill: parent
        anchors.margins: Style.space(16)
        z: 40
        visible: root.modalOpen
        color: Color.menu.background
        border.width: 1
        border.color: Color.accent
        radius: Style.cornerRadius
        MouseArea { anchors.fill: parent }
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Style.space(20)
            spacing: Style.space(12)
            RowLayout {
                Layout.fillWidth: true
                Text {
                    Layout.fillWidth: true
                    text: root.settingsOpen ? "Settings" : root.runningOpen ? "Identify a running app" : "Workspace " + root.expandedLane
                    color: Color.menu.text
                    font.family: Style.font.family
                    font.pixelSize: Style.font.title
                    textFormat: Text.PlainText
                }
                ValetButton { id: settingsClose; objectName: "dialogClose"; text: "Back"; onClicked: { root.settingsOpen = false; root.expandedLane = 0; root.runningOpen = false; search.forceActiveFocus() } }
            }
            ColumnLayout {
                visible: root.settingsOpen
                Layout.fillWidth: true
                spacing: Style.space(12)
                ValetButton { objectName: "celebrationsToggle"; text: "Celebrations: " + (root.settings.celebrations === false ? "Off" : "On"); checked: root.settings.celebrations !== false; enabled: !root.busy; onClicked: { root.cameoActive = false; root.requestAction(["settings", "celebrations", root.settings.celebrations === false ? "on" : "off"], "Celebration preference saved…") } }
                ValetButton { objectName: "motionToggle"; text: "Reduced motion: " + (root.settings.reducedMotion === true ? "On" : "Off"); checked: root.settings.reducedMotion === true; enabled: !root.busy; onClicked: { root.cameoActive = false; root.requestAction(["settings", "reduced-motion", root.settings.reducedMotion === true ? "off" : "on"], "Motion preference saved…") } }
                Text { Layout.fillWidth: true; text: "Reduced motion uses a still image instead of animation. Celebrations are silent and never launch another application."; color: Color.menu.text; textFormat: Text.PlainText; wrapMode: Text.WordWrap; font.family: Style.font.family; font.pixelSize: Style.font.body }
                ValetButton { text: "Refresh apps and assignments"; enabled: !root.busy; onClicked: root.requestAction(["snapshot"], "Refreshing…") }
                Text { Layout.fillWidth: true; text: "Claudia by anabology · AI-generated character and performance. Fan work; not affiliated with Anthropic."; color: Color.menu.text; textFormat: Text.PlainText; wrapMode: Text.WordWrap; font.family: Style.font.family; font.pixelSize: Style.font.caption }
            }
            ListView {
                objectName: "expandedAssignments"
                visible: root.expandedLane > 0
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: Style.space(8)
                model: root.expandedLane > 0 ? Model.assignments(root.snapshot, root.expandedLane) : []
                ScrollBar.vertical: ScrollBar {}
                delegate: AppTile {
                    required property var modelData
                    width: ListView.view.width - Style.space(12)
                    appData: modelData
                    draggable: false
                    badge: modelData.owned ? (modelData.launchOnStart ? "Login on" : "Login off") : "Locked"
                    onPicked: root.inspect(modelData, root.expandedLane)
                }
                Text { visible: parent.count === 0; text: "No apps assigned. Go back and choose an app first."; color: Color.menu.text; font.family: Style.font.family; font.pixelSize: Style.font.body }
            }
            Text {
                visible: root.runningOpen
                Layout.fillWidth: true
                text: "Choose the window belonging to “" + (root.detailRow ? root.detailRow.name : "") + "”. This rule will match every window with that exact class. Titles are not shown or saved; conflicts are checked before saving."
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                color: Color.menu.text
                font.family: Style.font.family
                font.pixelSize: Style.font.body
            }
            ListView {
                visible: root.runningOpen
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: Style.space(6)
                model: root.runningWindows
                ScrollBar.vertical: ScrollBar {}
                delegate: ValetButton {
                    required property var modelData
                    width: ListView.view.width - Style.space(12)
                    text: modelData.name + " · " + modelData.class
                    checked: root.chosenWindow && root.chosenWindow.address === modelData.address
                    onClicked: root.chosenWindow = modelData
                }
                Text { visible: root.runningWindows.length === 0; text: "No running windows found. Open the app, then try again."; textFormat: Text.PlainText; color: Color.menu.text; font.family: Style.font.family; font.pixelSize: Style.font.body }
            }
            ValetButton { objectName: "confirmIdentity"; visible: root.runningOpen; text: "Use this window identity"; emphasized: true; enabled: !!root.chosenWindow && !root.busy; onClicked: root.requestAction(["identify", root.detailRow.desktopId, root.chosenWindow.address, root.chosenWindow.class], "Window identity updated…") }
            Text { visible: root.hasError; Layout.fillWidth: true; text: root.statusText; textFormat: Text.PlainText; wrapMode: Text.WordWrap; color: Color.menu.text; font.family: Style.font.family; font.pixelSize: Style.font.body }
            Item { visible: root.settingsOpen; Layout.fillHeight: true }
        }
    }
}
