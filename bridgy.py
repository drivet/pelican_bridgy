from pelican import signals
from ronkyuu import sendWebmention
import requests


BRIDGY_ENDPOINT = r'https://brid.gy/publish/webmention'
PUBLISH_TARGETS = [r'https://brid.gy/publish/twitter']

syndicated_articles = []


def syndicate(generator):
    for article in list(generator.articles):
        if not hasattr(article, 'mp_syndicate_to'):
            article.mp_syndicate_to = ''

        if not hasattr(article, 'syndication'):
            article.syndication = ''

        if not article.mp_syndicate_to or article.syndication:
            continue

        article.syndication = []
        for syndicate_target in [t for t in article.mp_syndicate_to.split(',')
                                 if t in PUBLISH_TARGETS]:
            source_url = generator.settings['SITEURL'] + '/' + article.url
            if article.category == 'notes':
                syndicate_target += '?bridgy_omit_link=true'

            print('sending web mention from ' + source_url + " to " + syndicate_target + " using " + BRIDGY_ENDPOINT )
            r = sendWebmention(source_url, syndicate_target, BRIDGY_ENDPOINT)
            bridgy_response = r.json()
            if r.status_code == requests.codes.created:
                article.syndication.append(bridgy_response['url'])
            else:
                print('Bridgy webmention failed with ' + str(r.status_code))
                print('Error information ' + str(bridgy_response))
        else:
            print('no matching syndication targets')

        if article.syndication:
            syndicated_articles.append(article)


def save_syndication(p):
    print('calling save_syndication')
    for article in syndicated_articles:
        print('opening ' + article.source_file)
        with open(article.source_file, 'r') as f:
            contents = f.read()
        pieces = contents.split('\n\n', 1)
        new_contents = pieces[0] + '\nsyndication: ' + ','.join(syndicated_articles) + '\n' + pieces[1]
        print('saving ' + article.source_file)
        with open(article.source_file, 'w') as f:
            f.write(new_contents)


def register():
    signals.article_generator_finalized.connect(syndicate)
    #signals.finalized.connect(save_syndication)
