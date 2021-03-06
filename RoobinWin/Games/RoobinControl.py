   
#!/usr/bin/env python3
import os
import re
import sys
import wave
import time
import serial
import random
import pyaudio
import threading
import subprocess
import contextlib
# from lxml import etree #Delete
from subprocess import call
import serial.tools.list_ports
from os import path,getcwd,system
from future.backports.http.client import BadStatusLine
from SimpleWebSocketServer import SimpleWebSocketServer,WebSocket


# define constants for motors
HEADNOD = 6
HEADTURN = 1
EYETURN = 2
LIDBLINK = 3
TOPLIP = 4
BOTTOMLIP = 5
EYETILT = 0


FORMAT = pyaudio.paInt16
RATE = 44100

# array to hold 
sensors = [0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0]

# define a module level variable for the serial port
port=""
# define library version
version ="2.85"
global writing, voice, synthesizer
# flag to stop writing when writing for threading
writing = False
# global to set the params to speech synthesizer which control the voice
voice = ""
# Global flag to set synthesizer, default is festival, espeak also supported.
# If it's not festival then it needs to support -w parameter to write to file e.g. espeak or espeak-NG
synthesizer = "festival"

ser = None

# Function to check if a number is a digit including negative numbers
def is_digit(n):
    try:
        int(n)
        return True
    except ValueError:
        return  False
# speak depending on synthesizer

def init(portName):
    # pickup global instances of port, ser and sapi variables   
    global port,ser
    
    # Search for the Roobin serial port 
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        # print ("p0:" + p[0])
        # print ("p1:" + p[1])
        # If port has Roobin connected save the location
        if portName in p[1]:
            port = p[0]
            print ("Roobin found on port:" + port)
        elif portName in p[0]:
            port = p[0]
            print ("Roobin found on port:" + port)

    # If not found then try the first port
    if port == "":
        for p in ports:
            port = p[0]
            print ("Roobin probably found on port:" + port)
            break
            
    if port == "":
        print ("Roobin port " + portName + " not found")
        return False

    # Open the serial port
    ser = serial.Serial(port, 19200)

    # Set read timeout and write timeouts to blocking
    ser.timeout = None
    ser.write_timeout = None

    # Make an initial call to Festival without playing the sound to check it's all okay
    text = "Hi"
        
    # Create a bash command with the desired text. The command writes two files, a .wav with the speech audio and a .txt file containing the phonemes and the times.
    #speak (text)

    return True

# Startup Code

# xml file for motor definitions
# dir = "./"
# file = os.path.join(dir, 'MotorDefinitionsv21.omd')

# tree = etree.parse(file)
# print(tree)
# root = tree.getroot()
# print("-----------------")
# print(root)

# Motor Definitions

root = [{"Name":"HeadTurn", "Min":"0", "Max":"1000", "Motor":"1", "Speed":"40", "Reverse":"False", "Acceleration":"60", "RestPosition":"5", "Avoid":""},
		{"Name":"HeadNod", "Min":"140", "Max":"700", "Motor":"0", "Speed":"0", "Reverse":"True", "Acceleration":"60", "RestPosition":"5", "Avoid":""},
		{"Name":"EyeTurn", "Min":"380", "Max":"780", "Motor":"2", "Speed":"0", "Reverse":"False", "Acceleration":"0", "RestPosition":"5", "Avoid":""},
		{"Name":"EyeTilt", "Min":"520", "Max":"920", "Motor":"6", "Speed":"0", "Reverse":"False", "Acceleration":"30", "RestPosition":"5", "Avoid":""},
		{"Name":"TopLip", "Min":"0", "Max":"550", "Motor":"4", "Speed":"0", "Reverse":"True", "Acceleration":"0", "RestPosition":"5", "Avoid":"BottomLip"},
		{"Name":"BottomLip", "Min":"0", "Max":"550", "Motor":"5", "Speed":"0", "Reverse":"True", "Acceleration":"0", "RestPosition":"5", "Avoid":"TopLip"},
		{"Name":"LidBlink", "Min":"35", "Max":"305", "Motor":"3", "Speed":"0", "Reverse":"False", "Acceleration":"0", "RestPosition":"10", "Avoid":""},
		{"Name":"MouthOpen", "Min":"80", "Max":"460", "Motor":"7", "Speed":"0", "Reverse":"False", "Acceleration":"0", "RestPosition":"10", "Avoid":""}]

# Put motor ranges into lists
motorPos = [11,11,11,11,11,11,11,11]
motorMins = [0,0,0,0,0,0,0,0]
motorMaxs = [0,0,0,0,0,0,0,0]
motorRev = [False,False,False,False,False,False,False,False]
restPos = [0,0,0,0,0,0,0,0]
isAttached = [False,False,False,False,False,False,False,False]


# For each line in motor defs file
for child in root:
    indexStr = child["Motor"]
    index = int(indexStr)
    motorMins[index] = int(int(child["Min"])/1000*180)
    motorMaxs[index] = int(int(child["Max"])/1000*180)
    motorPos[index] = int(child["RestPosition"])
    restPos[index] = int(child["RestPosition"])
    if child["Reverse"] == "True":
        rev = True
        motorRev[index] = rev
    else:
        rev = False
        motorRev[index] = rev
        
# initialize with any port that has Arduino in the name
try:
    init("CH340")
except :
    print("Came up without Arduino.")
    pass

def recovery_util():
    try:
        ser.close()
    except:
        pass
    
    print("Want to open again now : ")
    time.sleep(2)
    print("3")
    print("2")
    print("1")
    try:
        init("CH340")
    except :
        print("Came up without Arduino.")
        pass

# Function to move Roobin's motors. Arguments | m (motor) → int (0-6) | pos (position) → int (0-10) | spd (speed) → int (0-10) **eg move(4,3,9) or move(0,9,3)**
def move(m, pos, spd=3):
    
    # Limit values to keep then within range
    pos = limit(pos)
    spd = limit(spd)
    absPos = pos

    # Reverse the motor if necessary   
    if motorRev[m]:
        pos = 10 - pos

    # Attach motor       
    attach(m)
    
    # Ensure the lips do not crash into each other. 
    # if m == TOPLIP and pos + motorPos[BOTTOMLIP] > 10:
    #     pos = 10 - motorPos[BOTTOMLIP]

    # if m == BOTTOMLIP and pos + motorPos[TOPLIP] > 10:
    #     pos = 10 - motorPos[TOPLIP]
        
    # Convert position (0-10) to a motor position in degrees

    # Only for Jaws babe :)
    
    # absPos = int(getPos(m,pos))

    # Scale range of speed
    spd = (250/10)*spd

    # Construct message from values
    msg = "m0"+str(m)+","+str(absPos)+","+str(spd)+"\n"

    # Write message to serial port
    serwrite(msg)

    # Update motor positions list
    motorPos[m] = pos  
 
# Function to write to serial port
# The serial port write_timeout doesn't work reliably on multiple threads so this
# blocks using a global variable
def serwrite(s):
    global writing
    # wait until previous write is finished
    while (writing):
        pass
        # print ('waiting on write')

    writing = True
    # print("=======================================")
    # print()
    # print(s.encode('latin-1'))
    # print()
    # print()
    # print(s)
    # print()
    # print("=======================================")
    try:
        ser.write(s.encode('latin-1')) 
    except:
        pass
    writing = False
    
# Function to attach Roobin's motors. Argument | m (motor) int (0-6)
def attach(m):
    if isAttached[m] == False:
        # Construct message
        msg = "a0"+str(m)+"\n"

        # Write message to serial port
        serwrite(msg)

        # Update flag
        isAttached[m] = True
    
# Function to detach Roobin's motors.  Argument | m (motor) int (0-6)
def detach(m):
    msg = "d0"+str(m)+"\n"    
    serwrite(msg)
    isAttached[m] = False
    
# Function to find the scaled position of a given motor. Arguments | m (motor) → int (0-6) | pos (position) → int (0-10) | Returns a position
def getPos(m, pos):
    mRange = motorMaxs[m]-motorMins[m]
    scaledPos = (mRange/10)*pos
    return scaledPos + motorMins[m]

# Function to set a different speech synthesizer - defaults to festival
def setSynthesizer(params):
    global synthesizer
    synthesizer = params
        
# Function to limit values so they are between 0 - 10
def limit(val):
     if int(val) > 50:
       return 50
     elif int(val) < 0: 
        return 0
     else:
        return val
   
# Function to move Roobin's lips in time with speech. Arguments | phonemes → list of phonemes[] | waits → list of waits[]
def moveSpeech(phonemes, times):
    startTime = time.time()
    timeNow = 0
    totalTime = times[len(times)-1]
    currentX = -1
    while timeNow < totalTime:     
        timeNow = time.time() - startTime
        for x in range (0,len(times)):
            if timeNow > times[x] and x > currentX:                
                posTop = phonememapTop(phonemes[x])
                posBottom = phonememapBottom(phonemes[x])
                move(TOPLIP,posTop,10)
                move(BOTTOMLIP,posBottom,10)
                currentX = x
    move(TOPLIP,5)
    move(BOTTOMLIP,5)
    
# Function to move Roobin's lips in time with speech. Arguments | phonemes → list of phonemes[] | waits → list of waits[]
def moveSpeechFest(phonemes, times):
    startTime = time.time()
    timeNow = 0
    totalTime = times[len(times)-1]
    currentX = -1
    while timeNow < totalTime:     
        timeNow = time.time() - startTime
        for x in range (0,len(times)):
            if timeNow > times[x] and x > currentX:                
                posTop = phonememapTopFest(phonemes[x])
                posBottom = phonememapBottomFest(phonemes[x])
                move(TOPLIP,posTop,10)
                move(BOTTOMLIP,posBottom,10)
                currentX = x
    move(TOPLIP,5)
    move(BOTTOMLIP,5)

# Function mapping phonemes to top lip positions. Argument | val → phoneme | returns a position as int
def phonememapTopFest(val):
    return {
        'p': 5,
        'b': 5,
        'm': 5,
        'ae': 7,
        'ax': 7,
        'ah': 7,
        'aw': 10,
        'aa': 10,
        'ao': 10,
        'ow': 10,
        'ey': 7,
        'eh': 7,
        'uh': 7,
        'ay': 7,
        'h': 7,
        'er': 8,
        'r': 8,
        'l': 8,
        'y': 6,
        'iy': 6,
        'ih': 6,
        'ix':6,
        'w': 6,
        'uw': 6,
        'oy': 6,
        's': 5,
        'z': 5,
        'sh': 5,
        'ch': 5,
        'jh': 5,
        'zh': 5,
        'th': 5,
        'dh': 5,
        'd': 5,
        't': 5,
        'n': 5,
        'k': 5,
        'g': 5,
        'ng': 5,
        'f': 6,
        'v': 6
}.get(val, 5)

# Function mapping phonemes to lip positions. Argument | val → phoneme | returns a position as int
def phonememapBottomFest(val):
    return {
        'p': 5,
        'b': 5,
        'm': 5,
        'ae': 8,
        'ax': 8,
        'ah': 8,
        'aw': 5,
        'aa': 10,
        'ao': 10,
        'ow': 10,
        'ey': 7,
        'eh': 7,
        'uh': 7,
        'ay': 7,
        'h': 7,
        'er': 8,
        'r': 8,
        'l': 8,
        'y': 6,
        'iy': 6,
        'ih': 6,
        'ix':6,
        'w': 6,
        'uw': 6,
        'oy': 6,
        's': 6,
        'z': 6,
        'sh': 6,
        'ch': 6,
        'jh': 6,
        'zh': 6,
        'th': 6,
        'dh': 6,
        'd': 6,
        't': 6,
        'n': 6,
        'k': 6,
        'g': 6,
        'ng': 6,
        'f': 5,
        'v': 5
}.get(val,5) 

# DOT MATRIX MOUTHING--------------------------------------------

def moveSpeechMouth(phonemes, times, name):

    # duration = eyed3.load(name).info.time_secs
    fname = name
    with contextlib.closing(wave.open(fname,'r')) as f:
        frames = f.getnframes()
        rate = f.getframerate()
        duration = frames / float(rate)
        print(f"{name} : {duration}")
    print("=-=-=-=-=-=-=-=-=-=-=-=-=")
    # print(duration)
    start = time.time()
    # print()
    # print(start)
    # print()
    # print()
    stop = start + duration*0.91
    while time.time() < stop:
            ph = random.randint(1,3)
            mouthing(ph)

    for i in range(10):
        mouthing(1)
        mouthing(1)
        mouthing(1)
    time.sleep(0.5)
    mouthing(1)
    mouthing(1)

def phonemes_gen(vcname):
    phonemes = []
    times = []
    return phonemes, times 

def mouthing(ph):
    msg = "p0"+str(ph)+"\n"
    serwrite(msg)

# DOT MATRIX MOUTHING--------------------------------------------
          
# Function mapping phonemes to top lip positions.
def phonememapTop(val):
        
    return 5 + val / 2;

# Function mapping phonemes to top lip positions.
# Bottom lip is 2/3 the movement of top lip
def phonememapBottom(val):
    return 5 + val / 3;

# Wait function
def wait(seconds):
    time.sleep(float(seconds))
    return

# Close the connection.
def close():       
    for x in range(0, len(motorMins)-1):
        detach(x)   

# Reset Roobin back to start position

def reset():
    for x in range(0,len(restPos)-1):
        move(x,restPos[x]) 

# Attach all motors.

def adjust():
    for i in range(7):
        move(i, restPos[i], 2)
        wait(1)

def adjust_again():
    for i in range(7):
        move(i, 2, 2)
        wait(1)

def robotWait(secs):
    msg = "b0"+str(secs)+"\n"
    serwrite(secs)

def eye(side="both", statement="neutral", delay="2"):
    spd = 0
    # stateSel = {"blink_left":1 , "blink": 2 , "blink_right" : 3, "look_left": 4 , "look_right" : 5 , "neutral" : 6 }
    stateSel = {"looksides":1 , "blink": 2 , "neutral" : 3,
                "rightArrow": 4, "leftArrow": 5, "upArrow": 6, "downArrow": 7,
                "full_on":8
                 }
    sideSel =  {"right":1 , "left" : 2 , "both" : 3}
	# right --> 01 # left  --> 10 # both  --> 11
    msg = "q"+str(sideSel[side])+str(stateSel[statement])+str(delay)+","+str(spd)+"\n"
	# Write message to serial port
    serwrite(msg)
    # robotWait(3)

#Changes eyes form
def change_eye_command(eye_state, eye_side):
    msg = "z" + str(eye_state) + str(eye_side) + "," + "\n"
    serwrite(msg)

#Changes mouth form
def change_mouth_command(mouth_state):
    msg = "f" + str(mouth_state) + "," + "\n"
    serwrite(msg)


"""

COMMAND PREFIXES USED:    a c d e h i k l m n p q r t v w x z

"""





if __name__ == "__main__":

    adjust()
    # wait(5)
    reset()

    try:
        print("here")
        # move(5,1,10)
        # move(5,5,10)
        # move(5,10,3)
        # wait(2)
    except KeyboardInterrupt:
        sys.exit(0)

    

