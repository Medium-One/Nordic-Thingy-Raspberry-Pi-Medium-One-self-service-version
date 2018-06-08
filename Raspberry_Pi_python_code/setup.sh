#!/usr/bin/env bash
sudo mkdir /m1
sudo mv /home/pi/nordic.sh /etc/init.d/
sudo mv /home/pi/login.txt /m1/
sudo mv /home/pi/m1_nordic_thingy.py /m1/
sudo chmod 755 /etc/init.d/nordic.sh
sudo chown root  /etc/init.d/nordic.sh
sudo chgrp root  /etc/init.d/nordic.sh
sudo update-rc.d nordic.sh defaults
sudo apt-get update
sudo apt-get install python-requests
sudo apt-get install python-pip libglib2.0-dev
sudo pip install bluepy