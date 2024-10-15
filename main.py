import os
import telebot
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account   


# Telegram Bot Token
BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN' 
bot = telebot.TeleBot(BOT_TOKEN)

# Google Drive API Credentials
SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive']
creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)   

drive_service = build('drive', 'v3', credentials=creds)   


# Handle file uploads
@bot.message_handler(content_types=['audio', 'video', 'photo', 'document'])
def handle_files(message):
    file_id = None
    file_name = None
    file_type = None

    if message.audio:
        file_id = message.audio.file_id
        file_name = message.audio.file_name
        file_type = 'audio'
    elif message.video:
        file_id = message.video.file_id
        file_name = message.video.file_name
        file_type = 'video'
    elif message.photo:
        file_id = message.photo[-1].file_id  # Get the largest photo
        file_name = 'image.jpg'  # Default name for images
        file_type = 'image'
    elif message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
        file_type = 'document'

    if file_id:
        try:
            file_info = bot.get_file(file_id)
            downloaded_file = bot.download_file(file_info.file_path)

            # Upload to Google Drive
            upload_to_drive(downloaded_file, file_name, file_type, message)

        except Exception as e:
            bot.reply_to(message, f"Error uploading file: {e}")

# Handle download links
@bot.message_handler(func=lambda message: '|' in message.text)
def handle_download_link(message):
    try:
        url, new_filename = message.text.split('|', 1)
        url = url.strip()
        new_filename = new_filename.strip()

        # (Implementation to download file from URL and upload to Drive)
        # ... (You'll need to add code here to download from the URL) ...

        # Example using a library like requests:
        # import requests
        # response = requests.get(url)
        # downloaded_file = response.content 

        upload_to_drive(downloaded_file, new_filename, 'link', message) 

    except Exception as e:
        bot.reply_to(message, f"Error processing link: {e}")


def upload_to_drive(file_content, file_name, file_type, message):
    try:
        media = MediaFileUpload(file_name, mimetype='application/octet-stream') 
        file_metadata = {'name': file_name}
        file = drive_service.files().create(body=file_metadata,
                                            media_body=media,
                                            fields='id').execute()   

        bot.reply_to(message, f"{file_type.capitalize()} uploaded to Google Drive! File ID: {file.get('id')}")
    except Exception as e:
        bot.reply_to(message, f"Error uploading to Drive: {e}")

# Start the bot
bot.polling()
