import cloudinary
import cloudinary.api
import random
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import googleapiclient.discovery
import google.auth
import os
import pickle
import requests
import json # client_secret.json ko load karne ke liye

# --- Cloudinary Configuration (Using GitHub Secrets) ---
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True
)

# --- YouTube API Configuration ---
# GitHub Actions par client_secret.json file ko dynamically banayenge
CLIENT_SECRETS_FILE = "client_secret.json" 
# token.pickle file GitHub Actions runner par banegi/use hogi
TOKEN_FILE = 'token.pickle'

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

def get_authenticated_service():
    """
    YouTube API ke liye authentication handle karta hai.
    GitHub Actions environment mein refresh token ka upyog karta hai.
    """
    credentials = None
    
    # Koshish karein ki token.pickle se credentials load ho jayein
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'rb') as token:
                credentials = pickle.load(token)
            print(f"Credentials loaded from {TOKEN_FILE}.")
        except Exception as e:
            print(f"Error loading token.pickle: {e}. Attempting new authorization.")
            os.remove(TOKEN_FILE) # Corrupt file ho sakti hai, delete karein
            credentials = None

    # Agar credentials nahi hain ya invalid hain
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print("Access token expired, attempting to refresh with stored refresh token...")
            try:
                credentials.refresh(Request())
                print("Access token refreshed successfully.")
            except Exception as e:
                print(f"Error refreshing token: {e}. Full re-authentication needed.")
                credentials = None # Refresh fail hone par naya auth flow
        
        # Agar credentials abhi bhi nahi hain (ya refresh fail ho gaya)
        if not credentials:
            print("No valid credentials found or refresh token failed. Initiating authorization flow from secret...")
            
            # GOOGLE_REFRESH_TOKEN secret se refresh token use karein
            refresh_token_secret = os.environ.get("GOOGLE_REFRESH_TOKEN")
            if not refresh_token_secret:
                raise ValueError("GOOGLE_REFRESH_TOKEN GitHub Secret is missing or empty.")
            
            try:
                with open(CLIENT_SECRETS_FILE, 'r') as f:
                    client_config = json.load(f)
                
                web_config = client_config.get("web") or client_config.get("installed")
                if not web_config:
                    raise ValueError("client_secret.json must contain 'web' or 'installed' client configuration.")

                credentials = google.oauth2.credentials.Credentials(
                    token=None,  # Abhi koi access token nahi hai
                    refresh_token=refresh_token_secret,
                    token_uri=web_config.get("token_uri"),
                    client_id=web_config.get("client_id"),
                    client_secret=web_config.get("client_secret"),
                    scopes=SCOPES
                )
                
                # Turant ek valid access token prapt karne ke liye refresh karein
                credentials.refresh(Request())
                print("Initial credentials created and refreshed using GOOGLE_REFRESH_TOKEN secret.")

            except Exception as e:
                print(f"FATAL: Could not establish credentials using GOOGLE_REFRESH_TOKEN secret: {e}")
                print("Please ensure GOOGLE_REFRESH_TOKEN and GOOGLE_CLIENT_SECRETS are correctly set in GitHub Secrets.")
                raise # Error hone par workflow ko fail karein
                
    # Credentials ko save karein future ke runs ke liye
    with open(TOKEN_FILE, 'wb') as token:
        pickle.dump(credentials, token)
    print(f"Credentials saved/updated to {TOKEN_FILE}.")
            
    return googleapiclient.discovery.build(
        API_SERVICE_NAME, API_VERSION, credentials=credentials)

def upload_video_to_youtube(youtube_service, video_file_path, title, description, tags):
    """
    Local file se YouTube par video upload karta hai.
    """
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "23" # Category ID for Comedy or Entertainment
        },
        "status": {
            "privacyStatus": "public" # public, private, ya unlisted
        }
    }

    print(f"Uploading '{title}' to YouTube...")
    insert_request = youtube_service.videos().insert(
        part="snippet,status",
        body=body,
        media_body=googleapiclient.http.MediaFileUpload(video_file_path)
    )
    response = insert_request.execute()
    print(f"Video successfully uploaded! Video ID: {response.get('id')}")
    print(f"YouTube URL: https://www.youtube.com/watch?v={response.get('id')}") # Corrected YouTube URL

def main():
    """
    Main function jo Cloudinary se video fetch karke YouTube par upload karti hai.
    """
    try:
        print("Fetching videos from Cloudinary 'ScareCam/' folder...")
        result = cloudinary.api.resources(
            type='upload',
            resource_type='video',
            prefix='ScareCam/',
            max_results=500
        )
        videos = result.get('resources', [])
        
        if not videos:
            print("Cloudinary 'ScareCam/' folder mein koi video nahi mili.")
            return

        random_video = random.choice(videos)
        video_url = random_video.get('secure_url')
        video_public_id = random_video.get('public_id')
        print(f"Selected random video: {video_public_id}, URL: {video_url}")

        local_video_filename = f"{video_public_id.split('/')[-1]}"
        if not local_video_filename.lower().endswith(('.mp4', '.mov', '.avi', '.webm')):
            local_video_filename += '.mp4' 

        print(f"Downloading video to {local_video_filename}...")
        
        with requests.get(video_url, stream=True) as r:
            r.raise_for_status()
            with open(local_video_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print("Video download complete.")

        # --- YouTube metadata (Scare Prank Content) ---
        scare_prank_titles = [
            "EPIC SCARE PRANK COMPILATION! You Won't Believe Their Reactions!",
            "CRAZIEST SCARE PRANKS GONE WRONG (Almost!)",
            "HILARIOUS SCARE PRANKS ON STRANGERS! (Public Reactions)",
            "BEST SCARE PRANKS OF ALL TIME! (Try Not To Laugh)",
            "GHOST PRANK! Scaring My Friends in the Dark!",
            "CLOWN SCARE PRANK! They Ran For Their Lives!",
            "SCARE CAM: Catching Unsuspecting Victims!",
            "EXTREME SCARE PRANK CHALLENGE! Who Gets Scared The Most?",
            "FUNNY SCARE PRANKS: Compilation of Jumpscares!",
            "THE ULTIMATE SCARE PRANK! (Viewer Discretion Advised)"
        ]
        
        youtube_title = random.choice(scare_prank_titles) 

        youtube_description = (
            "Welcome to our channel! Get ready for some heart-stopping laughs with our latest scare prank video! "
            "Watch as we unleash hilarious and terrifying pranks on unsuspecting people, capturing their priceless reactions. "
            "From jumpscares to elaborate setups, this compilation is guaranteed to make you jump and then burst into laughter!\n\n"
            "If you enjoyed these epic scares, don't forget to like, share, and subscribe for more prank videos!\n\n"
            "Disclaimer: These pranks are for entertainment purposes only. Please do not attempt to recreate them in real life "
            "without proper planning, safety measures, and consent. We do not condone dangerous or harmful pranks.\n\n"
            "--- Searching Tags --- \n"
            "#ScarePrank #Prank #Jumpscare #FunnyPranks #PrankCompilation #ScareCam #PublicPranks #HilariousReactions #PrankGoneWrong #Comedy #Entertainment #ScaryPrank #BestPranks #TryNotToLaugh #GhostPrank #ClownPrank #Prankster #ViralPrank #NewPrank #ExtremePrank"
        )
        
        youtube_tags = [
            "scare prank", "prank", "jumpscare", "funny pranks", 
            "prank compilation", "scare cam", "public pranks", 
            "hilarious reactions", "prank gone wrong", "comedy", 
            "entertainment", "scary prank", "best pranks", 
            "try not to laugh", "ghost prank", "clown prank", 
            "prankster", "viral prank", "new prank", "extreme prank"
        ]

        # 4. YouTube ke saath authenticate karein aur video upload karein
        youtube_service = get_authenticated_service()
        upload_video_to_youtube(youtube_service, local_video_filename, youtube_title, youtube_description, youtube_tags)

        # 5. Local video file ko delete karein (cleanup)
        os.remove(local_video_filename)
        print(f"Temporary local file deleted: {local_video_filename}")

    except Exception as e:
        print(f"Ek error aa gaya: {e}")
        raise # Error hone par GitHub Action job ko fail karein

if __name__ == "__main__":
    main()
