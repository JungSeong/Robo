

if __name__ == '__main__':
    neutral_first = False
    shared_value = multiprocessing.Value('i',0)
    shared_bool = multiprocessing.Value('b',False)
    p1 = multiprocessing.Process(target=check_sensor_thread, name='p1') # 프로세스 시작
    p5 = None
    p6 = multiprocessing.Process(target=robo_responding_thread, name='p6') 
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
            print("emotion_list is : ", _emotion)
            p2 = multiprocessing.Process(target=display_emotion,args=(_emotion,4))
            p2.start()
            p2.join()

        else:
            p = multiprocessing.active_children() # 현재 프로세스의 모든 살아있는 자식 리스트 반환
            for i in p:
                if i.name not in ['p1','p5','p6']:
                    i.terminate() # 작업자 프로세스 종료
            neutral = normal_list[0] # neutral
            neutral_first = True
            p5 = multiprocessing.Process(target=display_emotion,args=(neutral,4),name='p5')
            p5.start()
            p5.join() # 프로세스 실행이 완료될 때까지 기다린다