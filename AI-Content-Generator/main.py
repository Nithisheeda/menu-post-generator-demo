import json
import os
import uuid
import csv
import io
from datetime import datetime
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session, send_file
from werkzeug.utils import secure_filename
from openai import OpenAI

# OpenAI model configuration with fallback
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET', 'dev-secret-key')

# Configure file uploads
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Create upload directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize OpenAI client with validation
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

@app.route('/')
def index():
    """Main page with the menu input form"""
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_posts():
    """Generate social media posts from menu input"""
    try:
        # Get form data
        menu_text = request.form.get('menu_text', '').strip()
        num_posts = int(request.form.get('num_posts', 3))
        language = request.form.get('language', 'english')
        
        # Validate input
        if not menu_text:
            flash('Please enter your restaurant menu text.', 'error')
            return redirect(url_for('index'))
        
        if num_posts < 1 or num_posts > 10:
            flash('Number of posts must be between 1 and 10.', 'error')
            return redirect(url_for('index'))
        
        # Get A/B test mode preference
        ab_test_mode = request.form.get('ab_test_mode') == 'on'
        
        # Generate posts using OpenAI (optimized single call)
        posts = generate_multiple_social_media_posts(menu_text, num_posts, language, ab_test_mode)
        
        if not posts:
            flash('Failed to generate posts. Please try again.', 'error')
            return redirect(url_for('index'))
        
        # Merge uploaded images into posts for export
        uploaded_images = session.get('uploaded_images', {})
        for i, post in enumerate(posts):
            if str(i) in uploaded_images:
                post['image_url'] = f'/uploaded_image/{uploaded_images[str(i)]}'
        
        # Store posts in session for potential exports
        session['current_posts'] = posts
        session['current_menu_text'] = menu_text
        session['current_language'] = language
        
        return render_template('results.html', posts=posts, menu_text=menu_text, language=language, ab_test_mode=ab_test_mode)
    
    except ValueError:
        flash('Invalid number of posts. Please enter a valid number.', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        print(f"Error generating posts: {e}")
        flash('Sorry, we encountered an issue generating your posts. Please try again.', 'error')
        return redirect(url_for('index'))

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_image/<int:post_index>', methods=['POST'])
def upload_image(post_index):
    """Upload and replace image for a specific post"""
    if 'image' not in request.files:
        return jsonify({'error': 'No file selected'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and file.filename and allowed_file(file.filename):
        # Generate unique filename
        filename = str(uuid.uuid4()) + '.' + file.filename.rsplit('.', 1)[1].lower()
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Store in session for this post
        if 'uploaded_images' not in session:
            session['uploaded_images'] = {}
        session['uploaded_images'][str(post_index)] = filename
        
        # Also update the current posts if available
        if 'current_posts' in session and len(session['current_posts']) > post_index:
            session['current_posts'][post_index]['image_url'] = f'/uploaded_image/{filename}'
        
        session.modified = True
        
        return jsonify({'success': True, 'filename': filename, 'url': f'/uploaded_image/{filename}'})
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/uploaded_image/<filename>')
def uploaded_image(filename):
    """Serve uploaded images"""
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/export_posts')
def export_posts():
    """Export all posts as JSON or CSV"""
    format_type = request.args.get('format', 'json')
    posts = session.get('current_posts', [])
    
    if not posts:
        flash('No posts to export. Please generate posts first.', 'error')
        return redirect(url_for('index'))
    
    if format_type == 'csv':
        # Create CSV export
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        headers = ['Post_Index', 'Caption_EN', 'Caption_DE', 'Hashtags', 'Image_URL', 'Image_Prompt']
        writer.writerow(headers)
        
        # Write data
        for i, post in enumerate(posts):
            writer.writerow([
                i + 1,
                post.get('caption', ''),
                post.get('caption_german', ''),
                ', '.join(post.get('hashtags', [])),
                post.get('image_url', ''),
                post.get('image_prompt', '')
            ])
        
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name='social_media_posts.csv'
        )
    else:
        # JSON export
        export_data = {
            'menu_text': session.get('current_menu_text', ''),
            'language': session.get('current_language', 'english'),
            'generated_at': datetime.now().isoformat(),
            'posts': posts
        }
        
        return send_file(
            io.BytesIO(json.dumps(export_data, indent=2).encode()),
            mimetype='application/json',
            as_attachment=True,
            download_name='social_media_posts.json'
        )

def generate_multiple_social_media_posts(menu_text, num_posts, language='english', ab_test_mode=False):
    """Generate multiple Instagram-style social media posts in a single API call"""
    try:
        # Determine language instructions
        if language == 'german':
            lang_instruction = "Create posts in German language."
        elif language == 'both':
            lang_instruction = "Create posts in English first, then provide German translations."
        else:
            lang_instruction = "Create posts in English."

        # A/B test variants instruction
        variant_instruction = ""
        actual_posts_needed = num_posts
        if ab_test_mode:
            variant_instruction = " For each post concept, create TWO variants - one casual tone and one professional tone. This will result in pairs of posts for A/B testing."
            actual_posts_needed = num_posts * 2  # Double the posts for A/B variants
        
        prompt = f"""
        Based on the following restaurant menu, create {actual_posts_needed} engaging Instagram-style social media posts. 
        Each post should be appealing, include relevant hashtags, and encourage people to visit the restaurant.
        Make each post unique and focus on different menu items or aspects of the restaurant.
        {lang_instruction}{variant_instruction}
        
        HASHTAG REQUIREMENTS:
        - Include 1-2 local Berlin hashtags based on menu content (e.g., #Mitte for central location, #Kreuzberg for trendy area, #BerlinEats, #BerlinFoodie)
        - Limit total hashtags to exactly 3 per post
        - Make hashtags relevant to the specific dish and Berlin location
        
        IMAGE PROMPT REQUIREMENTS:
        - Style: "Photorealistic casual food photo, smartphone-style, natural lighting in Berlin bistro—no studio gloss"
        - Make each image prompt specific to the actual menu item mentioned
        
        Menu: {menu_text}
        
        Please respond with a JSON object in this format:
        {{
            "posts": [
                {{
                    "caption": "The main post text with emojis and engaging content",
                    "caption_german": "German translation (only if language is 'both')",
                    "hashtags": ["hashtag1", "hashtag2", "BerlinHashtag"],
                    "image_prompt": "Photorealistic casual food photo, smartphone-style, natural lighting in Berlin bistro—no studio gloss, showing [specific dish from menu]",
                    "variant": "casual/professional (only if ab_test_mode is true)"
                }},
                {{
                    "caption": "Another unique post about different menu items",
                    "caption_german": "German translation (only if language is 'both')",
                    "hashtags": ["hashtag1", "hashtag2", "BerlinHashtag"],
                    "image_prompt": "Photorealistic casual food photo, smartphone-style, natural lighting in Berlin bistro—no studio gloss, showing [specific dish from menu]",
                    "variant": "casual/professional (only if ab_test_mode is true)"
                }}
            ]
        }}
        
        Generate exactly {actual_posts_needed} posts in the array. Always include exactly 3 hashtags with Berlin location tags.
        """
        
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a social media expert specializing in restaurant marketing. Create engaging, authentic Instagram posts that highlight menu items and encourage restaurant visits. Always respond with valid JSON in the exact format requested."
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            timeout=30,
            max_tokens=2000
        )
        
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Empty response from OpenAI")
        
        result = json.loads(content)
        posts_data = result.get("posts", [])
        
        # Validate and clean the posts
        posts = []
        for i, post_data in enumerate(posts_data):
            if isinstance(post_data, dict) and "caption" in post_data:
                # Ensure hashtags are strings and normalize them
                hashtags = post_data.get("hashtags", [])
                if isinstance(hashtags, list):
                    # Normalize hashtags: remove # prefix, limit to 3, ensure Berlin tags
                    normalized_tags = []
                    for tag in hashtags:
                        if tag:
                            clean_tag = str(tag).strip().lstrip('#')
                            if clean_tag:
                                normalized_tags.append(clean_tag)
                    
                    # Ensure we have Berlin-specific hashtags (case-insensitive)
                    berlin_tags = ['berlineats', 'mitte', 'kreuzberg', 'berlinfoodie', 'berlin']
                    has_berlin_tag = any(tag.lower() in berlin_tags for tag in normalized_tags)
                    
                    # If no Berlin tag, replace last tag with a Berlin tag or add one
                    if not has_berlin_tag:
                        if len(normalized_tags) >= 3:
                            # Replace the last tag with a Berlin tag
                            normalized_tags[-1] = 'BerlinEats'
                        else:
                            # Add a Berlin tag
                            normalized_tags.append('BerlinEats')
                    
                    # Ensure exactly 3 hashtags
                    hashtags = normalized_tags[:3]
                    while len(hashtags) < 3:
                        if 'foodie' not in [tag.lower() for tag in hashtags]:
                            hashtags.append('foodie')
                        elif 'delicious' not in [tag.lower() for tag in hashtags]:
                            hashtags.append('delicious')
                        else:
                            hashtags.append('restaurant')
                else:
                    hashtags = ['BerlinEats', 'foodie', 'delicious']
                
                # Generate image using DALL-E
                image_url = None
                image_prompt = post_data.get("image_prompt", "")
                if image_prompt:
                    try:
                        image_url = generate_food_image(image_prompt)
                    except Exception as e:
                        print(f"Error generating image for post {i+1}: {e}")
                
                post = {
                    "caption": str(post_data.get("caption", "")),
                    "hashtags": hashtags,
                    "image_url": image_url,
                    "image_prompt": image_prompt,
                    "variant": post_data.get("variant", ""),
                    "post_id": str(uuid.uuid4())  # Unique ID for A/B tracking
                }
                
                # Add German translation if available
                if language == 'both' and post_data.get("caption_german"):
                    post["caption_german"] = str(post_data.get("caption_german", ""))
                
                posts.append(post)
        
        # Ensure we have the requested number of posts (pad or slice as needed)
        while len(posts) < actual_posts_needed:
            default_prompt = "Professional food photography of restaurant dish, appetizing and well-plated"
            default_image = None
            try:
                default_image = generate_food_image(default_prompt)
            except Exception:
                pass
            
            fallback_post = {
                "caption": "Check out our amazing menu! Come visit us today! 🍴✨",
                "hashtags": ["BerlinEats", "foodie", "Mitte"],
                "image_url": default_image,
                "image_prompt": default_prompt,
                "variant": "casual",
                "post_id": str(uuid.uuid4())
            }
            
            if language == 'both':
                fallback_post["caption_german"] = "Schaut euch unser fantastisches Menü an! Besucht uns heute! 🍴✨"
            
            posts.append(fallback_post)
        
        return posts[:actual_posts_needed]
    
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        raise ValueError("Invalid response format from AI service")
    except Exception as e:
        print(f"Error generating posts: {e}")
        raise ValueError("Failed to generate social media posts")

def generate_food_image(prompt):
    """Generate food image using DALL-E 3"""
    try:
        # Reference from python_openai blueprint integration
        response = openai_client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024",
        )
        
        if response and response.data and len(response.data) > 0:
            return response.data[0].url
        else:
            raise ValueError("No image data returned from DALL-E")
            
    except Exception as e:
        print(f"Error generating image: {e}")
        raise e

if __name__ == '__main__':
    # Use 0.0.0.0 to allow external connections in Replit
    app.run(debug=True, host='0.0.0.0', port=5000)
