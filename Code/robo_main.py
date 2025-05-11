import robo_function
import multiprocessing
from multiprocessing import Process, Event, Manager, Queue

# 감정 리스트
emotion_list = ['angry', 'sad', 'excited', 'happy', 'neutral']
normal_list = ['blink','sleep']

if __name__ == "__main__":
    sensor_detection_event = Event()
    mp_manager = Manager()
    mp_queue = Queue()

    neutral_first = False
    shared_value = mp_manager.Value('i',0)
    shared_bool = mp_manager.Value('b',False)
    
    check_sensor_thread = Process(target=robo_function.check_sensor, args=(sensor_detection_event,mp_queue,))
    robo_respond_thread = Process(target=robo_function.robo_respond, args=(shared_value, shared_bool, sensor_detection_event,)) 

    check_sensor_thread.start()
    robo_respond_thread.start()

    check_sensor_thread.join()
    robo_respond_thread.join()

    try :
        print("🔌 Starting bootup sequence...")
        robo_function.display_emotion('bootup',1, sensor_detection_event)
        print("⚡ Bootup complete")
        robo_function.display_emotion('blink',1, sensor_detection_event)
        neutral_thread = Process(target=robo_function.display_emotion, args=('neutral',3, sensor_detection_event,))
        neutral_thread.start()
        neutral_thread.join()
    
        while True:
            if sensor_detection_event.is_set(): # 센서에 입력 값이 들어오는 경우
                if shared_bool.value == False:
                    detected_emotion = mp_queue.get() # 큐에 들어있는 값을 가져옴
                    while not mp_queue.empty() : # 큐 상태가 비었는지 확인
                        mp_queue.get()
                    print("✅ Sensor input detected")
                if shared_bool.value == True:
                    print("✅ User prompt detected")
                    if shared_value.value == 1:
                        detected_emotion = "happy"
                    elif shared_value.value == 2:
                        detected_emotion = "sad"
                    elif shared_value.value == 3:
                        detected_emotion = "excited"
                    elif shared_value.value == 4:
                        detected_emotion = "neutral"
                    shared_bool.value = False

                print("Detected emotion is : ", detected_emotion)

                p2 = Process(target=robo_function.display_emotion,args=(detected_emotion, 4, sensor_detection_event,))
                p2.start()
                p2.join()
            else:
                p = multiprocessing.active_children() # 현재 프로세스의 모든 살아있는 자식 리스트 반환
                for i in p:
                    if i.name not in ['p1','p5','p6']:
                        i.terminate() # 작업자 프로세스 종료
                neutral = normal[0] # neutral
                neutral_first = True
                p5 = multiprocessing.Process(target=robo_function.display_emotion,args=(neutral,4),name='p5')
                p5.start()
                p5.join() # 프로세스 실행이 완료될 때까지 기다린다
    except KeyboardInterrupt:
        print("Program terminated by user")
    finally:
        sensor_detection_event.set()