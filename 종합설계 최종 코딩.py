

"""

PIR센서(움직임 감지) 기준 : 취침시간 22시~8시는 제외하고, 8시~22시까지 움직임이 감지되지 않을 때 위험 문자



냉장고
AM 7:00~10:00
PM 11:00~14:00
PM 17:00~20:00

3끼 중 1번 사용 X ->경고로 알림
3끼 중 2번 사용 X -> 위험으로 알림



초음파센서(화장실 방문빈도) 기준 : 3일의 방문빈도 측정해서 화장실 사용횟수 2회이상 8회 이하시 정상, 정상이 아닐시 문자

sudo python3 Nofitication.py

"""




#!/usr/bin/python
# -*- coding: utf-8 -*


import os, time
import RPi.GPIO as GPIO
import spidev


import sys

sys.path.insert(0, "../../")

from sdk.api.message import Message
from sdk.exceptions import CoolsmsException


class Notification:
    def __init__(self):
        print("Start :", str(self))

        self.last_reporting_day_us = 0  # 초음파 최종 레포트한 일자
        self.last_reporting_day_flex = 0  # 플렉스 최종 레포트한 일자
        self.last_reporting_day_pir = 0  # PIR 최종 레포트한 일자
        
        # 마지막 기록 일자
        #self.last_recording_day_us = 0    
        self.last_recording_day_flex = 0 
        self.last_recording_day_pir = 0 
        
        
        self.last_pir_sensing_time = time.time()
        self.pir_sensor_period = 5 # PIR센싱 반복 시간 (5로 하면 한번검출시 5초동안 측정안함)
        
        self.lastday_pir_sms = 0    # 전날 PIR SMS 통보여부
        self.lastday_flex_sms = 0    # 전날 FLEX SMS 통보여부
        self.lastday_us_sms = 0   # 전날 초음파 SMS 통보여부

        self.TOILET_CNT = 0  # 초음파센서 검출수

        self.FRIDGE_CNT_BREAKFAST = 0  # 플렉스센서 검출수. 아침
        self.FRIDGE_CNT_LUNCH = 0  # 플렉스센서 검출수. 점심
        self.FRIDGE_CNT_DINNER = 0 # 플렉스센서 검출수. 저녁

        self.ACTIVITY_CNT = 0 # 움직임 검출수

        self.us_start_time = time.time()     # 초음파센서 시작 기준 일자

        self.PIR_DELAY = 1         # PIR 검출후 딜레이 시간. 
        self.US_DELAY = 5          # 초음파 검출후 딜레이 시간. 5이상
        self.FLEX_DELAY = 5        # 플렉스 검출후 딜레이 시간 5이상

        self.PIR_DETECT_START = 8   # PIR 검출할 시작 시간
        self.PIR_DETECT_END = 22    # PIR 검출할 끝 시간

        self.US_REPORTING_PERIOD = 3*24*60*60  # 초음파센서 빈도 측정 주기(초) 3일인 경우, 3*24*60*60
        self.US_MIN_COUNT = 2         # 초음파 화장실 방문 빈도 최소횟수
        self.US_MAX_COUNT = 8         # 초음파 화장실 방문 빈도 최대횟수
        self.US_DISTANCE = 12         # 초음파 검출 거리 (cm)

        self.MORNING_START = 7    # 아침식사 시작 시간
        self.MORNING_END = 10     # 아침식사 끝 시간
        self.LUNCH_START = 11     # 점심식사 시작 시간
        self.LUNCH_END = 14       # 점심식사 끝 시간
        self.DINNER_START = 17    # 저녁식사 시작 시간
        self.DINNER_END = 20      # 저녁식사 끝 시간

        self.FLEX_THRESHOLD = 35  # 플렉스 센서 기준치
        
        self.SEND_SMS_TIME_PIR = 12   # SMS 전송시간 PIR센서
        self.SEND_SMS_TIME_FLEX = 12  # SMS 전송시간 FLEX센서
        self.SEND_SMS_TIME_US = 12    # SMS 전송시간 초음파센서
        
        
        self.InitSensor()


    def __del__(self):
        pass

    def InitSensor(self):
        self.PIN_PIR = 21
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.PIN_PIR,GPIO.IN)

        self.trig = 13
        self.echo = 19

        GPIO.setup(self.trig, GPIO.OUT)
        GPIO.setup(self.echo, GPIO.IN)


        self.spi=spidev.SpiDev()
        self.spi.open(0, 0)

        self.spi.max_speed_hz=1000000
        #count = 0

    def adc(self, channel):
        buff=self.spi.xfer2([1,(8+channel)<<4,0])
        adcvalue=((buff[1]&3)<<8)+buff[2]
        return adcvalue

    def getDisance(self):
        GPIO.output(self.trig, False)
        time.sleep(0.5)

        GPIO.output(self.trig, True)
        time.sleep(0.00001)
        GPIO.output(self.trig, False)

        while GPIO.input(self.echo) == 0 :
            pulse_start = time.time()

        while GPIO.input(self.echo) == 1 :
            pulse_end = time.time()

        pulse_duration = pulse_end - pulse_start
        distance = pulse_duration * 17000
        distance = round(distance, 2)

        return distance

    def getPir(self):
        result = GPIO.input(self.PIN_PIR)
        #print ("SENSOR Result", result)
        return result


    def getFlex(self):
        value = self.adc(0)

        if value > self.FLEX_THRESHOLD:    # 기준치보다 많이 구부러졌으면
            return True
        else:
            return False

    def send_sms(self, msg):
        print("문자전송: ", msg)

        # 211203 C:\kprj\dev\K211124_FlexUsPirSmsRpi
        #등록된 발신번호 : 01032233414
        #API key :
        #NCSPOKHLSVTCHHXP
        #Api secret :
        #9LQXDQWJX1YK4KFROCM1STS0XLGDRUGV

        api_key = "NCSPOKHLSVTCHHXP"
        api_secret = "9LQXDQWJX1YK4KFROCM1STS0XLGDRUGV"

        ## 4 params(to, from, type, text) are mandatory. must be filled
        params = dict()
        params['type'] = 'sms' # Message type ( sms, lms, mms, ata )
        params['to'] = '01032233414' # Recipients Number '01000000000,01000000001'
        params['from'] = '01032233414' # Sender number
        #params['text'] = 'Test Message 테스트 메시지 api' # Message
        params['text'] = msg

        # Optional parameters for your own needs. more informations visit to http://www.coolsms.co.kr/SMS_API_v2#POSTsend
        # params["image"] = "desert.jpg" # image for MMS. type must be set as "MMS"
        # params["mode"] = "test" # 'test' 모드. 실제로 발송되지 않으며 전송내역에 60 오류코드로 뜹니다. 차감된 캐쉬는 다음날 새벽에 충전 됩니다.
        # params["delay"] = "10" # 0~20사이의 값으로 전송지연 시간을 줄 수 있습니다.
        # params["force_sms"] = "true" # 푸시 및 알림톡 이용시에도 강제로 SMS로 발송되도록 할 수 있습니다.
        # params["refname"] = "" # Reference name
        # params["country"] = "KR" # Korea(KR) Japan(JP) America(USA) China(CN) Default is Korea
        # params["sender_key"] = "5554025sa8e61072frrrd5d4cc2rrrr65e15bb64" # 알림톡 사용을 위해 필요합니다. 신청방법 : http://www.coolsms.co.kr/AboutAlimTalk
        # params["template_code"] = "C004" # 알림톡 template code 입니다. 자세한 설명은 http://www.coolsms.co.kr/AboutAlimTalk을 참조해주세요.
        # params["datetime"] = "20140106153000" # Format must be(YYYYMMDDHHMISS) 2014 01 06 15 30 00 (2014 Jan 06th 3pm 30 00)
        # params["mid"] = "mymsgid01" # set message id. Server creates automatically if empty
        # params["gid"] = "mymsg_group_id01" # set group id. Server creates automatically if empty
        # params["subject"] = "Message Title" # set msg title for LMS and MMS
        # params["charset"] = "euckr" # For Korean language, set euckr or utf-8
        # params["app_version] = "Python SDK v2.0" # 어플리케이션 버전

        cool = Message(api_key, api_secret)

        try:
            response = cool.send(params)
            print("Success Count : %s" % response['success_count'])
            print("Error Count : %s" % response['error_count'])
            print("Group ID : %s" % response['group_id'])
            """
            Success Count : 1
            Error Count : 0
            Group ID : R2GCshLPG2gthWmh
            """
            if "error_list" in response:
                print("Error List : %s" % response['error_list'])

        except CoolsmsException as e:
            print("Error Code : %s" % e.code)
            print("Error Message : %s" % e.msg)




    def checkUltraSonic(self):
        #초음파센서(화장실 방문빈도) 기준 : 3일의 방문빈도 측정해서 화장실 사용횟수 2회이상 8회 이하시 정상, 정상이 아닐시 문자
        distance = self.getDisance()



        if time.time() - self.us_start_time > self.US_REPORTING_PERIOD:   # 측정주기 도달시
            
            hour = self.getTime_hour()
            if hour >= self.SEND_SMS_TIME_US:    # 레포팅 시간이 되었고,
                day = self.getTime_day()
                if self.last_reporting_day_us != day: # 금일 레포팅 안했으면
                    self.last_reporting_day_us = day
            
                self.TOILET_CNT = int(self.TOILET_CNT/2)
                print("화장실 검출 주기 경과 레포팅. 총검출 횟수:", self.TOILET_CNT)
                if self.TOILET_CNT >= self.US_MIN_COUNT and self.TOILET_CNT <= self.US_MAX_COUNT:
                    print("화장실 방문 빈도: 정상.", self.TOILET_CNT)
                else:
                    self.send_sms("화장실 방문 빈도: 비정상. 확인이 필요합니다")
                self.TOILET_CNT = 0
                self.us_start_time = time.time()


        if distance < self.US_DISTANCE:
            self.TOILET_CNT += 1
            print("화장실 방문 검출됨. 현재까지 검출횟수 ", self.TOILET_CNT)
            time.sleep(self.US_DELAY)


    def getTime_day(self):
        now = time.localtime()
        #print("%04d/%02d/%02d %02d:%02d:%02d" % (now.tm_year, now.tm_mon, now.tm_mday, now.tm_hour, now.tm_min, now.tm_sec))
        #print("현재 일자:",now.tm_mday)
        return now.tm_mday

    def getTime_hour(self):
        now = time.localtime()
        #print("현재 시:", now.tm_hour)
        return now.tm_hour

    def checkFlex(self):

        hour = self.getTime_hour()
        if hour >= self.DINNER_END:    # 측정완료 시간이 되었고,
            day = self.getTime_day()
            if self.last_recording_day_flex != day: # 금일 측정기록 안했으면
                self.last_recording_day_flex = day
                MEAL_CNT = 0              # 식사한 횟수
                if self.FRIDGE_CNT_BREAKFAST:
                    MEAL_CNT += 1
                if self.FRIDGE_CNT_LUNCH:
                    MEAL_CNT += 1
                if self.FRIDGE_CNT_DINNER:
                    MEAL_CNT += 1
                

                if MEAL_CNT > 2:
                    print("식사 활동 측정: 정상")
                elif MEAL_CNT == 2:
                    self.lastday_flex_sms = 1
                    print("식사 활동 측정 : 위험")
                else:
                    self.lastday_flex_sms = 2
                    print("식사 활동 측정 : 경고")
                
                self.FRIDGE_CNT_BREAKFAST = 0
                self.FRIDGE_CNT_LUNCH = 0
                self.FRIDGE_CNT_DINNER = 0


        if hour >= self.SEND_SMS_TIME_FLEX:    # 레포팅 시간이 되었고,
            day = self.getTime_day()
            if self.last_reporting_day_flex != day: # 금일 레포팅 안했으면
                self.last_reporting_day_flex = day
                if self.lastday_flex_sms == 1:
                    self.send_sms("식사 활동 레포팅 : 위험")
                elif self.lastday_flex_sms == 2:
                    self.send_sms("식사 활동 레포팅 : 경고")
                self.lastday_pir_sms = 0
                    

        if hour >= self.MORNING_START and hour < self.MORNING_END:      # 아침 식사 시간이고,
            if self.getFlex():            # FLEX 센서 검출 되었으면
                self.FRIDGE_CNT_BREAKFAST += 1
                print("아침 FLEX 센서 검출됨. 총검출횟수:", self.FRIDGE_CNT_BREAKFAST)
                time.sleep(self.FLEX_DELAY)

        if hour >= self.LUNCH_START and hour < self.LUNCH_END:      # 점심 식사 시간이고,
            if self.getFlex():            # FLEX 센서 검출 되었으면
                self.FRIDGE_CNT_LUNCH += 1
                print("점심 FLEX 센서 검출됨. 총검출횟수:", self.FRIDGE_CNT_LUNCH)
                time.sleep(self.FLEX_DELAY)

        if hour >= self.DINNER_START and hour < self.DINNER_END:      # 저녁 식사 시간이고,
            if self.getFlex():            # FLEX 센서 검출 되었으면
                self.FRIDGE_CNT_DINNER += 1
                print("저녁 FLEX 센서 검출됨. 총검출횟수:", self.FRIDGE_CNT_DINNER)
                time.sleep(self.FLEX_DELAY)



    def checkPir(self):

        hour = self.getTime_hour()

        if hour >= self.PIR_DETECT_END:    # 측정완료 시간이 되었고,
            day = self.getTime_day()
            if self.last_recording_day_pir != day: # 금일 측정 기록 안했으면
                self.last_recording_day_pir = day

                if self.ACTIVITY_CNT == 0:
                    self.lastday_pir_sms = 1         # PIR SMS 플래그 넣기
                else:
                    print("움직임 활동 레포팅. 총 검출횟수:", self.ACTIVITY_CNT)
                    self.ACTIVITY_CNT = 0

        if hour >= self.SEND_SMS_TIME_PIR:    # 레포팅 시간이 되었고,
            day = self.getTime_day()
            if self.last_reporting_day_pir != day: # 금일 레포팅 안했으면
                self.last_reporting_day_pir = day
                if self.lastday_pir_sms == 1:
                    self.lastday_pir_sms = 0
                    self.send_sms("위험! 활동 없음")
                    
                

        if hour >= self.PIR_DETECT_START and hour < self.PIR_DETECT_END:      # 활동 검출 시간이고
            if self.getPir():            # PIR 센서 검출 되었으면
            
                if time.time() - self.last_pir_sensing_time > self.pir_sensor_period:  # PIR 중복 측정여부 검출
                    self.last_pir_sensing_time = time.time()

                    self.ACTIVITY_CNT += 1
                    print("PIR 센서 검출됨. 총검출횟수:", self.ACTIVITY_CNT)
                    time.sleep(self.PIR_DELAY)




    def Run(self):
        print("RUN")
        #self.getTime()
        #exit()
        while(True):
            self.checkUltraSonic()
            self.checkFlex()
            self.checkPir()
            time.sleep(1)




    def APP_MAIN(self):
        if os.name == 'nt':
            self.Run()
        else:
            try:
                self.Run()
            except Exception as e :
                import sys
                _, _ , tb = sys.exc_info()    # tb  ->  traceback object
                print ("EXCEPTION ###", e, "[{}]".format(__file__), "[{}]".format(tb.tb_lineno))



if __name__ == "__main__":

    obj = Notification()
    obj.APP_MAIN()
















