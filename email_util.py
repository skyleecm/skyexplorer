# email_util.py
#    @copyright: 2007 -  Lee Chee Meng skyleecm@gmail.com
#    @License: GPL

import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from email import Encoders
import os
if not hasattr(__builtins__, 'basestring'):
    try:
        __builtins__.basestring = (str, unicode)
    except Exception, e:
        __builtins__['basestring'] = (str, unicode)

#----------------------------------------------------------------------
# bugs?
# gethostbyname('localhost') gives ****
import socket
lhost = socket.gethostname()
addr = socket.gethostbyname(lhost)
useLH = ('.' not in addr and lhost == 'localhost')


def sendMail(fr, to, subject, text, files=None, server='localhost'):
    msg = MIMEMultipart()
    msg['From'] = fr
    msg['To'] = COMMASPACE.join(to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    msg.attach(MIMEText(text))

    if files:
        for file in files:
            msg.attach(createPart(file))

    if useLH:
        smtp = smtplib.SMTP(server, local_hostname='[127.0.0.1]')
    else:
        smtp = smtplib.SMTP(server)
    smtp.sendmail(fr, to, msg.as_string())
    smtp.close()

def createPart(p):
    part = MIMEBase('application', 'octet-stream')
    f = file(p, 'rb')
    part.set_payload(f.read())
    f.close()
    Encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(p))
    return part

