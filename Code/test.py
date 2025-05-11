import time
import multiprocessing
import RPi.GPIO as GPIO
import os
import sys 
import logging
import spidev as SPI
sys.path.append("..")
from lib import LCD_2inch
from PIL import Image, ImageDraw, ImageFont
from random import randint

# 센서 핀 설정
touch_pin = 17
vibration_pin = 22

# 핀 설정
GPIO.setmode(GPIO.BCM)
GPIO.setup(touch_pin, GPIO.IN)
GPIO.setup(vibration_pin, GPIO.IN)

# LCD 설정
RST = 27
DC = 25
BL = 18
bus = 0 
device = 0 

# 각 감정별 프레임 수
frame_count = {
    'blink': 20, 
    'happy': 60, 
    'sad': 47,
    'dizzy': 67,
    'excited': 24,
    'neutral': 61,
    'happy2': 20,
    'angry': 20,
    'happy3': 26,
    'bootup': 124,
}

# 감정 리스트
emotion_list = ['angry', 'sad', 'excited']
normal_list = ['neutral', 'blink2']

# 소리를 재생하지 않을 감정 목록
no_sound_emotions = ['neutral']

# 공유 변수 설정
emotion_queue = multiprocessing.Queue()
state_change = multiprocessing.Event()
stop_event = multiprocessing.Event()

# 센서 감지 함수
def check_sensor():
    previous_touch_state = GPIO.input(touch_pin)
    
    while not stop_event.is_set():
        try:
            # 터치 센서 확인
            current_touch_state = GPIO.input(touch_pin)
            if current_touch_state == GPIO.HIGH and previous_touch_state != current_touch_state:
                if emotion_queue.empty():
                    emotion_queue.put('happy')
                    state_change.set()
                    print("Touch detected")
            previous_touch_state = current_touch_state
            
            # 진동 센서 확인
            if GPIO.input(vibration_pin) == 1:
                if emotion_queue.empty():
                    selected_emotion = emotion_list[randint(0, len(emotion_list)-1)]
                    emotion_queue.put(selected_emotion)
                    state_change.set()
                    print(f"Vibration detected, emotion: {selected_emotion}")
            
            time.sleep(0.1)
        except Exception as e:
            logging.error(f"Sensor check error: {e}")
            time.sleep(1)

# 이미지 표시 함수 - 단일 프로세스에서 실행
def display_emotion(emotion_name, iterations=1):
    try:
        # LCD 초기화
        disp = LCD_2inch.LCD_2inch()
        disp.Init()
        
        frame_num = frame_count.get(emotion_name, 0)
        if frame_num == 0:
            print(f"No frames found for emotion: {emotion_name}")
            return
            
        # 이미지 표시
        for _ in range(iterations):
            for i in range(frame_num):
                try:
                    image_path = f'./emotions/{emotion_name}/frame{i}.png'
                    image = Image.open(image_path)
                    disp.ShowImage(image)
                    image.close()
                    time.sleep(0.03)  # 프레임 간 지연
                except Exception as e:
                    print(f"Frame error: {e} - {image_path}")
                    continue
        
        # 소리 재생 (neutral 감정일 때는 소리 재생 안 함)
        if emotion_name not in no_sound_emotions:
            try:
                sound_path = f"./sound/emotion/{emotion_name}/so0.wav"
                os.system(f"aplay {sound_path}")
                print(f"Playing sound for {emotion_name}")
            except Exception as e:
                print(f"Sound error: {e}")
        else:
            print(f"No sound played for {emotion_name}")
            
    except Exception as e:
        print(f"Display emotion error: {e}")

# 부팅 시퀀스
def bootup_sequence():
    display_emotion('bootup', 1)
    display_emotion('blink', 1)

# 메인 함수
def main():
    # 로깅 설정
    logging.basicConfig(level=logging.INFO)
    
    # 센서 감지 프로세스 시작
    sensor_process = multiprocessing.Process(target=check_sensor, name='sensor_process')
    sensor_process.daemon = True
    sensor_process.start()
    
    # 현재 감정 표시 프로세스
    current_process = None
    
    try:
        # 부팅 시퀀스 - 메인 스레드에서 실행
        print("Starting bootup sequence...")
        bootup_sequence()
        print("Bootup complete")
        
        # 기본 상태 시작
        current_emotion = normal_list[0]
        current_process = multiprocessing.Process(
            target=display_emotion,
            args=(current_emotion, 1)
        )
        current_process.start()
        
        # 메인 루프 - 무한 반복
        while True:
            # 현재 프로세스가 완료되었는지 확인
            if current_process and not current_process.is_alive():
                # 상태 변경이 있는지 확인
                if state_change.is_set():
                    state_change.clear()
                    
                    # 새 감정 가져오기
                    if not emotion_queue.empty():
                        current_emotion = emotion_queue.get()
                        print(f"Changing to emotion: {current_emotion}")
                else:
                    # 기본 상태로 전환
                    current_emotion = normal_list[randint(0, len(normal_list)-1)]
                    print(f"Returning to normal state: {current_emotion}")
                
                # 새 프로세스 시작
                current_process = multiprocessing.Process(
                    target=display_emotion,
                    args=(current_emotion, 1)
                )
                current_process.start()
            
            # 상태 변경이 있고 현재 프로세스가 실행 중인 경우
            elif state_change.is_set() and current_process and current_process.is_alive():
                # 현재 프로세스 종료
                current_process.terminate()
                current_process.join(timeout=0.5)
                
                # 상태 변경 처리
                state_change.clear()
                
                # 새 감정 가져오기
                if not emotion_queue.empty():
                    current_emotion = emotion_queue.get()
                    print(f"Interrupting with emotion: {current_emotion}")
                    
                    # 새 프로세스 시작
                    current_process = multiprocessing.Process(
                        target=display_emotion,
                        args=(current_emotion, 1)
                    )
                    current_process.start()
            
            # 짧은 대기
            time.sleep(0.2)
                
    except KeyboardInterrupt:
        print("Program terminated by user")
    except Exception as e:
        print(f"Main error: {e}")
    finally:
        # 종료 시 정리
        stop_event.set()
        
        if current_process and current_process.is_alive():
            current_process.terminate()
            current_process.join(timeout=1)
            
        # GPIO 정리
        GPIO.cleanup()
        print("Program finished")

if __name__ == '__main__':
    main()
