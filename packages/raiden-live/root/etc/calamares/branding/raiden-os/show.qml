/* @DISTRO_NAME@ installer slideshow (Calamares slideshow API 1). */
import QtQuick 2.0;
import calamares.slideshow 1.0;

Presentation
{
    id: presentation

    Timer {
        interval: 12000
        running: true
        repeat: true
        onTriggered: presentation.goToNextSlide()
    }

    // Dark backdrop behind everything (no white edges between slides)
    Rectangle { anchors.fill: parent; color: "#0B1020" }

    component InfoSlide: Slide {
        id: slide
        property string image
        property string heading
        property string body

        // Use the whole slideshow area instead of the default content box
        x: 0
        y: 0
        width: parent.width
        height: parent.height

        Rectangle { anchors.fill: parent; color: "#0B1020" }
        Image {
            anchors.fill: parent
            source: slide.image
            fillMode: Image.PreserveAspectCrop
            smooth: true
        }
        Column {
            anchors.left: parent.left
            anchors.leftMargin: parent.width * 0.07
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width * 0.58
            spacing: 16
            Text {
                width: parent.width
                text: slide.heading
                color: "#FFFFFF"
                font.pixelSize: 30
                font.bold: true
                wrapMode: Text.WordWrap
            }
            Rectangle { width: 64; height: 4; radius: 2; color: "#2BD9F0" }
            Text {
                width: parent.width
                text: slide.body
                color: "#DCE3FF"
                font.pixelSize: 17
                lineHeight: 1.25
                wrapMode: Text.WordWrap
            }
        }
    }

    InfoSlide {
        image: "slide1.jpg"
        heading: qsTr("Welcome to @DISTRO_NAME@")
        body: qsTr("Fast, beautiful and familiar. Sit back while it installs; it only takes a few minutes.")
    }
    InfoSlide {
        image: "slide2.jpg"
        heading: qsTr("Make it yours")
        body: qsTr("Open Appearance to switch between a Windows-like taskbar, a centered Windows 11 style, a macOS-like dock or classic GNOME. Light or dark, your accent colour, your wallpaper.")
    }
    InfoSlide {
        image: "slide3.jpg"
        heading: qsTr("Thousands of apps")
        body: qsTr("Google Chrome, LibreOffice, Outlook, Microsoft 365, Claude and Antigravity are part of it, and Software brings thousands more apps from Flathub and Ubuntu together in one place.")
    }
    InfoSlide {
        image: "slide4.jpg"
        heading: qsTr("Ready for games")
        body: qsTr("Steam, Heroic, Lutris and ProtonPlus are installed, tuned for Windows games through Proton with GameMode and MangoHud. NVIDIA GeForce (GTX 750 and newer), AMD Radeon and Intel graphics get the right driver automatically.")
    }
    InfoSlide {
        image: "slide5.jpg"
        heading: qsTr("All-day battery")
        body: qsTr("Power modes in the quick settings, automatic power saving when the battery runs low, battery health protection on supported laptops and compressed memory for a smooth desktop.")
    }
    InfoSlide {
        image: "slide6.jpg"
        heading: qsTr("Safe and always up to date")
        body: qsTr("Security updates install automatically, Secure Boot is supported and Timeshift snapshots can roll your system back at any time.")
    }
}
