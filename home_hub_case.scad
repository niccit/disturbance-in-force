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
   [19.5, -5, 15, 5, 0, yappRectangle]                     // SD card slot
   ];

cutoutsLeft = [
   [5.5, -2, 11.42, 8.26, 0, yappRectangle]                // Power
   ,[19.75, -2, 12, 7, 0, yappRectangle]                   // HDMI 0
   ,[33.5, -2, 12, 7, 0, yappRectangle]                   // HDMI 1
   ];

cutoutsFront = [
   [3, 0, 15, 14, 0, yappRectangle]                      // Ethernet
   ,[22, 0, 14, 15, 0, yappRectangle]                     // High Speed USB
   ,[40, 0, 14, 15, 0, yappRectangle]                     // High Speed USB
   ];

cutoutsBase = [
    [85 / 2, 56 / 2, 50, 30, 20, yappCircle, maskOffsetBars, yappCenter]
    ];

snapJoins = [
    [shellLength / 2, 5, yappLeft, yappRight, yappSymmetric, yappRectangle]
   ,[shellWidth / 2, 5, yappFront, yappBack, yappSymmetric, yappRectangle]
    ];

labelsPlane = [
   [47, 30, 180, 2, yappLid, "Henny Penny:style=bold", 8, "No Touch The Pi", 0, yappTextLeftToRight, yappTextHAlignCenter, yappTextVAlignCenter]
   ];


YAPPgenerate();


