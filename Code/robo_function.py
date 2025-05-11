from lib import LCD_2inch
from PIL import Image,ImageDraw,ImageFont
from enum import Enum
from board import SCL, SDA
from gtts import gTTS
from enum import Enum
from pydub import AudioSegment
from pydub.playback import play
from random import randint
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from robo_main import emotion_list, normal_list

import multiprocessing
import time
import RPi.GPIO as GPIO
import os
import sys 
import time 
import logging
import speech_recognition as sr

load_dotenv()

# Basic GPIO Setup
touch_pin = 17
vibration_pin = 22
GPIO.setmode(GPIO.BCM)
GPIO.setup(touch_pin, GPIO.IN)
GPIO.setup(vibration_pin, GPIO.IN)

# Raspberry Pi pin configuration for LCD:
RST = 27
DC = 25
BL = 18

# 긱 김장 별 프레임 수
frame_count = {
    'angry': 20,
    'blink': 20,
    'bootup': 120,
    'dizzy': 67,
    'excited': 24, 
    'happy': 60, 
    'sad': 47,
    'neutral': 61,
    'sleep': 112
}

def generate_robo_response(user_query, chat_history, memory) :
    """
    Gemini API를 사용해 {user_query}에 대한 일상적인 대답을 생성해주는 함수입니다.

    Returns :
        robo_response (str)
    """

    robo_main_prompt = """
    당신은 Robo라는 이름을 가진 친절하고 상냥한 가정용 로봇입니다.
    지금까지 당신과 주인이 나눈 대화는 다음과 같습니다 : {chat_history}

    당신은 주인의 {user_query}에 대해 친젊하고 상냥하게, 1~3줄 이내로 답변하여야 합니다.
    """

    robo_main_template = PromptTemplate(
        template=robo_main_prompt,
        input_variables=["user_query", "chat_history"]
    )

    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        temperature=0.5,
        max_output_tokens=2000,
    )

    chain = LLMChain(
        llm=llm,
        prompt=robo_main_template,
        memory=memory,
        verbose=True
    )

    robo_response = chain.invoke({
        "user_query": user_query,
        "chat_history": chat_history,
    })['text']

    return robo_response

def check_emotion(query):
    if "기쁨" in query:
        return 1
    elif "슬픔" in query:
        return 2
    elif "바보" in query:
        return 3
    else:
        return 4

def check_sensor(sensor_detection_event, mp_queue):
    """
    센서에 입력 값이 들어오면 멀티 프로세싱의 shared_data로 알려주는 함수입니다.

    Returns :
        None
    """  
    previous_state = 1
    current_state = 0
    while True:
        if (GPIO.input(touch_pin) == GPIO.HIGH):
            if previous_state != current_state:
                print('touch')
                if (mp_queue.qsize()==0):
                    sensor_detection_event.set()
                    mp_queue.put('happy') # 큐에 항목 추가
                current_state = 1
            else:
                current_state = 0
        if GPIO.input(vibration_pin) == 1:
            print('vib')
            if (mp_queue.qsize()==0):
                sensor_detection_event.set()
                mp_queue.put('angry')
        time.sleep(0.1)

def play_sound(emotion):
    """
    효과음을 재생해주는 함수입니다.

    Returns :
        None
    """
    if emotion == 'neutral':
        emotion = 'blink'
        
    try :
        sound_path = os.path.join("sound/emotion",emotion,"so0.wav")
        print(f"⭕ {sound_path}")
        os.system(f"aplay {sound_path}")
    except Exception as e:
            print(f"Sound error: {e}")
    else:
        print(f"❌ No sound played for {emotion}")

def display_emotion(emotion,count,sensor_detection_event):
    """
    LCD에 {emotion}에 해당하는 표정을 띄워주고, 그에 맞는 효과음을 재생해주는 함수입니다.

    Returns :
        None
    """
    try :
        disp = LCD_2inch.LCD_2inch()
        disp.Init()

        for repeat in range(count):
            try:
                for idx in range(frame_count[emotion]):
                    emotion_path = os.path.join("emotions", emotion, f"frame{str(idx)}.png")
                    image = Image.open(emotion_path)	
                    disp.ShowImage(image)
                    if sensor_detection_event.is_set():
                        disp.clear()
                        logging.info("quit:")
                        break  
            except IOError as e:
                logging.info(e)    
            except KeyboardInterrupt:
                disp.clear()
                logging.info("quit:")
                exit()
        play_sound(emotion)
    except Exception as e:
        print(f"❌ Display emotion error: {e}")
    finally :
        disp.clear()

def robo_respond(shared_value, shared_bool, sensor_detection_event):
    """
    마이크를 통해 들어오는 사용자의 user_query에 대해 적절한 응답을 TTS로 생성해주는 함수입니다.

    Returns :
        None
    """
    memory = ConversationBufferMemory(memory_key="chat_history", input_key="user_query")
    chat_history = memory.load_memory_variables({})["chat_history"]

    status = "idle"
    r = sr.Recognizer()

    if status == "idle" :
        with sr.Microphone() as source:
            audio = r.listen(source, phrase_time_limit=10) # 한 번에 받을 수 있는 음성의 길이 : 10초
            try:
                user_query = r.recognize_google(audio, language='ko-KR')
                if "로보" in user_query:
                    print(user_query)
                    audio = AudioSegment.from_file("./sound/emotion/robo/so0.wav")
                    play(audio)
                    time.sleep(0.5)
                    status = "listening"
            except sr.UnknownValueError:
                print("Google Speech Recognition could not understand audio")
            except sr.RequestError as e:
                print("Could not request results from Google Speech Recognition service; {0}".format(e))

    elif status == "listening" :
        shared_bool.value = True
        with sr.Microphone() as source:
            audio = r.listen(source)
        try:
            user_query = r.recognize_google(audio, language='ko-KR')
            print(user_query)
            time.sleep(0.5)
            status = "responding"
        except sr.UnknownValueError:
            print("Google Speech Recognition could not understand audio")
        except sr.RequestError as e:
            print("Could not request results from Google Speech Recognition service; {0}".format(e))

    elif status == "responding" :  
        response = generate_robo_response(user_query, chat_history, memory)
        print(response)
        shared_value.value = check_emotion(user_query)
        tts = gTTS(response, lang='ko')
        tts_dir = "./audio/tts"       
        
        if not os.path.exists(tts_dir):
            os.makedirs(tts_dir)

        tts_path = os.path.join(f"{tts_dir}", "tts.mp3")
        tts.save(tts_path)

        print(f"⭕ TTS saved to {tts_dir}.")
        audio = AudioSegment.from_file(tts_path)
        play(audio)
        print("✅ TTS End")

        time.sleep(0.5)
        status = "idle"

# class Emotion(Enum):
#     ANGRY = 1
#     SAD = 2
#     EXCITED = 3
#     HAPPY = 4
#     NEUTRAL = 5

# def discriminate_emotion(user_query, emotion_list=emotion_list):
#     """
#     {user_query}가 어떤 감정에 해당하는지 분류해주는 함수입니다.

#     Returns :
#         emotion (int)
#     """

#     discriminator_prompt = """
#     당신은 {user_query}가 {emotion_list} 중 어떤 감정에 가장 가까운지 분류해주는 함수입니다.
#     반드시 {emotion_list}에 있는 감정 중 하나로 분류해야 합니다.
#     """

#     discriminate_template = PromptTemplate(
#         template=discriminator_prompt,
#         input_variables=["user_query", "emotion_list"]
#     )

#     llm = ChatGoogleGenerativeAI(
#         model="gemini-1.5-flash",
#         temperature=0.3,
#         max_output_tokens=200,
#     )

#     chain = LLMChain(
#         llm=llm,
#         prompt=discriminate_template,
#         verbose=True
#     )

#     discriminated_emotion = chain.invoke({
#         "user_query": user_query,
#         "emotion_list": emotion_list,
#     }).get('text', '').strip().lower()

#     print(discriminated_emotion)

#     if discriminated_emotion == 'angry' :
#         return Emotion.ANGRY
#     elif discriminated_emotion == 'sad' :
#         return Emotion.SAD
#     elif discriminated_emotion == 'excited' :
#         return Emotion.EXCITED
#     elif discriminated_emotion == 'happy' :
#         return Emotion.HAPPY
#     elif discriminated_emotion == 'neutral' :
#         return Emotion.NEUTRAL
#     else :
#         return