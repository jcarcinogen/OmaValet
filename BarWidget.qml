import QtQuick
import Quickshell
import qs.Ui

BarWidget {
    id: root
    moduleName: "io.github.jcarcinogen.omavalet"

    function open() {}
    function close() {}

    WidgetButton {
        anchors.fill: parent
        bar: root.bar
        text: "󰓃"
        tooltipText: "OmaValet"
    }
}
