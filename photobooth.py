#!/usr/bin/env python
# created by chris@drumminhands.com
# see instructions at
# http://www.drumminhands.com/2014/06/15/raspberry-pi-photo-booth/

import os
import glob
import time
import traceback
from time import sleep
import RPi.GPIO as GPIO
import picamera  # http://picamera.readthedocs.org/en/release-1.4/install2.html
import atexit
import sys
import socket
import pygame
from pygame.locals import QUIT, KEYDOWN, K_ESCAPE
import config  # this is the config python file config.py
import cups

####################
# Variables Config #
####################
led_pin = 27  # LED
btn_pin = 17  # pin for the start button
shutdown_btn_pin = 18  # pin for the shutdown button
print_btn_pin = 12  # pin for the print button

total_pics = 4  # number of pics to be taken
capture_delay = 1  # delay between pics
prep_delay = 3  # number of seconds at step 1 as users prep to have photo taken
gif_delay = 100  # How much time between frames in the animated gif
restart_delay = 5  # how long to display finished message before beginning a new session

# full frame of v1 camera is 2592x1944. Wide screen max is 2592,1555
# if you run into resource issues, try smaller, like 1920x1152.
# or increase memory
# http://picamera.readthedocs.io/en/release-1.12/fov.html#hardware-limits
high_res_w = config.camera_high_res_w  # width of high res image, if taken
high_res_h = config.camera_high_res_h  # height of high res image, if taken

#########################
# Variables that Change #
#########################
# Do not change these variables, as the code will change it anyway
transform_x = config.monitor_w  # how wide to scale the jpg when replaying
transfrom_y = config.monitor_h  # how high to scale the jpg when replaying
offset_x = 0  # how far off to left corner to display photos
offset_y = 0  # how far off to left corner to display photos
# how much to wait in-between showing pics on-screen after taking
replay_delay = 1
replay_cycles = 2  # how many times to show each photo on-screen after taking

#######################
# Photobooth image #
#######################
# Image ratio 4/3
image_h = 525
image_w = 700
margin = 50

# Output image ration 3/2
output_h = 1200
output_w = 1800

if not config.camera_landscape:
    tmp = image_h
    image_h = image_w
    image_w = tmp
    tmp = output_h
    output_h = output_w
    output_w = tmp
    tmp = high_res_h
    high_res_h = high_res_w
    high_res_w = tmp

################
# Other Config #
################
real_path = os.path.dirname(os.path.realpath(__file__))

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(led_pin, GPIO.OUT)  # LED
GPIO.setup(btn_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(shutdown_btn_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(print_btn_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
# for some reason the pin turns on at the beginning of the program. Why?
GPIO.output(led_pin, False)

# initialize pygame
pygame.init()
pygame.display.set_mode((config.monitor_w, config.monitor_h))
screen = pygame.display.get_surface()
pygame.display.set_caption('Photo Booth Pics')
if not config.debug_mode:
    pygame.mouse.set_visible(False)  # hide the mouse cursor
    pygame.display.toggle_fullscreen()

#############
# Functions #
#############


def cleanup():
    """
    @brief      clean up running programs as needed when main program exits
    """
    print('Ended abruptly')
    pygame.quit()
    GPIO.cleanup()


atexit.register(cleanup)


def input(events):
    """
    @brief      A function to handle keyboard/mouse/device input events
    @param      events  The events
    """
    for event in events:  # Hit the ESC key to quit the slideshow.
        if (event.type == QUIT or
                (event.type == KEYDOWN and event.key == K_ESCAPE)):
            pygame.quit()


def clear_pics(channel):
    """
    @brief      delete files in pics folder
    @param      channel  The channel
    """
    files = glob.glob(config.file_path + '*')
    for f in files:
        os.remove(f)
    # light the lights in series to show completed
    print "Deleted previous pics"
    for x in range(0, 3):  # blink light
        GPIO.output(led_pin, True)
        sleep(0.25)
        GPIO.output(led_pin, False)
        sleep(0.25)


def set_demensions(img_w, img_h):
    """
    @brief      Set variables to properly display the image on screen at right ratio
                Note this only works when in booting in desktop mode.
                When running in terminal, the size is not correct (it displays small).
                Why?

    @param      img_w  The image w
    @param      img_h  The image h
    """

    # connect to global vars
    global transform_y, transform_x, offset_y, offset_x

    # based on output screen resolution, calculate how to display
    ratio_h = (config.monitor_w * img_h) / img_w

    if (ratio_h < config.monitor_h):
        # Use horizontal black bars
        # print "horizontal black bars"
        transform_y = ratio_h
        transform_x = config.monitor_w
        offset_y = (config.monitor_h - ratio_h) / 2
        offset_x = 0
    elif (ratio_h > config.monitor_h):
        # Use vertical black bars
        # print "vertical black bars"
        transform_x = (config.monitor_h * img_w) / img_h
        transform_y = config.monitor_h
        offset_x = (config.monitor_w - transform_x) / 2
        offset_y = 0
    else:
        # No need for black bars as photo ratio equals screen ratio
        # print "no black bars"
        transform_x = config.monitor_w
        transform_y = config.monitor_h
        offset_y = offset_x = 0

    if config.debug_mode:
        print "Screen resolution debug:"
        print str(img_w) + " x " + str(img_h)
        print "ratio_h: " + str(ratio_h)
        print "transform_x: " + str(transform_x)
        print "transform_y: " + str(transform_y)
        print "offset_y: " + str(offset_y)
        print "offset_x: " + str(offset_x)


def show_image(image_path):
    """
    @brief      Display one image on screen
    @param      image_path  The image path
    """

    # clear the screen
    screen.fill((0, 0, 0))

    # load the image
    img = pygame.image.load(image_path)
    img = img.convert()

    # set pixel dimensions based on image
    set_demensions(img.get_width(), img.get_height())

    # rescale the image to fit the current display
    img = pygame.transform.scale(img, (transform_x, transfrom_y))
    screen.blit(img, (offset_x, offset_y))
    pygame.display.flip()


def clear_screen():
    """
    @brief      display a blank screen
    """
    screen.fill((0, 0, 0))
    pygame.display.flip()


def display_pics(jpg_group):
    """
    @brief      Display a group of images
    @param      jpg_group  The jpg group
    """
    for i in range(0, replay_cycles):  # show pics a few times
        for i in range(1, total_pics + 1):  # show each pic
            show_image(config.file_path + jpg_group + "-0" + str(i) + ".jpg")
            time.sleep(replay_delay)  # pause


def start_photobooth():
    """
    @brief      Define the photo taking function for when the big button is pressed
    """

    # press escape to exit pygame. Then press ctrl-c to exit python.
    input(pygame.event.get())

    #
    #  Begin Step 1
    #

    print "Get Ready"
    GPIO.output(led_pin, False)
    show_image(real_path + "/instructions.png")
    sleep(prep_delay)

    # clear the screen
    clear_screen()

    camera = picamera.PiCamera()
    if not config.camera_color_preview:
        camera.saturation = -100
    camera.iso = config.camera_iso

    # set camera resolution to high res
    camera.resolution = (high_res_w, high_res_h)

    #
    #  Begin Step 2
    #

    print "Taking pics"

    # get the current date and time for the start of the filename
    now = time.strftime("%Y-%m-%d-%H-%M-%S")

    if config.capture_count_pics:
        try:  # take the photos
            for i in range(1, total_pics + 1):
                if config.camera_landscape:
                    camera.hflip = True  # preview a mirror image
                    camera.start_preview(resolution=(config.monitor_w, config.monitor_h))
                else:
                    camera.vflip = True
                    camera.start_preview(rotation=270,resolution=(config.monitor_w, config.monitor_h))
                time.sleep(2)  # warm up camera
                GPIO.output(led_pin, True)  # turn on the LED
                filename = config.file_path + now + '-0' + str(i) + '.jpg'
                camera.stop_preview()
                if config.camera_landscape:
                    camera.hflip = False  # flip back when taking photo
                else:
                    camera.vflip = False
                os.system("aplay camera-shutter-sound.wav")  # Play sound
                camera.capture(filename)
                print(filename)
                GPIO.output(led_pin, False)  # turn off the LED
                show_image(real_path + "/pose" + str(i) + ".png")
                time.sleep(capture_delay)  # pause in-between shots
                clear_screen()
                if i == total_pics + 1:
                    break
        finally:
            camera.close()
    else:
        print("low resolution")
        # start preview at low res but the right ratio
        if config.camera_landscape:
            camera.start_preview(resolution=(config.monitor_w, config.monitor_h))
        else:
            camera.start_preview(rotation=270,resolution=(config.monitor_w, config.monitor_h))
        time.sleep(2)  # warm up camera

        try:  # take the photos
            for i, filename in enumerate(camera.capture_continuous(config.file_path + now + '-' + '{counter:02d}.jpg')):
                GPIO.output(led_pin, True)  # turn on the LED
                print(filename)
                time.sleep(capture_delay)  # pause in-between shots
                GPIO.output(led_pin, False)  # turn off the LED
                if i == total_pics - 1:
                    break
        finally:
            camera.stop_preview()
            camera.close()

    #
    #  Begin Step 3
    #

    # press escape to exit pygame. Then press ctrl-c to exit python.
    input(pygame.event.get())

    print "Creating an animated gif"

    show_image(real_path + "/processing.png")

    if config.make_gifs:  # make the gifs
        # make an animated gif
        graphicsmagick = "gm convert -delay " + \
            str(gif_delay) + " " + config.file_path + now + \
            "*.jpg " + config.file_path + now + ".gif"
        os.system(graphicsmagick)  # make the .gif

    if config.make_photobooth_image:
        print("Creating a photo booth picture")
        photobooth_image(now)

    #
    #  Begin Step 4
    #

    # press escape to exit pygame. Then press ctrl-c to exit python.
    input(pygame.event.get())

    try:
        display_pics(now)
    except Exception, e:
        tb = sys.exc_info()[2]
        traceback.print_exception(e.__class__, e, tb)
        pygame.quit()

    print "Done"

    show_image(real_path + "/finished.png")

    time.sleep(restart_delay)
    show_image(real_path + "/intro.png")
    GPIO.output(led_pin, True)  # turn on the LED


def shutdown(channel):
    """
    @brief      Shutdown the RaspberryPi
                config sudoers to be available to execute shutdown whitout password
                Add this line in file /etc/sudoers
                myUser ALL = (root) NOPASSWD: /sbin/halt
    """
    print("Your RaspberryPi will be shut down in few seconds...")
    os.system("sudo halt -p")


def photobooth_image(now):

    # Load images
    bgimage = pygame.image.load("bgimage.png")
    image1 = pygame.image.load(config.file_path + now + "-01.jpg")
    image2 = pygame.image.load(config.file_path + now + "-02.jpg")
    image3 = pygame.image.load(config.file_path + now + "-03.jpg")
    image4 = pygame.image.load(config.file_path + now + "-04.jpg")

    # Rotate Background
    if not config.camera_landscape:
        bgimage = pygame.transform.rotate(bgimage, 270)

    # Resize images
    bgimage = pygame.transform.scale(bgimage, (output_w, output_h))
    image1 = pygame.transform.scale(image1, (image_w, image_h))
    image2 = pygame.transform.scale(image2, (image_w, image_h))
    image3 = pygame.transform.scale(image3, (image_w, image_h))
    image4 = pygame.transform.scale(image4, (image_w, image_h))

    # Merge images
    bgimage.blit(image1, (margin, margin))
    bgimage.blit(image2, (margin * 2 + image_w, margin))
    bgimage.blit(image3, (margin, margin * 2 + image_h))
    bgimage.blit(image4, (margin * 2 + image_w, margin * 2 + image_h))

    pygame.image.save(bgimage, config.file_path + "/photobooth/" + now + ".jpg")


def print_image(channel):
    # Connect to cups and select printer 0
    conn = cups.Connection()
    printers = conn.getPrinters()
    printer_name = printers.keys()[0]

    # get last image
    files = filter(os.path.isfile, glob.glob(config.file_path + "/photobooth/*"))
    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

    # Lunch printing
    conn.printFile(printer_name, files[0], "PhotoBooth", {})

##################
#  Main Program  #
##################


# clear the previously stored pics based on config settings
if config.clear_on_startup:
    clear_pics(1)

# Add event listener to catch shutdown request
if config.enable_shutdown_btn:
    GPIO.add_event_detect(shutdown_btn_pin, GPIO.FALLING, callback=shutdown, bouncetime=1000)

# If printing enable, add event listener on print button
if config.enable_print_btn:
    GPIO.add_event_detect(print_btn_pin, GPIO.FALLING, callback=print_image, bouncetime=1000)

print "Photo booth app running..."
for x in range(0, 5):  # blink light to show the app is running
    GPIO.output(led_pin, True)
    sleep(0.25)
    GPIO.output(led_pin, False)
    sleep(0.25)

show_image(real_path + "/intro.png")

while True:
    # turn on the light showing users they can push the button
    GPIO.output(led_pin, True)
    # press escape to exit pygame. Then press ctrl-c to exit python.
    input(pygame.event.get())
    GPIO.wait_for_edge(btn_pin, GPIO.FALLING)
    time.sleep(config.debounce)  # debounce
    start_photobooth()
