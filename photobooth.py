#!/usr/bin/env python
# -*-coding:utf-8 -*
#
# Initial project created by chris@drumminhands.com
# Current fork made by Pedro Amorim (contact@pamorim.fr) and Vitor Amorim

import os
import glob
import time
from time import sleep
import traceback
import RPi.GPIO as GPIO
import picamera  # http://picamera.readthedocs.org/en/release-1.4/install2.html
import atexit
import sys
import pygame
from pygame.locals import QUIT, KEYDOWN, K_ESCAPE, K_SPACE, K_p
import config  # this is the config python file config.py
import cups

####################
# Variables Config #
####################
led_pin = config.led_pin
btn_pin = config.btn_pin
shutdown_btn_pin = config.shutdown_btn_pin
print_btn_pin = config.print_btn_pin
print_led_pin = config.print_led_pin

total_pics = 4  # number of pics to be taken
capture_delay = 1  # delay between pics
prep_delay = 3  # number of seconds at step 1 as users prep to have photo taken
gif_delay = 100  # How much time between frames in the animated gif
restart_delay = 3  # how long to display finished message before beginning a new session
# how much to wait in-between showing pics on-screen after taking
replay_delay = 1
replay_cycles = 2  # how many times to show each photo on-screen after taking

# full frame of v1 camera is 2592x1944. Wide screen max is 2592,1555
# if you run into resource issues, try smaller, like 1920x1152.
# or increase memory
# http://picamera.readthedocs.io/en/release-1.12/fov.html#hardware-limits
high_res_w = config.camera_high_res_w  # width of high res image, if taken
high_res_h = config.camera_high_res_h  # height of high res image, if taken

# Preview
if config.camera_landscape:
    preview_w = config.monitor_w
    preview_h = config.monitor_h
else:
    preview_w = config.monitor_h / (4 / 3)
    preview_h = config.monitor_h

#######################
# Photobooth image    #
#######################
# Image ratio 4/3
image_h = 525
image_w = 700
margin = 50

# Output image ration 3/2
output_h = 1200
output_w = 1800

#########################
# Variables that Change #
#########################
# Do not change these variables, as the code will change it anyway
transform_x = config.monitor_w  # how wide to scale the jpg when replaying
transfrom_y = config.monitor_h  # how high to scale the jpg when replaying
offset_x = 0  # how far off to left corner to display photos
offset_y = 0  # how far off to left corner to display photos
print_counter = 0
print_error = False

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
GPIO.setup(print_led_pin, GPIO.OUT)  # LED
# for some reason the pin turns on at the beginning of the program. Why?
GPIO.output(led_pin, False)
GPIO.output(print_led_pin, False)

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


@atexit.register
def cleanup():
    """
    @brief      clean up running programs as needed when main program exits
    """
    log('Ended abruptly!')
    pygame.quit()
    GPIO.cleanup()


def clear_pics(channel):
    """
    @brief      delete files in pics folder
    @param      channel  The channel
    """
    files = glob.glob(config.file_path + '*')
    for f in files:
        os.remove(f)
    # light the lights in series to show completed
    log("Deleted previous pics")
    for x in range(0, 3):  # blink light
        GPIO.output(led_pin, True)
        GPIO.output(print_led_pin, True)
        sleep(0.25)
        GPIO.output(led_pin, False)
        GPIO.output(print_led_pin, False)
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
        transform_y = ratio_h
        transform_x = config.monitor_w
        offset_y = (config.monitor_h - ratio_h) / 2
        offset_x = 0
    elif (ratio_h > config.monitor_h):
        # Use vertical black bars
        transform_x = (config.monitor_h * img_w) / img_h
        transform_y = config.monitor_h
        offset_x = (config.monitor_w - transform_x) / 2
        offset_y = 0
    else:
        # No need for black bars as photo ratio equals screen ratio
        transform_x = config.monitor_w
        transform_y = config.monitor_h
        offset_y = offset_x = 0

    if config.debug_mode:
        log("Screen resolution debug:")
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
            sleep(replay_delay)  # pause


def make_led_blinking(pin, counter=5, duration=0.25):
    """
    @brief      Make blinking a led with oneline code
    @param      pin         Led pin
    @param      counter     Number of time the led blink
    @param      pin         Duration between blink
    """
    for x in range(0, counter):
        GPIO.output(pin, True)
        sleep(duration)
        GPIO.output(pin, False)
        sleep(duration)


def start_photobooth():
    """
    @brief      Define the photo taking function for when the big button is pressed
    """

    # connect to global vars
    global print_counter

    #
    #  Begin Step 1
    #

    log("Get Ready")
    GPIO.output(led_pin, False)
    GPIO.output(print_led_pin, False)
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

    log("Taking pics")

    # get the current date and time for the start of the filename
    now = time.strftime("%Y-%m-%d-%H-%M-%S")

    try:  # take the photos
        for i in range(1, total_pics + 1):
            filename = config.file_path + now + '-0' + str(i) + '.jpg'

            camera.hflip = True  # preview a mirror image
            camera.start_preview(resolution=(preview_w, preview_h))
            sleep(2)  # warm up camera

            GPIO.output(led_pin, True)  # turn on the LED
            camera.stop_preview()
            camera.hflip = False  # flip back when taking photo

            os.system("aplay camera-shutter-sound.wav")  # Play sound

            camera.capture(filename)
            log("Capture : " + filename)
            GPIO.output(led_pin, False)  # turn off the LED

            show_image(real_path + "/pose" + str(i) + ".png")
            sleep(capture_delay)  # pause in-between shots
            clear_screen()
            # if i == total_pics + 1:
            #     break
    except Exception, e:
        tb = sys.exc_info()[2]
        traceback.print_exception(e.__class__, e, tb)
        pygame.quit()
    finally:
        camera.close()

    #
    #  Begin Step 3
    #

    log("Creating an animated gif")

    show_image(real_path + "/processing.png")

    if config.make_gifs:  # make the gifs
        # make an animated gif
        graphicsmagick = "gm convert -delay " + \
            str(gif_delay) + " " + config.file_path + now + \
            "*.jpg " + config.file_path + now + ".gif"
        os.system(graphicsmagick)  # make the .gif

    log("Creating a photo booth picture")
    photobooth_image(now)

    # reset print counter
    print_counter = 0

    #
    #  Begin Step 4
    #

    try:
        display_pics(now)
    except Exception, e:
        tb = sys.exc_info()[2]
        traceback.print_exception(e.__class__, e, tb)
        pygame.quit()

    log("Done")

    show_image(real_path + "/finished.png")

    sleep(restart_delay)
    show_image(real_path + "/intro.png")
    # turn on the LED
    GPIO.output(led_pin, True)
    GPIO.output(print_led_pin, True)


def shutdown(channel):
    """
    @brief      Shutdown the RaspberryPi
                config sudoers to be available to execute shutdown whitout password
                Add this line in file /etc/sudoers
                myUser ALL = (root) NOPASSWD: /sbin/halt
    """
    print("Your RaspberryPi will be shut down in few seconds...")
    pygame.quit()
    GPIO.cleanup()
    os.system("sudo halt -p")


def photobooth_image(now):

    # Load images
    bgimage = pygame.image.load(real_path + "/bgimage.png")
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

    file_path_photobooth = config.file_path + "photobooth/"
    # Check directory is writable
    if (os.access(config.file_path_photobooth, os.W_OK)):
        pygame.image.save(bgimage, file_path_photobooth + now + ".jpg")
    else:
        log("ERROR path not writeable: " + file_path_photobooth)


def print_image(channel):
    # connect to global vars
    global print_counter, print_error

    # Connect to cups and select printer 0
    conn = cups.Connection()
    printers = conn.getPrinters()
    printer_name = printers.keys()[0]

    if print_error:
        log("Printer restart after error")
        # restart printer
        conn.disablePrinter(printer_name)
        sleep(2)
        conn.enablePrinter(printer_name)
        print_error = False
        GPIO.output(print_led_pin, True)  # Turn LED on
        return  # End here, printer should restart jobs pendings on the queue

    if print_counter < config.max_print:
        print_counter += 1  # increase counter

        GPIO.output(print_led_pin, False)

        # get last image
        files = filter(os.path.isfile, glob.glob(config.file_path + "photobooth/*"))
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

        # Launch printing
        conn.printFile(printer_name, files[0], "PhotoBooth", {})
        log("Launch printing request on " + printer_name + " : " + files[0])

        # Check printer status
        printerAtt = conn.getPrinterAttributes(printer_name)
        if (printerAtt['printer-state'] != 3):
            log("Printer error : (" + str(printerAtt['printer-state']) + ") " + printerAtt['printer-state-message'])
            make_led_blinking(print_led_pin, 6, 0.15)  # LED blinking
            print_error = True
        else:
            # Turn LED on
            GPIO.output(print_led_pin, True)
    else:
        # Turn LED off
        make_led_blinking(print_led_pin, 2, 0.15)  # LED blinking
        GPIO.output(print_led_pin, False)
        log("You have reach print quota for image " + " : " + files[0])


def log(text):
    print time.strftime('%Y/%m/%d %H:%M:%S') + " | " + text

##################
#  Main Program  #
##################


# clear the previously stored pics based on config settings
if config.clear_on_startup:
    clear_pics(1)

# Add event listener to catch shutdown request
if config.enable_shutdown_btn:
    GPIO.add_event_detect(shutdown_btn_pin, GPIO.FALLING, callback=shutdown, bouncetime=config.debounce)

# If printing enable, add event listener on print button
if config.enable_print_btn:
    GPIO.add_event_detect(print_btn_pin, GPIO.FALLING, callback=print_image, bouncetime=config.debounce)

# Setup button start_photobooth
# DON'T USE THREADED CALLBACKS
GPIO.add_event_detect(btn_pin, GPIO.FALLING, bouncetime=config.debounce)

log("Photo booth app running...")

# blink light to show the app is running
make_led_blinking((print_led_pin, led_pin))  # LED blinking

show_image(real_path + "/intro.png")
# turn on the light showing users they can push the button
GPIO.output(led_pin, True)
GPIO.output(print_led_pin, True)

while True:
    sleep(1)
    # Keyboard shortcuts
    for event in pygame.event.get():
        # pygame.QUIT is sent when the user clicks the window's "X" button
        if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
            sys.exit()
        # Start photobooth with key "space"
        elif event.type == KEYDOWN and event.key == K_SPACE:
            start_photobooth()
        # Print last image with key "P"
        elif event.type == KEYDOWN and event.key == K_p:
            print_image()
    # Detect event on start button
    if GPIO.event_detected(btn_pin):
        start_photobooth()
