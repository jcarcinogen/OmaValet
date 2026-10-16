import QtQuick
import Quickshell.Io
import qs.Commons

// TextInput/TextField eagerly retrieves clipboard offers on affected Qt builds.
// TextEdit keeps native editing/IME and checks formats without fetching payloads.
// Never call its native paste() method.
FocusScope {
    id: field
    property alias text: editor.text
    property alias cursorPosition: editor.cursorPosition
    readonly property int selectionStart: editor.selectionStart
    readonly property int selectionEnd: editor.selectionEnd
    readonly property int textFormat: editor.textFormat
    property bool pasteAllowed: true
    property string helperPath: String(Qt.resolvedUrl("scripts/clipboard_safe_paste.py")).replace("file://", "")
    readonly property int maximumSearchLength: 256
    readonly property bool pastePending: pasteProcess.running
    property int revision: 0
    property int requestedRevision: -1
    property int requestedStart: 0
    property int requestedEnd: 0
    signal navigationKey(var event)
    signal pasteFailed(string message)
    implicitHeight: Style.space(42)
    activeFocusOnTab: true

    function clear() { editor.clear() }
    function selectAll() { editor.selectAll() }
    function boundedText(value) {
        var cleaned = value.replace(/[\r\n\t\u2028\u2029]/g, " ").replace(/[\u0000-\u001f\u007f-\u009f]/g, "")
        cleaned = cleaned.slice(0, maximumSearchLength)
        if (cleaned.length && /[\uD800-\uDBFF]/.test(cleaned.charAt(cleaned.length - 1))) cleaned = cleaned.slice(0, -1)
        return cleaned
    }
    onTextChanged: {
        revision++
        var clean = boundedText(text)
        if (clean !== text) {
            var position = cursorPosition
            text = clean
            cursorPosition = Math.min(position, text.length)
        }
    }
    onCursorPositionChanged: revision++
    onSelectionStartChanged: revision++
    onSelectionEndChanged: revision++
    onActiveFocusChanged: revision++
    onPasteAllowedChanged: revision++
    onEnabledChanged: revision++
    onVisibleChanged: revision++

    function requestPaste() {
        if (!pasteAllowed || !activeFocus || !enabled || !visible || pastePending) return
        requestedRevision = revision
        requestedStart = selectionStart
        requestedEnd = selectionEnd
        pasteProcess.running = true
    }
    function acceptPaste(reply, exitCode) {
        if (requestedRevision !== revision || !pasteAllowed || !activeFocus || !enabled || !visible) return
        var value
        try { value = JSON.parse(reply) } catch (_) { value = null }
        if (exitCode !== 0 || !value || value.ok !== true || typeof value.text !== "string") {
            pasteFailed("Paste skipped: clipboard unavailable, too large, or too slow.")
            return
        }
        if (value.text.length + text.length - (requestedEnd - requestedStart) > maximumSearchLength) {
            pasteFailed("Paste skipped: search is limited to 256 characters.")
            return
        }
        var start = requestedStart
        var end = requestedEnd
        var inserted = boundedText(value.text)
        if (end > start) editor.remove(start, end)
        editor.insert(start, inserted)
        cursorPosition = start + inserted.length
    }
    Rectangle {
        anchors.fill: parent
        color: Qt.alpha(Color.menu.text, 0.06)
        radius: Style.cornerRadius
        border.width: field.activeFocus ? 1 : 0
        border.color: Color.accent
    }
    Flickable {
        id: viewport
        objectName: "searchViewport"
        anchors.fill: parent
        anchors.leftMargin: Style.space(12)
        anchors.rightMargin: Style.space(12)
        contentWidth: editor.width
        contentHeight: height
        interactive: false
        clip: true
        function ensureCursorVisible() {
            var x = editor.cursorRectangle.x
            var right = x + editor.cursorRectangle.width
            var target = contentX
            if (x < target) target = x
            if (right > target + width) target = right - width
            contentX = Math.max(0, Math.min(target, contentWidth - width))
        }
        onWidthChanged: ensureCursorVisible()
        TextEdit {
            id: editor
            objectName: "searchEditor"
            focus: true
            width: Math.max(viewport.width, contentWidth + 2)
            height: viewport.height
            topPadding: Math.max(0, (height - font.pixelSize * 1.2) / 2)
            textFormat: TextEdit.PlainText
            wrapMode: TextEdit.NoWrap
            selectByMouse: true
            color: Color.menu.text
            selectionColor: Color.accent
            selectedTextColor: Color.menu.background
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            Accessible.name: "Search apps"
            Accessible.description: "Search installed apps. Paste is limited to 4 KiB and 256 search characters."
            onCursorRectangleChanged: viewport.ensureCursorVisible()
            onContentWidthChanged: viewport.ensureCursorVisible()
            Keys.priority: Keys.BeforeItem
            Keys.onPressed: function(event) {
                if (event.matches(StandardKey.Paste) || (event.key === Qt.Key_Insert && (event.modifiers & Qt.ShiftModifier))) {
                    event.accepted = true
                    field.requestPaste()
                } else {
                    field.navigationKey(event)
                    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) event.accepted = true
                }
            }
        }
    }
    Text {
        x: Style.space(12)
        anchors.verticalCenter: parent.verticalCenter
        visible: field.text.length === 0 && !editor.inputMethodComposing
        text: "Search apps"
        textFormat: Text.PlainText
        color: Qt.alpha(Color.menu.text, 0.7)
        font: editor.font
    }
    // Plain TextEdit has no built-in context menu. Swallow right/middle buttons
    // across the complete field before Qt can read the primary selection.
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.MiddleButton | Qt.RightButton
        onPressed: function(mouse) { mouse.accepted = true }
        onReleased: function(mouse) { mouse.accepted = true }
    }
    // External text drops are unsupported; app-tile DnD is separate.
    DropArea {
        anchors.fill: parent
        onEntered: function(drag) { drag.accepted = false }
        onDropped: function(drop) { drop.accepted = false }
    }
    Process {
        id: pasteProcess
        objectName: "safePasteProcess"
        command: ["python3", field.helperPath]
        stdout: StdioCollector { id: pasteOutput; waitForEnd: true }
        stderr: StdioCollector { waitForEnd: true }
        onExited: function(exitCode) { field.acceptPaste(pasteOutput.text, exitCode) }
    }
}
