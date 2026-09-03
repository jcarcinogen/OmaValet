import QtQuick
import qs.Ui

BarWidget {
    id: root
    moduleName: "io.github.jcarcinogen.omavalet"

    readonly property bool opened: root.bar && root.bar.shell
        ? root.bar.shell.isPluginOpen(root.moduleName)
        : false
    readonly property real openPanelIndicatorWidth: button.labelWidth

    function open(payloadJson) {
        if (root.bar && root.bar.shell)
            root.bar.shell.summon(root.moduleName, payloadJson || "{}")
    }

    function close() {
        if (root.bar && root.bar.shell)
            root.bar.shell.hide(root.moduleName)
    }

    function togglePanel() {
        if (root.bar && root.bar.shell)
            root.bar.shell.toggle(root.moduleName, "{}")
    }

    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

    WidgetButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        text: "󰓃"
        tooltipText: "OmaValet — park apps"
        horizontalMargin: 7.5
        onPressed: function(buttonCode) {
            if (buttonCode === Qt.LeftButton) root.togglePanel()
        }
    }
}
