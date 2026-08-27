import QtQuick

Item {
    id: root
    property bool opened: false

    function open(payloadJson) { opened = true }
    function close() { opened = false }
}
