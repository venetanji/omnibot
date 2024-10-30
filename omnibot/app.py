import streamlit as st
import asyncio
import websockets 
from websockets.asyncio.client import connect
from streamlit_webrtc import WebRtcMode, webrtc_streamer
import av
from asyncio import Queue
import json
from bot import graph
import random

whisper_websocket = "ws://localhost:8000/v1/audio/transcriptions?language=en"

if "loop" not in st.session_state:
    st.session_state.event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(st.session_state.event_loop)

st.title("💬 Omnibot")
st.caption("🚀 An agent with tools")
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "S", "content": "You are a helpful assistant"}]

if "config" not in st.session_state:
    st.session_state.config = {
        "configurable": {
            "thread_id": random.randint(1, 1000)
        }}

input_audio_queue = Queue()
user_message_queue = Queue()

def audio_frame_callback(frame):
    input_audio_queue.put_nowait(frame)
    
webrtc_ctx = webrtc_streamer(
    key="speech-to-text",
    mode=WebRtcMode.SENDONLY,
    audio_receiver_size=1024,
    media_stream_constraints={"video": False, "audio": True},
    audio_frame_callback=audio_frame_callback,
)

resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
async def consume_audio_frames(ws):

    while webrtc_ctx.state.playing:
        if input_audio_queue.qsize() < 2:
            # Queue is empty, waiting for frames
            await asyncio.sleep(0.1)
            continue
        else:
            # get audio frame from queue
            print("Queue size", input_audio_queue.qsize())
            frame = input_audio_queue.get_nowait()
            # resample audio frame at 16kHz
            frame = resampler.resample(frame)
            # send binary audio data to websocket
            print("Sending audio frame")
            await ws.send(frame[0].to_ndarray().tobytes())
            print("Audio frame sent")

async def receive_transcriptions(ws):
    global last_prediction
    last_prediction = ""
    async for message in ws:
        json_message = json.loads(message)
        #print("Received message", message)
        if json_message['text'].strip():
            last_prediction = json_message['text']

async def llm():
    while True:
        user_message = await user_message_queue.get()
        st.chat_message("user").write(user_message)
        for event in graph.stream({"messages": [("user", user_message)]}, config=st.session_state.config):
            for value in event.values():
                for last_message in value["messages"]:
                    if last_message.type == "ai":
                        if last_message.tool_calls:
                            st.session_state.messages.append({"role": "system", "content": f"Tool call: {last_message.tool_calls}"})
                            st.chat_message("C").write(f"Tool call: {last_message.tool_calls}")
                        else:
                            st.session_state.messages.append({"role": "assistant", "content": last_message.content})
                            st.chat_message("assistant").write(last_message.content)
                        break
                    elif last_message.type == "tool":
                        st.session_state.messages.append({"role": "system", "content": f"Tool response: {last_message.content}"})
                        st.chat_message("T").write(f"Tool response: {last_message.content}")
                        break

            
async def run_loop():
    async for ws in connect(whisper_websocket, close_timeout=1, open_timeout=1):
        try:
            audio_coros = []
            audio_coros.append(asyncio.create_task(consume_audio_frames(ws)))
            audio_coros.append(asyncio.create_task(receive_transcriptions(ws)))
            
            llm_coros = []
            llm_coros.append(asyncio.create_task(llm()))
            coros = audio_coros + llm_coros
            await asyncio.gather(*coros)
        except websockets.exceptions.ConnectionClosedOK:
            for task in coros:
                task.cancel()
            if last_prediction:
                user_message_queue.put_nowait(last_prediction)
                print("Last prediction: ", last_prediction)
            continue

if webrtc_ctx.state.playing:
    asyncio.run(run_loop())
else:
    print("WebRTC is not connected")
    asyncio.get_event_loop().stop()

