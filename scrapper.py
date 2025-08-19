from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import time
import json

MAIN_FILE_NAME = "olive_young_lipstick.csv"

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
    
    def extract_product_info(self, container):
        """
        Extract product information from a li.prdt-unit container
        """
        try:
            product = {}
            
            # Product name
            name_element = (
                container.select_one('.unit-desc .unit-btn') or
                container.select_one('.unit-desc a') or
                container.select_one('[class*="name"]') or
                container.select_one('.unit-desc')
            )
            if name_element:
                product['name'] = name_element.get_text(strip=True)
            
            # Brand
            brand_element = container.select_one('[class*="brand"]')
            product['brand'] = brand_element.get_text(strip=True) if brand_element else None
            
            # Price
            price_element = (
                container.select_one('[class*="price"]') or
                container.select_one('.unit-price') or
                container.select_one('[class*="cost"]')
            )
            product['price'] = price_element.get_text(strip=True) if price_element else None
            
            # Original price
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
            
            review_element = container.select_one('[class*="review"]')
            product['review_count'] = review_element.get_text(strip=True) if review_element else None
            
            # Product URL
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
            
            # Image URL
            img_element = container.select_one('.unit-thumb img') or container.select_one('img')
            if img_element:
                product['image_url'] = (
                    img_element.get('src') or 
                    img_element.get('data-src') or 
                    img_element.get('data-lazy-src')
                )
            
            # Discount
            discount_element = container.select_one('[class*="discount"], [class*="sale"]')
            product['discount'] = discount_element.get_text(strip=True) if discount_element else None
            
            # Stock status
            stock_element = container.select_one('[class*="stock"], [class*="available"]')
            product['stock_status'] = stock_element.get_text(strip=True) if stock_element else "Available"
            
            # Product ID
            product_id_input = container.select_one('input[name="prdtNo"]')
            if product_id_input:
                product['product_id'] = product_id_input.get('value')
            
            return product if product.get('name') else None
            
        except Exception as e:
            print(f"Error extracting product: {e}")
            return None
    
    def scrape_product_variants(self, product_url):
        """
        Go to the product detail page and extract all foundation shades.
        Returns a list of dictionaries with shade info.
        """
        try:
            self.driver.get(product_url)
            # Wait for variants to load
            self.wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'li.has-price')))
            time.sleep(1)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            variants = []

            variant_containers = soup.select('li.has-price')
            if not variant_containers:
                print(f"❌ No variants found for {product_url}")
                return []

            for vc in variant_containers:
                shade_name_elem = vc.select_one('p.list-thumb-info.line-ellipsis2')
                if shade_name_elem:
                    shade_name = shade_name_elem.get_text(strip=True)
                    img_elem = vc.select_one('img')
                    img_url = img_elem.get('src') if img_elem else None
                    variants.append({
                        'shade_name': shade_name,
                        'shade_image': img_url
                    })

            print(f"✓ Found {len(variants)} variants for {product_url}")
            return variants

        except Exception as e:
            print(f"Error scraping product variants for {product_url}: {e}")
            return []

    def scrape_current_page(self):
        """
        Scrape products from the current page and their variants
        """
        products = []
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        product_containers = soup.select('ul.categoryProductList.unit-list li.prdt-unit')
        if not product_containers:
            product_containers = soup.select('.prdt-unit') or soup.select('.product-unit-wrap')

        if not product_containers:
            print("❌ No product containers found with expected selectors")
            return []

        print(f"✓ Found {len(product_containers)} products on this page")

        for i, container in enumerate(product_containers):
            if i >= 50:
                break
            product_data = self.extract_product_info(container)
            if product_data and product_data.get('url'):
                # Scrape variants for this product
                product_data['variants'] = self.scrape_product_variants(product_data['url'])
            products.append(product_data)

        print(f"✓ Successfully extracted {len(products)} products from current page")
        return products
    
    def scrape_multiple_pages(self, max_pages=5):
        all_products = []
        
        for page_num in range(max_pages):
            print(f"\n{'='*50}")
            print(f"SCRAPING PAGE {page_num + 1}")
            print(f"{'='*50}")
            
            products = self.scrape_current_page()
            all_products.extend(products)
            
            if not products:
                print("No products found on this page")
                break
            
            if page_num < max_pages - 1:
                print(f"\nFound {len(products)} products on page {page_num + 1}")
                print(f"Total so far: {len(all_products)} products")
                
                user_input = input("\nContinue to next page? (y/n/manual): ").lower()
                
                if user_input == 'n':
                    break
                elif user_input == 'manual':
                    input("Navigate to the next page manually, then press ENTER...")
                else:
                    try:
                        next_selectors = [
                            "a[class*='next']", "button[class*='next']",
                            "[aria-label*='next']", "[title*='next']",
                            "a[class*='다음']", "button[class*='다음']"
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
        """Save products to CSV, including variants"""
        if products:
            for p in products:
                p['variants'] = json.dumps(p.get('variants', []), ensure_ascii=False)
            df = pd.DataFrame(products)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"\n✓ Saved {len(products)} products to {filename}")
        else:
            print("No products to save")
    
    def close(self):
        self.driver.quit()

# --- Main execution ---
if __name__ == "__main__":
    print("🔍 Olive Young Foundation Scraper")
    
    scraper = OliveYoungManualScraper()
    
    try:
        scraper.open_website_for_manual_navigation()
        foundations = scraper.scrape_multiple_pages(max_pages=5)
        if foundations:
            scraper.save_to_csv(foundations,MAIN_FILE_NAME)
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
