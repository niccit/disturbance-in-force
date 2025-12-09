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
paddingRight = 1;
paddingLeft = 3;

wallThickness = 1.5;
basePlaneThickness = 1.5;
lidPlaneThickness = 1.5;

baseWallHeight = 20;
lidWallHeight = 18;

ridgeHeight = 5;
ridgeSlack = 0.2;
roundRadius = 2;

standoffHeight = 5.0;
standoffPinDiameter = 2;
standoffHoleSlack = 0.5;
standoffDiameter = 4;

pcbStands = [
   [3, 3, yappHole, yappBaseOnly, yappSelfThreading]     // back left
   ,[3, 52, yappHole, yappBaseOnly, yappSelfThreading]   // back right
   ,[61, 3, yappHole, yappBaseOnly, yappSelfThreading]   // front left
   ,[61, 52, yappHole, yappBaseOnly, yappSelfThreading]  // front right
   ];

cutoutsBack = [
   [22, -7, 11, 5, 0, yappRectangle]                     // SD card slot
   ];

cutoutsLeft = [
   [5, -2, 11.42, 8.26, 0, yappRectangle]                // Power
   ,[23.5, -2, 7, 7, 0, yappRectangle]                   // HDMI 0
   ,[38.5, -2, 7, 7, 0, yappRectangle]                   // HDMI 1
   ];

cutoutsFront = [
   [3, 0, 15, 14, 0, yappRectangle]                      // Ethernet
   ,[22, 0, 14, 15, 0, yappRectangle]                     // High Speed USB
   ,[40, 0, 14, 15, 0, yappRectangle]                     // High Speed USB
   ];



YAPPgenerate();


