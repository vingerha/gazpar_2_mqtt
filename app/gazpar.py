#!/usr/bin/env python3
import logging
import requests
import json
import datetime
import os
import sys
import inspect
import time
from requests import Session
import http.cookiejar

# Constants
GRDF_DATE_FORMAT = "%Y-%m-%d"
GRDF_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
GRDF_API_MAX_RETRIES = 14 # number of retries max to get accurate data from GRDF
GRDF_API_WAIT_BTW_RETRIES = 20 # number of seconds between try 1 and try 2 (must not exceed 25s)
GRDF_API_ERRONEOUS_COUNT = 1 # Erroneous number of results send by GRDF
TYPE_I = 'informative' # type of measure Informative
TYPE_P = 'published' # type of measure Published



#######################################################################
#### Useful functions
#######################################################################

# Convert GRDF datetime string to date
def _convertDate(dateString):
    if dateString == None: return None
    else:
        myDate = datetime.datetime.strptime(dateString,GRDF_DATE_FORMAT).date()
        return myDate
    
# Convert GRDF datetime string to datetime
def _convertDateTime(dateTimeString):
    
    if dateTimeString == None: return None
    else:
        myDateTimeString = dateTimeString[0:19].replace('T',' ') # we remove timezone
        myDateTime = datetime.datetime.strptime(myDateTimeString,GRDF_DATETIME_FORMAT)
        return myDateTime
    
# Convert date to GRDF date string
def _convertGrdfDate(date):
    return date.strftime(GRDF_DATE_FORMAT)

# Get the time sleeping between 2 retries
def _getRetryTimeSleep(tryNo):
    
    # The time to sleep is exponential 
    return GRDF_API_WAIT_BTW_RETRIES * pow(tryNo,2.5)

#######################################################################
#### Class GRDF
#######################################################################
class Grdf:
    site_grdf_url = "https://monespace.grdf.fr/client/particulier/consommation"
    # Constructor
    def __init__(self):

        # Initialize instance variables
        self.session = None
        self.auth_nonce = None
        self.pceList = []
        self.whoiam = None
        self.isConnected = False
        self.account = None   
        self.session = requests.Session()
        logging.debug("After init")

    def login(self,username,password):
        SESSION_TOKEN_URL = "https://connexion.grdf.fr/api/v1/authn"
        AUTH_TOKEN_URL = "https://connexion.grdf.fr/login/sessionCookieRedirect"
        
        logging.info("Starting GRDF login process...")
        try:
            self.session.headers.update({
                "domain": "grdf.fr",
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
            })

            # Prepare payload
            payload = {
                "username": username,
                "password": password,
                "options": {
                    "multiOptionalFactorEnroll": False,
                    "warnBeforePasswordExpired": False
                }
            }
            
            logging.debug("Attempting to get session token...")
            response = self.session.post(SESSION_TOKEN_URL, json=payload)
            logging.debug("Session token response status: %s", response.status_code)
            logging.debug("Session token response: %s", response.text)

            if response.status_code != 200:
                logging.error("Failed to get session token. Status code: %s", response.status_code)
                logging.error("Response: %s", response.text)
                self.isConnected = False
                return

            # get auth token
            session_token = response.json().get("sessionToken")
            if not session_token:
                logging.error("No session token found in response")
                self.isConnected = False
                return
                
            logging.debug("Session token obtained: %s", session_token)
            jar = http.cookiejar.CookieJar()
            
            # Prepare auth params
            params = {
                "checkAccountSetupComplete": True,
                "token": session_token,
                "redirectUrl": "https://monespace.grdf.fr"
            }
            
            logging.debug("Attempting to get auth token...")
           
            response = self.session.get(AUTH_TOKEN_URL, params=params, allow_redirects=True, cookies=jar)
            logging.debug("Auth token response status: %s", response.status_code)
            logging.debug("Auth token response: %s", response.text)

            if response.status_code != 200:
                logging.error("Failed to get auth token. Status code: %s", response.status_code)
                logging.error("Response: %s", response.text)
                self.isConnected = False
                return

            self.auth_token = self.session.cookies.get("auth_token", domain="monespace.grdf.fr")
            if not self.auth_token:
                logging.error("No auth token found in cookies")
                self.isConnected = False
                return
                
            logging.debug("Auth token obtained")
            
            # Create a session.
            self.session.headers.update({
                "Host": "monespace.grdf.fr",
                "Domain": "grdf.fr",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json"
            })
            self.session.cookies.set("auth_token", self.auth_token, domain="monespace.grdf.fr")
                   
            # When everything is ok
            logging.info("GRDF login successful")
            self.isConnected = True
            
        except Exception as e:
            logging.error("Login failed with exception: %s", str(e))
            logging.error("Exception details:", exc_info=True)
            self.isConnected = False
    
    # Return GRDF quality status
    def isOk(self):
        
        # GRDF is ok when contains at least one valid PCE
        if self.countPce() == 0 or self.countPce() is None:
            return False
        elif self.countPceOk() == 0 or self.countPceOk() is None:
            return False
        else:
            return True
        
        
    
    # Get account info
    def getWhoami(self):
        
        logging.debug("Get whoami...")
        try:
            req = self.session.get('https://monespace.grdf.fr/api/e-connexion/users/whoami')
        except Exception as e:
            logging.error("Error while calling whoami:")
            logging.error(str(e))
            self.isConnected = False
       
        logging.debug("Whoami result %s", req.text)
        
        # Check returned JSON format
        try:
            account = json.loads(req.text)
        except Exception as e:
            logging.error("Whoami returned invalid JSON:")
            logging.error(str(e))
            logging.info(req.text)
            self.isConnected = False
            return None
        
        # Check Whoami content
        if 'code' in account:
            logging.info(req)
            logging.info("Whoami unsuccessful. Invalid returned information: %s", req.text)
            self.isConnected = False
            return None

        # Check that id is in account
        if not 'id' in account or account['id'] <= 0:
            logging.info(req)
            logging.info("Whoami unsuccessful. Invalid returned information: %s", req.text)
            self.isConnected = False
            return None
        else:
            # Create account
            self.account = Account(account)
            return self.account    
               
    # Get list of PCE
    def getPceList(self):
        
        logging.debug("Get PCEs list...")
        
        # Get PCEs from website
        try:
            req = self.session.get('https://monespace.grdf.fr/api/e-conso/pce')
        except Exception as e:
            logging.error("Error while calling pce:")
            logging.error(str(e))
            self.isConnected = False
            
        logging.debug("Get PCEs list result : %s",req.text)
        
        # Check PCEs list
        try:
            pceList = json.loads(req.text)
        except Exception as e:
            logging.error("PCEs returned invalid JSON:")
            logging.error(str(e))
            logging.info(req.text)
            self.isConnected = False
            return None
        
        if 'code' in pceList:
            logging.info(req)
            logging.info("PCEs unsuccessful. Invalid returned information: %s", req.text)
            self.isConnected = False
            return None
        
        # Ok everything is fine, we can create PCE
        for item in pceList:
            # Create PCE
            myPce = Pce(item)
            # Add PCE to list
            self.addPce(myPce)
    
    # Add PCE to list
    def addPce(self, pce):
        self.pceList.append(pce)
        
    # Return the number of PCE
    def countPce(self):
        return len(self.pceList)
    
    # Return the number of valid PCE
    def countPceOk(self):
        i = 0
        for myPce in self.pceList:
            if myPce.isOk() == True:
                i += 1
        return i
    
    # Get measures of a single PCE for a period range
    def getPceMeasures(self,pce, startDate, endDate, type):
        
        # Convert date
        myStartDate = _convertGrdfDate(startDate)
        myEndDate = _convertGrdfDate(endDate)

        if type == TYPE_I:
            req = self.session.get('https://monespace.grdf.fr/api/e-conso/pce/consommation/informatives?dateDebut=' + myStartDate + '&dateFin=' + myEndDate + '&pceList%5B%5D=' + pce.pceId)
        elif type == TYPE_P:
            req = self.session.get('https://monespace.grdf.fr/api/e-conso/pce/consommation/publiees?dateDebut=' + myStartDate + '&dateFin=' + myEndDate + '&pceList%5B%5D=' + pce.pceId)
        else:
            logging.error("Type of measures must be informative or published.")
            exit()


        measureList = json.loads(req.text)
        
        # Update PCE range of date
        #pce.dailyMeasureStart = startDate
        #pce.dailyMeasureEnd = endDate
        
        if measureList:

            for measure in measureList[pce.pceId]["releves"]:

                # Create the measure
                myMeasure = Measure(pce,measure,type)

                # Append measure to the PCE's measure list
                pce.addMeasure(myMeasure)

        else:
            logging.error("Measure list provided by GRDF is empty")



    # Get thresold
    def getPceThresold(self,pce):
        
        req = self.session.get('https://monespace.grdf.fr/api/e-conso/pce/'+ pce.pceId + '/seuils?frequence=Mensuel')
        thresoldList = json.loads(req.text)
        
        for thresold in thresoldList["seuils"]:
            
            # Create the thresold
            myThresold = Thresold(pce,thresold)
            
            # Append thresold to the PCE's thresold list
            pce.addThresold(myThresold)
    
    # for posting to url / websocket
    def open_url(self, host, uri, token, data=None):
        """
        GET or POST (if data) request from Home Assistant API.
        """
        # Generate URL
        api_url = host + uri

        headers = {
            "Authorization": "Bearer {}".format(
                token
            ),
            "Content-Type": "application/json",
        }
        logging.debug("GET/POST for URL %s, with headers: %s", api_url, headers)
        try:
            if data is None:
                response = requests.get(
                    api_url,
                    headers=headers,
                    verify=not False,
                    timeout=30,
                )

            else:
                response = requests.post(
                    api_url,
                    headers=headers,
                    json=data,
                    verify=not False,
                    timeout=30,
                )
                logging.debug(f"URL POST response: {response}")
        except Exception as e:
            # HANDLE CONNECTIVITY ERROR
            raise RuntimeError(f"url={api_url} : {e}")

        # HANDLE SERVER ERROR CODE
        if response.status_code not in (200, 201):
            raise RuntimeError(
                "url=%s - (code = %u)\ncontent=%r)"
                % (
                    api_url,
                    response.status_code,
                    response.content,
                )
            )

        try:
            j = json.loads(response.content.decode("utf-8"))
        except Exception as e:
            # Handle JSON ERROR
            raise RuntimeError(f"Unable to parse JSON : {e}")

        return j            
            
            
#######################################################################
#### Class Account
#######################################################################
class Account:
    
    # Constructor
    def __init__(self, account):
        
        self.type = account["type"]
        self.firstName = account["first_name"]
        self.lastName = account["last_name"]
        self.lastName = account["email"]
        self.json = account
        logging.info("account: %s", account)
    # Store in db
    def store(self,db):
        
        if self.json is not None:
            logging.debug("Store account into database")
            config_query = f"INSERT OR REPLACE INTO config VALUES (?, ?)"
            db.cur.execute(config_query, ["whoami", json.dumps(self.json)])
            


#######################################################################
#### Class PCE
#######################################################################    
class Pce:
    
    # Constructor
    def __init__(self, pce):
        
        # Init attributes
        self.alias = None
        self.pceId = None
        self.activationDate = None
        self.freqenceReleve = None
        self.state = None
        self.ownerName = None
        self.postalCode = None
        self.alias = None
        self.measureList = []
        self.thresholdList = []
        self.dailyMeasureStart = None
        self.dailyMeasureEnd = None
        
        # Set attributes
        self.alias = pce["alias"]
        self.pceId = pce["pce"]
        self.activationDate = _convertDateTime(pce["dateActivation"])
        self.frequenceReleve = pce["frequenceReleve"]
        self.state = pce["etat"]
        self.ownerName = pce["nomTitulaire"]
        self.postalCode = pce["codePostal"]
        self.json = pce
        
        
    # Store PCE into database
    def store(self,db):
        
        if self.json is not None:
            logging.debug("Store PCE %s into database",self.pceId)
            pce_query = f"INSERT OR REPLACE INTO pces VALUES (?, ?, ?, ?, ?, ?, ?)"
            db.cur.execute(pce_query, [self.pceId, self.alias, self.activationDate, self.frequenceReleve, self.state,
                                       self.ownerName, self.postalCode])
               
    
    # Add a measure to the PCE    
    def addMeasure(self, measure):
        self.measureList.append(measure)
        
    # Add a threshold to the PCE    
    def addThreshold(self, threshold):
        self.thresholdList.append(threshold)
        
    # Return the number of measure for the PCE and a type
    def countMeasure(self,type):
        i = 0
        for myMeasure in self.measureList:
            if type is None:
                i += 1
            elif myMeasure.type == type:
                i += 1
        return i
    
    # Return the number of threshold for the PCE
    def countThreshold(self):
        return len(self.thresholdList)
    
    # Return the number of valid measure for the PCE
    def countMeasureOk(self,type):
        i = 0
        for myMeasure in self.measureList:
            if myMeasure.type == type and myMeasure.isOk() == True:
                i += 1
        return i
    
    # Return PCE quality status
    def isOk(self):
        # To be ok, the PCE must contains at least one valid informative measure
        if not self.countMeasure(TYPE_I):
           return False
        elif not self.countMeasureOk(TYPE_I):
           return False
        else:
           return True 
    
    # Return the last valid measure for the PCE and a type
    def getLastMeasureOk(self,type):
        
        i = self.countMeasure(None) - 1
        measure = None
        
        while i>=0:
            if self.measureList[i].isOk() == True and self.measureList[i].type == type:
                measure = self.measureList[i]
                break;
            i -= 1
        
        return measure
    
    # Calculated measures from database
    def calculateMeasures(self,db,thresholdPercentage,type):
        
        # Get last valid measure as reference
        myMeasure = self.getLastMeasureOk(type)
        
        # Get current date, week, month and year
        dateNow = datetime.date.today()
        monthNow = int(dateNow.strftime("%m"))
        yearNow = int(dateNow.strftime("%Y"))
        logging.debug("Today : date %s, month %s, year %s",dateNow,monthNow,yearNow)
        weekNowFirstDate = dateNow - datetime.timedelta(days=dateNow.weekday() % 7)
        weekNowFirstDate = weekNowFirstDate
        monthNowFirstDate = datetime.datetime(yearNow,monthNow, 1).date()
        yearNowFirstDate = datetime.datetime(yearNow, 1, 1).date()
        logging.debug("First dates : week %s, month %s, year %s",weekNowFirstDate,monthNowFirstDate,yearNowFirstDate)
        
        
        # When db connexion is ok
        if db.cur and myMeasure:
        
            # Calendar measures
            
            ## Calculate Y0 gas
            startStr = f"'{dateNow}','start of year','-1 day'"
            endStr = f"'{dateNow}'"
            self.gasY0 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("Y0 gas : %s m3",self.gasY0)
            
            ## Calculate Y1 gas
            startStr = f"'{dateNow}','start of year','-1 year','-1 day'"
            endStr = f"'{dateNow}','start of year','-1 day'"
            self.gasY1 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("Y1 gas : %s m3",self.gasY1)
            
            ## Calculate Y2 gas
            startStr = f"'{dateNow}','start of year','-2 year','-1 day'"
            endStr = f"'{dateNow}','start of year','-1 year','-1 day'"
            self.gasY2 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("Y2 gas : %s m3",self.gasY2)
            
            ## Calculate M0Y0 gas
            startStr = f"'{dateNow}','start of month','-1 day'"
            endStr = f"'{dateNow}'"
            self.gasM0Y0 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("M0Y0 gas : %s m3",self.gasM0Y0)
            
            ## Calculate M1Y0 gas
            startStr = f"'{dateNow}','start of month','-1 month','-1 day'"
            endStr = f"'{dateNow}','start of month','-1 day'"
            self.gasM1Y0 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("M1Y0 gas : %s m3",self.gasM1Y0)
            
            ## Calculate M0Y1 gas
            startStr = f"'{dateNow}','start of month','-1 year','-1 day'"
            endStr = f"'{dateNow}','start of month','-11 months','-1 day'"
            self.gasM0Y1 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("M0Y1 gas : %s m3",self.gasM0Y1)
            
            ## Calculate W0Y0 gas
            startStr = f"'{weekNowFirstDate}','-1 day'"
            endStr = f"'{dateNow}'"
            self.gasW0Y0 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("W0Y0 gas : %s m3",self.gasW0Y0)
            
            ## Calculate W1Y0 gas
            startStr = f"'{weekNowFirstDate}','-8 days'"
            endStr = f"'{weekNowFirstDate}','-1 day'"
            self.gasW1Y0 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("W1Y0 gas : %s m3",self.gasW1Y0)
            
            ## Calculate W0Y1 gas
            startStr = f"'{weekNowFirstDate}','-1 year','-1 day'"
            endStr = f"'{weekNowFirstDate}','-1 year','+7 days'"
            self.gasW0Y1 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("W0Y1 gas : %s m3",self.gasW0Y1)
            
            ## Calculate D1 gas
            startStr = f"'{dateNow}','-2 day'"
            endStr = f"'{dateNow}','-1 day'"
            self.gasD1 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("D-1 gas : %s m3",self.gasD1)
            
            ## Calculate D2 gas
            startStr = f"'{dateNow}','-3 day'"
            endStr = f"'{dateNow}','-2 day'"
            self.gasD2 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("D-2 gas : %s m3",self.gasD2)
            
            ## Calculate D3 gas
            startStr = f"'{dateNow}','-4 day'"
            endStr = f"'{dateNow}','-3 day'"
            self.gasD3 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("D-3 gas : %s m3",self.gasD3)
            
            ## Calculate D4 gas
            startStr = f"'{dateNow}','-5 day'"
            endStr = f"'{dateNow}','-4 day'"
            self.gasD4 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("D-4 gas : %s m3",self.gasD4)
            
            ## Calculate D5 gas
            startStr = f"'{dateNow}','-6 day'"
            endStr = f"'{dateNow}','-5 day'"
            self.gasD5 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("D-5 gas : %s m3",self.gasD5)
            
            ## Calculate D6 gas
            startStr = f"'{dateNow}','-7 day'"
            endStr = f"'{dateNow}','-6 day'"
            self.gasD6 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("D-6 gas : %s m3",self.gasD6)
            
            ## Calculate D7 gas
            startStr = f"'{dateNow}','-8 day'"
            endStr = f"'{dateNow}','-7 day'"
            self.gasD7 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("D-7 gas : %s m3",self.gasD7)
            
            ## Calculate D1 gas gross
            dateStr = f"'{dateNow}','-1 day'"
            self.gasGrossD1 = self._getGrossCons(db,dateStr,type)
            logging.debug("D-1 gasGross : %s m3",self.gasGrossD1)
            
            ## Calculate D2 gas gross
            dateStr = f"'{dateNow}','-2 day'"
            self.gasGrossD2 = self._getGrossCons(db,dateStr,type)
            logging.debug("D-2 gasGross : %s m3",self.gasGrossD2)            

            ## Calculate D3 gas gross
            dateStr = f"'{dateNow}','-3 day'"
            self.gasGrossD3 = self._getGrossCons(db,dateStr,type)
            logging.debug("D-3 gasGross : %s m3",self.gasGrossD3)

            ## Calculate D4 gas gross
            dateStr = f"'{dateNow}','-4 day'"
            self.gasGrossD4 = self._getGrossCons(db,dateStr,type)
            logging.debug("D-4 gasGross : %s m3",self.gasGrossD4)              
            
            ## Calculate D5 gas gross
            dateStr = f"'{dateNow}','-5 day'"
            self.gasGrossD5 = self._getGrossCons(db,dateStr,type)
            logging.debug("D-5 gasGross : %s m3",self.gasGrossD5)

            ## Calculate D6 gas gross
            dateStr = f"'{dateNow}','-6 day'"
            self.gasGrossD6 = self._getGrossCons(db,dateStr,type)
            logging.debug("D-6 gasGross : %s m3",self.gasGrossD6)

            ## Calculate D7 gas gross
            dateStr = f"'{dateNow}','-7 day'"
            self.gasGrossD7 = self._getGrossCons(db,dateStr,type)
            logging.debug("D-7 gasGross : %s m3",self.gasGrossD7)              
            
            # Rolling measures
            
            ## Calculate R1Y
            startStr = f"'{dateNow}','-1 year'"
            endStr = f"'{dateNow}','-1 day'"
            self.gasR1Y = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("R1Y gas : %s m3",self.gasR1Y)
            
            ## Calculate R2Y1Y
            startStr = f"'{dateNow}','-2 year'"
            endStr = f"'{dateNow}','-1 year','-1 day'"
            self.gasR2Y1Y = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("R2Y1Y gas : %s m3",self.gasR2Y1Y)
            
            ## Calculate R1M
            startStr = f"'{dateNow}','-1 month'"
            endStr = f"'{dateNow}','-1 day'"
            self.gasR1M = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("R1M gas : %s m3",self.gasR1M)
            
            ## Calculate R2M1M
            startStr = f"'{dateNow}','-2 month'"
            endStr = f"'{dateNow}','-1 month','-1 day'"
            self.gasR2M1M = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("R2M1M gas : %s m3",self.gasR2M1M)
            
            ## Calculate R1MY1
            startStr = f"'{dateNow}','-1 month','-1 year'"
            endStr = f"'{dateNow}','-1 year','-1 day'"
            self.gasR1MY1 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("R1MY1 gas : %s m3",self.gasR1MY1)
            
            ## Calculate R1MY2
            startStr = f"'{dateNow}','-1 month','-2 year'"
            endStr = f"'{dateNow}','-2 year','-1 day'"
            self.gasR1MY2 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("R1MY2 gas : %s m3",self.gasR1MY2)
            
            ## Calculate R1W
            startStr = f"'{dateNow}','-7 days'"
            endStr = f"'{dateNow}','-1 day'"
            self.gasR1W = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("R1W gas : %s m3",self.gasR1W)
            
            ## Calculate R2W1W
            startStr = f"'{dateNow}','-14 days'"
            endStr = f"'{dateNow}','-7 days','-1 day'"
            self.gasR2W1W = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("R2W1W gas : %s m3",self.gasR2W1W)
            
            ## Calculate R1WY1
            startStr = f"'{dateNow}','-7 days','-1 year'"
            endStr = f"'{dateNow}','-1 year','-1 day'"
            self.gasR1WY1 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("R1WY1 gas : %s m3",self.gasR1WY1)
            
            ## Calculate R1WY2
            startStr = f"'{dateNow}','-7 days','-2 year'"
            endStr = f"'{dateNow}','-2 year','-1 day'"
            self.gasR1WY2 = self._getDeltaCons(db,startStr,endStr,type)
            logging.debug("R1WY2 gas : %s m3",self.gasR1WY2)
            
            
            # Thresholds measures
            
            ## Get M0 threshold
            startStr = f"'{dateNow}','start of month'"
            endStr = startStr
            self.tshM0 = self._getThreshold(db,startStr)
            logging.debug("M0 threshold : %s m3",self.tshM0)
            
            ## Get M0 conversion factor
            startStr = f"'{dateNow}','start of month'"
            endStr = f"'{dateNow}'"
            self.convM0 = self._getConversion(db,startStr,endStr,type)
            logging.debug("M0 factor : %s kwh / m3",self.convM0)
            
            ## M0 threshold percentage
            self.tshM0Pct = None
            self.tshM0Warn = None
            self.tshM0Pct = 0 # initial value
            self.tshM0Warn = "OFF" # initial value
            if self.tshM0 and self.gasM0Y0 and self.convM0 and thresholdPercentage:
                if self.tshM0 > 0:
                    self.tshM0Pct = round(((self.gasM0Y0 * self.convM0) / self.tshM0)*100)
                    if self.tshM0Pct > thresholdPercentage:
                        self.tshM0Warn = "ON"
            
            ## Get M1 threshold
            startStr = f"'{dateNow}','start of month','-1 month'"
            endStr = startStr
            self.tshM1 = self._getThreshold(db,startStr)
            logging.debug("M1 threshold : %s m3",self.tshM1)
            
            ## Get M1 conversion factor
            startStr = f"'{dateNow}','start of month','-1 month'"
            endStr = f"'{dateNow}','start of month','-1 day'"
            self.convM1 = self._getConversion(db,startStr,endStr,type)
            logging.debug("M1 factor : %s kwh / m3",self.convM1)
            
            
            ## M1 threshold percentage
            self.tshM1Pct = None
            self.tshM1Warn = None
            if self.tshM1 and self.gasM1Y0 and self.convM1 and thresholdPercentage:
                if self.tshM1 > 0:
                    self.tshM1Pct = round(((self.gasM1Y0 * self.convM1) / self.tshM1)*100)
                    if self.tshM1Pct > thresholdPercentage:
                        self.tshM1Warn = "ON"
                    else:
                        self.tshM1Warn = "OFF"
                    
            
    
    # Return the index difference between 2 measures 
    def _getDeltaCons(self,db,startStr,endStr,type):
        
        logging.debug("Retrieve delta conso between %s and %s",startStr,endStr)
        
        # We need to have at least 2 records to measure a delta index
        query = f"SELECT CASE WHEN COUNT(ALL) > 1 THEN max(end_index) - min(end_index) ELSE NULL END FROM measures WHERE pce = '{self.pceId}' AND type = '{type}' AND date BETWEEN date({startStr}) AND date({endStr}) GROUP BY pce"
        db.cur.execute(query)
        queryResult = db.cur.fetchone()
        if queryResult is not None:
            if queryResult[0] is not None:
                valueResult = int(queryResult[0])
                if valueResult >= 0:
                    return valueResult
                else:
                    logging.debug("Delta conso value is not valid : %s",valueResult)
                    return 0
            else:
                logging.debug("Delta conso could not be calculated because only 1 record has been found.")
                return 0
        else:
            logging.debug("Delta conso could not be calculated")
            return 0
            
    def _getGrossCons(self,db,cDate,type):
        
        logging.debug("Retrieve gross conso for: %s",cDate)
        
        # We need to have at least 2 records to measure a delta index
        query = f"SELECT volumeGrossConsumed FROM measures WHERE pce = '{self.pceId}' AND type = '{type}' AND date = date({cDate}) GROUP BY pce"
        db.cur.execute(query)
        queryResult = db.cur.fetchone()
        if queryResult is not None:
            valueResult = queryResult[0]
            if valueResult >= 0:
                return valueResult
            else:
                logging.debug("Gross conso value is not valid : %s",valueResult)
                return 0
        else:
            logging.debug("Gross conso could not be calculated")
            return 0            
    
    # Return the conversion factor max between 2 measures 
    def _getConversion(self,db,startStr,endStr,type):
        
        logging.debug("Retrieve conversion factor between %s and %s",startStr,endStr)
        
        query = f"SELECT max(conversion) FROM measures WHERE pce = '{self.pceId}' AND type = '{type}' AND date BETWEEN date({startStr}) AND date({endStr}) GROUP BY pce, type"
        db.cur.execute(query)
        queryResult = db.cur.fetchone()
        if queryResult is not None:
            if queryResult[0] is not None:
                valueResult = int(queryResult[0])
                if valueResult >= 0:
                    return valueResult
                else:
                    logging.debug("Conversion factor value is not valid : %s",valueResult)
                    return None
            else:
                logging.debug("Conversion factor could not be calculated.")
                return None
        else:
            logging.debug("Conversion factor could not be calculated.")
            return None
    
    # Return the threshold for a particular month 
    def _getThreshold(self,db,startStr):
        
        logging.debug("Retrieve threshold at date %s",startStr)
        
        query = f"SELECT energy FROM thresholds WHERE pce = '{self.pceId}' AND date = date({startStr})"
        db.cur.execute(query)
        queryResult = db.cur.fetchone()
        if queryResult is not None:
            if queryResult[0] is not None:
                valueResult = int(queryResult[0])
                if valueResult >= 0:
                    return valueResult
                else:
                    logging.debug("Threshold value is not valid : %s",valueResult)
                    return 0
            else:
                logging.debug("Threshold could not be calculated.")
                return 0
        else:
            logging.debug("Threshold could not be calculated")
            return 0
        
#######################################################################
#### Class Measure
#######################################################################                
class Measure:
    
    # Constructor
    def __init__(self, pce, measure,type):
        
        # Log the raw measure data for debugging
        logging.debug("Measure data received: %s", json.dumps({
            "volumeBrutConsomme": measure.get("volumeBrutConsomme"),
            "volumeConverti": measure.get("volumeConverti"),
            "indexDebut": measure.get("indexDebut"),
            "indexFin": measure.get("indexFin"),
            "type": type
        }, indent=2))
        
        # Init attributes
        self.type = type # Daily, Published
        self.startDateTime = None
        self.endDateTime = None
        self.gasDate = None
        self.startIndex = None
        self.endIndex = None
        self.volume = None
        self.volumeGross = None
        self.volumeInitial = None
        self.energy = None
        self.energyGross = 0
        self.temperature = None
        self.price = 0
        self.conversionFactor = None
        self.pce = None
        self.isDeltaIndex = False

        # Set attributes
        if measure["dateDebutReleve"]: self.startDateTime = _convertDateTime(measure["dateDebutReleve"])
        if measure["dateFinReleve"]: self.endDateTime = _convertDateTime(measure["dateFinReleve"])
        if measure["journeeGaziere"]: self.gasDate = _convertDate(measure["journeeGaziere"])
        elif self.startDateTime:
            self.gasDate = self.startDateTime.date()
        if measure["indexDebut"]: self.startIndex = int(measure["indexDebut"])
        if measure["indexFin"]: self.endIndex = int(measure["indexFin"])
        if measure["volumeBrutConsomme"]: 
            self.volumeGross = float(measure["volumeBrutConsomme"])
            self.volume = int(measure["volumeBrutConsomme"])
            logging.debug("Volume extracted from volumeBrutConsomme: %s m3 (type: %s)", self.volume, type)
        elif measure["volumeConverti"]:
            self.volume = int(measure["volumeConverti"])
            logging.debug("Volume extracted from volumeConverti: %s m3 (type: %s)", self.volume, type)
        if measure["energieConsomme"]: self.energy = int(measure["energieConsomme"])
        if measure["temperature"]: self.temperature = float(measure["temperature"])
        if measure["coeffConversion"]: self.conversionFactor = float(measure["coeffConversion"])
        if measure["coeffConversion"] and measure["volumeBrutConsomme"]: 
            self.energyGross = float(measure["volumeBrutConsomme"]) * float(measure["coeffConversion"])
        self.pce = pce
        
        
        # Fix informative volume and energy provided when required
        # When provided volume is not equal to delta index, we replace it by delta index
        # and we recalculate energy using delta index and conversion factor
        if self.isOk():
            deltaIndex = self.endIndex - self.startIndex
            if deltaIndex != self.volume and self.type == TYPE_I:
                logging.debug("Gas consumption of type %s, volume (%s m3) of measure %s has been replaced by the delta index (%s m3)",self.type, self.volume,self.gasDate,deltaIndex)
                self.volume = deltaIndex
                self.isDeltaIndex = True
                if self.conversionFactor:
                    self.energy = round(self.volume * self.conversionFactor)
            if deltaIndex != self.volume and self.type == TYPE_P:
                logging.debug("Gas consumption of type %s, volume (%s m3) of measure %s has been replaced by the delta index (%s m3)",self.type, self.volume,self.gasDate,deltaIndex)
                self.volume = deltaIndex
                self.isDeltaIndex = True
                if self.conversionFactor:
                    self.energy = round(self.volume * self.conversionFactor)

    # Store measure to database
    def store(self,db):

        dbTable = None
        if self.type == "informative":
            dbTable = "consumption_daily"
        elif self.type == "published":
            dbTable = "consumption_published"

        if self.isOk() and dbTable:
            logging.debug("Store measure type %s, %s,%s,%s, %s, %s, %s m3, %s m3, %s kWh, %s kWh, %s EUR, %s kwh/m3",self.type,str(self.gasDate),str(self.startDateTime), str(self.endDateTime),str(self.startIndex),str(self.endIndex), str(self.volume), str(self.volumeGross), str(self.energy), str(self.energyGross), self.price, str(self.conversionFactor))
            measure_query = f"INSERT OR REPLACE INTO measures VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            db.cur.execute(measure_query, [self.pce.pceId, self.type, self.gasDate, self.startDateTime, self.endDateTime, self.startIndex, self.endIndex, self.volume, self.volumeGross, self.energy, self.energyGross, self.price, self.conversionFactor])
        
    
    # Return measure measure quality status
    def isOk(self):
        
        if (self.volume == None and self.volumeGross == None): return False
        elif self.energy == None: return False
        elif self.startIndex == None: return False
        elif self.endIndex == None: return False
        elif self.gasDate == None: return False
        else: return True


#######################################################################
#### Class Threshold
#######################################################################   
class Threshold:
    
    # Constructor
    def __init__(self, pce, threshold):
        
        # Init attributes
        self.year = None
        self.month = None
        self.energy = None
        self.date = None
        
        # Set attributes
        if threshold["valeur"]: self.energy = int(threshold["valeur"])
        if threshold["annee"]: self.year = int(threshold["annee"])
        if threshold["mois"]: self.month = int(threshold["mois"])
        if self.year and self.month:
            # Set date to the first day of the month/year
            self.date = datetime.date(self.year,self.month,1)
        self.pce = pce
        
    # Store threshold to database
    def store(self,db):
        
        if self.isOk():
            logging.debug("Store threshold %s, %s kWh",str(self.date), str(self.energy))
            measure_query = f"INSERT OR REPLACE INTO thresholds VALUES (?, ?, ?)"
            db.cur.execute(measure_query, [self.pce.pceId, self.date, self.energy])
        
    # Return threshold quality status
    def isOk(self):
        if self.date == None: return False
        elif self.energy == None: return False
        else: return True
