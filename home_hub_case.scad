use <garage_sensor_case.scad>
// SPDX-License-Identifier: MIT
$fa = 1;
$fs = 0.4;

include <scad_libs/YAPP_Box/YAPPgenerator_v3.scad>

// --- YAPP setup --- //

printBaseShell = true;
printLidShell = true;

// Length and width from https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-mechanical-drawing.pdf
pcbLength = 85;
pcbWidth = 56;
pcbThickness = 1.6;

paddingFront = 4;
paddingBack = 2;
paddingRight = 4;
paddingLeft = 3;

wallThickness = 1.5;
basePlaneThickness = 1.5;
lidPlaneThickness = 1.5;

baseWallHeight = 10;
lidWallHeight = 15;

ridgeHeight = 5;
ridgeSlack = 0.2;
roundRadius = 2;

standoffHeight = 5.0;
standoffPinDiameter = 2;
standoffHoleSlack = 0.5;
standoffDiameter = 4;

cutoutsBack = [
   [20.5, -6.5, 15, 5, 0, yappRectangle]                     // SD card slot
   ];

cutoutsLeft = [
   [6.5, -3, 11.42, 8.26, 0, yappRectangle]                // Power
   ,[20.25, -3, 25.5, 7, 0, yappRectangle]                   // HDMI 0 & 1
   ];

cutoutsFront = [
   [3.5, -1.75, 50.6, 16, 0, yappRectangle]                      // Ethernet, USB
   ];

cutoutsBase = [
    [85 / 2, 56 / 2, 50, 30, 20, yappCircle, maskOffsetBars, yappCenter]
    ];

snapJoins = [
    [shellLength, 5, yappLeft, yappRight, yappSymmetric, yappRectangle]
   ,[shellWidth, 5, yappFront, yappBack, yappSymmetric, yappRectangle]
    ];

labelsPlane = [
   [47, 30, 180, 2, yappLid, "Henny Penny:style=bold", 8, "No Touch The Pi", 0, yappTextLeftToRight, yappTextHAlignCenter, yappTextVAlignCenter]
   ];

module secure_board() {
   difference() {
        cube([pcbLength + 2, pcbWidth + 2, 6.5], center=true);
        translate([0,  0, 0])
            color("blue")cube([pcbLength + 0.3, (pcbWidth) + 0.3, 6.5], center=true);
        translate([(pcbLength / 2), 0, 0])
            color("red")cube([3, pcbWidth - 4, 6.5], center=true);
        translate([(-pcbLength / 2), 0, 0])
            color("red")cube([3, pcbWidth - 10, 6.5], center=true);
        translate([0, (pcbWidth / 2), 0])
            color("green")cube([pcbLength - 10, 3, 6.5], center=true);
        translate([0, - (pcbWidth / 2), 0])
            color("green")cube([pcbLength - 10, 3, 6.5], center=true);
   }
}

module baseHookInside() {
    translate([pcbLength / 2 + 3.5, pcbWidth / 2 + 5, 3.5 - 0.01])
        secure_board();
}

YAPPgenerate();
baseHookInside();