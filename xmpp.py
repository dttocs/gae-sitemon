#  version 2.20 (24-09-2009): new support for XMPP
#  version 3.08 (26-10-2011): CronUrlDB3 replaces CronUrlDB

from cronDB import *
from google.appengine.api import xmpp
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext.webapp import xmpp_handlers


STR_ANSWER = "Cannot understand: %s"
STR_HELP = ("Allowed commands: /?\n /tellme\n /view\n /dashboard\n"
            "To learn more, go to %s/")
STR_NODATA = "No data available"   
STR_STATUS = "Status(%s): %s"
STR_STATISTICS = "Statistics(%s), total delay: %s, # errors: %s, # retrys: %s"
STR_NOTHING = "Nothing to check"
STR_WAIT = "Please wait, responses coming soon!"
STR_USER = "You are %s"


class XmppHandler(xmpp_handlers.CommandHandler):
  """Handler class for all XMPP activity."""

  def unhandled_command(self, message=None):
    # Show help text
    message.reply(STR_HELP % (self.request.host_url,))

  def text_message(self, message=None):
    im_from = db.IM("xmpp", message.sender)
    if im_from:
      message.reply(STR_ANSWER % (message.arg,))
    else:
      self.unhandled_command(message)

# the view command should be updated to provide more useful information!
  def view_command(self, message=None):
    im_from = db.IM("xmpp", message.sender)
    query = CronUrlDB3.all()
    if query.get() == None:
      message.reply(STR_NODATA)
    else:
      cronUrlDB = query.get()
      message.reply(STR_WAIT)
      for cronUrlDB in query:
        xmpp.send_message(im_from.address, STR_STATISTICS % (cronUrlDB.url, cronUrlDB.acc_delay, cronUrlDB.n_errors, cronUrlDB.n_retrys))

  def dashboard_command(self, message=None):
    im_from = db.IM("xmpp", message.sender)
    query = CronUrlDB3.all()
    if query.get() == None:
      message.reply(STR_NODATA)
    else:
      cronUrlDB = query.get()
      message.reply(STR_WAIT)
      for cronUrlDB in query:
        xmpp.send_message(im_from.address, STR_STATUS % (cronUrlDB.url, cronUrlDB.status))

  def tellme_command(self, message=None):
    im_from = db.IM("xmpp", message.sender)
    message.reply(STR_USER % im_from.address)

