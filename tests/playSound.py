#!/usr/bin/env python
# -*-coding:utf-8 -*

import os
import pygame
import time

# initialize pygame
pygame.mixer.pre_init(44100, -16, 2, 2048)  # setup mixer to avoid sound lag
pygame.init()

capture = pygame.mixer.Sound(os.path.dirname(os.path.realpath(__file__)) + "/../camera-shutter-sound.wav")  # load sound

# Main
print "Test before play sound"
capture.play()
time.sleep(0.5)  # Wait 500 ms for the sound to coincide with the capture of the picture.
print "Test after play sound"

time.sleep(1)
print "End"
