#!/usr/bin/env python3

import os
import argparse
import yaml
import datetime

argument_parser = argparse.ArgumentParser()
argument_parser.add_argument(
  '--mindate', '-m', help = 'The date from which to search for episodes in "YYYY-mm-dd" format.',
  default = str(datetime.date.min)
)
argument_parser.add_argument('--podcastsfile', '-p', help = 'The file containing the podcast data.')
argument_parser.add_argument('--output', '-o', help = 'The parent directory of the directory containing the podcast posts')
argument_parser.add_argument('--youtubekey', '-y', help = 'The Youtube api key to use when connecting to their api.')
argument_parser.add_argument('--spotifyid', '-i', help = 'The Spotify client id.')
argument_parser.add_argument('--spotifysecret', '-s', help = 'The secret to use when connecting to Spotify\'s api.')
args = argument_parser.parse_args()

min_date = args.mindate
podcasts_file = args.podcastsfile
output_parent = args.output
youtube_key = args.youtubekey
spotify_id = args.spotifyid
spotify_secret = args.spotifysecret

script_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "generate_posts.py")

with open(podcasts_file, 'r') as stream:
  try:
    podcasts = yaml.safe_load(stream)
    for podcast in podcasts:
      category = podcast['category']
      author = podcast['author']
      output = os.path.join(output_parent, category)

      command = f'{script_filename} --mindate {min_date} --output {output} --author {author} --category {category}'

      if 'youtube_playlist_id' in podcast:
        youtube_playlist_id = podcast['youtube_playlist_id']
        command += f' --youtubekey {youtube_key} --youtubeplaylistid {youtube_playlist_id}'

      if 'spotify_show_id' in podcast:
        spotify_show_id = podcast['spotify_show_id']
        command += f' --spotifyid {spotify_id} --spotifysecret {spotify_secret} --spotifyshowid {spotify_show_id}'

      if 'apple_podcast_id' in podcast:
        apple_podcast_id = podcast['apple_podcast_id']
        command += f' --applepodcastid {apple_podcast_id}'

      os.system(command)
  except yaml.YAMLError as exc:
    print(exc)
