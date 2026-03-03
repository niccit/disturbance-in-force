// SPDX-License-Identifier: MIT
$fa = 1;
$fs = 0.4;

include <scad_libs/YAPP_Box/YAPPgenerator_v3.scad>

// PIR sensor 14mm high
// Standoff height 5mm


printBaseShell = true;
printLidShell = true;

// Using these measurments to support the PIR sensor
pcbLength = 51;
pcbWidth = 32.34;
pcbThickness = 1;

// Seeed Studio XAIO ESP32-S3
// 21, 17.8, 1mm per https://www.seeedstudio.com/XIAO-ESP32S3-p-5627.html
seeedLength = 21;
seeedWidth = 17.8;
seeedThickness = 1;

// Sensor
// sensor diam 22.72
// 24.03mm, 32.34mm
// screw hole distance 28mm
// screw hole diameter = 2mm
sensorDiam = 24;

paddingLeft = 2;
paddingRight = 2;
paddingFront = 4;
paddingBack = 1;

wallThickness = 1.5;
basePlaneThickness = 1.5;
lidPlaneThickness = 1.5;

baseWallHeight = 18;
lidWallHeight = 12;

ridgeHeight = 5;
ridgeSlack = 0.2;
roundRadius = 2.0;

standoffHeight = 5.0;
standoffPinDiameter = 2;
standoffHoleSlack = 0.5;
standoffDiameter = 4;

pcbStands =
   [
      [11.75, shellWidth/2-3.5, 25, yappHole, yappLidOnly, yappSelfThreading, yappNoFillet]       // Back
      ,[41.75, shellWidth/2-3.5, 25, yappHole, yappLidOnly, yappSelfThreading, yappNoFillet]       // Front
   ];

cutoutsBack =
   [
      [pcbWidth/2-5, -2, 10, 6.4, 0, yappRectangle]
   ];

cutoutsLid =
   [
      [shellLength/2-15, shellWidth/2-15.5, 0, 0, 12, yappCircle]    // PIR cut out
   ];

boxMounts =
   [
      [10, 5, shellWidth, 3, yappBack]
      ,[-10, 5, shellWidth, 3, yappFront]
   ];

snapJoins =
   [
      [shellLength/2, 5, yappLeft, yappRight, yappSymmetric]
      ,[shellWidth/2, 5, yappFront, yappBack, yappSymmetric]
   ];

// If no headers are being used translate should be [0, 0, 1.5], add to the inner cube height is 0.5
//     and the board will snap in
// If headers are being used short side down, I would recommend [0, 0, 3] or [0, 0, 3.5]
//    and an add of 2 to the inner cube height
// My print used [0, 0, 2.5] with an add of 2 to the inner cube height and I didn't get the board to snap in,
//     however, the wires connecting it to the sensor keep it in place
module board_mount() {
   difference() {
      cube([seeedLength + 2, seeedWidth + 1.2, 5], center=true);
      translate([0, 0, 1.5])
         cube([seeedLength + 0.5, seeedWidth + 0.5, seeedThickness + 0.5], center=true);
   }
}


YAPPgenerate();
translate([14,20,4-0.003])
   board_mount();

