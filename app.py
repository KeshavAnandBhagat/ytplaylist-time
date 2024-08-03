from datetime import timedelta, datetime
from flask import Flask, Response, request, render_template
import isodate
import json
import re
import requests
import os

APIS = os.environ['APIS'].strip('][').split(',')

URL1 = 'https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&maxResults=50&fields=items/contentDetails/videoId,nextPageToken&key={}&playlistId={}&pageToken='
URL2 = 'https://www.googleapis.com/youtube/v3/videos?&part=contentDetails,snippet,statistics&id={}&key={}&fields=items(contentDetails/duration,snippet(title,publishedAt),statistics(viewCount,likeCount))'

def get_id(playlist_link):
    p = re.compile('^([\S]+list=)?([\w_-]+)[\S]*$')
    m = p.match(playlist_link)
    if m:
        return m.group(2)
    else:
        return 'invalid_playlist_link'

def parse_duration(a):
    ts, td = a.seconds, a.days
    th, tr = divmod(ts, 3600)
    tm, ts = divmod(tr, 60)
    ds = ''
    if td:
        ds += ' {} day{},'.format(td, 's' if td != 1 else '')
    if th:
        ds += ' {} hour{},'.format(th, 's' if th != 1 else '')
    if tm:
        ds += ' {} minute{},'.format(tm, 's' if tm != 1 else '')
    if ts:
        ds += ' {} second{}'.format(ts, 's' if ts != 1 else '')
    if ds == '':
        ds = '0 seconds'
    return ds.strip().strip(',')

def todayAt(hr, min=0, sec=0, micros=0):
    now = datetime.now()
    return now.replace(hour=hr, minute=min, second=sec, microsecond=micros)

def find_time_slice():
    timeNow = datetime.now()
    time_slice = 0
    if todayAt(0) <= timeNow < todayAt(4):
        time_slice = 1
    elif todayAt(4) <= timeNow < todayAt(8):
        time_slice = 2
    if todayAt(8) <= timeNow < todayAt(12):
        time_slice = 3
    if todayAt(12) <= timeNow < todayAt(16):
        time_slice = 4
    if todayAt(16) <= timeNow < todayAt(20):
        time_slice = 5
    return time_slice

app = Flask(__name__, static_url_path='/static')

@app.route("/", methods=['GET', 'POST'])
def home():
    if request.method == 'GET':
        return render_template("home.html")
    else:
        playlist_link = request.form.get('search_string').strip()
        playlist_id = get_id(playlist_link)

        next_page = ''
        cnt = 0
        total_duration = timedelta(0)
        tsl = find_time_slice()
        display_text = []

        print(APIS[tsl])
        video_details = []

        while True:
            vid_list = []
            try:
                print(URL1.format(APIS[tsl].strip("'"), playlist_id))
                results = json.loads(requests.get(URL1.format(APIS[tsl].strip("'"), playlist_id) + next_page).text)

                for x in results['items']:
                    vid_list.append(x['contentDetails']['videoId'])
            except KeyError:
                display_text = [results['error']['message']]
                break

            url_list = ','.join(vid_list)
            cnt += len(vid_list)

            try:
                op = json.loads(requests.get(URL2.format(url_list, APIS[tsl].strip("'"))).text)
                for x in op['items']:
                    duration = isodate.parse_duration(x['contentDetails']['duration'])
                    total_duration += duration
                    video_details.append({
                        'title': x['snippet']['title'],
                        'duration': duration,
                        'views': x['statistics'].get('viewCount', 'N/A'),
                        'likes': x['statistics'].get('likeCount', 'N/A'),
                        'publishedAt': x['snippet']['publishedAt']
                    })
            except KeyError:
                display_text = [results['error']['message']]
                break

            if 'nextPageToken' in results and cnt < 500:
                next_page = results['nextPageToken']
            else:
                if cnt >= 500:
                    display_text = ['No of videos limited to 500.']
                display_text += [
                    'No of videos : ' + str(cnt), 'Average length of video : ' + parse_duration(total_duration / cnt),
                    'Total length of playlist : ' + parse_duration(total_duration), 'At 1.25x : ' + parse_duration(total_duration / 1.25),
                    'At 1.50x : ' + parse_duration(total_duration / 1.5), 'At 1.75x : ' + parse_duration(total_duration / 1.75),
                    'At 2.00x : ' + parse_duration(total_duration / 2)
                ]
                break

        sorted_video_details = sorted(video_details, key=lambda x: isodate.parse_duration(x['duration']))

        display_text.append("Shortest Video: " + sorted_video_details[0]['title'])
        display_text.append("Longest Video: " + sorted_video_details[-1]['title'])
        display_text.append("Latest Video: " + max(video_details, key=lambda x: x['publishedAt'])['title'])
        display_text.append("Oldest Video: " + min(video_details, key=lambda x: x['publishedAt'])['title'])

        return render_template("home.html", display_text=display_text, video_details=video_details)

@app.route("/healthz", methods=['GET', 'POST'])
def healthz():
    return "Success", 200    

@app.route('/.well-known/brave-rewards-verification.txt')
def static_from_root_brave():
    return Response(
        'This is a Brave Rewards publisher verification file.\n\nDomain: ytplaylist-len.herokuapp.com\nToken: aae68b8a5242a8e5f0505ee6eaa406bd51edf0dc9a05294be196495df223385c',
        mimetype='text/plain')

@app.route('/ads.txt')
def static_from_root_google():
    return Response(
        'google.com, pub-8874895270666721, DIRECT, f08c47fec0942fa0',
        mimetype='text/plain')

if __name__ == "__main__":
    app.run(use_reloader=True, debug=False)
