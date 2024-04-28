
# ReadyCaptcha (reCAPTCHA V2/v3)

ReadyCaptcha is a Python-based application designed to manage and distribute Google reCAPTCHA tokens efficiently. 

This program functions like a bank for Google reCaptcha v2/v3 tokens. It solves it using the selected service tokens in advance, stores them, keeps them alive, and dispenses them to you as soon as they are needed.
It ensures you have a valid token on hand for situations where every second counts, such as registering a visit time or booking appointments.

Supported captcha solving services:
- cap.guru _(recommended)_
- 2captcha.com (aka rucaptcha.com)
- azcaptcha.com
- Anti-Captcha.com

## Features

- Dynamically manage a pool of Google reCAPTCHA tokens.
- Automatically retrieves and refreshes tokens to ensure validity.
- Provides tokens on demand and immediately replaces them.
- Discards tokens that have expired after a set duration.
- Enters a sleep mode during inactivity and reactivates upon request.
- User-friendly curses interface for monitoring and logging activity.
- Configurable thread management tailored to specific needs.

## Installation

Before running ReadyCaptcha, you need to install the required Python libraries. Ensure you have Python 3.6+ installed, then run the following commands:

```bash
pip install aiohttp asyncio datetime configparser threading curses
```

## Configuration

1. Fill out the `config.ini` file with the correct API keys and other necessary parameters as follows:

    ```ini
    [Settings]
    captcha_life_time = 55
    idle_time_to_sleep = 120
    max_captcha_solve_time = 230

    [API]
    reCaptchaUrl = "http://api.cap.guru/in.php"
    reCaptchaResultUrl = "http://api.cap.guru/res.php"
    api_key = "YOUR_API_KEY"
    page_url = "https://www.example.com"
    google_key = "YOUR_GOOGLE_SITE_KEY"
    ```

    Replace `YOUR_API_KEY` and `YOUR_GOOGLE_SITE_KEY` with your actual API keys.

I recommend using cap.guru <https://cap.guru/en/regen/?ref=148154> as it currently offers the most cost-effective captcha solving service. However, you can easily use other services like `2captcha.com`, `azcaptcha.com` or `Anti-Captcha.com
` as well. All of these have a similar API structure, and you simply need to specify their in.php and res.php in the config.ini file.

## Usage

To start the server and the interface, run the following command in your terminal:

```bash
python ready_captcha.py
```

To request a token, use the following URL:

```url
http://localhost:8001/getToken
```

This will provide a live token if available. If no tokens are available, it will return `NO_TOKENS_AVAILABLE`.

## Examples of Using the Service

### Python Example
Here's how you can retrieve a token using Python with the `requests` library. This script attempts to get a token and retries after 5 minutes if none are available.

```python
import requests
import time

url = "http://localhost:8001/getToken"

while True:
    response = requests.get(url)
    token = response.text
    if token != "NO_TOKENS_AVAILABLE":
        reCaptchaV2 = token
        break
    else:
        # Wait for 3 seconds before retrying
        time.sleep(3)
```

### JavaScript Example
Below is an example of how to request a token using JavaScript with the `fetch` API.

```javascript
const url = "http://localhost:8001/getToken";

function getToken() {
    fetch(url)
        .then(response => response.text())
        .then(token => {
            if (token !== "NO_TOKENS_AVAILABLE") {
                console.log("Token received: " + token);
                // Use the token as needed
            } else {
                console.log("No tokens available, retrying in 3 seconds...");
                setTimeout(getToken, 3000); // Retry after 3 seconds
            }
        })
        .catch(error => console.error('Error fetching token:', error));
}

getToken();
```
These examples should guide users in integrating your service with Python and JavaScript applications effectively.

## Development

This project is under development. If you have suggestions or feedback, please email them to ant.volnyh@gmail.com.

## License

ReadyCaptcha is open-source software licensed under the MIT license.
