from dotenv import load_dotenv
from datetime import datetime, timedelta, UTC
from pymongo import MongoClient

from flask import Flask, render_template, redirect, url_for, request, jsonify
from pyzbar.pyzbar import decode
from PIL import Image
import requests
from pprint import pprint
import os

load_dotenv()

#   client = MongoClient("mongodb://localhost:27017/")
client = MongoClient(os.getenv("MONGO_URI"), tls=True)
db = client["testdb"]
foodtracking_col = db["food_trackings"]
user_collection = db["users"]
#   db = client["food_app"]
#   collection = db["entries"]

try:
    client.admin.command("ping")
    print("MongoDB connection successful!")
except Exception as e:
    print("MongoDB connection failed:", e)


API_KEY = os.getenv("USDA_API_KEY")
url = "https://api.nal.usda.gov/fdc/v1/foods/search"
KEYWORDS = ("energy", "protein", "fat", "sugar", "carbohydrate", "water", "vitamin", "cholesterol", "sodium", "fiber", "calcium", "iron", "potassium", "zinc", "magnesium", "phosphorus", "selenium", "thiamin", "theobromine", "caffeine", "riboflavin", "copper", "niacin")
UNITS = ("KCAL", "G", "MG", "UG", "IU")

app = Flask(__name__)

def servingInfo(fd_data):
    
    serving = {
        "text": fd_data["householdServingFullText"],
        "size": fd_data["servingSize"],
        "unit": fd_data["servingSizeUnit"]
    }
    
    return serving

def foodPortionsInfo(fd_data):
    portions = []
    
    #foodPortions does not exist for fdcId: 170912, 170915
    for portion in fd_data.get("foodPortions", []):
        #print(portion["gramWeight"])
        #print(portion["amount"])
        #print(portion["modifier"])
        
        p = {}
        '''
        p["text"] = portion["modifier"]
        p["size"] = portion["amount"]
        p["unit"] = portion["gramWeight"]
        '''
        desc = portion.get("portionDescription", "")
        amount = str(portion.get("amount", ""))
        modifier = portion.get("modifier", "")
        
        p["text"] = desc if desc else f"{amount} {modifier}"
        p["size"] = portion.get("gramWeight", 0)
        p["unit"] = "g"
        
        portions.append(p)
    
    return portions

def get_food_data(data, food_type="Branded"):
    #################### NEEDS TO BE WORKED ON ##########################
    food_facts_data = []
    
    for food in data.get("foods", []):
        nutrient_data = []
        
        food_id = food["fdcId"]  
        print("fdcId:", food_id, " == ", food["description"], "-->", food["foodCategory"])
        
        fdcId_url = f"https://api.nal.usda.gov/fdc/v1/food/{food_id}?api_key={API_KEY}"
        res = requests.get(fdcId_url)
        
        # This shows the full URL with all query string parameters
        print("fdcId URL:", res.url)
        
        fdcId_data = res.json()
        #   pprint(fdcId_data)
        
        portions_data = [{"text": "Custom", "size": 100, "unit": fdcId_data.get("servingSizeUnit", "g")}] ########################## put 100g (Default) in here
        
        if food_type == "Branded":
            portions_data.append(servingInfo(fdcId_data))
            
        elif food_type == "SR Legacy":
            portions_data += foodPortionsInfo(fdcId_data)
    
        for n in food.get("foodNutrients", []):
            for kw in KEYWORDS:
                if kw in n["nutrientName"].lower() and n["unitName"] in UNITS:
                    #   print(n["nutrientName"], n["value"], n["unitName"])
                    
                    n_item = {}
                    n_item["nutrientName"] = "Calories" if n["nutrientName"] == "Energy" else n["nutrientName"]
                    n_item ["value"] = n["value"]
                    n_item["unitName"] = n["unitName"].lower()
                    
                    if n_item["nutrientName"] == "Calories":
                        nutrient_data.insert(0, n_item)
                    else:
                        nutrient_data.append(n_item)
        
        if food_type == "Branded":            
            food_facts_data.append({
                "fdcId": food_id,
                "description": food.get("description", ""),
                "category":  food.get("foodCategory", ""),
                "brand":    food.get("brandName", ""),
                "portions": portions_data,
                "nutrients": nutrient_data
            })
        elif food_type == "SR Legacy":
            food_facts_data.append({
                "fdcId": food_id,
                "description": food.get("description", ""),
                "category":  food.get("foodCategory", ""),
                "portions": portions_data,
                "nutrients": nutrient_data
            })

        print()
    
    #   pprint(food_facts_data)
    return food_facts_data
    #################### NEEDS TO BE WORKED ON ##########################

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/find-food")
def find_food():
    return render_template("find_food.html")


@app.route("/barcode-search", methods=['GET', 'POST'])
def barcode_search():
    
    if request.method == 'POST':
            food_type="Branded"
            
            # Get text input
            gtin_upc = request.form.get('gtin-upc')  # for the text input
            
            # Get uploaded file
            photo = request.files.get('photo-barcode')  # for the file input
            
            if gtin_upc:
             
                print(f"You Typed Barcode: {gtin_upc}\n")
                print(type(gtin_upc))
                
                if (not gtin_upc.isdigit()) or (not (len(gtin_upc) in (8, 12, 13, 14))):
                    print("invalid format")
                    return redirect(url_for('find_food'))
                
                params = {
                    "api_key": API_KEY,
                    "query": gtin_upc,
                    "dataType": [food_type],
                    "pageSize": 1,
                    "pageNumber": 1
                }
                
                response = requests.get(url, params=params)
                
                # This shows the full URL with all query string parameters
                print("Full URL:", response.url)
                
                print("STATUS:", response.status_code)
                #print("TEXT:", response.text[:500])   # show first 500 chars

                # Convert response to JSON
                data = response.json()
                #pprint(data)
                
                #################### NEEDS TO BE WORKED ON ##########################
                food_facts_data = get_food_data(data, food_type)
                pprint(food_facts_data)
                #################### NEEDS TO BE WORKED ON ##########################
                
                return render_template('find_food.html', food_type=food_type, food_facts_data=food_facts_data)
            
            # Check if a file was uploaded
            if photo and photo.filename != '':
                # File exists
                filename = photo.filename
                print(f"Photo uploaded successfully: {filename}")
                
                my_barcode = read_barcode(photo.stream)
                
                print(f"Barcode Scanned: {my_barcode}\n")
                
                if my_barcode == None:
                    return redirect(url_for('find_food'))
                
                params = {
                    "api_key": API_KEY,
                    "query": my_barcode,
                    "dataType": [food_type],
                    "pageSize": 1,
                    "pageNumber": 1
                }
                
                response = requests.get(url, params=params)
                
                # This shows the full URL with all query string parameters
                print("Full URL:", response.url)
                
                print("STATUS:", response.status_code)
                #print("TEXT:", response.text[:500])   # show first 500 chars

                # Convert response to JSON
                data = response.json()
                #pprint(data)
                
                #################### NEEDS TO BE WORKED ON ##########################
                food_facts_data = get_food_data(data, food_type)
                pprint(food_facts_data)
                #################### NEEDS TO BE WORKED ON ##########################
                
                return render_template('find_food.html', food_type=food_type, food_facts_data=food_facts_data)
            else:
                # No file uploaded
                print("No photo was uploaded.")
                
    return redirect(url_for('find_food'))

@app.route("/search-food", methods=['GET'])
def search_food_name():
    
    #value of a query string parameter 'search' from the URL
    query = request.args.get("food-name", "").strip()
    if not query:
        return "Please provide a food name"
    
    #page_number = request.args.get("page-number")
    page_number = request.args.get("page-number", default=1, type=int)
    page_size = request.args.get("page-size")
    
    selected_type = request.args.get("food-type")
    
    food_type =  "SR Legacy" if selected_type == "general" else "Branded"
    
    print(f"You entered: {query}\n")
    
    params = {
        "api_key": API_KEY,
        "query": query,
        "dataType": [food_type],
        "pageSize": page_size,
        "pageNumber": page_number
    }
    
    response = requests.get(url, params=params)
    
    # This shows the full URL with all query string parameters
    print("Full URL:", response.url)
    
    print("STATUS:", response.status_code)
    #print("TEXT:", response.text[:500])   # show first 500 chars

    # Convert response to JSON
    data = response.json()
    #pprint(data["foods"])
    
    total_results = data.get("totalHits", 0)
    #################### NEEDS TO BE WORKED ON ##########################
    food_facts_data = get_food_data(data, food_type)
    #################### NEEDS TO BE WORKED ON ##########################
    
    return render_template('find_food.html', total_results=total_results, food_type=food_type, food_facts_data=food_facts_data, foodname=query, page_number=page_number, page_size=page_size, selected_type=selected_type)


def get_food_trackings_weekly():
    user = user_collection.find_one({"username": "User1"})
    
    user_id = user['_id']
    print(f"user_id: {user_id}")

    one_week_ago = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")

    today = datetime.now(UTC).strftime("%Y-%m-%d")

    docs = foodtracking_col.find({
        "user": user_id,
        "date": {
            "$gte": one_week_ago,
            "$lte": today
        }
    })

    print("Weekly STARTS")
    for doc in docs:
        pprint(doc["date"])
    print("Weekly ENDS")  

@app.route("/save-entry", methods=["POST"])
def save_entry():
    
    # access and convert form data to a normal dictionary
    #   form_dict = request.form.to_dict()
    
    #   pprint(form_dict)  # This prints all submitted form fields
    
    user = user_collection.find_one({"username": "User1"})
    
    user_id = user['_id']
    print(f"user_id: {user_id}")
    
    # Basic fields
    food_items = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "description": request.form.get("description"),
        "category": request.form.get("category"),
        "brand": request.form.get("brand"),
        "portion": {
            "amount": float(request.form.get("amount", 0)),
            "unit": request.form.get("unit")
        },
        "quantity": int(request.form.get("quantity", 1))
    }

    # Multi-value fields for nutrients
    nutrient_names = request.form.getlist("nutrient_name[]")
    nutrient_values = request.form.getlist("nutrient_value[]")
    nutrient_units = request.form.getlist("nutrient_unit[]")

    # Build the nutrients array
    nutrients = []
    for name, value, unit in zip(nutrient_names, nutrient_values, nutrient_units):
        nutrients.append({
            "name": name,
            "value": float(value),
            "unit": unit
        })

    food_items["nutrients"] = nutrients

    # Print for debugging
    pprint(food_items)
    
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    print(f"Today Date: {today}")
    
    foodtracking_col.update_one(
        {"user": user_id, "date": today},
        {
            "$setOnInsert": {
                "user": user_id,
                "date": today
            },
            "$push": {
                "food_items": food_items
            }
        },
        upsert=True
    )
    
    '''
    return jsonify({
        "message": "Entry saved to MongoDB!"
    })
    '''
    return redirect(url_for('find_food'))

#######################  EDIT THIS  #############################
@app.route("/dashboard")
def dashboard():
    '''
    user = user_collection.find_one({"username": "User1"})
    
    user_id = user['_id']
    print(f"user_id: {user_id}")

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    print(f"Today is {today}")

    food_tracking_data = foodtracking_col.find_one({"user": user_id, "date": today })
    
    food_tracking_data["_id"] = str(food_tracking_data["_id"])
    food_tracking_data["user"] = str(food_tracking_data["user"])
    
    pprint(food_tracking_data)
    '''
    
    user = user_collection.find_one({"username": "User1"})
    
    user_id = user['_id']
    print(f"user_id: {user_id}")

    one_week_ago = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")

    today = datetime.now(UTC).strftime("%Y-%m-%d")

    docs = foodtracking_col.find({
        "user": user_id,
        "date": {
            "$gte": one_week_ago,
            "$lte": today
        }
    })
    
    food_tracking_data = []
    nutrient_name_labels = []
    nutrient_unit_labels = []
    
    for doc in docs:
        doc["_id"] = str(doc["_id"])
        doc["user"] = str(doc["user"])
        food_tracking_data.append(doc)
        
        for f_item in doc["food_items"]:
            for n_item in f_item["nutrients"]:
                if not (n_item["name"] in nutrient_name_labels):
                    nutrient_name_labels.append(n_item["name"])
                    nutrient_unit_labels.append(n_item["unit"])
    
    return render_template("dashboard2.html", food_tracking_data=food_tracking_data, nutrient_name_labels=nutrient_name_labels, nutrient_unit_labels=nutrient_unit_labels)


def read_barcode(image_path):
    image = Image.open(image_path)
    barcodes = decode(image)

    if not barcodes:
        print("No barcode found.")
        return
    
    for barcode in barcodes:
        barcode_data = barcode.data.decode("utf-8")
        #print(f"Barcode Data: {barcode_data}")
        return barcode_data[1:]

    '''
    for barcode in barcodes:
        barcode_data = barcode.data.decode("utf-8")
        barcode_type = barcode.type

        print(f"Barcode Type: {barcode_type}")
        print(f"Barcode Data: {barcode_data}")
    
        # UPC-A / EAN-13 are common GTIN formats
        if barcode_type in ("UPC-A", "EAN13", "EAN-13"):
            print("This is a GTIN/UPC barcode.")
    '''

# !TESTING FUNCTION ONLY!
def apiUSDA(barcode):
    url = "https://api.nal.usda.gov/fdc/v1/foods/search"

    params = {
        "api_key": API_KEY,
        "query": barcode,
        "pageSize": 1
    }

    response = requests.get(url, params=params)

    # Convert response to JSON
    data = response.json()
    
    return data

if __name__ == "__main__":
    #   app.run()
    app.run(host="0.0.0.0", port=5000)
