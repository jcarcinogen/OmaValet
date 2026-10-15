import QtQuick
import Quickshell
import qs.Commons
import "plugin"

// Marketing captures use the real components with public, fictional assignments.
// No backend calls, personal desktop data, windows or user settings are read.
ShellRoot {
    Window {
        width: 1100; height: 740; visible: true
        Board { id: board; anchors.fill: parent; scriptPath: "/nonexistent/preview-no-mutations.py" }
    }
    property var demoApps: [
        {desktopId:"brave-origin.desktop",name:"Brave Origin",icon:"brave-origin",workspace:1,launchOnStart:true},
        {desktopId:"chromium.desktop",name:"Chromium",icon:"chromium",workspace:4,launchOnStart:false},
        {desktopId:"Discord.desktop",name:"Discord",icon:"omarchy-discord",workspace:3,launchOnStart:false},
        {desktopId:"org.gnome.Nautilus.desktop",name:"Files",icon:"org.gnome.Nautilus",workspace:2,launchOnStart:false},
        {desktopId:"nvim.desktop",name:"Neovim",icon:"nvim",workspace:2,launchOnStart:false},
        {desktopId:"org.telegram.desktop.desktop",name:"Telegram",icon:"org.telegram.desktop",workspace:5,launchOnStart:true}
    ]
    Timer {
        interval: 1000; running: true
        onTriggered: {
            board.active=true
            board.applySnapshot({catalog:demoApps,valet:demoApps,workspaceCount:5,existing:{parking:[]},settings:{celebrations:true,reducedMotion:false},undoAvailable:false,applyPending:false,accessMode:"bar"})
            if (Quickshell.env("OMAVALET_PREVIEW_EXPANDED") === "1") board.expandedLane=5
            capture.start()
        }
    }
    Timer {
        id: capture
        interval: 500
        onTriggered: {
            var icons=board.visibleAssignmentIcons()
            if (icons.length!==6 || icons.some(function(icon){return !icon.ready || icon.fallback})) {
                console.error("PREVIEW_FAIL",JSON.stringify(icons)); Qt.quit(); return
            }
            board.grabToImage(function(result) {
                var saved=result.saveToFile(Quickshell.env("OMAVALET_PREVIEW_OUTPUT"))
                console.log(saved ? "PREVIEW_CAPTURE_PASS" : "PREVIEW_FAIL",JSON.stringify(board.debugState()))
                Qt.quit()
            },Qt.size(2200,1480))
        }
    }
}
