# Amazon Product Search API Integration

This project uses Oxylabs API to search for products on Amazon.

## Setup

1. Clone this repository
2. Create a `.env` file in the root directory and add your Oxylabs credentials:
```
OXYLABS_USERNAME=your_username_here
OXYLABS_PASSWORD=your_password_here
```
3. Get your Oxylabs credentials from [Oxylabs](https://oxylabs.io/)

## Usage

Run the main script:
```bash
python main.py
```

Or run the web application:
```bash
python app.py
```

This will start a web server where you can search for Amazon products using the Oxylabs API. The application allows you to:

1. Search for products on Amazon
2. View detailed product information
3. Export results to Excel
4. Enhance product images with AI

## Features

- Amazon product search
- Product data extraction
- AI-powered image enhancement
- Excel export functionality 