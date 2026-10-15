import QtQuick
import QtTest
import Quickshell
import "plugin"
ShellRoot {
    Window {
        visible: true; width:1100; height:740
        Board { id:board; anchors.fill:parent }
        TestCase {
            id:tests; when:false
            function check(value,label) { if(!value) throw new Error(label + ": " + JSON.stringify(board.debugState())) }
            function settled() { for(var n=0; n<150 && board.busy; n++) wait(20); check(!board.busy,"Backend completed"); wait(30); check(!board.hasError,"Backend operation") }
            function run() {
                board.open();settled()
                check(board.snapshot.valet.length===0,"Empty initial state")
                for(var i=0;i<3;i++) {
                    var app=board.snapshot.catalog.find(function(x){return x.desktopId===["qa-alpha.desktop","qa-beta.desktop","qa-gamma.desktop"][i]})
                    check(!!app,"Fixture desktop app")
                    board.chooseApp(app);board.park(app,i===0 ? 5 : i+1);settled()
                    check(board.snapshot.valet.length===i+1,"Applied assignment")
                }
                check(board.debugState().cameoLoaded,"Real backend milestone triggers cameo")
                board.requestAction(["undo"],"Undo…");settled()
                check(board.snapshot.valet.length===2,"Undo reflected in UI")
                board.requestAction(["settings","reduced-motion","on"],"Motion…");settled()
                check(board.settings.reducedMotion===true,"Settings response contract")
                board.inspect(Object.assign({},board.snapshot.valet[0],{owned:true}),5)
                board.requestAction(["running"],"Windows…");settled()
                check(board.runningWindows.length===1,"Running window contract")
                board.requestAction(["identify","qa-alpha.desktop","0xabc","qa-special"],"Identify…");settled()
                check(board.snapshot.valet[0].class==="^qa\\-special$","Identity persisted")
                var login=findChild(board,"loginToggle")
                check(login && login.visible && login.enabled,"Login control is reachable")
                mouseClick(login);settled()
                check(board.snapshot.valet[0].launchOnStart===true,"Click turns login on")
                check(login.text==="Start at login: On","Login button reflects saved On")
                mouseClick(login);settled()
                check(board.snapshot.valet[0].launchOnStart===false,"Second click turns login off")
                mouseClick(login);settled()
                check(board.snapshot.valet[0].launchOnStart===true,"Third click turns login on again")
                var lanes=findChild(board,"workspaceList")
                lanes.positionViewAtEnd();wait(100)
                var workspaceFive=findChild(board,"park-5")
                var center=workspaceFive.mapToItem(lanes,workspaceFive.width/2,workspaceFive.height/2)
                check(center.y>=0 && center.y<lanes.height,"Workspace 5 click is inside visible list")
                mouseClick(workspaceFive);wait(80)
                check(board.expandedLane===5,"Workspace 5 opens assignment popup")
                for(var toggle=0;toggle<2;toggle++) {
                    var popupLogin=findChild(board,"expandedLogin-qa-alpha.desktop")
                    check(popupLogin && popupLogin.visible && popupLogin.enabled,"Popup login control is reachable")
                    mouseClick(popupLogin);settled()
                    check(board.expandedLane===5,"Login toggle keeps popup open")
                    check(board.snapshot.valet[0].launchOnStart===(toggle===1),"Popup click persists correct login state")
                    popupLogin=findChild(board,"expandedLogin-qa-alpha.desktop")
                    check(popupLogin.text==="Start at login: "+(toggle===1 ? "On" : "Off"),"Recreated popup row reflects saved state")
                }
                board.requestAction(["snapshot"],"Refresh…");settled()
                check(board.snapshot.valet[0].launchOnStart===true,"Popup choice survives disk reload")
                mouseClick(findChild(board,"dialogClose"));wait(60)
                var assigned=findChild(board,"assigned-5-qa-alpha.desktop")
                check(assigned.badge==="󱓞","Workspace 5 rocket reflects popup choice")
                board.requestAction(["test-launch","qa-alpha.desktop"],"Launch…");settled()
                check(board.statusText.indexOf("Launch requested")===0,"Explicit launch feedback")
                board.setAccessMode("menu");settled()
                board.requestAction(["snapshot"],"Refresh…");settled()
                check(board.accessMode==="menu","Menu access persists across snapshot")
                board.setAccessMode("bar");settled()
                board.requestAction(["snapshot"],"Refresh…");settled()
                check(board.accessMode==="bar","Bar access persists across snapshot")
                board.close()
                console.log("INTEGRATION_PASS",JSON.stringify({assignments:board.snapshot.valet.length,identifiedClass:board.snapshot.valet[0].class,settings:board.settings}))
            }
        }
    }
    Timer { interval:300;running:true;onTriggered:{try{tests.run()}catch(error){console.error("INTEGRATION_FAIL",String(error))}Qt.quit()} }
}
