import asyncio
import aiohttp
from aiohttp import web
from datetime import datetime, timedelta
import threading
import curses
from queue import Queue
import time
import json
import configparser


import logging
# Logging setup
logging.basicConfig(filename='ReadyCaptcha-logging.log', filemode='a', format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.info("ReadyCaptcha application started!")


# Loading the configuration file
config = configparser.ConfigParser()
config.read('config.ini')

# Using common settings
CAPTCHA_LIFE_TIME = int(config['Settings']['captcha_life_time'])
IDLE_TIME_TO_SLEEP = int(config['Settings']['idle_time_to_sleep'])
MAX_CAPTCHA_SOLVE_TIME = int(config['Settings']['max_captcha_solve_time'])

# Using API settings
RECAPTCHA_URL = config['API']['reCaptchaUrl']
RECAPTCHA_RESULT_URL = config['API']['reCaptchaResultUrl']
API_KEY = config['API']['api_key']
PAGE_URL = config['API']['page_url']
GOOGLE_KEY = config['API']['google_key']


# Initializing variables to track statistics
request_count = 0
error_count = 0
give_token_count = 0
last_token_request = datetime.now()
dead_tokens_count = 0
valid_token = []
active_requests = 0
status = 'Active'

# Creating a message queue for data exchange between the asynchronous loop and curses thread
message_queue = Queue()

MAX_THREADS = int(input("Enter the maximum number of threads for captcha retrieval: "))

async def getCaptchaToken():
    """ Receives a captcha token and stores it in the vault """
    global request_count, error_count, active_requests
    start_time = datetime.now()
    request_count += 1
    active_requests += 1
    try:
        while True:
            async with aiohttp.ClientSession() as session:
                response = await session.get(f"{RECAPTCHA_URL}?key={API_KEY}&method=userrecaptcha&googlekey={GOOGLE_KEY}&pageurl={PAGE_URL}")
                logging.info(f"Captcha requested")
                text = await response.text()
                request_id = text.split('|')[1]
                captcha_token = ''
                start_wait_time = datetime.now()

                while not captcha_token:
                    # If we wait for the captcha to be resolved for more than a specified number of seconds, then we abort the request
                    if (datetime.now() - start_wait_time).total_seconds() > MAX_CAPTCHA_SOLVE_TIME:
                        raise asyncio.TimeoutError 

                    await asyncio.sleep(1) #Short break

                    result_response = await session.get(f"{RECAPTCHA_RESULT_URL}?key={API_KEY}&action=get&id={request_id}")
                    result_text = await result_response.text()
                    if result_text.startswith('OK'):
                        active_requests -= 1
                        logging.info(f"OK. Token received: {request_id}. Time taken to receive it: {(datetime.now() - start_time).total_seconds()} seconds")
                        captcha_token = result_text.split('|')[1]
                        valid_token.append((captcha_token, datetime.now()))
                        adjust_active_requests()
                        return  
                    elif result_text != "CAPCHA_NOT_READY":
                        logging.info(f"Error. Response received: {result_text}")
                        active_requests -= 1
                        error_count += 1  # Increasing the error counter when receiving an unexpected response
                        adjust_active_requests()
                        break 
    except asyncio.TimeoutError:
        logging.info(f"Captcha wait timeout №{request_id}. Request interrupted after 60 seconds")
        active_requests -= 1 # Reducing the active request counter
        error_count += 1  # Increasing the error counter when receiving an unexpected response
        adjust_active_requests()

    except Exception as e:
        logging.info(f"Global error. Response received: {e}")
        active_requests -= 1 # Reducing the active request counter
        error_count += 1  # Увеличиваем счётчик ошибок также при возникновении исключений
        adjust_active_requests()

def adjust_active_requests():
    """ Adapts the number of active requests as needed """
    global active_requests, MAX_THREADS 

    # If the status is "Pause", skip the iteration
    if status == "Pause":
        return  

    # Cancel the process if there are more tokens available than required
    if len(valid_token) > MAX_THREADS:
        return  

    # Running the missing number of requests
    if active_requests < MAX_THREADS:
        tasks = [getCaptchaToken() for _ in range(MAX_THREADS - active_requests)]
        asyncio.gather(*tasks)

async def maintain_tokens():
    """ Maintain tokens in a valid state """
    global last_token_request, status, valid_token, dead_tokens_count
    while True:
        current_time = datetime.now()
        
        # Removing expired tokens
        new_dead_tokens_count = sum(1 for _, token_time in valid_token if (current_time - token_time).total_seconds() >= CAPTCHA_LIFE_TIME)  
        
        # Add this amount to the total counter of expired tokens
        dead_tokens_count += new_dead_tokens_count
        
        # Deleting expired tokens
        valid_token = [(token, token_time) for token, token_time in valid_token if (current_time - token_time).total_seconds() < CAPTCHA_LIFE_TIME]

        # Changes the status if tokens have not been applied for for more than n-seconds
        if last_token_request and (current_time - last_token_request).total_seconds() > MAX_CAPTCHA_SOLVE_TIME:
            # If the time of the last request is longer than the set time, we change the status and wait
            status = "Pause"
            await asyncio.sleep(5)
            continue  # Moving on to the next iteration of the loop without requesting new tokens
        else:
            status = "Active"
            adjust_active_requests()
        
        await asyncio.sleep(5)


async def getToken(request):
    """ Issuance of live tokens """
    global last_token_request, give_token_count
    last_token_request = datetime.now()

    if print:
        give_token_count += 1
        token, _ = valid_token.pop(0)
        return web.Response(text=token)
    else:
        return web.Response(text="NO_TOKENS_AVAILABLE", status=200)

def update_ui(stdscr):
    """ Just making a beautiful interface """
    global message_queue, app
    curses.curs_set(0)  # Hide the cursor
    stdscr.nodelay(True)  # Non-blocking input mode

    # Initialization of color pairs
    if curses.has_colors():
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Зеленый текст
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Желтый текст


    while True:
        # Input processing
        key = stdscr.getch()
        if key == ord('0'):  # Check if the '0' key is pressed
            break  # Exit the loop to end the program

       # Trying to get a message from the queue
        try:
            message = message_queue.get_nowait()
        except Exception:
            message = None

        if message:
            # Update the interface if there is a new message
            stdscr.clear()
            stdscr.addstr(0, 0, "================= ReadyCaptcha ================\n")
            stdscr.addstr(f"===== RETRIEVAL, STORAGE, AND DISTRIBUTION ====\n")
            stdscr.addstr(f"============== Google reCAPTCHA V2 ============\n")
            stdscr.addstr(f"============= PROGRAM VERSION 1.3 =============\n")
            stdscr.addstr(f"============ AUTHOR: ANTON VOLNYKH ============\n\n")

            # Choosing a color pair depending on the status
            if message['status'] == 'Active':
                color_pair = curses.color_pair(1)
            elif message['status'] == 'Pause':
                color_pair = curses.color_pair(2)
            else:
                color_pair = curses.color_pair(0)  # Default color

            # Output a status bar using the selected color pair
            stdscr.addstr(f"Status: {message['status']}\n", color_pair)
            stdscr.addstr(f"Live tokens are available: {message['tokens_available']}\n\n")
            last_request_str = message['last_request_time'].strftime("%Y-%m-%d %H:%M:%S") if message['last_request_time'] else "N/A"
            stdscr.addstr(f"Gave away live tokens: {give_token_count}\n")
            stdscr.addstr(f"Expired tokens: {message['dead_tokens_count']}\n")
            stdscr.addstr(f"The last request for a token: {last_request_str}\n\n")
            
            cost_per_token = 0.03  # The cost of one token in USD
            total_cost = message['request_count'] * cost_per_token  # The total cost of tokens
            stdscr.addstr(f"Total tokens requested: {message['request_count']} ({total_cost:.2f} USD)\n")
            stdscr.addstr(f"Active requests: {active_requests}\n")

            stdscr.addstr(f"Errors when requesting a token: {message['error_count']}\n\n\n")
            stdscr.addstr("Attention: To exit, press 0. Otherwise, the terminal will break!")
            stdscr.refresh()

        # We sleep for a while to avoid excessive CPU load
        time.sleep(1)

    # Return the terminal to normal mode
    curses.nocbreak()
    curses.echo()
    curses.endwin()


    # Completion of background tasks and the main asyncio event loop
    if app is not None:
        asyncio.run(cleanup_background_tasks(app))

def run_curses():
    curses.wrapper(update_ui)

async def send_ui_updates():
    """ An auxiliary function for a beautiful interface """
    global last_token_request, request_count, error_count, valid_token, dead_tokens_count, give_token_count, active_requests
    while True:
        message = {
            'status': status,
            'tokens_available': len(valid_token),
            'last_request_time': last_token_request,
            'request_count': request_count,
            'dead_tokens_count': dead_tokens_count,
            'give_token_count': give_token_count,
            'active_requests': active_requests,
            
            'error_count': error_count
        }
        message_queue.put(message)
        await asyncio.sleep(1)

async def start_background_tasks(app):
    app['maintain_tokens'] = asyncio.create_task(maintain_tokens())
    app['send_ui_updates'] = asyncio.create_task(send_ui_updates())

async def cleanup_background_tasks(app):
    app['maintain_tokens'].cancel()
    app['send_ui_updates'].cancel()
    app['check_and_refill_tokens'].cancel()  
    await app['maintain_tokens']
    await app['send_ui_updates']
    await app['check_and_refill_tokens']  

app = None # A global variable for storing an application instance

async def seeTokens(request):
    """ The function returns a JSON response with all tokens in the repository with their receipt date. It is necessary to assess the situation from the outside. """
    tokens_list = [{'token': token, 'time': time.strftime("%Y-%m-%d %H:%M:%S")} for token, time in valid_token]
    return web.json_response(tokens_list)

async def init_app():
    global app
    app = web.Application()
    app.add_routes([web.get('/getToken', getToken), web.get('/seeToken', seeTokens)])
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    return app

if __name__ == '__main__':
    # Launching the curses interface update in a separate thread
    threading.Thread(target=run_curses, daemon=True).start()

    # Launching the aiohttp web server
    loop = asyncio.get_event_loop()
    app = loop.run_until_complete(init_app())
    web.run_app(app, host='0.0.0.0', port=8001)
