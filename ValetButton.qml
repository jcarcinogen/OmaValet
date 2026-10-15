import QtQuick
import QtQuick.Controls
import qs.Commons

Button {
    id: control
    property bool emphasized: false
    property string hint: ""
    implicitHeight: Style.space(40)
    implicitWidth: Math.max(Style.space(40), label.implicitWidth + Style.space(24))
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    Accessible.name: text
    ToolTip.visible: hovered && hint.length > 0
    ToolTip.text: hint
    ToolTip.delay: 500
    contentItem: Text {
        id: label
        text: control.text
        textFormat: Text.PlainText
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
        color: control.checked || control.emphasized ? Color.accent : Color.menu.text
        opacity: control.enabled ? 1 : 0.45
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        radius: Style.cornerRadius
        color: Qt.alpha(control.checked || control.emphasized ? Color.accent : Color.menu.text,
                        control.down ? 0.22 : control.hovered ? 0.13 : 0.06)
        border.width: control.activeFocus || control.checked ? Math.max(1, Style.space(1)) : 0
        border.color: Color.accent
    }
}
