# -*- coding: utf-8 -*-
#import ipdb
import logging
import argparse
import matplotlib.pyplot as plt
import numpy as np

# pyCGM2 settings
import pyCGM2
pyCGM2.CONFIG.setLoggingLevel(logging.INFO)

# vicon nexus
import ViconNexus

# pyCGM2 libraries
from pyCGM2.Tools import btkTools
from pyCGM2.Model.CGM2 import cgm,cgm2
from pyCGM2.Model import  modelFilters, modelDecorator
import pyCGM2.enums as pyCGM2Enums
from pyCGM2.Utils import files
from pyCGM2.Nexus import nexusFilters, nexusUtils,nexusTools


def detectSide(acq,left_markerLabel,right_markerLabel):

    flag,vff,vlf = btkTools.findValidFrames(acq,[left_markerLabel,right_markerLabel])

    left = acq.GetPoint(left_markerLabel).GetValues()[vff:vlf,2]
    right = acq.GetPoint(right_markerLabel).GetValues()[vff:vlf,2]

    side = "Left" if np.max(left)>np.max(right) else "Right"

    return side


if __name__ == "__main__":

    plt.close("all")
    DEBUG = False

    parser = argparse.ArgumentParser(description='2Dof Knee Calibration')
    parser.add_argument('-s','--side', type=str, help="Side : Left or Right")
    parser.add_argument('-b','--beginFrame', type=int, help="begin frame")
    parser.add_argument('-e','--endFrame', type=int, help="end frame")
    args = parser.parse_args()

    NEXUS = ViconNexus.ViconNexus()
    NEXUS_PYTHON_CONNECTED = NEXUS.Client.IsConnected()


    if NEXUS_PYTHON_CONNECTED: # run Operation

        # --------------------------PATH + FILE ------------------------------------

        if DEBUG:
            DATA_PATH = pyCGM2.CONFIG.TEST_DATA_PATH + "pyCGM2-Data\\Datasets Tests\\fraser\\New Session\\"
            reconstructedFilenameLabelledNoExt = "15KUFC01_Trial07"
            NEXUS.OpenTrial( str(DATA_PATH+reconstructedFilenameLabelledNoExt), 30 )

            side = "Left"
            args.beginFrame=1073
            args.endFrame=2961

            NEXUS.OpenTrial( str(DATA_PATH+reconstructedFilenameLabelledNoExt), 30 )

        else:
            DATA_PATH, reconstructedFilenameLabelledNoExt = NEXUS.GetTrialName()

        reconstructFilenameLabelled = reconstructedFilenameLabelledNoExt+".c3d"

        logging.info( "data Path: "+ DATA_PATH )
        logging.info( "reconstructed file: "+ reconstructFilenameLabelled)

        # --------------------------SUBJECT -----------------------------------
        # Notice : Work with ONE subject by session
        subjects = NEXUS.GetSubjectNames()
        subject = nexusTools.checkActivatedSubject(NEXUS,subjects)
        logging.info(  "Subject name : " + subject  )

        # --------------------pyCGM2 MODEL - INIT ------------------------------

        model = files.loadModel(DATA_PATH,subject)


        logging.info("loaded model : %s" %(model.version ))

        if model.version == "CGM1.0":
            settings = files.openJson(pyCGM2.CONFIG.PYCGM2_APPDATA_PATH,"CGM1-pyCGM2.settings")
        elif model.version == "CGM1.1":
            settings = files.openJson(pyCGM2.CONFIG.PYCGM2_APPDATA_PATH,"CGM1_1-pyCGM2.settings")
        elif model.version == "CGM2.1":
            settings = files.openJson(pyCGM2.CONFIG.PYCGM2_APPDATA_PATH,"CGM2_1-pyCGM2.settings")
        elif model.version == "CGM2.2":
            settings = files.openJson(pyCGM2.CONFIG.PYCGM2_APPDATA_PATH,"CGM2_2-pyCGM2.settings")
        elif model.version == "CGM2.2e":
            settings = files.openJson(pyCGM2.CONFIG.PYCGM2_APPDATA_PATH,"CGM2_2-Expert-pyCGM2.settings")
        elif model.version == "CGM2.3":
            settings = files.openJson(pyCGM2.CONFIG.PYCGM2_APPDATA_PATH,"CGM2_3-pyCGM2.settings")
        elif model.version == "CGM2.3e":
            settings = files.openJson(pyCGM2.CONFIG.PYCGM2_APPDATA_PATH,"CGM2_3-Expert-pyCGM2.settings")
        elif model.version == "CGM2.4":
            settings = files.openJson(pyCGM2.CONFIG.PYCGM2_APPDATA_PATH,"CGM2_4-pyCGM2.settings")
        elif model.version == "CGM2.4e":
            settings = files.openJson(pyCGM2.CONFIG.PYCGM2_APPDATA_PATH,"CGM2_4-Expert-pyCGM2.settings")
        else:
            raise Exception ("model version not found [contact admin]")

        # --------------------------SESSION INFOS ------------------------------------
        # info file
        info = files.manage_pycgm2SessionInfos(DATA_PATH,subject)

        #  translators management
        if model.version in  ["CGM1.0"]:
            translators = files.manage_pycgm2Translators(DATA_PATH,"CGM1.translators")
        elif model.version in  ["CGM1.1"]:
            translators = files.manage_pycgm2Translators(DATA_PATH,"CGM1-1.translators")
        elif model.version in  ["CGM2.1"]:
            translators = files.manage_pycgm2Translators(DATA_PATH,"CGM2-1.translators")
        elif model.version in  ["CGM2.2","CGM2.2e"]:
            translators = files.manage_pycgm2Translators(DATA_PATH,"CGM2-2.translators")
        elif model.version in  ["CGM2.3","CGM2.3e"]:
            translators = files.manage_pycgm2Translators(DATA_PATH,"CGM2-3.translators")
        elif model.version in  ["CGM2.4","CGM2.4e"]:
            translators = files.manage_pycgm2Translators(DATA_PATH,"CGM2-4.translators")

        if not translators:
           translators = settings["Translators"]


        # --------------------------ACQ WITH TRANSLATORS --------------------------------------

        # --- btk acquisition ----
        acqFunc = btkTools.smartReader(str(DATA_PATH + reconstructFilenameLabelled))

        btkTools.checkMultipleSubject(acqFunc)
        acqFunc =  btkTools.applyTranslators(acqFunc,translators)

        #---get frame range of interest---
        ff = acqFunc.GetFirstFrame()
        lf = acqFunc.GetLastFrame()

        initFrame = args.beginFrame if args.beginFrame is not None else ff
        endFrame = args.endFrame if args.endFrame is not None else lf

        iff=initFrame-ff
        ilf=endFrame-ff

        # motion
        if args.side is None:
            side = detectSide(acqFunc,"LANK","RANK")
            logging.info("Detected motion side : %s" %(side) )
        else:
            side = args.side

        if model.version in  ["CGM1.0","CGM1.1","CGM2.1","CGM2.2","CGM2.2e"]:
            validFrames,vff,vlf = btkTools.findValidFrames(acqFunc,cgm.CGM1LowerLimbs.MARKERS)


        # --------------------------RESET OF THE STATIC File---------

        # load btkAcq from static file
        staticFilename = model.m_staticFilename
        acqStatic = btkTools.smartReader(str(DATA_PATH+staticFilename))
        btkTools.checkMultipleSubject(acqStatic)
        acqStatic =  btkTools.applyTranslators(acqStatic,translators)

        # initial calibration ( i.e calibration from Calibration operation)
        leftFlatFoot = model.m_properties["CalibrationParameters"]["leftFlatFoot"]
        rightFlatFoot = model.m_properties["CalibrationParameters"]["rightFlatFoot"]
        markerDiameter = model.m_properties["CalibrationParameters"]["markerDiameter"]

        if side == "Left":
            # remove other functional calibration
            model.mp_computed["LeftKneeFuncCalibrationOffset"] = 0
        if side == "Right":
            # remove other functional calibration
            model.mp_computed["RightKneeFuncCalibrationOffset"] = 0

        # no rotation on both thigh - re init anatonical frame
        scp=modelFilters.StaticCalibrationProcedure(model)
        modelFilters.ModelCalibrationFilter(scp,acqStatic,model,
                               leftFlatFoot = leftFlatFoot, rightFlatFoot = rightFlatFoot,
                               markerDiameter=markerDiameter).compute()



        # static calibration procedure
        if model.version in  ["CGM1.0","CGM1.1","CGM2.1","CGM2.2","CGM2.2e"]:

            modMotion=modelFilters.ModelMotionFilter(scp,acqFunc,model,pyCGM2Enums.motionMethod.Determinist)
            modMotion.compute()

        elif model.version in  ["CGM2.3","CGM2.3e","CGM2.3","CGM2.4e"]:
            if side == "Left":
                thigh_markers = model.getSegment("Left Thigh").m_tracking_markers
                shank_markers = model.getSegment("Left Shank").m_tracking_markers

            elif side == "Right":
                thigh_markers = model.getSegment("Right Thigh").m_tracking_markers
                shank_markers = model.getSegment("Right Shank").m_tracking_markers

            validFrames,vff,vlf = btkTools.findValidFrames(acqFunc,thigh_markers+shank_markers)

            proximalSegmentLabel=str(side+" Thigh")
            distalSegmentLabel=str(side+" Shank")

            # Motion
            modMotion=modelFilters.ModelMotionFilter(scp,acqFunc,model,pyCGM2Enums.motionMethod.Sodervisk)
            modMotion.segmentalCompute([proximalSegmentLabel,distalSegmentLabel])


        # calibration decorators
        modelDecorator.KneeCalibrationDecorator(model).calibrate2dof(side,
                                                            indexFirstFrame = iff,
                                                            indexLastFrame = ilf )


        # --------------------------FINAL CALIBRATION OF THE STATIC File---------

        # ----  Calibration
        modelFilters.ModelCalibrationFilter(scp,acqStatic,model,
                           leftFlatFoot = leftFlatFoot, rightFlatFoot = rightFlatFoot,
                           markerDiameter=markerDiameter).compute()


        # ----------------------SAVE-------------------------------------------
        files.saveModel(model,DATA_PATH,subject)
        logging.warning("model updated with a  %s knee calibrated with 2Dof method" %(side))

        # ----------------------VICON INTERFACE-------------------------------------------
        #--- update mp
        nexusUtils.updateNexusSubjectMp(NEXUS,model,subject)

        if side == "Left":
            nexusTools.appendBones(NEXUS,subject,acqFunc,"LFE0", model.getSegment("Left Thigh"),OriginValues = acqFunc.GetPoint("LKJC").GetValues() )
        elif side == "Right":
            nexusTools.appendBones(NEXUS,subject,acqFunc,"RFE0", model.getSegment("Right Thigh"),OriginValues = acqFunc.GetPoint("RKJC").GetValues() )

        # --------------------------NEW MOTION FILTER - DISPLAY BONES---------
        if model.version in  ["CGM1.0","CGM1.1","CGM2.1","CGM2.2","CGM2.2e"]:

            modMotion=modelFilters.ModelMotionFilter(scp,acqFunc,model,pyCGM2Enums.motionMethod.Determinist)
            modMotion.compute()

        elif model.version in  ["CGM2.3","CGM2.3e","CGM2.3","CGM2.4e"]:

            # Motion
            modMotion=modelFilters.ModelMotionFilter(scp,acqFunc,model,pyCGM2Enums.motionMethod.Sodervisk)
            modMotion.segmentalCompute([proximalSegmentLabel,distalSegmentLabel])


        # -- add nexus Bones
        if side == "Left":
            nexusTools.appendBones(NEXUS,subject,acqFunc,"LFE1", model.getSegment("Left Thigh"),OriginValues = acqFunc.GetPoint("LKJC").GetValues() )
            logging.warning("offset %s" %(str(model.mp_computed["LeftKneeFuncCalibrationOffset"] )))
        elif side == "Right":
            nexusTools.appendBones(NEXUS,subject,acqFunc,"RFE1", model.getSegment("Right Thigh"),OriginValues = acqFunc.GetPoint("RKJC").GetValues() )
            logging.warning("offset %s" %(str(model.mp_computed["RightKneeFuncCalibrationOffset"] )))

    else:
        raise Exception("NO Nexus connection. Turn on Nexus")
