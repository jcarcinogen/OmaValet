import QtQuick
import QtTest
import Quickshell
import "plugin"
ShellRoot {
    Overlay { id: overlay }
    TestCase {
        id: tests; when:false
        function check(value,label) { if(!value) throw new Error(label) }
        function run() {
            overlay.open("{}")
            wait(300)
            var board=findChild(overlay,"omavaletBoard")
            check(!!board,"Hosted Board exists")
            for(var i=0;i<200 && board.busy;i++) wait(20)
            check(!board.busy && !board.hasError,"Hosted snapshot loaded")
            check(board.snapshot.catalog.length>0,"Hosted catalog populated")
            mouseClick(findChild(board,"settingsButton"))
            check(board.settingsOpen,"Native settings click")
            keyClick(Qt.Key_Escape)
            check(!board.settingsOpen,"Escape closes settings")
            board.celebrate();wait(200)
            check(board.debugState().cameoLoaded,"Cameo loaded in real Wayland layer")
            board.grabToImage(function(result){console.log("NATIVE_CAPTURE",result.saveToFile(Quickshell.env("OMAVALET_TEST_OUTPUT") + "/native-board.png"))})
            wait(100)
            overlay.close();wait(100)
            check(!overlay.opened && !board.debugState().cameoLoaded,"Close unloads cameo")
            overlay.open("{}");wait(300)
            keyClick(Qt.Key_Escape)
            check(!overlay.opened,"Escape closes actual overlay")
            console.log("WAYLAND_OVERLAY_PASS")
        }
    }
    Timer{interval:300;running:true;onTriggered:{try{tests.run()}catch(error){console.error("WAYLAND_OVERLAY_FAIL",String(error))}overlay.close();Qt.quit()}}
}
