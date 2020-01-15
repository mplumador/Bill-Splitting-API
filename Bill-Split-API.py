from flask import Flask
from flask import request
from flask import abort
from flask import session
import numbers
app = Flask(__name__)

#Needed for using a session to store cookies of records
app.secret_key = "SuperSecretKey"
#This should be offloaded via a config file, and should be some random string, as it is used to encrypt our cookies

#https://stackoverflow.com/questions/268272/getting-key-with-maximum-value-in-dictionary
#This will not return a list of all keys with the same max value, but will return the first instance
#This should be fine for our application
def getKeyOfLargestValue(someDict):
    return max(someDict, key=someDict.get)

def validateRecord(record):
    currName = record.get('payer')
    currAmount = record.get('amount')
    if(currName is None):
        #Payer key does not exist
        raise NameError("'payer' key is not found in the request.")
        #print("error here, payer key isn't seen")
    elif(currAmount is None):
        #Amount key does not exist
        raise NameError("'amount' key is not found in the request.")
        #print("error here, payment amount is not valid")
    elif(not isinstance(currAmount,numbers.Number)):
        #Amount value is not a numeric type
        raise TypeError("'amount' key is found in the request, but the value is not of numeric type")
        #print("error here, its not a numeric type")
    else:
        return True
    

def settlementDict(expenseList):
    settleDict = {}
    totalAmount = 0
    for people in expenseList:
        currName = people.get('payer')
        currAmount = people.get('amount')
        if(validateRecord(people)):
            #Data appears to be valid
            totalAmount += currAmount
            if(currName not in settleDict.keys()):
                settleDict[currName]=currAmount
            else:
                settleDict[currName] += currAmount
    #At this point we should have an aggregate total of each individuals contributions
    numPeople = len(settleDict)
    pricePerPerson = totalAmount/numPeople
    return (pricePerPerson, settleDict)


def settlementMath(pricePerPerson,settleDict):    
    #If the person that paid the most paid the price per person, then everyone paid the right amount
    resultDict = {'settlement':[]}
    currLargestContributor = getKeyOfLargestValue(settleDict)
    #We need to round our floating point values to make sense
    while(round(settleDict[currLargestContributor],2) != round(pricePerPerson,2)):
        for name in settleDict:
            if(name != currLargestContributor and settleDict[name] < pricePerPerson):
                #How much the highest contributor has payed
                contribAmount = settleDict[currLargestContributor]
                totalNeeded = contribAmount-pricePerPerson
                #How much this person has payed
                currPersonAmount = settleDict[name]
                totalToPay = pricePerPerson-currPersonAmount
                if(totalNeeded >= totalToPay):
                    resultDict['settlement'].append({'payer':name, 'recipient':currLargestContributor, 'amount':round(totalToPay,2)})
                    #Update our settleDict
                    settleDict[name] += totalToPay
                    settleDict[currLargestContributor] -= totalToPay
                    #print(resultDict)
                else:
                    resultDict['settlement'].append({'payer':name, 'recipient':currLargestContributor, 'amount':round(totalNeeded,2)})
                    settleDict[name] += totalNeeded
                    settleDict[currLargestContributor] -= totalNeeded
                    #print(resultDict)
            #Update our current largest contrib
            currLargestContributor = getKeyOfLargestValue(settleDict)
        #currLargestContributor = getKeyOfLargestValue(settleDict)
        #we don't need to update this outside of the FOR loop, since it will already be updated
        #We update this inside the FOR loop, for the case that after a payment has been made there is a new transaction leader.
    return resultDict
    

@app.route('/')
def index():
    return "Hello, World!"

#I believe this would be better served as a POST method rather than a GET method
#This SO post explains that it is more standard to ignore the body of a GET request on the server-side (but not URL parameters)
#https://stackoverflow.com/questions/978061/http-get-with-request-body
@app.route('/split', methods=['GET'])
def splitHandler():
    #Checking for if the request is json causes errors on a simple GET request with a body.
    #print(request.is_json)
    #Since we can't check if the request is json formatted, we force the body to be read as json regardless
    #This could produce an error, so we surround it in a try-catch block.
    try:
        content = request.get_json(force=True)
        #dict.get will return none if the key does not exist
        #This will be how we filter out invalid data
        expenses = content.get('expenses')
        if(expenses is not None):
            try:
                #SettlementDict returns a tuple of price per person as well as the settlement dictionary
                pricePer, setDict = settlementDict(expenses)
                result = settlementMath(pricePer,setDict)
                return result
            except Exception as e:
                return {"Error code":400, "Error message":e.args[0]}, 400
        else:
            #Throw 400 status code and details
            return {"Error code":400, "Error message":"Failed to find 'expenses' key in the request"}, 400
    except Exception as e:
        return {"Error code":400, "Error message":"Failed to parse request body as json"},400
@app.route('/record', methods=['POST'])
def recordHandler():
    if(request.is_json):
        content = request.get_json()
        try:
            validateRecord(content)
            temp = session.get('contributors')
            if(temp is None):
                #No session found, create it
                session['contributors'] = [content]
            else:
                #Session found, update it
                temp.append(content)
                session['contributors'] = temp
            #print(session['contributors'])
            return {"status":"OK"}, 200
        except Exception as e:
            return {"Error code":400, "Error message":e.args[0]}, 400
    else:
        return {"Error code":400, "Error message":"Body is not specified as application/json"},400

@app.route('/settle',methods=['POST'])
def settleHandler():
    #Technically all data should have already been validated prior to being added to the list (Via POST /record)
    #However, settleDict will check the validation again, meaning we need to re-surround in a try-catch block
    #This can be optimized by seperating out the validation from settleDict and implementing data validation into the GET /split method
    data = session.get('contributors')
    if(data is None or len(data) == 0):
        return {"Error code":400, "Error message:":"There were no records set in this session"}, 400
    else:
        try:
            pricePer, setDict = settlementDict(data)
            result = settlementMath(pricePer,setDict)
            session['contributors'] = []
            return result
        except Exception as e:
            return {"Error code":400, "Error message":e.args[0]}, 400

    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
