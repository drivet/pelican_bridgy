from pelican import signals

from ronkyuu import sendWebmention
import requests
import os
import base64
import json
import time


WEBSITE = 'website'
WEBSITE_CONTENTS = 'https://api.github.com/repos/drivet/' + WEBSITE + '/contents/content/'

BRIDGY_ENDPOINT = r'https://brid.gy/publish/webmention'
PUBLISH_TARGETS = [r'https://brid.gy/publish/twitter']

articles_to_syndicate = []
syndicated_articles = []


def fix_metadata(generator, metadata):
    if 'mp_syndicate_to' not in metadata:
        metadata['mp_syndicate_to'] = []
    else:
        metadata['mp_syndicate_to'] = metadata['mp_syndicate_to'].split(',')

    if 'syndication' not in metadata:
        metadata['syndication'] = []
    else:
        metadata['syndication'] = metadata['syndication'].split(',')


def find_articles_to_syndicate(generator):
    for article in list(generator.articles):
        # skip if we do not want to syndicate, or we have already syndicated
        if not article.mp_syndicate_to or article.syndication:
            continue

        for syndicate_target in [t for t in article.mp_syndicate_to if t in PUBLISH_TARGETS]:
            source_url = generator.settings['SITEURL'] + '/' + article.url
            if article.category == 'notes':
                syndicate_target += '?bridgy_omit_link=true'
            articles_to_syndicate.append([source_url, syndicate_target, article])


def syndicate(p):
    for link in articles_to_syndicate:
        source_url = link[0]
        syndicate_target = link[1]
        article = link[2]
        r = send_webmention(source_url, syndicate_target)
        if r and r.status_code == requests.codes.created:
            bridgy_response = r.json()
            article.syndication.append(bridgy_response['url'])

        if article.syndication:
            syndicated_articles.append(article)


def send_webmention(source_url, target_url):
    print('preparing to send webmention from ' + source_url + ' to ' + target_url)
    print('waiting for ' + source_url + ' to be accessible...')
    if not wait_for_url(source_url):
        print(source_url + ' is not accessible.  Skipping webmention')
        return None
    print('sending web mention from ' + source_url + " to " + target_url + " using " + BRIDGY_ENDPOINT)
    r = sendWebmention(source_url, target_url, BRIDGY_ENDPOINT)
    if r.status_code != requests.codes.created:
        print('Bridgy webmention failed with ' + str(r.status_code))
        print('Error information ' + str(r.json()))
    return r


def save_syndication(p):
    for article in syndicated_articles:
        path = os.path.relpath(article.source_path, p.settings['PATH'])
        url = WEBSITE_CONTENTS + path
        fetch_request = requests.get(url, auth=(os.environ['USERNAME'], os.environ['PASSWORD']))

        if fetch_request.status_code != 200:
            raise Exception('failed to fetch ' + url + ' from github, code: ' + fetch_request.status_code)

        response = fetch_request.json()
        contents = b64decode(response['content'])
        pieces = contents.split('\n\n', 1)
        new_contents = pieces[0] + '\nsyndication: ' + ','.join(article.syndication) + '\n\n' + pieces[1]
        put_request = requests.put(url, auth=(os.environ['USERNAME'], os.environ['PASSWORD']),
                                   data=json.dumps({'message': 'post to ' + path,
                                                    'content': b64encode(new_contents),
                                                    'sha': response['sha']}))
        if put_request.status_code != 201:
            raise Exception('failed to put article ' + url + ' on github, code: ' + put_request.status_code)


def b64decode(s):
    return base64.b64decode(s.encode()).decode()


def b64encode(s):
    return base64.b64encode(s.encode()).decode()


def wait_for_url(url):
    timeout_secs = 15
    wait_secs = 1
    started = time.time()

    done = False
    found = False
    while not done:
        print('requesting head from ' + url)
        r = requests.head(url)
        if r.status_code == 200:
            print('found head from ' + url)
            done = True
            found = True
        elif (time.time() - started) >= timeout_secs:
            print('timeout for ' + url)
            done = True
            found = False
        else:
            print('sleeping...', flush=True)
            time.sleep(wait_secs)
    return found


def register():
    signals.article_generator_context.connect(fix_metadata)
    signals.article_generator_finalized.connect(find_articles_to_syndicate)
    signals.finalized.connect(syndicate)
    signals.finalized.connect(save_syndication)
