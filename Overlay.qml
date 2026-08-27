import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui

Item {
    id: root

    property var shell: null
    property var manifest: null
    property bool opened: false
    property int workspaceCount: 5
    property string filterText: ""
    property var selectedApp: null
    property var valet: []
    property var existingParking: []
    property string statusText: ""
    property string scriptPath: String(Qt.resolvedUrl("scripts/omavalet.py")).replace("file://", "")

    readonly property color background: Color.menu.background
    readonly property color foreground: Color.menu.text
    readonly property color borderColor: Color.menu.border
    readonly property color scrim: Color.menu.scrim
    readonly property color selectedBackground: Color.menu.selectedBackground
    readonly property color selectedText: Color.menu.selectedText
    readonly property var borderSpec: Border.surfaceSpec("menu", "border", borderColor, Math.max(1, Style.space(2)))
    readonly property int cornerRadius: Style.cornerRadius
    readonly property int panelPadding: Style.spacing.panelPadding
    readonly property int cardWidth: Math.min(Style.space(1080), panel.width - Style.gapsOut * 2)
    readonly property int cardHeight: Math.min(Style.space(650), panel.height - Style.gapsOut * 2)

    function open(payloadJson) {
        opened = true
        statusText = ""
        loadSnapshot()
        Qt.callLater(function() { searchInput.forceActiveFocus() })
    }

    function close() {
        opened = false
    }

    function dismiss() {
        opened = false
        if (shell && typeof shell.hide === "function")
            shell.hide((manifest && manifest.id) || "io.github.jcarcinogen.omavalet")
    }

    function toggle() {
        if (opened) dismiss()
        else open("{}")
    }

    function iconSource(iconName) {
        var name = String(iconName || "application-x-executable")
        if (name.indexOf("/") === 0) return "file://" + name
        return Quickshell.iconPath(name, true)
    }

    function loadSnapshot() {
        if (snapshotProc.running) return
        statusText = "Calling the valet…"
        snapshotProc.command = ["python3", scriptPath, "snapshot"]
        snapshotProc.running = true
    }

    function applySnapshot(snapshot) {
        valet = snapshot.valet || []
        existingParking = (snapshot.existing && snapshot.existing.parking) || []
        rebuildCatalog(snapshot.catalog || [])
        statusText = ""
    }

    function rebuildCatalog(source) {
        if (source) catalogSource = source
        appModel.clear()
        var needle = filterText.toLowerCase().trim()
        for (var i = 0; i < catalogSource.length; i++) {
            var app = catalogSource[i]
            if (needle && String(app.name).toLowerCase().indexOf(needle) < 0) continue
            appModel.append({
                desktopId: String(app.desktopId),
                appName: String(app.name),
                execCommand: String(app.exec),
                appClass: String(app.class),
                iconName: String(app.icon || "")
            })
        }
    }

    property var catalogSource: []

    function isSelected(desktopId) {
        return selectedApp && selectedApp.desktopId === desktopId
    }

    function selectApp(desktopId, name, execCommand, appClass, iconName) {
        selectedApp = {
            desktopId: desktopId,
            name: name,
            exec: execCommand,
            className: appClass,
            icon: iconName
        }
    }

    function parkingForWorkspace(workspace) {
        var rows = []
        for (var i = 0; i < valet.length; i++) {
            var app = valet[i]
            if (Number(app.workspace) === workspace) {
                rows.push({
                    owned: true,
                    desktopId: String(app.desktopId || ""),
                    name: String(app.name || app.class || "App"),
                    icon: String(app.icon || ""),
                    source: "OmaValet"
                })
            }
        }
        for (var j = 0; j < existingParking.length; j++) {
            var parked = existingParking[j]
            if (Number(parked.workspace) === workspace) {
                rows.push({
                    owned: false,
                    desktopId: "",
                    name: String(parked.name || parked.class),
                    icon: String(parked.icon || ""),
                    source: String(parked.source || "Hyprland")
                })
            }
        }
        return rows
    }

    function parkSelected(workspace) {
        if (!selectedApp || actionProc.running) return
        statusText = "Parking " + selectedApp.name + " in workspace " + workspace + "…"
        actionProc.command = ["python3", scriptPath, "park", selectedApp.desktopId, String(workspace)]
        actionProc.running = true
    }

    function unpark(desktopId, appName) {
        if (!desktopId || actionProc.running) return
        statusText = "Returning " + appName + "…"
        actionProc.command = ["python3", scriptPath, "unpark", desktopId]
        actionProc.running = true
    }

    function consumeOutput(raw, action) {
        try {
            var payload = JSON.parse(String(raw || "{}"))
            applySnapshot(action ? payload.snapshot : payload)
            if (action) selectedApp = null
        } catch (error) {
            statusText = "The valet could not read the configuration."
        }
    }

    ListModel { id: appModel }

    Process {
        id: snapshotProc
        stdout: StdioCollector {
            waitForEnd: true
            onStreamFinished: root.consumeOutput(text, false)
        }
    }

    Process {
        id: actionProc
        stdout: StdioCollector {
            waitForEnd: true
            onStreamFinished: root.consumeOutput(text, true)
        }
    }

    PanelWindow {
        id: panel
        visible: root.opened
        anchors { top: true; bottom: true; left: true; right: true }
        color: "transparent"
        WlrLayershell.namespace: "omavalet"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
        exclusionMode: ExclusionMode.Ignore

        Rectangle {
            anchors.fill: parent
            color: root.scrim
        }

        MouseArea {
            anchors.fill: parent
            onClicked: root.dismiss()
        }

        BorderSurface {
            id: card
            width: root.cardWidth
            height: root.cardHeight
            anchors.centerIn: parent
            color: root.background
            radius: root.cornerRadius
            borderSpec: root.borderSpec
            padding: root.panelPadding

            MouseArea { anchors.fill: parent; onClicked: {} }

            Item {
                id: keyCatcher
                anchors.fill: parent
                focus: true
                Keys.priority: Keys.BeforeItem
                Keys.onPressed: function(event) {
                    if (event.key === Qt.Key_Escape) {
                        if (root.filterText) searchInput.text = ""
                        else root.dismiss()
                        event.accepted = true
                    } else if (event.modifiers & Qt.ControlModifier && event.key === Qt.Key_F) {
                        searchInput.forceActiveFocus()
                        event.accepted = true
                    }
                }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: card.contentTopInset
                anchors.rightMargin: card.contentRightInset
                anchors.bottomMargin: card.contentBottomInset
                anchors.leftMargin: card.contentLeftInset
                spacing: Style.spacing.md

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Style.spacing.md

                    Text {
                        text: "󰓃"
                        color: Color.accent
                        font.family: Style.font.family
                        font.pixelSize: Style.font.display
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Style.space(1)
                        Text {
                            text: "OmaValet"
                            color: root.foreground
                            font.family: Style.font.family
                            font.pixelSize: Style.font.title
                            font.bold: true
                        }
                        Text {
                            text: "Park startup apps where they belong"
                            color: root.foreground
                            opacity: 0.62
                            font.family: Style.font.family
                            font.pixelSize: Style.font.caption
                        }
                    }

                    Rectangle {
                        width: Style.space(250)
                        height: Style.space(38)
                        radius: root.cornerRadius
                        color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.06)
                        border.width: searchInput.activeFocus ? Math.max(1, Style.space(1)) : 0
                        border.color: Color.accent

                        TextInput {
                            id: searchInput
                            anchors.fill: parent
                            anchors.leftMargin: Style.spacing.md
                            anchors.rightMargin: Style.spacing.md
                            verticalAlignment: TextInput.AlignVCenter
                            color: root.foreground
                            selectionColor: Color.accent
                            selectedTextColor: root.selectedText
                            font.family: Style.font.family
                            font.pixelSize: Style.font.body
                            clip: true
                            onTextChanged: {
                                root.filterText = text
                                root.rebuildCatalog()
                            }
                            Text {
                                anchors.fill: parent
                                verticalAlignment: Text.AlignVCenter
                                text: "Search apps"
                                color: root.foreground
                                opacity: 0.38
                                visible: !searchInput.text
                                font: searchInput.font
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: Math.max(1, Style.space(1))
                    color: root.borderColor
                    opacity: 0.55
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: Style.spacing.lg

                    ColumnLayout {
                        Layout.preferredWidth: Style.space(285)
                        Layout.fillHeight: true
                        spacing: Style.spacing.sm

                        Text {
                            text: "APPS"
                            color: root.foreground
                            opacity: 0.5
                            font.family: Style.font.family
                            font.pixelSize: Style.font.caption
                            font.capitalization: Font.AllUppercase
                        }

                        ListView {
                            id: appList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            spacing: Style.spacing.xs
                            model: appModel

                            delegate: Rectangle {
                                required property string desktopId
                                required property string appName
                                required property string execCommand
                                required property string appClass
                                required property string iconName

                                width: appList.width
                                height: Style.space(46)
                                radius: root.cornerRadius
                                color: root.isSelected(desktopId)
                                    ? root.selectedBackground
                                    : (appMouse.containsMouse
                                        ? Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.06)
                                        : "transparent")

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: Style.spacing.sm
                                    anchors.rightMargin: Style.spacing.sm
                                    spacing: Style.spacing.sm

                                    Image {
                                        Layout.preferredWidth: Style.space(26)
                                        Layout.preferredHeight: Style.space(26)
                                        source: root.iconSource(iconName)
                                        fillMode: Image.PreserveAspectFit
                                        smooth: true
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: appName
                                        elide: Text.ElideRight
                                        color: root.isSelected(desktopId) ? root.selectedText : root.foreground
                                        font.family: Style.font.family
                                        font.pixelSize: Style.font.body
                                    }
                                }

                                MouseArea {
                                    id: appMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: root.selectApp(desktopId, appName, execCommand, appClass, iconName)
                                }
                            }
                        }
                    }

                    Rectangle {
                        Layout.preferredWidth: Math.max(1, Style.space(1))
                        Layout.fillHeight: true
                        color: root.borderColor
                        opacity: 0.45
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: Style.spacing.sm

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                Layout.fillWidth: true
                                text: "PARKING"
                                color: root.foreground
                                opacity: 0.5
                                font.family: Style.font.family
                                font.pixelSize: Style.font.caption
                                font.capitalization: Font.AllUppercase
                            }
                            Text {
                                text: root.selectedApp ? "Choose a workspace" : "Select an app first"
                                color: root.selectedApp ? Color.accent : root.foreground
                                opacity: root.selectedApp ? 1 : 0.45
                                font.family: Style.font.family
                                font.pixelSize: Style.font.caption
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: Style.spacing.sm

                            Repeater {
                                model: root.workspaceCount

                                Rectangle {
                                    id: workspaceLane
                                    required property int index
                                    readonly property int workspaceNumber: index + 1
                                    readonly property var parkedRows: root.parkingForWorkspace(workspaceNumber)
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    radius: root.cornerRadius
                                    color: laneMouse.containsMouse && root.selectedApp
                                        ? Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.13)
                                        : Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.035)
                                    border.width: laneMouse.containsMouse && root.selectedApp
                                        ? Math.max(1, Style.space(1)) : 0
                                    border.color: Color.accent

                                    MouseArea {
                                        id: laneMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        enabled: !!root.selectedApp
                                        onClicked: root.parkSelected(workspaceLane.workspaceNumber)
                                    }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: Style.spacing.sm
                                        spacing: Style.spacing.md

                                        ColumnLayout {
                                            Layout.preferredWidth: Style.space(64)
                                            spacing: 0
                                            Text {
                                                text: String(workspaceLane.workspaceNumber)
                                                color: root.foreground
                                                font.family: Style.font.family
                                                font.pixelSize: Style.font.display
                                                font.bold: true
                                            }
                                            Text {
                                                text: "WORKSPACE"
                                                color: root.foreground
                                                opacity: 0.35
                                                font.family: Style.font.family
                                                font.pixelSize: Style.font.caption
                                            }
                                        }

                                        Text {
                                            Layout.fillWidth: true
                                            visible: workspaceLane.parkedRows.length === 0
                                            text: root.selectedApp ? "Park here" : "Available"
                                            color: root.selectedApp ? Color.accent : root.foreground
                                            opacity: root.selectedApp ? 0.9 : 0.28
                                            font.family: Style.font.family
                                            font.pixelSize: Style.font.caption
                                        }

                                        ListView {
                                            id: parkedList
                                            Layout.fillWidth: true
                                            Layout.fillHeight: true
                                            visible: workspaceLane.parkedRows.length > 0
                                            orientation: ListView.Horizontal
                                            spacing: Style.spacing.xs
                                            clip: true
                                            model: workspaceLane.parkedRows

                                            delegate: Rectangle {
                                                id: parkedChip
                                                required property var modelData
                                                width: Math.min(
                                                    Style.space(190),
                                                    Math.max(Style.space(120), chipName.implicitWidth + Style.space(58))
                                                )
                                                height: Math.min(parkedList.height, Style.space(42))
                                                anchors.verticalCenter: parent ? parent.verticalCenter : undefined
                                                radius: root.cornerRadius
                                                color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.07)

                                                RowLayout {
                                                    anchors.fill: parent
                                                    anchors.leftMargin: Style.spacing.sm
                                                    anchors.rightMargin: Style.spacing.xs
                                                    spacing: Style.spacing.xs

                                                    Image {
                                                        Layout.preferredWidth: Style.space(22)
                                                        Layout.preferredHeight: Style.space(22)
                                                        source: root.iconSource(parkedChip.modelData.icon)
                                                        fillMode: Image.PreserveAspectFit
                                                    }
                                                    Text {
                                                        id: chipName
                                                        Layout.fillWidth: true
                                                        text: parkedChip.modelData.name
                                                        elide: Text.ElideRight
                                                        color: root.foreground
                                                        font.family: Style.font.family
                                                        font.pixelSize: Style.font.caption
                                                    }
                                                    Text {
                                                        text: parkedChip.modelData.owned ? "×" : "󰌾"
                                                        color: parkedChip.modelData.owned ? root.foreground : Color.accent
                                                        opacity: chipMouse.containsMouse || !parkedChip.modelData.owned ? 0.9 : 0.45
                                                        font.family: Style.font.family
                                                        font.pixelSize: Style.font.body
                                                    }
                                                }

                                                MouseArea {
                                                    id: chipMouse
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    onClicked: {
                                                        mouse.accepted = true
                                                        if (parkedChip.modelData.owned)
                                                            root.unpark(parkedChip.modelData.desktopId, parkedChip.modelData.name)
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: root.statusText || (root.selectedApp
                            ? root.selectedApp.name + " is ready to park"
                            : "Existing Hyprland assignments are locked; OmaValet entries can be returned with ×")
                        elide: Text.ElideRight
                        color: root.statusText ? Color.accent : root.foreground
                        opacity: root.statusText ? 1 : 0.5
                        font.family: Style.font.family
                        font.pixelSize: Style.font.caption
                    }
                    Text {
                        text: "Esc to close"
                        color: root.foreground
                        opacity: 0.4
                        font.family: Style.font.family
                        font.pixelSize: Style.font.caption
                    }
                }
            }
        }
    }
}
