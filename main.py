import os
import telebot
import requests
import time
import tempfile
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import threading
import uuid  # To generate unique gid

# Telegram bot token and owner ID
TOKEN = '6863982081:AAEQTE4Nv8aMsFn1AMtIJrlwCX9HWIPNPIs'  # Replace with your actual bot token
OWNER_ID = 5264219629  # Replace with your actual Telegram user ID
bot = telebot.TeleBot(TOKEN)

# Store sudo users
sudo_users = [OWNER_ID]  # The owner starts as the only sudo user

# Dictionary to keep track of active tasks
active_tasks = {}

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

# Calculate the download/upload speed
def calculate_speed(bytes_transferred, elapsed_time):
    if elapsed_time > 0:
        speed = bytes_transferred / elapsed_time  # Bytes per second
        return f"{speed / (1024 * 1024):.2f} MB/s"
    return "0 MB/s"

# Progress bar for downloading files with status update in the same message
def download_file_with_progress(url, temp_file_path, chat_id, message_id, gid):
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    chunk_size = 1024 * 1024  # 1 MB
    downloaded_size = 0
    start_time = time.time()

    with open(temp_file_path, 'wb') as f:
        for data in response.iter_content(chunk_size=chunk_size):
            # Check if the task has been canceled
            if active_tasks.get(gid) == "cancel":
                bot.edit_message_text(f"Download task with gid '{gid}' canceled!", chat_id=chat_id, message_id=message_id)
                os.remove(temp_file_path)
                return

            f.write(data)
            downloaded_size += len(data)
            progress = int(downloaded_size * 100 / total_size)
            elapsed_time = time.time() - start_time
            speed = calculate_speed(downloaded_size, elapsed_time)

            status_message = (f"GID: {gid}\nDownloading: {progress}% complete\n"
                              f"Elapsed time: {int(elapsed_time)} seconds\n"
                              f"Speed: {speed}")
            bot.edit_message_text(status_message, chat_id=chat_id, message_id=message_id)
            time.sleep(1)  # Avoid spamming updates too quickly

# Upload file to Google Drive with status update in the same message
def upload_file_to_gdrive(file_name, file_path, drive_service, chat_id, message_id, gid, parent_folder_id=None):
    file_metadata = {'name': file_name}
    if parent_folder_id:
        file_metadata['parents'] = [parent_folder_id]

    media = MediaFileUpload(file_path, resumable=True)
    request = drive_service.files().create(body=file_metadata, media_body=media, fields='id')

    response = None
    start_time = time.time()
    uploaded_size = 0
    total_size = os.path.getsize(file_path)
    
    while response is None:
        # Check if the task has been canceled
        if active_tasks.get(gid) == "cancel":
            bot.edit_message_text(f"Upload task with gid '{gid}' canceled!", chat_id=chat_id, message_id=message_id)
            return

        status, response = request.next_chunk()
        if status:
            uploaded_size = status.resumable_progress
            progress = int(uploaded_size * 100 / total_size)
            elapsed_time = time.time() - start_time
            speed = calculate_speed(uploaded_size, elapsed_time)

            status_message = (f"GID: {gid}\nUploading: {progress}% complete\n"
                              f"Elapsed time: {int(elapsed_time)} seconds\n"
                              f"Speed: {speed}")
            bot.edit_message_text(status_message, chat_id=chat_id, message_id=message_id)
        time.sleep(1)  # Avoid spamming updates too frequently

    return response.get('id')

# Ensure user is owner or sudo
def is_sudo(user_id):
    return user_id in sudo_users

# Handle /cancel command to cancel tasks
@bot.message_handler(commands=['cancel'])
def handle_cancel_task(message):
    if is_sudo(message.from_user.id):
        try:
            gid = message.text.split()[1]
            if gid in active_tasks:
                active_tasks[gid] = "cancel"
                bot.reply_to(message, f"Task with gid '{gid}' is being canceled.")
            else:
                bot.reply_to(message, f"No active task found with gid '{gid}'.")
        except IndexError:
            bot.reply_to(message, "Please provide a gid. Example: /cancel <gid>")
    else:
        bot.reply_to(message, "You do not have permission to use this command.")

# Handle /cancelall command to cancel all tasks (only for the owner)
@bot.message_handler(commands=['cancelall'])
def handle_cancel_all_tasks(message):
    if message.from_user.id == OWNER_ID:
        if active_tasks:
            # Cancel all active tasks
            for gid in active_tasks:
                active_tasks[gid] = "cancel"
            bot.reply_to(message, "All active tasks are being canceled.")
        else:
            bot.reply_to(message, "There are no active tasks to cancel.")
    else:
        bot.reply_to(message, "Only the owner can use this command.")

# Handle /m command: Upload files directly to Google Drive using a direct download link with status update
@bot.message_handler(commands=['m'])
def handle_upload_to_gdrive(message):
    if is_sudo(message.from_user.id):
        try:
            url = message.text.split()[1]
            gid = str(uuid.uuid4())  # Generate a unique gid for the task
            msg = bot.reply_to(message, f"Task GID: {gid}\nPreparing to download and upload the file to Google Drive...")

            file_name = url.split("/")[-1]
            temp_file_path = os.path.join(tempfile.gettempdir(), file_name)

            # Register the task
            active_tasks[gid] = "active"

            # Create a new thread for downloading and uploading to avoid blocking
            def task():
                try:
                    # Download file with progress and live status update
                    download_file_with_progress(url, temp_file_path, message.chat.id, msg.message_id, gid)

                    # Authenticate Google Drive
                    credentials = authenticate_gdrive()
                    drive_service = build('drive', 'v3', credentials=credentials)

                    # Upload file to Google Drive with progress and live status update
                    upload_file_to_gdrive(file_name, temp_file_path, drive_service, message.chat.id, msg.message_id, gid)

                    os.remove(temp_file_path)  # Cleanup after upload
                    bot.edit_message_text(f"File '{file_name}' uploaded successfully to Google Drive!", chat_id=message.chat.id, message_id=msg.message_id)
                except Exception as e:
                    bot.reply_to(message, f"An error occurred: {str(e)}")
                finally:
                    # Remove task from active tasks
                    active_tasks.pop(gid, None)

            threading.Thread(target=task).start()

        except Exception as e:
            bot.reply_to(message, f"An error occurred: {str(e)}")
    else:
        bot.reply_to(message, "You do not have permission to use this command.")

# Handle /l command: Upload file directly to Telegram from a direct download link with status update
@bot.message_handler(commands=['l'])
def handle_upload_to_telegram(message):
    if is_sudo(message.from_user.id):
        try:
            url = message.text.split()[1]
            gid = str(uuid.uuid4())  # Generate a unique gid for the task
            msg = bot.reply_to(message, f"Task GID: {gid}\nPreparing to download and upload the file to Telegram...")

            file_name = url.split("/")[-1]
            temp_file_path = os.path.join(tempfile.gettempdir(), file_name)

            # Register the task
            active_tasks[gid] = "active"

            # Create a new thread for downloading and uploading to avoid blocking
            def task():
                try:
                    # Download file with progress and live status update
                    download_file_with_progress(url, temp_file_path, message.chat.id, msg.message_id, gid)

                    # Upload file to Telegram
                    with open(temp_file_path, 'rb') as f:
                        bot.send_document(message.chat.id, f)

                    os.remove(temp_file_path)  # Cleanup after upload
                    bot.edit_message_text(f"File '{file_name}' uploaded successfully to Telegram!", chat_id=message.chat.id, message_id=msg.message_id)
                except Exception as e:
                    bot.reply_to(message, f"An error occurred: {str(e)}")
                finally:
                    # Remove task from active tasks
                    active_tasks.pop(gid, None)

            threading.Thread(target=task).start()

        except Exception as e:
            bot.reply_to(message, f"An error occurred: {str(e)}")
    else:
        bot.reply_to(message, "You do not have permission to use this command.")

# Command to start the bot
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if is_sudo(message.from_user.id):
        bot.reply_to(message, "Welcome! You can use the following commands:\n"
                              "/m [direct download link] - Upload file directly to Google Drive\n"
                              "/l [direct download link] - Upload file directly to Telegram\n"
                              "/addsudo [user_id] - Add a user as sudo\n"
                              "/lz [direct download link] - Unzip file and upload to Telegram\n"
                              "/mz [direct download link] - Unzip file and upload to Google Drive\n"
                              "/speedtest - Test the server's internet speed\n"
                              "/cancel <gid> - Cancel a specific task by gid\n"
                              "/cancelall - Cancel all active tasks (owner only)")
    else:
        bot.reply_to(message, "You do not have permission to use this bot.")

# Run the bot
if __name__ == '__main__':
    try:
        print("Starting bot...")
        bot.polling(none_stop=True)  # Keeps the bot running
    except Exception as e:
        print(f"An error occurred while running the bot: {e}")
