#!/usr/bin/env python
#-*- coding: utf-8 -*-

"""
    Script to fetch the daily news from
    the NHK News Easy website, clean it,
    upload it to S3 and then submit it to
    Instapaper.
"""

import io, os, sys
import time
import requests
import boto

from pyquery import PyQuery as pq


BUCKET_NAME = os.environ.get("BUCKET_NAME", "sample-bucket")
BUCKET_PREFIX = os.environ.get("BUCKET_PREFIX", "sample-prefix")
INSTAPAPER_USERNAME = os.environ.get("INSTAPAPER_USERNAME", "user")
INSTAPAPER_PASSWORD = os.environ.get("INSTAPAPER_PASSWORD", "password")

""" Stream from stdin
    'rt' mode = unicode text, 'rb' = binary stream
    'rt' mode is line buffered, 'rb' use a smart buffer
"""
def process_stdin(handler, mode='rt'):
    sys.stdin = io.open(sys.stdin.fileno(), mode)
    for chunk in sys.stdin:
        handler(chunk)

""" Process stdin stream line by line
"""
def read_handler(data):
    url = data.strip('\n') # Remove the EOL
    r = requests.get(url)
    
    l = []
    today = time.strftime('%Y-%m-%d')
    
    if len(r.json()) > 0:
        l = r.json()[0].get(today, [])

    if not l:
        print "No news for today."
        exit(0)

    for i, item in enumerate(l):
        if item.get("news_id"):
            print i, item.get("title", "No Title")
            print "   => ", generate_content_url(url, item["news_id"])
            content = fetch_item(generate_content_url(url, item["news_id"]))
            result = put_item(today, item["news_id"], content)
            print "   Saved at ", result
            push_to_instapaper(result, item.get("title", None))

"""
    Find the URL of the content given its
    base URL and content identifier
"""
def generate_content_url(base_url, content_id):
    content_url = base_url.rsplit('/', 1)[0]
    content_path = "%s/%s.html" % (content_id, content_id)
    content_url = '/'.join([content_url, content_path])
    return content_url

"""
    Download the article
"""
def fetch_item(url):
    r = requests.get(url)
    r.encoding = "utf-8"
    content = prettify(r.text)
    return content

"""
    Remove furigana + random elements
"""
def prettify(html):
    html = pq(html)
    html("#main rt").empty() # Remove furigana
    html("ruby").each(lambda i, e: pq(e).replaceWith(pq(e).text())) # Unwrap ruby
    html("#main span").each(lambda i, e: pq(e).replaceWith(pq(e).text())) # Unwrap spans
    html("#main a").each(lambda i, e: pq(e).replaceWith(pq(e).text())) # Unwrap links
    html("#soundkana").empty() # Remove sound
    article = html("#main")
    html("body").empty().append(article) # Put the content in the body
    return html.html()

"""
    Upload the content on S3
"""
def put_item(date, uid, content):
    from boto.s3.key import Key
    try:
        c = boto.connect_s3()
        b = c.get_bucket(BUCKET_NAME)
        k = Key(b)
        k.key = "%s/%s/%s.html" % (BUCKET_PREFIX, date, uid)
        k.content_type = "text/html"
        k.set_contents_from_string(content)
        #print "Stored at ", k.key
        return k.generate_url(3600*732, force_http=True)
    except Exception as e:
        print "S3 Upload Failed: ", e

"""
    Push URL to Instapaper
"""
def push_to_instapaper(url, title=None):
    r = requests.get("https://www.instapaper.com/api/add",
                    auth=(INSTAPAPER_USERNAME, INSTAPAPER_PASSWORD),
                    params={'url': url, 'title': title})
    if r.status_code != 201:
        print "HTTP %i: Failed to push to Instapaper" % r.status_code

def main():
    process_stdin(read_handler)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        exit('')