#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import datetime
import schedule
import time
from dateutil.relativedelta import relativedelta
import logging

import gazpar
import mqtt
import standalone
import hass
import param
import database
import influxdb
import price
import datetime as dt
from hass_ws import HomeAssistantWs


# gazpar2mqtt constants
G2M_VERSION = '0.8.7'
G2M_DB_VERSION = '0.4.0'
G2M_INFLUXDB_VERSION = '0.1.0'

#######################################################################
#### Functions
#######################################################################

# Sub to get date with year offset
def _getYearOfssetDate(day, number):
    return day - relativedelta(years=number)

# Sub to return format wanted
def _dateTimeToStr(datetime):
    return datetime.strftime("%d/%m/%Y - %H:%M:%S")

# Sub to wait between 2 GRDF tries
def _waitBeforeRetry(tryCount):
    waitTime = round(gazpar._getRetryTimeSleep(tryCount))
    if waitTime < 200:
        logging.info("Wait %s seconds (%s min) before next try",waitTime,round(waitTime/60))
    else:
        logging.info("Wait %s minutes before next try",round(waitTime/60))
    time.sleep(waitTime)

########################################################################################################################
#### Running program
########################################################################################################################
def run(myParams):

    myMqtt = None
    myGrdf = None

    # Store time now
    dtn = _dateTimeToStr(datetime.datetime.now())


    # STEP 1 : Connect to database
    ####################################################################################################################
    logging.info("-----------------------------------------------------------")
    logging.info("#        Connection to SQLite database                     #")
    logging.info("-----------------------------------------------------------")

    # Create/Update database
    logging.info("Connection to SQLite database...")
    myDb = database.Database(myParams.dbPath)


    # Connect to database
    myDb.connect(G2M_VERSION,G2M_DB_VERSION,G2M_INFLUXDB_VERSION)
    if myDb.isConnected() :
        logging.info("SQLite database connected !")
    else:
        logging.error("Unable to connect to SQLite database.")

    # Check program version
    g2mVersion = myDb.getConfig(database.G2M_KEY)
    g2mDate = myDb.getConfig(database.LAST_EXEC_KEY)
    logging.info("Last execution date %s, program was in version %s.",g2mDate,g2mVersion)
    if g2mVersion != G2M_VERSION:
        logging.warning("gazpar2mqtt version (%s) has changed since last execution (%s)",G2M_VERSION,g2mVersion)
        # Update program version
        myDb.updateVersion(database.G2M_KEY,G2M_VERSION)
        myDb.commit()


    # Reinit database when required :
    if myParams.dbInit:
        logging.info("Reinitialization of the database...")
        myDb.reInit(G2M_VERSION,G2M_DB_VERSION,G2M_INFLUXDB_VERSION)
        logging.info("Database reinitialized to version %s",G2M_DB_VERSION)
    else:
        # Compare dabase version
        logging.info("Checking database version...")
        dbVersion = myDb.getConfig(database.DB_KEY)
        if dbVersion == G2M_DB_VERSION:
            logging.info("Your database is already up to date : version %s.",G2M_DB_VERSION)

            # Display current database statistics
            logging.info("Retrieve database statistics...")
            dbStats = myDb.getMeasuresCount(gazpar.TYPE_I)
            logging.info("%s informatives measures stored", dbStats["rows"])
            logging.info("%s PCE(s)", dbStats["pce"])
            logging.info("First measure : %s", dbStats["minDate"])
            logging.info("Last measure : %s", dbStats["maxDate"])

        else:
            logging.warning("Your database (version %s) is not up to date.",dbVersion)
            logging.info("Reinitialization of your database to version %s...",G2M_DB_VERSION)
            myDb.reInit(G2M_VERSION,G2M_DB_VERSION,G2M_INFLUXDB_VERSION)
            dbVersion = myDb.getConfig(database.DB_KEY)
            logging.info("Database reinitialized to version %s !",dbVersion)


    # STEP 2 : Log to MQTT broker
    ####################################################################################################################
    logging.info("-----------------------------------------------------------")
    logging.info("#              Connection to Mqtt broker                   #")
    logging.info("-----------------------------------------------------------")

    try:

        logging.info("Connect to Mqtt broker...")
        
        # Create mqtt client      
        myMqtt = mqtt.Mqtt(myParams.mqttClientId,myParams.mqttUsername,myParams.mqttPassword,myParams.mqttSsl,myParams.mqttQos,myParams.mqttRetain)   
        
        # Connect mqtt broker
        myMqtt.connect(myParams.mqttHost,myParams.mqttPort)

        # Wait for connection callback
        time.sleep(2)

        if myMqtt.isConnected:
            logging.info("Mqtt broker connected !")

    except:
        logging.error("Unable to connect to Mqtt broker. Please check that broker is running, or check broker configuration.")

    # STEP 3 : Get data from GRDF website
    ####################################################################################################################
    if myMqtt.isConnected:

        logging.info("-----------------------------------------------------------")
        logging.info("#            Get data from GRDF website                   #")
        logging.info("-----------------------------------------------------------")

        tryCount = 0
        # Connection
        while tryCount < gazpar.GRDF_API_MAX_RETRIES :
            try:

                tryCount += 1

                # Create Grdf instance
                logging.debug("Connection to GRDF, try %s/%s...",tryCount,gazpar.GRDF_API_MAX_RETRIES)
                myGrdf = gazpar.Grdf()
                logging.debug("After myGrdf")
                # Connect to Grdf website

                myGrdf.login(myParams.grdfUsername,myParams.grdfPassword)


                # Check connection
                if myGrdf.isConnected:
                    logging.info("GRDF connected !")
                    break
                else:
                    logging.info("Unable to login to GRDF website")
                    myGrdf = None  # Reset to None on failed login
                    _waitBeforeRetry(tryCount)

            except Exception as e:
                logging.error("Error during GRDF login: %s", str(e))
                myGrdf = None  # Reset to None on exception
                _waitBeforeRetry(tryCount)


        # When GRDF is connected
        if myGrdf is not None and myGrdf.isConnected:

            # Sub-step 3A : Get account info
            try:

                # Get account informations and store it to db
                logging.info("Retrieve account informations")
                myAccount = myGrdf.getWhoami()
                logging.info("MyAccount: %s", myAccount)
                myAccount.store(myDb)
                myDb.commit()

            except:
                logging.warning("Unable to get account information from GRDF website.")


            # Sub-step 3B : Get list of PCE
            logging.info("Retrieve list of PCEs...")
            try:
                myGrdf.getPceList()
                logging.info("%s PCE found !",myGrdf.countPce())
            except:
                myGrdf.isConnected = False
                logging.info("Unable to get any PCE !")

            # Loop on PCE
            if myGrdf.pceList:
                for myPce in myGrdf.pceList:

                    # Store PCE in database
                    myPce.store(myDb)
                    myDb.commit()


                    # Sub-step 3C : Get measures of the PCE

                    # Get measures of the PCE
                    logging.info("---------------------------------")
                    logging.info("Get measures of PCE %s alias %s",myPce.pceId,myPce.alias)


                    # Set date range
                    if not myParams.grdfStartDate: myParams.grdfStartDate = '2020-01-01' # can be omitted if param.py back to default
                    minDateTimeLimit = _getYearOfssetDate(datetime.datetime.now(), 3) # GRDF min date is 3 years ago
                    minDateTime = datetime.datetime.strptime(myParams.grdfStartDate, "%Y-%m-%d")
                    startDate = minDateTime.date()
                    endDate = datetime.date.today()
                    if minDateTime < minDateTimeLimit:
                        startDate = minDateTimeLimit.date()
                        logging.info("Range period : from %s (3 years ago) to %s (today) ...",startDate,endDate)
                    
                    logging.info("Range period : from %s (self defined) to %s (today) ...",startDate,endDate)
                    

                    # Get informative measures
                    logging.info("---------------")
                    logging.info("Retrieve informative measures...")
                    try:
                        myGrdf.getPceMeasures(myPce,startDate,endDate,gazpar.TYPE_I)
                        logging.info("Informative measures found !")
                    except:
                        logging.error("Error during informative measures collection")


                    # Analyse data
                    measureCount = myPce.countMeasure(gazpar.TYPE_I)
                    if measureCount > 0:
                        logging.info("Analysis of informative measures provided by GRDF...")
                        logging.info("%s informative measures provided by Grdf", measureCount)
                        measureOkCount = myPce.countMeasureOk(gazpar.TYPE_I)
                        logging.info("%s informative measures are ok", measureOkCount)
                        accuracy = round((measureOkCount/measureCount)*100)
                        logging.info("Accuracy is %s percent",accuracy)

                        # Get last informative measure
                        myMeasure = myPce.getLastMeasureOk(gazpar.TYPE_I)
                        if myMeasure:
                            logging.info("Last valid informative measure provided by GRDF : ")
                            logging.info("Date = %s", myMeasure.gasDate)
                            logging.info("Start index = %s, End index = %s", myMeasure.startIndex, myMeasure.endIndex)
                            logging.info("Volume = %s m3, Energy = %s kWh, Factor = %s", myMeasure.volume, myMeasure.energy,
                                         myMeasure.conversionFactor)
                            if myMeasure.isDeltaIndex:
                                logging.warning("Inconsistencies detected on the measure : ")
                                logging.warning(
                                    "Volume provided by Grdf (%s m3) has been replaced by the volume between start index and end index (%s m3)",
                                    myMeasure.volumeInitial, myMeasure.volume)
                        else:
                            logging.warning("Unable to find the last informative measure.")


                    # Get published measures
                    logging.info("---------------")
                    logging.info("Retrieve published measures...")
                    try:
                        myGrdf.getPceMeasures(myPce, startDate, endDate, gazpar.TYPE_P)
                        logging.info("Published measures found !")
                    except:
                        logging.error("Error during published measures collection")

                    # Analyse data
                    measureCount = myPce.countMeasure(gazpar.TYPE_P)
                    if measureCount > 0:
                        logging.info("Analysis of published measures provided by GRDF...")
                        logging.info("%s published measures provided by Grdf", measureCount)
                        measureOkCount = myPce.countMeasureOk(gazpar.TYPE_P)
                        logging.info("%s published measures are ok", measureOkCount)
                        accuracy = round((measureOkCount / measureCount) * 100)
                        logging.info("Accuracy is %s percent", accuracy)

                        # Get last published measure
                        myMeasure = myPce.getLastMeasureOk(gazpar.TYPE_P)
                        if myMeasure:
                            logging.info("Last valid published measure provided by GRDF : ")
                            logging.info("Start date = %s, End date = %s", myMeasure.startDateTime, myMeasure.endDateTime)
                            logging.info("Start index = %s, End index = %s", myMeasure.startIndex, myMeasure.endIndex)
                            logging.info("Volume = %s m3, Energy = %s kWh, Factor = %s", myMeasure.volume, myMeasure.energy,
                                         myMeasure.conversionFactor)
                            if myMeasure.isDeltaIndex:
                                logging.warning("Inconsistencies detected on the measure : ")
                                logging.warning(
                                    "Volume provided by Grdf (%s m3) has been replaced by the volume between start index and end index (%s m3)",
                                    myMeasure.volumeInitial, myMeasure.volume)
                        else:
                            logging.warning("Unable to find the last published measure.")

                    # Store to database
                    logging.info("---------------")
                    if myPce.measureList:
                        logging.info("Update of database with retrieved measures...")
                        for myMeasure in myPce.measureList:
                            # Store measure into database
                            myMeasure.store(myDb)

                        # Commmit database
                        myDb.commit()
                        logging.info("Database updated !")

                    else:
                        logging.info("Unable to store any measure for PCE %s to database !",myPce.pceId)


                    # Sub-step 3D : Get thresholds of the PCE

                    # Get threshold
                    logging.info("---------------")
                    logging.info("Retrieve PCE's thresholds from GRDF...")
                    try:
                        myGrdf.getPceThreshold(myPce)
                        thresholdCount = myPce.countThreshold()
                        logging.info("%s thresholds found !",thresholdCount)

                    except:
                        logging.warning("Error to get PCE's thresholds, verify if you have setup thresholds for your PCE/account")

                    # Update database
                    if myPce.thresholdList:
                        # Store thresholds into database
                        logging.info("Update of database with retrieved thresholds...")
                        for myThreshold in myPce.thresholdList:
                            myThreshold.store(myDb)
                        # Commmit database
                        myDb.commit()
                        logging.info("Database updated !")


                    # Sub-step 3E : Calculate measures of the PCE

                    # Calculate informative measures
                    try:
                        myPce.calculateMeasures(myDb,myParams.thresholdPercentage,gazpar.TYPE_I)
                    except:
                        logging.error("Unable to calculate informative measures")


            else:
                logging.info("No PCE retrieved.")


                                                                                                                                                                                                                     
                     
    ####################################################################################################################     
    # STEP 5A : Standalone mode
    ####################################################################################################################
    if myMqtt.isConnected \
        and myParams.standalone \
        and myGrdf is not None and myGrdf.isConnected:

        try:

            logging.info("-----------------------------------------------------------")
            logging.info("#           Stand alone publication mode                  #")
            logging.info("-----------------------------------------------------------")
            
            # Loop on PCEs
            for myPce in myGrdf.pceList:

                logging.info("Publishing values of PCE %s alias %s...",myPce.pceId,myPce.alias)
                logging.info("---------------------------------")

                # Set parameters
                prefix = myParams.mqttTopic + '/' + myPce.pceId

                # Display topic root
                logging.info("You can retrieve published values subscribing topic %s/#",prefix)

                # Instantiate Standalone class by PCE
                mySa = standalone.Standalone(prefix)

                # Set values
                if not myPce.isOk(): # PCE is not correct

                    ## Publish status values
                    logging.info("Publishing to Mqtt status values...")
                    myMqtt.publish(mySa.statusTopic+"date", dtn)
                    myMqtt.publish(mySa.statusTopic+"connectivity", "OFF")
                    logging.info("Status values published !")


                else: # Values when Grdf succeeded



                    # Publish informative values
                    logging.info("Publishing to Mqtt...")

                    ## Last informative measure
                    myMeasure = myPce.getLastMeasureOk(gazpar.TYPE_I)
                    if myMeasure:
                        logging.debug("Creation of last informative measures")
                        myMqtt.publish(mySa.lastTopic+"date", myMeasure.gasDate)
                        myMqtt.publish(mySa.lastTopic+"energy", myMeasure.energy)
                        myMqtt.publish(mySa.lastTopic+"gas", myMeasure.volume)
                        myMqtt.publish(mySa.lastTopic+"index", myMeasure.endIndex)
                        myMqtt.publish(mySa.lastTopic+"conversion_Factor", myMeasure.conversionFactor)
                    else:
                        logging.warning("Unable to publish last measure infos.")

                    ## Last published measure
                    myMeasure = myPce.getLastMeasureOk(gazpar.TYPE_P)
                    if myMeasure:
                        logging.debug("Creation of last published measures")
                        myMqtt.publish(mySa.publishedTopic + "start_date", myMeasure.startDateTime)
                        myMqtt.publish(mySa.publishedTopic + "end_date", myMeasure.endDateTime)
                        myMqtt.publish(mySa.publishedTopic + "energy", myMeasure.energy)
                        myMqtt.publish(mySa.publishedTopic + "gas", myMeasure.volume)
                        myMqtt.publish(mySa.publishedTopic + "index", myMeasure.endIndex)
                        myMqtt.publish(mySa.publishedTopic + "conversion_Factor", myMeasure.conversionFactor)
                    else:
                        logging.warning("Unable to publish last measure infos.")

                    ## Calculated calendar measures
                    logging.debug("Creation of calendar measures")

                    ### Year
                    myMqtt.publish(mySa.histoTopic+"current_year_gas", myPce.gasY0)
                    myMqtt.publish(mySa.histoTopic+"previous_year_gas", myPce.gasY1)

                    ### Month
                    myMqtt.publish(mySa.histoTopic+"current_month_gas", myPce.gasM0Y0)
                    myMqtt.publish(mySa.histoTopic+"previous_month_gas", myPce.gasM1Y0)
                    myMqtt.publish(mySa.histoTopic+"current_month_previous_year_gas", myPce.gasM0Y1)

                    ### Week
                    myMqtt.publish(mySa.histoTopic+"current_week_gas", myPce.gasW0Y0)
                    myMqtt.publish(mySa.histoTopic+"previous_week_gas", myPce.gasW1Y0)
                    myMqtt.publish(mySa.histoTopic+"current_week_previous_year-gas", myPce.gasW0Y1)

                    ### Day
                    myMqtt.publish(mySa.histoTopic+"day-1_gas", myPce.gasD1)
                    myMqtt.publish(mySa.histoTopic+"day-2_gas", myPce.gasD2)
                    myMqtt.publish(mySa.histoTopic+"day-3_gas", myPce.gasD3)
                    myMqtt.publish(mySa.histoTopic+"day-4_gas", myPce.gasD4)
                    myMqtt.publish(mySa.histoTopic+"day-5_gas", myPce.gasD5)
                    myMqtt.publish(mySa.histoTopic+"day-6_gas", myPce.gasD6)
                    myMqtt.publish(mySa.histoTopic+"day-7_gas", myPce.gasD7)

                    ## Calculated rolling measures
                    logging.debug("Creation of rolling measures")

                    ### Rolling year
                    myMqtt.publish(mySa.histoTopic+"rolling_year_gas", myPce.gasR1Y)
                    myMqtt.publish(mySa.histoTopic+"rolling_year_last_year_gas", myPce.gasR2Y1Y)

                    ### Rolling month
                    myMqtt.publish(mySa.histoTopic+"rolling_month_gas", myPce.gasR1M)
                    myMqtt.publish(mySa.histoTopic+"rolling_month_last_month_gas", myPce.gasR2M1M)
                    myMqtt.publish(mySa.histoTopic+"rolling_month_last_year_gas", myPce.gasR1MY1)
                    myMqtt.publish(mySa.histoTopic+"rolling_month_last_2_year_gas", myPce.gasR1MY2)

                    ### Rolling week
                    myMqtt.publish(mySa.histoTopic+"rolling_week_gas", myPce.gasR1W)
                    myMqtt.publish(mySa.histoTopic+"rolling_week_last_week_gas", myPce.gasR2W1W)
                    myMqtt.publish(mySa.histoTopic+"rolling_week_last_year_gas", myPce.gasR1WY1)
                    myMqtt.publish(mySa.histoTopic+"rolling_week_last_2_year_gas", myPce.gasR1WY2)

                    ### Thresholds, only if existing
                    if myPce.tshM0:
                        myMqtt.publish(mySa.thresholdTopic+"current_month_threshold", myPce.tshM0)
                        myMqtt.publish(mySa.thresholdTopic+"current_month_threshold_percentage", myPce.tshM0Pct)
                        myMqtt.publish(mySa.thresholdTopic+"current_month_threshold_warning", myPce.tshM0Warn)
                        myMqtt.publish(mySa.thresholdTopic+"previous_month_threshold", myPce.tshM1)
                        myMqtt.publish(mySa.thresholdTopic+"previous_month_threshold_percentage", myPce.tshM1Pct)
                        myMqtt.publish(mySa.thresholdTopic+"previous_month_threshold_warning", myPce.tshM1Warn)

                    logging.info("All measures published !")

                    ## Publish status values
                    logging.info("Publishing to Mqtt status values...")
                    myMqtt.publish(mySa.statusTopic+"date", dtn)
                    myMqtt.publish(mySa.statusTopic+"connectivity", "ON")
                    logging.info("Status values published !")

                # Release memory
                del mySa

        except:
            logging.error("Standalone mode : unable to publish value to mqtt broker")

    ####################################################################################################################
    # STEP 5B : Home Assistant discovery mode
    ####################################################################################################################
    if myMqtt.isConnected \
        and myParams.hassDiscovery \
        and myGrdf is not None and myGrdf.isConnected:

        try:

            logging.info("-----------------------------------------------------------")
            logging.info("#           Home assistant publication mode               #")
            logging.info("-----------------------------------------------------------")

            # Create hass instance
            myHass = hass.Hass(myParams.hassPrefix)

            # Loop on PCEs
            for myPce in myGrdf.pceList:

                logging.info("Publishing values of PCE %s alias %s...",myPce.pceId,myPce.alias)
                logging.info("---------------------------------")


                # Create the device corresponding to the PCE
                deviceId = myParams.hassDeviceName.replace(" ","_") + "_" +  myPce.pceId
                deviceName = myParams.hassDeviceName + " " +  myPce.alias
                myDevice = hass.Device(myHass,myPce.pceId,deviceId,deviceName)

                # Create entity PCE
                logging.debug("Creation of the PCE entity")
                myEntity = hass.Entity(myDevice,hass.SENSOR,'pce_state','pce_state',hass.NONE_TYPE,None,None)
                myEntity.setValue(myPce.state)
                myEntity.addAttribute("pce_alias",myPce.alias)
                myEntity.addAttribute("pce_id",myPce.pceId)
                myEntity.addAttribute("freqence",myPce.freqenceReleve)
                myEntity.addAttribute("activation_date ",myPce.activationDate)
                myEntity.addAttribute("owner_name",myPce.ownerName)
                myEntity.addAttribute("postal_code",myPce.postalCode)

                # Process hass's entities to be valuated
                if not myPce.isOk(): # Values when PCE is not correct

                    # Create entities and set values
                    myEntity = hass.Entity(myDevice,hass.BINARY,'connectivity','Connectivity',hass.CONNECTIVITY_TYPE,None,None).setValue('OFF')

                else: # Values when PCE is correct


                    # Create entities and set values

                    ## Last informative measure
                    logging.debug("Creation of last informative measures entities")
                    myMeasure = myPce.getLastMeasureOk(gazpar.TYPE_I)
                    if myMeasure:
                        myEntity = hass.Entity(myDevice, hass.SENSOR, 'index', 'index', hass.GAS_TYPE, hass.ST_TTI,
                                               'm³').setValue(myMeasure.endIndex)
                        myEntity = hass.Entity(myDevice, hass.SENSOR, 'conversion_factor', 'conversion factor',
                                               None, None, 'kWh/m³').setValue(myMeasure.conversionFactor)
                        myEntity = hass.Entity(myDevice, hass.SENSOR, 'gas', 'gas', hass.GAS_TYPE, hass.ST_TT,
                                               'm³').setValue(myMeasure.volume)
                        myEntity = hass.Entity(myDevice, hass.SENSOR, 'energy', 'energy', hass.ENERGY_TYPE, hass.ST_TT,
                                               'kWh').setValue(myMeasure.energy)
                        myEntity = hass.Entity(myDevice, hass.SENSOR, 'consumption_date', 'consumption date',
                                               hass.NONE_TYPE, None, None).setValue(str(myMeasure.gasDate))
                    else:
                        logging.warning("Unable to publish last informative measure infos.")

                    ## Last published measure
                    logging.debug("Creation of last published measures entities")
                    myMeasure = myPce.getLastMeasureOk(gazpar.TYPE_P)
                    if myMeasure:
                        myEntity = hass.Entity(myDevice, hass.SENSOR, 'published_index', 'published index', hass.GAS_TYPE, hass.ST_TTI,
                                               'm³').setValue(myMeasure.endIndex)
                        myEntity = hass.Entity(myDevice, hass.SENSOR, 'published_conversion_factor', 'published conversion factor',
                                               None, None, 'kWh/m³').setValue(myMeasure.conversionFactor)
                        myEntity = hass.Entity(myDevice, hass.SENSOR, 'published_gas', 'published gas', hass.GAS_TYPE, hass.ST_TT,
                                               'm³').setValue(myMeasure.volume)
                        myEntity = hass.Entity(myDevice, hass.SENSOR, 'published_energy', 'published energy', hass.ENERGY_TYPE, hass.ST_TT,
                                               'kWh').setValue(myMeasure.energy)
                        myEntity = hass.Entity(myDevice, hass.SENSOR, 'published_consumption_start_date', 'published consumption start date',
                                               hass.NONE_TYPE, None, None).setValue(str(myMeasure.startDateTime))
                        myEntity = hass.Entity(myDevice, hass.SENSOR, 'published_consumption_end_date',
                                               'published consumption end date',
                                               hass.NONE_TYPE, None, None).setValue(str(myMeasure.endDateTime))
                    else:
                        logging.warning("Unable to publish last published measure infos.")

                    ## Calculated calendar measures
                    logging.debug("Creation of calendar entities")

                    ### Year
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'current_year_gas','current year gas',hass.GAS_TYPE,hass.ST_TTI,'m³').setValue(myPce.gasY0)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'previous_year_gas','previous year gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasY1)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'previous_2_year_gas','previous 2 years gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasY2)

                    ### Month
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'current_month_gas','current month gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasM0Y0)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'previous_month_gas','previous month gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasM1Y0)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'current_month_last_year_gas','current month of last year gas',hass.GAS_TYPE,hass.ST_TTI,'m³').setValue(myPce.gasM0Y1)

                    ### Week
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'current_week_gas','current week gas',hass.GAS_TYPE,hass.ST_TTI,'m³').setValue(myPce.gasW0Y0)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'previous_week_gas','previous week gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasW1Y0)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'current_week_last_year_gas','current week of last year gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasW0Y1)

                    ### Day
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'day_1_gas','day-1 gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasD1)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'day_2_gas','day-2 gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasD2)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'day_3_gas','day-3 gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasD3)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'day_4_gas','day-4 gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasD4)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'day_5_gas','day-5 gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasD5)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'day_6_gas','day-6 gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasD6)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'day_7_gas','day-7 gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasD7)
                    
                    ### Day Gross
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'day_1_gas_gross','day-1 gas gross',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasGrossD1)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'day_2_gas_gross','day-2 gas gross',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasGrossD2)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'day_3_gas_gross','day-3 gas gross',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasGrossD3)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'day_4_gas_gross','day-4 gas gross',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasGrossD4)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'day_5_gas_gross','day-5 gas gross',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasGrossD5)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'day_6_gas_gross','day-6 gas gross',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasGrossD6)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'day_7_gas_gross','day-7 gas gross',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasGrossD7)


                    ## Calculated rolling measures
                    logging.debug("Creation of rolling entities")

                    ### Rolling year
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'rolling_year_gas','rolling year gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasR1Y)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'rolling_year_last_year_gas','rolling year of last year gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasR2Y1Y)

                    ### Rolling month
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'rolling_month_gas','rolling month gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasR1M)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'rolling_month_last_month_gas','rolling month of last month gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasR2M1M)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'rolling_month_last_year_gas','rolling month of last year gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasR1MY1)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'rolling_month_last_2_year_gas','rolling month of last 2 years gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasR1MY2)

                    ### Rolling week
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'rolling_week_gas','rolling week gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasR1W)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'rolling_week_last_week_gas','rolling week of last week gas',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasR2W1W)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'rolling_week_last_year_gas','rolling week of last year',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasR1WY1)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'rolling_week_last_2_year_gas','rolling week of last 2 years',hass.GAS_TYPE,hass.ST_TT,'m³').setValue(myPce.gasR1WY2)

                    ### Threshold
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'current_month_threshold','threshold of current month',hass.ENERGY_TYPE,hass.ST_TT,'kWh').setValue(myPce.tshM0)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'current_month_threshold_percentage','threshold of current month percentage',hass.NONE_TYPE,hass.ST_TT,'%').setValue(myPce.tshM0Pct)
                    myEntity = hass.Entity(myDevice,hass.BINARY,'current_month_threshold_problem','threshold of current month problem',hass.PROBLEM_TYPE,None,None).setValue(myPce.tshM0Warn)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'previous_month_threshold','threshold of previous month',hass.ENERGY_TYPE,hass.ST_TT,'kWh').setValue(myPce.tshM1)
                    myEntity = hass.Entity(myDevice,hass.SENSOR,'previous_month_threshold_percentage','threshold of previous month percentage',hass.NONE_TYPE,hass.ST_MEAS,'%').setValue(myPce.tshM1Pct)
                    myEntity = hass.Entity(myDevice,hass.BINARY,'previous_month_threshold_problem','threshld of previous month problem',hass.PROBLEM_TYPE,None,None).setValue(myPce.tshM1Warn)

                    ## Other
                    logging.debug("Creation of other entities")
                    myEntity = hass.Entity(myDevice,hass.BINARY,'connectivity','connectivity',hass.CONNECTIVITY_TYPE,None,None).setValue('ON')                                      
                                               
                # Publish config, state (when value not none), attributes (when not none)
                logging.info("Publishing devices...")
                logging.info("You can retrieve published values subscribing topic %s",myDevice.hass.prefix + "/+/" + myDevice.id + "/#")
                for topic,payload in myDevice.getStatePayload().items():
                    myMqtt.publish(topic,payload)
                logging.info("Devices published !")

            # Release memory
            del myHass

        except:
            logging.error("Home Assistant discovery mode : unable to publish value to mqtt broker")
            
    ####################################################################################################################
    # STEP 4a : Prices
    ####################################################################################################################

    logging.info("-----------------------------------------------------------")
    logging.info("#                    Load prices                          #")
    logging.info("-----------------------------------------------------------")

    # Load data from prices file
    logging.info("Loading prices from file %s of directory %s", price.FILE_NAME, myParams.pricePath)
    myPrices = price.Prices(myParams.pricePath, myParams.priceKwhDefault, myParams.priceFixDefault)
    if len(myPrices.pricesList):
        logging.info("%s range(s) of prices found !", len(myPrices.pricesList))
        
    ####################################################################################################################
    # STEP 4b : Prices
    ####################################################################################################################

    logging.info("-----------------------------------------------------------")
    logging.info("#                    Write prices                         #")
    logging.info("-----------------------------------------------------------")
    if myGrdf is not None and myGrdf.isConnected \
        and myDb.isConnected() :

        try:

            cursor = myDb.isConnected()

            # Loop on PCEs
            for myPce in myGrdf.pceList:   
        
                myPcePrices = myPrices.getPricesByPce(myPce.pceId)
                if myPcePrices:
                    # Loop on prices of the PCE and write the current price
                    for myPrice in myPcePrices:
                        #informative / daily values
                        query = f"UPDATE measures SET price= ( energyGrossConsumed * {myPrice.kwhPrice} ) + {myPrice.fixPrice} where pce = '{myPce.pceId}' and type = '{gazpar.TYPE_I}' and date between '{myPrice.startDate}' and '{myPrice.endDate}'"
                        logging.debug("Query_I: %s", query )
                        cursor.execute(query) 
                        myDb.commit()

                        #published / periodic values
                        query = f"UPDATE measures SET price= ( energyGrossConsumed * {myPrice.kwhPrice} ) + ((JulianDay(periodEnd) - JulianDay(periodStart)) * {myPrice.fixPrice}) where pce = '{myPce.pceId}' and type = '{gazpar.TYPE_P}' and date between '{myPrice.startDate}' and '{myPrice.endDate}'"
                        logging.debug("Query_P: %s", query )
                        
                        cursor.execute(query) 

                        myDb.commit()

                else:
                    logging.warning("No prices file found, using the default price (%s €/kWh and %s €/day).", myParams.priceKwhDefault, myParams.priceFixDefault)
                    
                    cursor.execute(f"SELECT pce, type, date, energy, price FROM measures")
                    data = cursor.fetchall()
                    
                    for x in data:
                        try: 
                            cursor.execute(f"UPDATE measures SET price= ( energyGrossConsumed * {myParams.priceKwhDefault} ) + {myParams.priceFixDefault}") 
                            myDb.commit()
                        except Exception as e:
                            logging.error("Writing Prices with default values, error: %s", e)  
                    
                        
        except Exception as e:
            logging.error("Home Assistant Prices error: %s", e)
            
            
    ####################################################################################################################
    # STEP 5C : Home Assistant Long Term statistics
    ####################################################################################################################
    if myParams.hassLts \
        and myGrdf is not None and myGrdf.isConnected \
        and not myParams.hassLtsDelete :
        
        try: 
            logging.info("-----------------------------------------------------------")
            logging.info("#   Home assistant Long Term Statistics (WebService)      #")
            logging.info("-----------------------------------------------------------")

            # Load database in cache
            myDb.load()

            data = {}
            data_pub = {}
            ssl_data= {
                    "gateway": myParams.hassSslGateway,
                    "certfile": myParams.hassSslCertfile,
                    "keyfile": myParams.hassSslKeyfile
                    }    
            # Loop on PCEs
            for myPce in myDb.pceList:
                logging.info("Writing webservice information of PCE %s alias %s...", myPce.pceId, myPce.alias)

                stats_array = []
                stats_array_kwh = []
                stats_array_cost = []
                stats_array_pub = []
                stats_array_kwh_pub = []
                stats_array_pub_cost = []
                prev_stat_sum = 0
                prev_stat_kwh_sum = 0
                prev_stat_pub_sum = 0
                prev_stat_kwh_pub_sum = 0
                prev_price_sum = 0
                prev_price_pub_sum = 0
                for myMeasure in myPce.measureList:
                    date_with_timezone = myMeasure.date.replace(tzinfo=dt.timezone.utc)
                    date_formatted = date_with_timezone.strftime(
                        "%Y-%m-%dT%H:%M:%S%z"
                    )
                    if myMeasure.type == gazpar.TYPE_I :
                        stat = {
                            "start": date_formatted,  # formatted date
                            "state": myMeasure.volumeGross,
                            "sum": prev_stat_sum + myMeasure.volumeGross,
                        }
                        stat_kwh = {
                            "start": date_formatted,  # formatted date
                            "state": myMeasure.energyGross,
                            "sum": prev_stat_kwh_sum + myMeasure.energyGross,
                        }                        
                        stat_cost = {
                            "start": date_formatted,  # formatted date
                            "state": myMeasure.price,
                            "sum": prev_price_sum + myMeasure.price,
                        }
                        stats_array.append(stat)
                        stats_array_kwh.append(stat_kwh)                    
                        stats_array_cost.append(stat_cost)
                        prev_stat_sum = prev_stat_sum + myMeasure.volumeGross
                        prev_stat_kwh_sum = prev_stat_kwh_sum + myMeasure.energyGross
                        prev_price_sum =  prev_price_sum + myMeasure.price                
                    else:
                        stat_pub = {
                            "start": date_formatted,  # formatted date
                            "state": myMeasure.volumeGross,
                            "sum": prev_stat_pub_sum + myMeasure.volumeGross,
                        }   
                        stat_kwh_pub = {
                            "start": date_formatted,  # formatted date
                            "state": myMeasure.energyGross,
                            "sum": prev_stat_kwh_pub_sum + myMeasure.energyGross,
                        }                       
                        stat_cost_pub = {
                            "start": date_formatted,  # formatted date
                            "state": myMeasure.price,
                            "sum": prev_price_pub_sum + myMeasure.price,
                        }
                        stats_array_pub.append(stat_pub)
                        stats_array_kwh_pub.append(stat_kwh_pub)                    
                        stats_array_pub_cost.append(stat_cost_pub)
                        prev_stat_pub_sum = prev_stat_pub_sum + myMeasure.volumeGross
                        prev_stat_kwh_pub_sum = prev_stat_kwh_pub_sum + myMeasure.energyGross
                        prev_price_pub_sum = prev_price_pub_sum + myMeasure.price
                    
                
                sensor_name = 'gazpar:' + myParams.hassDeviceName + '_' + myPce.alias.lower().strip().replace(" ", "_") + '_consumption_stat'
                sensor_name_kwh = 'gazpar:' + myParams.hassDeviceName + '_' + myPce.alias.lower().strip().replace(" ", "_") + '_consumption_kwh_stat'
                sensor_name_pub = 'gazpar:' + myParams.hassDeviceName + '_' + myPce.alias.lower().strip().replace(" ", "_") + '_consumption_pub_stat'
                sensor_name_kwh_pub = 'gazpar:' + myParams.hassDeviceName + '_' + myPce.alias.lower().strip().replace(" ", "_") + '_consumption_kwh_pub_stat'
                sensor_name_cost = 'gazpar:' + myParams.hassDeviceName + '_' + myPce.alias.lower().strip().replace(" ", "_") + '_consumption_cost_stat'
                sensor_name_cost_pub = 'gazpar:' + myParams.hassDeviceName + '_' + myPce.alias.lower().strip().replace(" ", "_") + '_consumption_pub_cost_stat'                
                
                logging.debug(f"Writing Websocket Home Assistant LTS for PCE: {myPce.pceId}, sensor name: {sensor_name}")
                ha_host = myParams.hassHost.replace('http://', '').replace('https://', '')
                HomeAssistantWs("import", myPce.pceId, ha_host, myParams.hassSsl, ssl_data, myParams.hassToken, sensor_name, 'm³', stats_array)
                HomeAssistantWs("import", myPce.pceId, ha_host, myParams.hassSsl, ssl_data, myParams.hassToken, sensor_name_kwh, 'kWh', stats_array_kwh)
                HomeAssistantWs("import", myPce.pceId, ha_host, myParams.hassSsl, ssl_data, myParams.hassToken, sensor_name_cost, 'EUR', stats_array_cost)
                
                logging.debug(f"Writing Websocket Home Assistant Published LTS for PCE: {myPce.pceId}, sensor name: {sensor_name_pub}")
                HomeAssistantWs("import", myPce.pceId, ha_host, myParams.hassSsl, ssl_data, myParams.hassToken, sensor_name_pub, 'm³', stats_array_pub)
                HomeAssistantWs("import", myPce.pceId, ha_host, myParams.hassSsl, ssl_data, myParams.hassToken, sensor_name_kwh_pub, 'kWh', stats_array_kwh_pub)
                HomeAssistantWs("import", myPce.pceId, ha_host, myParams.hassSsl, ssl_data, myParams.hassToken, sensor_name_cost_pub, 'EUR',  stats_array_pub_cost)                
           
        except Exception as e:
            logging.error("Home Assistant Long Term Statistics : unable to publish LTS to Webservice HA with error: %s", e)
            logging.error("Retrying with API") 
                    
            try:
                logging.info("-----------------------------------------------------------")
                logging.info("#      Home assistant Long Term Statistics (API)          #")
                logging.info("-----------------------------------------------------------")

                # Load database in cache
                myDb.load()
                data = {}
                data_pub = {}
                # Loop on PCEs
                for myPce in myDb.pceList:
                    logging.info("Writing api information of PCE %s alias %s...", myPce.pceId, myPce.alias)
                    sensor_name = 'gazpar:' + myParams.hassDeviceName + '_' + myPce.alias.lower().strip().replace(" ", "_") + '_consumption_stat'
                    sensor_name_pub = 'gazpar:' + myParams.hassDeviceName + '_' + myPce.alias.lower().strip().replace(" ", "_") + '_consumption_pub_stat'
                    stats_array = []
                    stats_array_pub = []
                    for myMeasure in myPce.measureList:
                        date_with_timezone = myMeasure.date.replace(tzinfo=dt.timezone.utc)
                        date_formatted = date_with_timezone.strftime(
                            "%Y-%m-%dT%H:%M:%S%z"
                        )
                        stat = {
                            "start": date_formatted,  # formatted date
                            "state": myMeasure.volumeGross,
                            "sum": myMeasure.endIndex,
                        }
                        # Add the stat to the array
                        if myMeasure.type == 'informative':
                            stats_array.append(stat)
                        else:
                            stats_array_pub.append(stat)
                    
                    data = {
                        "has_mean": False,
                        "has_sum": True,
                        "statistic_id": (
                            sensor_name
                                ),
                        "unit_of_measurement": "m³",
                        "source": "recorder",
                        "stats": stats_array,
                    }
                    data_pub = {
                        "has_mean": False,
                        "has_sum": True,
                        "statistic_id": (
                            sensor_name_pub
                                ),
                        "unit_of_measurement": "m³",
                        "source": "recorder",
                        "stats": stats_array_pub,
                    }
                    
                logging.debug(f"Writing HA LTS for PCE: {myPce.pceId}, sensor name: {sensor_name}, data: {data}")
                myGrdf.open_url(myParams.hassHost, myParams.hassStatisticsUri, myParams.hassToken, data)
                logging.debug(f"Writing HA LTS Published for PCE: {myPce.pceId}, sensor name: {sensor_name_pub}, data: {data_pub}")
                myGrdf.open_url(myParams.hassHost, myParams.hassStatisticsUri, myParams.hassToken, data_pub)
            
            except Exception as e:
                logging.error("Home Assistant Long Term Statistics : unable to publish LTS to HA with error: %s", e)            
        

    ####################################################################################################################
    # STEP 5D : Delete Home Assistant Long Term statistics
    ####################################################################################################################
    if myParams.hassLtsDelete :
        
        try: 
            logging.info("------------------------------------------------------------------")
            logging.info("#   Delete Home assistant Long Term Statistics (WebService)      #")
            logging.info("------------------------------------------------------------------")
            
            # Load database in cache
            myDb.load()
            
            ssl_data= {
                    "gateway": myParams.hassSslGateway,
                    "certfile": myParams.hassSslCertfile,
                    "keyfile": myParams.hassSslKeyfile
                    }  
            # Loop on PCEs
            for myPce in myDb.pceList:
                sensor_name = 'gazpar:' + myParams.hassDeviceName + '_' + myPce.alias.lower().strip().replace(" ", "_") + '_consumption_stat'
                sensor_name_kwh = 'gazpar:' + myParams.hassDeviceName + '_' + myPce.alias.lower().strip().replace(" ", "_") + '_consumption_kwh_stat'
                sensor_name_pub = 'gazpar:' + myParams.hassDeviceName + '_' + myPce.alias.lower().strip().replace(" ", "_") + '_consumption_pub_stat'
                sensor_name_kwh_pub = 'gazpar:' + myParams.hassDeviceName + '_' + myPce.alias.lower().strip().replace(" ", "_") + '_consumption_kwh_pub_stat'
                sensor_name_cost = 'gazpar:' + myParams.hassDeviceName + '_' + myPce.alias.lower().strip().replace(" ", "_") + '_consumption_cost_stat'
                sensor_name_cost_pub = 'gazpar:' + myParams.hassDeviceName + '_' + myPce.alias.lower().strip().replace(" ", "_") + '_consumption_pub_cost_stat'                  
                logging.debug(f"Deleting Home Assistant LTS for PCE: {myPce.pceId}, sensor name: {sensor_name}")
                ha_host = myParams.hassHost.replace('http://', '').replace('https://', '')
                HomeAssistantWs("delete", myPce.pceId, ha_host, myParams.hassSsl, ssl_data, myParams.hassToken, sensor_name, None, None)
                HomeAssistantWs("delete", myPce.pceId, ha_host, myParams.hassSsl, ssl_data, myParams.hassToken, sensor_name_kwh, None, None)
                HomeAssistantWs("delete", myPce.pceId, ha_host, myParams.hassSsl, ssl_data, myParams.hassToken, sensor_name_cost, None, None)      
                logging.debug(f"Deleting Home Assistant Published LTS for PCE: {myPce.pceId}, sensor name: {sensor_name_pub}")
                HomeAssistantWs("delete", myPce.pceId, ha_host, myParams.hassSsl, ssl_data, myParams.hassToken, sensor_name_pub, None, None) 
                HomeAssistantWs("delete", myPce.pceId, ha_host, myParams.hassSsl, ssl_data, myParams.hassToken, sensor_name_kwh_pub, None, None)
                HomeAssistantWs("delete", myPce.pceId, ha_host, myParams.hassSsl, ssl_data, myParams.hassToken, sensor_name_cost_pub, None, None)                  

            
        except Exception as e:
                logging.error("Home Assistant Long Term Statistics : unable to delete LTS with error: %s", e)               
                

    ####################################################################################################################
    # STEP 6 : Disconnect mqtt broker
    ####################################################################################################################
    if myMqtt.isConnected:

        logging.info("-----------------------------------------------------------")
        logging.info("#               Disconnection from MQTT                    #")
        logging.info("-----------------------------------------------------------")

        try:
            myMqtt.disconnect()
            logging.info("Mqtt broker disconnected")
        except:
            logging.error("Unable to disconnect mqtt broker")
            sys.exit(1)

    # Release memory
    del myMqtt
    del myGrdf


    ####################################################################################################################
    # STEP 7 : Influxdb
    ####################################################################################################################
    if myParams.influxEnable:

        logging.info("-----------------------------------------------------------")
        logging.info("#            Write to Influxdb v2                         #")
        logging.info("-----------------------------------------------------------")

        # Check Influxdb version
        influxDbVersion = myDb.getConfig(database.INFLUX_KEY)
        if influxDbVersion == G2M_INFLUXDB_VERSION:
            logging.info("Your influxdb version is up to date %s",G2M_INFLUXDB_VERSION)
        else:
            logging.warning("Influxdb version (%s) is not up to date %s", influxDbVersion, G2M_INFLUXDB_VERSION)
            logging.warning("Inconsistencies data could be performed. You should recreate the bucket to delete old data.")
            # Update version
            myDb.updateVersion(database.INFLUX_KEY,G2M_INFLUXDB_VERSION)
            myDb.commit()

        myInflux = influxdb.InfluxDb('v2')
        myInflux.connect(myParams.influxHost, myParams.influxPort, myParams.influxOrg, myParams.influxBucket, myParams.influxToken )

        logging.info("Bucket %s.",myParams.influxBucket)

        # Load database in cache
        myDb.load()

        # Loop on PCEs
        for myPce in myDb.pceList:

            # Sub-step A : Write PCE informations
            logging.info("Writing informations of PCE %s alias %s...", myPce.pceId, myPce.alias)
            point = myInflux.setPcePoint(myPce)
            if not myInflux.write(point):
                logging.warning("Unable to write informations of the PCE.")
            else:
                logging.info("Informations of PCE written successfully !")

            # Sub-step B : Write current price of the PCE
            logging.info("Writing prices of PCE %s alias %s...", myPce.pceId, myPce.alias)
            myPcePrices = myPrices.getPricesByPce(myPce.pceId)
            if myPcePrices:
                # Loop on prices of the PCE and write the current price
                errorCount = 0
                writeCount = 0
                for myPrice in myPcePrices:
                    myDate = datetime.date.today()
                    if myDate >= myPrice.startDate and myDate <= myPrice.endDate:
                        # Set point
                        point = myInflux.setPricePoint(myPce,myPrice,False,None,None)
                        # Write
                        if not myInflux.write(point):
                            logging.error("Unable to write price !")
                        else:
                            writeCount += 1
                logging.info("%s price(s) written successfully !",writeCount)
            else:
                logging.warning("No prices found, use of the default price (%s €/kWh and %s €/day).", myParams.priceKwhDefault, myParams.priceFixDefault)
                point = myInflux.setPricePoint(myPce, None, True, myPrices.defaultKwhPrice,myPrices.defaultFixPrice)
                if not myInflux.write(point):
                    logging.error("Unable to write price !")
                else:
                    logging.info("Default price written successfully !")


            # Sub-step B : Write measures of the PCE
            logging.info("Writing measures of PCE %s alias %s...", myPce.pceId, myPce.alias)
            errorCount = 0
            writeCount = 0
            for myMeasure in myPce.measureList:
                if myMeasure.type == gazpar.TYPE_I:

                    # Set point
                    point = myInflux.setMeasurePoint(myMeasure,myPrices)

                    # Write
                    if not myInflux.write(point):
                        errorCount += 1
                    else:
                        writeCount += 1

                    # Check number of error
                    if errorCount > influxdb.WRITE_MAX_ERROR:
                        logging.warning("Writing stopped because of too many errors.")
                        break
            logging.info("%s measure(s) of PCE written successfully !",writeCount)


            # Sub-step C : Write thresholds of the PCE
            logging.info("Writing thresholds of PCE %s alias %s...", myPce.pceId, myPce.alias)
            errorCount = 0
            writeCount = 0
            for myThreshold in myPce.thresholdList:

                # Set point
                point = myInflux.setThresholdPoint(myThreshold)

                # Write
                if not myInflux.write(point):
                    errorCount += 1
                else:
                    writeCount += 1

                # Check number of error
                if errorCount > influxdb.WRITE_MAX_ERROR:
                    logging.warning("Writing stopped because of too many errors.")
                    break
            logging.info("%s threshold(s) of PCE written successfully !",writeCount)

        # Disconnect
        logging.info("Disconnection of influxdb...")
        myInflux.close()
        logging.info("Influxdb disconnected.")

        # Release memory
        del myInflux

    ####################################################################################################################
    # STEP 7 : Disconnect from database
    ####################################################################################################################
    logging.info("-----------------------------------------------------------")
    logging.info("#          Disconnection from SQLite database              #")
    logging.info("-----------------------------------------------------------")

    if myDb.isConnected() :
        myDb.close()
        logging.info("SQLite database disconnected")
    del myDb

    ####################################################################################################################
    # STEP 8 : Display next run info and end of program
    ####################################################################################################################
    logging.info("-----------------------------------------------------------")
    logging.info("#                Next run                                 #")
    logging.info("-----------------------------------------------------------")
    if myParams.scheduleTime is not None:
        logging.info("gazpar2mqtt next run scheduled at %s",myParams.scheduleTime)
    else:
        logging.info("No schedule defined.")


    logging.info("-----------------------------------------------------------")
    logging.info("#                  End of program                         #")
    logging.info("-----------------------------------------------------------")


########################################################################################################################
#### Main
########################################################################################################################
if __name__ == "__main__":
    
    # Load params
    myParams = param.Params()
        
    # Set logging
    if myParams.debug:
        myLevel = logging.DEBUG
        logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=myLevel)
    else:
        myLevel = logging.INFO
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=myLevel)
    
    
    # Say welcome and be nice
    logging.info("-----------------------------------------------------------")
    logging.info("#               Welcome to gazpar2mqtt                    #")
    logging.info("-----------------------------------------------------------")
    logging.info("Program version : %s",G2M_VERSION)
    logging.info("Database version : %s", G2M_DB_VERSION)
    logging.info("Influxdb version : %s", G2M_INFLUXDB_VERSION)
    logging.info("Please note that the the tool is under development, various functions may disappear or be modified.")
    logging.debug("If you can read this line, you are in DEBUG mode.")
    
    # Log params info
    logging.info("-----------------------------------------------------------")
    logging.info("#                Program parameters                       #")
    logging.info("-----------------------------------------------------------")
    myParams.logParams()
    
    # Check params
    logging.info("Check parameters...")
    if myParams.checkParams():
        logging.info("Parameters are ok !")
    else:
        logging.error("Error on parameters. End of program.")
        quit()

    
    # Run
    if myParams.scheduleTime is not None:
        
        # Run once at lauch
        try:
            run(myParams)
        except Exception as e:
            logging.error("Error during initial run: %s", str(e))
            # Don't exit, continue with scheduling

        # Then run at scheduled time
        schedule.every().day.at(myParams.scheduleTime).do(run, myParams)
        
        # Main scheduling loop with error handling
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Sleep for 1 minute instead of 1 second to reduce CPU usage
            except Exception as e:
                logging.error("Error in scheduling loop: %s", str(e))
                # Wait a bit before retrying to avoid tight error loops
                time.sleep(300)  # 5 minutes
                continue
        
    else:
        
        # Run once
        run(myParams)
        logging.info("End of gazpar2mqtt. See u...")
