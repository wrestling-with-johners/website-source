module WrestlingWithJohners
  class PodcastIndexPage < Jekyll::Page
    def initialize(site, podcast_data)
      category = podcast_data['category']
      @site = site # the current site instance.
      @base = site.source # the path to the source directory.
      @dir = category # the directory the page will reside in.

      # All pages have the same filename
      @basename = 'index'
      @ext = '.html'
      @name = 'index.html'

      # Add frontmatter
      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'podcast-page.html')

      self.data['layout'] = 'podcast-page'
      self.data['permalink'] = '/' + category + '/'
      self.data['title'] = podcast_data['title']
      self.data['background'] = '/img/' + podcast_data['background']
      pagination = {}
      pagination['enabled'] = true
      pagination['category'] = category
      self.data['pagination'] = pagination
      self.data['author'] = podcast_data['author']
    end
  end

  class PodcastIndexPageGenerator < Jekyll::Generator
    safe true
    priority :highest

    def generate(site)
      Jekyll.logger.info "Podcast Index Page Generator: ", "Generating Pages"
      # inject data and add to pages
      site.data['podcasts'].each do |podcast_data|
        site.pages << PodcastIndexPage.new(site, podcast_data)
      end
    end
  end
end
