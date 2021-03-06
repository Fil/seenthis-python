"""
Documentation of the SeenThis API: see the README

"""

import os
import sys
import string
import urllib2
import hashlib
import locale
import json
import base64
import traceback

from FeedParserPlus import FeedParserPlus

try:
    from simpletal import simpleTAL, simpleTALES, simpleTALUtils
except ImportError:
    print >>sys.stderr, "I need the module simpleTAL, see <http://www.owlfish.com/software/simpleTAL/>"

__VERSION__ = '0.0'

authfile = "%s/.seenthis/auth" % os.environ['HOME']
create_endpoint = 'https://seenthis.net/api/messages'
retrieve_endpoint_tmpl = 'https://seenthis.net/api/people/%s/messages'
get_endpoint_tmpl = 'https://seenthis.net/api/messages/%i'
url_endpoint_tmpl = 'https://seenthis.net/api/url/%s'
mytemplate = """
<entry xmlns='http://www.w3.org/2005/Atom'
       xmlns:thr='http://purl.org/syndication/thread/1.0'
       xmlns:docs='http://schemas.google.com/docs/2007'>
    <summary tal:content="message"/>
</entry>
"""
outsideencoding = "UTF-8"
myencoding = locale.getpreferredencoding()
if myencoding is None:
    myencoding='UTF-8'
    
class InternalError(Exception):
    pass

class NotFound(Exception):
    pass

class CredentialsNotFound(InternalError):
    pass

class InvalidResponse(Exception):
    pass

class Connection:

    def __init__(self, credentials=None):
        if credentials:
            self.username, self.password = credentials
        else:
            if not os.path.exists(authfile):
                raise CredentialsNotFound(authfile)
            auth = open(authfile)
            self.username = auth.readline()[:-1]
            self.password = auth.readline()[:-1]
        self.retrieve_endpoint = retrieve_endpoint_tmpl % self.username
        self.template = simpleTAL.compileXMLTemplate(mytemplate)
        
    def _add_headers(self, r, post=False):
        credentials = base64.b64encode('%s:%s' % (self.username, self.password))
        r.add_header('User-agent', 'SeenThis-package/%s Python/%s' % \
                     (__VERSION__, sys.version.split()[0]))
        r.add_header('Authorization', 'Basic %s' % credentials)
        if post:
            r.add_header('Content-Type', 'application/atom+xml;type=entry')

    def get_message(self, msgid):
        """ Returns a FeedParserPlus object (which inherits from
        traditional FeedparserDict) representing one SeenThis message. """
        endpoint = get_endpoint_tmpl % int(msgid)
        request = urllib2.Request(url=endpoint)
        self._add_headers(request)
        server = urllib2.urlopen(request)
        data = server.read()
        try:
            atom_entry = FeedParserPlus.parse(data)
        except:
            import tempfile
            (datafilefd, datafilename) = tempfile.mkstemp(suffix=".atom",
                                                          prefix="seenthis_", text=True)
            datafile = os.fdopen(datafilefd, 'w')
            datafile.write(data)
            datafile.close()
            raise InvalidResponse("ATOM parsing error of the answer. The data has been saved in %s" % datafilename)
        # If the message-ID does not exist, SeenThis does not return a
        # 404 and sends back an invalid XML file :-(
        # http://seenthis.net/messages/70646 So, we hack.
        if atom_entry.has_key("bozo_exception"):
            raise NotFound("Message %i does not apparently exist" % int(msgid))
        return atom_entry
    
    def get(self, n=None, continue_on_error=False):
        """
        n is the number of messages to retrieve. When None, we just retrieve what
        SeenThis gives us (today, the last 25 messages). Otherwise, we
        loop to retrieve n messages. Warning: because there may be
        less messages on SeenThis, there is no guarantee to have n
        entries in the result.

        To get all the messages, just set n to a very high number.

        The result is a FeedParserPlus object (which inherits from
        traditional FeedparserDict).
        """
        total = 0
        over = False
        result = None
        step = 0
        while not over:
            # TODO: we could use feedparser to retrieve the feed, not
            # only to parse it...
            if step == 0:
                endpoint = self.retrieve_endpoint
            else:
                endpoint = "%s/%i" % (self.retrieve_endpoint, total)
            request = urllib2.Request(url=endpoint)
            self._add_headers(request)
            server = urllib2.urlopen(request)
            data = server.read()
            # Bad workaround FeedParser's bug #91 http://code.google.com/p/feedparser/issues/detail?id=91
            for line in data:
                # Awfully slow, we should replace :-) it with something faster
                if string.find(data, "!DOCTYPE") != -1:
                    data = string.replace(data, "!DOCTYPE", "!\ DOCTYPE")
            try:
                atom_feed = FeedParserPlus.parse(data)
            except:
                import tempfile
                (datafilefd, datafilename) = tempfile.mkstemp(suffix=".atom",
                                                            prefix="seenthis_", text=True)
                datafile = os.fdopen(datafilefd, 'w')
                datafile.write(data)
                datafile.close()
                print >>sys.stderr, \
                      "Parsing error of the answer. The data has been saved in %s" % \
                      datafilename
                if continue_on_error:
                    (exc_type, exc_value, exc_traceback) = sys.exc_info()
                    print "Exception %s \"%s\" %s" % \
                          (exc_type, exc_value, 
                           traceback.format_list(traceback.extract_tb(exc_traceback)))
                    step += 1
                    continue
                else:
                    raise
            got = len(atom_feed['entries'])
            if got == 0:
                over = True
            else:
                total += got
                step += 1
                print >>sys.stderr, "Got %i entries..." % total
                if result is None:
                    result = atom_feed
                else:
                    for entry in atom_feed['entries']:
                        result['entries'].append(entry)
                if n is not None and total >= n:
                    over = True
        return result

    def post(self, message):
        # TODO: allows to use a message-ID as parameter and set
        # thr:in-reply-to (the post should then go under an existing
        # thread.
        context = simpleTALES.Context(allowPythonPath=False)
        context.addGlobal ("message", unicode(message, encoding=myencoding))
        result = simpleTALUtils.FastStringOutput()
        self.template.expand (context, result, outputEncoding=outsideencoding)
        request = urllib2.Request(url=create_endpoint,
                                  data=result.getvalue())
        self._add_headers(request, post=True)
        server = urllib2.urlopen(request)
        return server.read()

    def url_exists(self, url):
        """ Returns an dictionary. Field "found" is a boolean indicating if
        the URL was found. Field "messages" is an array of message numbers
        where the URL is found. You can then use the get_message()
        method to retrieve it. """
        digester = hashlib.md5()
        digester.update(url)
        endpoint = url_endpoint_tmpl % digester.hexdigest()
        request = urllib2.Request(url=endpoint)
        self._add_headers(request)
        server = urllib2.urlopen(request)
        result = server.read()
        try:
            values = json.loads(result)
        except ValueError:
            raise InvalidResponse("Invalid JSON data returned by SeenThis")
        return {"found": values["status"] == "success",
                 "messages": values["messages"]}
