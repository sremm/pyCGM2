# -*- coding: utf-8 -*-
import pyCGM2; LOGGER = pyCGM2.LOGGER
import os
import shutil

import pyCGM2
from pyCGM2.Model.CGM2 import cgm
from pyCGM2.Lib.CGM import  cgm2_1
from pyCGM2.Utils import files
from pyCGM2.Utils import utils
from pyCGM2.qtm import qtmTools
from pyCGM2 import enums
from pyCGM2.Tools import btkTools
from  pyCGM2.Lib import eventDetector,report
from pyCGM2.Report import normativeDatasets
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
import argparse

from pyCGM2.Anomaly import AnomalyFilter, AnomalyDetectionProcedure


def command():
    parser = argparse.ArgumentParser(description='CGM21 workflow')
    parser.add_argument('--sessionFile', type=str, help='setting xml file from qtm', default="session.xml")
    parser.add_argument('-ae','--anomalyException', action='store_true', help='stop if anomaly detected ')

    args = parser.parse_args()
    sessionFilename = args.sessionFile
    main(sessionFilename,anomalyException=args.anomalyException)


def main(sessionFilename,createPDFReport=True,checkEventsInMokka=True,anomalyException=False):

    detectAnomaly = False
    LOGGER.set_file_handler("pyCGM2-QTM-Workflow.log")


    LOGGER.logger.info("------------QTM - pyCGM2 Workflow---------------")

    sessionXML = files.readXml(os.getcwd()+"\\",sessionFilename)
    sessionDate = files.getFileCreationDate(os.getcwd()+"\\"+sessionFilename)


    #---------------------------------------------------------------------------
    #management of the Processed folder
    DATA_PATH = os.getcwd()+"\\"+"processed\\"
    files.createDir(DATA_PATH)

    staticMeasurement = qtmTools.findStatic(sessionXML)
    calibrateFilenameLabelled = qtmTools.getFilename(staticMeasurement)
    if not os.path.isfile(DATA_PATH+calibrateFilenameLabelled):
        shutil.copyfile(os.getcwd()+"\\"+calibrateFilenameLabelled,DATA_PATH+calibrateFilenameLabelled)
        LOGGER.logger.info("qualisys exported c3d file [%s] copied to processed folder"%(calibrateFilenameLabelled))

    dynamicMeasurements= qtmTools.findDynamic(sessionXML)
    for dynamicMeasurement in dynamicMeasurements:
        reconstructFilenameLabelled = qtmTools.getFilename(dynamicMeasurement)

        # marker
        order_marker = int(float(dynamicMeasurement.Marker_lowpass_filter_order.text))
        fc_marker = float(dynamicMeasurement.Marker_lowpass_filter_frequency.text)

        if not os.path.isfile(DATA_PATH+reconstructFilenameLabelled):
            shutil.copyfile(os.getcwd()+"\\"+reconstructFilenameLabelled,DATA_PATH+reconstructFilenameLabelled)
            LOGGER.logger.info("qualisys exported c3d file [%s] copied to processed folder"%(reconstructFilenameLabelled))

            acq=btkTools.smartReader(str(DATA_PATH+reconstructFilenameLabelled))

            acq,zeniState = eventDetector.zeni(acq,
                                fc_lowPass_marker=fc_marker,
                                order_lowPass_marker=order_marker)

            if zeniState:
                btkTools.smartWriter(acq, str(DATA_PATH + reconstructFilenameLabelled))
                if checkEventsInMokka:
                    cmd = "Mokka.exe \"%s\""%(str(DATA_PATH + reconstructFilenameLabelled))
                    os.system(cmd)

    # --------------------------GLOBAL SETTINGS ------------------------------------
    # global setting ( in user/AppData)

    if os.path.isfile(pyCGM2.PYCGM2_APPDATA_PATH + "CGM2_1-pyCGM2.settings"):
        settings = files.openFile(pyCGM2.PYCGM2_APPDATA_PATH,"CGM2_1-pyCGM2.settings")
    else:
        settings = files.openFile(pyCGM2.PYCGM2_SETTINGS_FOLDER,"CGM2_1-pyCGM2.settings")
    # --------------------------MP ------------------------------------
    required_mp,optional_mp = qtmTools.SubjectMp(sessionXML)


    #  translators management
    translators = files.getTranslators(os.getcwd()+"\\","CGM2_1.translators")
    if not translators:  translators = settings["Translators"]


    # --------------------------MODEL CALIBRATION -----------------------
    LOGGER.logger.info("--------------------------MODEL CALIBRATION -----------------------")
    staticMeasurement = qtmTools.findStatic(sessionXML)
    calibrateFilenameLabelled = qtmTools.getFilename(staticMeasurement)

    LOGGER.logger.info("----- CALIBRATION-  static file [%s]--"%(calibrateFilenameLabelled))

    leftFlatFoot = utils.toBool(sessionXML.Left_foot_normalised_to_static_trial.text)
    rightFlatFoot = utils.toBool(sessionXML.Right_foot_normalised_to_static_trial.text)
    headFlat = utils.toBool(sessionXML.Head_normalised_to_static_trial.text)
    markerDiameter = float(sessionXML.Marker_diameter.text)*1000.0
    hjcMethod = settings["Calibration"]["HJC"]
    pointSuffix = None

    acqStatic = btkTools.smartReader(DATA_PATH+calibrateFilenameLabelled)

    # Calibration operation
    # --------------------

    model,acqStatic,detectAnomaly = cgm2_1.calibrate(DATA_PATH,
        calibrateFilenameLabelled,
        translators,
        required_mp,optional_mp,
        leftFlatFoot,rightFlatFoot,headFlat,markerDiameter,
        hjcMethod,
        pointSuffix,
        anomalyException=anomalyException)


    LOGGER.logger.info("----- CALIBRATION-  static file [%s]-----> DONE"%(calibrateFilenameLabelled))

    # --------------------------MODEL FITTING ----------------------------------
    LOGGER.logger.info("--------------------------MODEL FITTING ----------------------------------")
    dynamicMeasurements= qtmTools.findDynamic(sessionXML)

    modelledC3ds = list()
    eventInspectorStates = list()
    for dynamicMeasurement in dynamicMeasurements:

        reconstructFilenameLabelled = qtmTools.getFilename(dynamicMeasurement)

        LOGGER.logger.info("----Processing of [%s]-----"%(reconstructFilenameLabelled))
        mfpa = qtmTools.getForcePlateAssigment(dynamicMeasurement)
        momentProjection_text = sessionXML.Moment_Projection.text
        if momentProjection_text == "Default":
            momentProjection_text = settings["Fitting"]["Moment Projection"]
        if momentProjection_text == "Distal":
            momentProjection = enums.MomentProjection.Distal
        elif momentProjection_text == "Proximal":
            momentProjection =   enums.MomentProjection.Proximal
        elif momentProjection_text == "Global":
            momentProjection =   enums.MomentProjection.Global
        elif momentProjection_text == "JCS":
            momentProjection =  enums.MomentProjection.JCS



        acq = btkTools.smartReader(DATA_PATH+reconstructFilenameLabelled)

        # filtering
        # -----------------------

        # marker
        order_marker = int(float(dynamicMeasurement.Marker_lowpass_filter_order.text))
        fc_marker = float(dynamicMeasurement.Marker_lowpass_filter_frequency.text)

        # force plate
        order_fp = int(float(dynamicMeasurement.Forceplate_lowpass_filter_order.text))
        fc_fp = float(dynamicMeasurement.Forceplate_lowpass_filter_frequency.text)


        # event checking
        # -----------------------
        geap = AnomalyDetectionProcedure.GaitEventAnomalyProcedure()
        adf = AnomalyFilter.AnomalyDetectionFilter(acq,reconstructFilenameLabelled,geap)
        anomaly = adf.run()
        if anomaly["ErrorState"]:
            raise Exception ("[pyCGM2] Badly gait event detection. check the log file")

        # fitting operation
        # -----------------------
        acqGait,detectAnomaly = cgm2_1.fitting(model,DATA_PATH, reconstructFilenameLabelled,
            translators,
            markerDiameter,
            pointSuffix,
            mfpa,momentProjection,
            fc_lowPass_marker=fc_marker,
            order_lowPass_marker=order_marker,
            fc_lowPass_forcePlate = fc_fp,
            order_lowPass_forcePlate = order_fp,
            anomalyException=anomalyException)

        outFilename = reconstructFilenameLabelled
        btkTools.smartWriter(acqGait, str(DATA_PATH + outFilename))
        modelledC3ds.append(outFilename)

        LOGGER.logger.info("----Processing of [%s]-----> DONE"%(reconstructFilenameLabelled))


    # --------------------------GAIT PROCESSING -----------------------

    LOGGER.logger.info("---------------------GAIT PROCESSING -----------------------")
    if createPDFReport:
        nds = normativeDatasets.NormativeData("Schwartz2008","Free")

        types = qtmTools.detectMeasurementType(sessionXML)
        for type in types:

            modelledTrials = list()
            for dynamicMeasurement in dynamicMeasurements:
                if  qtmTools.isType(dynamicMeasurement,type):
                    filename = qtmTools.getFilename(dynamicMeasurement)
                    modelledTrials.append(filename)

            report.pdfGaitReport(DATA_PATH,model,modelledTrials, nds,pointSuffix, title = type)
            LOGGER.logger.info("----- Gait Processing -----> DONE")

    LOGGER.logger.info("-------------------------------------------------------")
    if detectAnomaly:
        LOGGER.logger.error("Anomalies has been detected - Find Error messages, then check warning message in the log file")
    else:
        LOGGER.logger.info("workflow return with no detected anomalies")
