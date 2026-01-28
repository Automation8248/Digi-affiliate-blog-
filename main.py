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
    # Remove markdown formatting characters
    text = text.replace('**', '').replace('*', '').replace('##', '').replace('#', '')
    # Remove "Title:" prefix if AI adds it
    text = re.sub(r'^Title:\s*', '', text, flags=re.IGNORECASE)
    return text.strip()

def get_smart_labels(product):
    # SEO Optimized Labels (Mix of Niche + Product Name + Generic)
    niche_keywords = product.get('niche', 'Health').split('&')
    clean_niche = [w.strip() for w in niche_keywords]
    
    base_labels = ["Health Tips", "Wellness Review", "Best Supplements"]
    product_label = [product['product_name']]
    
    # Combine and Select 4-5 Unique Labels
    all_labels = list(set(product_label + clean_niche + base_labels))
    return all_labels[:5]

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

# --- 3. AI CONTENT GENERATION (HOOK TITLES) ---

def generate_content(product):
    print(f"✍️ Writing article for: {product['product_name']}...")
    
    system_prompt = """
    You are a professional Click-Through Rate (CTR) Expert and Health Copywriter.
    
    TASK:
    1. Create a viral, high-converting "Hook Title" (No product name first, focus on benefit/curiosity).
       Example: "How to Reset Your Metabolism in 5 Days" (Not "Sumatra Slim Belly Tonic Review").
    2. Write a 1000+ word blog post in HTML format (<p>, <h2>, <ul>, <li>).
    
    STRICT OUTPUT FORMAT:
    Title: [Insert Hook Title Here]
    |||
    [Insert Body Content Here]
    """
    
    user_prompt = f"Write a review for '{product['product_name']}' in the niche '{product['niche']}'."

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
        
        # Split Title and Body using the separator |||
        if "|||" in cleaned_text:
            parts = cleaned_text.split("|||")
            title = parts[0].replace("Title:", "").strip()
            body = parts[1].strip()
        else:
            # Fallback
            lines = cleaned_text.split('\n')
            title = lines[0].replace("Title:", "").strip()
            body = "\n".join(lines[1:])
            
        # Ensure Title is clean
        title = title.replace('"', '').replace('*', '')
        
        # Break body into paragraphs
        paragraphs = [p for p in body.split('\n\n') if len(p) > 20]
        
        return title, paragraphs
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return f"Review: {product['product_name']}", ["Content generation failed."]

# --- 4. IMAGE & BUTTON INJECTION (AMAZON STYLE) ---

def create_promo_block(image_url, affiliate_link):
    # Amazon Style Button (Orange/Yellow Gradient)
    btn_style = """
        background: linear-gradient(to bottom, #f8c147 0%, #f7dfa5 100%);
        background-color: #f0c14b;
        border: 1px solid #a88734;
        color: #111 !important;
        padding: 10px 20px;
        font-size: 16px;
        font-weight: bold;
        text-decoration: none;
        border-radius: 3px;
        display: inline-block;
        margin: 15px 0;
        cursor: pointer;
        box-shadow: 0 1px 0 rgba(255,255,255,0.4) inset;
    """
    
    img_style = "width: 100%; max-width: 600px; height: auto; border: 1px solid #eee; margin-bottom: 10px;"
    
    # Image is clickable (Linked to Affiliate)
    html = f"""
    <div style="text-align: center; margin: 30px 0;">
        <a href="{affiliate_link}" target="_blank" rel="nofollow">
            <img src="{image_url}" style="{img_style}" alt="Product Image">
        </a>
        <br>
        <a href="{affiliate_link}" target="_blank" rel="nofollow" style="{btn_style}">
            BUY NOW
        </a>
    </div>
    """
    return html

def merge_content(title, paragraphs, product):
    all_images = product.get('image_urls', [])
    if not all_images: all_images = []
    
    # Logic: Images ko shuffle (mix) kar do sequence badalne ke liye
    selected_images = list(all_images)
    if len(selected_images) < 4:
         selected_images = (selected_images * 4)[:4] # Agar kam hain to repeat karo
    
    random.shuffle(selected_images) # Random Sequence (Kabhi upar, kabhi niche)
    
    affiliate_link = product['affiliate_link']
    final_html = ""
    
    # 1. Add H1 Title inside Body (Same as Blog Title)
    final_html += f"<h1 style='text-align: center; color: #2c3e50;'>{title}</h1>"
    
    # 2. Add First Paragraph
    if paragraphs:
        final_html += f"<p>{paragraphs[0]}</p>"
        remaining_paras = paragraphs[1:]
    else:
        remaining_paras = []
        
    # 3. Add First Image & Button immediately after 1st Paragraph
    if selected_images:
        final_html += create_promo_block(selected_images.pop(0), affiliate_link)
        
    # 4. Mix remaining images in the rest of the text
    if selected_images and remaining_paras:
        # Calculate gap to distribute images evenly
        gap = max(2, len(remaining_paras) // (len(selected_images) + 1))
        idx = 0
        
        for img in selected_images:
            for _ in range(gap):
                if idx < len(remaining_paras):
                    final_html += f"<p>{remaining_paras[idx]}</p>"
                    idx += 1
            final_html += create_promo_block(img, affiliate_link)
            
        # Add remaining text
        while idx < len(remaining_paras):
            final_html += f"<p>{remaining_paras[idx]}</p>"
            idx += 1
    else:
        for p in remaining_paras: final_html += f"<p>{p}</p>"
        
    return final_html

# --- 5. PUBLISH TO BLOGGER ---

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
        
        # Wrap content in a professional div
        final_styled_body = f"""
        <div style="font-family: Verdana, sans-serif; font-size: 16px; line-height: 1.6; color: #333; background-color: #fff; padding: 10px;">
            {content_html}
            <br><hr>
            <p style="font-size: 12px; color: #666; text-align: center; margin-top: 20px;">
                <i>This article contains affiliate links. We may earn a commission if you buy through our links.</i>
            </p>
        </div>
        """
        
        body = {
            "kind": "blogger#post",
            "title": title, # Clean Hook Title
            "content": final_styled_body,
            "labels": labels 
        }
        
        posts = service.posts()
        result = posts.insert(blogId=BLOGGER_ID, body=body).execute()
        print(f"✅ SUCCESS! Published: '{title}'")
        print(f"🔗 URL: {result['url']}")
        
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
        
        # Generate Content (Returns Title and Paragraphs separately)
        title_text, paras = generate_content(product_data)
        
        if not paras:
            print("❌ Error: No content generated.")
            exit()
            
        # Merge Content (Adds Images, Buttons, and Title inside body)
        final_blog_post = merge_content(title_text, paras, product_data)
        
        # Publish
        post_to_blogger(title_text, final_blog_post, seo_labels)
        update_history(selected_file)
        
    except Exception as e:
        print(f"❌ Main Loop Error: {e}")
