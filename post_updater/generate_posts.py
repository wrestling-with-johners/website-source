#!/usr/bin/env python3

import argparse
import base64
import os
import re
import fnmatch

import datetime
import html
import requests
from googleapiclient.discovery import build

YOUTUBE_PLAYLIST_ID = 'UU2P51c6szAyElgFPdKiqzEg'
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

SPOTIFY_SHOW_ID = '0s5QReHi6jMO3Kmm1I2yCd'

APPLE_PODCAST_ID = '1442108418'

def find_episode_number(title):
  ep_then_number = re.findall(r'EP ?\d+ ', title.lower(), re.IGNORECASE)
  if (len(ep_then_number) > 0):
    return int(re.findall(r'\d+', ep_then_number[0])[0])
  number_then_name = re.findall(r'\d+: Wrestling With Johners: ', title.lower(), re.IGNORECASE)
  if (len(number_then_name) > 0):
    return int(re.findall(r'\d+', number_then_name[0])[0])
  return None

class YoutubeData:
  def __init__(self, episode_number, title, date, video_id):
    self.episode_number = episode_number
    self.title = title
    self.date = date
    self.video_id = video_id

  def __str__(self):
    return 'Number: `{}`\nTitle: `{}`\nID: `{}`\nDate: `{}`\n'.format(self.episode_number, self.title, self.video_id, self.datetime)


class YoutubeScraper:
  def __init__(self, search_from_date):
    self.search_from_date = search_from_date
    self.youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=YOUTUBE_API_KEY)

  def get_youtube_videos(self):
    return self.get_youtube_videos_with_token(None)

  def get_youtube_videos_with_token(self, next_page_token):
    results = self.youtube.playlistItems().list(
      part = 'snippet',
      playlistId = YOUTUBE_PLAYLIST_ID,
      maxResults = 50,
      pageToken = next_page_token,
      fields="nextPageToken,items(snippet(publishedAt,title,resourceId(videoId)))"
    ).execute()

    data = []
  
    for result in results.get('items', []):
      snippet = result['snippet']
      title = html.unescape(snippet['title'])
      print ('Youtube `{}`'.format(title))
      episode_number = find_episode_number(title)
      video_id = snippet['resourceId']['videoId']
      date_time = snippet['publishedAt']
      date = datetime.datetime.strptime(date_time, '%Y-%m-%dT%H:%M:%S.%f%z').date()
      if date >= self.search_from_date:
        data.append(YoutubeData(episode_number, title, date, video_id))
	  
    if 'nextPageToken' in results:
      print ('token {}'. format(results['nextPageToken']))
      return data + self.get_youtube_videos_with_token(results['nextPageToken'])
    else:
      print ('no token')
      return data


class SpotifyData:
  def __init__(self, episode_number, title, date, track_id):
    self.episode_number = episode_number
    self.title = title
    self.date = date
    self.track_id = track_id

  def __str__(self):
    return 'Number: `{}`\nTitle: `{}`\nID: `{}`\nDate: `{}`\n'.format(self.episode_number, self.title, self.track_id, self.date)


class SpotifyScraper:
  def __init__(self, search_from_date):
    self.search_from_date = search_from_date

  def get_authorization(self):
    data = '{}:{}'.format(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
    bytes = base64.b64encode(data.encode('utf-8'))
    bytes_as_string = str(bytes, 'utf-8')
    return 'Basic {}'.format(bytes_as_string)

  def get_access_key(self):
    result = requests.post(
      'https://accounts.spotify.com/api/token',
      data = {'grant_type': 'client_credentials'},
      headers = {'Authorization': self.get_authorization()}
    )
    if (result.ok):
      return result.json()["access_token"]
    else:
      result.raise_for_status()

  def get_tracks(self, access_key, url):
    result = requests.get(
      url,
      headers = {
        'Authorization': 'Bearer {}'.format(access_key),
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      }
    )
    if (result.ok):
      result_json = result.json()
	  
      data = []

      for result in result_json['items']:
        name = html.unescape(result['name'])
        print ('Spotify `{}`'.format(name))
        episode_number = find_episode_number(name)
        track_id = result['id']
        date = datetime.datetime.strptime(result['release_date'], '%Y-%m-%d').date()
        if date >= self.search_from_date:
          data.append(SpotifyData(episode_number, name, date, track_id))
        
      if 'next' in result_json and result_json['next']:
        print ('token {}'.format(result_json['next']))
        return data + self.get_tracks(access_key, result_json['next'])
      else:
        print ('no token')
        return data
    else :
      result.raise_for_status()

  def get_all_tracks(self):
    access_key = self.get_access_key()
    return self.get_tracks(access_key, 'https://api.spotify.com/v1/shows/{}/episodes?limit=50&offset=0&market=US'.format(SPOTIFY_SHOW_ID))



class AppleData:
  def __init__(self, episode_number, title, date, track_id):
    self.episode_number = episode_number
    self.title = title
    self.date = date
    self.track_id = track_id

  def __str__(self):
    return 'Number: `{}`\nTitle: `{}`\nID: `{}`\nDate: `{}`\n'.format(self.episode_number, self.title, self.track_id, self.date)


class AppleScraper:
  def __init__(self, search_from_date):
    self.search_from_date = search_from_date

  def get_tracks(self, next_url_part):
    response = requests.get('https://amp-api.podcasts.apple.com{}'.format(next_url_part), headers = {
      'Accept': 'application/json',
      'Referer': 'https://podcasts.apple.com/us/podcast/id{}'.format(APPLE_PODCAST_ID),
      'Origin': 'https://podcasts.apple.com',
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36',
      'Authorization': 'Bearer eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IldlYlBsYXlLaWQifQ.eyJpc3MiOiJBTVBXZWJQbGF5IiwiaWF0IjoxNTc0MTk3NDA3LCJleHAiOjE1ODk3NDk0MDd9.ael_GP97O4fyXJuQAQlmC7ieY-t-OOGFwtXShhVA6m_p9Sq03D-_FiUKSfZ2iXGob3vPFnDe0s_OKI3Tg7KVaA',
      'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
    })
    if response.ok:
      response_json = response.json()
      data = []
      for episode in response_json['data']:
        track_id = episode['id']
        attributes = episode['attributes']
        title = attributes['name']
        print ('Apple `{}`'.format(title))
        date = datetime.datetime.strptime(attributes['releaseDateTime'], '%Y-%m-%dT%H:%M:%S%z').date()
        if 'episodeNumber' in attributes:
          episode_number = attributes['episodeNumber']
        else:
          episode_number = find_episode_number(title)
        if date >= self.search_from_date:
          data.append(AppleData(episode_number, title, date, track_id))
      
      if 'next' in response_json:
        print (response_json['next'])
        return data + self.get_tracks(response_json['next'])
      else:
        print('no more data')
        return data
    else:
      response.raise_for_status()

  def get_all_tracks(self):
    return self.get_tracks('/v1/catalog/us/podcasts/{}/episodes?offset=0&limit=10'.format(APPLE_PODCAST_ID))


class PostData:
  def __init__(self, episode_number, title, date, youtube_video_id, spotify_track_id, apple_track_id, categories, author):
    self.episode_number = episode_number
    self.title = title
    self.date = date
    self.youtube_video_id = youtube_video_id
    self.spotify_track_id = spotify_track_id
    self.apple_track_id = apple_track_id
    self.categories = categories
    self.author = author

  def __str__(self):
    return 'Number: `{}`\nTitle: `{}`\nDate: `{}`\nYoutube: `{}`\nSpotify: `{}`'.format(self.episode_number, self.title, self.date, self.youtube_video_id, self.spotify_track_id)


class Matcher:
  def __init__(self, youtube_data, spotify_data, apple_data):
    self.youtube_data = youtube_data
    self.spotify_data = spotify_data
    self.apple_data = apple_data
    self.title_regex = re.compile(r'(ep ?\d+(( – )|(–))?)|([\W_]+)')

  def title_to_key(self, title):
    return self.title_regex.sub('', title.lower())

  def add_data(self, data_by_episode_number, data_by_title, debug_string, episode_data, add_specific_data):
    for data in episode_data:
      if data.episode_number and data.episode_number in data_by_episode_number:
        print ('Matched {} `{}` With `Ep{}`'.format(debug_string, data.title, data.episode_number))
        add_specific_data(data_by_episode_number[data.episode_number], data)
        continue
      title_key = self.title_to_key(data.title)
      if title_key in data_by_title:
        print ('Matched {} `{}` With `{}`'.format(debug_string, data.title, title_key))
        post_data = data_by_title[title_key]
        post_data.title = data.title
        add_specific_data(post_data, data)
        if (data.date < post_data.date):
          post_data.date = data.date
        if data.episode_number:
          post_data.episode_number = data.episode_number
          post_data.categories.add('podcasts')
        continue
      self.add_new_data(data_by_episode_number, data_by_title, debug_string, data, add_specific_data)

  def add_new_data(self, data_by_episode_number, data_by_title, debug_string, episode_data, add_specific_data):
    categories = set()
    if episode_data.episode_number:
      categories.add('podcasts')
    if 'interview' in episode_data.title.lower():
      categories.add('interviews')
    post_data = PostData(episode_data.episode_number, episode_data.title, episode_data.date, None, None, None, categories, 'john')
    add_specific_data(post_data, episode_data)
    title_key = self.title_to_key(post_data.title)
    print ('New {}, {} -> {}'.format(debug_string, episode_data.title, title_key))
    data_by_title[title_key] = post_data
    if (post_data.episode_number):
      data_by_episode_number[post_data.episode_number] = post_data

  def match(self):
    data_by_episode_number = {}
    data_by_title = {}
    
    def assign_youtube_video_id(some_post_data, youtube_data):
      some_post_data.youtube_video_id = youtube_data.video_id
    
    def assign_spotify_track_id(some_post_data, spotify_data):
      some_post_data.spotify_track_id = spotify_data.track_id
    
    def assign_apple_track_id(some_post_data, apple_data):
      some_post_data.apple_track_id = apple_data.track_id

    for spotify_data in self.spotify_data:
      self.add_new_data(data_by_episode_number, data_by_title, 'Spotify', spotify_data, assign_spotify_track_id)
    
    self.add_data(data_by_episode_number, data_by_title, 'Youtube', self.youtube_data, assign_youtube_video_id)
    
    self.add_data(data_by_episode_number, data_by_title, 'Apple', self.apple_data, assign_apple_track_id)
    
    return data_by_title.values()

class PostWriter:
  def __init__(self, matched_data, output_directory):
    self.matched_data = matched_data
    self.output_directory = output_directory

  def value_or_empty(self, value):
    if value:
      return str(value)
    else:
      return ''

  def sanitize_filename(self, filename):
    return "".join([c for c in filename if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    
  def format_as_podcast(self, data):
    return '---\nlayout: post\ntitle: "{}"\ndate: {}\ncategories: {}\nauthor: john\nspotify_track_id: {}\nyoutube_video_id: {}\napple_track_id: {}\n---\n'.format(data.title, data.date.strftime('%Y-%m-%d'), ' '.join(sorted(data.categories)), self.value_or_empty(data.spotify_track_id), self.value_or_empty(data.youtube_video_id), self.value_or_empty(data.apple_track_id))

  def format_as_generic(self, data):
    return '---\nlayout: post\ntitle: "{}"\ndate: {}\ncategories:\nauthor: john\nspotify_track_id: {}\nyoutube_video_id: {}\napple_track_id: {}\n---\n'.format(data.title, data.date.strftime('%Y-%m-%d'), self.value_or_empty(data.spotify_track_id), self.value_or_empty(data.youtube_video_id), self.value_or_empty(data.apple_track_id))

  def output_to_file(self, parent_directory, data):
    if data.episode_number:
      filename = '{}-EP{}.markdown'.format(data.date.strftime('%Y-%m-%d'), data.episode_number)
      filename_pattern = r'\d{{4}}-\d{{2}}-\d{{2}}-EP{}\.markdown'.format(data.episode_number)
      for name in os.listdir(parent_directory):
        if re.match(filename_pattern, name):
          print ('Matched {} with existing {}'.format(data.episode_number, name))
          filename = name
          existing_file = open(os.path.join(parent_directory, name), 'r')
          lines = existing_file.readlines()
          title = lines[2].split(':')[1].strip()
          title = title[1:-1]
          data.title = title
          data.date = datetime.datetime.strptime(lines[3].split(':')[1].strip(), '%Y-%m-%d').date()
          data.categories = set(lines[4].split(':')[1].strip().split(' '))
          data.author = lines[5].split(':')
          spotify_track_id = lines[6].split(':')[1].strip()
          youtube_video_id = lines[7].split(':')[1].strip()
          apple_track_id = lines[8].split(':')[1].strip()
          if spotify_track_id:
            data.spotify_track_id = spotify_track_id
          if youtube_video_id:
            data.youtube_video_id = youtube_video_id
          if apple_track_id:
            data.apple_track_id = apple_track_id
          break
      to_write = self.format_as_podcast(data)
    else:
      filename = '{}-{}.markdown'.format(data.date.strftime('%Y-%m-%d'), self.sanitize_filename(data.title))
      to_write = self.format_as_generic(data)

    output_file = open(os.path.join(parent_directory, filename), 'w')
    
    print ('Writing to: `{}`'.format(output_file.name))
    output_file.write(to_write)
    output_file.close()

  def write(self):
    for data in self.matched_data:
      self.output_to_file(self.output_directory, data)

def find_search_from_date(directory):
  max_date = datetime.date.min
  for filename in os.listdir(directory):
    if re.match(r'\d{4}-\d{2}-\d{2}-EP\d+.*', filename):
      print ('checking {}'.format(filename))
      date = datetime.datetime.strptime(re.findall(r'\d{4}-\d{2}-\d{2}', filename)[0], '%Y-%m-%d').date()
      if date > max_date:
        max_date = date 
  return max_date

argument_parser = argparse.ArgumentParser()
argument_parser.add_argument('--mindate', '-m', help = 'The date from which to search for episodes in "YYYY-mm-dd" format.', default = str(datetime.date.min))
argument_parser.add_argument('--autodate', '-a', help = 'Automatically find the search from date using the post files in this directory. The files should be formatted "YYYY-mm-dd-EP*"')
argument_parser.add_argument('--output', '-o', help = 'The directory in which to output the results.', default = '_posts')
argument_parser.add_argument('--youtubekey', '-y', help = 'The Youtube api key to use when connecting to their api.', required = True)
argument_parser.add_argument('--spotifyid', '-i', help = 'The Spotify client id.', required = True)
argument_parser.add_argument('--spotifysecret', '-s', help = 'The secret to use when connecting to Spotify\'s api.', required = True)
args = argument_parser.parse_args()

if args.autodate:
  search_from_date = find_search_from_date(args.autodate)
else:
  search_from_date = datetime.datetime.strptime(args.mindate, '%Y-%m-%d').date()
  
output_directory = args.output

YOUTUBE_API_KEY = args.youtubekey
SPOTIFY_CLIENT_ID = args.spotifyid
SPOTIFY_CLIENT_SECRET = args.spotifysecret

print ('Searching for posts from {}'.format(search_from_date))

youtube_data = YoutubeScraper(search_from_date).get_youtube_videos()

spotify_data = SpotifyScraper(search_from_date).get_all_tracks()

apple_data = AppleScraper(search_from_date).get_all_tracks()

matched_data = Matcher(youtube_data, spotify_data, apple_data).match()

PostWriter(matched_data, output_directory).write()
