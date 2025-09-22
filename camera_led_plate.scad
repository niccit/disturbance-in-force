// SPDX-License-Identifier: MIT
$fa = 1;
$fs = 0.4;

use <scad_libs/threads-scad/threads.scad>

plate_diam = 50;
plate_h = 8;
led_diam = 6.15;
cable_l = 16.5;
cable_w = 3;
camera_mount = 3;
camera_depth = 6.13;
camera_l_w = 12;

module plate() {
   difference() {
      cylinder(d=plate_diam-2, h=plate_h); // center
      // LED lights left side
      translate([0, 18, 0])
         color("red")cylinder(d=led_diam, h=plate_h);
      translate([-16, 6, 0])
         color("red")cylinder(d=led_diam, h=plate_h);
      translate([-14, -10, 0])
         color("red")cylinder(d=led_diam, h=plate_h);
      // LED lights right side
      translate([16, 6, 0])
         color("orange")cylinder(d=led_diam, h=plate_h);
      translate([16, -9, 0])
         color("orange")cylinder(d=led_diam, h=plate_h);
      translate([0, -18, 0])
         color("orange")cylinder(d=led_diam, h=plate_h);
      // camera cut out
      translate([0, 0, 0])
         color("lightblue")cube([camera_l_w, camera_l_w, camera_depth+15], center=true);
      // camera mounting holes
      translate([-10.5, 11.5, -1.5])
         color("purple")camera_mount_hole();                // top left
     translate([10.5, 11.5, -1.5])
         color("purple")camera_mount_hole();                // top right
   }
}

// mounting rim
module rim(){
   union()
      {
         difference(){
            color("pink")cylinder(d=plate_diam+8, h=2);
            translate([0, 0, 0])
               cylinder(d=plate_diam-2, h=2);
         }
         translate([0, 32-0.01, 0])
            mounting_hook();
         translate([0, -32-0.01, 0])
            mounting_hook();
      }
}

// mounting hooks
module mounting_hook()
{
   difference()
   {
      cylinder(d=8, h=2);
      translate([0, 0, -0.5])
         color("navy")cylinder(d=5.8, h=3);
   }
}

module camera_mount_hole() {
   ScrewThread(2.20, plate_h, pitch=0, tooth_angle=30, tolerance=0.4, tooth_height=0);
}

union()
   {
      plate();
      translate([0-0.01, 0-0.01, 0])
      rim();
   }


