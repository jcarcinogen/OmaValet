import QtQuick
import Quickshell
import Quickshell.Io
import qs.Ui

BarWidget {
    id: root
    moduleName: "io.github.jcarcinogen.omavalet"

    readonly property bool opened: overlayLoader.item ? overlayLoader.item.opened === true : false
    readonly property real openPanelIndicatorWidth: button.labelWidth

    function open(payloadJson) {
        if (overlayLoader.item) overlayLoader.item.open(payloadJson || "{}")
    }

    function close() {
        if (overlayLoader.item) overlayLoader.item.close()
    }

    function togglePanel() {
        if (!overlayLoader.item) return
        if (opened) overlayLoader.item.dismiss()
        else overlayLoader.item.open("{}")
    }

    function injectOverlay() {
        var target = overlayLoader.item
        if (!target) return
        if ("shell" in target && root.bar) target.shell = root.bar.shell
        if ("workspaceCount" in target)
            target.workspaceCount = root.setting("workspaceCount", 5)
    }

    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

    onBarChanged: injectOverlay()
    onSettingsChanged: injectOverlay()

    Loader {
        id: overlayLoader
        // Keep Overlay.qml loaded so parking lanes stay available.
        active: true
        source: Qt.resolvedUrl("Overlay.qml")
        visible: false
        onLoaded: {
            root.injectOverlay()
            Qt.callLater(root.injectOverlay)
        }
    }

    IpcHandler {
        target: "io.github.jcarcinogen.omavalet"
        function open(): void { root.open("{}") }
        function close(): void { root.close() }
        function show(): void { root.open("{}") }
        function hide(): void { root.close() }
        function toggle(): void { root.togglePanel() }
    }

    WidgetButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        text: "󰓃"
        tooltipText: "OmaValet — park startup apps"
        horizontalMargin: 7.5
        onPressed: function(buttonCode) {
            if (buttonCode === Qt.LeftButton) root.togglePanel()
        }
    }
}
