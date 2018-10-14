import io
import logging
import pyaudio
import requests
import wave

from textwrap import dedent
from oauthlib.oauth2 import WebApplicationClient
from requests_oauthlib import OAuth2Session

log = logging.getLogger(__name__)

GENERATE_API = 'https://avatar.lyrebird.ai/api/v0/generate'
TOKEN_API = 'https://avatar.lyrebird.ai/api/v0/token'
AUTH_API = 'https://myvoice.lyrebird.ai/authorize'


def generate_oauth2_url(oauth2_client_id, redirect_uri):
    client = WebApplicationClient(
        client_id=oauth2_client_id,
        token_type="authorization_code",
    )
    oauth = OAuth2Session(
        client=client,
        scope="voice",
        redirect_uri=redirect_uri,
    )
    auth_url, state = oauth.authorization_url(AUTH_API)
    return auth_url, state


def generate_oauth2_token(oauth2_client_id, oauth2_client_secret, expected_state, callback_uri):
    code, response_state = callback_uri.split('?')[-1].split('&')
    code = code.split('=')[1]
    response_state = response_state.split('=')[1].rstrip()

    if expected_state != response_state:
        raise AssertionError("MITM attack! (or you failed to copy-paste...)")

    token_json = {
        "grant_type": "authorization_code",
        "client_id": oauth2_client_id,
        "client_secret": oauth2_client_secret,
        "code": code,
    }
    token_response = requests.post(TOKEN_API, json=token_json)
    token_response.raise_for_status()
    return token_response.json()['access_token']


def get_auth_with_user_input(oauth2_client_id, oauth2_client_secret, redirect_uri):
    """Generates an OAuth2 token for the user, by getting them to authorize via a browser, and paste the result back."""
    auth_url, state = generate_oauth2_url(oauth2_client_id, redirect_uri)
    user_auth_response = input(
        dedent("""
        Please click this link, authorize the request, and paste the full redirected URL here:
        %s
        
        Tip: In pycharm, hit space after pasting, then hit enter.
        """ % auth_url)
    )
    return generate_oauth2_token(oauth2_client_id, oauth2_client_secret, state, user_auth_response)


async def generate_voice_for_text(text: str, access_token: str) -> bytes:
    """Generates a byte string of the given text, using the Lyrebird API."""
    headers = {"Authorization": "Bearer {token}".format(token=access_token)}
    result = requests.post(
        GENERATE_API,
        headers=headers,
        json={
            'text': text
        }
    )
    result.raise_for_status()
    log.info("Successfully generated audio for: %s", text)
    return result.content


def rewrite_sample_rate_to(byte_stream: io.BytesIO, target_rate: int):
    output_stream = io.BytesIO()
    with wave.open(byte_stream, 'rb') as input_wav:
        with wave.open(output_stream, 'wb') as output_wav:
            # Copy all the params
            output_wav.setparams(input_wav.getparams())
            # Change the framerate
            output_wav.setframerate(target_rate)
            # Now write out to the new file
            input_frames = input_wav.readframes(input_wav.getnframes())
            output_wav.writeframes(input_frames)
    output_stream.seek(0)
    return output_stream


def play_audio(audio_bytes: bytes):
    """Play the given byte string, which must be .wav format."""
    with wave.open(io.BytesIO(audio_bytes)) as wav:
        channels = wav.getnchannels()
        rate = wav.getframerate()
        width = wav.getsampwidth()
        print(wav.getparams())

    pya = pyaudio.PyAudio()
    stream = pya.open(
        format=pya.get_format_from_width(width=width),
        channels=channels,
        rate=rate,
        output=True,
    )
    log.debug("Audio started")
    stream.write(audio_bytes)
    stream.stop_stream()
    stream.close()
    pya.terminate()
    log.info("Audio finished")
