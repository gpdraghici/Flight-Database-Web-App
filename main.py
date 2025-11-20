from flask import Flask, render_template, session, request, url_for, redirect, flash, g
from datetime import datetime
import sqlite3
from decimal import Decimal


# SQLite database file
DATABASE = 'flying_schema.db'

def get_db():
    #Get database connection with right settings 
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE, timeout=10.0, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    #Close db connection
    db = g.pop('db', None)
    if db is not None:
        db.close()

app = Flask(__name__)

app.secret_key = 'gabriel'

# Set close_db to run after each request
app.teardown_appcontext(close_db)

# Redirect to homepage
@app.route('/')
def index():
    return redirect(url_for('homepage'))

#function to organize data from query to use for display
def organizeData(results, organizeType):
    flightInfoList= []
    for flight in results:


        arrivalDateTime = flight['arrival']
        departureDateTime = flight['departure']
        arrivalDate = arrivalDateTime.strftime("%B %d, %Y")
        arrivalTime = arrivalDateTime.strftime("%I:%M %p").lstrip("0").replace(":00", "")
        departureDate = departureDateTime.strftime("%B %d, %Y")
        departureTime = departureDateTime.strftime("%I:%M %p").lstrip("0").replace(":00", "")
        flightInfo = {
            "airline": flight['airline_name'],
            "departureLocation": flight['airport_code'],
            "arrivalDate": arrivalDate,
            "arrivalTime": arrivalTime,
            "departureDate": departureDate,
            "departureTime": departureTime,
            "arrivalLocation": flight['arrival_airport_code'],
            "basePrice": flight['base_price'],
            "status": flight['Status'],
            "flightNum": flight['flight_num']
        }

        #calculate price
        db = get_db(); cursor = db.cursor()
        query = """SELECT COUNT(Ticket.ticket_id) as tickets
                FROM flight JOIN ticket ON flight.flight_num = ticket.flight_num
                WHERE flight.flight_num = ?
                GROUP BY flight.flight_num"""
        query2 = """SELECT Airplane.num_seats as capacity
                FROM flight JOIN airplane ON flight.airplane_id = airplane.airplane_id
                WHERE flight.flight_num = ?
                GROUP BY flight.flight_num"""
        cursor.execute(query, (flightInfo['flightNum'],))
        ticketResult = cursor.fetchall()
        if ticketResult:
            tickets = ticketResult[0]['tickets']
        else:
            tickets = 0
        cursor.execute(query2, (flightInfo['flightNum'],))
        capacityResult = cursor.fetchall()
        if capacityResult:
            capacity = capacityResult[0]['capacity']
        cursor.close()
        if tickets > 0.8 * capacity:
            flightInfo['basePrice'] = (flightInfo['basePrice']  * Decimal('1.25')).quantize(Decimal('0.00'))
        if organizeType == 'search' and tickets < capacity:
            flightInfoList.append(flightInfo)
        if organizeType == 'mine':
            flightInfoList.append(flightInfo)
        cursor.close()


    return flightInfoList

 
@app.route('/userHome')
def userHome():
    
    #gets name of user
    email = session['user_id']
    db = get_db(); cursor = db.cursor()
    cursor.execute('SELECT first_name FROM customer WHERE email = ?', (email,))
    user = cursor.fetchone()
    cursor.close()
    name = user['first_name'] 

    #gets flights of user
    db = get_db(); cursor2 = db.cursor()
    query = """SELECT flight.airline_name, flight.airport_code, flight.arrival, flight.departure, flight.arrival_airport_code, flight.base_price, flight.Status, flight.flight_num 
            FROM ticket INNER JOIN flight ON ticket.flight_num = flight.flight_num 
            WHERE ticket.email = ? and flight.departure > datetime('now')
            """
    print(email)
    cursor2.execute(query, (email,))
    userFlights = cursor2.fetchall()
    cursor2.close()
    print(userFlights)
    organizeType = 'mine'
    flightInfoList = organizeData(userFlights, organizeType)
    print(flightInfoList)

    return render_template('userHome.html', name=name, flightInfo=flightInfoList)
    

@app.route('/tripSearch', methods=['GET', 'POST'])
def tripSearch():
    if request.method == 'POST':
        #getting information from form
        startingPoint = request.form['startingPoint']
        destination = request.form['destination']
        tripType = request.form['tripType']
        deptDate = request.form['deptDate']

        #need if statement incase of one-way
        if request.form.get('retDate'):
            retDate = request.form['retDate']   
    
        db = get_db(); cursor = db.cursor()


        #one-way
        query = """SELECT *
                FROM flight 
                WHERE flight.airport_code=? AND flight.arrival_airport_code=? AND date(flight.departure)=? and flight.departure > datetime('now')"""
        cursor.execute(query, (startingPoint, destination, deptDate))
        leaving = cursor.fetchall()
        organizeType = 'search'
        organizedLeavingData = organizeData(leaving, organizeType)
        cursor.close()



        #only happens if round-trip
        db = get_db(); cursor = db.cursor()
        if tripType == 'round-trip':
            query2 = """SELECT * 
                       FROM flight 
                       WHERE airport_code=? AND arrival_airport_code=? AND date(departure)=?"""
            cursor.execute(query2, (destination, startingPoint, retDate))
            returning = cursor.fetchall()
            organizedReturningData = organizeData(returning, 'search')
            cursor.close()
            combinedData =  zip(organizedLeavingData, organizedReturningData)
        else:
            combinedData=[]
            organizedReturningData = []

        return render_template('results.html', flightInfoLeaving=organizedLeavingData, flightInfoReturning=organizedReturningData, combinedData=combinedData, tripType=tripType)
            
    db = get_db(); cursor = db.cursor()
    query = """SELECT DISTINCT airport_code
                FROM airport"""
    cursor.execute(query )

    codes = cursor.fetchall()


    return render_template('tripSearch.html', codes=codes)

#function to cancel ticket, sends user back to home

@app.route('/cancelTicket', methods=['POST'])
def cancelTicket():
 
    email = session['user_id']
    flightNum = request.form['cancelTicket']
    db = get_db(); cursor = db.cursor()
    query = """DELETE 
                FROM Ticket
                WHERE flight_num=? and email=?
            """
    cursor.execute(query, (flightNum, email))
    get_db().commit()
    cursor.close()
    
    return redirect(url_for('userHome'))

#function to actually purchase the ticket
@app.route('/actualTicketPurchase', methods=['POST'])
def actualTicketPurchasel():
    purchaseDOBMonth = request.form['purchaseDOBMonth']
    purchaseDOBDay = request.form['purchaseDOBDay']
    purchaseDOBYear = request.form['purchaseDOBYear']
    purchaseDOBDate = f"{purchaseDOBYear}-{purchaseDOBMonth}-{purchaseDOBDay}"  
    flight_num1 = request.form['purchaseInfoNum1']
    calc_price1 = request.form['purchaseInfoPrice1']
    purchaseEmail =request.form['purchaseEmail']
    purchaseFirstName = request.form['purchaseFirstName']
    purchaseLastName = request.form['purchaseLastName']
    purchaseCardType = request.form['cardType']
    rating = None
    comments = None
    purchaseCardNum = request.form['purchaseCardNum']
    purchaseCardExp = request.form['purchaseCardExp']
    db = get_db(); cursor = db.cursor()
    query = """SELECT MAX(purchase_id) as max_purchase_id, datetime('now') as current_time FROM purchase"""
    cursor.execute(query)
    queryInfo = cursor.fetchall()
    query2 = """SELECT MAX(ticket_id) as max_ticket_id FROM ticket"""
    cursor.execute(query2)
    queryInfo2 = cursor.fetchall()
    cursor.close()
    ticket_id = (queryInfo2[0]['max_ticket_id'] or 0) + 1
    purchase_id = (queryInfo[0]['max_purchase_id'] or 0) + 1
    now = queryInfo[0]['current_time']
    db = get_db(); cursor = db.cursor()
    query = """INSERT INTO `Ticket` (`ticket_id`, `email`, `flight_num`, `rating`, `comments`, `calc_price`, `first_name`, `last_name`, `dob`) 
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)"""
    query2 = """INSERT INTO `Purchase` (`purchase_id`, `ticket_id`, `purchase_date_time`, `card_info`, `card_exp`, `card_type`) 
            VALUES(?, ?, ?, ?, ?, ?)
            """
    cursor.execute(query, (ticket_id, purchaseEmail, flight_num1, rating, comments, calc_price1, purchaseFirstName, purchaseLastName, purchaseDOBDate))
    cursor.execute(query2, (purchase_id, ticket_id, now, purchaseCardNum, purchaseCardExp, purchaseCardType))
    get_db().commit()
    flight_num2 = request.form['purchaseInfoNum2']
    calc_price2 = request.form['purchaseInfoPrice2']
    if flight_num2:

        query = """INSERT INTO `Ticket` (`ticket_id`, `email`, `flight_num`, `rating`, `comments`, `calc_price`, `first_name`, `last_name`, `dob`) 
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)"""

        cursor.execute(query, (ticket_id, purchaseEmail, flight_num2, rating, comments, calc_price2, purchaseFirstName, purchaseLastName, purchaseDOBDate))
    
    cursor.close()


    return redirect(url_for('userHome'))
    

           
#function to get to purchase page
@app.route('/purchaseTicket', methods=['GET', 'POST'])
def purchaseTicketRound():
    purchaseTicketFlightID1 = request.form['purchaseTicketNum1']
    purchaseTicketPricee1 = request.form['purchaseTicketPrice1']
    purchaseTicketFlightID2 = request.form['purchaseTicketNum2']
    purchaseTicketPricee2 = request.form['purchaseTicketPrice2']

    return render_template('purchaseTicket.html', purchaseInfoNum1=purchaseTicketFlightID1, purchaseInfoPrice1=purchaseTicketPricee1, purchaseInfoNum2=purchaseTicketFlightID2, purchaseInfoPrice2=purchaseTicketPricee2)

#function to get to past flights page
@app.route('/userPastFlights', methods=['GET', 'POST'])
def userPastFlights():
    email = session['user_id']
    db = get_db(); cursor = db.cursor()
    query = """SELECT flight.airline_name, flight.airport_code, flight.arrival, flight.departure, flight.arrival_airport_code, flight.base_price, flight.Status, flight.flight_num, ticket.ticket_id 
            FROM ticket INNER JOIN flight ON ticket.flight_num = flight.flight_num 
            WHERE ticket.email = ? and flight.departure < datetime('now')"""
    cursor.execute(query, (email,))
    userFlights = cursor.fetchall()
    cursor.close()
    flightInfoList= []
    #cant sent this to function because it will miss ticket_id
    for flight in userFlights:
        arrivalDateTime = flight['arrival']
        departureDateTime = flight['departure']
        arrivalDate = arrivalDateTime.strftime("%B %d, %Y")
        arrivalTime = arrivalDateTime.strftime("%I:%M %p").lstrip("0").replace(":00", "")
        departureDate = departureDateTime.strftime("%B %d, %Y")
        departureTime = departureDateTime.strftime("%I:%M %p").lstrip("0").replace(":00", "")
        flightInfo = {
            "airline": flight['airline_name'],
            "departureLocation": flight['airport_code'],
            "arrivalDate": arrivalDate,
            "arrivalTime": arrivalTime,
            "departureDate": departureDate,
            "departureTime": departureTime,
            "arrivalLocation": flight['arrival_airport_code'],
            "basePrice": flight['base_price'],
            "status": flight['Status'],
            "flightNum": flight['flight_num'],
            "ticketID": flight['ticket_id']
        }
        flightInfoList.append(flightInfo)



    return render_template('userPastFlights.html', flightInfo=flightInfoList )


#post rate and comment (will replace preexisting ones)
@app.route('/rateAndComment', methods=['GET', 'POST'])
def rateAndComment():
    email = session['user_id']
    ticket_id = request.form['ticket_ID']
    rating = request.form['rating']
    comment = request.form['comment']
    db = get_db(); cursor = db.cursor()
    query = """UPDATE Ticket 
                SET rating=?, comments=?
                WHERE email=? and ticket_id=?
            """
    cursor.execute(query, (rating, comment, email, ticket_id))
    get_db().commit()
    cursor.close()
    
    return redirect(url_for('userPastFlights'))

#spending function
@app.route('/spending', methods=['GET', 'POST'])
def spending():
    today = datetime.today()
    if today.month > 6:
        sixMonthsAgo = today.replace(month=(today.month - 6))
    else:
        sixMonthsAgo = today.replace(month=((12 + today.month - 6)))

    email = session['user_id']
    today = datetime.today()
    oneYearAgo = today.replace(year=today.year - 1)
    db = get_db(); cursor = db.cursor()
    query = """SELECT SUM(ticket.calc_price) as amount
            FROM Purchase JOIN Ticket ON Purchase.ticket_id = Ticket.ticket_id
            WHERE email=? and purchase.purchase_date_time > ?
            GROUP BY Ticket.email"""
    cursor.execute(query, (email, oneYearAgo))
    result = cursor.fetchall()
    if result:
        lastYear = result[0]['amount']
    else:
        lastYear = 0
    query2 = """SELECT DATE_FORMAT(Purchase.purchase_date_time, '%%Y-%%m') AS month, SUM(ticket.calc_price) AS totalSpent
                FROM Purchase JOIN Ticket ON Purchase.ticket_id = Ticket.ticket_id
                WHERE Ticket.email = ? and purchase.purchase_date_time > ?
                GROUP BY month
                ORDER BY month ASC
            """
    cursor.execute(query2, (email, sixMonthsAgo))
    result2 = cursor.fetchall()


    cursor.close()


    return render_template("spending.html", totalSpentYear=lastYear, data=result2)

#user spending results
@app.route('/spendingUpdate', methods=['POST'])
def spendingUpdate():
    today = datetime.today()
    if today.month > 6:
        sixMonthsAgo = today.replace(month=(today.month - 6))
    else:
        sixMonthsAgo = today.replace(month=((12 + today.month - 6)))
    email = session['user_id']
    db = get_db(); cursor = db.cursor()
    startDate = request.form['startDateInput']
    endDate = request.form['endDateInput']
    startDateObj = datetime.strptime(startDate, '%Y-%m-%d')
    endDateObj = datetime.strptime(endDate, '%Y-%m-%d')

    query = """SELECT SUM(ticket.calc_price) as amount
        FROM Purchase JOIN Ticket ON Purchase.ticket_id = Ticket.ticket_id
        WHERE email=? and purchase.purchase_date_time BETWEEN ? and ?
        GROUP BY Ticket.email"""
    formattedStartDate =  startDateObj.strftime("%B %d, %Y")
    formattedEndDate = endDateObj.strftime("%B %d, %Y")
    cursor.execute(query, (email, startDate, endDate))
    result = cursor.fetchall()
    if not result:
        sinceYear = 0
    else:
        sinceYear = result[0]['amount']




    oneYearAgo = today.replace(year=today.year - 1)
    query2 = """SELECT SUM(ticket.calc_price) as amount
            FROM Purchase JOIN Ticket ON Purchase.ticket_id = Ticket.ticket_id
            WHERE email=? and purchase.purchase_date_time > ?
            GROUP BY Ticket.email"""
    cursor.execute(query2, (email, oneYearAgo))
    result2 = cursor.fetchall()

    if result2:
        lastYear = result2[0]['amount']
    else:
        lastYear = 0




    query3 = """SELECT DATE_FORMAT(Purchase.purchase_date_time, '%%Y-%%m') AS month, SUM(ticket.calc_price) AS totalSpent
                FROM Purchase JOIN Ticket ON Purchase.ticket_id = Ticket.ticket_id
                WHERE Ticket.email = ? and purchase.purchase_date_time > ?
                GROUP BY month
                ORDER BY month ASC
            """
    cursor.execute(query3, (email, sixMonthsAgo))
    result3 = cursor.fetchall()

    query4 = """SELECT DATE_FORMAT(Purchase.purchase_date_time, '%%Y-%%m') AS month, 
                    SUM(ticket.calc_price) AS totalSpent
                    FROM Purchase 
                    JOIN Ticket ON Purchase.ticket_id = Ticket.ticket_id
                    WHERE email=? AND purchase.purchase_date_time BETWEEN ? AND ?
                    GROUP BY month
                    ORDER BY month ASC"""
    cursor.execute(query4, (email, startDateObj, endDateObj))
    resultRange = cursor.fetchall()
    print(resultRange)

    
 





    cursor.close()
    return render_template('spendingUpdate.html', totalSpentYear=lastYear, data=result3, startDate=formattedStartDate, endDate=formattedEndDate, sinceTotal=sinceYear, rangeMonthData=resultRange)

#logout page
@app.route('/userLogout', methods=['GET', 'POST'])
def userLogout():
    if request.method == 'POST':
        yesNo = request.form['yesNo']
        if yesNo == 'logout':
            session.clear()
            
            return redirect(url_for('homepage'))
        else:
            return redirect(url_for('userHome'))

    return render_template('userLogout.html')



# function to determine if the user is a customer or staff

def determine_user_type(email, password):
    db = get_db(); cursor = db.cursor()

    cursor.execute('SELECT password FROM Customer WHERE email = ?', (email,))
    customer = cursor.fetchone()
    if customer and customer['password'] == password:
        return "customer"

    cursor.execute('SELECT password FROM Staff WHERE username = ?', (email,))
    staff = cursor.fetchone()
    if staff and staff['password'] == password:
        return "staff"

    return None



@app.route('/loginAuth', methods=['GET', 'POST'])
def loginAuth():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']

        user_type = determine_user_type(username, password)
        if user_type == "customer":
            session['user_id'] = username
            session['role'] = 'customer'
            return redirect(url_for('userHome'))
        elif user_type == "staff":
            session['user'] = username
            session['role'] = 'staff'
            return redirect(url_for('staffHome'))
        else:
            error_message = "User not found. Please check your login details."
            return render_template('login.html', error=error_message)
    return render_template('login.html')


# HOMEPAGE, the first page you see when you open the app
@app.route('/homepage', methods=['POST', 'GET'])
def homepage():
    if request.method == 'POST':
        # getting information from form
        startingPoint = request.form['startingPoint']
        destination = request.form['destination']
        tripType = request.form['tripType']

        deptDate = request.form['deptDate']



        # need if statement incase of one-way
        if request.form.get('retDate'):
            retDate = request.form['retDate']

        db = get_db(); cursor = db.cursor()

        # one-way
        query = """SELECT *
                FROM flight 
                WHERE flight.airport_code=? AND flight.arrival_airport_code=? AND date(flight.departure)=? and flight.departure > datetime('now')"""
        cursor.execute(query, (startingPoint, destination, deptDate))
        leaving = cursor.fetchall()
        organizedLeavingData = organizeData(leaving, 'search')
        cursor.close()

        # only happens if round-trip
        db = get_db(); cursor = db.cursor()
        if tripType == 'round-trip':
            query2 = """SELECT * 
                       FROM flight 
                       WHERE airport_code=? AND arrival_airport_code=? AND date(departure)=?"""
            cursor.execute(query2, (destination, startingPoint, retDate))
            returning = cursor.fetchall()
            organizedReturningData = organizeData(returning, 'search')
            cursor.close()
            combinedData = zip(organizedLeavingData, organizedReturningData)
        else:
            combinedData = []
            organizedReturningData = []

        return render_template('resultsPublic.html', flightInfoLeaving=organizedLeavingData,
                               flightInfoReturning=organizedReturningData, combinedData=combinedData, tripType=tripType)
    db = get_db(); cursor = db.cursor()
    query = """SELECT DISTINCT airport_code
                FROM airport"""
    cursor.execute(query )

    codes = cursor.fetchall()

    return render_template('homepage.html', codes=codes)


@app.route('/staffHome', methods=['GET'])
def staffHome():
    if 'role' in session and session['role'] == 'staff':
        username = session['user']
        db = get_db(); cursor = db.cursor()
        query = "SELECT * FROM flight WHERE departure > datetime('now') and departure < datetime('now') + INTERVAL 1 MONTH"
        cursor.execute(query)
        flights = cursor.fetchall()
        db = get_db(); cursor2 = db.cursor()
        cursor2.execute("SELECT first_name FROM staff WHERE username = ?", (username,))
        user = cursor2.fetchall()
        name = user[0]['first_name']
        return render_template('staffHome.html', flights=flights, name=name)
    else:
        return redirect(url_for('loginAuth'))


# Function to register a customer
@app.route('/customerRegister', methods=['GET', 'POST'])
def customerRegister():
    if request.method == "POST":
        username = request.form['email']
        passport_country = request.form['passport_country']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        password = request.form['password']
        phone_numbers = request.form.getlist('phone_numbers[]')


        dob = request.form['dob']
        address = request.form['address']
        passport_number = request.form['passport_number']
        passport_exp_date = request.form['passport_exp_date']

        db = get_db(); cursor = db.cursor()
        query = 'Select * FROM Customer WHERE email = ?'
        cursor.execute(query, (username,))
        data = cursor.fetchone()
      

        if data:
            error = "This customer already exists."
            cursor.close()
            return render_template("customerRegister.html", error=error)

        else:
            ins = 'INSERT INTO Customer VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)'
            cursor.execute(ins, (
            username, passport_country, first_name, last_name, password, dob, address, passport_number,
            passport_exp_date))

            phone_q = "INSERT INTO UserPhoneNumbers (email, phone_number) VALUES (?, ?)"
            for phone in phone_numbers:
              cursor.execute(phone_q, (username, phone))
            get_db().commit()
            

            get_db().commit()
            cursor.close()
            flash("Registration successful!", "success")

            return render_template("login.html")
    return render_template("customerRegister.html")


# FUNCTION to register a staff
@app.route('/staffRegister', methods=['GET', 'POST'])
def staffRegister():
    if request.method == 'POST':
        username = request.form['username']
        airline_name = request.form['airline_name']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        dob = request.form['dob']
        password = request.form['password']
        phone_numbers = request.form.getlist('phone_numbers[]')
        emails = request.form.getlist('emails[]')

        db = get_db(); cursor = db.cursor()
        query = 'SELECT * FROM Staff WHERE username = ?'
        cursor.execute(query, (username,))
        data = cursor.fetchone()
      

        if data:
            error = "This staff already exists."
            cursor.close()
            return render_template("staffRegister.html", error=error)

        else:
            ins = "INSERT INTO Staff VALUES (?, ?, ?, ?, ?, ?)"
            cursor.execute(ins, (username, airline_name, first_name, last_name, dob, password))

            email_q = "INSERT INTO StaffEmails (username, email) VALUES (?, ?)"
            print(emails)
            for email in emails:
              cursor.execute(email_q, (username, email))

            phone_q = "INSERT INTO StaffPhoneNumbers (username, phone_number) VALUES (?, ?)"
            for phone in phone_numbers:
              cursor.execute(phone_q, (username, phone))
            get_db().commit()
            cursor.close()

            flash("Registration successful!", "success")

            return render_template("login.html")
    return render_template('staffRegister.html')


# staff logout function 
@app.route('/staffLogout', methods=['GET', 'POST'])
def staffLogout():
    if request.method == 'POST':
        yesNo = request.form['yesNo']
        if yesNo == 'logout':
            session.clear()
            return redirect(url_for('homepage'))
        else:
            return redirect(url_for('staffHome'))

    return render_template('staffLogout.html')


# create flight function
@app.route('/createFlight', methods=['GET', 'POST'])
def createFlight():
    if 'role' in session and session['role'] == 'staff':

        if request.method == 'POST':

            # create a new flight
            flight_num = request.form['flight_num']
            airline_name = request.form['airline_name']
            airplane_id = request.form['airplane_id']
            airport_code = request.form['airport_code']
            arrival = request.form['arrival']
            departure = request.form['departure']
            base_price = request.form['base_price']
            arrival_airport_code = request.form['arrival_airport_code']
            status = request.form['status']

            db = get_db(); cursor = db.cursor()
            query = 'SELECT * FROM flight WHERE flight_num = ?'
            cursor.execute(query, (flight_num,))

            data = cursor.fetchone()
            

            if data:
                # if the query returns data than the flight already exists
                error = "This flight already exists."
                cursor.close()
                return render_template(createFlight.template, error=error)

            else:
                ins = 'INSERT INTO flight VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)'
                cursor.execute(ins, (
                flight_num, airline_name, airplane_id, airport_code, arrival, departure, base_price,
                arrival_airport_code, status))
                get_db().commit()
                cursor.close()
                flash("Flight created!", "success")
                return render_template('createFlight.html')
        else:
            return render_template('createFlight.html')



    else:
        return redirect(url_for('loginAuth'))


# add airplane function
@app.route('/addAirplane', methods=['GET', 'POST'])
def addAirplane():
    if 'role' in session and session['role'] == 'staff':
        if request.method == 'POST':
            # add a new airplane
            airplane_id = request.form['airplane_id']
            airline_name = request.form['airline_name']
            manufacturer = request.form['manufacturer']
            model_number = request.form['model_number']
            manufactur_date = request.form['manufactur_date']
            num_seats = request.form['num_seats']

            db = get_db(); cursor = db.cursor()
            query = 'SELECT * FROM Airplane WHERE airplane_id = ?'
            cursor.execute(query, (airplane_id,))

            data = cursor.fetchone()

            if data:
                # there already is a plane with this id
                error = "This plane already exists."
                #cursor.close()
                return render_template("addAirplane.html", error=error)
            else:
                ins = 'INSERT INTO Airplane(airplane_id, airline_name, manufacturer, model_number, manufacture_date, num_seats) VALUES (?, ?, ?, ?, ?, ?)'
                cursor.execute(ins, (airplane_id, airline_name, manufacturer, model_number, manufactur_date, num_seats))
                get_db().commit()
                #cursor.close()
                
                query_airplanes = 'SELECT * FROM Airplane WHERE airline_name = ?'
                cursor.execute(query_airplanes, (airline_name,))
                airplanes = cursor.fetchall()
              
                flash("Airplane added!", "success")
                return render_template("addAirplaneConfirmation.html", airplanes=airplanes)

        else:
            return render_template("addAirplane.html")

    else:
        return redirect(url_for('loginAuth'))


# add new airport, accessed within the staffHome page
@app.route('/addAirport', methods=['GET', 'POST'])
def addAirport():
    if 'role' in session and session['role'] == 'staff':
        if request.method == 'POST':

            # add an airport
            airport_code = request.form['airport_code']
            airport_name = request.form['airport_name']
            city = request.form['city']
            country = request.form['country']
            num_terminals = request.form['num_terminals']
            airportType = request.form['type']

            db = get_db(); cursor = db.cursor()
            query = 'SELECT * FROM Airport WHERE airport_code = ?'
            cursor.execute(query, (airport_code,))
            data = cursor.fetchone()

            if data:
                error = "This airport already exists."
                cursor.close()
                return render_template(addAirport.template, error=error)

            else:
                ins = 'INSERT INTO Airport VALUES (?, ?, ?, ?, ?, ?)'
                cursor.execute(ins, (airport_code, airport_name, city, country, num_terminals, airportType))
                get_db().commit()
                cursor.close()
                flash("Airport added!", "success")
                return render_template("addAirport.html")
        else:
            return render_template("addAirport.html")



    else:
        return redirect(url_for('loginAuth'))


# view ratings, accessed within the staffHome
@app.route('/viewRatings', methods=['GET'])
def viewRatings():
    if 'role' in session and session['role'] == 'staff':
        # gets the ratings from the flight
        db = get_db(); cursor = db.cursor()

        cursor.execute(
            'SELECT ticket.rating, ticket.flight_num, ticket.comments FROM Ticket INNER JOIN Flight on Ticket.flight_num = Flight.flight_num')
        flraco = cursor.fetchall()
        flight_data = {}

        for entry in flraco:
            flight_num = entry['flight_num']
            rating = entry['rating']
            comment = entry['comments']

            if flight_num not in flight_data:
                flight_data[flight_num] = {'ratings_comments': []}

            if rating is not None or comment:
                flight_data[flight_num]['ratings_comments'].append({'rating': rating, 'comment': comment})
           

        flight_averages = {
            flight_num: sum([entry['rating'] for entry in flight_data[flight_num]['ratings_comments']]) / len(flight_data[flight_num]['ratings_comments']) 
            if flight_data[flight_num]['ratings_comments'] else None
            for flight_num in flight_data
        }
        flight_details = []
        for flight_num, data in flight_data.items():
            flight_details.append({
                "flight_num": flight_num, "average": flight_averages[flight_num], 'ratings_comments': data['ratings_comments']
            })

        cursor.close()

        return render_template('viewRatings.html', flight_details=flight_details)
    else:
        return redirect(url_for('loginAuth'))


# scheudle maitence, accessed within the staffHome page
@app.route('/scheduleMaintenance', methods=['GET', 'POST'])
def scheduleMaintenance():
    if 'role' in session and session['role'] == 'staff':
        if request.method == 'POST':

            # logic to schedule maitence
            airplane_id = request.form['airplane_id']
            start_date_time = request.form['start_date_time']
            end_date_time = request.form['end_date_time']

            db = get_db(); cursor = db.cursor()
            query = 'SELECT * FROM Maitenance WHERE airplane_id = ?'
            cursor.execute(query, (airplane_id,))

            data = cursor.fetchone()

            if data:
                error = "Maintenance has already been scheduled on this plane."
                cursor.close()
                return render_template("scheduleMaintenance.html", error=error)

            else:
                ins = 'INSERT INTO Maitenance VALUES (?, ?, ?)'
                cursor.execute(ins, (airplane_id, start_date_time, end_date_time))
                get_db().commit()
                cursor.close()
                flash("Maitenance scheduled!", "success")
                return render_template("scheduleMaintenance.html")
        else:
            return render_template("scheduleMaintenance.html")




    else:
        return redirect(url_for('loginAuth'))


# customers, accessed within the staffHome page - (NOT DONE!!!!!!)
@app.route('/viewCustomers', methods=['GET', 'POST'])
def viewCustomers():
    if 'role' in session and session['role'] == 'staff':
        db = get_db(); cursor = db.cursor()

        # Query to get the most frequent customer in the last year
        query_frequent_customer = "SELECT Ticket.email, COUNT(*) AS flight_count FROM Ticket INNER JOIN Flight ON Ticket.flight_num = Flight.flight_num WHERE Flight.departure > DATE_SUB(datetime('now'), INTERVAL 1 YEAR) GROUP BY Ticket.email ORDER BY flight_count DESC LIMIT 1"
        cursor.execute(query_frequent_customer)
        frequent_customer = cursor.fetchone()

        # Query to get all customers
        query_all_customers = "SELECT DISTINCT email FROM Ticket"
        cursor.execute(query_all_customers)
        all_customers = cursor.fetchall()

        customer_flights = []
        selected_customer = None

        # If the user submits a POST request to view flights for a specific customer
        if request.method == 'POST':
            selected_customer = request.form['email']
            query_customer_flights = "SELECT Flight.flight_num, Flight.departure, Flight.arrival, Flight.airport_code, Flight.arrival_airport_code FROM Ticket INNER JOIN Flight ON Ticket.flight_num = Flight.flight_num WHERE Ticket.email = ?"
            cursor.execute(query_customer_flights, (selected_customer,))
            customer_flights = cursor.fetchall()

        cursor.close()


        return render_template("viewCustomers.html", frequent_customer=frequent_customer, all_customers=all_customers,
                               selected_customer=selected_customer, customer_flights=customer_flights)
    else:
        return redirect(url_for('loginAuth'))


# views the monthly and yearly revenue
@app.route('/viewRevenue', methods=['GET'])
def viewRevenue():
    if 'role' in session and session['role'] == 'staff':

        db = get_db(); cursor = db.cursor()

        from datetime import datetime, timedelta
        current_date = datetime.now()
        one_month_later = current_date + timedelta(days=30)

        query = 'SELECT base_price, departure FROM Flight'
        cursor.execute(query)
        revenue_month = 0
        revenue_year = 0

        data = cursor.fetchall()
        cursor.close()
        for ticket in data:
            base_price = ticket['base_price']
            departure = ticket['departure']
            ##datetime.strftime(departure)
            #departure_date = datetime.strptime(departure, '%Y-%m-%d %H:%M:%S')
            if departure < one_month_later:
                revenue_month += base_price
            revenue_year += base_price

        return render_template("viewRevenue.html", revenue_month=revenue_month, revenue_year=revenue_year)
    else:
        return redirect(url_for('loginAuth'))


@app.route('/changeFlightStatus', methods=['GET', 'POST'])
def changeFlightStatus():
    if 'role' in session and session['role'] == 'staff':
        if request.method == 'POST':
            status = request.form['status']
            airplane_id = request.form['airplane_id']

            db = get_db(); cursor = db.cursor()
            query = """UPDATE Flight SET status = ? WHERE airplane_id = ?"""
            cursor.execute(query, (status, airplane_id))
            get_db().commit()

            cursor.close()

            # Flash a success message
            flash("Flight status updated successfully!", category="success")

            return redirect(url_for('changeFlightStatus'))
        return render_template('changeFlightStatus.html')
    else:
        return redirect(url_for('loginAuth'))

if __name__ == "__main__":
    app.run("127.0.0.1", 5000, debug=True)