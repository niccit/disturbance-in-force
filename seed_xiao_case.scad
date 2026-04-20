// OpenSCAD file
// Created: 3/27/26
// Case/enclosure for Seeed Studio XIAO board

$fn = 50; // Circle resolution
$fs = 0.4;

include <scad_libs/YAPP_Box/YAPPgenerator_v3.scad>

// --- YAPP setup --- //

printBaseShell = true;
printLidShell = true;

// Length and width from https://www.adafruit.com/product/5700
pcbLength = 21.7;
pcbWidth = 17.8;
pcbThickness = 5.7;

paddingFront = 2;
paddingBack = 5;
paddingRight = 5;
paddingLeft = 5;

wallThickness = 1.5;
basePlaneThickness = 1.5;
lidPlaneThickness = 1.5;

baseWallHeight = 5;
lidWallHeight = 8;

ridgeHeight = 4;
ridgeSlack = 0.2;
roundRadius = 2;

standoffHeight = 3;
standoffPinDiameter = 0.3;
standoffHoleSlack = 0.5;
standoffDiameter = 2;

cutoutsBack = [
   [3, -7.5, 12, 7.5, 2, yappRoundedRect]
];

boxMounts = [
    [-6, 3, shellWidth, 1.5, yappFront, yappBase]
];

snapJoins = [
    [shellLength / 2, 5, yappLeft, yappRight, yappSymmetric, yappRectangle]
   ,[shellWidth / 2, 5, yappFront, yappSymmetric, yappRectangle]
   ,[2, 5, yappBack, yappSymmetric, yappRectangle]
    ];

module secure_board() {
   difference() {
        cube([pcbLength + 2, pcbWidth + 2, pcbThickness], center=true);
        translate([0,  0, 0])
            color("blue")cube([pcbLength - 0.55, pcbWidth - 0.10, (pcbThickness) + 0.5], center=true);
        translate([pcbWidth - 6, 0, 0])
            color("red")cube([3, pcbWidth - 4, (pcbThickness) + 0.5], center=true);
        translate([-pcbWidth + 6, 0, 0])
            color("red")cube([3, pcbWidth - 4, (pcbThickness) + 0.5], center=true);
        translate([0, pcbLength - 12, 0])
            color("green")cube([pcbLength - 4, 3, (pcbThickness) + 0.5], center=true);
        translate([0, - pcbLength + 12, 0])
            color("green")cube([pcbLength - 4, 3, (pcbThickness) + 0.5], center=true);
   }
}

module baseHookInside() {
    translate([shellLength / 2 - (wallThickness - 1), shellWidth / 2 - (wallThickness - 1.5), 3 - 0.01])
        secure_board();
}


YAPPgenerate();
baseHookInside();
// secure_board();
