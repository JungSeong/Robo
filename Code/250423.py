import time
from board import SCL, SDA
import multiprocessing

import RPi.GPIO as GPIO
import os
import sys 
import time 
import logging
from dotenv import load_dotenv

from lib import LCD_2inch
from PIL import Image,ImageDraw,ImageFont

from random import randint
import google.generativeai as genai
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
import speech_recognition as sr

sys.path.append("..")
load_dotenv()

touch_pin = 17
vibration_pin = 22

genai.configure(api_key = os.getenv("GOOGLE_API_KEY"))
system_instruction = "당신은 사람의 {user_query}에 대해 친절하게 답변해주는 Emo라는 이름을 가진 가정용 로봇입니다. {user_query}에 대해 두 문장 이내로 친절하게 답변해주세요."
model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system_instruction)
# model = genai.GenerativeModel('gemini-pro')
chat_session = model.start_chat(history=[])  # ChatSession 객체 반환

# Set up pins
GPIO.setmode(GPIO.BCM)
GPIO.setup(touch_pin, GPIO.IN)
GPIO.setup(vibration_pin, GPIO.IN)

# Raspberry Pi pin configuration for LCD:
RST = 27
DC = 25
BL = 18
bus = 0 
device = 0 

frame_count = {'blink':39, 'happy':60, 'sad':47,'dizzy':67,'excited':24,'neutral':61,'happy2':20,'angry':20,'happy3':26,'bootup3':124,'blink2':20}

emotion = ['angry','sad','excited']
normal = ['neutral','blink2']

q = multiprocessing.Queue() # 프로세스 간에 데이터를 주고 받기 위한 파이프라인
event = multiprocessing.Event() # 프로세스 간에 신호를 주고받기 위한 동기화 도구, 내부에 불리언 플래그(flag)를 가짐
is_responsing = False
gemini_emotion = 0

def check_sensor(): 
    previous_state = 1
    current_state = 0
    while True:
        if (GPIO.input(touch_pin) == GPIO.HIGH):
            if previous_state != current_state:
                if (q.qsize()==0):
                    event.set() # 이벤트 발생 (flag를 True로 설정)
                    q.put('happy') # 큐에 항목 추가
                current_state = 1
            else:
                current_state = 0
        if GPIO.input(vibration_pin) == 1:
            print('vib')
            if (q.qsize()==0):
                event.set()
                q.put(emotion[randint(0,2)])
        time.sleep(0.05)

def check_emotion(query):
    if "기쁨" in query:
        return 1
    elif "슬픔" in query:
        return 2
    elif "바보" in query:
        return 3
    else:
        return 4

def check_sound():
    status = "idle"

    while True:
        print("recording is running")
        r = sr.Recognizer()

        if status == "idle" :
            with sr.Microphone() as source:
                audio = r.listen(source)
                try:
                    user_query = r.recognize_google(audio, language='ko-KR')
                    if "로보" in user_query:
                        audio = AudioSegment.from_file("./sound/emotion/robo/so0.wav")
                        play(audio)
                        print("frist",user_query)
                        time.sleep(0.5)
                        status = "listening"
                except sr.UnknownValueError:
                    print("Google Speech Recognition could not understand audio")
                except sr.RequestError as e:
                    print("Could not request results from Google Speech Recognition service; {0}".format(e))

        elif status == "listening" :
            tts_dir = "./audio/tts"
            with sr.Microphone() as source:
                audio = r.listen(source)
            try:
                user_query = r.recognize_google(audio, language='ko-KR')
                print("second",user_query)
                time.sleep(0.5)
                status = "responding"
            except sr.UnknownValueError:
                print("Google Speech Recognition could not understand audio")
            except sr.RequestError as e:
                print("Could not request results from Google Speech Recognition service; {0}".format(e))

        elif status == "responding" :  
            shared_bool.value = True # 멀티 프로세스 공유 변수 shared_bool을 True로
            response = chat_session.send_message(user_query) 
            print("response",response.text)
            shared_value.value = check_emotion(user_query) # 멀티 프로세스 공유 변수 shared_value를 1~4로
            tts = gTTS(response.text, lang='ko')
            tts_dir = "./audio/tts"

            if not os.path.exists(tts_dir):
                os.makedirs(tts_dir)

            tts_path = os.path.join(f"{tts_dir}", "test_mp3.mp3")
            tts.save(tts_path)

            event.set() # 이벤트를 실행
            print(f"⭕ TTS saved to {tts_dir}.")
            audio = AudioSegment.from_file(tts_path)
            play(audio)
            print("audio end")

            time.sleep(0.5)
            status = "idle"
        
def bootup():
    show('bootup3',1)
    for i in range(1):
        p2 = multiprocessing.Process(target=show,args=('blink2',3))
        # p3 = multiprocessing.Process(target=rotate,args=(0,150,0.005))
        # p4 = multiprocessing.Process(target=baserotate,args=(90,45,0.01))
        p2.start()
        # p3.start()
        # p4.start()
        # p4.join()
        p2.join()
        # p3.join()
    
def sound(emotion):
    for i in range(1):
	    os.system("aplay /home/pi/Desktop/Emo/Code/sound/emotion/"+emotion+"/so"+str(i)+".wav")

def show(emotion,count):
    disp = LCD_2inch.LCD_2inch()
    disp.Init()

    for idx in range(count):
        try:
            for i in range(frame_count[emotion]):
                image = Image.open('/home/pi/Desktop/Emo/Code/emotions/'+emotion+'/frame'+str(i)+'.png')	
                disp.ShowImage(image)
                # Added part
                if event.is_set():
                 break  
        except IOError as e:
            logging.info(e)    
        except KeyboardInterrupt:
            disp.module_exit()
            logging.info("quit:")
            exit()

if __name__ == '__main__':
    neutral_first = False
    shared_value = multiprocessing.Value('i',0)
    shared_bool = multiprocessing.Value('b',False)
    p1 = multiprocessing.Process(target=check_sensor, name='p1') # 프로세스 시작
    p5 = None
    p6 = multiprocessing.Process(target=check_sound, name='p6') 
    p6.start()
    p1.start()
    bootup() # 처음 부팅을 담당하는 함수
    
    while True:
        if event.is_set():
            if neutral_first == True and p5 is not None:
                p5.terminate()
                print("neutral terminate test")
            # p5.terminate()
            event.clear() # 이벤트 해제
            _emotion = ""
            if shared_bool.value == False:
                _emotion = q.get() # 큐에 들어있는 값을 가져옴
                while not q.empty() : # 큐 상태가 비었는지 확인
                    q.get()
                print("senson detection")
            if shared_bool.value == True:
                print("voice detection")
                if shared_value.value == 1:
                    _emotion = "happy"
                elif shared_value.value == 2:
                    _emotion = "sad"
                elif shared_value.value == 3:
                    _emotion = "excited"
                elif shared_value.value == 4:
                    _emotion = "neutral"
                shared_bool.value = False
            print("emotion is : ", _emotion)
            p2 = multiprocessing.Process(target=show,args=(_emotion,4))
            p2.start()
            if _emotion != "neutral":
                p3 = multiprocessing.Process(target=sound,args=(_emotion,))
                p3.start()
                p3.join()
            p2.join()

        else:
            p = multiprocessing.active_children() # 현재 프로세스의 모든 살아있는 자식 리스트 반환
            for i in p:
                if i.name not in ['p1','p5','p6']:
                    i.terminate() # 작업자 프로세스 종료
            neutral = normal[0] # neutral
            neutral_first = True
            p5 = multiprocessing.Process(target=show,args=(neutral,4),name='p5')
            p5.start()
            p5.join() # 프로세스 실행이 완료될 때까지 기다린다