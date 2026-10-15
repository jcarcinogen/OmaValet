import QtQuick
import QtQuick.Layouts
import qs.Commons

// Instantiated only for a finite cameo. No window, input handler, audio or poller.
Item {
    id: cameo
    property bool reducedMotion: false
    readonly property int frame: animation.item ? animation.item.currentFrame : -1
    readonly property int frameCount: animation.item ? animation.item.frameCount : 0
    signal finished()
    implicitWidth: Style.space(190)
    implicitHeight: Style.space(220)
    ColumnLayout {
        anchors.fill: parent
        spacing: Style.space(3)
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Loader {
                id: animation
                anchors.fill: parent
                active: !cameo.reducedMotion
                sourceComponent: AnimatedImage {
                    objectName: "cyberTrenchAnimation"
                    source: "assets/cyber-trench.webp"
                    fillMode: Image.PreserveAspectFit
                    cache: false
                    playing: true
                    onStatusChanged: if (status === Image.Error) cameo.finished()
                }
            }
            Loader {
                anchors.fill: parent
                active: cameo.reducedMotion
                sourceComponent: Image {
                    source: "assets/cyber-trench.png"
                    fillMode: Image.PreserveAspectFit
                    onStatusChanged: if (status === Image.Error) cameo.finished()
                }
            }
        }
        Text {
            Layout.fillWidth: true
            text: "Everything in its place."
            textFormat: Text.PlainText
            color: Color.accent
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            horizontalAlignment: Text.AlignHCenter
        }
        Text {
            Layout.fillWidth: true
            text: "Double-click the logo to replay."
            textFormat: Text.PlainText
            color: Color.menu.text
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
    }
    Timer { interval: cameo.reducedMotion ? 1800 : 4200; running: true; onTriggered: cameo.finished() }
}
