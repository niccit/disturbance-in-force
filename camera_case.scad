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
      [24, 0.5, yappHole, yappBaseOnly, yappSelfThreading]
      ,[82, 0.5, yappHole, yappBaseOnly, yappSelfThreading]
      ,[24, 49.5, yappHole, yappBaseOnly, yappSelfThreading]
      ,[82, 49.5, yappHole, yappBaseOnly, yappSelfThreading]
      ,[20, 25.75, 28, default, 5, 3, yappLidOnly, yappSelfThreading]
      ,[83, 25.75, 28, default, 5, 3, yappLidOnly, yappSelfThreading]
   ];

cutoutsRight =
   [
      [69, -2, 12, 8, 0, yappRectangle]            // usb power
   ];

cutoutsLid =
   [
      [52, 26, 0, 0, 25, yappCircle, yappCenter]   // Cut out for camera/IR LED mount
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