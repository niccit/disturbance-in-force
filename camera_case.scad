// SPDX-License-Identifier: MIT
$fa = 1;
$fs = 0.4;

include <scad_libs/YAPP_Box/YAPPgenerator_v3.scad>

// --- YAPP setup --- //

printBaseShell = true;
printLidShell = true;

wallThickness = 2.5;
basePlaneThickness = 2.5;
lidPlaneThickness = 2.5;

baseWallHeight = 18;
lidWallHeight = 16;

pcbLength = 85;
pcbWidth = 56;
pcbThickness = 1.6;

paddingFront = 4;
paddingBack = 3;
paddingRight = 1;
paddingLeft = 6;

ridgeHeight = 5;
ridgeSlack = 0.2;
roundRadius = 0.5;

standoffHeight = 5.0;
standoffPinDiameter = 2;
standoffHoleSlack = 0.5;
standoffDiameter = 4;

pcbStands =
   [
      [24, 0.5, yappHole, yappBaseOnly, yappSelfThreading]                       // back left
      ,[82, 0.5, yappHole, yappBaseOnly, yappSelfThreading]                      // front left
      ,[24, 49.5, yappHole, yappBaseOnly, yappSelfThreading]                     // back right
      ,[82, 49.5, yappHole, yappBaseOnly, yappSelfThreading]                     // front right
      ,[pcbWidth/2 + 2.5, pcbLength/2 - 31, 26.5, default, default, default, default, 0.75, yappHole, yappLidOnly, yappSelfThreading]    // back left
      ,[pcbWidth/2 + 30.5, pcbLength/2 - 31, 26.5, default, default, default, default, 0.75, yappHole, yappLidOnly, yappSelfThreading]   // front left
      ,[pcbWidth/2 + 2.5, 39.75, 26.5, default, default, default, default, 0.75, yappHole, yappLidOnly, yappSelfThreading]    // back right
      ,[pcbWidth/2 + 30.5, 39.75, 26.5, default, default, default, default, 0.75, yappHole, yappLidOnly, yappSelfThreading]
   ];

cutoutsRight =
   [
      [69, -2, 12, 8, 0, yappRectangle]            // usb power
   ];

cutoutsLid =
   [
      [pcbWidth/2 + 8, pcbLength/2 - 25, 0, 0, 8, yappCircle]                    // Camera Lens
      ,[pcbWidth/2 + 6.75, 8, 0, 0, 3, yappCircle]                            // Main board sensor
      ,[pcbWidth/2 - 25, pcbLength/2 - 26, 0, 0, 9, yappCircle]                  // Back LED
      ,[pcbWidth/2 - 9.5, 30.2, 0, 0, 3, yappCircle]                              // Back LED Sensor
      ,[pcbWidth/2 + 39, pcbLength/2 - 26, 0, 0, 9, yappCircle]                  // Front LED
      ,[pcbWidth/2 + 35, 15.5, 0, 0, 3, yappCircle]                            // Front LED Sensor
   ];

snapJoins =
   [
      [shellLength/4, 5, yappLeft, yappRight, yappSymmetric]
      ,[shellWidth/2, 5, yappFront, yappBack, yappSymmetric]
   ];

boxMounts =
   [
      [10, 5, shellWidth, 3, yappBack]
      ,[-10, 5, shellWidth, 3, yappFront]
   ];

YAPPgenerate();