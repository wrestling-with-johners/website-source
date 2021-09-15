from seleniumwire import webdriver

def get_auth():
  # Setup headless Firefox web driver.
  fireFoxOptions = webdriver.FirefoxOptions()
  fireFoxOptions.headless = True

  with webdriver.Firefox(options = fireFoxOptions) as driver:
    # Reduce the scope of tracked requests to those to the API for podcasts. This way we can reasonably expect
    # the first request in the stack to be the one we want; bearing the auth token.
    driver.scopes = ['https://amp-api.podcasts.apple.com/v1/*']
    driver.get('https://podcasts.apple.com/us/podcast/wrestling-with-johners-podcast/id1442108418')

    # Wait for a request which contains the authorisation token.
    request = driver.wait_for_request('https://amp-api.podcasts.apple.com/', 90)

    return request.headers.get('Authorization')

def main():
  print(f'Auth: {get_auth()}')

if __name__ == "__main__":
    main()