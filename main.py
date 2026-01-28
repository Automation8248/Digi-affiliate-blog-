import os
import json
import random
import re
import time
from datetime import datetime
from openai import OpenAI
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

# --- CONFIGURATION ---
GITHUB_TOKEN = os.environ.get("GH_MARKETPLACE_TOKEN") 

# 👉 HARDCODED BLOG ID (Error Free)
BLOGGER_ID = "8697171360337652733"

# Authentication Variables
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN")

# DeepSeek Client
client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=GITHUB_TOKEN,
)

# --- 1. CLEANER & HELPER FUNCTIONS ---

def clean_text_for_blogger(text):
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = text.replace('**', '').replace('*', '').replace('##', '').replace('#', '')
    text = text.replace('Title:', '').strip()
    return text

def get_smart_labels(product):
    return ["Health", "Review", "Wellness", product['product_name']]

# --- 2. MEMORY & PRODUCT SELECTION ---

def get_eligible_product():
    if os.path.exists('history.json'):
        with open('history.json', 'r') as f:
            try: history = json.load(f)
            except: history = {}
    else: history = {}

    all_files = [f for f in os.listdir('products') if f.endswith('.json')]
    
    if not all_files:
        print("❌ CRITICAL: No JSON files found in 'products/' folder.")
        exit()

    available_products = []
    today = datetime.now().date()
    
    for filename in all_files:
        product_name = filename.replace('.json', '')
        last_used_str = history.get(product_name)
        if last_used_str:
            last_used_date = datetime.strptime(last_used_str, "%Y-%m-%d").date()
            if (today - last_used_date).days < 5:
                continue 
        available_products.append(filename)

    if not available_products:
        print("⚠️ All products in cooldown. Picking random.")
        return random.choice(all_files)

    return random.choice(available_products)

def update_history(filename):
    product_name = filename.replace('.json', '')
    if os.path.exists('history.json'):
        with open('history.json', 'r') as f:
            try: history = json.load(f)
            except: history = {}
    else: history = {}
    history[product_name] = datetime.now().strftime("%Y-%m-%d")
    with open('history.json', 'w') as f: json.dump(history, f, indent=4)

# --- 3. AI CONTENT GENERATION ---

def generate_content(product):
    print(f"✍️ Writing article for: {product['product_name']}...")
    
    system_prompt = """
    Write a 1000+ word SEO blog post using HTML tags (<p>, <h2>, <ul>, <li>).
    Do NOT use Markdown. Do NOT use Title tags inside body.
    Structure: Intro, Problem, Solution, Ingredients, Benefits, Conclusion.
    """
    
    user_prompt = f"Write a review for '{product['product_name']}' ({product['niche']})."

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="DeepSeek-R1",
            temperature=1.0,
            max_tokens=4000 
        )
        raw_text = response.choices[0].message.content
        cleaned_text = clean_text_for_blogger(raw_text)
        
        lines = cleaned_text.split('\n')
        title = lines[0][:60] if lines else f"{product['product_name']} Review"
        body_text = "\n".join(lines[1:])
        paragraphs = [p for p in body_text.split('\n\n') if len(p) > 20]
        
        return title, paragraphs
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return f"{product['product_name']} Review", ["Content generation failed."]

# --- 4. IMAGE & BUTTON INJECTION ---

def create_promo_block(image_url, affiliate_link):
    btn_style = "background-color: #d32f2f; color: white !important; padding: 16px 25px; font-weight: bold; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; font-size: 18px; text-transform: uppercase;"
    img_style = "width: 100%; max-width: 600px; height: auto; border: 1px solid #ddd; border-radius: 8px;"
    
    html = f"""
    <div style="text-align: center; margin: 30px 0;">
        <a href="{affiliate_link}" rel="nofollow"><img src="{image_url}" style="{img_style}"></a><br>
        <a href="{affiliate_link}" rel="nofollow" style="{btn_style}">BUY NOW (OFFICIAL SITE)</a>
    </div>
    """
    return html

def merge_content(paragraphs, product):
    all_images = product.get('image_urls', [])
    if not all_images: all_images = []
    
    # Safe logic if images are missing
    if len(all_images) < 1: 
        return "".join([f"<p>{p}</p>" for p in paragraphs])

    selected_images = (all_images * 4)[:4]
    random.shuffle(selected_images)
    
    affiliate_link = product['affiliate_link']
    final_html = ""
    
    if paragraphs: final_html += f"<p>{paragraphs[0]}</p>"
    
    if selected_images:
        final_html += create_promo_block(selected_images.pop(0), affiliate_link)
    
    remaining_paras = paragraphs[1:]
    if selected_images and remaining_paras:
        gap = max(2, len(remaining_paras) // (len(selected_images) + 1))
        idx = 0
        for img in selected_images:
            for _ in range(gap):
                if idx < len(remaining_paras):
                    final_html += f"<p>{remaining_paras[idx]}</p>"
                    idx += 1
            final_html += create_promo_block(img, affiliate_link)
        while idx < len(remaining_paras):
            final_html += f"<p>{remaining_paras[idx]}</p>"
            idx += 1
    else:
        for p in remaining_paras: final_html += f"<p>{p}</p>"
        
    return final_html

# --- 5. PUBLISH TO BLOGGER (WITH HTML STYLING) ---

def post_to_blogger(title, content_html, labels):
    print(f"🔑 Authenticating... (Target Blog ID: {BLOGGER_ID})")
    
    if not CLIENT_ID or not CLIENT_SECRET or not REFRESH_TOKEN:
        print("❌ ERROR: Secrets missing (CLIENT_ID/SECRET/REFRESH_TOKEN)")
        return

    creds_info = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "token_uri": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/blogger"]
    }

    try:
        creds = Credentials.from_authorized_user_info(creds_info)
        service = build('blogger', 'v3', credentials=creds)
        
        # 👉 HERE IS THE HTML FORMAT LOGIC (UPDATED)
        # Hum pure content ko ek Professional <div> mein wrap kar rahe hain
        final_styled_body = f"""
        <div style="font-family: Arial, sans-serif; font-size: 16px; line-height: 1.6; color: #333; background-color: #fff; padding: 10px;">
            {content_html}
            <br><hr>
            <p style="font-size: 12px; color: #666; text-align: center; margin-top: 20px;">
                <i>This article contains affiliate links. We may earn a commission if you buy through our links.</i>
            </p>
        </div>
        """
        
        body = {
            "kind": "blogger#post",
            "title": title,
            "content": final_styled_body, # Styled HTML Bheja ja raha hai
            "labels": labels 
        }
        
        posts = service.posts()
        result = posts.insert(blogId=BLOGGER_ID, body=body).execute()
        print(f"✅ SUCCESS! View Post: {result['url']}")
        
    except HttpError as e:
        print(f"❌ HTTP Error: {e}")
        print(f"🔍 Reason: {e.error_details}")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

# --- MAIN ---
if __name__ == "__main__":
    try:
        selected_file = get_eligible_product()
        print(f"🚀 Processing: {selected_file}")
        
        with open(f'products/{selected_file}', 'r') as f:
            product_data = json.load(f)
            
        seo_labels = get_smart_labels(product_data)
        title_text, paras = generate_content(product_data)
        
        if not paras:
            print("❌ Error: No content generated.")
            exit()
            
        final_blog_post = merge_content(paras, product_data)
        
        # Post with HTML Styling
        post_to_blogger(title_text, final_blog_post, seo_labels)
        
        update_history(selected_file)
        
    except Exception as e:
        print(f"❌ Main Loop Error: {e}")
