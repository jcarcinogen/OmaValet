import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons

Item {
    id: root
    property var shell: null
    property var manifest: null
    property bool opened: false
    property bool initialized: false

    function open(payloadJson) {
        if (opened) return
        opened = true
        if (board.item) board.item.open()
        initialized = true
    }
    function close() {
        opened = false
        if (board.item) board.item.close()
    }
    function dismiss() {
        close()
        if (shell && typeof shell.hide === "function")
            shell.hide((manifest && manifest.id) || "io.github.jcarcinogen.omavalet")
    }
    function toggle() { if (opened) dismiss(); else open("{}") }

    IpcHandler {
        target: "io.github.jcarcinogen.omavalet"
        function status(): string {
            return JSON.stringify(board.item ? board.item.debugState() : {active:false,busy:false,cameoLoaded:false})
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
        Shortcut {
            sequence: "Escape"
            enabled: root.opened
            onActivated: if (board.item) board.item.handleEscape()
        }
        Rectangle { anchors.fill: parent; color: Color.menu.scrim }
        MouseArea { anchors.fill: parent; onClicked: root.dismiss() }
        Loader {
            id: board
            anchors.centerIn: parent
            width: Math.max(0, Math.min(Style.space(1100), panel.width - Style.gapsOut * 2))
            height: Math.max(0, Math.min(Style.space(740), panel.height - Style.gapsOut * 2))
            focus: true
            active: root.initialized
            source: "Board.qml"
            onLoaded: if (root.opened) item.open()
        }
        Connections {
            target: board.item
            function onDismissed() { root.dismiss() }
        }
    }
}
