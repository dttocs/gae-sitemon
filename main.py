#!/usr/bin/env python
#
#  http://cron-tab.appspot.com/
#  version 2.03 (18-07-2009): templates added!
#  version 2.14 (08-09-2009): added graphics and sendmail
#  version 2.21 (24-09-2009): added support for XMPP
#  version 2.22 (25-05-2010): Issue 2 corrected
#  version 2.23 (13-03-2011): adding support for taskqueue (experimental: 1 task)
#  version 2.24 (05-04-2011): porting to django 1.2
#  version 2.31 (10-04-2011): multiple urls in crontab using namespaces
#  version 2.33 (19-09-2011): retry to avoid false error indication
#  version 3.00 (20-09-2011): CronUrlDB3 replaces CronUrlDB including new fields
#  version 4.00 (14-01-2013): porting to python 2.7
#
# author: javalc6
#
# IMPORTANT NOTICE, please read:
# 
# This software is licensed under the terms of the GNU GENERAL PUBLIC LICENSE,
# please read the enclosed file license.txt or http://www.gnu.org/licenses/licenses.html
# 
# Note that this software is freeware and it is not designed, licensed or intended
# for use in mission critical, life support and military purposes.
# 
# The use of this software is at the risk of the user.

import cgi
import time
import datetime
import wsgiref.handlers
import os
import logging
import re

import webapp2 as webapp
from google.appengine.ext.webapp.util import run_wsgi_app

from cronDB import *
from xmpp import XmppHandler
from google.appengine.api import mail
from google.appengine.api import urlfetch
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from google.appengine.api import taskqueue
from google.appengine.api import namespace_manager
from urlparse import urlparse

# style used in html templates
style = u'''
<style type="text/css">
<!--
body       { background-color: #FFFFEE; color: #000000; font-family: Arial }
td.header  { background-color: #F0F000;}
.small       { font-size: 8pt; font-style: normal; font-family: Arial, Helvetica; }
table { background-color:#FFFFFF; border-width:3px; border-style:solid; border-color:#006699; }
td    { background-color: #DEE3E7; }
th    { background-color: #C8D1D7; }
table.menu { background-color:#FFFFFF; border-width:0px; }
-->
</style>
'''

#sendmail as suggested by user lovaxi
def sendmail(status, url, log_file = ''):
  query = ConfigDB.all()
  if query.get() != None:
    if query.get().send_mail:
      if status == -1:
        mail_body = 'web site (%s) down!' % url
      elif status == 0:
        mail_body = 'web site (%s) status undefined' % url
      elif status == 200:
        mail_body = 'web site (%s) up and running!' % url
      elif status == -2:
        mail_body = 'bad url (%s) provided for the cron-tab feature' % url
      elif status == -3:
        mail_body = 'unexpected content from %s, fails checkvalue' % url
        mail.send_mail(sender = query.get().admin_email,
              to = query.get().alert_email,
              subject = 'Server status change notification',
              body = mail_body,
              attachments=[('log.txt', log_file)])
        return
      else:
        mail_body = 'web site (%s) down\nstatus: %s' % (url, status)
      mail.send_mail(sender = query.get().admin_email,
              to = query.get().alert_email,
              subject = 'Server status change notification',
              body = mail_body)

#printHtml
def printHtml(self, template_name, template_values={}):
  path = os.path.join(os.path.dirname(__file__), os.path.join('templates', template_name))
  self.response.out.write(template.render(path, template_values))

# MainHandler
class MainHandler(webapp.RequestHandler):
  def get(self):
    template_values = {
      'style': style,
      'header': header(self),
      'footer': footer(self),
    }
    printHtml(self, 'main.html', template_values)

# CronHandler
class CronHandler(webapp.RequestHandler):
  def get(self):
    query = CronUrlDB3.all()
    for cronUrlDB in query:
      taskqueue.add(url='/exectask', params={'key': cronUrlDB.key(), 'retry': 0})


# TaskHandler
class TaskHandler(webapp.RequestHandler):
  def post(self):
    cronUrlDB = db.get(self.request.get('key'))
    if cronUrlDB == None:
      return
    timeref = datetime.datetime.now()
    content = '' #default value
    try:
      result = urlfetch.fetch(cronUrlDB.url, deadline=10)
      newstatus = result.status_code #preliminary result, now check if content is correct (checkvalue)
      if result.status_code == 200:
        if len(cronUrlDB.checkvalue) != 0:
          if not re.search(cronUrlDB.checkvalue, result.content, re.I):            
            newstatus = -3 # bad content
            content = result.content
    except urlfetch.InvalidURLError:
      self.response.out.write('Exception: Not an URL')
      newstatus = -2 # bad url
      return
    except urlfetch.DownloadError:
      self.response.out.write('Exception: Download error')
      newstatus = -1 # download error
#    logging.info('retry: %s', self.request.get('retry'))
    if int(self.request.get('retry')) > 0:
      process_remote_test(self, cronUrlDB, timeref, newstatus, content)
      return
    if newstatus == 200:
      process_remote_test(self, cronUrlDB, timeref, newstatus, content)
    else:
      cronUrlDB.n_retrys = cronUrlDB.n_retrys + 1
      cronUrlDB.put()
      taskqueue.add(url='/exectask', countdown = 10, params={'key': cronUrlDB.key(), 'retry': 1})

#process_remote_test
def process_remote_test(self, cronUrlDB, timeref, newstatus, content):
    sendmail_flag = (newstatus != cronUrlDB.status)
    cronUrlDB.status = newstatus
    delay = (datetime.datetime.now() - timeref)
    delay_ms = delay.microseconds / 1000.0 + delay.seconds * 1000.0
    if cronUrlDB.counter == 0:
      cronUrlDB.date = timeref
      cronUrlDB.counter = 1
      if cronUrlDB.status == 200:
        cronUrlDB.n_errors = 0
      else:
        cronUrlDB.n_errors = 1
      cronUrlDB.acc_delay = delay_ms
      cronUrlDB.min_delay = delay_ms
      cronUrlDB.max_delay = delay_ms
      cronUrlDB.put()
    elif cronUrlDB.counter >= 5:  # update statsDB every 10 minutes
      no_date = cronUrlDB.date
      no_mean_delay = cronUrlDB.acc_delay / cronUrlDB.counter
      no_min_delay = cronUrlDB.min_delay
      no_max_delay = cronUrlDB.max_delay
      no_n_errors = cronUrlDB.n_errors
      no_n_retrys = cronUrlDB.n_retrys
       
      namespace_manager.set_namespace(self.request.get('key'))
      statDB = StatDB3()
      statDB.date = no_date
      statDB.mean_delay = no_mean_delay
      statDB.min_delay = no_min_delay
      statDB.max_delay = no_max_delay
      statDB.n_errors = no_n_errors
      statDB.n_retrys = no_n_retrys
      statDB.put()
      namespace_manager.set_namespace('') # remove namespace
        
      cronUrlDB.date = timeref
      cronUrlDB.counter = 1
      if cronUrlDB.status == 200:
        cronUrlDB.n_errors = 0
      else:
        cronUrlDB.n_errors = 1
      cronUrlDB.acc_delay = delay_ms
      cronUrlDB.min_delay = delay_ms
      cronUrlDB.max_delay = delay_ms
      cronUrlDB.n_retrys = 0
      cronUrlDB.put()
    else:      
      cronUrlDB.counter = cronUrlDB.counter + 1
      if cronUrlDB.status != 200:
        cronUrlDB.n_errors = cronUrlDB.n_errors + 1
      cronUrlDB.acc_delay = delay_ms + cronUrlDB.acc_delay
      if cronUrlDB.min_delay > delay_ms:
        cronUrlDB.min_delay = delay_ms
      if cronUrlDB.max_delay < delay_ms:
        cronUrlDB.max_delay = delay_ms
      cronUrlDB.put()
    if sendmail_flag:
      sendmail(cronUrlDB.status, cronUrlDB.url, content)

# ClearHandler
class ClearHandler(webapp.RequestHandler):
  def get(self):
    cquery = CronUrlDB3.all()
    for cronUrlDB in cquery:
      namespace_manager.set_namespace(str(cronUrlDB.key()))
      query = StatDB3.all()
      if query.count() > 0:
        statDB = query.get()
        acc_delay = statDB.mean_delay
        min_delay = statDB.min_delay
        max_delay = statDB.max_delay
        n_errors = statDB.n_errors
        n_retrys = statDB.n_retrys
        n_items = 1
        for statDB in query:
          n_errors += statDB.n_errors
          n_retrys += statDB.n_retrys
          n_items +=1
          acc_delay += statDB.mean_delay
          if min_delay > statDB.min_delay:
            min_delay = statDB.min_delay
          if max_delay < statDB.max_delay:
            max_delay = statDB.max_delay
          statDB.delete()
        dailyDB = DailyDB3()
        dailyDB.mean_delay = acc_delay / n_items
        dailyDB.min_delay = min_delay
        dailyDB.max_delay = max_delay
        dailyDB.date = datetime.datetime.now().date()
        dailyDB.n_errors = n_errors
        dailyDB.n_retrys = n_retrys
        dailyDB.put()

#    query = db.GqlQuery("SELECT * FROM StatDB3")
#    query = StatDB3.all()
#    db.delete(query.fetch(500))

# ViewHandler
class ViewHandler(webapp.RequestHandler):
  def get(self):
    ns = self.request.get('ns')

    cronUrlDBs = CronUrlDB3.all()
    names = []
    for cronUrlDB in cronUrlDBs:
      names.append(cronUrlDB)
      if ns == '':
        ns = str(cronUrlDB.key())

    namespace_manager.set_namespace(ns)
      
    if self.request.get('action') == 'week':
      dailyDBs = db.GqlQuery("SELECT * FROM DailyDB3 ORDER BY date DESC LIMIT 7")
      latency = []
      errors = []
      for dailyDB in dailyDBs:
        latency.append(int(dailyDB.mean_delay))
        errors.append(int(dailyDB.n_errors))
      latency.reverse()
      errors.reverse()
      template_values = {
        'style': style,
        'header': header(self),
        'footer': footer(self),
        'ns': ns,
        'names': names,
        'dailyDBs': dailyDBs,
        'latency': latency,
        'errors': errors,
      }
    elif self.request.get('action') == 'month':
      dailyDBs = db.GqlQuery("SELECT * FROM DailyDB3 ORDER BY date DESC LIMIT 30")
      latency = []
      errors = []
      for dailyDB in dailyDBs:
        latency.append(int(dailyDB.mean_delay))
        errors.append(int(dailyDB.n_errors))
      latency.reverse()
      errors.reverse()
      template_values = {
        'style': style,
        'header': header(self),
        'footer': footer(self),
        'ns': ns,
        'names': names,
        'dailyDBs': dailyDBs,
        'latency': latency,
        'errors': errors,
      }
    else:   
      statDBs = db.GqlQuery("SELECT * FROM StatDB3 ORDER BY date DESC LIMIT 12")
      latency = []
      errors = []
      for statDB in statDBs:
        latency.append(int(statDB.mean_delay))
        errors.append(int(statDB.n_errors))
      latency.reverse()
      errors.reverse()
      template_values = {
        'style': style,
        'header': header(self),
        'footer': footer(self),
        'ns': ns,
        'names': names,
        'statDBs': statDBs,
        'latency': latency,
        'errors': errors,
      }
    printHtml(self, 'view.html', template_values)

# dashboard
def dashboard(self):

    status = []
    cquery = CronUrlDB3.all()
    for cronUrlDB in cquery:
      namespace_manager.set_namespace(str(cronUrlDB.key()))
      query = StatDB3.all()
      if query.count() > 0:
        n_errors = 0
        n_retrys = 0
        for statDB in query:
          n_errors += statDB.n_errors
          n_retrys += statDB.n_retrys
        if n_errors > 4:
          image = 'level3.png'
        elif n_errors > 1:
          image = 'level2.png'
        elif n_retrys > 0:
          image = 'level1.png'
        else:
          image = 'level0.png'
      else:
        image = 'level.png'
      status.append((cronUrlDB, image))

    namespace_manager.set_namespace('') # remove namespace

    template_values = {
      'style': style,
      'header': header(self),
      'footer': footer(self),
      'urlDBs': UrlDB.all(),
      'status': status,
    }
    printHtml(self, 'checkurl.html', template_values)

#CheckurlHandler
class CheckurlHandler(webapp.RequestHandler):
  def get(self):
    value = self.request.get("url")
    if value:
      urlDB = db.get(value)
      self.response.out.write(urlDB.check_url())
    else:
      dashboard(self)

#AdminHandler
class AdminHandler(webapp.RequestHandler):
  def post(self):
    action = self.request.get('action')
    result = None
    if action == 'addurl2':
      if self.request.get('url').startswith('http://'):
        urlDB = UrlDB()
        urlDB.url = self.request.get('url').strip()
        urlDB.put()
        result = 'url added'
      else:
        result = 'url must start with http://'
    if action == 'addcronurl2':
      if self.request.get('url').startswith('http://'):
        cronUrlDB = CronUrlDB3()
        cronUrlDB.url = self.request.get('url').strip()
        cronUrlDB.alias = self.request.get('alias').strip()
        if len(cronUrlDB.alias) == 0: 
          cronUrlDB.alias = cronUrlDB.url
        cronUrlDB.checkvalue = self.request.get('checkvalue').strip()
        cronUrlDB.counter = 0 # just defined!
        cronUrlDB.n_errors = 0
        cronUrlDB.n_retrys = 0
        cronUrlDB.status = 0 # undef
        cronUrlDB.put()
        result = 'cron url added'
      else:
        result = 'url must start with http://'
    if action == 'edit.email':
      if self.request.get('admin.email').find('@') != -1:
        if self.request.get('alert.email').find('@') != -1:
          query = ConfigDB.all()
          if query.get() == None: # singleton
            configDB = ConfigDB()
          else:
            configDB = query.get()
          configDB.admin_email = self.request.get('admin.email')
          configDB.alert_email = self.request.get('alert.email')
          configDB.send_mail = (self.request.get('send.email') == 'True')
          configDB.put()
          result = 'email values saved in configuration'
        else:
          result = 'alert email must contain @'
      else:
        result = 'admin email must contain @'
    render_admin(self, action, result, None)

  def get(self):
    action = self.request.get('action')
    result = None
    if action == 'delete':
      mykey = self.request.get('key')
    else:
      mykey = None
    if action == 'delete2':
      mykey = self.request.get('key')
      entity = db.get(mykey)
      if entity:
        entity.delete()
        result = 'entity deleted'
      else:
        result = 'nothing to delete'
    render_admin(self, action, result, mykey)

# render_admin
def render_admin(self, action, result, mykey):
    query = ConfigDB.all()
    if query.get() != None:
      admin_email = query.get().admin_email
      alert_email = query.get().alert_email
      send_mail = query.get().send_mail
    else:
      admin_email = ''
      alert_email = ''
      send_mail = ''
    template_values = {
      'style': style,
      'header': header(self),
      'footer': footer(self),
      'action': action,
      'result': result,
      'mykey': mykey,
      'cronUrlDBs': CronUrlDB3.all(),
      'urlDBs': UrlDB.all(),
      'admin_email': admin_email,
      'alert_email': alert_email,
      'send_mail': send_mail,
    }
    printHtml(self, 'admin.html', template_values)

# header
def header(self):
    return "".join(('''<table class="menu" width="100%" cellpadding="0" cellspacing="0"><tr><td align="left">
      <a href="view">View statistics</a> | <a href="checkurl">Dashboard</a> | <a href="admin">Admin</a></td>''',
      '<td align="right">%s [%s]</td>' % (users.get_current_user(), datetime.datetime.now().strftime("%d %b %y, %H:%M:%S")),
      '</tr></table>'
    ))

# footer
def footer(self):
    return '<div align="center" style="font-size: smaller">Powered by <a title="cron-tab@googlecode" href="http://code.google.com/p/cron-tab/">cron-tab</a></div>'


app = webapp.WSGIApplication([('/', MainHandler), 
                                        ('/view', ViewHandler), 
                                        ('/cron', CronHandler), 
                                        ('/clear', ClearHandler), 
                                        ('/exectask', TaskHandler), 
                                        ('/checkurl', CheckurlHandler), 
                                        ('/admin', AdminHandler), 
                                        ('/_ah/xmpp/message/chat/', XmppHandler),
                                       ], debug=True)

#
#  main()
#
def main():
    run_wsgi_app(app)

if __name__ == '__main__':
  main()