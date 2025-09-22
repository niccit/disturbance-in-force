// SPDX-License-Identifier: MIT
$fa = 1;
$fs = 0.4;

include <scad_libs/YAPP_Box/YAPPgenerator_v3.scad>

// PIR sensor 14mm high
// Standoff height 5mm


printBaseShell = true;
printLidShell = true;

// RaspberryPi Pico
// 51m, 21mm, 1mm per https://www.adafruit.com/product/5526
pcbLength = 51;
pcbWidth = 32.34;
pcbThickness = 1;

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
      [3, 10.5, yappHole, yappBaseOnly, yappSelfThreading]
      ,[51, 10.5, yappHole, yappBaseOnly, yappSelfThreading]
      ,[3, 22.5, yappHole, yappBaseOnly, yappSelfThreading]
      ,[51, 22.5, yappHole, yappBaseOnly, yappSelfThreading]
      ,[11.75, shellWidth/2-3.5, 25, yappHole, yappLidOnly, yappSelfThreading, yappNoFillet]
      ,[41.75, shellWidth/2-3.5, 25, yappHole, yappLidOnly, yappSelfThreading, yappNoFillet]
   ];

cutoutsBack =
   [
      [pcbWidth/2-5, 0, 10, 6.4, 0, yappRectangle]
   ];

cutoutsLid =
   [
      [shellLength/2-15, shellWidth/2-15.5, 0, 0, 12, yappCircle]    // PIR cut out
//      ,[9, shellWidth/2-5, 0, 0, 1.5, yappCircle]                    // Back mounting hole
//      ,[39, shellWidth/2-5, 0, 0, 1.5, yappCircle]
   ];

boxMounts =
   [
      [10, 5, shellWidth, 3, yappBack]
      ,[-10, 5, shellWidth, 3, yappFront]
   ];

snapJoins =
   [
      [shellLength/4, 5, yappLeft, yappRight, yappSymmetric]
      ,[shellWidth/2, 5, yappFront, yappBack, yappSymmetric]
   ];


YAPPgenerate();


