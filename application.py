from flask import Flask, render_template, request,jsonify
from flask_cors import CORS,cross_origin
import requests
from bs4 import BeautifulSoup as bs
from urllib.request import urlopen as uReq
import logging
import functools
from urllib.error import HTTPError
import urllib.request
import time
from pymongo.mongo_client import MongoClient


logging.basicConfig(filename="scrapper.log" , level=logging.INFO)

app = Flask(__name__)



@app.route("/", methods = ['GET'])
@cross_origin()
def homepage():
    return render_template("index.html")

def get_product_links(prodCat):
    prod_links =[]
    root_link= 'https://www.amazon.in'
    for product in prodCat:
        try:
            prod_links.append( root_link + product['href'] )
        except Exception as e:
            logging.info(e)
    logging.info(prod_links)
    return prod_links


def get_customer_reviews(page_product_link):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    'accept-language': 'en-GB,en;q=0.9',}
    req = urllib.request.Request(url=page_product_link,headers=headers)
    try:
        open_prod_page = bs(uReq(req),'html.parser')
        time.sleep(0.05)
        logging.info("URLOPEN Called from -----> get_customer_reviews")
        cust_rev_boxes = open_prod_page.find_all("div",{"class":"a-section review aok-relative"})
        return page_product_link,cust_rev_boxes
    except Exception as e:
        logging.error(e)
        error = 'Unable to open product link' + str(page_product_link)
        logging.error(error)

    
    

def get_customer_details(product_link,cust_review_boxes): 
    customer_review_list = []
    for customer in cust_review_boxes:
        customer_uname = ''
        customer_rating = ''
        customer_sentiment = ''
        customer_review_l = ''
        customer_review_details ={}
        try:
            try:
                customer_uname = customer.find("div",{"class":"a-profile-content"}).span.text
            except:
                no_uname = "No username found"
                logging.info(no_uname)
            try:
                customer_rating = customer.find("i",{"data-hook":"review-star-rating"}).span.text
            except:
                no_rating = "No rating found"
                logging.info(no_rating)

            # Below code to pick review summary from span tag as it does not have any identifier
            try:
                span_tags = customer.find("a",{"class":"a-size-base a-link-normal review-title a-color-base review-title-content a-text-bold"}).find_all("span")
                sentiment_span = [span for span in span_tags if not span.has_attr('class')]
                customer_sentiment = sentiment_span[0].text
            except:
                no_sentiment = "No Sentiment summary available"
                logging.info(no_sentiment)
            try:
                customer_review_l = customer.find("div",{"class":"a-expander-content reviewText review-text-content a-expander-partial-collapse-content"}).span.text
            except:
                no_review_l = "No long review found"
                logging.info(no_review_l)

            customer_review_details = {
                "product_link"  : product_link,
                "customer_unam" : customer_uname,
                "customer_rating" : customer_rating,
                "customer_sentiment" : customer_sentiment,
                "customer_review_l" : customer_review_l
                #"customer_review_l" : "customer_review_l"            
            }
            logging.info("Review Extracted {}".format(customer_review_details))
            customer_review_list.append(customer_review_details) 
        except Exception as e:
            logging.error(e)
            error = 'Error with -----> ' + str(product_link)
            logging.error(error)
        return customer_review_list

def connectMongo():
    uri = "mongodb+srv://anoopgeorge:kiuHFSiLpW7mOyed@cluster0.jlvs1rq.mongodb.net/?retryWrites=true&w=majority"
    # Create a new client and connect to the server
    client = MongoClient(uri)
    # Send a ping to confirm a successful connection
    try:
        client.admin.command('ping')
        logging.info("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        logging.error(e)      
    return client     

@app.route("/review" , methods = ['POST' , 'GET'])
@cross_origin()
def index():
    if request.method == 'POST':
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
        'accept-language': 'en-GB,en;q=0.9',}
        searchString = request.form['content'].replace(" ","")
        app.logger.info(request.form['content'])        
        app.logger.info(searchString)
        search_url = "https://www.amazon.in/s?k=" + searchString
        req = urllib.request.Request(url=search_url,headers=headers)
        logging.info("Product link ----->" + str(search_url))
        try:
            searchResult = uReq(req)
            logging.info("URLOPEN Called from -----> index /review")
        except Exception as e:
            logging.error(e)
            return render_template('result.html')

        searchResustBs = bs(searchResult,'html.parser')
        product_Catalogue = searchResustBs.find_all("a",{"class":"a-link-normal s-underline-text s-underline-link-text s-link-style a-text-normal"})
        product_Links = get_product_links(product_Catalogue)

        product_review_list = []
        mongo_client = connectMongo()
        for product in product_Links:
            logging.info("Product parser---> {}".format(product))
            product_review = {}
            result = get_customer_reviews(product)
            if result is not None:
                product, customer_rev_boxes = result
                if customer_rev_boxes is not None:
                    customer_review_list = get_customer_details(product,customer_rev_boxes)
                    if customer_review_list is not None:
                        product_review_list = product_review_list + customer_review_list
        scraper_db = mongo_client['scraper_db']
        amazon_collection = scraper_db['amazon_collection']
        final_result = {"searchString" : searchString,
                        "product_review_list" : product_review_list
                        }
        logging.info("Push to mongoDB intiated")
        try:
            amazon_collection.insert_one(final_result)
        except Exception as e:
            logging.error(e)
        logging.info("Push to mongoDB completed")
        logging.info("log my final result {}".format(product_review_list))
        logging.shutdown()
        return render_template('result.html',reviews= product_review_list)
    else:
        return render_template('index.html')


if __name__=="__main__":
    app.run(host="0.0.0.0",debug=True)
