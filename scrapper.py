from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import time
import json

class OliveYoungManualScraper:
    def __init__(self):
        self.options = Options()
        # Keep browser visible for manual interaction
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        self.driver = webdriver.Chrome(options=self.options)
        self.wait = WebDriverWait(self.driver, 10)
        self.base_url = "https://global.oliveyoung.com"
    
    def open_website_for_manual_navigation(self):
        """
        Open the website and wait for user to manually navigate to foundations
        """
        print("Opening Olive Young website...")
        self.driver.get(self.base_url)
        
        print("\n" + "="*60)
        print("MANUAL NAVIGATION REQUIRED:")
        print("1. Handle any popups (region selection, etc.)")
        print("2. Navigate to: Makeup → Foundation")
        print("3. Set any filters you want (brand, price range, etc.)")
        print("4. Make sure you're on the foundation products page")
        print("5. Press ENTER in this terminal when ready to start scraping...")
        print("="*60 + "\n")
        
        # Wait for user confirmation
        input("Press ENTER when you've navigated to the foundation page and are ready to scrape...")
        
        return True
    
    def scrape_current_page(self):
        """
        Scrape products from whatever page is currently loaded
        """
        products = []
        
        print("Analyzing current page structure...")
        
        # Get page source
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        
        # Use the exact selectors from the inspection
        # Main container: ul.categoryProductList.unit-list
        # Individual products: li.prdt-unit
        product_containers = soup.select('ul.categoryProductList.unit-list li.prdt-unit')
        
        if not product_containers:
            # Fallback selectors based on the inspection
            product_containers = soup.select('.prdt-unit') or soup.select('.product-unit-wrap')
        
        if product_containers:
            print(f"✓ Found {len(product_containers)} products using Olive Young structure")
        else:
            print("❌ No product containers found with expected selectors")
            # Debug: show actual structure
            unit_list = soup.select('ul.categoryProductList.unit-list')
            if unit_list:
                print(f"Found categoryProductList container, but no prdt-unit items")
                children = unit_list[0].find_all('li', recursive=False)
                print(f"Direct children: {len(children)}")
                for child in children[:3]:
                    print(f"  - {child.get('class', 'no-class')}")
            return []
        
        # Extract data from each product
        for i, container in enumerate(product_containers):
            if i >= 50:  # Limit for safety
                break
                
            product_data = self.extract_product_info(container)
            if product_data and product_data.get('name'):
                products.append(product_data)
        
        print(f"✓ Successfully extracted {len(products)} products from current page")
        return products
    
    def extract_product_info(self, container):
        """
        Extract product information from a li.prdt-unit container
        """
        try:
            product = {}
            
            # Based on the HTML structure visible in inspection:
            
            # Product name - look in unit-desc area
            name_element = (
                container.select_one('.unit-desc .unit-btn') or
                container.select_one('.unit-desc a') or
                container.select_one('[class*="name"]') or
                container.select_one('.unit-desc')
            )
            if name_element:
                product['name'] = name_element.get_text(strip=True)
            
            # Brand - often in the name or separate element
            brand_element = container.select_one('[class*="brand"]')
            product['brand'] = brand_element.get_text(strip=True) if brand_element else None
            
            # Price - look for price elements
            price_element = (
                container.select_one('[class*="price"]') or
                container.select_one('.unit-price') or
                container.select_one('[class*="cost"]')
            )
            product['price'] = price_element.get_text(strip=True) if price_element else None
            
            # Original price (discount scenarios)
            original_price_element = (
                container.select_one('[class*="original"]') or
                container.select_one('[class*="regular"]') or
                container.select_one('[class*="before"]')
            )
            product['original_price'] = original_price_element.get_text(strip=True) if original_price_element else None
            
            # Rating/Reviews
            rating_element = (
                container.select_one('[class*="rating"]') or
                container.select_one('[class*="star"]') or
                container.select_one('[class*="score"]')
            )
            product['rating'] = rating_element.get_text(strip=True) if rating_element else None
            
            # Review count
            review_element = container.select_one('[class*="review"]')
            product['review_count'] = review_element.get_text(strip=True) if review_element else None
            
            # Product URL - from unit-thumb or unit-desc links
            link_element = (
                container.select_one('.unit-thumb a') or
                container.select_one('.unit-desc a') or
                container.select_one('a[href*="product"]')
            )
            if link_element:
                href = link_element.get('href')
                if href:
                    if href.startswith('http'):
                        product['url'] = href
                    elif href.startswith('/'):
                        product['url'] = f"{self.base_url}{href}"
                    else:
                        product['url'] = f"{self.base_url}/{href}"
            
            # Image URL - from unit-thumb area
            img_element = container.select_one('.unit-thumb img') or container.select_one('img')
            if img_element:
                product['image_url'] = (
                    img_element.get('src') or 
                    img_element.get('data-src') or 
                    img_element.get('data-lazy-src')
                )
            
            # Additional fields that might be available
            
            # Discount percentage
            discount_element = container.select_one('[class*="discount"], [class*="sale"]')
            product['discount'] = discount_element.get_text(strip=True) if discount_element else None
            
            # Stock status
            stock_element = container.select_one('[class*="stock"], [class*="available"]')
            product['stock_status'] = stock_element.get_text(strip=True) if stock_element else "Available"
            
            # Product ID (from the inspection, there might be hidden inputs with product IDs)
            product_id_input = container.select_one('input[name="prdtNo"]')
            if product_id_input:
                product['product_id'] = product_id_input.get('value')
            
            return product if product.get('name') else None
            
        except Exception as e:
            print(f"Error extracting product: {e}")
            return None
    
    def get_text_by_selectors(self, container, selectors):
        """Helper to try multiple CSS selectors"""
        for selector in selectors:
            element = container.select_one(selector)
            if element and element.get_text(strip=True):
                return element.get_text(strip=True)
        return None
    
    def scrape_multiple_pages(self, max_pages=5):
        """
        Scrape multiple pages with manual navigation
        """
        all_products = []
        
        for page_num in range(max_pages):
            print(f"\n{'='*50}")
            print(f"SCRAPING PAGE {page_num + 1}")
            print(f"{'='*50}")
            
            # Scrape current page
            products = self.scrape_current_page()
            all_products.extend(products)
            
            if not products:
                print("No products found on this page")
                break
            
            # Ask user about next page
            if page_num < max_pages - 1:
                print(f"\nFound {len(products)} products on page {page_num + 1}")
                print(f"Total so far: {len(all_products)} products")
                
                user_input = input("\nContinue to next page? (y/n/manual): ").lower()
                
                if user_input == 'n':
                    break
                elif user_input == 'manual':
                    input("Navigate to the next page manually, then press ENTER...")
                else:
                    # Try to find and click next page automatically
                    try:
                        next_selectors = [
                            "a[class*='next']", "button[class*='next']",
                            "[aria-label*='next']", "[title*='next']",
                            "a[class*='다음']", "button[class*='다음']"  # Korean for "next"
                        ]
                        
                        next_clicked = False
                        for selector in next_selectors:
                            try:
                                next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                                if next_button.is_enabled():
                                    next_button.click()
                                    time.sleep(3)
                                    next_clicked = True
                                    break
                            except:
                                continue
                        
                        if not next_clicked:
                            print("Couldn't find next page button automatically.")
                            input("Please navigate to next page manually and press ENTER...")
                    
                    except Exception as e:
                        print(f"Error navigating to next page: {e}")
                        input("Please navigate to next page manually and press ENTER...")
        
        return all_products
    
    def save_to_csv(self, products, filename='olive_young_foundations.csv'):
        """Save products to CSV"""
        if products:
            df = pd.DataFrame(products)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"\n✓ Saved {len(products)} products to {filename}")
            
            # Show summary
            print(f"\nData Summary:")
            print(f"- Total products: {len(products)}")
            print(f"- With prices: {sum(1 for p in products if p.get('price'))}")
            print(f"- With brands: {sum(1 for p in products if p.get('brand'))}")
            print(f"- With ratings: {sum(1 for p in products if p.get('rating'))}")
            
            # Show top brands
            brands = [p.get('brand') for p in products if p.get('brand')]
            if brands:
                from collections import Counter
                top_brands = Counter(brands).most_common(5)
                print(f"\nTop brands found:")
                for brand, count in top_brands:
                    print(f"  - {brand}: {count} products")
        else:
            print("No products to save")
    
    def close(self):
        """Close browser"""
        self.driver.quit()

# Main execution
if __name__ == "__main__":
    print("🔍 Olive Young Foundation Scraper")
    print("This script opens a browser for manual navigation, then auto-scrapes products")
    
    scraper = OliveYoungManualScraper()
    
    try:
        # Step 1: Manual navigation
        scraper.open_website_for_manual_navigation()
        
        # Step 2: Automatic scraping
        foundations = scraper.scrape_multiple_pages(max_pages=5)
        
        # Step 3: Save results
        if foundations:
            scraper.save_to_csv(foundations)
        else:
            print("❌ No foundation products were found")
    
    except KeyboardInterrupt:
        print("\n⚠️ Scraping interrupted by user")
    except Exception as e:
        print(f"❌ Error during scraping: {e}")
    finally:
        print("\n🔒 Closing browser...")
        scraper.close()
        print("✅ Done!")