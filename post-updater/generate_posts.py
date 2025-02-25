#!/usr/bin/env python3

import argparse
import base64
import os
import re
import fnmatch
import sys

import datetime
import dateutil.parser as datetime_parser
import html
from requests import Session
from requests.adapters import HTTPAdapter, Retry
import time
from googleapiclient.discovery import build
import frontmatter

from get_apple_auth import get_auth


YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

MAX_SLEEP_TIME = 30

http_session = Session()
retries = Retry(
  total = 5,
  backoff_factor = 0.1,
  status_forcelist = [500, 502, 503, 504, 404]
)
http_session.mount('https://', HTTPAdapter(max_retries=retries))

def find_episode_number(title):
  ep_then_number = re.findall(r'EP ?\d+ ', title.lower(), re.IGNORECASE)
  if (len(ep_then_number) > 0):
    return int(re.findall(r'\d+', ep_then_number[0])[0])
  return None

def find_part_number(title):
  part_x_of_y = re.findall(r'\(Part \d+\/\d+\)', title.lower(), re.IGNORECASE)
  if len(part_x_of_y) > 0:
    return int(re.findall(r'\d+', part_x_of_y[0])[0])
  else:
    return None

def grouped(iterable, n):
  return zip(*[iter(iterable)]*n)

def escape_for_frontmatter(title):
  return title.replace('"', r'\"')

class YoutubeData:
  def __init__(self, episode_number, part_number, title, date, video_id):
    self.episode_number = episode_number
    self.part_number = part_number
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
      part = 'snippet,contentDetails',
      playlistId = YOUTUBE_PLAYLIST_ID,
      maxResults = 50,
      pageToken = next_page_token,
      fields="nextPageToken,items(snippet(title,resourceId(videoId),description),contentDetails(videoPublishedAt))"
    ).execute()

    data = []

    continue_search = True

    for result in results.get('items', []):
      # Ignore any video without a published at, they're private or otherwise not applicable
      content_details = result['contentDetails']
      if 'videoPublishedAt' in content_details:
        date_time = content_details['videoPublishedAt']
        date = datetime_parser.isoparse(date_time).date()
        snippet = result['snippet']
        title = escape_for_frontmatter(html.unescape(snippet['title']))
        print ('Youtube `{}`'.format(title))
        episode_number = find_episode_number(title)
        if episode_number == None:
          description = snippet['description']
          description_split = description.split('\n')
          description_last_line = description_split[-1]
          episode_number = find_episode_number(description_last_line)
          part_number = find_part_number(description_last_line)
        else:
          part_number = find_part_number(title)
        video_id = snippet['resourceId']['videoId']
        if date >= self.search_from_date:
          data.append(YoutubeData(episode_number, part_number, title, date, video_id))
        else:
          continue_search = False
          break

    if continue_search and 'nextPageToken' in results:
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
    result = http_session.post(
      'https://accounts.spotify.com/api/token',
      data = {'grant_type': 'client_credentials'},
      headers = {'Authorization': self.get_authorization()}
    )
    if (result.ok):
      return result.json()["access_token"]
    else:
      result.raise_for_status()

  def get_tracks(self, access_key, url):
    result = http_session.get(
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

      continue_search = True

      for result in result_json['items']:
        if result is not None:
          name = escape_for_frontmatter(html.unescape(result['name']))
          print ('Spotify `{}`'.format(name))
          episode_number = find_episode_number(name)
          track_id = result['id']
          date = datetime.datetime.strptime(result['release_date'], '%Y-%m-%d').date()
          if date >= self.search_from_date:
            data.append(SpotifyData(episode_number, name, date, track_id))
          else:
            continue_search = False
            break

      if continue_search and 'next' in result_json and result_json['next']:
        return data + self.get_tracks(access_key, result_json['next'])
      else:
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
    with open(os.path.join(os.path.dirname(__file__), 'apple_auth'), 'r') as file:
      self.auth = file.readline()

  def get_tracks(self, next_url_part, retry_apple_auth = True):
    response = http_session.get('https://amp-api.podcasts.apple.com{}'.format(next_url_part), headers = {
      'Accept': '*/*',
      'Referer': 'https://podcasts.apple.com/',
      'Origin': 'https://podcasts.apple.com',
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
      'Authorization': self.auth,
    })
    if response.ok:
      response_json = response.json()
      data = []
      continue_search = True
      for episode in response_json['data']:
        track_id = episode['id']
        if 'attributes' in episode:
          attributes = episode['attributes']
          title = escape_for_frontmatter(attributes['name'])
          print ('Apple `{}`'.format(title))
          date = datetime.datetime.strptime(attributes['releaseDateTime'], '%Y-%m-%dT%H:%M:%S%z').date()
          if 'episodeNumber' in attributes:
            episode_number = attributes['episodeNumber']
          else:
            episode_number = find_episode_number(title)
          if date >= self.search_from_date:
            data.append(AppleData(episode_number, title, date, track_id))
          else:
            continue_search = False
            break
        else:
          print (f'Unable to get apple data for track {track_id}.')
      
      if continue_search and 'next' in response_json:
        print (response_json['next'])
        return data + self.get_tracks(response_json['next'], retry_apple_auth)
      else:
        print('no more data')
        return data

    elif response.status_code == 401:
      print ('Apple responded with 401')
      if retry_apple_auth:
        self.auth = get_auth()
        with open(os.path.join(os.path.dirname(__file__), 'apple_auth'), 'w') as file:
          file.write(self.auth)
        return self.get_tracks(next_url_part, False)
      else:
        print ('Halting attempts, unable to reacquire auth')
        return []
    elif response.status_code == 429:
      print(f"Response Headers: {response.headers}")
      sleep_time = min(response.headers.get('Retry-After', MAX_SLEEP_TIME), MAX_SLEEP_TIME)
      print(f'Apple responded with 429, sleeping for {sleep_time} seconds')
      time.sleep(sleep_time)
      return self.get_tracks(next_url_part, retry_apple_auth)
    else:
      response.raise_for_status()

  def get_all_tracks(self):
    return self.get_tracks('/v1/catalog/us/podcasts/{}/episodes?offset=0&limit=10'.format(APPLE_PODCAST_ID))


class YoutubeMetadata:
  def __init__(self, video_id, part_number):
    self.video_id = video_id
    self.part_number = part_number
    
  def __hash__(self):
    return self.part_number.__hash__()
    
  def __eq__(self, other):
    if isinstance(other, YoutubeMetadata):
      return self.part_number == other.part_number
    else:
      return false
    
  def __str__(self):
    return '{},{}'.format(self.part_number, self.video_id)
    
  def __repr__(self):
    return str(self)

class PostData:
  def __init__(self, episode_number, title, date, youtube_video_id, spotify_track_id, apple_track_id, categories, author, youtube_metadata):
    self.episode_number = episode_number
    self.title = title
    self.date = date
    self.youtube_video_id = youtube_video_id
    self.spotify_track_id = spotify_track_id
    self.apple_track_id = apple_track_id
    self.categories = categories
    self.author = author
    self.youtube_metadata = youtube_metadata

  def add_youtube_metadata(self, youtube_data):
    youtube_metadata = YoutubeMetadata(youtube_data.video_id, youtube_data.part_number)
    if not youtube_metadata in self.youtube_metadata:
      print('Adding youtube metadata for part {} to ep {}'.format(youtube_metadata.part_number, self.episode_number))
      self.youtube_metadata.add(youtube_metadata)
    else:
      print('Attempted to override existing part data for part {} in ep {}'.format(youtube_metadata.part_number, self.episode_number))

  def __str__(self):
    return 'Number: `{}`\nTitle: `{}`\nDate: `{}`\nYoutube: `{}`\nSpotify: `{}`'.format(self.episode_number, self.title, self.date, self.youtube_video_id, self.spotify_track_id)


class Matcher:
  def __init__(self, spotify_data, apple_data):
    self.spotify_data = spotify_data
    self.apple_data = apple_data
    self.title_regex = re.compile(r' ')

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
        continue
      self.add_new_data(data_by_episode_number, data_by_title, debug_string, data, add_specific_data)

  def add_new_data(self, data_by_episode_number, data_by_title, debug_string, episode_data, add_specific_data):
    categories = set()
    if 'interview' in episode_data.title.lower():
      categories.add('interviews')
    post_data = PostData(episode_data.episode_number, episode_data.title, episode_data.date, None, None, None, categories, 'john', set())
    add_specific_data(post_data, episode_data)
    title_key = self.title_to_key(post_data.title)
    print ('New {}, {} -> {}'.format(debug_string, episode_data.title, title_key))
    data_by_title[title_key] = post_data
    if (post_data.episode_number):
      data_by_episode_number[post_data.episode_number] = post_data

  def match(self):
    data_by_episode_number = {}
    data_by_title = {}

    def assign_spotify_track_id(some_post_data, spotify_data):
      some_post_data.spotify_track_id = spotify_data.track_id
    
    def assign_apple_track_id(some_post_data, apple_data):
      some_post_data.apple_track_id = apple_data.track_id

    for spotify_data in self.spotify_data:
      self.add_new_data(data_by_episode_number, data_by_title, 'Spotify', spotify_data, assign_spotify_track_id)

    self.add_data(data_by_episode_number, data_by_title, 'Apple', self.apple_data, assign_apple_track_id)
    
    return data_by_title.values()

def value_or_empty(value):
  if value:
    return str(value)
  else:
    return ''

def sanitize_filename(filename):
  return "".join([c for c in filename if c.isalpha() or c.isdigit() or c==' ']).rstrip()

def youtube_metadata_as_string(data):
  if not data.youtube_metadata:
    return ''
  else:
    return ','.join(str(metadata) for metadata in data.youtube_metadata)

def format_post(data):
  return '---\nlayout: post\ntitle: "{}"\ndate: {}\ncategories: {}\nauthor: {}\nspotify_track_id: {}\nyoutube_video_id: {}\napple_track_id: {}\nyoutube_metadata: {}\n---\n'.format(data.title, data.date.strftime('%Y-%m-%d'), ' '.join(sorted(data.categories)), data.author, value_or_empty(data.spotify_track_id), value_or_empty(data.youtube_video_id), value_or_empty(data.apple_track_id), youtube_metadata_as_string(data))

def sanitize_filename(filename):
  return "".join([c for c in filename if c.isalpha() or c.isdigit() or c==' ']).rstrip()

class PostWriter:
  def __init__(self, matched_data, output_directory, categories, author):
    self.matched_data = matched_data
    self.output_directory = output_directory
    self.categories = categories
    self.author = author

  def value_or_empty(self, value):
    if value:
      return str(value)
    else:
      return ''
    
  def youtube_metadata_as_string(self, data):
    if not data.youtube_metadata:
      return ''
    else:
      return ','.join(str(metadata) for metadata in data.youtube_metadata)

  def parse_youtube_metadata(self, line_string):
    line_split_on_front = line_string.split('youtube_metadata: ')
    data = set()
    if len(line_split_on_front) > 1:
      without_front = line_split_on_front[1]
      each_part = without_front.split(',')
      for part_number, video_id in grouped(each_part, 2):
        data.add(YoutubeMetadata(video_id, int(part_number)))
    return data

  def match_with_existing(self, parent_directory, data, filename_pattern):
    for name in os.listdir(parent_directory):
      if re.match(filename_pattern, name):
        print ('Potential Match for {} with existing {}'.format(data.title, name))
        filename = name
        existing_file = open(os.path.join(parent_directory, name), 'r')
        lines = existing_file.readlines()

        # If an item has a matching title and release date within a week of another we assume they're the same thing
        date_in_file = datetime.datetime.strptime(lines[3].split(':')[1].strip(), '%Y-%m-%d').date()
        if abs((date_in_file - data.date).days) <= 7:
          print ('Matched {} with existing {}'.format(data.title, name))
          data.date = date_in_file
          title = lines[2].split(':', 1)[1].strip()
          title = title[1:-1]
          data.title = title
          data.categories.update(lines[4].split(':', 1)[1].strip().split(' '))
          data.author = lines[5].split(':', 1)[1].strip()
          spotify_track_id = lines[6].split(':', 1)[1].strip()
          youtube_video_id = lines[7].split(':', 1)[1].strip()
          apple_track_id = lines[8].split(':', 1)[1].strip()
          if lines[9].strip() == '---':
            print('Existing youtube metadata not found')
            youtube_metadata = None
          else:
            youtube_metadata = self.parse_youtube_metadata(lines[9].strip())
          if spotify_track_id:
            data.spotify_track_id = spotify_track_id
          if youtube_video_id:
            data.youtube_video_id = youtube_video_id
          if apple_track_id:
            data.apple_track_id = apple_track_id
          if youtube_metadata:
            new_youtube_metadata = data.youtube_metadata
            data.youtube_metadata = youtube_metadata
            for metadata in new_youtube_metadata:
              data.add_youtube_metadata(metadata)
          break
        else:
          print('Unable to match, file date ({}) and data date ({}) are not within a week of each other'.format(date_in_file, data.date))

  def output_to_file(self, parent_directory, data):
    data.categories.update(self.categories)
    if self.author:
      data.author = self.author

    sanitized_title = sanitize_filename(data.title)
    filename = '{}-{}.markdown'.format(data.date.strftime('%Y-%m-%d'), sanitized_title)
    self.match_with_existing(parent_directory, data, r'\d{{4}}-\d{{2}}-\d{{2}}-{}\.markdown'.format(sanitized_title))

    to_write = format_post(data)

    with open(os.path.join(parent_directory, filename), 'w') as output_file:
      print ('Writing to: `{}`'.format(output_file.name))
      output_file.write(to_write)

  def write(self):
    os.makedirs(self.output_directory, exist_ok = True)
    for data in self.matched_data:
      self.output_to_file(self.output_directory, data)

class YoutubePostWriter:
  def __init__(self, data, output_directory, categories, author):
    self.data = data
    self.output_directory = output_directory
    self.categories = categories
    self.author = author

  def output_to_file(self, parent_directory, existing_files, item):
    item.categories.update(self.categories)
    if self.author:
      item.author = self.author

    if item.youtube_video_id in existing_files:
      # Delete this file and create a new one later
      existing_file = existing_files[item.youtube_video_id]
      os.remove(existing_file['path'])
      existing_files.pop(item.youtube_video_id)

    sanitized_title = sanitize_filename(item.title)
    filename = '{}-{}.markdown'.format(item.date.strftime('%Y-%m-%d'), sanitized_title)

    to_write = format_post(item)

    with open(os.path.join(parent_directory, filename), 'w') as output_file:
      print ('Writing to: `{}`'.format(output_file.name))
      output_file.write(to_write)

  def write(self):
    os.makedirs(self.output_directory, exist_ok = True)
    existing_files = {}

    for name in os.listdir(self.output_directory):
      path_to_file = os.path.join(self.output_directory, name)
      with open(path_to_file, 'r') as file:
        post_frontmatter = frontmatter.load(file)
        existing_files[post_frontmatter['youtube_video_id']] = {'frontmatter': post_frontmatter, 'path': path_to_file}

    for item in self.data:
      categories = set()
      categories.add('videos')
      post_data = PostData(item.episode_number, item.title, item.date, item.video_id, None, None, categories, None, None)
      self.output_to_file(self.output_directory, existing_files, post_data)

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
argument_parser.add_argument('--youtubekey', '-y', help = 'The Youtube api key to use when connecting to their api.')
argument_parser.add_argument('--spotifyid', '-i', help = 'The Spotify client id.')
argument_parser.add_argument('--spotifysecret', '-s', help = 'The secret to use when connecting to Spotify\'s api.')
argument_parser.add_argument('--youtubeplaylistid', help = 'The id of the youtube playlist to search')
argument_parser.add_argument('--spotifyshowid', help = 'The id of the spotify show')
argument_parser.add_argument('--applepodcastid', help = "The id of the apple podcast")
argument_parser.add_argument('--category', nargs = '+', help = 'Any extra category(s) to include for each post')
argument_parser.add_argument('--author', help = 'The author for each post')
args = argument_parser.parse_args()

if args.autodate:
  search_from_date = find_search_from_date(args.autodate)
else:
  search_from_date = datetime.datetime.strptime(args.mindate, '%Y-%m-%d').date()
  
if any([args.youtubekey, args.youtubeplaylistid]) and not all([args.youtubekey, args.youtubeplaylistid]):
  print ('When using any of youtubekey and youtubeplaylistid all must be defined')
  argument_parser.print_help()
  sys.exit(2)
  
if any([args.spotifyid, args.spotifysecret, args.spotifyshowid]) and not all([args.spotifyid, args.spotifysecret, args.spotifyshowid]):
  print ('When using any of spotifyid, spotifysecret and spotifyshowid all must be defined')
  argument_parser.print_help()
  sys.exit(2)

if args.category:
  categories = args.category
else:
  categories = []

author = args.author

output_directory = args.output

YOUTUBE_API_KEY = args.youtubekey
SPOTIFY_CLIENT_ID = args.spotifyid
SPOTIFY_CLIENT_SECRET = args.spotifysecret

YOUTUBE_PLAYLIST_ID = args.youtubeplaylistid
SPOTIFY_SHOW_ID = args.spotifyshowid
APPLE_PODCAST_ID = args.applepodcastid

print('Searching for posts for {} from {}'.format(author, search_from_date))

if any([args.youtubekey, args.youtubeplaylistid]):
  youtube_data = YoutubeScraper(search_from_date).get_youtube_videos()
else:
  youtube_data = []

if any([args.spotifyid, args.spotifysecret, args.spotifyshowid]):
  spotify_data = SpotifyScraper(search_from_date).get_all_tracks()
else:
  spotify_data = []

if args.applepodcastid:
  apple_data = AppleScraper(search_from_date).get_all_tracks()
else:
  apple_data = []

matched_data = Matcher(spotify_data, apple_data).match()

PostWriter(matched_data, output_directory, categories, author).write()

YoutubePostWriter(youtube_data, os.path.join(output_directory, 'videos'), categories, author).write()
