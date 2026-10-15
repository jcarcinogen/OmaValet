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
            var lanes=findChild(board,"workspaceList")
            lanes.positionViewAtEnd();wait(100)
            var workspaceFive=findChild(board,"park-5")
            var center=workspaceFive.mapToItem(lanes,workspaceFive.width/2,workspaceFive.height/2)
            check(center.y>=0 && center.y<lanes.height,"Workspace 5 click is inside visible list")
            mouseClick(workspaceFive);wait(80)
            check(board.expandedLane===5,"Native workspace 5 popup opens")
            var login=findChild(board,"expandedLogin-qa-alpha.desktop")
            check(login && login.visible,"Native popup login button exists")
            mouseClick(login)
            for(var n=0;n<150 && board.busy;n++) wait(20)
            wait(60)
            check(!board.busy && !board.hasError,"Native popup login save succeeds")
            check(board.expandedLane===5 && findChild(board,"expandedLogin-qa-alpha.desktop").text==="Start at login: Off","Native popup stays open and updates")
            mouseClick(findChild(board,"dialogClose"));wait(60)
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
