import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import qs.Commons
import "Model.js" as Model

ItemDelegate {
    id: tile
    property var appData: ({})
    property var board: null
    property string badge: ""
    property string badgeDescription: ""
    property bool compact: false
    readonly property bool iconReady: appIcon.status === Image.Ready
    readonly property bool fallbackIcon: String(appIcon.source).endsWith("/application-fallback.svg")
    property bool selected: false
    property bool draggable: true
    property bool moved: false
    signal picked()
    implicitHeight: Style.space(46)
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    Accessible.name: String(appData.name || "App") + (badgeDescription ? ", " + badgeDescription : badge ? ", " + badge : "")
    ToolTip.visible: (hovered || mouse.containsMouse) && (compact || badgeDescription.length > 0 || String(appData.name || "").length > 20)
    ToolTip.text: String(appData.name || "") + (badgeDescription ? "\n" + badgeDescription : "")
    ToolTip.delay: 500
    contentItem: RowLayout {
        spacing: Style.space(8)
        Image {
            id: appIcon
            objectName: "appIcon"
            source: Quickshell.iconPath(Model.iconName(tile.appData.icon), true) || Qt.resolvedUrl("assets/application-fallback.svg")
            Layout.preferredWidth: Style.space(tile.compact ? 28 : 24)
            Layout.preferredHeight: Style.space(tile.compact ? 28 : 24)
            fillMode: Image.PreserveAspectFit
        }
        Text {
            visible: !tile.compact
            text: String(tile.appData.name || "App")
            textFormat: Text.PlainText
            Layout.fillWidth: true
            elide: Text.ElideRight
            color: Color.menu.text
            font.family: Style.font.family
            font.pixelSize: Style.font.body
        }
        Text {
            visible: !tile.compact && tile.badge.length > 0
            text: tile.badge
            textFormat: Text.PlainText
            color: Color.accent
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
        }
    }
    Text {
        objectName: "compactBadge"
        visible: tile.compact && tile.badge.length > 0
        anchors.top: parent.top
        anchors.right: parent.right
        text: tile.badge
        textFormat: Text.PlainText
        color: Color.accent
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
    }
    background: Rectangle {
        radius: Style.cornerRadius
        color: Qt.alpha(tile.selected ? Color.accent : Color.menu.text,
                        tile.selected ? 0.16 : tile.hovered ? 0.09 : 0.035)
        border.width: tile.activeFocus || tile.selected ? Math.max(1, Style.space(1)) : 0
        border.color: Color.accent
    }
    onClicked: picked()
    MouseArea {
        id: mouse
        anchors.fill: parent
        enabled: tile.enabled
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        drag.target: tile.draggable && tile.board ? tile.board.dragItem : null
        onPressed: function(event) {
            tile.moved = false
            tile.forceActiveFocus()
            if (tile.draggable && tile.board) {
                var point = tile.mapToItem(tile.board, event.x, event.y)
                tile.board.prepareDrag(tile.appData, point.x, point.y)
            }
        }
        onPositionChanged: {
            if (drag.active && tile.board) {
                tile.moved = true
                tile.board.dragging = true
            }
        }
        onReleased: {
            if (tile.board && tile.moved) tile.board.finishDrag()
        }
        onCanceled: if (tile.board) tile.board.cancelDrag()
        onClicked: if (!tile.moved) tile.picked()
    }
}
