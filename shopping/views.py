# shopping/views.py
from django.shortcuts import render
from . import utils  # Import the functions from utils.py
import time

def index(request):
    context = {}
    if request.method == "POST":
        # Retrieve form data; provide defaults if not entered.
        query = request.POST.get("query", "").strip()
        min_price = request.POST.get("min_price", "0").strip()
        max_price = request.POST.get("max_price", "10000000").strip()  # A very high number as unlimited

        # Validate the search query
        if not query:
            context["error"] = "Please enter a search query."
            return render(request, "shopping/index.html", context)

        # Convert prices to float (with error checking)
        try:
            min_price = float(min_price) if min_price else 0.0
            max_price = float(max_price) if max_price else 1e8
        except ValueError:
            context["error"] = "Please enter valid numeric values for prices."
            return render(request, "shopping/index.html", context)

        # --- Step 1: Search and Filter by Price ---
        products = utils.search_amazon(query, min_price, max_price)
        if not products:
            context["error"] = "No products found within the specified price range."
            return render(request, "shopping/index.html", context)

        # --- Step 2: Select Top 10 by Star Rating (from search results) ---
        products.sort(key=lambda x: x[0], reverse=True)
        top_10_by_rating = products[:10]

        # --- Step 3: Compute Composite Satisfaction Scores for these Top 10 ---
        product_details = []
        for rating, url, price in top_10_by_rating:
            result = utils.compute_composite_satisfaction(url, fallback_rating=rating)
            if result is None:
                print(f"Skipping URL due to errors: {url}")
                continue
            composite_score, star_rating, cust_rev_score = result
            product_details.append({
                "URL": url,
                "Price": price,
                "Star_Rating": star_rating,
                "Customer_Review_Score": cust_rev_score,
                "Composite_Satisfaction_Score": composite_score
            })
            # Pause briefly to avoid overwhelming the server
            time.sleep(1)
        
        # --- Step 4: Select Top 5 based on Composite Satisfaction Score and add Rank ---
        product_details.sort(key=lambda x: x["Composite_Satisfaction_Score"], reverse=True)
        top_5_products = product_details[:5]
        for idx, product in enumerate(top_5_products, start=1):
            product["Rank"] = idx

        context["products"] = top_5_products

    return render(request, "shopping/index.html", context)
