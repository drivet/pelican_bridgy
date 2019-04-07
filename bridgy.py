from pelican import signals

from ronkyuu import sendWebmention
import requests
import os
import base64
import json


WEBSITE = 'website'
WEBSITE_CONTENTS = 'https://api.github.com/repos/drivet/' + WEBSITE + '/contents/content/'

BRIDGY_ENDPOINT = r'https://brid.gy/publish/webmention'
PUBLISH_TARGETS = [r'https://brid.gy/publish/twitter']

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


def syndicate(generator):
    for article in list(generator.articles):
        # skip if we do not want to syndicate, or we have already syndicated
        if not article.mp_syndicate_to or article.syndication:
            continue

        for syndicate_target in [t for t in article.mp_syndicate_to if t in PUBLISH_TARGETS]:
            source_url = generator.settings['SITEURL'] + '/' + article.url
            if article.category == 'notes':
                syndicate_target += '?bridgy_omit_link=true'

            print('sending web mention from ' + source_url + " to " + syndicate_target + " using " + BRIDGY_ENDPOINT)
            r = sendWebmention(source_url, syndicate_target, BRIDGY_ENDPOINT)
            bridgy_response = r.json()
            if r.status_code == requests.codes.created:
                article.syndication.append(bridgy_response['url'])
            else:
                print('Bridgy webmention failed with ' + str(r.status_code))
                print('Error information ' + str(bridgy_response))

        if article.syndication:
            syndicated_articles.append(article)


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


def register():
    signals.article_generator_context.connect(fix_metadata)
    signals.article_generator_finalized.connect(syndicate)
    signals.finalized.connect(save_syndication)
