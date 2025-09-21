import requests
from bs4 import BeautifulSoup
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from langdetect import detect, DetectorFactory
import time

# Set seed for consistent language detection
DetectorFactory.seed = 0

# Uncomment if you haven't downloaded the VADER lexicon:
# nltk.download('vader_lexicon')

def compute_composite_satisfaction(url, fallback_rating=0.0):
    """
    Fetches the product page, extracts the overall star rating and customer reviews,
    performs sentiment analysis on the reviews, and computes:
      - customer_review_score = (2.5 * average_compound + 2.5)
      - composite_score = (0.7 * star_rating) + 0.3 * customer_review_score

    If the product page faces a 503 error or fails to return valid review data,
    the function retries once. If the second attempt also fails or no reviews are processed,
    it returns None so that the URL can be skipped.
    """
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/98.0.4758.102 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.google.com/"
    }
    session.headers.update(headers)
    
    # First attempt to fetch the product page
    try:
        response = session.get(url, timeout=10)
    except Exception as e:
        print(f"Error fetching product URL {url}: {e}")
        # Retry after a short delay
        time.sleep(2)
        try:
            response = session.get(url, timeout=10)
        except Exception as e:
            print(f"Second attempt failed for URL {url}: {e}")
            return None

    # If we get a 503, retry once after a delay
    if response.status_code == 503:
        print(f"Received 503 error for URL: {url}; retrying after delay...")
        time.sleep(2)
        response = session.get(url, timeout=10)
    
    if response.status_code != 200:
        print(f"Error fetching page (Status {response.status_code}) for URL: {url}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')

    # Extract overall rating with fallback
    overall_rating_elem = soup.find("span", {"data-hook": "rating-out-of-text"})
    if not overall_rating_elem:
        overall_rating_elem = soup.find("span", class_="a-icon-alt")
    overall_rating_text = overall_rating_elem.get_text(strip=True) if overall_rating_elem else ""
    try:
        product_page_star_rating = float(overall_rating_text.split()[0])
    except Exception:
        product_page_star_rating = 0.0

    # Use fallback rating if extraction fails
    if product_page_star_rating == 0.0 and fallback_rating > 0:
        product_page_star_rating = fallback_rating

    # Extract customer reviews
    review_divs = soup.find_all("div", {"class": "review-text-content"})
    reviews_list = []
    for review in review_divs:
        review_text = review.get_text(strip=True)
        try:
            if detect(review_text) != 'en':
                continue
        except Exception:
            pass
        reviews_list.append(review_text)

    # If no reviews are found, skip this product
    if not reviews_list:
        print(f"No reviews found for URL: {url}; skipping this product.")
        return None

    # Perform sentiment analysis on reviews
    analyzer = SentimentIntensityAnalyzer()
    total_compound = 0.0
    for review in reviews_list:
        sentiment = analyzer.polarity_scores(review)
        total_compound += sentiment['compound']
    count_reviews = len(reviews_list)
    average_compound = total_compound / count_reviews

    customer_review_score = (2.5 * average_compound + 2.5)
    composite_satisfaction_score = (0.7 * product_page_star_rating) + (0.3 * customer_review_score)
    
    return composite_satisfaction_score, product_page_star_rating, customer_review_score


def search_amazon(query, min_price, max_price):
    """
    Searches Amazon India for the given query and returns a list of tuples:
      (star_rating, product URL, price)
    for products within the given price range.
    This version uses enhanced headers and a persistent session to reduce 503 errors.
    """
    # Create a session and update headers
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/98.0.4758.102 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.google.com/"
    }
    session.headers.update(headers)
    
    # Construct search URL (adding common query parameters)
    search_url = f"https://www.amazon.in/s?k={query}&ref=nb_sb_noss"
    
    # Attempt to fetch the search results
    try:
        response = session.get(search_url, timeout=10)
    except Exception as e:
        print("Error during GET request:", e)
        return []
    
    # If blocked (503), wait and retry once
    if response.status_code == 503:
        print("Received 503 error; retrying after a short delay...")
        time.sleep(2)
        response = session.get(search_url, timeout=10)
    
    if response.status_code != 200:
        print("Error fetching search results. Status:", response.status_code)
        return []
    
    soup = BeautifulSoup(response.content, 'html.parser')
    product_items = soup.find_all('div', {'data-component-type': 's-search-result'})
    print("Found", len(product_items), "product items for query:", query)
    products = []
    
    for item in product_items:
        # Extract product URL
        link_tag = item.find('a', {'class': 'a-link-normal'})
        if not link_tag or not link_tag.get('href'):
            continue
        product_url = "https://www.amazon.in" + link_tag.get('href')
        
        # Extract star rating from the search result
        rating_value = 0.0
        rating_span = item.find('span', {'class': 'a-icon-alt'})
        if rating_span:
            rating_text = rating_span.get_text().strip()  # e.g., "4.5 out of 5 stars"
            try:
                rating_value = float(rating_text.split(" ")[0])
            except Exception:
                rating_value = 0.0

        # Extract price using primary strategy
        price_value = None
        price_container = item.find("span", class_="a-price")
        if price_container:
            whole = price_container.find("span", class_="a-price-whole")
            fraction = price_container.find("span", class_="a-price-fraction")
            if whole:
                price_text = whole.get_text(strip=True)
                if fraction:
                    price_text = price_text + "." + fraction.get_text(strip=True)
                try:
                    price_value = float(price_text.replace('₹','').replace(',', '').strip())
                except Exception:
                    price_value = None

        # Fallback: Look for a price in an offscreen span
        if price_value is None:
            price_elem = item.find("span", class_="a-offscreen")
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                try:
                    price_value = float(price_text.replace('₹','').replace(',', '').strip())
                except Exception:
                    price_value = None

        if price_value is None:
            print("Skipping product (missing price):", product_url)
            continue

        # Log details before filtering
        print("Product found:", product_url, "Price:", price_value, "Rating:", rating_value)
        
        # Filter based on the price range
        if not (min_price <= price_value <= max_price):
            print("Skipping due to price filter:", price_value, "not in", min_price, "-", max_price)
            continue
        
        products.append((rating_value, product_url, price_value))
    
    print("Total products returned:", len(products))
    return products
