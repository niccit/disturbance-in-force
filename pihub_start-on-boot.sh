#! /usr/bin/bash

USER="dietpi"

DIR=/home/$USER/home_hub

cd $DIR
echo $PWD
source .venv/bin/activate
python pi_code.py
