#!/usr/bin/env python
#
#  http://cron-tab.appspot.com/
#  version 1 (07-07-2009): first release
#  version 2.20 (24-09-2009): added method check_url
#  version 3.x (20-09-2011): CronUrlDB3 replaces CronUrlDB including new fields, StatDB3,DailyDB3
#
# author: javalc6
#
import time
import datetime
import re

from google.appengine.api import urlfetch
from google.appengine.ext import db

# UrlDB
class UrlDB(db.Model):
  url = db.StringProperty()
  delay = db.FloatProperty() # last delay
  date = db.DateTimeProperty() # last check
  n_errors = db.IntegerProperty() # number of errors
# check_url
  def check_url(self):
    timeref = datetime.datetime.now()
    try:
      result = urlfetch.fetch(self.url)
    except urlfetch.InvalidURLError:
      return 'Error: Not an URL'
    except urlfetch.DownloadError:
      return 'Error: Download error'
    if result.status_code == 200:
      delay = (datetime.datetime.now() - timeref)
      if len(result.content) > 0:
        if re.search('</html>', result.content, re.I):
          return "OK: %s ms" % (delay.microseconds/1000.0 + delay.seconds * 1000.0) 
        else:
          return "Error: bad html"
      else:
        return 'Error: Empty response'
    else:
      return 'Error: %s' % result.status_code

# StatDB3
class StatDB3(db.Model):
  mean_delay = db.FloatProperty() # accumulated delay
  min_delay = db.FloatProperty() # minimum delay
  max_delay = db.FloatProperty() # maximum delay
  date = db.DateTimeProperty()
  n_errors = db.IntegerProperty() # number of errors
  n_retrys = db.IntegerProperty() # number of retrys

# DailyDB3
class DailyDB3(db.Model):
  mean_delay = db.FloatProperty() # accumulated delay
  min_delay = db.FloatProperty() # minimum delay
  max_delay = db.FloatProperty() # maximum delay
  date = db.DateProperty()
  n_errors = db.IntegerProperty() # number of errors
  n_retrys = db.IntegerProperty() # number of retrys

# CronUrlDB3
class CronUrlDB3(db.Model):
  url = db.StringProperty()
  alias = db.StringProperty()
  checkvalue = db.StringProperty()
  counter = db.IntegerProperty()
  acc_delay = db.FloatProperty() # accumulated delay
  min_delay = db.FloatProperty() # minimum delay
  max_delay = db.FloatProperty() # maximum delay
  date = db.DateTimeProperty(auto_now_add=True)
  n_errors = db.IntegerProperty() # number of errors
  n_retrys = db.IntegerProperty() # number of retrys
  status = db.IntegerProperty(0) # 0: undef, 1: ok, -1: error, -2: bad url, -3: bad content (checkvalue not found)

# ConfigDB
class ConfigDB(db.Model):
  admin_email = db.StringProperty()
  alert_email = db.StringProperty()
  send_mail = db.BooleanProperty()