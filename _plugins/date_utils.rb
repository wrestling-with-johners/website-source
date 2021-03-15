require 'liquid'
require 'active_support/all'

module Jekyll
  module DateUtils
    # Get the days from start to end
    def day_range(start_date, end_date)
      days = []
      (Date.parse(start_date)..Date.parse(end_date)).each do |day|
        days << day.strftime('%Y/%m/%d')
      end
      return days.reverse()
    end

    def day_name_range(start_day)
      days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
      return days.rotate(start_day).reverse()
    end
  end
end

Liquid::Template.register_filter(Jekyll::DateUtils)
