import feedparser

from simpletal import simpleTAL, simpleTALES, simpleTALUtils

mytemplate = """
<feed xmlns="http://www.w3.org/2005/Atom">
  <title tal:condition="feed/title" tal:content="feed/title"/>
  <link tal:condition="feed/link" tal:content="feed/link"/>
  <updated tal:condition="feed/updated" tal:content="feed/updated"/>
  <id tal:condition="feed/id" tal:content="feed/id"/>
  <!-- TODO other feed variables -->
  <entry xmlns='http://www.w3.org/2005/Atom'
       xmlns:thr='http://purl.org/syndication/thread/1.0'
       tal:repeat="entry entries">
    <title tal:condition="entry/title" tal:content="entry/title"/>
    <summary tal:condition="entry/summary" tal:content="entry/summary"/>
    <content tal:condition="entry/content" tal:content="python: entry.content[0]['value']"/> <!-- TODO: metadata and the other items in content -->
    <id tal:condition="entry/id" tal:content="entry/id"/>
    <published tal:condition="entry/published" tal:content="entry/published"/>
    <updated tal:condition="entry/updated" tal:content="entry/updated"/>
    <!-- TODO other entry fields -->
  </entry>
</feed>
"""
context = simpleTALES.Context(allowPythonPath=True)
template = simpleTAL.compileXMLTemplate (mytemplate)

class FeedParserPlus(feedparser.FeedParserDict):

    def serialize(self):
        context.addGlobal ("feed", self.feed)
        context.addGlobal ("entries", self.entries)
        result = simpleTALUtils.FastStringOutput()
        template.expand (context, result)
        return result.getvalue()

    @classmethod
    def parse(klass, text):
        result = feedparser.parse(text)
        return FeedParserPlus(result)
    


