#!/bin/sh
# /etc/init.d/nordic.sh
### BEGIN INIT INFO
# Provides: nordic
# Required-Start: $network $syslog $remote_fs
# Required-Stop: $network
# Default-Start: 2 3 5
# Default-Stop: 0 1 6
# Short-Description: M1 python
# Description: Start or stop the M1 python script
### END INIT INFO


# sudo chmod 755 /etc/init.d/nordic.sh
# sudo chown root  /etc/init.d/nordic.sh
# sudo chgrp root  /etc/init.d/nordic.sh
# sudo update-rc.d nordic.sh defaults
# sudo apt-get update
# sudo apt-get install python-requests
# sudo apt-get install python-pip libglib2.0-dev
# sudo pip install bluepy

case "$1" in
  start)
    echo "Starting Service "
    python /m1/m1_nordic_thingy.py
    ;;
  stop)
    echo "Stopping Service "
    ;;
  *)
    echo "Usage: /etc/init.d/test {start|stop}"
    exit 1
    ;;
esac

exit 0
