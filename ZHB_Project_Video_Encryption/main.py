import sys
import time
import argparse
from socket import *
import threading
import pyaudio
import wave
import struct
import pickle
import numpy as np
import cv2
import pymysql
import os
import re
from moviepy.editor import VideoFileClip
from moviepy.editor import AudioFileClip
#---------------------------网络传输参数----------------------------------------
parser = argparse.ArgumentParser()

parser.add_argument('--host', type=str, default='127.0.0.1')
parser.add_argument('--port', type=int, default=10087)
parser.add_argument('--level', type=int, default=1)
parser.add_argument('-v', '--version', type=int, default=4)

args = parser.parse_args()

IP = args.host
PORT = args.port
VERSION = args.version
LEVEL = args.level
#---------------------------视频传输部分----------------------------------------
"""加密相关图片的读取"""
noise = cv2.imread("123.jpg")
key = np.array(noise,dtype = 'int')

"""音频地址"""
fg_audio_path = "wave.wav"
fg_video_path = "video.mp4"
"""接收端"""
class Video_Server(threading.Thread):
    def __init__(self, port, version) :
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.ADDR = ('', port)
        self.i = 1
        if version == 4:
            self.sock = socket(AF_INET ,SOCK_STREAM)
        else:
            self.sock = socket(AF_INET6 ,SOCK_STREAM)
    def __del__(self):
        self.sock.close()
        try:
            cv2.destroyAllWindows()
        except:
            pass
    def run(self):
        print("VIDEO server starts...")
        self.sock.bind(self.ADDR)
        self.sock.listen(1)
        conn, addr = self.sock.accept()
        print("remote VIDEO client success connected...")
        data = "".encode("utf-8")
        payload_size = struct.calcsize("L")		# 结果为4
        cv2.namedWindow('VIDEO', cv2.WINDOW_NORMAL)
        videoWriter = cv2.VideoWriter(fg_video_path, cv2.VideoWriter_fourcc('M','P','E','G'),10,(640,480))
        while True:
            while len(data) < payload_size:
                data += conn.recv(81920)
            packed_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("L", packed_size)[0]
            while len(data) < msg_size:
                data += conn.recv(81920)
            frame_data = data[:msg_size]
            data = data[msg_size:]
            frame = pickle.loads(frame_data)
            #if self.i >= 34:
            videoWriter.write(frame)
            #else:
            
            """解密"""

            frame = np.array(frame,dtype='int')
            frame = np.bitwise_xor(frame,key)
            
            """显示视频"""
            frame = np.array(frame,'uint8')
            self.i = self.i+1
            cv2.imshow('VIDEO', frame)
            if cv2.waitKey(1) & 0xFF == 27:
                videoWriter.release()
                break

"""发送端"""
class Video_Client(threading.Thread):
    def __init__(self ,ip, port, level, version):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.ADDR = (ip, port)
        if level <= 3:
            self.interval = level
        else:
            self.interval = 3
        self.fx = 1 / (self.interval + 1)
        if self.fx < 0.3:	# 限制最大帧间隔为3帧
            self.fx = 0.3
        if version == 4:
            self.sock = socket(AF_INET, SOCK_STREAM)
        else:
            self.sock = socket(AF_INET6, SOCK_STREAM)
        self.cap = cv2.VideoCapture(0)
    def __del__(self) :
        self.sock.close()
        self.cap.release()
    def run(self):
        print("VIDEO client starts...")
        while True:
            try:
                self.sock.connect(self.ADDR)
                break
            except:
                time.sleep(3)
                continue
        print("VIDEO client connected...")
        fps = 30
        size = (int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        while self.cap.isOpened():
            ret, frame = self.cap.read()
            frame = np.bitwise_xor(frame,key)
            frame = np.array(frame,'uint8')
            data = pickle.dumps(frame)
            try:
                self.sock.sendall(struct.pack("L", len(data)) + data)
            except:
                break
            for i in range(self.interval):
                self.cap.read()

#---------------------------音频传输部分----------------------------------------
"""音频参数声明"""
CHUNK = 1024
FORMAT = pyaudio.paInt16    # 格式
CHANNELS = 2    # 输入/输出通道数
RATE = 44100    # 音频数据的采样频率
RECORD_SECONDS = 0.5    # 记录秒
p = pyaudio.PyAudio()

"""接收端"""
class Audio_Server(threading.Thread):
    def __init__(self, port, version) :
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.ADDR = ('', port)
        if version == 4:
            self.sock = socket(AF_INET ,SOCK_STREAM)
        else:
            self.sock = socket(AF_INET6 ,SOCK_STREAM)
        self.p = pyaudio.PyAudio()  # 实例化PyAudio,并于下面设置portaudio参数
        self.stream = None
    def __del__(self):
        self.sock.close()   # 关闭套接字
        if self.stream is not None:
            self.stream.stop_stream()   # 暂停播放 / 录制
            self.stream.close()     # 终止流
        self.p.terminate()      # 终止会话
    def run(self):
        print("Video server starts...")
        self.sock.bind(self.ADDR)
        self.sock.listen(1)
        conn, addr = self.sock.accept()
        print("remote Video client success connected...")
        data = "".encode("utf-8")
        payload_size = struct.calcsize("L")     # 返回对应于格式字符串fmt的结构，L为4
        self.stream = self.p.open(format=FORMAT,
                                  channels=CHANNELS,
                                  rate=RATE,
                                  output=True,
                                  frames_per_buffer = CHUNK
                                  )

        wf = wave.open(fg_audio_path,'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
            
        while True:
            while len(data) < payload_size:
                data += conn.recv(81920)
            packed_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("L", packed_size)[0]
            while len(data) < msg_size:
                data += conn.recv(81920)
            frame_data = data[:msg_size]
            data = data[msg_size:]
            frames = pickle.loads(frame_data)
            wf.writeframes(b''.join(frames))
            for frame in frames:
                self.stream.write(frame, CHUNK)
            cv2.imshow("AUDIO",noise)
            if cv2.waitKey(1) & 0xFF == 27:
                wf.close()
                break

"""发送端"""
class Audio_Client(threading.Thread):
    def __init__(self ,ip, port, version):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.ADDR = (ip, port)
        if version == 4:
            self.sock = socket(AF_INET, SOCK_STREAM)
        else:
            self.sock = socket(AF_INET6, SOCK_STREAM)
        self.p = pyaudio.PyAudio()
        self.stream = None
        print("AUDIO client starts...")
    def __del__(self) :
        self.sock.close()
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()
    def run(self):
        while True:
            try:
                self.sock.connect(self.ADDR)
                break
            except:
                time.sleep(3)
                continue
        print("AUDIO client connected...")
        self.stream = self.p.open(format=FORMAT, 
                             channels=CHANNELS,
                             rate=RATE,
                             input=True,
                             frames_per_buffer=CHUNK)
        while self.stream.is_active():
            frames = []
            for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
                data = self.stream.read(CHUNK)
                frames.append(data)
            senddata = pickle.dumps(frames)
            try:
                self.sock.sendall(struct.pack("L", len(senddata)) + senddata)
            except:
                break
#---------------------------------主函数---------------------------------------
if __name__ == '__main__':
    vclient = Video_Client(IP, PORT, LEVEL, VERSION)
    vserver = Video_Server(PORT, VERSION)
    aclient = Audio_Client(IP, PORT+1, VERSION)
    aserver = Audio_Server(PORT+1, VERSION)
    vclient.start()
    aclient.start()
    time.sleep(1)    # make delay to start server
    vserver.start()
    aserver.start()
    while True:
        time.sleep(1)
        if not vserver.is_alive() or not vclient.is_alive():
            print("Video connection lost...")
        if not aserver.is_alive() or not aclient.is_alive():
            print("Audio connection lost...")
        if not aserver.is_alive() and not aclient.is_alive():
            video = VideoFileClip(fg_video_path)
            audio = AudioFileClip(fg_audio_path)
            videoclip2 = video.set_audio(audio)
            name1 = fg_video_path.split('.', 1)[0] + "_out.mp4"
            videoclip2.write_videofile(name1)
            try:
                db = pymysql.connect(host='localhost', user='root', passwd='123456', db='mysql')
                db.autocommit(True)
                cursor=db.cursor()
                '''创建表'''
                sql=""" create table if not exists path(id int,p varchar(100)) engine=innodb charset utf8"""
                cursor.execute(sql)
                i=1
                cursor.execute("truncate table path")
                for path,dirpath ,file in os.walk(r"D:\2091211176"):
                    for f in file:
                        r1=r'(video_out.mp4)'
                        if re.findall(r1,f):
                            path=path.replace("\\","||")
                            insert="insert into path(id,p) values({},'{}')".format(i,path+"||"+f)
                            cursor.execute(insert)
                            i+=1
                cursor.execute("select * from path")
                db.commit()
                rows=cursor.fetchall()
                for r in rows:
                    print(r)
                print("complete!!!!")
            except:
                print("连接失败")
            sys.exit(0)