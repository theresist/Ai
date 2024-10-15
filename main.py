import os
import telebot
import requests
import io
import zipfile
import tempfile
import speedtest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Telegram bot token
TOKEN = '6863982081:AAEQTE4Nv8aMsFn1AMtIJrlwCX9HWIPNPIs'  # Replace with your actual bot token
bot = telebot.TeleBot(TOKEN)

# Google Drive API setup
SCOPES = ['https://www.googleapis.com/auth/drive']
credentials = None

# Authenticate Google Drive
def authenticate_gdrive():
    global credentials
    if os.path.exists('token.json'):
        credentials = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            credentials = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(credentials.to_json())
    print("Google Drive authentication complete.")
    return credentials

# Upload file to Google Drive
def upload_file_to_gdrive(file_name, file_path, drive_service, parent_folder_id=None):
    file_metadata = {'name': file_name}
    if parent_folder_id:
        file_metadata['parents'] = [parent_folder_id]

    media = MediaIoBaseUpload(open(file_path, 'rb'), mimetype='application/octet-stream', resumable=True)
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"Uploaded {file_name} to Google Drive with file ID: {file.get('id')}")
    return file.get('id')

# Handle /m command: Upload files directly to Google Drive using a direct download link
@bot.message_handler(commands=['m'])
def handle_upload_to_gdrive(message):
    try:
        url = message.text.split()[1]  # Expect the direct download link as an argument
        print(f"Received /m command with URL: {url}")
        bot.reply_to(message, "Downloading and uploading the file to Google Drive...")

        # Download the file to a temporary location
        response = requests.get(url, stream=True)
        file_name = url.split("/")[-1]

        # Save the file temporarily on the bot's server
        temp_file_path = os.path.join(tempfile.gettempdir(), file_name)
        with open(temp_file_path, 'wb') as f:
            f.write(response.content)

        # Authenticate Google Drive
        credentials = authenticate_gdrive()
        drive_service = build('drive', 'v3', credentials=credentials)

        # Upload file to Google Drive
        upload_file_to_gdrive(file_name, temp_file_path, drive_service)

        # Delete the temporary file from the bot's server
        os.remove(temp_file_path)
        print(f"Deleted the temporary file: {temp_file_path}")

        bot.reply_to(message, f"File '{file_name}' uploaded successfully to Google Drive!")

    except Exception as e:
        print(f"Error during /m command: {e}")
        bot.reply_to(message, f"An error occurred: {str(e)}")

# Handle /l command: Upload file directly to Telegram from a direct download link
@bot.message_handler(commands=['l'])
def handle_upload_to_telegram(message):
    try:
        url = message.text.split()[1]  # Expect the direct download link as an argument
        print(f"Received /l command with URL: {url}")
        bot.reply_to(message, "Downloading and uploading the file to Telegram...")

        # Download the file from the URL
        response = requests.get(url, stream=True)
        file_name = url.split("/")[-1]

        # Save the file temporarily on the bot's server
        temp_file_path = os.path.join(tempfile.gettempdir(), file_name)
        with open(temp_file_path, 'wb') as f:
            f.write(response.content)

        # Upload the file to Telegram
        with open(temp_file_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption=f"Here is your file: {file_name}")
        
        # Delete the temporary file from the bot's server
        os.remove(temp_file_path)
        print(f"Deleted the temporary file: {temp_file_path}")

        bot.reply_to(message, f"File '{file_name}' uploaded successfully to Telegram!")

    except Exception as e:
        print(f"Error during /l command: {e}")
        bot.reply_to(message, f"An error occurred: {str(e)}")

# Handle /lz command: Unzip a file from direct download link and upload contents to Telegram
@bot.message_handler(commands=['lz'])
def handle_unzip_and_upload_to_telegram(message):
    try:
        url = message.text.split()[1]  # Expect the direct download link as an argument
        print(f"Received /lz command with URL: {url}")
        bot.reply_to(message, "Downloading, unzipping, and uploading the files to Telegram...")

        # Download the zip file from the URL
        response = requests.get(url, stream=True)
        zip_file_data = io.BytesIO(response.content)

        with zipfile.ZipFile(zip_file_data) as zip_ref:
            # Extract and upload each file
            for file_name in zip_ref.namelist():
                with zip_ref.open(file_name) as extracted_file:
                    file_data = io.BytesIO(extracted_file.read())  # Read file content in memory
                    file_data.seek(0)  # Reset pointer to start
                    bot.send_document(message.chat.id, file_data, caption=f"Here is your file: {file_name}")
        
        bot.reply_to(message, "Files unzipped and uploaded successfully to Telegram!")

    except Exception as e:
        print(f"Error during /lz command: {e}")
        bot.reply_to(message, f"An error occurred: {str(e)}")

# Handle /mz command: Unzip a file from direct download link and upload contents to Google Drive
@bot.message_handler(commands=['mz'])
def handle_unzip_and_upload_to_gdrive(message):
    try:
        url = message.text.split()[1]  # Expect the direct download link as an argument
        print(f"Received /mz command with URL: {url}")
        bot.reply_to(message, "Downloading, unzipping, and uploading the files to Google Drive...")

        # Download the zip file from the URL
        response = requests.get(url, stream=True)
        zip_file_data = io.BytesIO(response.content)

        # Authenticate Google Drive
        credentials = authenticate_gdrive()
        drive_service = build('drive', 'v3', credentials=credentials)

        with zipfile.ZipFile(zip_file_data) as zip_ref:
            # Extract and upload each file to Google Drive
            for file_name in zip_ref.namelist():
                with zip_ref.open(file_name) as extracted_file:
                    temp_file_data = io.BytesIO(extracted_file.read())  # Read file content in memory
                    temp_file_data.seek(0)  # Reset pointer to start
                    # Upload the extracted file to Google Drive
                    upload_file_to_gdrive(file_name, temp_file_data, drive_service)
        
        bot.reply_to(message, "Files unzipped and uploaded successfully to Google Drive!")

    except Exception as e:
        print(f"Error during /mz command: {e}")
        bot.reply_to(message, f"An error occurred: {str(e)}")

# Handle /speedtest command: Test the server's internet speed
@bot.message_handler(commands=['speedtest'])
def handle_speedtest(message):
    try:
        bot.reply_to(message, "Running speed test...")
        st = speedtest.Speedtest()

        # Get download, upload, and ping
        download_speed = st.download() / 1_000_000  # Convert from bits/s to Mbit/s
        upload_speed = st.upload() / 1_000_000  # Convert from bits/s to Mbit/s
        ping = st.results.ping

        # Format the results and send back
        speed_report = (
            f"Download Speed: {download_speed:.2f} Mbps\n"
            f"Upload Speed: {upload_speed:.2f} Mbps\n"
            f"Ping: {ping} ms"
        )
        bot.reply_to(message, speed_report)

    except Exception as e:
        print(f"Error during /speedtest command: {e}")
        bot.reply_to(message, f"An error occurred while testing speed: {str(e)}")

# Command to start the bot
@bot.message_handler(commands=['start'])
def send_welcome(message):
    print("Received /start command")
    bot.reply_to(message, "Welcome! You can use the following commands:\n"
                          "/m [direct download link] - Upload file directly to Google Drive\n"
                          "/l [direct download link] - Upload file directly to Telegram\n"
                          "/lz [direct download link] - Unzip file and upload to Telegram\n"
                          "/mz [direct download link] - Unzip file and upload to Google Drive\n"
                          "/speedtest - Test the server's internet speed")

# Handle unknown commands
@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    print(f"Received unknown command: {message.text}")
    bot.reply_to(message, "Unknown command. Use /m to upload a file to Google Drive or /l to upload to Telegram.")

# Run the bot
if __name__ == '__main__':
    try:
        print("Starting bot...")
        bot.polling(none_stop=True)  # Keeps the bot running
    except Exception as e:
        print(f"An error occurred while running the bot: {e}")
