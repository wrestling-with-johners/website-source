#!/usr/bin/env python3

import os

parent_directory = os.path.join('../', '_posts', 'wrestling-with-johners')

for post_file in os.listdir(parent_directory):
  with open(os.path.join(parent_directory, post_file), 'r+') as post:
    print(post_file)
    lines = post.readlines()
    categories = lines[4].split(':')[1].strip().split(' ')
    try:
      index = categories.index('podcasts')
      categories[index] = 'wrestling-with-johners'
      categories_line = ' '.join(categories)
      lines[4] = f'categories: {categories_line}\n'
      # write back to file
      print(lines)
      post.seek(0)
      post.writelines(lines)
      post.truncate()
    except ValueError as error:
      # Ignore, not a podcast
      print(f'Ignoring {post_file}: {error}')
      continue

