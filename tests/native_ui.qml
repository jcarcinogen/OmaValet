import QtQuick
import QtTest
import Quickshell
import "plugin"

// Native Qt interaction tests in an isolated HOME. Backend failure is intentional:
// these tests assert UI command arguments, not successful compositor application.
ShellRoot {
    Window {
        id: window
        width: 1100; height: 740; visible: true
        Board { id: board; anchors.fill: parent; scriptPath: "/nonexistent/omavalet-ui-fixture.py" }
        TestCase {
            id: tests
            when: false
            property int passed: 0
            function check(value, message) { if (!value) throw new Error(message) }
            function equal(actual, expected, message) { check(JSON.stringify(actual) === JSON.stringify(expected), message + ": " + JSON.stringify(actual)) }
            function child(name) { var result = findChild(board, name); check(result !== null, "Missing " + name); return result }
            function fixture() {
                var entries = []
                for (var i=0; i<12; i++) entries.push({desktopId:"qa"+i+".desktop",name:"QA App "+i,icon:"application-x-executable",workspace:1,launchOnStart:false})
                return {catalog:entries,valet:entries.slice(0,12),workspaceCount:10,existing:{parking:[{name:"Locked external app",class:"locked",workspace:2,source:"windows.lua"}]},settings:{celebrations:true,reducedMotion:false},undoAvailable:true}
            }
            function reset() {
                board.close()
                board.active = true
                board.selectedApp = null
                board.detailRow = null
                board.destinationMode = false
                board.filter = "All"
                board.hasError = false
                board.retryAvailable = false
                child("appSearch").text = ""
                board.applySnapshot(fixture())
                wait(60)
            }
            function test_search_digits() {
                var search = child("appSearch")
                search.forceActiveFocus()
                keyClick(Qt.Key_9)
                equal(search.text,"9","Search keeps digit")
                equal(board.debugState().appCount,1,"Search result count")
                check(!board.busy,"Digit did not park")
                keyClick(Qt.Key_Escape)
                equal(search.text,"","Escape clears search")
            }
            function test_keyboard_destination() {
                var search = child("appSearch")
                search.forceActiveFocus()
                keyClick(Qt.Key_Return)
                check(board.destinationMode,"Enter enters destination mode")
                equal(board.selectedApp.desktopId,"qa0.desktop","First result selected")
                keyClick(Qt.Key_3)
                equal(board.actionName,"park","Number dispatches park")
                equal(child("backendRequest").command.slice(-3),["park","qa0.desktop","3"],"Exact keyboard destination")
                tryCompare(board,"busy",false,2000)
                check(board.hasError,"Real process failure is visible")
                equal(board.snapshot.valet.length,12,"Failure preserves last-good board")
            }
            function test_click_and_overflow() {
                mouseClick(child("more-1"))
                equal(board.expandedLane,1,"Overflow opens")
                equal(child("expandedAssignments").count,12,"All overflow assignments reachable")
                mouseClick(child("dialogClose"))
                equal(board.expandedLane,0,"Dialog closes")
                board.inspect({name:"Locked",owned:false,source:"windows.lua"},2)
                check(!child("removeAssignment").visible,"External rule has no remove")
            }
            function test_workspace_icons_at_narrow_width() {
                var originalWidth=window.width
                try {
                    window.width=800; wait(100)
                    var tile=child("assigned-1-qa0.desktop")
                    check(tile.compact && tile.visible,"Assigned icon remains visible at narrow width")
                    var icon=findChild(tile,"appIcon")
                    check(icon && String(icon.source).length>0,"Assigned icon resolves to a theme image")
                    tryCompare(icon,"status",Image.Ready,2000)
                    check(icon.status===Image.Ready,"Assigned icon actually decodes")
                    var lane=child("lane-1"), point=tile.mapToItem(lane,0,0)
                    check(point.x>=0 && point.x+tile.width<=lane.width,"Icon fits inside workspace row")
                    check(child("more-1").visible,"Overflow stays reachable beside icons")
                    mouseClick(tile)
                    equal(board.detailRow.desktopId,"qa0.desktop","Icon click selects assigned app")
                    var locked=child("assigned-2-locked")
                    check(locked.compact && !locked.draggable,"External assignment has a locked icon tile")
                } finally { window.width=originalWidth; wait(100) }
            }
            function test_drag_to_lane() {
                var tile = child("app-qa0.desktop")
                var lane = child("lane-2")
                var start = tile.mapToItem(board, tile.width/2,tile.height/2)
                var end = lane.mapToItem(board,lane.width/2,lane.height/2)
                board.actionName = ""
                mousePress(board,start.x,start.y,Qt.LeftButton)
                for(var i=1;i<=12;i++) mouseMove(board,start.x+(end.x-start.x)*i/12,start.y+(end.y-start.y)*i/12,15)
                mouseRelease(board,end.x,end.y,Qt.LeftButton)
                wait(60)
                equal(board.actionName,"park","Drag dispatches park")
                equal(child("backendRequest").command.slice(-3),["park","qa0.desktop","2"],"Exact drag destination")
                check(!board.dragging,"Drag state cleaned")
                tryCompare(board,"busy",false,2000)
            }
            function test_ten_lanes_scroll() {
                var list=child("workspaceList")
                equal(list.count,10,"Ten lanes")
                list.positionViewAtEnd()
                wait(100)
                var last=child("park-10")
                check(last.height>=40,"Last lane has full button target")
                var point=last.mapToItem(list,0,0)
                check(point.y>=0 && point.y+last.height<=list.height,"Last lane is reachable by scroll")
            }
            function test_malformed_snapshot_and_retry() {
                board.actionName="snapshot"
                board.consume("not json",0)
                check(board.hasError,"Malformed JSON detected")
                equal(board.snapshot.valet.length,12,"Malformed JSON preserves assignments")
                board.actionName="park"
                board.consume(JSON.stringify({ok:false,saved:true,applied:false,error:"Fixture reload failed",snapshot:fixture()}),1)
                check(board.retryAvailable,"Saved-only failure offers retry")
                check(child("retryButton").visible,"Retry is visible")
            }
            function test_success_clears_retry() {
                board.actionName="park"
                board.consume(JSON.stringify({ok:false,saved:true,applied:false,error:"reload failure",snapshot:fixture()}),1)
                check(board.retryAvailable,"Retry offered on failed apply")
                board.actionName="retry"
                board.consume(JSON.stringify({ok:true,saved:true,applied:true,snapshot:fixture()}),0)
                check(!board.retryAvailable && !child("retryButton").visible,"Applied success clears Retry")
            }
            function test_rapid_requests_are_serialized() {
                check(board.requestAction(["park","qa0.desktop","2"],"First"),"First accepted")
                check(!board.requestAction(["undo"],"Second"),"Immediate second request refused")
                equal(child("backendRequest").command.slice(-3),["park","qa0.desktop","2"],"Pending argv is not overwritten")
                for(var i=0;i<100 && board.busy;i++) wait(20)
                check(!board.busy,"Request completes")
            }
            function test_settings_focus_and_off() {
                mouseClick(child("settingsButton"))
                check(board.settingsOpen,"Settings opens")
                keyClick(Qt.Key_Tab)
                check(!child("appSearch").activeFocus,"Modal focus does not enter background")
                board.settingsOpen=false
                var value=fixture();value.settings.celebrations=false;board.applySnapshot(value)
                board.celebrate()
                check(!board.debugState().cameoLoaded,"Off setting blocks cameo")
            }
            function test_reduced_motion() {
                var value=fixture();value.settings.reducedMotion=true;board.applySnapshot(value)
                board.celebrate();wait(100)
                check(board.debugState().cameoLoaded,"Reduced-motion still is shown")
                equal(board.debugState().frameCount,0,"Animation is not instantiated")
                wait(1850)
                check(!board.debugState().cameoLoaded,"Still unloads")
            }
            function test_animation_and_teardown() {
                board.celebrate();wait(160)
                equal(board.debugState().frameCount,97,"Native Qt decodes all frames")
                var before=board.debugState().frame
                wait(280)
                check(board.debugState().frame>before,"Animation advances")
                board.close();wait(20)
                check(!board.debugState().cameoLoaded,"Close unloads animation")
                board.active=true;board.celebrate()
                tryCompare(board,"cameoActive",false,6000)
                check(!board.debugState().cameoLoaded,"Finite animation unloads after timeout")
            }
            function run() {
                var names=["search_digits","keyboard_destination","click_and_overflow","workspace_icons_at_narrow_width","drag_to_lane","ten_lanes_scroll","malformed_snapshot_and_retry","success_clears_retry","rapid_requests_are_serialized","settings_focus_and_off","reduced_motion","animation_and_teardown"]
                var failures=[]
                for (var i=0;i<names.length;i++) {
                    try { reset(); tests["test_"+names[i]](); passed++; console.log("NATIVE_PASS",names[i]) }
                    catch(error) { failures.push(names[i]+": "+String(error)); console.error("NATIVE_FAIL",names[i],String(error)) }
                }
                reset()
                board.grabToImage(function(result) { result.saveToFile(Quickshell.env("OMAVALET_TEST_OUTPUT") + "/board-tested.png") })
                wait(100)
                console.log("NATIVE_RESULT",JSON.stringify({passed:passed,failed:failures.length,failures:failures}))
            }
        }
    }
    Timer { interval:300; running:true; onTriggered: { tests.run(); Qt.quit() } }
}
