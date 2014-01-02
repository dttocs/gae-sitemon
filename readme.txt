============================================================
!     cron-tab, version 3.0 (author: javal6, 09-2011)      !
============================================================
The following features are provided by the tool cron-tab: 

- Perform periodic test of cron urls. Result of the tests can be viewed in the View statistics page. 
- Sparkline presentation of statistics from periodic tests
- Automatic sendmail of alert in case of failure from periodic test
- Check the status of several links at any time. The status is displayed in the Dashboard page. 
- Added support for google talk. Now you can use google talk or another XMPP client to connect to cron-tab@appspot.com

Also an administrator interface is provided to configure properly this tool. 
============================================================
Release notes
version 2.3: added the possibility to configure multiple cron urls.
version 3.0: added the possibility to configure a check value used to test the web page retrieved, the dashboard shows the status using weather symbols (e.g. sunny)
============================================================
Installation of cron-tab

prerequisites:
- sign-up for an account on google application engine (GAE): http://appengine.google.com/
- download and install the Google App Engine SDK
- internet connection from your PC

how to install cron-tab application:
- unpack all files included in cron-tab.zip into a specific local directory, e.g 'myapp'
- upload all files from 'myapp' to google application engine server: appcfg.py update myapp
============================================================
cron-tab application URL:

http://cron-tab.appspot.com/
http://cron-tab.appspot.com/admin
http://cron-tab.appspot.com/view
http://cron-tab.appspot.com/checkurl

xmpp://cron-tab@appspot.com

called ONLY from cron table, not from browser:
http://cron-tab.appspot.com/cron
http://cron-tab.appspot.com/clear
============================================================
Commands available using XMPP:

/? help
/tellme tell user identity
/view view latest result of periodic test
/dashboard check the status of several links

============================================================
!      Licensed under GPL 2.0 conditions,                  !
!      please read enclosed file 'licence.txt'             !
============================================================
