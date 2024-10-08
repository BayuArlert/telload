from quart import Quart, request, Response, jsonify, session
from quart_cors import cors
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from datetime import datetime, timezone
from datetime import timedelta
from telethon.errors import SessionPasswordNeededError
import secrets
import asyncio
import base64
import logging
import json
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Quart(__name__)
app = cors(app,
           allow_credentials=True,
           allow_origin=["http://127.0.0.1:8000", "http://localhost:8000"],
           allow_methods=["GET", "POST", "OPTIONS"],
           allow_headers=["Content-Type"],
           expose_headers=["Content-Type"])

app.secret_key = secrets.token_hex(16)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(
    minutes=100)

API_ID = '23786363'
API_HASH = '099402880432b069398b080a3a6ba0f8'

client = TelegramClient('anon', API_ID, API_HASH)

STORAGE_FOLDER = Path('downloaded_images')
STORAGE_FOLDER.mkdir(exist_ok=True)


@app.before_serving
async def startup():
    await client.connect()


@app.after_serving
async def cleanup():
    await client.disconnect()


@app.route('/send_code', methods=['POST', 'OPTIONS'])
async def send_code():
    if request.method == 'OPTIONS':
        return '', 204

    data = await request.get_json()
    phone_number = data.get('phone_number')

    try:
        await client.send_code_request(phone_number)
        session['phone_number'] = phone_number
        logger.info(
            f"Phone number saved in session: {session['phone_number']}")
        return jsonify({"success": True, "message": "Kode verifikasi telah dikirim"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/verify_code', methods=['POST', 'OPTIONS'])
async def verify_code():
    if request.method == 'OPTIONS':
        return '', 204

    data = await request.get_json()
    code = data.get('code')
    phone_number = session.get('phone_number')

    logger.info(f"Verifying code: {code} for phone number: {phone_number}")

    if not phone_number:
        return jsonify({"success": False, "message": "Sesi tidak valid"}), 400

    try:
        await client.sign_in(phone_number, code)
        session['logged_in'] = True
        return jsonify({"success": True, "message": "Login berhasil"})
    except SessionPasswordNeededError:
        return jsonify({"success": False, "message": "Diperlukan password dua langkah"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route('/logout', methods=['POST', 'OPTIONS'])
async def logout():
    if request.method == 'OPTIONS':
        return '', 204

    session.clear()
    return jsonify({"success": True, "message": "Logout berhasil"})


@app.route('/check_auth', methods=['GET', 'OPTIONS'])
async def check_auth():
    if request.method == 'OPTIONS':
        return '', 204

    if session.get('logged_in'):
        return jsonify({"authenticated": True, "phone_number": session.get('phone_number')})
    else:
        return jsonify({"authenticated": False})


async def stream_response(messages, entity, start_date, end_date, save_folder):
    try:
        total_messages = len(messages.messages)
        processed_messages = 0
        media_count = 0
        messages_in_range = 0

        for index, message in enumerate(messages.messages):
            current_date = message.date.replace(tzinfo=None)
            in_range = start_date <= current_date <= end_date
            has_media = hasattr(message, 'media') and message.media is not None

            processed_messages += 1
            progress = (processed_messages / total_messages) * 100

            # Send progress update
            yield json.dumps({'type': 'progress', 'percent': progress}) + '\n'

            if in_range:
                messages_in_range += 1
                if has_media:
                    media_count += 1
                    try:
                        file_bytes = await client.download_media(message.media, file=bytes)
                        if file_bytes:
                            filename = f"image_{message.date.strftime('%Y%m%d_%H%M%S')}_{index}.jpg"
                            file_path = save_folder / filename

                            with open(file_path, 'wb') as f:
                                f.write(file_bytes)

                            base64_image = base64.b64encode(
                                file_bytes).decode('utf-8')

                            # Send image data
                            yield json.dumps({
                                'type': 'image',
                                'data': base64_image,
                                'date': message.date.isoformat(),
                                'local_path': str(file_path)
                            }) + '\n'

                            logger.info(
                                f"Berhasil menyimpan gambar ke {file_path}")
                    except Exception as e:
                        logger.error(f"Error saat mengunduh media: {e}")

        # Send final summary
        yield json.dumps({
            'type': 'summary',
            'messages_in_range': messages_in_range,
            'media_count': media_count,
            'downloaded_images': media_count,
            'save_folder': str(save_folder)
        }) + '\n'

    except Exception as e:
        logger.error(f"Error in stream_response: {e}")
        yield json.dumps({'type': 'error', 'message': str(e)}) + '\n'


@app.route('/download', methods=['POST', 'OPTIONS'])
async def download_images():
    if request.method == 'OPTIONS':
        return '', 204

    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Autentikasi diperlukan"}), 401

    try:
        data = await request.get_json()
        group_link = data['group_link']

        # Parse dates and make them timezone-aware
        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')

        # Make dates timezone-aware (using UTC)
        start_date = start_date.replace(
            hour=0, minute=0, second=0, tzinfo=timezone.utc)
        end_date = end_date.replace(
            hour=23, minute=59, second=59, tzinfo=timezone.utc)

        try:
            entity = await client.get_entity(group_link)
        except ValueError:
            return Response(json.dumps({'type': 'error', 'message': 'Invalid group link'}),
                            mimetype='application/json', status=400)

        group_name = getattr(
            entity, 'title', 'unknown_group').replace(' ', '_')
        date_range = f"{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"
        save_folder = STORAGE_FOLDER / f"{group_name}_{date_range}"
        save_folder.mkdir(exist_ok=True)

        logger.info(f"Menyimpan gambar ke folder: {save_folder}")

        return Response(stream_download_images(entity, start_date, end_date, save_folder),
                        mimetype='text/event-stream')

    except Exception as e:
        logger.error(f"Error dalam fungsi download_images: {e}")
        return Response(json.dumps({'type': 'error', 'message': str(e)}),
                        mimetype='application/json', status=500)

# Ubah fungsi stream_download_images


async def stream_download_images(entity, start_date, end_date, save_folder):
    try:
        offset_id = 0
        limit = 100
        total_messages = 0
        downloaded_images = 0
        group_name = getattr(entity, 'title', 'unknown_group')

        yield f"data: {json.dumps({'type': 'group_info', 'name': group_name})}\n\n"

        while True:
            history = await client(GetHistoryRequest(
                peer=entity,
                limit=limit,
                offset_date=None,
                offset_id=offset_id,
                max_id=0,
                min_id=0,
                add_offset=0,
                hash=0
            ))

            if not history.messages:
                break

            total_in_batch = len(history.messages)
            processed_in_batch = 0

            for message in history.messages:
                message_date = message.date.replace(tzinfo=timezone.utc)
                processed_in_batch += 1

                # Mengirim progress untuk setiap pesan yang diproses
                progress_percent = (
                    (total_messages + processed_in_batch) / 1000) * 100
                yield f"data: {json.dumps({'type': 'progress', 'percent': min(progress_percent, 100)})}\n\n"

                if start_date <= message_date <= end_date:
                    if message.media and hasattr(message.media, 'photo'):
                        try:
                            file_bytes = await client.download_media(message.media, bytes)
                            if file_bytes:
                                downloaded_images += 1
                                filename = f"image_{message_date.strftime('%Y%m%d_%H%M%S')}_{message.id}.jpg"

                                # Simpan file
                                file_path = save_folder / filename
                                with open(file_path, 'wb') as f:
                                    f.write(file_bytes)

                                # Kirim data gambar ke client
                                base64_image = base64.b64encode(
                                    file_bytes).decode('utf-8')
                                yield json.dumps({
                                    'type': 'image',
                                    'data': base64_image,
                                    'date': message_date.isoformat()
                                }) + '\n'
                        except Exception as e:
                            logger.error(
                                f"Error downloading image from message {message.id}: {e}")
                            yield f"data: {json.dumps({'type': 'error', 'message': f'Error downloading image: {str(e)}'})}\n\n"

            if len(history.messages) < limit:
                break

            offset_id = history.messages[-1].id
            total_messages += len(history.messages)

            if total_messages >= 1000:
                break

        # Kirim ringkasan di akhir
        yield json.dumps({
            'type': 'summary',
            'downloaded_images': downloaded_images,
            'save_folder': str(save_folder),
            'group_name': group_name
        }) + '\n'

    except Exception as e:
        logger.error(f"Error in stream_download_images: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

if __name__ == '__main__':
    app.run(debug=True)
