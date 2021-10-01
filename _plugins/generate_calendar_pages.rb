module WrestlingWithJohners
  require "active_support/all"

  class CalendarPage < Jekyll::Page
    def initialize(site, page_num, date, last_page_num)
      @site = site # the current site instance.
      @base = site.source # the path to the source directory.
      # the directory the page will reside in.
      if page_num != nil
        @dir = "calendar/" + page_num.to_s
      else
        @dir = "calendar/"
      end

      # All pages have the same filename
      @basename = 'index'
      @ext = '.html'
      @name = 'index.html'

      # Add frontmatter
      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'calendar.html')

      self.data['layout'] = 'calendar'
      self.data['title'] = 'Calendar'
      if page_num != nil
        self.data['permalink'] = '/calendar/' + page_num.to_s
      else
        self.data['permalink'] = '/calendar/'
      end

      start_date = (date - 6.days)
      self.data['start_day'] = start_date.wday
      self.data['start_date'] = start_date.strftime("%Y/%m/%d")
      self.data['end_date'] = date.strftime("%Y/%m/%d")
      self.data['background'] = '/img/calendar-background.jpg'

      if page_num != nil
        if page_num < last_page_num
          self.data['prev'] = (page_num + 1).to_s
        end
        if page_num > 0
          self.data['next'] = (page_num - 1).to_s
        end
      else
        self.data['prev'] = "1"
      end
    end
  end

  class CalendarPageGenerator < Jekyll::Generator
    safe true
    priority :low

    def generate(site)
      Jekyll.logger.info "Calendar Pages Generator: ", "Generating Pages"
      # inject data and add to pages
      start_date = site.posts.docs.first['date']
      end_date = site.posts.docs.last['date']

      number_of_weeks = (end_date - start_date).seconds.in_weeks.to_i

      (0..number_of_weeks).each do |page_num|
        page_date = end_date - page_num.weeks
        site.pages << CalendarPage.new(site, page_num, page_date, number_of_weeks)
        if page_num == 0
          site.pages << CalendarPage.new(site, nil, page_date, number_of_weeks)
        end
      end
    end
  end


end

module Jekyll
  module PostUtils
    @@posts_by_date = nil

    def posts_by_date
      if @@posts_by_date == nil
        # Generate dictionary
        @@posts_by_date = {}
        @context.registers[:site].posts.docs.each do |post|
          post_date = post.data['date'].strftime("%Y/%m/%d")
          posts = @@posts_by_date[post_date]
          if @@posts_by_date[post_date] == nil
            posts = [post]
            @@posts_by_date[post_date] = posts
          else
            posts.push(post)
          end
        end
      end
      return @@posts_by_date
    end

    def posts_on_date(date)
      if posts_by_date[date] != nil
        return posts_by_date[date]
      else
        return []
      end
    end
  end
end

Liquid::Template.register_filter(Jekyll::PostUtils)
