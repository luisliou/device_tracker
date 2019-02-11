#!/bin/sh
COOKIE=$1
USER=$2
PASS=$3
IP=$4

JQ=./jq-linux64

get_post_data()
{
  COOKIE_VAL=$(cat $1 | grep COOKIE.* -o | awk '{print $2;}')
  PSWD_MD5=$(echo -n $3 | md5sum | tr [a-z] [A-Z] | awk '{print $1;}')
  ENCODED=$(echo -n $PSWD_MD5':'$COOKIE_VAL | md5sum | tr [a-z] [A-Z] | awk '{print $1;}')
  POST_DATA=$(echo -n 'nonce='$COOKIE_VAL'&encoded='$USER'%3A'$ENCODED)
  echo $POST_DATA
}

if [ $# != 4 ]; then
  echo "USAGE: COOKIE_FILE USER_NAME PASSWORD GATEWAY_IP"
  exit 1
fi

CMD=$(curl -c $COOKIE -H 'Referer:http://$IP/' -b $COOKIE http://$IP/data/version.json?option=logout -s | $JQ '.timeout')
if [ $CMD != 'true' ]; then
  echo "Failed to reset cookie!"
  exit 1
fi
get_post_data $COOKIE $USER $PASS

CMD=$(echo "curl -b $COOKIE -c $COOKIE -X POST --data $POST_DATA http://$IP/data/version.json -s")
echo --------------------Logging---------------------------------------------------------------------
echo "|"     $CMD
echo ------------------------------------------------------------------------------------------------
STATUS=$($CMD | $JQ '.status')
echo $STATUS

if [ $STATUS == 0 ]; then
  echo Logged in successfully!
  echo AllMACs:
  CMD=$(curl -H 'Referer:http://'$IP'/' -c $COOKIE -b $COOKIE http://$IP/data/station.json?radioID=1 -s)
  RET=$(echo $CMD | $JQ '.data')
  if [ "$RET" == "null" ]; then
    echo "ERROR: Failed to get MACs. No data!"
    exit 1
  fi
  CMD=$(curl -H 'Referer:http://'$IP'/' -c $COOKIE -b $COOKIE http://$IP/data/station.json?radioID=0 -s)
  RET1=$(echo $CMD | $JQ '.data')
  echo $RET | $JQ '.[].mac' | sed -e 's/\"//g' -e 's/\-/:/g'
  echo $RET1 | $JQ '.[].mac' | sed -e 's/\"//g' -e 's/\-/:/g'
#  CMD=$(curl -b $COOKIE -H 'Referer:http://$IP/' -b $COOKIE http://$IP/data/station.json?radioID=1 -s | $JQ '.data[].mac' | sed -e 's/\"//g' -e 's/\-/:/g')
else
  echo Failed!
  echo Status:$STATUS
#  CMD=$(curl -c $COOKIE -H 'Referer:http://$IP/' -b $COOKIE http://$IP/data/confirmLogin.json -s)
fi
